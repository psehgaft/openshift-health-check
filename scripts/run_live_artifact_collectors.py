#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def run_collector(spec):
    started = time.time()
    argv = spec.get("argv") or []
    timeout_seconds = int(spec.get("timeout_seconds") or 0) or None
    output_kind = spec.get("output_kind") or "none"
    output_path = spec.get("output_path") or ""

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        wrote_output = False
        if proc.returncode == 0 and output_kind == "file" and output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(stdout, encoding="utf-8")
            wrote_output = True
        return {
            "name": spec.get("name", "unknown"),
            "argv": argv,
            "rc": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "duration_seconds": round(time.time() - started, 2),
            "output_kind": output_kind,
            "output_path": output_path,
            "wrote_output": wrote_output,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": spec.get("name", "unknown"),
            "argv": argv,
            "rc": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"timed out after {timeout_seconds} seconds",
            "timed_out": True,
            "duration_seconds": round(time.time() - started, 2),
            "output_kind": output_kind,
            "output_path": output_path,
            "wrote_output": False,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "name": spec.get("name", "unknown"),
            "argv": argv,
            "rc": 1,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
            "duration_seconds": round(time.time() - started, 2),
            "output_kind": output_kind,
            "output_path": output_path,
            "wrote_output": False,
        }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: run_live_artifact_collectors.py <collector-spec-json>"}))
        return 1

    spec_path = Path(sys.argv[1]).expanduser().resolve()
    if not spec_path.exists() or not spec_path.is_file():
        print(json.dumps({"error": "collector spec path not found", "path": str(spec_path)}))
        return 2

    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    collectors = [item for item in payload.get("collectors", []) if item.get("enabled")]
    max_workers = min(
        max(1, int(payload.get("parallelism", 1))),
        max(1, len(collectors) if collectors else 1),
    )

    results = {}
    if collectors:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(run_collector, spec): spec.get("name", "unknown") for spec in collectors}
            for future in as_completed(futures):
                result = future.result()
                results[result["name"]] = result

    print(
        json.dumps(
            {
                "parallelism": max_workers,
                "collector_count": len(collectors),
                "results": results,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
