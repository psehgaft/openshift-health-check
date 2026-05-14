#!/usr/bin/env python3
import json
import sys


def parse_cpu_to_millicores(value):
    if value in (None, ""):
        return 0.0
    text = str(value).strip()
    if text.endswith("m"):
        try:
            return float(text[:-1])
        except Exception:
            return 0.0
    try:
        return float(text) * 1000.0
    except Exception:
        return 0.0


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_pod_cpu_request_map.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        pods = data.get("pods") or []
        nodes = data.get("nodes") or []
    else:
        pods = data or []
        nodes = []

    def raw_aliases(raw):
        text = str(raw or "").strip()
        if not text:
            return []
        aliases = [text]
        short = text.split(".", 1)[0]
        if short and short not in aliases:
            aliases.append(short)
        return aliases

    node_alias_to_canonical = {}
    for node in nodes:
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

    result = {}
    node_cpu_request_millicores = {}
    for pod in pods:
        namespace = pod.get("metadata", {}).get("namespace", "")
        name = pod.get("metadata", {}).get("name", "")
        raw_node_name = str(((pod.get("spec", {}) or {}).get("nodeName")) or "").strip()
        canonical_node_name = (
            node_alias_to_canonical.get(raw_node_name)
            or node_alias_to_canonical.get(raw_node_name.split(".", 1)[0] if raw_node_name else "")
            or raw_node_name
        )
        containers = (pod.get("spec", {}).get("containers", []) or []) + (pod.get("spec", {}).get("initContainers", []) or [])
        total = 0.0
        for container in containers:
            total += parse_cpu_to_millicores(((container.get("resources", {}) or {}).get("requests", {}) or {}).get("cpu"))
        result[f"{namespace}/{name}"] = round(total, 3)
        if canonical_node_name:
            node_cpu_request_millicores[canonical_node_name] = round(
                float(node_cpu_request_millicores.get(canonical_node_name, 0.0)) + total,
                3,
            )

    print(json.dumps({
        "pod_cpu_request_map": result,
        "node_cpu_request_millicores": node_cpu_request_millicores,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
