#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_inspect.py <inspect-path>"}))
        return 1
    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": "inspect path not found", "path": str(root)}))
        return 2

    files = [p for p in root.rglob("*") if p.is_file()]
    resource_markers = {
        "nodes": 0,
        "pods": 0,
        "namespaces": 0,
        "events": 0,
        "operators": 0,
        "machineconfigpools": 0,
        "routes": 0,
        "persistentvolumes": 0,
        "persistentvolumeclaims": 0,
    }
    namespace_names = set()
    for path in files:
        rel = str(path.relative_to(root)).lower()
        if "node" in rel:
            resource_markers["nodes"] += 1
        if "pod" in rel:
            resource_markers["pods"] += 1
        if "namespace" in rel:
            resource_markers["namespaces"] += 1
        if "event" in rel:
            resource_markers["events"] += 1
        if "operator" in rel:
            resource_markers["operators"] += 1
        if "machineconfigpool" in rel or "mcp" in rel:
            resource_markers["machineconfigpools"] += 1
        if "route" in rel:
            resource_markers["routes"] += 1
        if "persistentvolumeclaim" in rel or "pvc" in rel:
            resource_markers["persistentvolumeclaims"] += 1
        if "persistentvolume" in rel or "/pv" in rel:
            resource_markers["persistentvolumes"] += 1
        parts = rel.split("/")
        if "namespaces" in parts:
            idx = parts.index("namespaces")
            if idx + 1 < len(parts):
                namespace_names.add(parts[idx + 1])

    payload = {
        "summary": {
            "path": str(root),
            "file_count": len(files),
            "yaml_file_count": len([p for p in files if p.suffix.lower() in {".yaml", ".yml"}]),
            "json_file_count": len([p for p in files if p.suffix.lower() == ".json"]),
            "text_file_count": len([p for p in files if p.suffix.lower() in {".txt", ".log"}]),
            "top_level_entries": len(list(root.iterdir())),
            "resource_markers": resource_markers,
            "namespace_count": len(namespace_names),
        },
        "samples": {
            "files": [str(p.relative_to(root)) for p in sorted(files)[:25]],
            "namespaces": sorted(namespace_names)[:25],
        },
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
