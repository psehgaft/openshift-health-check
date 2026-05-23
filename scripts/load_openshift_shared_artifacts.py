#!/usr/bin/env python3
"""Load OpenShift shared artifacts using their canonical in-memory keys."""

import json
import sys
from pathlib import Path


def artifact_key(path, artifact):
    kind = artifact.get("kind")
    if kind == "shared-collection":
        return "collection"
    if kind == "shared-analysis-graph":
        return "analysis_graph"
    return artifact.get("key") or path.stem


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: load_openshift_shared_artifacts.py <dir>"}))
        return 1

    root = Path(sys.argv[1])
    if not root.exists():
        print("{}")
        return 0
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {root}"}))
        return 1

    payload = {}
    for path in sorted(root.glob("*.json")):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        payload[artifact_key(path, artifact)] = artifact

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
