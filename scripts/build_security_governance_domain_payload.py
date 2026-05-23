#!/usr/bin/env python3
"""Build the OpenShift security and governance domain payload."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Review identity posture, privileged access, certificate hygiene, and active "
    "compliance standards before treating security and governance as "
    "production-ready."
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


def section_get(artifact, section, key, default):
    return first_defined(nested_get(artifact, section, key), default=default)


def build_payload(data):
    mode = data.get("mode") or "live"
    collected = mode == "collected"
    artifact = data.get("security_governance_posture_artifact") or {}
    render_inputs = data.get("security_governance_posture_render_inputs") or {}
    summary = data.get("security_compliance_summary") or {}

    namespace_hygiene = {
        "user_namespaces": section_get(
            artifact, "namespace_hygiene", "user_namespaces", data.get("user_namespace_names") or []
        ),
        "namespaces_without_networkpolicy": section_get(
            artifact,
            "namespace_hygiene",
            "namespaces_without_networkpolicy",
            data.get("namespaces_without_networkpolicy") or [],
        ),
        "namespaces_without_resourcequota": section_get(
            artifact,
            "namespace_hygiene",
            "namespaces_without_resourcequota",
            data.get("namespaces_without_resourcequota") or [],
        ),
        "namespaces_without_limitrange": section_get(
            artifact,
            "namespace_hygiene",
            "namespaces_without_limitrange",
            data.get("namespaces_without_limitrange") or [],
        ),
        "empty_user_namespaces": section_get(
            artifact,
            "namespace_hygiene",
            "empty_user_namespaces",
            data.get("empty_user_namespaces") or [],
        ),
        "namespaces_missing_ingress_policies": section_get(
            artifact,
            "namespace_hygiene",
            "namespaces_missing_ingress_policies",
            data.get("namespaces_missing_ingress_policies") or [],
        ),
        "namespaces_missing_egress_policies": section_get(
            artifact,
            "namespace_hygiene",
            "namespaces_missing_egress_policies",
            data.get("namespaces_missing_egress_policies") or [],
        ),
        "metadata_governance_findings": section_get(
            artifact,
            "namespace_hygiene",
            "metadata_governance_findings",
            first_defined(
                nested_get(render_inputs, "namespace_metadata_governance_findings"),
                default=data.get("top_namespace_metadata_governance_findings") or [],
            ),
        ),
    }
    if collected:
        namespace_hygiene["node_metadata_governance_findings"] = section_get(
            artifact,
            "namespace_hygiene",
            "node_metadata_governance_findings",
            first_defined(
                nested_get(render_inputs, "node_metadata_governance_findings"),
                default=data.get("top_node_metadata_governance_findings") or [],
            ),
        )

    compliance_findings_key = (
        "compliance_suite_findings" if collected else "top_compliance_suite_findings"
    )
    standards_findings_key = (
        "compliance_standards_findings"
        if collected
        else "top_compliance_standards_findings"
    )
    access_serviceaccounts_key = (
        "stale_access_review_serviceaccounts"
        if collected
        else "top_stale_access_review_serviceaccounts"
    )
    access_users_key = (
        "stale_access_review_users" if collected else "top_stale_access_review_users"
    )
    access_groups_key = (
        "stale_access_review_groups" if collected else "top_stale_access_review_groups"
    )

    return {
        "summary": first_defined(nested_get(artifact, "summary"), default=summary),
        "recommendations": first_defined(
            nested_get(artifact, "recommendations"),
            default=get(summary, "recommendation", RECOMMENDATION),
        ),
        "auth_posture_summary": first_defined(
            nested_get(artifact, "auth_posture_summary"),
            default=data.get("auth_posture_summary") or {},
        ),
        "auth_findings": first_defined(
            nested_get(artifact, "auth_findings"),
            nested_get(render_inputs, "auth_findings"),
            default=data.get("auth_findings") or [],
        ),
        "namespace_hygiene": namespace_hygiene,
        "pod_security": {
            "issue_type_counts": section_get(
                artifact,
                "pod_security",
                "issue_type_counts",
                first_defined(
                    nested_get(render_inputs, "pod_security_issue_type_counts"),
                    default=data.get("security_issue_type_counts") or {},
                ),
            ),
            "findings": section_get(
                artifact,
                "pod_security",
                "findings",
                first_defined(
                    nested_get(render_inputs, "pod_security_findings"),
                    default=data.get("top_security_findings") or [],
                ),
            ),
            "findings_total": section_get(
                artifact,
                "pod_security",
                "findings_total",
                first_defined(
                    nested_get(render_inputs, "pod_security_findings_count"),
                    default=data.get("security_findings_count") or 0,
                ),
            ),
        },
        "privileged_access": {
            "serviceaccounts": section_get(
                artifact,
                "privileged_access",
                "serviceaccounts",
                first_defined(
                    nested_get(render_inputs, "privileged_serviceaccount_access"),
                    default=data.get("top_privileged_serviceaccount_access") or [],
                ),
            ),
            "users": section_get(
                artifact,
                "privileged_access",
                "users",
                first_defined(
                    nested_get(render_inputs, "privileged_user_access"),
                    default=data.get("top_privileged_user_access") or [],
                ),
            ),
            "groups": section_get(
                artifact,
                "privileged_access",
                "groups",
                first_defined(
                    nested_get(render_inputs, "privileged_group_access"),
                    default=data.get("top_privileged_group_access") or [],
                ),
            ),
        },
        "compliance": {
            "summary": section_get(
                artifact, "compliance", "summary", data.get("compliance_suite_summary") or []
            ),
            "findings": section_get(
                artifact, "compliance", "findings", data.get(compliance_findings_key) or []
            ),
            "operator_summary": section_get(
                artifact,
                "compliance",
                "operator_summary",
                data.get("compliance_operator_summary") or {},
            ),
            "standards_summary": section_get(
                artifact,
                "compliance",
                "standards_summary",
                data.get("compliance_standards_summary") or [],
            ),
            "standards_findings": section_get(
                artifact,
                "compliance",
                "standards_findings",
                data.get(standards_findings_key) or [],
            ),
            "result_counts": section_get(
                artifact,
                "compliance",
                "result_counts",
                data.get("compliance_result_counts") or {},
            ),
        },
        "access_review": {
            "likely_unused_serviceaccounts": section_get(
                artifact,
                "access_review",
                "likely_unused_serviceaccounts",
                first_defined(
                    nested_get(render_inputs, "access_review_serviceaccounts"),
                    default=data.get(access_serviceaccounts_key) or [],
                ),
            ),
            "stale_users": section_get(
                artifact,
                "access_review",
                "stale_users",
                first_defined(
                    nested_get(render_inputs, "access_review_users"),
                    default=data.get(access_users_key) or [],
                ),
            ),
            "stale_groups": section_get(
                artifact,
                "access_review",
                "stale_groups",
                first_defined(
                    nested_get(render_inputs, "access_review_groups"),
                    default=data.get(access_groups_key) or [],
                ),
            ),
        },
        "scc": {
            "item_count": section_get(
                artifact,
                "scc",
                "item_count",
                first_defined(
                    nested_get(render_inputs, "scc_item_count"),
                    default=data.get("securitycontextconstraints_items_count") or 0,
                ),
            ),
            "pod_findings": section_get(
                artifact,
                "scc",
                "pod_findings",
                first_defined(
                    nested_get(render_inputs, "scc_pod_findings"),
                    default=data.get("top_scc_pod_findings") or [],
                ),
            ),
            "grant_findings": section_get(
                artifact,
                "scc",
                "grant_findings",
                first_defined(
                    nested_get(render_inputs, "scc_grant_findings"),
                    default=data.get("top_scc_grant_findings") or [],
                ),
            ),
        },
        "secret_inventory": {
            "likely_unused_secrets": section_get(
                artifact,
                "secret_inventory",
                "likely_unused_secrets",
                first_defined(
                    nested_get(render_inputs, "likely_unused_secrets"),
                    default=data.get("likely_unused_secrets") or [],
                ),
            ),
            "secret_total_count": section_get(
                artifact,
                "secret_inventory",
                "secret_total_count",
                first_defined(nested_get(render_inputs, "secret_total_count"), default=0),
            ),
            "secret_type_counts": section_get(
                artifact,
                "secret_inventory",
                "secret_type_counts",
                first_defined(
                    nested_get(render_inputs, "secret_type_counts"),
                    default=data.get("secret_type_counts") or {},
                ),
            ),
            "expiring_certificates_warning": section_get(
                artifact,
                "secret_inventory",
                "expiring_certificates_warning",
                first_defined(
                    nested_get(render_inputs, "expiring_certificates_warning"),
                    default=data.get("expiring_certificates_warning") or [],
                ),
            ),
            "expiring_certificates_critical": section_get(
                artifact,
                "secret_inventory",
                "expiring_certificates_critical",
                first_defined(
                    nested_get(render_inputs, "expiring_certificates_critical"),
                    default=data.get("expiring_certificates_critical") or [],
                ),
            ),
        },
        "image_registry": {
            "findings": section_get(
                artifact,
                "image_registry",
                "findings",
                first_defined(
                    nested_get(render_inputs, "image_registry_findings"),
                    default=data.get("top_image_registry_findings") or [],
                ),
            ),
            "internal_registry_workloads": section_get(
                artifact,
                "image_registry",
                "internal_registry_workloads",
                first_defined(
                    nested_get(render_inputs, "internal_registry_workloads"),
                    default=data.get("top_internal_registry_workloads") or [],
                ),
            ),
        },
        "workload_protection": {
            "vulnerability_scanning": section_get(
                artifact,
                "workload_protection",
                "vulnerability_scanning",
                nested_get(render_inputs, "workload_vulnerability_scanning_section", default={}),
            ),
            "advanced_cluster_security": section_get(
                artifact,
                "workload_protection",
                "advanced_cluster_security",
                nested_get(render_inputs, "advanced_cluster_security_section", default={}),
            ),
        },
        "secret_management": {
            "external_secrets_operator": section_get(
                artifact,
                "secret_management",
                "external_secrets_operator",
                nested_get(render_inputs, "external_secrets_operator_section", default={}),
            ),
            "cyberark_conjur_secrets_management": section_get(
                artifact,
                "secret_management",
                "cyberark_conjur_secrets_management",
                nested_get(
                    render_inputs,
                    "cyberark_conjur_secrets_management_section",
                    default={},
                ),
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
