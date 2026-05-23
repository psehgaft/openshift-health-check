#!/usr/bin/env python3
import json
import sys


def parse_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def int_value(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def top(items, limit: int) -> list:
    return as_list(items)[: max(limit, 0)]


def attr_value(item, attr: str):
    value = item
    for part in attr.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def sort_by_attr(items, attr: str, reverse: bool = False) -> list:
    def key(item):
        value = attr_value(item, attr)
        if value is None:
            return ""
        return value

    return sorted(as_list(items), key=key, reverse=reverse)


def select_attr_equal(items, attr: str, expected) -> list:
    return [item for item in as_list(items) if attr_value(item, attr) == expected]


def select_attr_gt_int(items, attr: str, threshold: int) -> list:
    selected = []
    for item in as_list(items):
        value = int_value(attr_value(item, attr), 0)
        if value > threshold:
            selected.append(item)
    return selected


def reject_issue(items, issue: str) -> list:
    return [item for item in as_list(items) if item.get("issue") != issue]


def dict_items_by_value_desc(data: dict, limit: int) -> list:
    items = [{"key": key, "value": value} for key, value in as_dict(data).items()]
    return top(sorted(items, key=lambda item: item.get("value"), reverse=True), limit)


def issue_type_counts(items: list[dict]) -> dict:
    counts = {}
    for item in as_list(items):
        issue = item.get("issue")
        counts[issue] = counts.get(issue, 0) + 1
    return counts


def unique_by_attr(items: list[dict], attr: str) -> list:
    seen = set()
    unique = []
    for item in as_list(items):
        value = attr_value(item, attr)
        if value in seen:
            continue
        seen.add(value)
        unique.append(item)
    return unique


def build(data: dict) -> dict:
    limits = as_dict(data.get("limits"))
    restart_limit = int_value(limits.get("restart_limit"), 10)
    restart_table_limit = int_value(limits.get("restart_table_limit"), 100)
    restart_table_threshold = int_value(limits.get("restart_table_threshold"), 3)
    old_pod_table_limit = int_value(limits.get("old_pod_table_limit"), 20)
    pvc_issue_limit = int_value(limits.get("pvc_issue_limit"), 10)
    event_reason_limit = int_value(limits.get("event_reason_limit"), 10)
    alert_group_limit = int_value(limits.get("alert_group_limit"), 10)
    namespace_issue_limit = int_value(limits.get("namespace_issue_limit"), 10)
    workload_issue_limit = int_value(limits.get("workload_issue_limit"), 10)
    security_issue_limit = int_value(limits.get("security_issue_limit"), 10)
    deprecated_api_limit = int_value(limits.get("deprecated_api_limit"), 10)

    workload_resilience_data = as_dict(data.get("workload_resilience_data"))
    pod_restart_hotspots = as_list(data.get("pod_restart_hotspots"))
    high_restart_pods = sort_by_attr(
        select_attr_gt_int(pod_restart_hotspots, "restarts", restart_table_threshold),
        "restarts",
        reverse=True,
    )

    privileged_serviceaccounts = sort_by_attr(
        sort_by_attr(data.get("privileged_serviceaccount_access"), "namespace"),
        "name",
    )
    stale_serviceaccounts = sort_by_attr(
        sort_by_attr(data.get("stale_access_review_serviceaccounts"), "namespace"),
        "name",
    )

    stale_users = sort_by_attr(unique_by_attr(data.get("stale_access_review_users"), "name"), "name")
    stale_groups = sort_by_attr(unique_by_attr(data.get("stale_access_review_groups"), "name"), "name")

    return {
        "scored_day2_posture_findings": as_list(
            data.get("scored_day2_posture_findings")
            if data.get("scored_day2_posture_findings") is not None
            else data.get("day2_posture_findings")
        ),
        "scored_workload_practice_findings": reject_issue(
            data.get("workload_practice_findings"), "missing-pod-disruption-budget"
        ),
        "default_storageclasses": select_attr_equal(data.get("storageclass_summary"), "is_default", True),
        "top_pod_restart_hotspots": top(sort_by_attr(pod_restart_hotspots, "restarts", reverse=True), restart_limit),
        "high_restart_pods": high_restart_pods,
        "top_high_restart_pods": top(high_restart_pods, restart_table_limit),
        "top_pvc_issues": top(data.get("pvc_issues"), pvc_issue_limit),
        "top_pv_issues": top(data.get("pv_issues"), pvc_issue_limit),
        "top_event_reasons": dict_items_by_value_desc(data.get("warning_event_reason_counts"), event_reason_limit),
        "top_alert_groups": dict_items_by_value_desc(data.get("firing_alert_name_counts"), alert_group_limit),
        "top_alert_namespaces": dict_items_by_value_desc(
            data.get("firing_alert_namespace_counts"), namespace_issue_limit
        ),
        "top_namespace_issue_summary": top(data.get("namespace_issue_summary"), namespace_issue_limit),
        "top_workload_health_issues": top(data.get("workload_health_issues"), workload_issue_limit),
        "top_unhealthy_user_pods": top(data.get("unhealthy_user_pods"), workload_issue_limit),
        "top_high_replica_workloads": top(
            sort_by_attr(data.get("high_replica_workloads"), "replicas", reverse=True),
            workload_issue_limit,
        ),
        "top_workload_resilience_findings": top(workload_resilience_data.get("findings"), workload_issue_limit),
        "top_workload_resilience_pdb_review_findings": top(
            workload_resilience_data.get("pdb_review_findings"), workload_issue_limit
        ),
        "top_aged_user_pods": top(sort_by_attr(data.get("aged_user_pods"), "age_days", reverse=True), old_pod_table_limit),
        "top_orphan_pods": top(data.get("orphan_pods"), workload_issue_limit),
        "top_workload_label_governance_findings": top(data.get("workload_label_governance_findings"), workload_issue_limit),
        "top_node_label_governance_findings": top(data.get("node_label_governance_findings"), workload_issue_limit),
        "top_workload_resource_findings": top(data.get("workload_resource_findings"), workload_issue_limit),
        "top_workload_probe_findings": top(data.get("workload_probe_findings"), workload_issue_limit),
        "top_overprovisioned_pods": top(data.get("overprovisioned_pods"), workload_issue_limit),
        "top_quota_pressure_findings": top(data.get("quota_pressure_findings"), workload_issue_limit),
        "top_security_findings": top(data.get("security_findings"), security_issue_limit),
        "top_workload_practice_findings": top(data.get("workload_practice_findings"), security_issue_limit),
        "top_route_issues": top(data.get("route_issues"), workload_issue_limit),
        "top_ingress_issues": top(data.get("ingress_issues"), workload_issue_limit),
        "top_route_host_conflicts": top(data.get("route_host_conflicts"), workload_issue_limit),
        "top_ingress_host_conflicts": top(data.get("ingress_host_conflicts"), workload_issue_limit),
        "top_deprecated_crd_findings": top(data.get("deprecated_crd_findings"), deprecated_api_limit),
        "top_deprecated_api_lines": top(data.get("deprecated_api_lines"), deprecated_api_limit),
        "top_services_without_endpoints": top(data.get("services_without_endpoints"), workload_issue_limit),
        "top_likely_unused_serviceaccounts": top(data.get("likely_unused_serviceaccounts"), workload_issue_limit),
        "top_likely_unused_configmaps": top(data.get("likely_unused_configmaps"), workload_issue_limit),
        "top_likely_unused_secrets": top(data.get("likely_unused_secrets"), workload_issue_limit),
        "top_likely_unused_crds": top(data.get("likely_unused_crds"), deprecated_api_limit),
        "top_image_registry_findings": top(data.get("image_registry_findings"), security_issue_limit),
        "top_internal_registry_workloads": top(data.get("internal_registry_workloads"), workload_issue_limit),
        "top_feature_findings": top(data.get("feature_findings"), security_issue_limit),
        "top_observability_findings": top(data.get("observability_findings"), security_issue_limit),
        "top_apiservice_issues": top(data.get("apiservice_issues"), security_issue_limit),
        "top_failed_pipelineruns": top(data.get("failed_pipelineruns"), workload_issue_limit),
        "top_buildconfigs_without_triggers": top(data.get("buildconfigs_without_triggers"), workload_issue_limit),
        "top_compliance_suite_findings": top(data.get("compliance_suite_findings"), security_issue_limit),
        "top_compliance_standards_findings": top(data.get("compliance_standards_findings"), security_issue_limit),
        "top_backup_posture_findings": top(data.get("backup_posture_findings"), security_issue_limit),
        "top_machine_healthcheck_findings": top(data.get("machine_healthcheck_findings"), security_issue_limit),
        "top_day2_posture_findings": top(data.get("day2_posture_findings"), security_issue_limit),
        "top_live_cluster_compare_findings": top(data.get("live_cluster_compare_findings"), security_issue_limit),
        "top_live_managed_gate_findings": top(data.get("live_managed_gate_findings"), security_issue_limit),
        "top_live_advisor_findings": top(data.get("live_advisor_findings"), security_issue_limit),
        "top_live_must_gather_findings": top(data.get("live_must_gather_findings"), security_issue_limit),
        "top_live_omc_findings": top(data.get("omc_findings"), security_issue_limit),
        "top_live_inspect_findings": top(data.get("live_inspect_findings"), security_issue_limit),
        "top_live_sosreport_findings": top(data.get("live_sosreport_findings"), security_issue_limit),
        "top_scc_grant_findings": top(data.get("scc_grant_findings"), security_issue_limit),
        "top_scc_pod_findings": top(data.get("scc_pod_findings"), security_issue_limit),
        "top_namespace_metadata_governance_findings": top(
            data.get("namespace_metadata_governance_findings"), security_issue_limit
        ),
        "top_privileged_serviceaccount_access": top(privileged_serviceaccounts, security_issue_limit),
        "top_privileged_user_access": top(sort_by_attr(data.get("privileged_user_access"), "name"), security_issue_limit),
        "top_privileged_group_access": top(sort_by_attr(data.get("privileged_group_access"), "name"), security_issue_limit),
        "top_stale_access_review_serviceaccounts": top(stale_serviceaccounts, security_issue_limit),
        "top_stale_access_review_users": top(stale_users, security_issue_limit),
        "top_stale_access_review_groups": top(stale_groups, security_issue_limit),
        "security_issue_type_counts": issue_type_counts(data.get("security_findings")),
        "workload_practice_issue_type_counts": issue_type_counts(data.get("workload_practice_findings")),
        "workload_probe_issue_type_counts": issue_type_counts(data.get("workload_probe_findings")),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_openshift_aggregate_facts.py <input-json-path>"}))
        return 2
    print(json.dumps(build(parse_json(sys.argv[1]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
