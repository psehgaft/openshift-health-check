#!/usr/bin/env python3
import json
import sys

import build_external_alert_delivery_findings
import build_log_forwarding_findings
import build_metrics_forwarding_findings
import build_vendor_managed_telemetry


DEFAULT_VENDOR = {
    "vendor_managed_metrics_forwarding_present": False,
    "vendor_managed_log_forwarding_present": False,
    "metrics_vendor_names": [],
    "log_vendor_names": [],
}

DEFAULT_LOG = {
    "findings": [],
    "outputs": [],
    "external_outputs": [],
    "pipeline_counts": {"application": 0, "infrastructure": 0, "audit": 0},
    "external_pipeline_counts": {"application": 0, "infrastructure": 0, "audit": 0},
}

DEFAULT_METRICS = {
    "findings": [],
    "cluster_external_count": 0,
    "user_external_count": 0,
}

DEFAULT_ALERTS = {
    "findings": [],
    "receivers": [],
    "config_sources": [],
    "alert_delivery_source_count": 0,
    "external_alert_receiver_count": 0,
    "external_alert_delivery_configured": False,
    "alert_routing_to_external_receiver_configured": False,
    "alertmanagerconfigs_with_external_routes": 0,
    "alertmanagerconfigs_without_route_receivers": 0,
}


def as_dict(value):
    return value if isinstance(value, dict) else {}


def nested_get(data, path, default=None):
    value = data
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return value if value is not None else default


def bool_value(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def build(data):
    graph = as_dict(data.get("analysis_graph"))
    vendor = build_vendor_managed_telemetry.build({
        "dynakubes": nested_get(graph, ["dynakubes", "items"], []),
        "edgeconnects": nested_get(graph, ["edgeconnects", "items"], []),
        "datadogagents": nested_get(graph, ["datadogagents", "items"], []),
        "clusteragents": nested_get(graph, ["clusteragents", "items"], []),
        "infravizs": nested_get(graph, ["infravizs", "items"], []),
        "lokistacks": nested_get(graph, ["lokistacks", "items"], []),
        "crds": nested_get(graph, ["crds", "items"], []),
        "namespaces": nested_get(graph, ["namespaces", "items"], []),
        "pods": nested_get(graph, ["pods", "items"], []),
        "deployments": nested_get(graph, ["deployments", "items"], []),
        "daemonsets": nested_get(graph, ["daemonsets", "items"], []),
        "statefulsets": nested_get(graph, ["statefulsets", "items"], []),
    })
    vendor = vendor if isinstance(vendor, dict) else dict(DEFAULT_VENDOR)

    log_data = build_log_forwarding_findings.build({
        "items": nested_get(graph, ["clusterlogforwarders", "items"], []),
        "vendor_managed_present": vendor.get("vendor_managed_log_forwarding_present", False),
        "vendor_names": vendor.get("log_vendor_names", []),
        "require_cluster_log_forwarder": bool_value(data.get("require_cluster_log_forwarder")),
    })
    metrics_data = build_metrics_forwarding_findings.build({
        "cluster_remote_write": nested_get(data, ["cluster_monitoring_config_parsed", "prometheusK8s", "remoteWrite"], []),
        "user_remote_write": nested_get(data, ["user_workload_monitoring_config_parsed", "prometheus", "remoteWrite"], []),
        "vendor_managed_present": vendor.get("vendor_managed_metrics_forwarding_present", False),
        "vendor_names": vendor.get("metrics_vendor_names", []),
        "require_external_metrics_remote_write": bool_value(data.get("require_external_metrics_remote_write")),
    })
    alert_data = build_external_alert_delivery_findings.build({
        "items": nested_get(graph, ["alertmanagerconfigs", "items"], []),
        "cluster_alertmanager_additional_configs": nested_get(data, ["cluster_monitoring_config_parsed", "alertmanagerMain", "additionalAlertmanagerConfigs"], []),
        "user_workload_alertmanager_additional_configs": nested_get(data, ["user_workload_monitoring_config_parsed", "alertmanager", "additionalAlertmanagerConfigs"], []),
        "require_external_alert_delivery": bool_value(data.get("require_external_alert_delivery")),
    })

    return {
        "vendor": vendor if isinstance(vendor, dict) else dict(DEFAULT_VENDOR),
        "log_forwarding": log_data if isinstance(log_data, dict) else dict(DEFAULT_LOG),
        "metrics_forwarding": metrics_data if isinstance(metrics_data, dict) else dict(DEFAULT_METRICS),
        "alert_delivery": alert_data if isinstance(alert_data, dict) else dict(DEFAULT_ALERTS),
    }


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_observability_forwarding_bundle.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(as_dict(data))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
