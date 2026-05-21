#!/usr/bin/env python3
"""Load artifact hashes from a directory of JSON artifacts."""

import json
import sys
from pathlib import Path


def normalize_key(path: Path, artifact: object) -> str:
    if isinstance(artifact, dict):
        if artifact.get("kind") == "shared-analysis-graph":
            return "analysis_graph"
        if artifact.get("kind") == "shared-collection":
            return "collection"
        if artifact.get("key"):
            return str(artifact["key"])
    return path.stem.replace("-", "_")


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: load_json_artifact_hash_dir.py <dir>"}))
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
        key = normalize_key(path, artifact)
        payload[key] = artifact.get("artifact_hash", "") if isinstance(artifact, dict) else ""

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
