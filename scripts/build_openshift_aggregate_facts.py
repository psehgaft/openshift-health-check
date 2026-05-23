#!/usr/bin/env python3
from datetime import datetime, timezone
import json
import re
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


def parse_timestamp(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"\.\d+Z$", "Z", text)
    try:
        return datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def age_days(value: str) -> float:
    parsed = parse_timestamp(value)
    if not parsed:
        return 0.0
    return (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0


def latest_managed_time(metadata: dict) -> str:
    latest = None
    latest_text = ""
    for field in as_list(metadata.get("managedFields")):
        text = str(as_dict(field).get("time") or "").strip()
        parsed = parse_timestamp(text)
        if parsed and (latest is None or parsed > latest):
            latest = parsed
            latest_text = text
    return latest_text


def object_age_row(item: dict, kind: str, age_basis_timestamp: str, age_basis: str) -> dict:
    metadata = as_dict(item.get("metadata"))
    return {
        "kind": kind,
        "namespace": str(metadata.get("namespace") or ""),
        "name": str(metadata.get("name") or "unknown"),
        "created_at": str(metadata.get("creationTimestamp") or "unknown"),
        "last_changed_at": age_basis_timestamp or str(metadata.get("creationTimestamp") or "unknown"),
        "age_days": round(age_days(age_basis_timestamp), 1),
        "age_basis": age_basis,
    }


def stale_configmaps(items: list, exclude_re, threshold_days: int) -> list:
    selected = []
    for item in as_list(items):
        metadata = as_dict(item.get("metadata"))
        namespace = str(metadata.get("namespace") or "")
        if exclude_re.search(namespace):
            continue
        last_changed = latest_managed_time(metadata)
        basis = "managedFields.lastUpdate" if last_changed else "creationTimestamp"
        timestamp = last_changed or str(metadata.get("creationTimestamp") or "")
        if age_days(timestamp) > threshold_days:
            row = object_age_row(item, "ConfigMap", timestamp, basis)
            row["key_count"] = len(as_dict(item.get("data"))) + len(as_dict(item.get("binaryData")))
            selected.append(row)
    return sort_by_attr(selected, "age_days", reverse=True)


def stale_secrets(items: list, exclude_re, secret_type: str, threshold_days: int) -> list:
    selected = []
    for item in as_list(items):
        metadata = as_dict(item.get("metadata"))
        namespace = str(metadata.get("namespace") or "")
        item_type = str(item.get("type") or "Opaque")
        if exclude_re.search(namespace) or item_type != secret_type:
            continue
        last_changed = latest_managed_time(metadata)
        basis = "managedFields.lastUpdate" if last_changed else "creationTimestamp"
        timestamp = last_changed or str(metadata.get("creationTimestamp") or "")
        if age_days(timestamp) > threshold_days:
            row = object_age_row(item, "Secret", timestamp, basis)
            row["type"] = item_type
            selected.append(row)
    return sort_by_attr(selected, "age_days", reverse=True)


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


SCC_PRIVILEGE_RANKS = {
    "privileged": 100,
    "hostmount-anyuid": 90,
    "hostnetwork": 80,
    "hostaccess": 70,
    "anyuid": 60,
    "nonroot-v2": 30,
    "nonroot": 30,
    "restricted-v2": 10,
    "restricted": 10,
    "not-collected": 0,
}


def scc_privilege_rank(item: dict) -> int:
    try:
        rank = int(as_dict(item).get("scc_privilege_rank"))
    except (TypeError, ValueError):
        rank = -1
    if rank >= 0:
        return rank

    name = str(as_dict(item).get("scc") or "not-collected").strip()
    if not name:
        return 0
    return SCC_PRIVILEGE_RANKS.get(name, 40)


def sort_security_findings(items: list) -> list:
    return sorted(
        as_list(items),
        key=lambda item: (
            -scc_privilege_rank(item),
            str(as_dict(item).get("scc") or "not-collected"),
            str(as_dict(item).get("namespace") or ""),
            str(as_dict(item).get("pod") or ""),
            str(as_dict(item).get("issue") or ""),
        ),
    )


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


def reason_key(reason) -> str:
    if isinstance(reason, (list, tuple)) and reason:
        return str(reason[0] or "").strip()
    if isinstance(reason, dict):
        return str(reason.get("reason") or reason.get("name") or reason.get("type") or "").strip()
    return str(reason or "").strip()


def normalize_overprovisioned_pods(items: list[dict]) -> list:
    merged = {}
    for item in as_list(items):
        namespace = str(item.get("namespace") or "")
        pod = str(item.get("pod") or item.get("name") or "")
        key = (namespace, pod)
        if key not in merged:
            merged[key] = dict(item)
            merged[key]["reasons"] = []
        existing = {reason_key(reason) for reason in as_list(merged[key].get("reasons"))}
        for reason in as_list(item.get("reasons")):
            name = reason_key(reason)
            if not name or name in existing:
                continue
            merged[key]["reasons"].append(reason)
            existing.add(name)
        merged[key]["reason_names"] = sorted(existing)
    rows = list(merged.values())
    rows.sort(
        key=lambda item: (
            -int_value(item.get("cpu_request_millicores"), 0),
            -int_value(item.get("memory_request_mib"), 0),
            str(item.get("namespace", "")),
            str(item.get("pod", "")),
        )
    )
    return rows


def normalize_probe_findings(items: list[dict]) -> list:
    merged = {}
    for item in as_list(items):
        key = (
            str(item.get("kind") or ""),
            str(item.get("namespace") or ""),
            str(item.get("name") or ""),
        )
        if key not in merged:
            merged[key] = {
                "kind": key[0],
                "namespace": key[1],
                "name": key[2],
                "missing_probe_types": [],
                "containers": [],
            }
        issue = str(item.get("issue") or "").strip()
        if issue and issue not in merged[key]["missing_probe_types"]:
            merged[key]["missing_probe_types"].append(issue)
        for container in as_list(item.get("containers")):
            text = str(container or "").strip()
            if text and text not in merged[key]["containers"]:
                merged[key]["containers"].append(text)
        if not as_list(item.get("containers")):
            for container in str(item.get("detail") or "").split(","):
                text = container.strip()
                if text and text not in merged[key]["containers"]:
                    merged[key]["containers"].append(text)
    rows = list(merged.values())
    rows.sort(
        key=lambda item: (
            -len(item.get("missing_probe_types", [])),
            item.get("namespace", ""),
            item.get("kind", ""),
            item.get("name", ""),
        )
    )
    for row in rows:
        row["issue"] = ", ".join(row["missing_probe_types"])
        row["detail"] = ", ".join(row["containers"])
    return rows


def build(data: dict) -> dict:
    limits = as_dict(data.get("limits"))
    restart_limit = int_value(limits.get("restart_limit"), 10)
    restart_table_limit = int_value(limits.get("restart_table_limit"), 100)
    restart_table_threshold = int_value(limits.get("restart_table_threshold"), 3)
    old_pod_table_limit = int_value(limits.get("old_pod_table_limit"), 20)
    stale_pod_table_limit = int_value(limits.get("stale_pod_table_limit"), 50)
    stale_pod_age_days = int_value(limits.get("stale_pod_age_days"), 100)
    stale_configmap_table_limit = int_value(limits.get("stale_configmap_table_limit"), 50)
    stale_configmap_age_days = int_value(limits.get("stale_configmap_age_days"), 100)
    stale_generic_secret_table_limit = int_value(limits.get("stale_generic_secret_table_limit"), 50)
    stale_generic_secret_age_days = int_value(limits.get("stale_generic_secret_age_days"), 100)
    stale_dockerconfigjson_secret_table_limit = int_value(limits.get("stale_dockerconfigjson_secret_table_limit"), 50)
    stale_dockerconfigjson_secret_age_days = int_value(limits.get("stale_dockerconfigjson_secret_age_days"), 200)
    pvc_issue_limit = int_value(limits.get("pvc_issue_limit"), 10)
    event_reason_limit = int_value(limits.get("event_reason_limit"), 10)
    alert_group_limit = int_value(limits.get("alert_group_limit"), 10)
    namespace_issue_limit = int_value(limits.get("namespace_issue_limit"), 10)
    workload_issue_limit = int_value(limits.get("workload_issue_limit"), 10)
    security_issue_limit = int_value(limits.get("security_issue_limit"), 10)
    deprecated_api_limit = int_value(limits.get("deprecated_api_limit"), 10)

    workload_resilience_data = as_dict(data.get("workload_resilience_data"))
    pod_restart_hotspots = as_list(data.get("pod_restart_hotspots"))
    exclude_re = re.compile(data.get("user_namespaces_exclude_regex") or r"^$")
    high_restart_pods = sort_by_attr(
        select_attr_gt_int(pod_restart_hotspots, "restarts", restart_table_threshold),
        "restarts",
        reverse=True,
    )
    stale_user_pods = [
        item for item in as_list(data.get("aged_user_pods")) if int_value(attr_value(item, "age_days"), 0) > stale_pod_age_days
    ]

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
        "top_stale_user_pods": top(sort_by_attr(stale_user_pods, "age_days", reverse=True), stale_pod_table_limit),
        "top_stale_configmaps": top(
            stale_configmaps(data.get("configmaps"), exclude_re, stale_configmap_age_days),
            stale_configmap_table_limit,
        ),
        "top_stale_generic_secrets": top(
            stale_secrets(data.get("secrets"), exclude_re, "Opaque", stale_generic_secret_age_days),
            stale_generic_secret_table_limit,
        ),
        "top_stale_dockerconfigjson_secrets": top(
            stale_secrets(
                data.get("secrets"),
                exclude_re,
                "kubernetes.io/dockerconfigjson",
                stale_dockerconfigjson_secret_age_days,
            ),
            stale_dockerconfigjson_secret_table_limit,
        ),
        "top_orphan_pods": top(data.get("orphan_pods"), workload_issue_limit),
        "top_workload_label_governance_findings": top(data.get("workload_label_governance_findings"), workload_issue_limit),
        "top_node_label_governance_findings": top(data.get("node_label_governance_findings"), workload_issue_limit),
        "top_workload_resource_findings": top(data.get("workload_resource_findings"), workload_issue_limit),
        "top_workload_probe_findings": top(normalize_probe_findings(data.get("workload_probe_findings")), workload_issue_limit),
        "top_overprovisioned_pods": top(normalize_overprovisioned_pods(data.get("overprovisioned_pods")), workload_issue_limit),
        "top_quota_pressure_findings": top(data.get("quota_pressure_findings"), workload_issue_limit),
        "top_security_findings": top(sort_security_findings(data.get("security_findings")), security_issue_limit),
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
