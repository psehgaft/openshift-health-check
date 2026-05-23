#!/usr/bin/env python3
"""Prepare OpenShift render-time artifacts and support table facts."""

import json
import sys
from pathlib import Path


POSTURE_FACT_PREFIXES = {
    "evidence_and_supportability": "supportability",
    "platform_health": "platform_health",
    "node_health_and_capacity": "node_health",
    "application_access_and_network_isolation": "network_access",
    "backup_and_disaster_recovery": "backup_recovery",
    "observability": "observability",
    "security_and_governance": "security_governance",
    "workload_health": "workload_health",
    "platform_architecture_and_lifecycle": "architecture_lifecycle",
    "capacity_planning_snapshot": "capacity_snapshot",
    "declarative_operations": "declarative_operations",
    "container_platform_adoption_and_release_engineering": "release_engineering",
    "day2_production_readiness": "day2_readiness",
}

POSTURE_RENDER_INPUT_KEYS = {
    "evidence_and_supportability": {
        "supportability_summary",
        "diagnostics_coverage",
        "product_evidence",
        "product_evidence_findings",
        "connected_cluster_posture",
        "connected_cluster_findings",
        "connected_cluster_advisor_summary",
        "node_diagnostics_summary",
        "node_diagnostics_findings",
        "advisor_summary",
        "advisor_findings",
        "insights_archive_summary",
        "insights_archive_findings",
        "evidence_coverage",
    },
    "platform_health": {
        "summary",
        "findings",
        "operators",
        "infrastructure_component_summary",
        "infrastructure_component_issues",
        "etcd_ocp_diag_summary",
        "etcd_ocp_diag_findings",
        "omc_summary",
        "omc_findings",
        "apiservice_issues",
        "image_registry_findings",
        "feature_findings",
        "internal_registry_workloads",
        "control_plane_query_status_map",
        "apiserver_readyz_status",
        "apiserver_readyz_failed_checks",
    },
    "node_health_and_capacity": {
        "machineconfigpools",
        "nodes",
        "quota_pressure_findings",
        "node_capacity_summary_by_density_desc",
        "node_capacity_summary_by_density_asc",
        "high_pod_density_nodes",
        "high_cpu_nodes",
        "high_memory_nodes",
        "high_disk_nodes",
    },
    "application_access_and_network_isolation": {
        "route_object_count",
        "ingress_object_count",
        "route_issues",
        "route_host_conflicts",
        "ingress_issues",
        "ingress_host_conflicts",
        "route_ingress_host_conflicts",
        "services_without_endpoints",
        "ingresscontrollers_summary",
        "ingresscontrollers_issues",
    },
    "backup_and_disaster_recovery": {
        "pv_issues",
        "pvc_issues",
        "backup_posture_findings",
        "backup_storage_locations",
        "backup_schedules",
        "recent_backups",
        "recent_restores",
        "machinehealthcheck_summary",
        "machine_healthcheck_findings",
    },
    "observability": {
        "forwarding_summary",
        "prometheus_query",
        "findings",
        "connected_cluster_posture",
        "connected_cluster_findings",
        "advisor_summary",
        "advisor_findings",
        "insights_archive_summary",
        "insights_archive_findings",
    },
    "security_and_governance": {
        "namespace_metadata_governance_findings",
        "node_metadata_governance_findings",
        "auth_findings",
        "pod_security_issue_type_counts",
        "pod_security_findings",
        "pod_security_findings_count",
        "privileged_serviceaccount_access",
        "privileged_user_access",
        "privileged_group_access",
        "access_review_serviceaccounts",
        "access_review_users",
        "access_review_groups",
        "scc_item_count",
        "scc_pod_findings",
        "scc_grant_findings",
        "likely_unused_secrets",
        "secret_total_count",
        "secret_type_counts",
        "expiring_certificates_warning",
        "expiring_certificates_critical",
        "image_registry_findings",
        "internal_registry_workloads",
        "workload_vulnerability_scanning_section",
        "advanced_cluster_security_section",
        "external_secrets_operator_section",
    },
    "workload_health": {
        "metric_source_status",
        "platform_pod_issues",
        "workload_resilience_findings",
        "workload_resilience_pdb_review_findings",
        "workload_resilience_summary",
        "workload_probe_issue_type_counts",
        "top_pod_cpu_usage_summary",
        "top_pod_memory_usage_summary",
        "unhealthy_user_pods",
        "restart_hotspots",
        "workload_resilience_pdb_review_findings",
        "aged_user_pods",
        "stale_user_pods",
        "stale_configmaps",
        "stale_generic_secrets",
        "stale_dockerconfigjson_secrets",
        "workload_health_issues",
        "high_replica_workloads",
        "orphan_pods",
        "workload_label_governance_findings",
        "node_label_governance_findings",
        "workload_resource_findings",
        "workload_probe_findings",
        "overprovisioned_pods",
        "services_without_endpoints",
    },
    "platform_architecture_and_lifecycle": {
        "upgrade_readiness_summary",
        "reference_compliance_summary",
        "reference_compliance_findings",
        "managed_gate_summary",
        "managed_gate_findings",
        "topology_resilience",
        "available_updates",
        "conditional_updates",
        "cluster_update_history",
        "deprecated_crd_findings",
        "deprecated_api_lines",
        "cluster_compare_findings",
        "managed_gate_top_findings",
    },
    "capacity_planning_snapshot": {
        "cluster_current_state",
        "cluster_profile",
        "architecture_lifecycle_summary",
        "cluster_current_state_sanity_findings",
        "cluster_current_state_build_error",
        "runtime_signal_resolution_map",
    },
    "declarative_operations": {
        "declarative_operations_summary",
    },
    "container_platform_adoption_and_release_engineering": {
        "release_engineering_adoption_summary",
        "cicd_runner_summary",
        "cicd_runner_findings",
        "buildconfig_strategy_counts",
        "pipelinerun_status_counts",
        "failed_pipelineruns",
        "buildconfigs_without_triggers",
    },
    "day2_production_readiness": {
        "day2_production_readiness_summary",
        "day2_posture_summary",
        "checks",
        "findings",
        "capability_sections",
        "capability_assessment_state",
        "capability_assessment_error",
        "product_evidence",
        "product_evidence_findings",
    },
}

POD_SECURITY_ISSUE_LABELS = {
    "privileged-containers": "Privileged containers",
    "host-network": "Host network",
    "host-pid": "Host PID",
    "host-ipc": "Host IPC",
    "hostpath-volume": "Local hostPath storage",
    "run-as-root": "Run as root",
    "missing-seccomp-profile": "Missing seccomp profile",
    "unconfined-seccomp-profile": "Unconfined seccomp profile",
    "allow-privilege-escalation-not-disabled": "Privilege escalation not disabled",
    "run-as-non-root-not-enforced": "Run as non-root not enforced",
    "read-only-root-filesystem-not-enabled": "Read-only root filesystem not enabled",
    "capabilities-not-fully-dropped": "Capabilities not fully dropped",
    "literal-sensitive-env": "Literal sensitive env values",
    "literal-sensitive-arg": "Literal sensitive command or arg values",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def shared_artifact_key(path, artifact):
    kind = artifact.get("kind")
    if kind == "shared-collection":
        return "collection"
    if kind == "shared-analysis-graph":
        return "analysis_graph"
    return artifact.get("key") or path.stem


def load_artifact_dir(root, key_func=None):
    path = Path(root)
    if not path.exists():
        return {}
    if not path.is_dir():
        raise ValueError(f"not a directory: {path}")
    payload = {}
    for artifact_path in sorted(path.glob("*.json")):
        artifact = load_json(artifact_path)
        key = key_func(artifact_path, artifact) if key_func else artifact.get("key")
        payload[key or artifact_path.stem] = artifact
    return payload


def recursive_merge(left, right):
    merged = dict(left or {})
    for key, value in (right or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = recursive_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def nested_get(data, *keys, default=None):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def condition_status(item, condition_type, default="Unknown"):
    for condition in nested_get(item, "status", "conditions", default=[]) or []:
        if condition.get("type") == condition_type:
            return condition.get("status", default)
    return default


def graph_items(graph, key):
    value = graph.get(key) if isinstance(graph, dict) else {}
    return value.get("items", []) if isinstance(value, dict) else []


def first_count_map(*values):
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def count_rows_by_key(counts):
    if not isinstance(counts, dict):
        return []
    return [{"key": key, "value": counts[key]} for key in sorted(counts)]


def count_rows_by_value_desc(counts, labels=None):
    if not isinstance(counts, dict):
        return []
    rows = []
    for key, value in counts.items():
        rows.append(
            {
                "key": key,
                "label": (labels or {}).get(key, key),
                "value": value,
            }
        )
    return sorted(rows, key=lambda item: (-safe_int(item.get("value")), item.get("key", "")))


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_limit(value, default):
    limit = safe_int(value)
    return limit if limit > 0 else default


def list_value(value):
    return value if isinstance(value, list) else []


def dict_value(value):
    return value if isinstance(value, dict) else {}


def first_list(*values):
    for value in values:
        if isinstance(value, list):
            return value
    return []


def sorted_dict_list(rows, key):
    return sorted(list_value(rows), key=lambda item: str(dict_value(item).get(key, "")))


def slice_rows(rows, limit):
    return list_value(rows)[:limit]


def unique_slice_rows(rows, limit, key="name"):
    seen = set()
    selected = []
    for item in list_value(rows):
        row = dict_value(item)
        value = row.get(key, "unknown")
        if value in seen:
            continue
        seen.add(value)
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def names_from_rows(rows, key="name"):
    names = [str(dict_value(item).get(key, "")).strip() for item in list_value(rows)]
    return [name for name in names if name]


def has_area(rows, area):
    return any(dict_value(item).get("area") == area for item in list_value(rows))


def capacity_value_label(value):
    text = str(value or "unknown")
    if text in {"unknown", "not-assessed"} or text.endswith("-unknown") or text.endswith(
        "not-assessed"
    ):
        return "not-derived"
    return text


def count_pairs(rows, key, label_func=None, limit=10):
    values = []
    for item in slice_rows(rows, limit):
        row = dict_value(item)
        label = row.get(key, "unknown")
        if label_func:
            label = label_func(label)
        values.append(f"{label}={row.get('count', 0)}")
    return ", ".join(values)


def status_bucket(value):
    status = str(value or "UNKNOWN").strip().upper()
    if status in {"OK", "HEALTHY", "PASS", "PASSED", "PRESENT", "SUPPORTED"}:
        return "ok"
    if status in {"WARNING", "WARN", "INFO", "FAIR", "MEDIUM", "PARTIAL"}:
        return "warn"
    if status in {"CRITICAL", "FAILED", "FAIL", "ERROR", "BLOCKED"}:
        return "critical"
    return "unknown"


def condition_types_with_status(item, status_value):
    conditions = nested_get(item, "status", "conditions", default=[]) or []
    return [
        condition.get("type")
        for condition in conditions
        if condition.get("status") == status_value and condition.get("type")
    ]


def node_roles(labels):
    roles = []
    for key in sorted((labels or {}).keys()):
        if not key.startswith("node-role.kubernetes.io/"):
            continue
        role = key.replace("node-role.kubernetes.io/", "", 1)
        roles.append(role or "worker")
    return ", ".join(roles) or "worker"


def node_pressures(item):
    pressure_types = {
        "MemoryPressure",
        "DiskPressure",
        "PIDPressure",
        "OutOfDisk",
        "NetworkUnavailable",
    }
    pressures = [
        condition_type
        for condition_type in condition_types_with_status(item, "True")
        if condition_type in pressure_types
    ]
    return ", ".join(pressures) or "None"


def node_ready_status(item):
    return condition_status(item, "Ready", default=item.get("ready", "Unknown"))


def node_ready_badge_status(ready_status):
    if ready_status == "True":
        return "OK"
    if ready_status == "Unknown":
        return "UNKNOWN"
    return "WARN"


def condition_badge_status(value, ok_value="True", warn_value=None, info_value=None):
    if value == ok_value:
        return "OK"
    if warn_value is not None and value == warn_value:
        return "WARN"
    if info_value is not None and value == info_value:
        return "INFO"
    if value == "Unknown":
        return "UNKNOWN"
    return "OK"


def build_operator_summary(graph):
    items = []
    for item in graph_items(graph, "clusteroperators"):
        versions = nested_get(item, "status", "versions", default=[]) or []
        items.append(
            {
                "name": nested_get(item, "metadata", "name", default="unknown"),
                "available": condition_status(item, "Available"),
                "degraded": condition_status(item, "Degraded"),
                "progressing": condition_status(item, "Progressing"),
                "version": versions[0].get("version", "unknown")
                if versions and isinstance(versions[0], dict)
                else "unknown",
            }
        )
    return items


def build_mcp_summary(graph):
    items = []
    for item in graph_items(graph, "machineconfigpools"):
        items.append(
            {
                "name": nested_get(item, "metadata", "name", default="unknown"),
                "degraded": condition_status(item, "NodeDegraded"),
                "updating": condition_status(item, "Updating"),
                "updated": condition_status(item, "Updated"),
                "machine_count": nested_get(item, "status", "machineCount", default=0),
                "ready_machine_count": nested_get(
                    item, "status", "readyMachineCount", default=0
                ),
            }
        )
    return items


def build_route_summary(graph):
    items = []
    for item in graph_items(graph, "routes"):
        admitted_statuses = []
        for ingress in nested_get(item, "status", "ingress", default=[]) or []:
            admitted_statuses.extend(
                condition.get("status")
                for condition in ingress.get("conditions", []) or []
                if condition.get("type") == "Admitted"
            )
        items.append(
            {
                "namespace": nested_get(item, "metadata", "namespace", default="unknown"),
                "name": nested_get(item, "metadata", "name", default="unknown"),
                "host": nested_get(item, "spec", "host", default=""),
                "admitted": "True" in admitted_statuses,
                "service_name": nested_get(item, "spec", "to", "name", default="unknown"),
            }
        )
    return items


def compact_node_items(graph):
    items = []
    for item in graph_items(graph, "nodes"):
        if item.get("kind") != "Node":
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        if not metadata.get("name") or not isinstance(status.get("nodeInfo"), dict):
            continue
        labels = metadata.get("labels") or {}
        node_info = status.get("nodeInfo") or {}
        ready_status = node_ready_status(item)
        items.append(
            {
                "name": metadata.get("name", "unknown"),
                "roles": node_roles(labels),
                "ready_status": ready_status,
                "ready_badge_status": node_ready_badge_status(ready_status),
                "pressures": node_pressures(item),
                "kubelet_version": node_info.get("kubeletVersion", "unknown"),
                "os_image": node_info.get("osImage", "unknown"),
                "metadata": {
                    "name": metadata.get("name", "unknown"),
                    "labels": labels,
                },
                "status": {
                    "conditions": status.get("conditions") or [],
                    "nodeInfo": node_info,
                },
            }
        )
    return items


def compact_machineconfigpool_items(graph):
    items = []
    for item in graph_items(graph, "machineconfigpools"):
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        updated = condition_status(item, "Updated", default=item.get("updated", "Unknown"))
        updating = condition_status(item, "Updating", default=item.get("updating", "Unknown"))
        degraded = condition_status(item, "Degraded", default=item.get("degraded", "Unknown"))
        items.append(
            {
                "name": metadata.get("name", "unknown"),
                "updated": updated,
                "updated_badge_status": condition_badge_status(
                    updated, ok_value="True", warn_value="False"
                ),
                "updating": updating,
                "updating_badge_status": condition_badge_status(
                    updating, ok_value="False", info_value="True"
                ),
                "degraded": degraded,
                "degraded_badge_status": condition_badge_status(
                    degraded, ok_value="False", warn_value="True"
                ),
                "machine_count": status.get("machineCount", 0),
                "ready_machine_count": status.get("readyMachineCount", 0),
                "updated_machine_count": status.get("updatedMachineCount", 0),
                "metadata": {"name": metadata.get("name", "unknown")},
                "status": {
                    "conditions": status.get("conditions") or [],
                    "machineCount": status.get("machineCount", 0),
                    "readyMachineCount": status.get("readyMachineCount", 0),
                    "updatedMachineCount": status.get("updatedMachineCount", 0),
                },
            }
        )
    return items


def build_template_graph_render(graph):
    return {
        "apiservices_count": len(graph_items(graph, "apiservices")),
        "ingresses_count": len(graph_items(graph, "ingresses")),
        "machineconfigpools": compact_machineconfigpool_items(graph),
        "nodes": compact_node_items(graph),
        "routes_count": len(graph_items(graph, "routes")),
        "secrets_count": len(graph_items(graph, "secrets")),
        "securitycontextconstraints_count": len(
            graph_items(graph, "securitycontextconstraints")
        ),
    }


def build_day2_capability_render(capability_sections, cluster_profile):
    capability_profile = dict_value(dict_value(cluster_profile).get("capabilities"))
    sections = []
    counts = {
        "ok": 0,
        "warn": 0,
        "critical": 0,
        "unknown": 0,
        "required_gaps": 0,
        "required_total": 0,
    }
    for item in list_value(capability_sections):
        section = dict_value(item)
        section_key = str(section.get("key", "")).strip()
        if not section_key:
            continue
        if not dict_value(capability_profile.get(section_key)).get("enabled", False):
            continue
        sections.append(section)
        bucket = status_bucket(section.get("status", "UNKNOWN"))
        counts[bucket] += 1
        if bool(section.get("required", False)):
            counts["required_total"] += 1
            if bucket != "ok":
                counts["required_gaps"] += 1
    return {"sections": sections, "counts": counts}


def build_template_table_render(data, posture_artifacts, cluster_profile):
    render_count_maps = data.get("render_count_maps")
    if not isinstance(render_count_maps, dict):
        render_count_maps = {}
    render_table_inputs = data.get("render_table_inputs")
    if not isinstance(render_table_inputs, dict):
        render_table_inputs = {}
    render_limits = data.get("render_limits")
    if not isinstance(render_limits, dict):
        render_limits = {}

    security_artifact = posture_artifacts.get("security_and_governance") or {}
    security_inputs = security_artifact.get("render_inputs") or {}
    node_artifact = posture_artifacts.get("node_health_and_capacity") or {}
    node_inputs = node_artifact.get("render_inputs") or {}
    workload_artifact = posture_artifacts.get("workload_health") or {}
    workload_inputs = workload_artifact.get("render_inputs") or {}
    lifecycle_artifact = posture_artifacts.get("platform_architecture_and_lifecycle") or {}
    lifecycle_inputs = lifecycle_artifact.get("render_inputs") or {}
    capacity_artifact = posture_artifacts.get("capacity_planning_snapshot") or {}
    capacity_inputs = capacity_artifact.get("render_inputs") or {}
    release_artifact = (
        posture_artifacts.get("container_platform_adoption_and_release_engineering")
        or {}
    )
    release_inputs = release_artifact.get("render_inputs") or {}
    day2_artifact = posture_artifacts.get("day2_production_readiness") or {}
    day2_inputs = day2_artifact.get("render_inputs") or {}
    capacity_current_state = dict_value(
        render_table_inputs.get("capacity_cluster_current_state")
        or capacity_artifact.get("cluster_current_state")
        or capacity_inputs.get("cluster_current_state")
    )
    capacity_sanity_findings = first_list(
        render_table_inputs.get("capacity_cluster_current_state_sanity_findings"),
        capacity_artifact.get("cluster_current_state_sanity_findings"),
        capacity_inputs.get("cluster_current_state_sanity_findings"),
    )

    return {
        "aged_user_pod_rows": slice_rows(
            first_list(
                render_table_inputs.get("aged_user_pods"),
                workload_artifact.get("aged_user_pods"),
                workload_inputs.get("aged_user_pods"),
            ),
            safe_limit(render_limits.get("old_pod_table_limit"), 25),
        ),
        "available_update_rows": slice_rows(
            first_list(
                render_table_inputs.get("available_updates"),
                lifecycle_artifact.get("available_updates"),
                lifecycle_inputs.get("available_updates"),
            ),
            safe_limit(render_limits.get("top_release_table_limit"), 10),
        ),
        "buildconfig_strategy_count_rows": count_rows_by_key(
            first_count_map(
                render_count_maps.get("buildconfig_strategy_counts"),
                release_artifact.get("buildconfig_strategy_counts"),
                release_inputs.get("buildconfig_strategy_counts"),
            )
        ),
        "compliance_result_count_rows": count_rows_by_key(
            first_count_map(render_count_maps.get("compliance_result_counts"))
        ),
        "control_plane_query_error_rows": count_rows_by_key(
            first_count_map(render_count_maps.get("control_plane_query_errors"))
        ),
        "capacity_current_state_summary": {
            "container_runtimes": count_pairs(
                capacity_current_state.get("container_runtimes"),
                "runtime",
                capacity_value_label,
                safe_limit(render_limits.get("top_capacity_summary_limit"), 10),
            ),
            "has_ip_capacity_findings": has_area(
                capacity_sanity_findings, "ip-capacity-services"
            )
            or has_area(capacity_sanity_findings, "ip-capacity-pods"),
            "has_node_shape_findings": has_area(
                capacity_sanity_findings, "node-platform-version"
            )
            or has_area(capacity_sanity_findings, "worker-pools")
            or has_area(capacity_sanity_findings, "machineconfigpools"),
            "instance_types": count_pairs(
                capacity_current_state.get("instance_types"),
                "instance_type",
                None,
                safe_limit(render_limits.get("top_capacity_summary_limit"), 10),
            ),
            "node_shapes": count_pairs(
                capacity_current_state.get("node_shapes"),
                "shape",
                capacity_value_label,
                safe_limit(render_limits.get("top_capacity_shape_summary_limit"), 12),
            ),
            "os_images": count_pairs(
                capacity_current_state.get("os_images"),
                "os_image",
                capacity_value_label,
                safe_limit(render_limits.get("top_capacity_summary_limit"), 10),
            ),
            "shape_placeholder_present": any(
                capacity_value_label(dict_value(item).get("type")) == "not-derived"
                for item in list_value(capacity_current_state.get("worker_pools"))
            )
            or any(
                capacity_value_label(dict_value(item).get("shape")) == "not-derived"
                for item in list_value(capacity_current_state.get("node_shapes"))
            ),
        },
        "cluster_update_history_rows": slice_rows(
            first_list(
                render_table_inputs.get("cluster_update_history"),
                lifecycle_artifact.get("cluster_update_history"),
                lifecycle_inputs.get("cluster_update_history"),
            ),
            5,
        ),
        "conditional_update_rows": slice_rows(
            first_list(
                render_table_inputs.get("conditional_updates"),
                lifecycle_artifact.get("conditional_updates"),
                lifecycle_inputs.get("conditional_updates"),
            ),
            safe_limit(render_limits.get("top_release_table_limit"), 10),
        ),
        "default_storageclass_names": names_from_rows(
            render_table_inputs.get("default_storageclasses")
        ),
        "day2_capability_render": build_day2_capability_render(
            first_list(
                day2_artifact.get("capability_sections"),
                day2_inputs.get("capability_sections"),
            ),
            cluster_profile,
        ),
        "firing_alert_severity_rows": count_rows_by_key(
            first_count_map(render_count_maps.get("firing_alerts_by_severity"))
        ),
        "node_capacity_density_asc_rows": unique_slice_rows(
            first_list(
                render_table_inputs.get("node_capacity_summary_by_density_asc"),
                node_artifact.get("node_capacity_summary_by_density_asc"),
                node_inputs.get("node_capacity_summary_by_density_asc"),
            ),
            safe_limit(render_limits.get("node_density_table_limit"), 10),
        ),
        "node_capacity_density_desc_rows": unique_slice_rows(
            first_list(
                render_table_inputs.get("node_capacity_summary_by_density_desc"),
                node_artifact.get("node_capacity_summary_by_density_desc"),
                node_inputs.get("node_capacity_summary_by_density_desc"),
            ),
            safe_limit(render_limits.get("node_density_table_limit"), 10),
        ),
        "pipelinerun_status_count_rows": count_rows_by_key(
            first_count_map(
                render_count_maps.get("pipelinerun_status_counts"),
                release_artifact.get("pipelinerun_status_counts"),
                release_inputs.get("pipelinerun_status_counts"),
            )
        ),
        "pod_security_issue_type_count_rows": count_rows_by_value_desc(
            first_count_map(
                render_count_maps.get("pod_security_issue_type_counts"),
                security_artifact.get("pod_security_issue_type_counts"),
                security_inputs.get("pod_security_issue_type_counts"),
            ),
            labels=POD_SECURITY_ISSUE_LABELS,
        ),
        "pv_phase_count_rows": count_rows_by_key(
            first_count_map(render_count_maps.get("pv_phase_counts"))
        ),
        "pvc_phase_count_rows": count_rows_by_key(
            first_count_map(render_count_maps.get("pvc_phase_counts"))
        ),
        "pod_cpu_usage_rows": slice_rows(
            first_list(
                render_table_inputs.get("top_pod_cpu_usage_summary"),
                workload_artifact.get("top_pod_cpu_usage_summary"),
                workload_inputs.get("top_pod_cpu_usage_summary"),
            ),
            safe_limit(render_limits.get("pod_usage_table_limit"), 25),
        ),
        "pod_memory_usage_rows": slice_rows(
            first_list(
                render_table_inputs.get("top_pod_memory_usage_summary"),
                workload_artifact.get("top_pod_memory_usage_summary"),
                workload_inputs.get("top_pod_memory_usage_summary"),
            ),
            safe_limit(render_limits.get("pod_usage_table_limit"), 25),
        ),
        "storageclass_rows": sorted_dict_list(
            render_table_inputs.get("storageclass_summary"), "name"
        ),
        "workload_probe_issue_type_count_rows": count_rows_by_value_desc(
            first_count_map(
                render_count_maps.get("workload_probe_issue_type_counts"),
                workload_artifact.get("workload_probe_issue_type_counts"),
                workload_inputs.get("workload_probe_issue_type_counts"),
            )
        ),
    }


def build_posture_render_slices(posture_artifacts):
    payload = {}
    for artifact_key in POSTURE_FACT_PREFIXES:
        artifact = posture_artifacts.get(artifact_key) or {}
        render_inputs = artifact.get("render_inputs", {})
        allowed_render_input_keys = POSTURE_RENDER_INPUT_KEYS.get(artifact_key, set())
        artifact_slice = {
            key: value for key, value in artifact.items() if key != "render_inputs"
        }
        payload[artifact_key] = {
            "artifact": artifact_slice,
            "render_inputs": {
                key: render_inputs[key]
                for key in allowed_render_input_keys
                if isinstance(render_inputs, dict) and key in render_inputs
            },
        }
    return payload


def build_capability_artifact_sections(capability_artifacts):
    sections = {}
    for key, artifact in (capability_artifacts or {}).items():
        section = artifact.get("section") if isinstance(artifact, dict) else None
        if isinstance(section, dict) and section:
            sections[key] = section
    return sections


def compact_collection_artifact(artifact):
    artifact = dict_value(artifact)
    return {
        "schema_version": artifact.get("schema_version"),
        "repo_contract_version": artifact.get("repo_contract_version"),
        "run_id": artifact.get("run_id"),
        "platform_family": artifact.get("platform_family"),
        "report_mode": artifact.get("report_mode"),
        "key": artifact.get("key"),
        "kind": artifact.get("kind"),
        "status": artifact.get("status"),
        "generated_at": artifact.get("generated_at"),
        "cluster_profile": artifact.get("cluster_profile") or {},
        "evidence_summary": artifact.get("evidence_summary") or {},
        "collection_summary": artifact.get("collection_summary") or {},
        "collection_failures": artifact.get("collection_failures") or [],
        "collection_skipped_optional_commands": artifact.get(
            "collection_skipped_optional_commands"
        )
        or [],
        "live_support_data": artifact.get("live_support_data") or {},
    }


def compact_analysis_graph_artifact(artifact):
    artifact = dict_value(artifact)
    return {
        "schema_version": artifact.get("schema_version"),
        "repo_contract_version": artifact.get("repo_contract_version"),
        "run_id": artifact.get("run_id"),
        "platform_family": artifact.get("platform_family"),
        "report_mode": artifact.get("report_mode"),
        "key": artifact.get("key"),
        "kind": artifact.get("kind"),
        "status": artifact.get("status"),
        "generated_at": artifact.get("generated_at"),
        "cluster_profile": artifact.get("cluster_profile") or {},
    }


def build_payload(data):
    shared_loaded = load_artifact_dir(
        data.get("shared_dir") or "", key_func=shared_artifact_key
    )
    posture_loaded = load_artifact_dir(data.get("postures_dir") or "")
    capability_loaded = load_artifact_dir(data.get("capabilities_dir") or "")

    shared_artifacts = recursive_merge(data.get("openshift_shared_artifacts"), shared_loaded)
    posture_artifacts = recursive_merge(
        data.get("openshift_posture_artifacts"), posture_loaded
    )
    capability_artifacts = recursive_merge(
        data.get("openshift_capability_artifacts"), capability_loaded
    )

    collection_artifact = shared_artifacts.get("collection") or {}
    analysis_graph_artifact = shared_artifacts.get("analysis_graph") or {}
    collected_resource_graph = collection_artifact.get(
        "collected_resource_graph", data.get("collected_resource_graph") or {}
    )
    analysis_graph = analysis_graph_artifact or data.get("analysis_graph") or {}
    cluster_profile = (
        analysis_graph_artifact.get("cluster_profile")
        or collection_artifact.get("cluster_profile")
        or data.get("cluster_profile")
        or {}
    )
    support_table_graph = analysis_graph or collected_resource_graph or {}

    payload = {
        "openshift_shared_collection_artifact": compact_collection_artifact(
            collection_artifact
        ),
        "openshift_shared_analysis_graph_artifact": compact_analysis_graph_artifact(
            analysis_graph_artifact
        ),
        "openshift_artifact_backed_cluster_profile": cluster_profile,
        "openshift_capability_artifact_sections": build_capability_artifact_sections(
            capability_artifacts
        ),
        "openshift_posture_render_slices": build_posture_render_slices(
            posture_artifacts
        ),
        "openshift_template_graph_render": build_template_graph_render(
            support_table_graph
        ),
        "openshift_template_table_render": build_template_table_render(
            data, posture_artifacts, cluster_profile
        ),
        "analysis_graph_ingress_count": len(graph_items(analysis_graph, "ingresses")),
        "cluster_profile": cluster_profile,
        "evidence_summary": collection_artifact.get(
            "evidence_summary", data.get("evidence_summary") or {}
        ),
        "assessment_collection_summary": collection_artifact.get(
            "collection_summary", data.get("assessment_collection_summary") or {}
        ),
        "assessment_collection_failures": collection_artifact.get(
            "collection_failures", data.get("assessment_collection_failures") or []
        ),
        "assessment_collection_skipped_optional_commands": collection_artifact.get(
            "collection_skipped_optional_commands",
            data.get("assessment_collection_skipped_optional_commands") or [],
        ),
        "live_support_data": collection_artifact.get(
            "live_support_data", data.get("live_support_data") or {}
        ),
        "assessment_operator_status_summary": build_operator_summary(support_table_graph),
        "assessment_mcp_summary": build_mcp_summary(support_table_graph),
        "assessment_route_summary": build_route_summary(support_table_graph),
    }
    return payload


def main():
    data = json.loads(sys.stdin.read() or "{}")
    payload = build_payload(data)
    output_path = data.get("output_path") or ""
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"output_path": str(path)}, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
