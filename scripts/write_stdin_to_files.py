#!/usr/bin/env python3
"""Write stdin to multiple files."""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Destination file paths")
    parser.add_argument("--mode", default="0644", help="Octal file mode to apply")
    parser.add_argument(
        "--json-pretty",
        action="store_true",
        help="Parse stdin as JSON and write stable pretty-printed JSON",
    )
    parser.add_argument(
        "--normalize-unknown-labels",
        action="store_true",
        help="Normalize legacy unknown labels in text content before writing",
    )
    args = parser.parse_args()

    content = sys.stdin.read()
    if args.json_pretty:
        content = json.dumps(json.loads(content or "{}"), indent=4, ensure_ascii=False)
        content += "\n"
    if args.normalize_unknown_labels:
        content = re.sub(
            r"\b(?:UNKONWN|UNKNWON|UNKNONW|UNKNOWN|Unknown|unknown)\b",
            "not-assessed",
            content,
        )
    file_mode = int(args.mode, 8)
    written = []

    for raw_path in args.paths:
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        os.chmod(path, file_mode)
        written.append(str(path))

    sys.stdout.write("\n".join(written))
    if written:
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
