#!/usr/bin/env python3
import json
import re
import sys


def parse_cpu(value):
    if value in (None, ""):
        return 0.0
    text = str(value).strip()
    if text.endswith("m"):
        try:
            return float(text[:-1]) / 1000.0
        except Exception:
            return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def parse_mem(value):
    if value in (None, ""):
        return 0.0
    text = str(value).strip()
    units = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "Pi": 1024**5,
        "Ei": 1024**6,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
        "P": 1000**5,
        "E": 1000**6,
    }
    for suffix, multiplier in units.items():
        if text.endswith(suffix):
            try:
                return float(text[: -len(suffix)]) * multiplier
            except Exception:
                return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    node_alloc = {}
    for node in data.get("nodes") or []:
        meta = node.get("metadata", {}) or {}
        status = node.get("status", {}) or {}
        alloc = status.get("allocatable", {}) or {}
        name = meta.get("name") or ""
        if not name:
            continue
        node_alloc[name] = {
            "cpu_m": parse_cpu(alloc.get("cpu")) * 1000.0,
            "memory_b": parse_mem(alloc.get("memory")),
            "disk_b": parse_mem(alloc.get("ephemeral-storage")),
            "pods": int(alloc.get("pods") or 0),
        }

    node_cpu_req = {}
    node_mem_req = {}
    node_disk_req = {}
    node_pod_counts = {}
    pod_cpu_rows = []
    pod_mem_rows = []
    for pod in data.get("pods") or []:
        meta = pod.get("metadata", {}) or {}
        spec = pod.get("spec", {}) or {}
        ns = meta.get("namespace") or ""
        name = meta.get("name") or ""
        node = spec.get("nodeName") or ""
        if node:
            node_pod_counts[node] = node_pod_counts.get(node, 0) + 1

        cpu_m = 0.0
        mem_b = 0.0
        disk_b = 0.0
        for container in spec.get("containers") or []:
            req = (container.get("resources", {}) or {}).get("requests", {}) or {}
            cpu_m += parse_cpu(req.get("cpu")) * 1000.0
            mem_b += parse_mem(req.get("memory"))
            disk_b += parse_mem(req.get("ephemeral-storage"))

        if node:
            node_cpu_req[node] = node_cpu_req.get(node, 0.0) + cpu_m
            node_mem_req[node] = node_mem_req.get(node, 0.0) + mem_b
            node_disk_req[node] = node_disk_req.get(node, 0.0) + disk_b

        if ns and name and not exclude_re.match(ns):
            pod_cpu_rows.append({"metric": {"namespace": ns, "pod": name}, "value": [0, str(cpu_m / 1000.0)]})
            pod_mem_rows.append({"metric": {"namespace": ns, "pod": name}, "value": [0, str(mem_b)]})

    node_cpu_rows = []
    node_mem_rows = []
    node_disk_rows = []
    node_density_rows = []
    for node_name, alloc in node_alloc.items():
        cpu_pct = round((node_cpu_req.get(node_name, 0.0) / alloc["cpu_m"]) * 100.0, 1) if alloc["cpu_m"] > 0 else 0.0
        mem_pct = round((node_mem_req.get(node_name, 0.0) / alloc["memory_b"]) * 100.0, 1) if alloc["memory_b"] > 0 else 0.0
        disk_pct = round((node_disk_req.get(node_name, 0.0) / alloc["disk_b"]) * 100.0, 1) if alloc["disk_b"] > 0 else 0.0
        density_pct = round((node_pod_counts.get(node_name, 0) / alloc["pods"]) * 100.0, 1) if alloc["pods"] > 0 else 0.0
        node_cpu_rows.append({"metric": {"node": node_name}, "value": [0, str(cpu_pct)]})
        node_mem_rows.append({"metric": {"node": node_name}, "value": [0, str(mem_pct)]})
        node_disk_rows.append({"metric": {"node": node_name}, "value": [0, str(disk_pct)]})
        node_density_rows.append({"metric": {"node": node_name}, "value": [0, str(density_pct)]})

    pod_cpu_rows.sort(key=lambda item: float(item["value"][1]), reverse=True)
    pod_mem_rows.sort(key=lambda item: float(item["value"][1]), reverse=True)

    sample_alert_rules = ((data.get("omc_summary") or {}).get("sample_alert_rules") or [])[:20]
    firing_alerts = [
        {"metric": {"severity": "warning", "alertname": line, "namespace": "cluster"}, "value": [0, "1"]}
        for line in sample_alert_rules
    ]

    print(
        json.dumps(
            {
                "node_cpu_utilization": node_cpu_rows,
                "node_memory_utilization": node_mem_rows,
                "node_disk_utilization": node_disk_rows,
                "kubelet_pod_density": node_density_rows,
                "top_pod_cpu_usage": pod_cpu_rows[:50],
                "top_pod_memory_usage": pod_mem_rows[:50],
                "pod_cpu_usage_all": pod_cpu_rows,
                "pod_memory_usage_all": pod_mem_rows,
                "firing_alerts": firing_alerts,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
