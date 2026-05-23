#!/usr/bin/env python3
"""Run multiple JSON-file helpers from one stdin payload.

The input format is:
{
  "fail_on_error": true,
  "helpers": [
    {"name": "example", "script": "scripts/helper.py", "input": {...}, "args": []}
  ]
}

Each helper still receives a JSON file path, preserving the existing helper
contract while avoiding repeated Ansible command tasks.
"""

import contextlib
import io
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path


def repo_root():
    return Path(__file__).resolve().parent.parent


def resolve_repo_tmp_root() -> str:
    explicit = os.environ.get("OHC_REPO_TMPDIR") or os.environ.get("TMPDIR")
    path = Path(explicit) if explicit else repo_root() / ".runtime" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def parse_payload():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid batch payload: {exc}"}))
        raise SystemExit(2)
    return payload if isinstance(payload, dict) else {}


def resolve_script_path(script):
    path = Path(script)
    if not path.is_absolute():
        path = repo_root() / path
    return path.resolve()


def run_helper(helper):
    name = str(helper.get("name") or "")
    script = resolve_script_path(str(helper.get("script") or ""))
    args = [str(item) for item in (helper.get("args") or [])]
    helper_input = helper.get("input", {})

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
        dir=resolve_repo_tmp_root(),
    ) as handle:
        json.dump(helper_input, handle)
        temp_path = handle.name

    old_argv = sys.argv[:]
    stdout = io.StringIO()
    stderr = io.StringIO()
    rc = 0
    try:
        sys.argv = [str(script), temp_path, *args]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                runpy.run_path(str(script), run_name="__main__")
            except SystemExit as exc:
                rc = int(exc.code or 0) if isinstance(exc.code, int) else 1
    except Exception as exc:  # noqa: BLE001 - propagate helper failure as structured output.
        rc = 1
        stderr.write(f"{type(exc).__name__}: {exc}\n")
    finally:
        sys.argv = old_argv
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

    stdout_text = stdout.getvalue()
    parsed_output = None
    parse_error = ""
    if stdout_text.strip():
        try:
            parsed_output = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)

    return {
        "name": name,
        "rc": rc,
        "stdout": stdout_text,
        "stderr": stderr.getvalue(),
        "output": parsed_output,
        "parse_error": parse_error,
    }


def main() -> int:
    payload = parse_payload()
    helpers = payload.get("helpers") or []
    if not isinstance(helpers, list):
        print(json.dumps({"error": "helpers must be a list"}))
        return 2

    results = {}
    failed = []
    for helper in helpers:
        if not isinstance(helper, dict):
            continue
        result = run_helper(helper)
        name = result.get("name") or f"helper_{len(results) + 1}"
        results[name] = result
        if int(result.get("rc") or 0) != 0:
            failed.append(name)

    print(json.dumps({"results": results, "failed": failed}, separators=(",", ":")))
    return 1 if failed and bool(payload.get("fail_on_error", True)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
