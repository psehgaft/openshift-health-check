#!/usr/bin/env python3
"""Load normalized control-plane backup artifact evidence."""

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_control_plane_backup_evidence.py <path>"}))
        return 1
    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists() or not path.is_file():
        print(json.dumps({"error": "path not found", "path": str(path)}))
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"error": f"invalid json: {exc}", "path": str(path)}))
        return 3
    if not isinstance(data, dict):
        print(json.dumps({"error": "expected a JSON object", "path": str(path)}))
        return 4
    print(json.dumps(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
