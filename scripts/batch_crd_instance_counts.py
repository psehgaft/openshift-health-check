#!/usr/bin/env python3
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_count(kube_cli, timeout_seconds, item):
    plural = item.get("plural", "")
    group = item.get("group", "")
    resource = f"{plural}.{group}" if plural and group else ""
    argv = [kube_cli, "get", resource, "-A", "-o", "json"]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        count = 0
        if proc.returncode == 0 and (proc.stdout or "").strip():
            try:
                count = len((json.loads(proc.stdout) or {}).get("items", []))
            except Exception:
                proc = subprocess.CompletedProcess(argv, 1, proc.stdout, "failed to parse json")
        return {
            "name": item.get("name", ""),
            "group": group,
            "plural": plural,
            "rc": proc.returncode,
            "count": count,
            "stderr": (proc.stderr or "").strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "name": item.get("name", ""),
            "group": group,
            "plural": plural,
            "rc": 124,
            "count": 0,
            "stderr": f"timed out after {timeout_seconds} seconds",
        }
    except Exception as exc:
        return {
            "name": item.get("name", ""),
            "group": group,
            "plural": plural,
            "rc": 1,
            "count": 0,
            "stderr": str(exc),
        }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: batch_crd_instance_counts.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    kube_cli = data.get("kube_cli", "oc")
    timeout_seconds = int(data.get("timeout_seconds", 60))
    max_workers = max(1, int(data.get("parallelism", 8)))
    items = data.get("crds", [])

    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(items)))) as pool:
        futures = [pool.submit(run_count, kube_cli, timeout_seconds, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())

    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
