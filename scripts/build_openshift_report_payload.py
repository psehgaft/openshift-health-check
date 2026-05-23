#!/usr/bin/env python3
"""Build the shared OpenShift report payload from resolved report facts."""

import argparse
import json
import os
import sys
from pathlib import Path


def get(data, key, default=None):
    if isinstance(data, dict) and key in data:
        return data[key]
    return default


def nested_get(data, *keys, default=None):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def truthy(value):
    return bool(value)


def recursive_merge(left, right):
    merged = dict(left or {})
    for key, value in (right or {}).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = recursive_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def collected_bool_path(data, key):
    return len(str(data.get(key) or "").strip()) > 0


def build_checkpoint(data):
    return {
        "manifest_path": data.get("report_resume_manifest_path") or "",
        "last_completed_stage": data.get("report_resume_last_completed_stage") or "",
        "resume_next_stage": data.get("report_resume_last_resume_next_stage") or "",
        "run_mode": data.get("report_run_mode") or "fresh",
    }


def build_audit(data):
    return {
        "score_total": data.get("audit_score_total", 0),
        "score_max": data.get("audit_score_max", 0),
        "cluster_health_score": data.get("cluster_health_score", 0),
        "cluster_health_score_label": data.get("cluster_health_score_label") or "unknown",
        "cluster_health_score_legend": data.get("cluster_health_score_legend") or [],
        "critical_checks": data.get("audit_critical_checks") or [],
        "warning_checks": data.get("audit_warning_checks") or [],
        "checks": data.get("audit_checks") or [],
    }


def build_collected_evidence_coverage(data):
    coverage = dict(data.get("evidence_coverage") or {})
    must_gather_present = collected_bool_path(data, "must_gather_path")
    inspect_present = collected_bool_path(data, "inspect_path")
    cluster_compare_present = collected_bool_path(data, "cluster_compare_path")
    managed_gates_present = collected_bool_path(data, "managed_gates_path")
    advisor_present = collected_bool_path(data, "advisor_export_path")
    insights_present = collected_bool_path(data, "insights_archive_path")
    sosreport_paths = data.get("sosreport_paths") or []
    prometheus_summary = data.get("prometheus_evidence_summary") or {}

    return recursive_merge(
        coverage,
        {
            "must_gather": {
                "category": "oc-native",
                "applicable": True,
                "status": "present" if must_gather_present else "missing",
                "detail": (
                    "Collected from oc adm must-gather."
                    if must_gather_present
                    else "No oc adm must-gather directory was provided."
                ),
                "requested": True,
                "collected": must_gather_present,
            },
            "inspect": {
                "category": "oc-native",
                "applicable": True,
                "status": get(data.get("evidence_coverage") or {}, "inspect", "missing"),
                "detail": (
                    "Collected from oc adm inspect."
                    if inspect_present
                    else "No oc adm inspect directory was provided."
                ),
                "requested": True,
                "collected": inspect_present,
            },
            "prometheus_query": {
                "category": "metric-api",
                "applicable": False,
                "status": prometheus_summary.get("status", "not-collected"),
                "detail": (
                    "Prometheus/Thanos metrics are queried only during live runs; "
                    "collected-state mode relies on metrics already present in "
                    "must-gather or support artifacts."
                ),
                "requested": False,
                "collected": prometheus_summary.get("collected", False),
                "transport": prometheus_summary.get("transport", "unavailable"),
                "query_count": prometheus_summary.get("query_count", 0),
                "non_empty_result_count": prometheus_summary.get(
                    "non_empty_result_count", 0
                ),
            },
            "cluster_compare": {
                "category": "oc-plugin",
                "applicable": True,
                "status": get(
                    data.get("evidence_coverage") or {}, "cluster_compare", "missing"
                ),
                "detail": (
                    "Collected from oc cluster-compare output."
                    if cluster_compare_present
                    else "No oc cluster-compare output was provided."
                ),
                "requested": False,
                "collected": cluster_compare_present,
            },
            "managed_gates": {
                "category": "provider-api",
                "applicable": managed_gates_present,
                "status": get(
                    data.get("evidence_coverage") or {}, "managed_gates", "missing"
                ),
                "detail": (
                    "Collected from provider-managed gate evidence."
                    if managed_gates_present
                    else "No provider-managed gate evidence was provided."
                ),
                "requested": False,
                "collected": managed_gates_present,
            },
            "advisor_export": {
                "category": "external-service",
                "applicable": True,
                "status": get(
                    data.get("evidence_coverage") or {}, "advisor_data", "missing"
                ),
                "detail": (
                    "Collected from Advisor or Insights export."
                    if advisor_present
                    else "No Advisor or Insights export was provided."
                ),
                "requested": False,
                "collected": advisor_present,
            },
            "insights_archive": {
                "category": "oc-native",
                "applicable": True,
                "status": get(
                    data.get("evidence_coverage") or {}, "insights_archive", "missing"
                ),
                "detail": (
                    "Collected from a supplied Insights archive directory."
                    if insights_present
                    else "No live Insights Operator archive is available in "
                    "collected-state mode unless supplied in the bundle."
                ),
                "requested": False,
                "collected": insights_present,
            },
            "sosreport": {
                "category": "node-level",
                "applicable": True,
                "status": get(
                    data.get("evidence_coverage") or {}, "node_diagnostics", "missing"
                ),
                "detail": (
                    "Collected from oc debug node/<node> plus sosreport or provided "
                    "node-level archives."
                    if len(sosreport_paths) > 0
                    else "No oc debug node/<node> sosreport or node-level archive was "
                    "provided."
                ),
                "requested": False,
                "collected": len(sosreport_paths) > 0,
                "count": len(sosreport_paths),
            },
        },
    )


def build_collected_payload(data):
    now = data.get("ansible_date_time_iso8601") or ""
    evidence_hygiene_data = data.get("evidence_hygiene_data") or {}
    openshift_shared_collection_artifact = (
        data.get("openshift_shared_collection_artifact") or {}
    )
    return {
        "metadata": {
            "generated_at": now,
            "completed_at": now,
            "context": data.get("report_context") or "not-collected",
            "api_server": data.get("report_api_server") or "not-collected",
            "user": data.get("report_user") or "not-collected",
            "report_confidence": data.get("report_confidence") or "medium",
            "local_user": data.get("local_user") or "unknown",
            "local_hostname": data.get("local_hostname") or "unknown",
            "platform_family": data.get("platform_family") or "openshift",
            "provider_family": data.get("resolved_provider_family")
            or data.get("provider_family")
            or "generic",
            "evidence_mode": data.get("evidence_mode_resolved") or "must_gather",
            "cluster_type": data.get("report_cluster_type")
            or nested_get(data, "cluster_profile", "cluster_classification_label")
            or nested_get(data, "cluster_profile", "deployment_type")
            or data.get("platform_family")
            or "openshift",
            "checkpoint": build_checkpoint(data),
        },
        "cluster_profile": data.get("openshift_artifact_backed_cluster_profile")
        or data.get("cluster_profile")
        or {},
        "cluster_current_state": {},
        "health_summary": data.get("assessment_health_summary") or {},
        "suggested_next_steps": data.get("suggested_next_steps") or [],
        "execution_stats": data.get("execution_stats") or {},
        "audit": build_audit(data),
        "supportability": {
            "summary": data.get("supportability_summary") or {},
            "diagnostics_coverage": data.get("diagnostics_coverage") or {},
            "product_evidence": data.get("assessment_product_evidence") or {},
            "product_evidence_findings": data.get("assessment_product_evidence_findings")
            or [],
            "connected_cluster_posture": data.get(
                "assessment_connected_cluster_posture"
            )
            or data.get("connected_cluster_posture")
            or {},
            "connected_cluster_findings": data.get(
                "assessment_connected_cluster_findings"
            )
            or data.get("connected_cluster_findings")
            or [],
            "node_diagnostics_summary": data.get("node_diagnostics_summary") or {},
            "node_diagnostics_findings": data.get("node_diagnostics_findings") or [],
            "advisor_summary": data.get("advisor_summary") or {},
            "advisor_findings": data.get("advisor_findings") or [],
            "insights_archive_summary": data.get("insights_archive_summary") or {},
            "insights_archive_findings": data.get("insights_archive_findings") or [],
            "managed_gate_summary": data.get("managed_gate_summary") or {},
            "managed_gate_findings": data.get("managed_gate_findings") or [],
            "reference_compliance_summary": data.get("reference_compliance_summary")
            or {},
            "reference_compliance_findings": data.get("reference_compliance_findings")
            or [],
            "etcd_ocp_diag_summary": data.get("etcd_ocp_diag_summary") or {},
            "etcd_ocp_diag_findings": data.get("etcd_ocp_diag_findings") or [],
            "omc_summary": data.get("omc_summary") or {},
            "omc_findings": data.get("omc_findings") or [],
        },
        "evidence": {
            "summary": openshift_shared_collection_artifact.get(
                "evidence_summary", data.get("evidence_summary") or {}
            ),
            "coverage": build_collected_evidence_coverage(data),
            "limitations": data.get("evidence_limitations") or [],
            "sources": data.get("evidence_sources") or [],
            "must_gather_inventory": data.get("must_gather_inventory") or {},
            "hygiene_summary": evidence_hygiene_data.get("summary", {}),
            "hygiene_findings": evidence_hygiene_data.get("findings", []),
            "hygiene_roots": evidence_hygiene_data.get("roots", []),
            "sensitive_candidates": evidence_hygiene_data.get(
                "sensitive_candidates", []
            ),
            "redaction_guidance": evidence_hygiene_data.get("redaction_guidance", []),
            "redaction_outputs": data.get("evidence_redaction_outputs") or {},
        },
        "domains": data.get("openshift_report_domain_payload") or {},
        "findings": {
            "assessment_health": data.get("assessment_health_findings") or [],
            "reference_compliance": data.get("reference_compliance_findings") or [],
            "node_diagnostics": data.get("node_diagnostics_findings") or [],
            "advisor": data.get("advisor_findings") or [],
            "managed_gates": data.get("managed_gate_findings") or [],
            "etcd_ocp_diag": data.get("etcd_ocp_diag_findings") or [],
            "omc": data.get("omc_findings") or [],
            "insights_archive": data.get("insights_archive_findings") or [],
            "connected_cluster": data.get("assessment_connected_cluster_findings")
            or data.get("connected_cluster_findings")
            or [],
            "product_evidence": data.get("assessment_product_evidence_findings") or [],
        },
        "metrics": {
            "diagnostics_coverage": data.get("diagnostics_coverage") or {},
            "prometheus_evidence_summary": data.get("prometheus_evidence_summary") or {},
            "evidence_coverage": data.get("evidence_coverage") or {},
            "must_gather_inventory": data.get("must_gather_inventory") or {},
            "day2_posture_summary": data.get("day2_posture_summary") or {},
            "backup_storage_location_summary": data.get("backup_storage_location_summary")
            or [],
            "backup_schedule_summary": data.get("backup_schedule_summary") or [],
            "backup_summary": data.get("backup_summary") or [],
            "restore_summary": data.get("restore_summary") or [],
            "machinehealthcheck_summary": data.get("machinehealthcheck_summary") or [],
        },
        "supplemental_artifacts": {
            "cluster_compare": data.get("cluster_compare_data") or {},
            "inspect": data.get("inspect_data") or {},
            "sosreport": data.get("sosreport_data") or {},
            "advisor_export": data.get("advisor_export_data") or {},
            "insights_archive": data.get("insights_archive_data") or {},
            "managed_gates": data.get("managed_gates_data") or {},
        },
        "cluster_compare": {"data": data.get("cluster_compare_data") or {}},
        "inspect": {"data": data.get("inspect_data") or {}},
        "sosreport": {"data": data.get("sosreport_data") or {}},
        "advisor_export": {"data": data.get("advisor_export_data") or {}},
        "insights_archive": {"data": data.get("insights_archive_data") or {}},
        "managed_gates": {"data": data.get("managed_gates_data") or {}},
    }


def build_live_supportability(data):
    live_support_data = data.get("live_support_data") or {}
    return {
        "summary": data.get("live_supportability_summary") or {},
        "reference_compliance_summary": data.get("live_reference_compliance_summary")
        or {},
        "reference_compliance_findings": data.get("top_live_cluster_compare_findings")
        or [],
        "managed_gate_summary": nested_get(
            live_support_data, "parsed", "managed_gates", "summary", default={}
        ),
        "managed_gate_findings": data.get("top_live_managed_gate_findings") or [],
        "advisor_summary": nested_get(
            live_support_data, "parsed", "advisor_export", "summary", default={}
        ),
        "advisor_findings": data.get("top_live_advisor_findings") or [],
        "insights_archive_summary": data.get("insights_archive_summary") or {},
        "insights_archive_findings": data.get("insights_archive_findings") or [],
        "must_gather_findings": data.get("top_live_must_gather_findings") or [],
        "etcd_ocp_diag_summary": data.get("etcd_ocp_diag_summary") or {},
        "etcd_ocp_diag_findings": data.get("etcd_ocp_diag_findings") or [],
        "omc_summary": data.get("omc_summary") or {},
        "omc_findings": data.get("top_live_omc_findings") or [],
        "node_diagnostics_summary": data.get("live_node_diagnostics_summary") or {},
        "node_diagnostics_findings": (data.get("top_live_inspect_findings") or [])
        + (data.get("top_live_sosreport_findings") or []),
    }


def build_live_findings(data, include_aged_pods):
    findings = {
        "report_collection_failures": data.get("report_collection_failures") or [],
        "degraded_operators": data.get("degraded_operators") or [],
        "unavailable_operators": data.get("unavailable_operators") or [],
        "not_ready_nodes": data.get("not_ready_nodes") or [],
        "pressure_nodes": data.get("pressure_nodes") or [],
        "infrastructure_component_issues": data.get("infrastructure_component_issues")
        or [],
        "apiservice_issues": data.get("top_apiservice_issues") or [],
        "ingresscontroller_issues": data.get("ingresscontroller_issues") or [],
        "workload_health_issues": data.get("top_workload_health_issues") or [],
        "unhealthy_user_pods": data.get("top_unhealthy_user_pods") or [],
        "workload_probe_findings": data.get("top_workload_probe_findings") or [],
        "high_restart_pods": data.get("top_high_restart_pods") or [],
        "high_replica_workloads": data.get("top_high_replica_workloads") or [],
        "orphan_pods": data.get("top_orphan_pods") or [],
        "workload_label_governance_findings": data.get(
            "top_workload_label_governance_findings"
        )
        or [],
        "workload_resource_findings": data.get("top_workload_resource_findings") or [],
        "overprovisioned_pods": data.get("top_overprovisioned_pods") or [],
        "failed_pipelineruns": data.get("top_failed_pipelineruns") or [],
        "buildconfigs_without_triggers": data.get("top_buildconfigs_without_triggers")
        or [],
        "quota_pressure_findings": data.get("top_quota_pressure_findings") or [],
        "route_issues": data.get("top_route_issues") or [],
        "ingress_issues": data.get("top_ingress_issues") or [],
        "route_host_conflicts": data.get("top_route_host_conflicts") or [],
        "ingress_host_conflicts": data.get("top_ingress_host_conflicts") or [],
        "auth_findings": data.get("auth_findings") or [],
        "security_findings": data.get("top_security_findings") or [],
        "workload_practice_findings": data.get("top_workload_practice_findings") or [],
        "empty_user_namespaces": data.get("empty_user_namespaces") or [],
        "services_without_endpoints": data.get("top_services_without_endpoints") or [],
        "likely_unused_serviceaccounts": data.get("top_likely_unused_serviceaccounts")
        or [],
        "likely_unused_configmaps": data.get("top_likely_unused_configmaps") or [],
        "likely_unused_secrets": data.get("top_likely_unused_secrets") or [],
        "likely_unused_crds": data.get("top_likely_unused_crds") or [],
        "image_registry_findings": data.get("top_image_registry_findings") or [],
        "internal_registry_workloads": data.get("top_internal_registry_workloads") or [],
        "feature_findings": data.get("top_feature_findings") or [],
        "scc_grant_findings": data.get("top_scc_grant_findings") or [],
        "compliance_suite_findings": data.get("top_compliance_suite_findings") or [],
        "backup_posture_findings": data.get("top_backup_posture_findings") or [],
        "machine_healthcheck_findings": data.get("top_machine_healthcheck_findings")
        or [],
        "day2_posture_findings": data.get("top_day2_posture_findings") or [],
        "cluster_compare_findings": data.get("top_live_cluster_compare_findings") or [],
        "managed_gate_findings": data.get("top_live_managed_gate_findings") or [],
        "advisor_findings": data.get("top_live_advisor_findings") or [],
        "insights_archive": data.get("insights_archive_findings") or [],
        "must_gather_findings": data.get("top_live_must_gather_findings") or [],
        "etcd_ocp_diag": data.get("etcd_ocp_diag_findings") or [],
        "omc": data.get("top_live_omc_findings") or [],
        "inspect_findings": data.get("top_live_inspect_findings") or [],
        "sosreport_findings": data.get("top_live_sosreport_findings") or [],
        "observability_findings": data.get("top_observability_findings") or [],
        "deprecated_crd_findings": data.get("top_deprecated_crd_findings") or [],
        "deprecated_api_lines": data.get("top_deprecated_api_lines") or [],
        "pv_issues": data.get("top_pv_issues") or [],
        "pvc_issues": data.get("top_pvc_issues") or [],
        "expiring_certificates_critical": data.get("expiring_certificates_critical")
        or [],
        "expiring_certificates_warning": data.get("expiring_certificates_warning") or [],
    }
    if include_aged_pods:
        findings["aged_user_pods"] = data.get("top_aged_user_pods") or []
        findings["stale_user_pods"] = data.get("top_stale_user_pods") or []
        findings["stale_configmaps"] = data.get("top_stale_configmaps") or []
        findings["stale_generic_secrets"] = data.get("top_stale_generic_secrets") or []
        findings["stale_dockerconfigjson_secrets"] = data.get("top_stale_dockerconfigjson_secrets") or []
    return findings


def build_live_metrics(data, resume):
    report_collection = data.get("report_collection") or {}
    if resume:
        return {
            "report_collection": {
                "failed_commands": report_collection.get("failed_commands", 0),
                "core_failed_commands": report_collection.get("core_failed_commands", 0),
            },
            "report_confidence": data.get("report_confidence") or "unknown",
        }

    live_support_data = data.get("live_support_data") or {}
    parsed = live_support_data.get("parsed") or {}
    return {
        "report_collection": report_collection,
        "day2_posture_summary": data.get("day2_posture_summary") or {},
        "live_cluster_compare_summary": nested_get(
            parsed, "cluster_compare", "summary", default={}
        ),
        "live_managed_gates_summary": nested_get(
            parsed, "managed_gates", "summary", default={}
        ),
        "live_advisor_summary": nested_get(
            parsed, "advisor_export", "summary", default={}
        ),
        "live_insights_archive_summary": nested_get(
            parsed, "insights_archive", "summary", default={}
        ),
        "prometheus_evidence_summary": data.get("prometheus_evidence_summary") or {},
        "prom_query_status_map": data.get("control_plane_query_status_map")
        or data.get("prom_query_status_map")
        or {},
        "prom_query_error_map": data.get("prom_query_error_map") or {},
        "runtime_signal_resolution_map": data.get("runtime_signal_resolution_map") or {},
        "observability_signal_resolution_map": data.get(
            "observability_signal_resolution_map"
        )
        or {},
        "control_plane_evidence_summary": nested_get(
            data, "control_plane_evidence_data", "summary", default={}
        ),
        "control_plane_offline_signals_present": data.get(
            "control_plane_offline_signals_present", False
        ),
        "live_inspect_summary": nested_get(parsed, "inspect", "summary", default={}),
        "live_sosreport_summary": nested_get(
            parsed, "sosreport", "summary", default={}
        ),
        "report_collection_success_rate_pct": data.get(
            "report_collection_success_rate_pct", 0
        ),
        "report_confidence": data.get("report_confidence") or "unknown",
        "report_confidence_detail": data.get("report_confidence_detail") or "",
        "infrastructure_component_summary": data.get(
            "infrastructure_component_summary"
        )
        or [],
        "ingresscontroller_summary": data.get("ingresscontroller_summary") or [],
        "observability_forwarding_summary": data.get(
            "observability_forwarding_summary"
        )
        or {},
        "apiservice_issues": data.get("apiservice_issues") or [],
        "secret_type_counts": data.get("secret_type_counts") or {},
        "buildconfig_strategy_counts": data.get("buildconfig_strategy_counts") or {},
        "pipelinerun_status_counts": data.get("pipelinerun_status_counts") or {},
        "compliance_result_counts": data.get("compliance_result_counts") or {},
        "compliance_suite_summary": data.get("compliance_suite_summary") or [],
        "compliance_operator_summary": data.get("compliance_operator_summary") or {},
        "compliance_standards_summary": data.get("compliance_standards_summary") or [],
        "backup_storage_location_summary": data.get("backup_storage_location_summary")
        or [],
        "backup_schedule_summary": data.get("backup_schedule_summary") or [],
        "backup_summary": data.get("backup_summary") or [],
        "restore_summary": data.get("restore_summary") or [],
        "machinehealthcheck_summary": data.get("machinehealthcheck_summary") or [],
        "scc_posture_summary": data.get("scc_posture_summary") or [],
        "dataprotectionapplication_summary": data.get("dataprotectionapplication_summary")
        or [],
        "apiserver_readyz_status": data.get("apiserver_readyz_status") or "unavailable",
        "apiserver_readyz_failed_checks": data.get("apiserver_readyz_failed_checks", 0),
        "etcd_wal_fsync_p99_ms": data.get("etcd_wal_fsync_p99_ms") or "",
        "etcd_backend_commit_p99_ms": data.get("etcd_backend_commit_p99_ms") or "",
        "etcd_leader_changes_5m": data.get("etcd_leader_changes_5m") or "",
        "etcd_members_reporting_leader": data.get("etcd_members_reporting_leader")
        or "",
        "etcd_leader_count": data.get("etcd_leader_count") or "",
        "etcd_peer_rtt_p99_ms": data.get("etcd_peer_rtt_p99_ms") or "",
        "apiserver_request_p99_seconds": data.get("apiserver_request_p99_seconds")
        or "",
        "apiserver_request_5xx_rate": data.get("apiserver_request_5xx_rate") or "",
        "apiserver_request_read_rate": data.get("apiserver_request_read_rate") or "",
        "apiserver_request_write_rate": data.get("apiserver_request_write_rate") or "",
        "apiserver_current_read_inflight": data.get("apiserver_current_read_inflight")
        or "",
        "apiserver_current_write_inflight": data.get(
            "apiserver_current_write_inflight"
        )
        or "",
        "apiserver_storage_objects_total": data.get("apiserver_storage_objects_total")
        or "",
        "top_alert_groups": data.get("top_alert_groups") or [],
        "top_event_reasons": data.get("top_event_reasons") or [],
        "top_pod_cpu_usage_summary": data.get("top_pod_cpu_usage_summary") or [],
        "top_pod_memory_usage_summary": data.get("top_pod_memory_usage_summary") or [],
        "node_capacity_summary_by_density_desc": data.get(
            "node_capacity_summary_by_density_desc"
        )
        or [],
    }


def build_live_payload(data, resume):
    now = (
        data.get("report_resume_report_timestamp")
        or data.get("report_generated_at")
        or data.get("ansible_date_time_iso8601")
        or ""
    )
    live_support_data = data.get("live_support_data") or {}
    artifacts = live_support_data.get("artifacts") or {}
    parsed = live_support_data.get("parsed") or {}
    context = (
        data.get("report_resume_oc_context")
        if resume
        else data.get("oc_context_stdout")
    ) or "unknown"
    api_server = (
        data.get("report_resume_api_server") if resume else data.get("oc_server_stdout")
    ) or "unknown"
    user = (data.get("report_resume_ocp_user") if resume else data.get("oc_user_stdout")) or "unknown"
    cluster_type = (
        data.get("report_render_cluster_type")
        if resume
        else data.get("report_cluster_type")
    ) or data.get("platform_family") or "openshift"
    cluster_profile = (
        data.get("report_render_cluster_profile")
        if resume
        else data.get("openshift_artifact_backed_cluster_profile")
    ) or data.get("cluster_profile") or {}

    return {
        "metadata": {
            "generated_at": now,
            "completed_at": now,
            "context": str(context).strip() or "unknown",
            "api_server": str(api_server).strip() or "unknown",
            "user": str(user).strip() or "unknown",
            "cluster_type": cluster_type,
            "report_confidence": data.get("report_confidence") or "unknown",
            "local_user": data.get("local_user") or "unknown",
            "local_hostname": data.get("local_hostname") or "unknown",
            "platform_family": data.get("platform_family") or "openshift",
            "provider_family": data.get("resolved_provider_family")
            or data.get("provider_family")
            or "generic",
            "evidence_mode": "live",
            "checkpoint": build_checkpoint(data),
        },
        "cluster_profile": cluster_profile,
        "cluster_current_state": data.get("cluster_current_state") or {},
        "health_summary": data.get("health_summary") or {},
        "suggested_next_steps": data.get("suggested_next_steps") or [],
        "execution_stats": data.get("execution_stats") or {},
        "audit": build_audit(data),
        "supportability": build_live_supportability(data),
        "evidence": {
            "summary": data.get("live_evidence_summary") or {},
            "coverage": data.get("live_evidence_coverage") or {},
        },
        "domains": data.get("openshift_report_domain_payload") or {},
        "findings": build_live_findings(data, include_aged_pods=resume),
        "metrics": build_live_metrics(data, resume),
        "supplemental_artifacts": {
            "collection": artifacts.get("collection", {}),
            "summary": artifacts.get("summary", {}),
            **(
                {}
                if resume
                else {
                    "must_gather_inventory": nested_get(
                        parsed, "must_gather_inventory", default={}
                    ),
                    "inspect": parsed.get("inspect", {}),
                    "cluster_compare": parsed.get("cluster_compare", {}),
                    "managed_gates": parsed.get("managed_gates", {}),
                    "advisor_export": parsed.get("advisor_export", {}),
                    "insights_archive": parsed.get("insights_archive", {}),
                    "sosreport": parsed.get("sosreport", {}),
                }
            ),
        },
    }


def build_payload(data):
    mode = data.get("payload_mode") or "collected"
    if mode == "collected":
        return build_collected_payload(data)
    if mode == "live_resume":
        return build_live_payload(data, resume=True)
    if mode == "live":
        return build_live_payload(data, resume=False)
    raise ValueError(f"unsupported payload_mode: {mode}")


def build_render_payload(payload):
    """Return the subset needed by the Markdown template.

    The full JSON report can carry large supplemental artifacts. The Markdown
    render path primarily needs metadata, health, supportability, and domains.
    Keeping only those fields in Ansible facts avoids a second large
    parse/serialize cycle without changing the persisted JSON report.
    """
    if not isinstance(payload, dict):
        return {}
    keys = [
        "metadata",
        "cluster_profile",
        "cluster_current_state",
        "health_summary",
        "suggested_next_steps",
        "execution_stats",
        "audit",
        "supportability",
        "evidence",
        "domains",
        "findings",
        "metrics",
    ]
    return {key: payload.get(key) for key in keys if key in payload}


def write_json_payload(payload, paths):
    written = []
    content = json.dumps(payload, indent=4, ensure_ascii=False, sort_keys=True) + "\n"
    for raw_path in paths or []:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o644)
        written.append(str(path))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        nargs="?",
        default="-",
        help="Optional JSON input path; stdin is used when absent or missing.",
    )
    parser.add_argument(
        "--output-json",
        action="append",
        default=[],
        help="Write the full pretty JSON payload to this path. May be repeated.",
    )
    parser.add_argument(
        "--stdout-mode",
        choices=["full", "render"],
        default="full",
        help="Select whether stdout receives the full payload or render-sized payload.",
    )
    args = parser.parse_args()

    if args.input_path != "-":
        try:
            with open(args.input_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            data = json.loads(sys.stdin.read() or "{}")
    else:
        data = json.loads(sys.stdin.read() or "{}")
    payload = build_payload(data)
    written = write_json_payload(payload, args.output_json)
    stdout_payload = build_render_payload(payload) if args.stdout_mode == "render" else payload
    if written:
        stdout_payload = dict(stdout_payload)
        stdout_payload["_payload_written_paths"] = written
    print(json.dumps(stdout_payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
