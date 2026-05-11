#!/usr/bin/env python3
"""Parse offline control-plane evidence from must-gather artifacts."""

import gzip
import json
import re
import sys
from pathlib import Path
from typing import List, Optional


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def find_first(root: Path, pattern: str) -> Optional[Path]:
    matches = sorted(root.rglob(pattern))
    return matches[0] if matches else None


def read_text_maybe_gzip(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8", errors="replace")


def parse_int(value) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_control_plane_evidence.py <must-gather-path>"}))
        return 1

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists():
        print(json.dumps({"error": "must-gather path not found", "path": str(root)}))
        return 2

    endpoint_health_path = find_first(root, "endpoint_health.json")
    endpoint_status_path = find_first(root, "endpoint_status.json")
    object_count_path = find_first(root, "object_count.json")
    alarm_list_path = find_first(root, "alarm_list.json")
    termination_logs = sorted(root.rglob("static-pods/kube-apiserver/*termination*.log*"))

    endpoint_health = read_json(endpoint_health_path) if endpoint_health_path else None
    endpoint_status = read_json(endpoint_status_path) if endpoint_status_path else None
    object_count = read_json(object_count_path) if object_count_path else None
    alarm_list = read_json(alarm_list_path) if alarm_list_path else None

    healthy_endpoint_count = 0
    endpoint_count = 0
    if isinstance(endpoint_health, list):
        endpoint_count = len(endpoint_health)
        healthy_endpoint_count = sum(1 for item in endpoint_health if isinstance(item, dict) and item.get("health") is True)

    members_reporting_leader = 0
    leader_ids = set()
    if isinstance(endpoint_status, list):
        for item in endpoint_status:
            if not isinstance(item, dict):
                continue
            status = item.get("Status") or {}
            leader = status.get("leader")
            if leader not in (None, "", 0):
                members_reporting_leader += 1
                leader_ids.add(str(leader))
    leader_count = len(leader_ids)

    apiserver_storage_objects_total = None
    if isinstance(object_count, dict):
        totals = [parse_int(value) for value in object_count.values()]
        apiserver_storage_objects_total = sum(value for value in totals if value is not None)

    alarm_count = 0
    if isinstance(alarm_list, dict):
        alarms = alarm_list.get("alarms")
        if isinstance(alarms, list):
            alarm_count = len(alarms)

    readyz_failed_checks = 0
    readyz_shutdown_failed_checks = 0
    readyz_sample_lines = []  # type: List[str]
    for path in termination_logs:
        try:
            text = read_text_maybe_gzip(path)
        except Exception:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if "readyz" not in line.lower():
                continue
            if len(readyz_sample_lines) < 10:
                readyz_sample_lines.append(line)
            if re.search(r"shutdown check failed:\s*readyz", line, re.IGNORECASE):
                readyz_shutdown_failed_checks += 1
            elif "failed" in line.lower():
                readyz_failed_checks += 1

    present = any(
        [
            endpoint_health_path,
            endpoint_status_path,
            object_count_path,
            alarm_list_path,
            termination_logs,
        ]
    )

    print(
        json.dumps(
            {
                "summary": {
                    "present": bool(present),
                    "source": "must-gather",
                    "endpoint_health_present": bool(endpoint_health_path),
                    "endpoint_status_present": bool(endpoint_status_path),
                    "object_count_present": bool(object_count_path),
                    "alarm_list_present": bool(alarm_list_path),
                    "apiserver_termination_logs_present": len(termination_logs) > 0,
                    "etcd_endpoint_count": endpoint_count,
                    "etcd_healthy_endpoint_count": healthy_endpoint_count,
                    "etcd_members_reporting_leader": members_reporting_leader,
                    "etcd_leader_count": leader_count,
                    "etcd_alarm_count": alarm_count,
                    "apiserver_storage_objects_total": apiserver_storage_objects_total,
                    "apiserver_readyz_failed_checks": readyz_failed_checks,
                    "apiserver_readyz_shutdown_failed_checks": readyz_shutdown_failed_checks,
                    "termination_log_count": len(termination_logs),
                },
                "artifacts": {
                    "endpoint_health_path": str(endpoint_health_path) if endpoint_health_path else "",
                    "endpoint_status_path": str(endpoint_status_path) if endpoint_status_path else "",
                    "object_count_path": str(object_count_path) if object_count_path else "",
                    "alarm_list_path": str(alarm_list_path) if alarm_list_path else "",
                    "termination_logs": [str(path) for path in termination_logs[:10]],
                },
                "samples": {
                    "readyz_lines": readyz_sample_lines,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
