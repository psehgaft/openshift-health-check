#!/usr/bin/env python3
"""Build OpenShift node capacity summary facts."""

import json
import re
import sys


ROLE_PREFIX = "node-role.kubernetes.io/"


def get_path(data, *path, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def quantity_to_millicores(value):
    text = str(value if value is not None else "0").strip()
    if text.endswith("m"):
        try:
            return int(float(text[:-1] or 0))
        except ValueError:
            return 0
    try:
        return int(float(text or 0) * 1000)
    except ValueError:
        return 0


def int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def node_roles(node):
    labels = get_path(node, "metadata", "labels", default={}) or {}
    roles = []
    for key in labels:
        key = str(key or "")
        if key.startswith(ROLE_PREFIX):
            roles.append(key[len(ROLE_PREFIX) :])
    return roles


def primary_role(roles):
    for preferred in ("master", "control-plane", "infra", "worker"):
        if preferred in roles:
            return preferred
    return sorted(roles)[0] if roles else "worker"


def unique_nonempty(values):
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def node_lookup_candidates(node):
    metadata = node.get("metadata") or {}
    status = node.get("status") or {}
    labels = metadata.get("labels") or {}
    addresses = [
        address.get("address")
        for address in status.get("addresses") or []
        if isinstance(address, dict)
    ]
    return unique_nonempty(
        [metadata.get("name"), labels.get("kubernetes.io/hostname"), *addresses]
    )


def expand_lookup_candidates(candidates):
    expanded = list(candidates)
    expanded.extend(re.sub(r"\..*$", "", candidate) for candidate in candidates)
    return unique_nonempty(expanded)


def first_matching_key(candidates, mapping, default):
    if not isinstance(mapping, dict):
        return default
    for candidate in candidates:
        if candidate in mapping:
            return candidate
    return default


def pod_items_from_inputs(data):
    graph_pods = get_path(data, "analysis_graph", "pods", "items", default=[]) or []
    if graph_pods:
        return graph_pods
    pods = data.get("pods") or {}
    if isinstance(pods, dict):
        return pods.get("items") or []
    if isinstance(pods, list):
        return pods
    return []


def direct_scheduled_pod_count(pods, candidates):
    candidate_set = set(candidates)
    count = 0
    for pod in pods:
        if not isinstance(pod, dict):
            continue
        node_name = get_path(pod, "spec", "nodeName")
        if node_name in candidate_set:
            count += 1
    return count


def build_node_capacity_summary(data):
    nodes = data.get("openshift_node_items") or []
    pods = pod_items_from_inputs(data)
    pod_counts = data.get("node_pod_counts") or {}
    pod_counts_fallback = data.get("node_pod_counts_fallback") or {}
    cpu_requests = data.get("node_cpu_request_millicores") or {}
    default_max_pods = data.get("cluster_max_pods_per_node_default", 250)

    summary = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(get_path(node, "metadata", "name", default="") or "")
        if not name:
            continue

        candidates = node_lookup_candidates(node)
        expanded_candidates = expand_lookup_candidates(candidates)
        pod_count_key = first_matching_key(candidates, pod_counts, name)
        fallback_pod_count_key = first_matching_key(candidates, pod_counts_fallback, name)
        cpu_request_key = first_matching_key(candidates, cpu_requests, name)

        pods_allocatable = int_value(
            get_path(node, "status", "allocatable", "pods", default=default_max_pods),
            int_value(default_max_pods, 0),
        )
        cpu_allocatable = quantity_to_millicores(
            get_path(node, "status", "allocatable", "cpu", default="0")
        )
        scheduled_pods = max(
            int_value(pod_counts.get(pod_count_key, 0)),
            int_value(pod_counts_fallback.get(fallback_pod_count_key, 0)),
            direct_scheduled_pod_count(pods, expanded_candidates),
        )
        requested_cpu = int_value(cpu_requests.get(cpu_request_key, 0))
        pod_capacity_basis = pods_allocatable if pods_allocatable > 0 else 1
        cpu_capacity_basis = cpu_allocatable if cpu_allocatable > 0 else 1

        summary.append(
            {
                "name": name,
                "role": primary_role(node_roles(node)),
                "pods_allocatable": pods_allocatable,
                "scheduled_pods": scheduled_pods,
                "pod_density_pct": round((scheduled_pods / pod_capacity_basis) * 100, 1),
                "cpu_allocatable_millicores": cpu_allocatable,
                "requested_cpu_millicores": requested_cpu,
                "requested_cpu_pct": round((requested_cpu / cpu_capacity_basis) * 100, 1),
            }
        )

    return summary


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    summary = build_node_capacity_summary(data)
    print(
        json.dumps(
            {
                "node_capacity_summary": summary,
                "node_capacity_summary_by_density_desc": sorted(
                    summary,
                    key=lambda item: item.get("pod_density_pct", 0),
                    reverse=True,
                ),
                "node_capacity_summary_by_density_asc": sorted(
                    summary,
                    key=lambda item: item.get("pod_density_pct", 0),
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
