#!/usr/bin/env python3
import json
import sys


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def nested_get(data, path, default=None):
    value = data
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return value if value is not None else default


def text(value, default=""):
    return str(value if value is not None else default)


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def metric_value(item):
    value = nested_get(item, ["value"], [])
    if isinstance(value, list) and len(value) > 1:
        return round(number(value[1]), 1)
    return 0.0


def increment(counter, key):
    counter[key] = int(counter.get(key, 0)) + 1


def build_alert_summaries(alerts):
    by_severity = {}
    name_counts = {}
    namespace_counts = {}

    for item in as_list(alerts):
        severity = text(nested_get(item, ["metric", "severity"], "unknown"), "unknown")
        alert_name = text(nested_get(item, ["metric", "alertname"], "unknown"), "unknown")
        alert_namespace = text(nested_get(item, ["metric", "namespace"], "cluster"), "cluster")
        increment(by_severity, severity)
        increment(name_counts, alert_name)
        increment(namespace_counts, alert_namespace)

    return by_severity, name_counts, namespace_counts


def build_node_threshold_summaries(items, status, low_threshold=None, high_threshold=None):
    low = []
    high = []
    if status != "observed":
        return low, high

    for item in as_list(items):
        value = metric_value(item)
        entry = {
            "instance": text(nested_get(item, ["metric", "instance"], "unknown"), "unknown"),
            "value": value,
        }
        if low_threshold is not None and value < low_threshold:
            low.append(entry)
        if high_threshold is not None and value > high_threshold:
            high.append(entry)

    return low, high


def build_pod_density_summaries(items, status, warn_threshold, critical_threshold):
    high = []
    critical = []
    if status != "observed":
        return high, critical

    for item in as_list(items):
        value = metric_value(item)
        entry = {
            "node": text(nested_get(item, ["metric", "node"], "unknown"), "unknown"),
            "value": value,
        }
        if value > critical_threshold:
            critical.append(entry)
        elif value > warn_threshold:
            high.append(entry)

    return high, critical


def build(data):
    signal_map = as_dict(data.get("runtime_signal_resolution_map"))
    alert_severity, alert_names, alert_namespaces = build_alert_summaries(data.get("firing_alerts"))
    low_cpu, high_cpu = build_node_threshold_summaries(
        data.get("node_cpu_utilization_results"),
        nested_get(signal_map, ["node_cpu_utilization", "status"], "not-collected"),
        low_threshold=20.0,
        high_threshold=85.0,
    )
    low_memory, high_memory = build_node_threshold_summaries(
        data.get("node_memory_utilization_results"),
        nested_get(signal_map, ["node_memory_utilization", "status"], "not-collected"),
        low_threshold=30.0,
        high_threshold=85.0,
    )
    _, high_disk = build_node_threshold_summaries(
        data.get("node_disk_utilization_results"),
        nested_get(signal_map, ["node_disk_utilization", "status"], "not-collected"),
        high_threshold=85.0,
    )
    high_density, critical_density = build_pod_density_summaries(
        data.get("kubelet_pod_density_results"),
        nested_get(signal_map, ["kubelet_pod_density", "status"], "not-collected"),
        number(data.get("pod_density_warn_pct"), 0.0),
        number(data.get("pod_density_critical_pct"), 0.0),
    )

    return {
        "firing_alerts_by_severity": alert_severity,
        "firing_alert_name_counts": alert_names,
        "firing_alert_namespace_counts": alert_namespaces,
        "low_cpu_nodes": low_cpu,
        "high_cpu_nodes": high_cpu,
        "low_memory_nodes": low_memory,
        "high_memory_nodes": high_memory,
        "high_disk_nodes": high_disk,
        "high_pod_density_nodes": high_density,
        "critical_pod_density_nodes": critical_density,
    }


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_observability_metric_summaries.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
