#!/usr/bin/env python3
"""Parse selected omc must-gather diagnostics into a small JSON summary."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def resolve_omc_binary(explicit_path: str | None) -> str | None:
    if explicit_path:
        candidate = Path(explicit_path)
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
        return None

    repo_candidate = Path(__file__).resolve().parent / "omc"
    if repo_candidate.exists() and os.access(repo_candidate, os.X_OK):
        return str(repo_candidate)

    return shutil.which("omc")


def run_omc_command(omc_bin: str, must_gather_path: Path, args: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="omc-context.") as tmpdir:
        env = os.environ.copy()
        env["HOME"] = tmpdir
        env["XDG_CONFIG_HOME"] = tmpdir
        env["XDG_CACHE_HOME"] = tmpdir
        env["XDG_DATA_HOME"] = tmpdir

        use_cmd = [omc_bin, "use", str(must_gather_path)]
        use_result = subprocess.run(
            use_cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if use_result.returncode != 0:
            return {
                "ok": False,
                "command": use_cmd,
                "rc": use_result.returncode,
                "stdout": use_result.stdout,
                "stderr": use_result.stderr,
            }

        cmd = [omc_bin] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "command": cmd,
            "rc": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }


def run_omc_command_candidates(omc_bin: str, must_gather_path: Path, command_sets: list[list[str]]) -> dict:
    attempts = []
    for args in command_sets:
        result = run_omc_command(omc_bin, must_gather_path, args)
        attempts.append({
            "command": result.get("command", []),
            "rc": result.get("rc", 1),
            "stderr": result.get("stderr", "").strip(),
        })
        if result.get("ok"):
            result["attempts"] = attempts
            return result

    failed = attempts[-1] if attempts else {}
    return {
        "ok": False,
        "command": failed.get("command", []),
        "rc": failed.get("rc", 1),
        "stdout": "",
        "stderr": failed.get("stderr", ""),
        "attempts": attempts,
    }


def parse_pipe_table(output: str) -> list[dict[str, str]]:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    table_lines = [line for line in lines if line.lstrip().startswith("|") and line.rstrip().endswith("|")]
    if len(table_lines) < 2:
        return []

    headers = [cell.strip().lower().replace(" ", "_").replace("/", "_") for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[1:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def parse_prom_rules(output: str) -> dict:
    firing = 0
    pending = 0
    sample_rules: list[str] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("group "):
            continue
        state_match = re.search(r"\b(firing|pending)\b", line, re.IGNORECASE)
        if not state_match:
            continue
        state = state_match.group(1).lower()
        if state == "firing":
            firing += 1
        elif state == "pending":
            pending += 1
        if len(sample_rules) < 10:
            sample_rules.append(line)

    return {
        "firing_count": firing,
        "pending_count": pending,
        "alert_count": firing + pending,
        "sample_rules": sample_rules,
    }


def build_payload(must_gather_path: Path, omc_bin: str | None) -> dict:
    if omc_bin is None:
        return {
            "summary": {
                "present": False,
                "verdict": "not-collected",
                "tool_available": False,
                "must_gather_path": str(must_gather_path),
                "detail": "omc binary was not found on PATH or in scripts/omc.",
            },
            "findings": [],
            "commands": {},
        }

    etcd_result = run_omc_command(omc_bin, must_gather_path, ["etcd", "status"])
    prom_result = run_omc_command_candidates(
        omc_bin,
        must_gather_path,
        [
            ["prometheus", "rules", "-s", "firing,pending", "-o", "wide"],
            ["prom", "rules", "-s", "firing,pending", "-o", "wide"],
        ],
    )

    etcd_rows = parse_pipe_table(etcd_result.get("stdout", "")) if etcd_result.get("ok") else []
    endpoint_error_count = sum(1 for row in etcd_rows if row.get("errors", "").strip())
    leader_count = sum(1 for row in etcd_rows if row.get("is_leader", "").lower() == "true")
    learner_count = sum(1 for row in etcd_rows if row.get("is_learner", "").lower() == "true")

    prom_summary = parse_prom_rules(prom_result.get("stdout", "")) if prom_result.get("ok") else {
        "firing_count": 0,
        "pending_count": 0,
        "alert_count": 0,
        "sample_rules": [],
    }

    present = bool(etcd_rows or prom_summary["alert_count"] > 0 or etcd_result.get("ok") or prom_result.get("ok"))
    findings = []
    if endpoint_error_count > 0:
        findings.append({
            "severity": "warning",
            "area": "omc-etcd-status",
            "detail": f"omc etcd status reported errors on {endpoint_error_count} endpoint(s).",
        })
    if etcd_rows and leader_count != 1:
        findings.append({
            "severity": "warning",
            "area": "omc-etcd-status",
            "detail": f"omc etcd status reported {leader_count} leader endpoint(s); expected 1.",
        })
    if prom_summary["firing_count"] > 0:
        findings.append({
            "severity": "warning",
            "area": "omc-prom-rules",
            "detail": f"omc prom rules reported {prom_summary['firing_count']} firing alert rule(s).",
        })
    if prom_summary["pending_count"] > 0:
        findings.append({
            "severity": "info",
            "area": "omc-prom-rules",
            "detail": f"omc prom rules reported {prom_summary['pending_count']} pending alert rule(s).",
        })

    if not present:
        verdict = "not-collected"
    elif any(item["severity"] == "warning" for item in findings):
        verdict = "review-required"
    else:
        verdict = "supported"

    return {
        "summary": {
            "present": present,
            "verdict": verdict,
            "tool_available": True,
            "must_gather_path": str(must_gather_path),
            "omc_binary": omc_bin,
            "etcd_status_present": bool(etcd_rows),
            "endpoint_count": len(etcd_rows),
            "leader_count": leader_count,
            "learner_count": learner_count,
            "endpoint_error_count": endpoint_error_count,
            "prom_rules_present": prom_result.get("ok", False),
            "alert_count": prom_summary["alert_count"],
            "firing_alert_count": prom_summary["firing_count"],
            "pending_alert_count": prom_summary["pending_count"],
            "sample_alert_rules": prom_summary["sample_rules"],
        },
        "findings": findings,
        "commands": {
            "etcd_status": {
                "ok": etcd_result.get("ok", False),
                "rc": etcd_result.get("rc", 1),
                "stderr": etcd_result.get("stderr", "").strip(),
            },
            "prom_rules": {
                "ok": prom_result.get("ok", False),
                "rc": prom_result.get("rc", 1),
                "stderr": prom_result.get("stderr", "").strip(),
                "attempts": prom_result.get("attempts", []),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("must_gather_path")
    parser.add_argument("--omc-bin", dest="omc_bin", default=os.environ.get("OMC_BIN", ""))
    args = parser.parse_args()

    must_gather_path = Path(args.must_gather_path)
    if not must_gather_path.exists():
        print(json.dumps({"error": "must-gather path not found", "path": str(must_gather_path)}))
        return 1

    omc_bin = resolve_omc_binary(args.omc_bin.strip() or None)
    print(json.dumps(build_payload(must_gather_path, omc_bin)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
