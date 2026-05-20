#!/usr/bin/env python3
"""Load a single JSON file and emit it to stdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: load_json_file.py <file>"}))
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print("{}")
        return 0
    if not path.is_file():
        print(json.dumps({"error": f"not a file: {path}"}))
        return 1

    payload = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
