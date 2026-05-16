#!/usr/bin/env python3
import json
import re
import sys


def raw_aliases(raw):
    text = str(raw or "").strip()
    if not text:
        return []
    aliases = [text]
    short = text.split(".", 1)[0]
    if short and short not in aliases:
        aliases.append(short)
    return aliases


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    pod_restart_hotspots = []
    pod_phase_counts = {}
    node_pod_counts = {}
    namespace_pod_counts = {}
    pod_object_counts = {
        "total": 0,
        "running": 0,
        "user_total": 0,
        "user_running": 0,
    }

    node_alias_to_canonical = {}
    for node in data.get("nodes") or []:
        metadata = node.get("metadata") or {}
        status = node.get("status") or {}
        labels = metadata.get("labels") or {}
        canonical_name = str(metadata.get("name") or "").strip()
        if not canonical_name:
            continue
        alias_values = []
        alias_values.extend(raw_aliases(canonical_name))
        alias_values.extend(raw_aliases(labels.get("kubernetes.io/hostname")))
        for address in status.get("addresses") or []:
            alias_values.extend(raw_aliases((address or {}).get("address")))
        for alias in alias_values:
            node_alias_to_canonical.setdefault(alias, canonical_name)

    for item in data.get("pods") or []:
        status = item.get("status") or {}
        spec = item.get("spec") or {}
        metadata = item.get("metadata") or {}
        phase = str(status.get("phase") or "Unknown")
        raw_node_name = str(spec.get("nodeName") or "unscheduled")
        node_name = (
            node_alias_to_canonical.get(raw_node_name)
            or node_alias_to_canonical.get(raw_node_name.split(".", 1)[0])
            or raw_node_name
        )
        namespace_name = str(metadata.get("namespace") or "")
        pod_name = str(metadata.get("name") or "unknown")
        is_user_namespace = not exclude_re.search(namespace_name or "")

        pod_phase_counts[phase] = pod_phase_counts.get(phase, 0) + 1
        for node_alias in raw_aliases(node_name):
            node_pod_counts[node_alias] = node_pod_counts.get(node_alias, 0) + 1
        namespace_pod_counts[namespace_name] = namespace_pod_counts.get(namespace_name, 0) + 1

        pod_object_counts["total"] += 1
        if phase == "Running":
            pod_object_counts["running"] += 1
        if is_user_namespace:
            pod_object_counts["user_total"] += 1
            if phase == "Running":
                pod_object_counts["user_running"] += 1

        restart_count = sum(
            int(container.get("restartCount") or 0)
            for container in (status.get("containerStatuses") or [])
        )
        restart_count += sum(
            int(container.get("restartCount") or 0)
            for container in (status.get("initContainerStatuses") or [])
        )
        if is_user_namespace and restart_count > 0:
            pod_restart_hotspots.append(
                {
                    "namespace": namespace_name,
                    "name": pod_name,
                    "phase": phase,
                    "restarts": restart_count,
                    "node": node_name,
                }
            )

    print(
        json.dumps(
            {
                "pod_restart_hotspots": pod_restart_hotspots,
                "pod_phase_counts": pod_phase_counts,
                "node_pod_counts": node_pod_counts,
                "namespace_pod_counts": namespace_pod_counts,
                "pod_object_counts": pod_object_counts,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
