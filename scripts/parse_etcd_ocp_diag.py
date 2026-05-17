#!/usr/bin/env python3
"""Parse etcd must-gather logs into a JSON summary using the vendored etcd-ocp-diag helpers."""

import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional


def _strip_suffix(value, suffix):
    if suffix and value.endswith(suffix):
        return value[:-len(suffix)]
    return value


def load_vendor_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("etcd_ocp_diag_vendor", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load vendor module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_duration_ms(value: str) -> Optional[float]:
    if not value:
        return None
    if value.endswith("ms"):
        try:
            return float(_strip_suffix(value, "ms"))
        except ValueError:
            return None
    if value.endswith("s") and "m" not in value:
        try:
            return float(_strip_suffix(value, "s")) * 1000
        except ValueError:
            return None
    if "m" in value and value.endswith("s"):
        try:
            mins, secs = value.split("m", 1)
            return (float(mins) * 60000) + (float(_strip_suffix(secs, "s")) * 1000)
        except ValueError:
            return None
    return None


def summarize_metric(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"count": 0, "max_ms": 0, "median_ms": 0, "min_ms": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "max_ms": round(max(ordered), 3),
        "median_ms": round(median(ordered), 3),
        "min_ms": round(min(ordered), 3),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_etcd_ocp_diag.py <must-gather-path>"}))
        return 1

    must_gather_path = Path(sys.argv[1])
    if not must_gather_path.exists():
        print(json.dumps({"error": "must-gather path not found", "path": str(must_gather_path)}))
        return 1

    vendor_path = Path(__file__).with_name("etcd-ocp-diag.py")
    vendor = load_vendor_module(vendor_path)
    pod_dirs = [Path(p) for p in vendor.get_dirs(str(must_gather_path), "**/openshift-etcd/pods/etcd-*")]

    if not pod_dirs:
        print(
            json.dumps(
                {
                    "summary": {
                        "present": False,
                        "verdict": "not-collected",
                        "pod_count": 0,
                        "log_file_count": 0,
                        "rotated_log_count": 0,
                        "error_count_total": 0,
                        "slow_fsync_count": 0,
                        "apply_took_too_long_count": 0,
                        "request_timeout_count": 0,
                        "leader_election_count": 0,
                        "lost_leader_count": 0,
                        "heartbeat_failure_count": 0,
                        "buffer_full_count": 0,
                        "overloaded_count": 0,
                        "source": "vendored-etcd-ocp-diag",
                    },
                    "findings": [],
                    "pods": [],
                }
            )
        )
        return 0

    pattern_counts = Counter()
    pod_pattern_counts = defaultdict(Counter)
    apply_took_too_long_ms = []  # type: List[float]
    apply_took_too_long_expected_ms = []  # type: List[float]
    slow_fsync_ms = []  # type: List[float]
    slow_fsync_expected_ms = []  # type: List[float]
    pod_summaries = []
    total_log_files = 0
    total_rotated_logs = 0

    tracked_patterns = {
        "apply request took too long": "apply_took_too_long_count",
        "slow fdatasync": "slow_fsync_count",
        "etcdserver: request timed out": "request_timeout_count",
        "elected leader": "leader_election_count",
        "lost leader": "lost_leader_count",
        "failed to send out heartbeat": "heartbeat_failure_count",
        "sending buffer is full": "buffer_full_count",
        "leader is overloaded likely from slow disk": "overloaded_count",
        "server is likely overloaded": "overloaded_count",
    }

    for pod_dir in pod_dirs:
        pod_name = vendor.get_etcd_pod(pod_dir)
        pod_logs = []
        current_log = pod_dir / "etcd" / "etcd" / "logs" / "current.log"
        previous_log = pod_dir / "etcd" / "etcd" / "logs" / "previous.log"
        if current_log.exists():
            pod_logs.append(current_log)
        if previous_log.exists():
            pod_logs.append(previous_log)
        rotated_logs = [Path(p) for p in vendor.get_rotated_logs(pod_dir)]
        pod_logs.extend(rotated_logs)

        total_log_files += len([p for p in pod_logs if p.name in {"current.log", "previous.log"}])
        total_rotated_logs += len(rotated_logs)

        for log_path in pod_logs:
            try:
                content = log_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for pattern_text, key in tracked_patterns.items():
                count = content.count(pattern_text)
                if count > 0:
                    pattern_counts[key] += count
                    pod_pattern_counts[pod_name][key] += count

            for line in content.splitlines():
                if "apply request took too long" in line:
                    for result in vendor.extract_json_objects(line):
                        duration = parse_duration_ms(str(result.get("took", "")))
                        if duration is not None:
                            apply_took_too_long_ms.append(duration)
                        expected_duration = parse_duration_ms(str(result.get("expected-duration", "")))
                        if expected_duration is not None:
                            apply_took_too_long_expected_ms.append(expected_duration)
                if "slow fdatasync" in line:
                    for result in vendor.extract_json_objects(line):
                        duration = parse_duration_ms(str(result.get("took", "")))
                        if duration is not None:
                            slow_fsync_ms.append(duration)
                        expected_duration = parse_duration_ms(str(result.get("expected-duration", "")))
                        if expected_duration is not None:
                            slow_fsync_expected_ms.append(expected_duration)

        pod_summaries.append(
            {
                "name": pod_name,
                "counts": dict(sorted(pod_pattern_counts[pod_name].items())),
                "log_files": len(pod_logs),
                "rotated_log_files": len(rotated_logs),
            }
        )

    findings = []
    if pattern_counts["lost_leader_count"] > 0:
        findings.append(
            {
                "severity": "critical",
                "area": "etcd",
                "detail": f"etcd logs recorded lost leader events: {pattern_counts['lost_leader_count']}",
            }
        )
    if pattern_counts["request_timeout_count"] > 0:
        findings.append(
            {
                "severity": "critical",
                "area": "etcd",
                "detail": f"etcd request timeout messages observed: {pattern_counts['request_timeout_count']}",
            }
        )
    if pattern_counts["apply_took_too_long_count"] > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "etcd",
                "detail": f"etcd apply request latency warnings observed: {pattern_counts['apply_took_too_long_count']}",
            }
        )
    if pattern_counts["slow_fsync_count"] > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "etcd",
                "detail": f"etcd slow fdatasync warnings observed: {pattern_counts['slow_fsync_count']}",
            }
        )
    if pattern_counts["leader_election_count"] > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "etcd",
                "detail": f"etcd leader election messages observed: {pattern_counts['leader_election_count']}",
            }
        )
    if pattern_counts["heartbeat_failure_count"] > 0 or pattern_counts["buffer_full_count"] > 0 or pattern_counts["overloaded_count"] > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "etcd",
                "detail": (
                    "etcd log pressure signals observed: "
                    f"heartbeat failures={pattern_counts['heartbeat_failure_count']}, "
                    f"buffer full={pattern_counts['buffer_full_count']}, "
                    f"overloaded={pattern_counts['overloaded_count']}"
                ),
            }
        )

    verdict = "supported"
    if any(item["severity"] == "critical" for item in findings):
        verdict = "unsupported-risk"
    elif findings:
        verdict = "review-required"

    payload = {
        "summary": {
            "present": True,
            "verdict": verdict,
            "pod_count": len(pod_dirs),
            "log_file_count": total_log_files,
            "rotated_log_count": total_rotated_logs,
            "error_count_total": sum(pattern_counts.values()),
            "slow_fsync_count": pattern_counts["slow_fsync_count"],
            "apply_took_too_long_count": pattern_counts["apply_took_too_long_count"],
            "request_timeout_count": pattern_counts["request_timeout_count"],
            "leader_election_count": pattern_counts["leader_election_count"],
            "lost_leader_count": pattern_counts["lost_leader_count"],
            "heartbeat_failure_count": pattern_counts["heartbeat_failure_count"],
            "buffer_full_count": pattern_counts["buffer_full_count"],
            "overloaded_count": pattern_counts["overloaded_count"],
            "apply_took_too_long_stats": summarize_metric(apply_took_too_long_ms),
            "apply_took_too_long_expected_stats": summarize_metric(apply_took_too_long_expected_ms),
            "slow_fsync_stats": summarize_metric(slow_fsync_ms),
            "slow_fsync_expected_stats": summarize_metric(slow_fsync_expected_ms),
            "source": "vendored-etcd-ocp-diag",
        },
        "findings": findings,
        "pods": pod_summaries,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
