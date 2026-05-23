#!/usr/bin/env python3
"""Write a JSON object of keyed artifacts as individual JSON files."""

import argparse
import json
import os
import sys
from pathlib import Path


def safe_key(value: str) -> str:
    key = str(value or "").strip()
    if not key:
        raise ValueError("artifact key is empty")
    if "/" in key or "\\" in key or key in {".", ".."}:
        raise ValueError(f"unsafe artifact key: {key}")
    return key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="Destination artifact directory")
    parser.add_argument("--prefix", default="", help="Manifest path prefix, for example postures/")
    parser.add_argument("--mode", default="0644", help="Octal file mode to apply")
    args = parser.parse_args()

    artifact_map = json.load(sys.stdin)
    if not isinstance(artifact_map, dict):
        print(json.dumps({"error": "stdin must be a JSON object of keyed artifacts"}))
        return 1

    root = Path(args.directory)
    root.mkdir(parents=True, exist_ok=True)
    file_mode = int(args.mode, 8)
    completed = []

    for raw_key, artifact in sorted(artifact_map.items()):
        key = safe_key(raw_key)
        if not isinstance(artifact, dict):
            print(json.dumps({"error": f"artifact for {key} must be an object"}))
            return 1
        path = root / f"{key}.json"
        path.write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(path, file_mode)
        completed.append(f"{args.prefix}{key}.json")

    print(json.dumps({"completed": completed, "count": len(completed)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
