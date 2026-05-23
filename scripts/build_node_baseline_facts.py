#!/usr/bin/env python3
"""Build OpenShift node baseline facts from analysis graph nodes."""

import json
import sys


PRESSURE_TYPES = {
    "MemoryPressure",
    "DiskPressure",
    "PIDPressure",
    "OutOfDisk",
    "NetworkUnavailable",
}


def condition_status(conditions, condition_type, default="Unknown"):
    for condition in conditions or []:
        if str((condition or {}).get("type") or "") == condition_type:
            return str((condition or {}).get("status") or default)
    return default


def node_roles(node):
    labels = ((node.get("metadata") or {}).get("labels") or {})
    roles = []
    prefix = "node-role.kubernetes.io/"
    for key in labels:
        key = str(key or "")
        if key.startswith(prefix):
            roles.append(key[len(prefix) :])
    return roles


def primary_role(roles):
    for preferred in ("master", "control-plane", "infra", "worker"):
        if preferred in roles:
            return preferred
    return sorted(roles)[0] if roles else "worker"


def valid_node(item):
    metadata = item.get("metadata") or {}
    return (
        item.get("kind") == "Node"
        and bool(str(metadata.get("name") or "").strip())
        and str(metadata.get("name") or "") != "cluster"
    )


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    graph = data.get("analysis_graph") or {}
    raw_nodes = ((graph.get("nodes") or {}).get("items") or [])
    openshift_node_items = [item for item in raw_nodes if isinstance(item, dict) and valid_node(item)]

    not_ready_nodes = []
    pressure_nodes = []
    primary_node_role_counts = {}
    kubelet_version_counts = {}
    control_plane_count = 0
    worker_count = 0
    infra_count = 0

    for node in openshift_node_items:
        metadata = node.get("metadata") or {}
        status = node.get("status") or {}
        name = str(metadata.get("name") or "")
        conditions = status.get("conditions") or []

        if condition_status(conditions, "Ready").lower() not in {"true", "ready"}:
            not_ready_nodes.append(name)

        active_pressures = [
            str(condition.get("type") or "")
            for condition in conditions
            if str(condition.get("status") or "") == "True"
            and str(condition.get("type") or "") in PRESSURE_TYPES
        ]
        if active_pressures:
            pressure_nodes.append({"name": name, "pressures": active_pressures})

        role = primary_role(node_roles(node))
        primary_node_role_counts[role] = primary_node_role_counts.get(role, 0) + 1
        if role in {"master", "control-plane"}:
            control_plane_count += 1
        elif role == "worker":
            worker_count += 1
        elif role == "infra":
            infra_count += 1

        kubelet_version = str(((status.get("nodeInfo") or {}).get("kubeletVersion")) or "unknown")
        kubelet_version_counts[kubelet_version] = kubelet_version_counts.get(kubelet_version, 0) + 1

    print(
        json.dumps(
            {
                "openshift_node_items": openshift_node_items,
                "not_ready_nodes": not_ready_nodes,
                "pressure_nodes": pressure_nodes,
                "primary_node_role_counts": primary_node_role_counts,
                "kubelet_version_counts": kubelet_version_counts,
                "openshift_control_plane_node_count": control_plane_count,
                "openshift_worker_node_count": worker_count,
                "openshift_infra_node_count": infra_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
