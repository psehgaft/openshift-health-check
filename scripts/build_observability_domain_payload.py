#!/usr/bin/env python3
"""Build the OpenShift observability domain payload."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Review monitoring health, alert-routing, log forwarding, and metrics "
    "forwarding before treating observability as production-ready."
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
    artifact = data.get("observability_posture_artifact") or {}
    render_inputs = data.get("observability_posture_render_inputs") or {}
    summary = data.get("observability_summary") or {}

    collected = mode == "collected"
    findings_key = "observability_findings" if collected else "top_observability_findings"
    connected_posture_default = (
        data.get("assessment_connected_cluster_posture")
        or data.get("connected_cluster_posture")
        or {}
        if collected
        else {}
    )
    connected_findings_default = (
        data.get("assessment_connected_cluster_findings")
        or data.get("connected_cluster_findings")
        or []
        if collected
        else []
    )
    advisor_summary_default = (
        data.get("advisor_summary") or {}
        if collected
        else data.get("live_advisor_export_summary") or {}
    )
    advisor_findings_default = (
        data.get("advisor_findings") or []
        if collected
        else data.get("top_live_advisor_findings") or []
    )

    return {
        "summary": first_defined(nested_get(artifact, "summary"), default=summary),
        "recommendations": first_defined(
            nested_get(artifact, "recommendations"),
            default=get(summary, "recommendation", RECOMMENDATION),
        ),
        "forwarding_summary": first_defined(
            nested_get(artifact, "forwarding_summary"),
            nested_get(render_inputs, "forwarding_summary"),
            default=data.get("observability_forwarding_summary") or {},
        ),
        "prometheus_query": first_defined(
            nested_get(artifact, "prometheus_query"),
            nested_get(render_inputs, "prometheus_query"),
            default=data.get("prometheus_evidence_summary") or {},
        ),
        "findings": first_defined(
            nested_get(artifact, "findings"),
            nested_get(render_inputs, "findings"),
            default=data.get(findings_key) or [],
        ),
        "connected_cluster_posture": first_defined(
            nested_get(artifact, "connected_cluster_posture"),
            nested_get(render_inputs, "connected_cluster_posture"),
            default=connected_posture_default,
        ),
        "connected_cluster_findings": first_defined(
            nested_get(artifact, "connected_cluster_findings"),
            nested_get(render_inputs, "connected_cluster_findings"),
            default=connected_findings_default,
        ),
        "advisor_summary": first_defined(
            nested_get(artifact, "advisor_summary"),
            nested_get(render_inputs, "advisor_summary"),
            default=advisor_summary_default,
        ),
        "advisor_findings": first_defined(
            nested_get(artifact, "advisor_findings"),
            nested_get(render_inputs, "advisor_findings"),
            default=advisor_findings_default,
        ),
        "insights_archive_summary": first_defined(
            nested_get(artifact, "insights_archive_summary"),
            nested_get(render_inputs, "insights_archive_summary"),
            default=data.get("insights_archive_summary") or {},
        ),
        "insights_archive_findings": first_defined(
            nested_get(artifact, "insights_archive_findings"),
            nested_get(render_inputs, "insights_archive_findings"),
            default=data.get("insights_archive_findings") or [],
        ),
    }


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
