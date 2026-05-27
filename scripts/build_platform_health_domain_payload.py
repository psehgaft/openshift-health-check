#!/usr/bin/env python3
"""Build the OpenShift platform health domain payload."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Core platform health is acceptable for this run. Keep operator availability, "
    "node readiness, routing, and control-plane runtime signals under normal "
    "review while you work lower-priority posture items."
)


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


def first_non_empty(*values, default=None):
    for value in values:
        if value is MISSING:
            continue
        if value in (None, "", [], {}, ()):  # preserve explicit scalars, skip empty containers
            continue
        return value
    return default


def build_payload(data):
    mode = data.get("mode") or "live"
    artifact = data.get("platform_health_posture_artifact") or {}
    render_inputs = data.get("platform_health_posture_render_inputs") or {}
    collected = mode == "collected"

    summary_default = (
        data.get("core_platform_health_summary")
        or (data.get("assessment_health_summary") or {})
        if collected
        else data.get("core_platform_health_summary") or (data.get("health_summary") or {})
    )
    findings_default = (
        data.get("core_platform_health_findings")
        or (data.get("assessment_health_findings") or [])
        if collected
        else data.get("core_platform_health_findings") or []
    )
    operators_default = data.get("assessment_operator_status_summary") or [] if collected else []
    omc_findings_default = (
        data.get("omc_findings") or []
        if collected
        else data.get("top_live_omc_findings") or []
    )
    apiservice_issues_default = (
        data.get("apiservice_issues") or []
        if collected
        else data.get("top_apiservice_issues") or []
    )
    image_registry_default = {
        "findings": first_defined(
            nested_get(render_inputs, "image_registry_findings"),
            default=(
                data.get("image_registry_findings") or []
                if collected
                else data.get("top_image_registry_findings") or []
            ),
        ),
        "feature_findings": first_defined(
            nested_get(render_inputs, "feature_findings"),
            default=(
                data.get("feature_findings") or []
                if collected
                else data.get("top_feature_findings") or []
            ),
        ),
        "internal_registry_workloads": first_defined(
            nested_get(render_inputs, "internal_registry_workloads"),
            default=(
                data.get("internal_registry_workloads") or []
                if collected
                else data.get("top_internal_registry_workloads") or []
            ),
        ),
    }

    payload = {
        "summary": first_non_empty(
            nested_get(artifact, "summary"),
            nested_get(render_inputs, "summary"),
            default=summary_default,
        ),
        "recommendations": first_non_empty(
            nested_get(artifact, "recommendations"),
            default=RECOMMENDATION,
        ),
        "findings": first_non_empty(
            nested_get(artifact, "findings"),
            nested_get(render_inputs, "findings"),
            default=findings_default,
        ),
        "operators": first_non_empty(
            nested_get(artifact, "operators"),
            first_non_empty(nested_get(render_inputs, "operators")),
            default=operators_default,
        ),
        "infrastructure_components": first_non_empty(
            nested_get(artifact, "infrastructure_components"),
            default={
                "summary": first_defined(
                    nested_get(render_inputs, "infrastructure_component_summary"),
                    default=data.get("infrastructure_component_summary") or [],
                ),
                "issues": first_defined(
                    nested_get(render_inputs, "infrastructure_component_issues"),
                    default=data.get("infrastructure_component_issues") or [],
                ),
            },
        ),
        "etcd_ocp_diag_summary": first_non_empty(
            nested_get(artifact, "etcd_ocp_diag_summary"),
            first_non_empty(nested_get(render_inputs, "etcd_ocp_diag_summary")),
            default=data.get("etcd_ocp_diag_summary") or {},
        ),
        "etcd_ocp_diag_findings": first_non_empty(
            nested_get(artifact, "etcd_ocp_diag_findings"),
            first_non_empty(nested_get(render_inputs, "etcd_ocp_diag_findings")),
            default=data.get("etcd_ocp_diag_findings") or [],
        ),
        "omc_summary": first_non_empty(
            nested_get(artifact, "omc_summary"),
            first_non_empty(nested_get(render_inputs, "omc_summary")),
            default=data.get("omc_summary") or {},
        ),
        "omc_findings": first_non_empty(
            nested_get(artifact, "omc_findings"),
            first_non_empty(nested_get(render_inputs, "omc_findings")),
            default=omc_findings_default,
        ),
        "apiservice_issues": first_non_empty(
            nested_get(artifact, "apiservice_issues"),
            first_non_empty(nested_get(render_inputs, "apiservice_issues")),
            default=apiservice_issues_default,
        ),
        "image_registry": first_non_empty(
            nested_get(artifact, "image_registry"),
            default=image_registry_default,
        ),
    }

    if collected:
        payload["control_plane_query_status_map"] = first_defined(
            nested_get(artifact, "control_plane_query_status_map"),
            nested_get(render_inputs, "control_plane_query_status_map"),
            default=data.get("control_plane_query_status_map") or {},
        )
        payload["apiserver_readyz_status"] = first_defined(
            nested_get(artifact, "apiserver_readyz_status"),
            nested_get(render_inputs, "apiserver_readyz_status"),
            default=data.get("apiserver_readyz_status") or "not-collected",
        )
        payload["apiserver_readyz_failed_checks"] = first_defined(
            nested_get(artifact, "apiserver_readyz_failed_checks"),
            nested_get(render_inputs, "apiserver_readyz_failed_checks"),
            default=data.get("apiserver_readyz_failed_checks") or 0,
        )

    return payload


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
