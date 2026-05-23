#!/usr/bin/env python3
"""Build the OpenShift node health and capacity domain payload."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Review node readiness, pressure, pod density, capacity hotspots, quota "
    "pressure, metric-backed utilization, and node diagnostics coverage before "
    "treating node capacity as healthy."
)


def get(data, key, default=None):
    if isinstance(data, dict) and key in data:
        return data[key]
    return default


def nested_get(data, *keys, default=MISSING):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def first_defined(*values, default=None):
    for value in values:
        if value is not MISSING:
            return value
    return default


def build_payload(data):
    mode = data.get("mode") or "live"
    artifact = data.get("node_health_posture_artifact") or {}
    render_inputs = data.get("node_health_posture_render_inputs") or {}
    summary = data.get("node_health_capacity_summary") or {}

    collected = mode == "collected"
    diagnostics_findings_default = (
        data.get("node_diagnostics_findings") or []
        if collected
        else (data.get("top_live_inspect_findings") or [])
        + (data.get("top_live_sosreport_findings") or [])
    )
    machineconfigpools_default = (
        data.get("assessment_mcp_summary") or []
        if collected
        else data.get("cluster_current_state_machineconfigpools") or []
    )

    return {
        "summary": first_defined(nested_get(artifact, "summary"), default=summary),
        "recommendations": first_defined(
            nested_get(artifact, "recommendations"),
            default=get(summary, "recommendation", RECOMMENDATION),
        ),
        "diagnostics_summary": first_defined(
            nested_get(artifact, "diagnostics_summary"),
            default=data.get("node_diagnostics_summary") or {},
        ),
        "diagnostics_findings": first_defined(
            nested_get(artifact, "diagnostics_findings"),
            default=diagnostics_findings_default,
        ),
        "machineconfigpools": first_defined(
            nested_get(artifact, "machineconfigpools"),
            nested_get(render_inputs, "machineconfigpools"),
            default=machineconfigpools_default,
        ),
        "nodes": first_defined(
            nested_get(artifact, "nodes"),
            nested_get(render_inputs, "nodes"),
            default=data.get("openshift_node_items") or [],
        ),
        "quota_pressure_findings": first_defined(
            nested_get(artifact, "quota_pressure_findings"),
            nested_get(render_inputs, "quota_pressure_findings"),
            default=data.get("top_quota_pressure_findings") or [],
        ),
        "node_capacity_summary_by_density_desc": first_defined(
            nested_get(artifact, "node_capacity_summary_by_density_desc"),
            nested_get(render_inputs, "node_capacity_summary_by_density_desc"),
            default=data.get("node_capacity_summary_by_density_desc") or [],
        ),
        "node_capacity_summary_by_density_asc": first_defined(
            nested_get(artifact, "node_capacity_summary_by_density_asc"),
            nested_get(render_inputs, "node_capacity_summary_by_density_asc"),
            default=data.get("node_capacity_summary_by_density_asc") or [],
        ),
        "high_pod_density_nodes": first_defined(
            nested_get(artifact, "high_pod_density_nodes"),
            nested_get(render_inputs, "high_pod_density_nodes"),
            default=data.get("high_pod_density_nodes") or [],
        ),
        "high_cpu_nodes": first_defined(
            nested_get(artifact, "high_cpu_nodes"),
            nested_get(render_inputs, "high_cpu_nodes"),
            default=data.get("high_cpu_nodes") or [],
        ),
        "high_memory_nodes": first_defined(
            nested_get(artifact, "high_memory_nodes"),
            nested_get(render_inputs, "high_memory_nodes"),
            default=data.get("high_memory_nodes") or [],
        ),
        "high_disk_nodes": first_defined(
            nested_get(artifact, "high_disk_nodes"),
            nested_get(render_inputs, "high_disk_nodes"),
            default=data.get("high_disk_nodes") or [],
        ),
    }


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
