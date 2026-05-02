#!/usr/bin/env python3
import base64
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_expiry(timeout_seconds, item):
    cert_b64 = item.get("tls_crt", "")
    if not cert_b64:
        return {
            "namespace": item.get("namespace", ""),
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "rc": 1,
            "not_after": "",
            "stderr": "missing tls.crt",
        }
    try:
        cert_pem = base64.b64decode(cert_b64)
        proc = subprocess.run(
            ["openssl", "x509", "-noout", "-enddate"],
            input=cert_pem,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        not_after = ""
        if proc.returncode == 0:
            line = proc.stdout.decode("utf-8", errors="replace").strip()
            not_after = line.removeprefix("notAfter=")
        return {
            "namespace": item.get("namespace", ""),
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "rc": proc.returncode,
            "not_after": not_after,
            "stderr": proc.stderr.decode("utf-8", errors="replace").strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "namespace": item.get("namespace", ""),
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "rc": 124,
            "not_after": "",
            "stderr": f"timed out after {timeout_seconds} seconds",
        }
    except Exception as exc:
        return {
            "namespace": item.get("namespace", ""),
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "rc": 1,
            "not_after": "",
            "stderr": str(exc),
        }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: batch_tls_secret_expiry.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    timeout_seconds = int(data.get("timeout_seconds", 20))
    max_workers = max(1, int(data.get("parallelism", 2)))
    items = data.get("secrets", [])

    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(items)))) as pool:
        futures = [pool.submit(run_expiry, timeout_seconds, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())

    print(json.dumps({"results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
