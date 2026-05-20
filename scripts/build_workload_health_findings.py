#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

from workload_noise_filters import is_operator_managed_object


def compile_matcher(pattern: str):
    regex = re.compile(pattern or r"^$")
    return regex.match


def parse_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def creation_age_days(timestamp: str) -> float:
    text = str(timestamp or "").strip()
    if not text:
        return 0.0
    normalized = re.sub(r"\.\d+Z$", "Z", text)
    created = datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400.0


def ready_counts(pod: dict) -> tuple[int, int]:
    statuses = (((pod or {}).get("status") or {}).get("containerStatuses") or [])
    total = len(statuses)
    ready = sum(1 for status in statuses if status.get("ready") is True)
    return ready, total


def collect_platform_and_user_pod_findings(data: dict) -> dict:
    platform_match = compile_matcher(data.get("platform_namespaces_regex") or r"^$")
    exclude_match = compile_matcher(data.get("user_namespaces_exclude_regex") or r"^$")
    operator_namespaces = data.get("operator_managed_namespace_names") or []
    filter_operator_pods = bool(data.get("filter_operator_managed_user_pods", False))
    include_aged = bool(data.get("include_aged_user_pods", False))
    age_threshold = float(data.get("age_threshold_days", 30))

    platform_pod_issues = []
    unhealthy_user_pods = []
    aged_user_pods = []

    for item in data.get("pods", []) or []:
        metadata = item.get("metadata") or {}
        namespace = str(metadata.get("namespace") or "")
        name = str(metadata.get("name") or "unknown")
        phase = str(((item.get("status") or {}).get("phase") or "Unknown"))
        ready, total = ready_counts(item)

        if platform_match(namespace) and (
            phase not in {"Running", "Succeeded", "Completed"}
            or (phase == "Running" and total > 0 and ready < total)
        ):
            platform_pod_issues.append(
                {
                    "namespace": namespace,
                    "name": name,
                    "phase": phase,
                    "ready": f"{ready}/{total}",
                }
            )

        if exclude_match(namespace):
            continue
        if filter_operator_pods and is_operator_managed_object(item, operator_namespaces):
            continue

        if phase not in {"Running", "Succeeded", "Completed"}:
            unhealthy_user_pods.append(
                {
                    "namespace": namespace,
                    "name": name,
                    "phase": phase,
                    "ready": f"{ready}/{total}",
                }
            )

        if include_aged:
            created_at = str(metadata.get("creationTimestamp") or "")
            if created_at:
                age_days = creation_age_days(created_at)
                if age_days > age_threshold:
                    owner = ((metadata.get("ownerReferences") or []) or [{}])[0] or {}
                    aged_user_pods.append(
                        {
                            "namespace": namespace,
                            "name": name,
                            "phase": phase,
                            "created_at": created_at,
                            "age_days": round(age_days, 1),
                            "owner_kind": str(owner.get("kind") or "none"),
                            "owner_name": str(owner.get("name") or "none"),
                        }
                    )

    return {
        "platform_pod_issues": platform_pod_issues,
        "unhealthy_user_pods": unhealthy_user_pods,
        "aged_user_pods": aged_user_pods,
    }


def pod_spec_for_item(item: dict, collection_name: str) -> dict:
    spec = item.get("spec") or {}
    if collection_name == "deploymentconfigs":
        return ((spec.get("template") or {}).get("spec") or {})
    return (((spec.get("template") or {}).get("spec")) or {})


def labels_for_item(item: dict, collection_name: str) -> dict:
    metadata = item.get("metadata") or {}
    if collection_name == "deploymentconfigs":
        return ((metadata.get("labels") or {}) or {})
    template = (((item.get("spec") or {}).get("template")) or {})
    template_meta = template.get("metadata") or {}
    return (template_meta.get("labels") or metadata.get("labels") or {})


def workload_kind_and_counters(collection_name: str, item: dict) -> tuple[str, int, int, int]:
    spec = item.get("spec") or {}
    status = item.get("status") or {}
    if collection_name == "deployments":
        return (
            "Deployment",
            int(spec.get("replicas", 1) or 1),
            int(status.get("availableReplicas", 0) or 0),
            int(status.get("readyReplicas", 0) or 0),
            int(status.get("updatedReplicas", 0) or 0),
        )
    if collection_name == "statefulsets":
        return (
            "StatefulSet",
            int(spec.get("replicas", 1) or 1),
            int(status.get("currentReplicas", 0) or 0),
            int(status.get("readyReplicas", 0) or 0),
            int(status.get("updatedReplicas", 0) or 0),
        )
    if collection_name == "daemonsets":
        return (
            "DaemonSet",
            int(status.get("desiredNumberScheduled", 0) or 0),
            int(status.get("numberReady", 0) or 0),
            int(status.get("numberReady", 0) or 0),
            int(status.get("updatedNumberScheduled", 0) or 0),
        )
    return (
        "DeploymentConfig",
        int(spec.get("replicas", 1) or 1),
        int(status.get("availableReplicas", 0) or 0),
        int(status.get("readyReplicas", 0) or 0),
        int(status.get("updatedReplicas", 0) or 0),
    )


def collect_workload_findings(data: dict) -> dict:
    exclude_match = compile_matcher(data.get("user_namespaces_exclude_regex") or r"^$")
    operator_namespaces = data.get("operator_managed_namespace_names") or []
    filter_operator_workloads = bool(data.get("filter_operator_managed_workloads", False))
    include_probe_findings = bool(data.get("include_probe_findings", False))
    include_high_replica = bool(data.get("include_high_replica_workloads", False))
    high_replica_threshold = int(data.get("high_replica_threshold", 10) or 10)

    deployment_issues = []
    statefulset_issues = []
    daemonset_issues = []
    deploymentconfig_issues = []
    workload_probe_findings = []
    high_replica_workloads = []

    collections = [
        ("deployments", deployment_issues),
        ("statefulsets", statefulset_issues),
        ("daemonsets", daemonset_issues),
        ("deploymentconfigs", deploymentconfig_issues),
    ]
    for collection_name, issue_bucket in collections:
        for item in data.get(collection_name, []) or []:
            metadata = item.get("metadata") or {}
            namespace = str(metadata.get("namespace") or "")
            if exclude_match(namespace):
                continue
            if filter_operator_workloads and is_operator_managed_object(item, operator_namespaces):
                continue

            kind, desired, available, ready, updated = workload_kind_and_counters(collection_name, item)
            name = str(metadata.get("name") or "unknown")
            if desired > 0:
                mismatch = (
                    (kind in {"Deployment", "DeploymentConfig"} and (available < desired or ready < desired or updated < desired))
                    or (kind == "StatefulSet" and (ready < desired or updated < desired))
                    or (kind == "DaemonSet" and (available < desired or updated < desired))
                )
                if mismatch:
                    issue_bucket.append(
                        {
                            "kind": kind,
                            "namespace": namespace,
                            "name": name,
                            "desired": desired,
                            "available": available,
                            "ready": ready,
                            "updated": updated,
                        }
                    )

            if include_high_replica and desired > high_replica_threshold:
                high_replica_workloads.append(
                    {
                        "kind": kind,
                        "namespace": namespace,
                        "name": name,
                        "replicas": desired,
                    }
                )

            if include_probe_findings and kind in {"Deployment", "StatefulSet", "DaemonSet"}:
                containers = (pod_spec_for_item(item, collection_name).get("containers") or [])
                if not containers:
                    continue
                missing_liveness = [str(c.get("name") or "unknown") for c in containers if c.get("livenessProbe") is None]
                missing_readiness = [str(c.get("name") or "unknown") for c in containers if c.get("readinessProbe") is None]
                missing_startup = [str(c.get("name") or "unknown") for c in containers if c.get("startupProbe") is None]
                for issue_name, names in (
                    ("missing-liveness-probe", missing_liveness),
                    ("missing-readiness-probe", missing_readiness),
                    ("missing-startup-probe", missing_startup),
                ):
                    if names:
                        workload_probe_findings.append(
                            {
                                "kind": kind,
                                "namespace": namespace,
                                "name": name,
                                "issue": issue_name,
                                "containers": names,
                                "detail": ", ".join(names),
                            }
                        )

    workload_health_issues = deployment_issues + statefulset_issues + daemonset_issues + deploymentconfig_issues
    return {
        "deployment_issues": deployment_issues,
        "statefulset_issues": statefulset_issues,
        "daemonset_issues": daemonset_issues,
        "deploymentconfig_issues": deploymentconfig_issues,
        "workload_health_issues": workload_health_issues,
        "high_replica_workloads": high_replica_workloads,
        "workload_probe_findings": workload_probe_findings,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_workload_health_findings.py <input-json-path>"}))
        return 2

    data = parse_json(sys.argv[1])
    payload = {}
    payload.update(collect_platform_and_user_pod_findings(data))
    payload.update(collect_workload_findings(data))
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
