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
        pods = json.load(handle)

    result = {}
    for pod in pods:
        namespace = pod.get("metadata", {}).get("namespace", "")
        name = pod.get("metadata", {}).get("name", "")
        containers = (pod.get("spec", {}).get("containers", []) or []) + (pod.get("spec", {}).get("initContainers", []) or [])
        total = 0.0
        for container in containers:
            total += parse_cpu_to_millicores(((container.get("resources", {}) or {}).get("requests", {}) or {}).get("cpu"))
        result[f"{namespace}/{name}"] = round(total, 3)

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
