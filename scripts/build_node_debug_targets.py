#!/usr/bin/env python3
"""Build symptom-derived node debug target facts."""

import json
import sys


INVALID_NODE_NAMES = {"", "unknown", "unscheduled"}


def as_list(value):
    return value if isinstance(value, list) else []


def node_name(value):
    return str(value or "").strip()


def item_attr(item, key):
    return item.get(key) if isinstance(item, dict) else None


def valid_node(value):
    name = node_name(value)
    return name if name not in INVALID_NODE_NAMES else ""


def add_candidate(candidates, value, reason):
    name = valid_node(value)
    if name:
        candidates.append({"node": name, "reason": reason})


def build(data):
    candidates = []
    workload_candidates = []
    for item in as_list(data.get("not_ready_nodes")):
        add_candidate(candidates, item, "not-ready")
    for item in as_list(data.get("pressure_nodes")):
        add_candidate(candidates, item_attr(item, "name"), "node-pressure")
    for item in as_list(data.get("high_pod_density_nodes")):
        add_candidate(candidates, item_attr(item, "node"), "high-pod-density")
    for item in as_list(data.get("critical_pod_density_nodes")):
        add_candidate(candidates, item_attr(item, "node"), "critical-pod-density")
    for item in as_list(data.get("top_high_restart_pods")):
        add_candidate(workload_candidates, item_attr(item, "node"), "restart-hotspot")

    try:
        restart_threshold = int(data.get("pod_restart_warning_threshold", 5) or 5)
    except (TypeError, ValueError):
        restart_threshold = 5
    for item in as_list(data.get("pod_restart_hotspots")):
        try:
            restarts = int(item_attr(item, "restarts") or 0)
        except (TypeError, ValueError):
            restarts = 0
        if restarts >= restart_threshold:
            add_candidate(workload_candidates, item_attr(item, "node"), "restart-hotspot")

    nodes = []
    reason_map = {}
    for candidate in candidates:
        node = candidate["node"]
        reason = candidate["reason"]
        if node not in reason_map:
            nodes.append(node)
            reason_map[node] = []
        if reason not in reason_map[node]:
            reason_map[node].append(reason)

    return {
        "node_debug_target_candidates": candidates,
        "node_debug_target_nodes": nodes,
        "node_debug_target_reason_map": reason_map,
        "workload_debug_target_candidates": workload_candidates,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_node_debug_targets.py <input-json-path>"}))
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
