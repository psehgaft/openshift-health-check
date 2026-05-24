#!/usr/bin/env python3
"""Build the OpenShift workload health domain payload from existing facts."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Review unhealthy user pods, rollout failures, restart hotspots, probe coverage, "
    "resource hygiene, ownership, labels, and rightsizing context before treating "
    "workload posture as healthy."
)


def get(data, key, default=None):
    if isinstance(data, dict) and key in data:
        return data[key]
    return default


def first_defined(*values, default=None):
    for value in values:
        if value is not MISSING:
            return value
    return default


def nested_get(data, *keys, default=MISSING):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def sorted_restart_hotspots(items):
    if not isinstance(items, list):
        return []
    return sorted(items, key=lambda item: get(item, "restarts", 0) if isinstance(item, dict) else 0, reverse=True)[:15]


def resilience_summary(data):
    data = data if isinstance(data, dict) else {}
    return {
        "multi_replica_workload_count": get(data, "multi_replica_workload_count", 0),
        "multi_replica_workloads_without_pdb": get(data, "multi_replica_workloads_without_pdb", 0),
        "multi_replica_workloads_without_usable_pdb": get(data, "multi_replica_workloads_without_usable_pdb", 0),
        "multi_replica_workloads_without_spread_policy": get(data, "multi_replica_workloads_without_spread_policy", 0),
        "multi_replica_workloads_with_node_or_zone_spread_policy": get(
            data, "multi_replica_workloads_with_node_or_zone_spread_policy", 0
        ),
        "multi_replica_workloads_with_other_spread_policy": get(
            data, "multi_replica_workloads_with_other_spread_policy", 0
        ),
    }


def build_payload(data):
    mode = data.get("mode") or "live"
    artifact = data.get("workload_health_posture_artifact") or {}
    render_inputs = data.get("workload_health_posture_render_inputs") or {}
    summary = data.get("workload_health_summary") or {}
    resilience = data.get("workload_resilience_data") or {}

    payload = {
        "summary": first_defined(nested_get(artifact, "summary"), default=summary),
        "recommendations": first_defined(
            nested_get(artifact, "recommendations"),
            default=get(summary, "recommendation", RECOMMENDATION),
        ),
        "metric_source_status": first_defined(
            nested_get(artifact, "metric_source_status"),
            nested_get(render_inputs, "metric_source_status"),
            default=data.get("audit_report_observability_prometheus_status")
            or get(data.get("prometheus_evidence_summary") or {}, "status", "not-collected"),
        ),
        "platform_pod_issues": first_defined(
            nested_get(artifact, "platform_pod_issues"),
            nested_get(render_inputs, "platform_pod_issues"),
            default=data.get("platform_pod_issues") or [],
        ),
        "workload_resilience_findings": first_defined(
            nested_get(artifact, "workload_resilience_findings"),
            nested_get(render_inputs, "workload_resilience_findings"),
            default=(data.get("top_workload_resilience_findings") if mode == "live" else None)
            or get(resilience, "findings", []),
        ),
        "workload_resilience_pdb_review_findings": first_defined(
            nested_get(artifact, "workload_resilience_pdb_review_findings"),
            nested_get(render_inputs, "workload_resilience_pdb_review_findings"),
            default=(data.get("top_workload_resilience_pdb_review_findings") if mode == "live" else None)
            or get(resilience, "pdb_review_findings", []),
        ),
        "workload_resilience_summary": first_defined(
            nested_get(artifact, "workload_resilience_summary"),
            nested_get(render_inputs, "workload_resilience_summary"),
            default=resilience_summary(resilience),
        ),
        "workload_probe_issue_type_counts": first_defined(
            nested_get(artifact, "workload_probe_issue_type_counts"),
            nested_get(render_inputs, "workload_probe_issue_type_counts"),
            default=data.get("workload_probe_issue_type_counts") or {},
        ),
        "top_pod_cpu_usage_summary": first_defined(
            nested_get(artifact, "top_pod_cpu_usage_summary"),
            nested_get(render_inputs, "top_pod_cpu_usage_summary"),
            default=data.get("top_pod_cpu_usage_summary") or [],
        ),
        "top_pod_memory_usage_summary": first_defined(
            nested_get(artifact, "top_pod_memory_usage_summary"),
            nested_get(render_inputs, "top_pod_memory_usage_summary"),
            default=data.get("top_pod_memory_usage_summary") or [],
        ),
    }

    fallback_names = {
        "unhealthy_user_pods": "top_unhealthy_user_pods" if mode == "live" else "unhealthy_user_pods",
        "workload_health_issues": "top_workload_health_issues" if mode == "live" else "workload_health_issues",
        "high_replica_workloads": "top_high_replica_workloads" if mode == "live" else "high_replica_workloads",
        "orphan_pods": "top_orphan_pods" if mode == "live" else "orphan_pods",
        "workload_label_governance_findings": (
            "top_workload_label_governance_findings" if mode == "live" else "workload_label_governance_findings"
        ),
        "node_label_governance_findings": (
            "top_node_label_governance_findings" if mode == "live" else "node_label_governance_findings"
        ),
        "workload_resource_findings": "top_workload_resource_findings" if mode == "live" else "workload_resource_findings",
        "workload_probe_findings": "top_workload_probe_findings" if mode == "live" else "workload_probe_findings",
        "overprovisioned_pods": "top_overprovisioned_pods" if mode == "live" else "overprovisioned_pods",
        "services_without_endpoints": "top_services_without_endpoints" if mode == "live" else "services_without_endpoints",
        "stale_user_pods": "top_stale_user_pods" if mode == "live" else "top_stale_user_pods",
        "stale_configmaps": "top_stale_configmaps" if mode == "live" else "top_stale_configmaps",
        "stale_generic_secrets": "top_stale_generic_secrets" if mode == "live" else "top_stale_generic_secrets",
        "stale_dockerconfigjson_secrets": (
            "top_stale_dockerconfigjson_secrets" if mode == "live" else "top_stale_dockerconfigjson_secrets"
        ),
        "likely_unused_configmaps": "top_likely_unused_configmaps" if mode == "live" else "top_likely_unused_configmaps",
        "likely_unused_secrets": "top_likely_unused_secrets" if mode == "live" else "top_likely_unused_secrets",
    }
    for payload_key, fallback_key in fallback_names.items():
        payload[payload_key] = first_defined(
            nested_get(artifact, payload_key),
            nested_get(render_inputs, payload_key),
            default=data.get(fallback_key) or [],
        )

    if mode == "live":
        payload["restart_hotspots"] = first_defined(
            nested_get(artifact, "restart_hotspots"),
            nested_get(render_inputs, "restart_hotspots"),
            default=data.get("top_high_restart_pods") or [],
        )
        payload["aged_user_pods"] = first_defined(
            nested_get(artifact, "aged_user_pods"),
            nested_get(render_inputs, "aged_user_pods"),
            default=data.get("top_aged_user_pods") or [],
        )
    else:
        payload["restart_hotspots"] = first_defined(
            nested_get(artifact, "restart_hotspots"),
            nested_get(render_inputs, "restart_hotspots"),
            default=sorted_restart_hotspots(data.get("pod_restart_hotspots") or []),
        )

    return payload


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
