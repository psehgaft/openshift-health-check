#!/usr/bin/env python3
"""Validate vendor-managed telemetry detection behavior."""

import json
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"vendor-managed telemetry validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: validate_vendor_managed_telemetry.py <input-json>")

    repo_root = Path(__file__).resolve().parent.parent
    input_path = Path(sys.argv[1]).resolve()
    script_path = repo_root / "scripts" / "build_vendor_managed_telemetry.py"

    raw = subprocess.check_output(
        [sys.executable, str(script_path), str(input_path)],
        text=True,
    )
    payload = json.loads(raw)

    metrics_vendors = payload.get("metrics_vendor_names") or []
    log_vendors = payload.get("log_vendor_names") or []

    if metrics_vendors != ["dynatrace", "datadog", "appdynamics", "splunk"]:
        fail(f"unexpected metrics vendors: {metrics_vendors!r}")
    if log_vendors != ["dynatrace", "datadog", "splunk", "loki"]:
        fail(f"unexpected log vendors: {log_vendors!r}")
    if "appdynamics" in log_vendors:
        fail("AppDynamics must not be treated as a log-forwarding vendor by default")
    if not payload.get("vendor_managed_metrics_forwarding_present", False):
        fail("vendor_managed_metrics_forwarding_present must be true for the fixture")
    if not payload.get("vendor_managed_log_forwarding_present", False):
        fail("vendor_managed_log_forwarding_present must be true for the fixture")

    print(f"{input_path}: vendor-managed telemetry validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
