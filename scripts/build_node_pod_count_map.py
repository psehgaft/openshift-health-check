#!/usr/bin/env python3
import glob
import json
import os
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


def build_alias_map(nodes):
    node_alias_to_canonical = {}
    for node in nodes or []:
        metadata = node.get("metadata", {}) or {}
        status = node.get("status", {}) or {}
        labels = metadata.get("labels", {}) or {}
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
    return node_alias_to_canonical


def load_pod_count(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return len(items)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_node_pod_count_map.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    must_gather_path = str((data or {}).get("must_gather_path") or "").strip()
    node_alias_to_canonical = build_alias_map((data or {}).get("nodes") or [])
    node_pod_counts = {}

    if must_gather_path:
        pattern = os.path.join(must_gather_path, "**", "nodes", "*", "pods_info.json")
        for path in glob.glob(pattern, recursive=True):
            node_dir = os.path.basename(os.path.dirname(path))
            canonical_name = (
                node_alias_to_canonical.get(node_dir)
                or node_alias_to_canonical.get(node_dir.split(".", 1)[0])
                or node_dir
            )
            try:
                pod_count = load_pod_count(path)
            except Exception:
                continue
            node_pod_counts[canonical_name] = max(
                int(node_pod_counts.get(canonical_name, 0) or 0),
                int(pod_count or 0),
            )

    print(json.dumps({"node_pod_counts": node_pod_counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
