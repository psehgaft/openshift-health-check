#!/usr/bin/env python3
"""Build the collected-state OpenShift domain payload."""

import json
import sys


SUPPORTABILITY_RECOMMENDATION = (
    "Resolve the named unsupported, review-required, or incomplete supportability "
    "conditions before using lower-priority sections for final sign-off."
)
CAPACITY_RECOMMENDATION = (
    "Use the baseline and growth tables to plan scaling, upgrades, and workload placement."
)
LIFECYCLE_RECOMMENDATION = (
    "Review lifecycle support status, upgrade readiness, and failure-domain spread before "
    "treating the architecture posture as production-ready."
)
DECLARATIVE_RECOMMENDATION = (
    "Review declarative operations evidence, managed-cluster registration, and supporting "
    "identity, backup, machine-remediation, and lifecycle context before treating "
    "declarative operations as strong."
)
RELEASE_RECOMMENDATION = (
    "Review failed pipelines, build-automation ownership, and cluster-hosted runner health "
    "before treating release engineering as healthy."
)
DAY2_RECOMMENDATION = (
    "Use the owning posture sections and capability sections as the remediation queue, and "
    "rerun the assessment when blockers or incomplete evidence are cleared."
)


def nested_get(data, *keys, default=None):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def first_defined(*values, default=None):
    for value in values:
        if value is not None:
            return value
    return default


def field(source, key, default=None):
    if isinstance(source, dict) and key in source:
        return source[key]
    return default


def recommendation(summary, fallback):
    if isinstance(summary, dict):
        return summary.get("recommendation") or fallback
    return fallback


def resolve_capability_sections(data):
    resolved = data.get("day2_capability_sections_artifact_resolved")
    if isinstance(resolved, list) and resolved:
        return resolved

    sections = data.get("day2_capability_sections") or []
    artifact_sections = data.get("openshift_capability_artifact_sections") or {}
    if not isinstance(artifact_sections, dict):
        artifact_sections = {}

    artifacts = data.get("openshift_capability_artifacts") or {}
    for key, artifact in artifacts.items():
        if key in artifact_sections:
            continue
        section = field(artifact, "section", {})
        if isinstance(section, dict) and section:
            artifact_sections[key] = section

    resolved = []
    for section in sections:
        section_key = field(section, "key", "")
        if section_key and section_key in artifact_sections:
            resolved.append(artifact_sections[section_key])
        else:
            resolved.append(section)
    return resolved


def build_supportability(data):
    artifact = data.get("supportability_posture_artifact") or {}
    render_inputs = data.get("supportability_posture_render_inputs") or {}
    return {
        "summary": first_defined(
            field(artifact, "summary"),
            field(render_inputs, "supportability_summary"),
            data.get("supportability_summary"),
            default={},
        ),
        "recommendations": field(
            artifact, "recommendations", SUPPORTABILITY_RECOMMENDATION
        ),
        "diagnostics_coverage": first_defined(
            field(artifact, "diagnostics_coverage"),
            field(render_inputs, "diagnostics_coverage"),
            data.get("diagnostics_coverage"),
            default={},
        ),
        "product_evidence": first_defined(
            field(artifact, "product_evidence"),
            field(render_inputs, "product_evidence"),
            data.get("assessment_product_evidence"),
            default={},
        ),
        "product_evidence_findings": first_defined(
            field(artifact, "product_evidence_findings"),
            field(render_inputs, "product_evidence_findings"),
            data.get("assessment_product_evidence_findings"),
            default=[],
        ),
        "connected_cluster_posture": first_defined(
            field(artifact, "connected_cluster_posture"),
            field(render_inputs, "connected_cluster_posture"),
            data.get("assessment_connected_cluster_posture"),
            data.get("connected_cluster_posture"),
            default={},
        ),
        "connected_cluster_findings": first_defined(
            field(artifact, "connected_cluster_findings"),
            field(render_inputs, "connected_cluster_findings"),
            data.get("assessment_connected_cluster_findings"),
            data.get("connected_cluster_findings"),
            default=[],
        ),
        "connected_cluster_advisor_summary": first_defined(
            field(artifact, "connected_cluster_advisor_summary"),
            field(render_inputs, "connected_cluster_advisor_summary"),
            data.get("advisor_summary"),
            default={},
        ),
        "node_diagnostics_summary": first_defined(
            field(artifact, "node_diagnostics_summary"),
            field(render_inputs, "node_diagnostics_summary"),
            data.get("node_diagnostics_summary"),
            default={},
        ),
        "node_diagnostics_findings": first_defined(
            field(artifact, "node_diagnostics_findings"),
            field(render_inputs, "node_diagnostics_findings"),
            data.get("node_diagnostics_findings"),
            default=[],
        ),
        "advisor_summary": first_defined(
            field(artifact, "advisor_summary"),
            field(render_inputs, "advisor_summary"),
            data.get("advisor_summary"),
            default={},
        ),
        "advisor_findings": first_defined(
            field(artifact, "advisor_findings"),
            field(render_inputs, "advisor_findings"),
            data.get("advisor_findings"),
            default=[],
        ),
        "insights_archive_summary": first_defined(
            field(artifact, "insights_archive_summary"),
            field(render_inputs, "insights_archive_summary"),
            data.get("insights_archive_summary"),
            default={},
        ),
        "insights_archive_findings": first_defined(
            field(artifact, "insights_archive_findings"),
            field(render_inputs, "insights_archive_findings"),
            data.get("insights_archive_findings"),
            default=[],
        ),
        "evidence_coverage": first_defined(
            field(artifact, "evidence_coverage"),
            field(render_inputs, "evidence_coverage"),
            data.get("evidence_coverage"),
            default={},
        ),
    }


def build_lifecycle(data):
    artifact = data.get("architecture_lifecycle_posture_artifact") or {}
    render_inputs = data.get("architecture_lifecycle_posture_render_inputs") or {}
    summary = first_defined(
        field(artifact, "summary"), data.get("architecture_lifecycle_summary"), default={}
    )
    return {
        "summary": summary,
        "architecture_lifecycle_summary": summary,
        "upgrade_readiness_summary": first_defined(
            field(artifact, "upgrade_readiness_summary"),
            field(render_inputs, "upgrade_readiness_summary"),
            data.get("upgrade_readiness_summary"),
            default={},
        ),
        "recommendations": field(
            artifact, "recommendations", recommendation(summary, LIFECYCLE_RECOMMENDATION)
        ),
        "reference_compliance_summary": first_defined(
            field(artifact, "reference_compliance_summary"),
            field(render_inputs, "reference_compliance_summary"),
            data.get("reference_compliance_summary"),
            default={},
        ),
        "reference_compliance_findings": first_defined(
            field(artifact, "reference_compliance_findings"),
            field(render_inputs, "reference_compliance_findings"),
            data.get("reference_compliance_findings"),
            default=[],
        ),
        "managed_gate_summary": first_defined(
            field(artifact, "managed_gate_summary"),
            field(render_inputs, "managed_gate_summary"),
            data.get("managed_gate_summary"),
            default={},
        ),
        "managed_gate_findings": first_defined(
            field(artifact, "managed_gate_findings"),
            field(render_inputs, "managed_gate_findings"),
            data.get("managed_gate_findings"),
            default=[],
        ),
        "topology_resilience": first_defined(
            field(artifact, "topology_resilience"),
            field(render_inputs, "topology_resilience"),
            data.get("topology_resilience"),
            default={},
        ),
        "available_updates": first_defined(
            field(artifact, "available_updates"),
            field(render_inputs, "available_updates"),
            data.get("available_updates"),
            default=[],
        ),
        "conditional_updates": first_defined(
            field(artifact, "conditional_updates"),
            field(render_inputs, "conditional_updates"),
            data.get("conditional_updates"),
            default=[],
        ),
        "cluster_update_history": first_defined(
            field(artifact, "cluster_update_history"),
            field(render_inputs, "cluster_update_history"),
            data.get("cluster_update_history"),
            default=[],
        ),
        "deprecated_crd_findings": first_defined(
            field(artifact, "deprecated_crd_findings"),
            field(render_inputs, "deprecated_crd_findings"),
            data.get("top_deprecated_crd_findings"),
            default=[],
        ),
        "deprecated_api_lines": first_defined(
            field(artifact, "deprecated_api_lines"),
            field(render_inputs, "deprecated_api_lines"),
            data.get("top_deprecated_api_lines"),
            default=[],
        ),
        "cluster_compare_findings": first_defined(
            field(artifact, "cluster_compare_findings"),
            field(render_inputs, "cluster_compare_findings"),
            data.get("top_live_cluster_compare_findings"),
            default=[],
        ),
        "managed_gate_top_findings": first_defined(
            field(artifact, "managed_gate_top_findings"),
            field(render_inputs, "managed_gate_top_findings"),
            data.get("top_live_managed_gate_findings"),
            default=[],
        ),
    }


def build_capacity(data):
    artifact = data.get("capacity_snapshot_posture_artifact") or {}
    render_inputs = data.get("capacity_snapshot_posture_render_inputs") or {}
    return {
        "summary": field(artifact, "summary", {}),
        "recommendations": field(artifact, "recommendations", CAPACITY_RECOMMENDATION),
        "cluster_current_state": first_defined(
            field(artifact, "cluster_current_state"),
            field(render_inputs, "cluster_current_state"),
            data.get("cluster_current_state"),
            default={},
        ),
        "cluster_profile": first_defined(
            field(artifact, "cluster_profile"),
            field(render_inputs, "cluster_profile"),
            data.get("openshift_artifact_backed_cluster_profile"),
            data.get("cluster_profile"),
            default={},
        ),
        "architecture_lifecycle_summary": first_defined(
            field(artifact, "architecture_lifecycle_summary"),
            field(render_inputs, "architecture_lifecycle_summary"),
            data.get("architecture_lifecycle_summary"),
            default={},
        ),
        "cluster_current_state_sanity_findings": first_defined(
            field(artifact, "cluster_current_state_sanity_findings"),
            field(render_inputs, "cluster_current_state_sanity_findings"),
            data.get("cluster_current_state_sanity_findings"),
            default=[],
        ),
        "cluster_current_state_build_error": first_defined(
            field(artifact, "cluster_current_state_build_error"),
            field(render_inputs, "cluster_current_state_build_error"),
            data.get("cluster_current_state_build_error"),
            default="",
        ),
        "runtime_signal_resolution_map": first_defined(
            field(artifact, "runtime_signal_resolution_map"),
            field(render_inputs, "runtime_signal_resolution_map"),
            data.get("runtime_signal_resolution_map"),
            default={},
        ),
    }


def build_declarative(data):
    artifact = data.get("declarative_operations_posture_artifact") or {}
    render_inputs = data.get("declarative_operations_posture_render_inputs") or {}
    summary = data.get("declarative_operations_summary") or {}
    return {
        "summary": first_defined(field(artifact, "summary"), summary, default={}),
        "declarative_operations_summary": first_defined(
            field(artifact, "declarative_operations_summary"),
            field(render_inputs, "declarative_operations_summary"),
            summary,
            default={},
        ),
        "recommendations": field(
            artifact, "recommendations", recommendation(summary, DECLARATIVE_RECOMMENDATION)
        ),
    }


def build_release_engineering(data):
    artifact = data.get("release_engineering_posture_artifact") or {}
    render_inputs = data.get("release_engineering_posture_render_inputs") or {}
    summary = data.get("release_engineering_adoption_summary") or {}
    return {
        "summary": first_defined(field(artifact, "summary"), summary, default={}),
        "release_engineering_adoption_summary": first_defined(
            field(artifact, "release_engineering_adoption_summary"),
            field(render_inputs, "release_engineering_adoption_summary"),
            summary,
            default={},
        ),
        "recommendations": field(
            artifact, "recommendations", recommendation(summary, RELEASE_RECOMMENDATION)
        ),
        "cicd_runner_summary": first_defined(
            field(artifact, "cicd_runner_summary"),
            field(render_inputs, "cicd_runner_summary"),
            nested_get(summary, "runner_summary"),
            default={},
        ),
        "cicd_runner_findings": first_defined(
            field(artifact, "cicd_runner_findings"),
            field(render_inputs, "cicd_runner_findings"),
            nested_get(summary, "runner_findings"),
            default=[],
        ),
        "buildconfig_strategy_counts": first_defined(
            field(artifact, "buildconfig_strategy_counts"),
            field(render_inputs, "buildconfig_strategy_counts"),
            data.get("buildconfig_strategy_counts"),
            default={},
        ),
        "pipelinerun_status_counts": first_defined(
            field(artifact, "pipelinerun_status_counts"),
            field(render_inputs, "pipelinerun_status_counts"),
            data.get("pipelinerun_status_counts"),
            default={},
        ),
        "failed_pipelineruns": first_defined(
            field(artifact, "failed_pipelineruns"),
            field(render_inputs, "failed_pipelineruns"),
            data.get("top_failed_pipelineruns"),
            default=[],
        ),
        "buildconfigs_without_triggers": first_defined(
            field(artifact, "buildconfigs_without_triggers"),
            field(render_inputs, "buildconfigs_without_triggers"),
            data.get("top_buildconfigs_without_triggers"),
            default=[],
        ),
    }


def build_day2(data):
    artifact = data.get("day2_readiness_posture_artifact") or {}
    render_inputs = data.get("day2_readiness_posture_render_inputs") or {}
    day2_summary = data.get("day2_posture_summary") or {}
    day2_readiness_summary = data.get("day2_production_readiness_summary") or {}
    declarative_artifact = data.get("declarative_operations_posture_artifact") or {}
    declarative_render_inputs = data.get("declarative_operations_posture_render_inputs") or {}
    release_artifact = data.get("release_engineering_posture_artifact") or {}
    release_render_inputs = data.get("release_engineering_posture_render_inputs") or {}
    declarative_summary = data.get("declarative_operations_summary") or {}

    return {
        "summary": first_defined(
            field(artifact, "summary"),
            field(render_inputs, "day2_production_readiness_summary"),
            day2_readiness_summary,
            default={},
        ),
        "declarative_operations_summary": first_defined(
            field(declarative_artifact, "declarative_operations_summary"),
            field(declarative_render_inputs, "declarative_operations_summary"),
            declarative_summary,
            default={},
        ),
        "day2_posture_summary": first_defined(
            field(artifact, "day2_posture_summary"),
            field(render_inputs, "day2_posture_summary"),
            day2_summary,
            default={},
        ),
        "day2_production_readiness_summary": first_defined(
            field(artifact, "day2_production_readiness_summary"),
            field(render_inputs, "day2_production_readiness_summary"),
            day2_readiness_summary,
            default={},
        ),
        "operations_recommendations": field(
            declarative_artifact,
            "recommendations",
            recommendation(declarative_summary, DECLARATIVE_RECOMMENDATION),
        ),
        "recommendations": field(
            artifact,
            "recommendations",
            recommendation(day2_readiness_summary, DAY2_RECOMMENDATION),
        ),
        "release_engineering_adoption_summary": first_defined(
            field(release_artifact, "release_engineering_adoption_summary"),
            field(release_render_inputs, "release_engineering_adoption_summary"),
            data.get("release_engineering_adoption_summary"),
            default={},
        ),
        "checks": first_defined(
            field(artifact, "checks"),
            field(render_inputs, "checks"),
            data.get("day2_posture_checks"),
            default=[],
        ),
        "findings": first_defined(
            field(artifact, "findings"),
            field(render_inputs, "findings"),
            data.get("day2_posture_findings"),
            default=[],
        ),
        "capability_sections": first_defined(
            field(artifact, "capability_sections"),
            field(render_inputs, "capability_sections"),
            resolve_capability_sections(data),
            data.get("day2_capability_sections"),
            default=[],
        ),
        "capability_assessment_state": first_defined(
            field(artifact, "capability_assessment_state"),
            field(render_inputs, "capability_assessment_state"),
            nested_get(day2_summary, "capability_assessment_state"),
            default="unknown",
        ),
        "capability_assessment_error": first_defined(
            field(artifact, "capability_assessment_error"),
            field(render_inputs, "capability_assessment_error"),
            nested_get(day2_summary, "capability_assessment_error"),
            default="",
        ),
        "product_evidence": first_defined(
            field(artifact, "product_evidence"),
            field(render_inputs, "product_evidence"),
            data.get("assessment_product_evidence"),
            default={},
        ),
        "product_evidence_findings": first_defined(
            field(artifact, "product_evidence_findings"),
            field(render_inputs, "product_evidence_findings"),
            data.get("assessment_product_evidence_findings"),
            default=[],
        ),
        "builds": {
            "buildconfigs_without_triggers": first_defined(
                field(release_artifact, "buildconfigs_without_triggers"),
                field(release_render_inputs, "buildconfigs_without_triggers"),
                data.get("buildconfigs_without_triggers"),
                default=[],
            )
        },
        "pipelines": {
            "failed_pipelineruns": first_defined(
                field(release_artifact, "failed_pipelineruns"),
                field(release_render_inputs, "failed_pipelineruns"),
                data.get("failed_pipelineruns"),
                default=[],
            )
        },
    }


def build_payload(data):
    return {
        "evidence_and_supportability": build_supportability(data),
        "platform_health": data.get("platform_health_domain_payload") or {},
        "observability": data.get("observability_domain_payload") or {},
        "node_health_and_capacity": data.get("node_health_domain_payload") or {},
        "upgrade_and_lifecycle_risk": build_lifecycle(data),
        "capacity_planning_snapshot": build_capacity(data),
        "declarative_operations": build_declarative(data),
        "container_platform_adoption_and_release_engineering": build_release_engineering(data),
        "production_day2_readiness": build_day2(data),
        "security_and_governance": data.get("security_governance_domain_payload") or {},
        "network_and_application_access": data.get("network_access_domain_payload") or {},
        "workload_health": data.get("workload_health_domain_payload") or {},
        "storage_and_resilience": data.get("storage_resilience_domain_payload") or {},
    }


def main():
    data = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
