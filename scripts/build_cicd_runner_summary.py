#!/usr/bin/env python3
"""Summarize cluster-hosted CI/CD runner and agent workload signals."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROVIDER_PATTERNS = {
    "gitlab-runner": [
        "gitlab-runner",
        "gitlab.com/runner",
        "ci_server_url",
    ],
    "jenkins-agent": [
        "jenkins-agent",
        "jenkins/slave",
        "jenkins/inbound-agent",
        "jenkins_agent_name",
        "jenkins_secret",
        "jnlp",
    ],
    "github-actions-runner": [
        "actions-runner",
        "gha-runner",
        "githubactionsrunner",
        "actions.github.com",
        "runner-scale-set",
        "runnerdeployment",
        "runnerreplicaset",
        "ephemeralrunner",
        "ephemeralrunnerset",
    ],
    "azure-devops-agent": [
        "azure-pipelines-agent",
        "azure-devops-agent",
        "azdo-agent",
        "vsts-agent",
        "azp_url",
        "azp_token",
        "azp_pool",
    ],
    "generic-runner": [
        "ci-runner",
        "cicd-runner",
        "build-runner",
    ],
}

RUNNER_WORD_RE = re.compile(r"(runner|agent|jenkins|gitlab|github-actions|azure-pipelines|azdo|vsts)", re.I)
SYSTEM_NAMESPACE_RE = re.compile(r"^(kube-|openshift-|default$)")


def items(graph: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = graph.get(key, {})
    if isinstance(value, dict):
        raw_items = value.get("items", [])
        return raw_items if isinstance(raw_items, list) else []
    return []


def metadata_text(resource: dict[str, Any]) -> str:
    metadata = resource.get("metadata", {}) or {}
    labels = metadata.get("labels", {}) or {}
    annotations = metadata.get("annotations", {}) or {}
    parts = [
        metadata.get("name", ""),
        metadata.get("namespace", ""),
        " ".join(f"{k}={v}" for k, v in labels.items()),
        " ".join(f"{k}={v}" for k, v in annotations.items()),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def pod_text(pod: dict[str, Any]) -> str:
    spec = pod.get("spec", {}) or {}
    containers = (spec.get("containers", []) or []) + (spec.get("initContainers", []) or [])
    parts = [metadata_text(pod), spec.get("serviceAccountName", "")]
    for container in containers:
        parts.extend([container.get("name", ""), container.get("image", "")])
        for env in container.get("env", []) or []:
            parts.append(env.get("name", ""))
    return " ".join(str(part) for part in parts if part).lower()


def classify_provider(text: str) -> str:
    for provider, patterns in PROVIDER_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            return provider
    if RUNNER_WORD_RE.search(text):
        return "generic-runner"
    return ""


def pod_ready(pod: dict[str, Any]) -> bool:
    statuses = ((pod.get("status", {}) or {}).get("containerStatuses", []) or [])
    if not statuses:
        return False
    return all(bool(status.get("ready")) for status in statuses)


def pod_restarts(pod: dict[str, Any]) -> int:
    statuses = ((pod.get("status", {}) or {}).get("containerStatuses", []) or [])
    return sum(int(status.get("restartCount") or 0) for status in statuses)


def waiting_reasons(pod: dict[str, Any]) -> list[str]:
    statuses = ((pod.get("status", {}) or {}).get("containerStatuses", []) or [])
    reasons = []
    for status in statuses:
        waiting = (status.get("state", {}) or {}).get("waiting", {}) or {}
        reason = waiting.get("reason")
        if reason:
            reasons.append(str(reason))
    return reasons


def pod_unschedulable(pod: dict[str, Any]) -> bool:
    if ((pod.get("status", {}) or {}).get("phase") or "") != "Pending":
        return False
    for condition in ((pod.get("status", {}) or {}).get("conditions", []) or []):
        if condition.get("type") == "PodScheduled" and condition.get("status") == "False":
            reason = str(condition.get("reason") or "").lower()
            message = str(condition.get("message") or "").lower()
            return "unschedulable" in reason or "insufficient" in message or "didn't match" in message
    return False


def pod_privileged(pod: dict[str, Any]) -> bool:
    spec = pod.get("spec", {}) or {}
    containers = (spec.get("containers", []) or []) + (spec.get("initContainers", []) or [])
    for container in containers:
        security_context = container.get("securityContext", {}) or {}
        if security_context.get("privileged") is True:
            return True
    return False


def pod_has_requests(pod: dict[str, Any]) -> bool:
    spec = pod.get("spec", {}) or {}
    containers = spec.get("containers", []) or []
    if not containers:
        return False
    for container in containers:
        requests = ((container.get("resources", {}) or {}).get("requests", {}) or {})
        if not requests.get("cpu") or not requests.get("memory"):
            return False
    return True


def pod_summary(pod: dict[str, Any], provider: str) -> dict[str, Any]:
    metadata = pod.get("metadata", {}) or {}
    status = pod.get("status", {}) or {}
    phase = status.get("phase") or "not-assessed"
    reasons = waiting_reasons(pod)
    return {
        "namespace": metadata.get("namespace", "not-assessed"),
        "name": metadata.get("name", "not-assessed"),
        "provider": provider,
        "phase": phase,
        "ready": pod_ready(pod),
        "restarts": pod_restarts(pod),
        "node": (pod.get("spec", {}) or {}).get("nodeName", "not-assessed"),
        "waiting_reasons": reasons,
        "unschedulable": pod_unschedulable(pod),
        "privileged": pod_privileged(pod),
        "has_cpu_memory_requests": pod_has_requests(pod),
    }


def detect_controller_resources(graph: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for key in ("deployments", "statefulsets", "daemonsets", "replicasets"):
        for resource in items(graph, key):
            provider = classify_provider(metadata_text(resource))
            if provider:
                counts[provider] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_cicd_runner_summary.py <input-json-path>"}))
        return 2

    graph = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    runner_pods = []
    for pod in items(graph, "pods"):
        text = pod_text(pod)
        provider = classify_provider(text)
        if not provider:
            continue
        namespace = ((pod.get("metadata", {}) or {}).get("namespace") or "")
        if SYSTEM_NAMESPACE_RE.match(namespace) and provider == "generic-runner":
            continue
        runner_pods.append(pod_summary(pod, provider))

    provider_counts = Counter(pod["provider"] for pod in runner_pods)
    phase_counts = Counter(pod["phase"] for pod in runner_pods)
    unhealthy = [
        pod for pod in runner_pods
        if pod["phase"] not in {"Running", "Succeeded"} or not pod["ready"] or pod["restarts"] > 0
    ]
    pending = [pod for pod in runner_pods if pod["phase"] == "Pending"]
    unschedulable = [pod for pod in runner_pods if pod["unschedulable"]]
    privileged = [pod for pod in runner_pods if pod["privileged"]]
    missing_requests = [pod for pod in runner_pods if not pod["has_cpu_memory_requests"]]
    restart_total = sum(pod["restarts"] for pod in runner_pods)

    controller_counts = detect_controller_resources(graph)
    metric_hint = (
        "runner-native metrics were not detected from collected Kubernetes objects; use Prometheus/Thanos "
        "or product APIs for queue depth, busy runner count, job duration, and failure-rate trends"
    )

    summary = {
        "present": bool(runner_pods or controller_counts),
        "runner_pod_count": len(runner_pods),
        "running_ready_pod_count": sum(1 for pod in runner_pods if pod["phase"] == "Running" and pod["ready"]),
        "unhealthy_pod_count": len(unhealthy),
        "pending_pod_count": len(pending),
        "unschedulable_pod_count": len(unschedulable),
        "restart_total": restart_total,
        "privileged_pod_count": len(privileged),
        "missing_requests_pod_count": len(missing_requests),
        "provider_counts": dict(sorted(provider_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "controller_counts": controller_counts,
        "metrics_coverage": "not-derived",
        "metrics_guidance": metric_hint,
        "top_unhealthy_pods": sorted(unhealthy, key=lambda item: (not item["unschedulable"], -item["restarts"], item["namespace"], item["name"]))[:10],
        "top_runner_pods": sorted(runner_pods, key=lambda item: (item["provider"], item["namespace"], item["name"]))[:15],
    }

    findings = []
    if summary["present"]:
        findings.append({
            "finding": "Cluster-hosted runner footprint",
            "severity": "INFO",
            "current_state": f"runnerPods={summary['runner_pod_count']}, providers={summary['provider_counts'] or summary['controller_counts']}",
            "business_impact": "CI/CD jobs consume cluster compute and can compete with application workloads during delivery bursts.",
            "technical_evidence": f"phases={summary['phase_counts']}, controllers={summary['controller_counts']}",
            "recommended_action": "Track runner pods separately from application workloads and align runner namespace quotas, priorities, and node placement with delivery demand.",
        })
    if unhealthy or unschedulable:
        findings.append({
            "finding": "Runner health and scheduling pressure",
            "severity": "WARNING",
            "current_state": f"unhealthy={len(unhealthy)}, pending={len(pending)}, unschedulable={len(unschedulable)}, restarts={restart_total}",
            "business_impact": "Unhealthy or unschedulable runners can increase CI/CD queue time and delay production fixes.",
            "technical_evidence": f"top={summary['top_unhealthy_pods'][:5]}",
            "recommended_action": "Check runner pod events, namespace quota, node selectors, tolerations, image pulls, secrets, and node capacity before scaling additional delivery workloads.",
        })
    if privileged or missing_requests:
        findings.append({
            "finding": "Runner isolation and resource governance",
            "severity": "WARNING" if privileged else "INFO",
            "current_state": f"privilegedPods={len(privileged)}, missingCpuMemoryRequests={len(missing_requests)}",
            "business_impact": "Privileged or unbounded runners increase blast radius and make delivery workload capacity less predictable.",
            "technical_evidence": f"providers={summary['provider_counts']}",
            "recommended_action": "Use dedicated namespaces, least-privilege service accounts, explicit CPU and memory requests, quotas, and dedicated nodes or taints for high-volume runner pools.",
        })
    if summary["present"]:
        findings.append({
            "finding": "Runner-native metrics coverage",
            "severity": "INFO",
            "current_state": "metricsCoverage=not-derived",
            "business_impact": "Without runner-native metrics, the report can see pod health but not CI/CD queue depth, busy runner percentage, or job-duration trends.",
            "technical_evidence": summary["metrics_guidance"],
            "recommended_action": "Expose and scrape runner/controller metrics where available, then use Prometheus/Thanos or the CI/CD product API to report busy runners, queued jobs, job duration, and failure rate.",
        })

    print(json.dumps({"summary": summary, "findings": findings}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
