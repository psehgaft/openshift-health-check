#!/usr/bin/env python3
"""Load a directory of JSON artifacts into a single JSON object."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: load_json_artifact_dir.py <dir>"}))
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
        key = artifact.get("key") or path.stem
        payload[key] = artifact

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
