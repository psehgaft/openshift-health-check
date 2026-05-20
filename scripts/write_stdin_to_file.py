#!/usr/bin/env python3
"""Write stdin to a target file path with a fixed mode."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Destination file path")
    parser.add_argument("--mode", default="0600", help="Octal file mode to apply")
    args = parser.parse_args()

    target = Path(args.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    content = sys.stdin.read()
    target.write_text(content, encoding="utf-8")
    os.chmod(target, int(args.mode, 8))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
