#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed


def resolve_repo_tmp_root():
    explicit = os.environ.get("OHC_REPO_TMPDIR") or os.environ.get("TMPDIR")
    if explicit:
        os.makedirs(explicit, exist_ok=True)
        return explicit
    fallback = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".runtime", "tmp")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def run_command(spec, timeout_seconds):
    try:
        proc = subprocess.run(
            spec["argv"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "name": spec["name"],
            "rc": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "stdout_lines": proc.stdout.splitlines(),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": spec["name"],
            "rc": 124,
            "stdout": exc.stdout or "",
            "stderr": f"timed out after {timeout_seconds} seconds",
            "stdout_lines": (exc.stdout or "").splitlines(),
            "timed_out": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": spec["name"],
            "rc": 1,
            "stdout": "",
            "stderr": str(exc),
            "stdout_lines": [],
            "timed_out": False,
        }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: run_parallel_collection.py <input.json>"}))
        return 1

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    commands = data.get("commands") or []
    timeout_seconds = int(data.get("timeout_seconds") or 0)
    requested_workers = int(data.get("max_workers") or 1)
    max_workers = min(max(1, requested_workers), max(1, len(commands)))

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(run_command, spec, timeout_seconds): spec["name"] for spec in commands}
        for future in as_completed(futures):
            result = future.result()
            results[result["name"]] = result

    output_dir = tempfile.mkdtemp(prefix="cluster-health-parallel-collect-", dir=resolve_repo_tmp_root())
    results_path = os.path.join(output_dir, "collected-commands.json")
    status_path = os.path.join(output_dir, "collected-command-status.json")
    with open(results_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle)
    with open(status_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                name: {
                    "rc": result.get("rc", 1),
                    "stderr": result.get("stderr", ""),
                    "timed_out": result.get("timed_out", False),
                }
                for name, result in results.items()
            },
            handle,
        )

    print(
        json.dumps(
            {
                "results_path": results_path,
                "status_path": status_path,
                "command_count": len(commands),
                "max_workers": max_workers,
                "timeout_seconds": timeout_seconds,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
