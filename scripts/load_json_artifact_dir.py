#!/usr/bin/env python3
"""Load a directory of JSON artifacts into a single JSON object."""

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="Directory containing JSON artifacts")
    parser.add_argument(
        "--output",
        default="",
        help="Write the artifact map to this JSON file instead of stdout.",
    )
    parser.add_argument(
        "--var-name",
        default="",
        help="Wrap the artifact map under this key when writing --output.",
    )
    parser.add_argument("--mode", default="0644", help="Octal mode for --output")
    args = parser.parse_args()

    root = Path(args.directory)
    if not root.exists():
        payload = {}
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({args.var_name: payload} if args.var_name else payload, sort_keys=True) + "\n", encoding="utf-8")
            os.chmod(output, int(args.mode, 8))
            print(json.dumps({"output": str(output), "count": 0}, sort_keys=True))
        else:
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

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output_payload = {args.var_name: payload} if args.var_name else payload
        output.write_text(json.dumps(output_payload, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(output, int(args.mode, 8))
        print(json.dumps({"output": str(output), "count": len(payload)}, sort_keys=True))
        return 0

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
