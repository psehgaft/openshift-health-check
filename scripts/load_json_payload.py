#!/usr/bin/env python3
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file")
    group.add_argument("--stdin", action="store_true")
    args = parser.parse_args()

    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as handle:
                raw = handle.read()
        else:
            raw = sys.stdin.read()

        if not raw.strip():
            print(json.dumps({"ok": False, "data": {}, "error": "JSON payload was empty"}))
            return

        print(json.dumps({"ok": True, "data": json.loads(raw), "error": ""}))
    except Exception as exc:
        print(json.dumps({"ok": False, "data": {}, "error": str(exc)}))


if __name__ == "__main__":
    main()
