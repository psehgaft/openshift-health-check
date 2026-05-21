#!/usr/bin/env python3
"""Run an existing JSON-file helper by feeding it stdin through one temp file."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def resolve_repo_tmp_root() -> str:
    explicit = os.environ.get("OHC_REPO_TMPDIR") or os.environ.get("TMPDIR")
    if explicit:
        Path(explicit).mkdir(parents=True, exist_ok=True)
        return explicit
    fallback = str((Path(__file__).resolve().parent.parent / ".runtime" / "tmp"))
    Path(fallback).mkdir(parents=True, exist_ok=True)
    return fallback


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_json_helper_from_stdin.py <helper.py> [helper-args...]", file=sys.stderr)
        return 2

    helper_path = Path(sys.argv[1])
    helper_args = sys.argv[2:]
    payload = sys.stdin.read()

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
        dir=resolve_repo_tmp_root(),
    ) as handle:
        handle.write(payload)
        temp_path = handle.name

    try:
        proc = subprocess.run(
            [sys.executable, str(helper_path), temp_path, *helper_args],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        return proc.returncode
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
