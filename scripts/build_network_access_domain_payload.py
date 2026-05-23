#!/usr/bin/env python3
"""Build the OpenShift network and application access domain payload."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Review route and ingress health, exposed-namespace isolation, and proxy or "
    "egress posture before treating network access as production-ready."
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
    artifact = data.get("network_access_posture_artifact") or {}
    render_inputs = data.get("network_access_posture_render_inputs") or {}
    summary = data.get("network_architecture_summary") or {}

    collected = mode == "collected"
    route_issue_key = "assessment_route_issues" if collected else "top_route_issues"
    route_conflict_key = "route_host_conflicts" if collected else "top_route_host_conflicts"
    ingress_issue_key = "ingress_issues" if collected else "top_ingress_issues"
    ingress_conflict_key = "ingress_host_conflicts" if collected else "top_ingress_host_conflicts"
    service_key = "services_without_endpoints" if collected else "top_services_without_endpoints"
    ingress_count_key = "analysis_graph_ingress_count" if collected else "ingresses_items_count"

    return {
        "summary": first_defined(nested_get(artifact, "summary"), default=summary),
        "recommendations": first_defined(
            nested_get(artifact, "recommendations"),
            default=get(summary, "recommendation", RECOMMENDATION),
        ),
        "route_object_count": first_defined(
            nested_get(artifact, "route_object_count"),
            nested_get(render_inputs, "route_object_count"),
            default=len(data.get("assessment_route_summary") or []),
        ),
        "ingress_object_count": first_defined(
            nested_get(artifact, "ingress_object_count"),
            nested_get(render_inputs, "ingress_object_count"),
            default=data.get(ingress_count_key) or 0,
        ),
        "routes": (data.get("assessment_route_summary") or []) if collected else [],
        "route_issues": first_defined(
            nested_get(artifact, "route_issues"),
            nested_get(render_inputs, "route_issues"),
            default=data.get(route_issue_key) or [],
        ),
        "route_host_conflicts": first_defined(
            nested_get(artifact, "route_host_conflicts"),
            nested_get(render_inputs, "route_host_conflicts"),
            default=data.get(route_conflict_key) or [],
        ),
        "ingress_issues": first_defined(
            nested_get(artifact, "ingress_issues"),
            nested_get(render_inputs, "ingress_issues"),
            default=data.get(ingress_issue_key) or [],
        ),
        "ingress_host_conflicts": first_defined(
            nested_get(artifact, "ingress_host_conflicts"),
            nested_get(render_inputs, "ingress_host_conflicts"),
            default=data.get(ingress_conflict_key) or [],
        ),
        "route_ingress_host_conflicts": first_defined(
            nested_get(artifact, "route_ingress_host_conflicts"),
            nested_get(render_inputs, "route_ingress_host_conflicts"),
            default=data.get("route_ingress_host_conflicts") or [],
        ),
        "services_without_endpoints": first_defined(
            nested_get(artifact, "services_without_endpoints"),
            nested_get(render_inputs, "services_without_endpoints"),
            default=data.get(service_key) or [],
        ),
        "ingresscontrollers": {
            "summary": first_defined(
                nested_get(artifact, "ingresscontrollers", "summary"),
                nested_get(render_inputs, "ingresscontrollers_summary"),
                default=data.get("ingresscontroller_summary") or [],
            ),
            "issues": first_defined(
                nested_get(artifact, "ingresscontrollers", "issues"),
                nested_get(render_inputs, "ingresscontrollers_issues"),
                default=data.get("ingresscontroller_issues") or [],
            ),
        },
    }


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
