#!/usr/bin/env python3
"""Build common workload health, resilience, and probe findings in one pass."""

import json
import sys

from build_workload_health_findings import (
    collect_platform_and_user_pod_findings,
    collect_workload_findings,
)
from build_workload_probe_findings import build_probe_findings_for_kind, get_path
from build_workload_resilience import build as build_resilience


EMPTY_RESILIENCE = {
    "findings": [],
    "pdb_review_findings": [],
    "multi_replica_workload_count": 0,
    "multi_replica_workloads_without_pdb": 0,
    "multi_replica_workloads_without_usable_pdb": 0,
    "multi_replica_workloads_without_spread_policy": 0,
    "multi_replica_workloads_with_node_or_zone_spread_policy": 0,
    "multi_replica_workloads_with_other_spread_policy": 0,
}


def build_probe_findings(data, graph):
    exclude_regex = str(data.get("user_namespaces_exclude_regex") or "")
    operator_namespaces = set(data.get("operator_managed_namespace_names") or [])
    findings = list(data.get("workload_probe_findings") or [])
    findings.extend(
        build_probe_findings_for_kind(
            get_path(graph, "deployments", "items", default=[]) or [],
            "Deployment",
            exclude_regex,
            operator_namespaces,
        )
    )
    findings.extend(
        build_probe_findings_for_kind(
            get_path(graph, "statefulsets", "items", default=[]) or [],
            "StatefulSet",
            exclude_regex,
            operator_namespaces,
        )
    )
    findings.extend(
        build_probe_findings_for_kind(
            get_path(graph, "daemonsets", "items", default=[]) or [],
            "DaemonSet",
            exclude_regex,
            operator_namespaces,
        )
    )
    return findings


def build(data):
    graph = data.get("analysis_graph") or {}
    operator_namespaces = data.get("operator_managed_namespace_names") or []

    health_input = {
        "pods": get_path(graph, "pods", "items", default=[]) or [],
        "deployments": get_path(graph, "deployments", "items", default=[]) or [],
        "statefulsets": get_path(graph, "statefulsets", "items", default=[]) or [],
        "daemonsets": get_path(graph, "daemonsets", "items", default=[]) or [],
        "platform_namespaces_regex": data.get("platform_namespaces_regex") or "^$",
        "user_namespaces_exclude_regex": data.get("user_namespaces_exclude_regex") or "^$",
        "operator_managed_namespace_names": operator_namespaces,
        "filter_operator_managed_user_pods": True,
        "filter_operator_managed_workloads": True,
        "include_aged_user_pods": True,
        "age_threshold_days": 30,
        "include_high_replica_workloads": True,
        "high_replica_threshold": 10,
        "include_probe_findings": False,
    }

    workload_health = {}
    workload_health.update(collect_platform_and_user_pod_findings(health_input))
    workload_health.update(collect_workload_findings(health_input))

    resilience_input = {
        "deployments": get_path(graph, "deployments", "items", default=[]) or [],
        "statefulsets": get_path(graph, "statefulsets", "items", default=[]) or [],
        "deploymentconfigs": get_path(graph, "deploymentconfigs", "items", default=[]) or [],
        "poddisruptionbudgets": get_path(graph, "poddisruptionbudgets", "items", default=[]) or [],
        "exclude_regex": data.get("user_namespaces_exclude_regex") or "^$",
        "operator_managed_namespace_names": operator_namespaces,
    }
    resilience = build_resilience(resilience_input) or dict(EMPTY_RESILIENCE)
    probe_findings = build_probe_findings(data, graph)

    return {
        "workload_health_findings_data": workload_health,
        "platform_pod_issues": workload_health.get("platform_pod_issues", []),
        "unhealthy_user_pods": workload_health.get("unhealthy_user_pods", []),
        "aged_user_pods": workload_health.get("aged_user_pods", []),
        "deployment_issues": workload_health.get("deployment_issues", []),
        "statefulset_issues": workload_health.get("statefulset_issues", []),
        "daemonset_issues": workload_health.get("daemonset_issues", []),
        "workload_health_issues": workload_health.get("workload_health_issues", []),
        "high_replica_workloads": workload_health.get("high_replica_workloads", []),
        "workload_resilience_data": resilience,
        "workload_practice_findings_append": resilience.get("findings", []),
        "workload_probe_findings": probe_findings,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_common_workload_analysis_bundle.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
