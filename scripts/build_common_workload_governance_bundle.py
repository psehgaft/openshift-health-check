#!/usr/bin/env python3
"""Build workload and node governance facts in one helper invocation."""

import json
import sys

from build_node_label_governance_findings import build as build_node_label_governance
from build_workload_governance_facts import build as build_workload_governance


def graph_items(graph, key):
    value = graph.get(key) if isinstance(graph, dict) else {}
    return value.get("items", []) if isinstance(value, dict) else []


def first_non_empty(*values):
    for value in values:
        if value:
            return value
    return []


def build(data):
    graph = data.get("analysis_graph") or {}
    collected_graph = data.get("collected_resource_graph") or {}
    collected_nodes = collected_graph.get("nodes") if isinstance(collected_graph, dict) else {}
    node_source = first_non_empty(
        graph_items(graph, "nodes"),
        data.get("nodes", {}).get("items", []) if isinstance(data.get("nodes"), dict) else [],
        collected_nodes.get("items", []) if isinstance(collected_nodes, dict) else [],
    )

    workload_governance = build_workload_governance(
        {
            "pods": graph_items(graph, "pods"),
            "namespaces": graph_items(graph, "namespaces"),
            "deployments": graph_items(graph, "deployments"),
            "statefulsets": graph_items(graph, "statefulsets"),
            "daemonsets": graph_items(graph, "daemonsets"),
            "operator_managed_namespace_names": data.get("operator_managed_namespace_names") or [],
            "exclude_regex": data.get("user_namespaces_exclude_regex") or "^$",
        }
    )
    node_governance = build_node_label_governance({"nodes": node_source})

    return {
        "workload_governance_facts": workload_governance,
        "orphan_pods": workload_governance.get("orphan_pods", []),
        "workload_label_governance_findings": workload_governance.get("workload_label_governance_findings", []),
        "workload_resource_findings": workload_governance.get("workload_resource_findings", []),
        "node_label_governance_source_nodes": node_source,
        "node_label_governance_findings": node_governance.get("node_label_governance_findings", []),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_common_workload_governance_bundle.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
