#!/usr/bin/env python3
"""Build a compact timing artifact from playbook timing events."""

import json
import sys
from pathlib import Path


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_stage_events(events):
    starts = {}
    stages = []
    for event in events:
        stage = str(event.get("stage") or "").strip()
        kind = str(event.get("event") or "").strip().lower()
        epoch = as_float(event.get("epoch"))
        if not stage:
            continue
        if kind == "start":
            starts[stage] = event
        elif kind == "end":
            start = starts.get(stage)
            duration = None
            if start:
                duration = round(max(0.0, epoch - as_float(start.get("epoch"))), 2)
            stages.append(
                {
                    "stage": stage,
                    "status": "complete" if start else "end-without-start",
                    "started_at": start.get("iso8601") if start else "",
                    "completed_at": event.get("iso8601") or "",
                    "duration_seconds": duration,
                }
            )

    completed_names = {item["stage"] for item in stages if item.get("status") == "complete"}
    for stage, start in starts.items():
        if stage not in completed_names:
            stages.append(
                {
                    "stage": stage,
                    "status": "running-or-interrupted",
                    "started_at": start.get("iso8601") or "",
                    "completed_at": "",
                    "duration_seconds": None,
                }
            )
    return stages


def summarize_live_collectors(live_support_data):
    artifacts = live_support_data.get("artifacts") if isinstance(live_support_data, dict) else {}
    results = artifacts.get("results") if isinstance(artifacts, dict) else {}
    collectors = []
    if not isinstance(results, dict):
        return collectors
    for name, result in sorted(results.items()):
        if not isinstance(result, dict):
            continue
        collectors.append(
            {
                "name": name,
                "rc": result.get("rc"),
                "timed_out": bool(result.get("timed_out", False)),
                "duration_seconds": result.get("duration_seconds"),
                "output_kind": result.get("output_kind", "none"),
                "wrote_output": bool(result.get("wrote_output", False)),
            }
        )
    return collectors


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_report_timing_artifact.py <input-json>"}))
        return 2

    payload_path = Path(sys.argv[1]).expanduser().resolve()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    events = payload.get("events") or []
    if not isinstance(events, list):
        events = []

    stages = summarize_stage_events(events)
    total_duration = None
    if len(events) >= 2:
        total_duration = round(
            max(0.0, as_float(events[-1].get("epoch")) - as_float(events[0].get("epoch"))),
            2,
        )

    artifact = {
        "schema_version": payload.get("schema_version", "1"),
        "repo_contract_version": payload.get("repo_contract_version", "openshift-artifact-workspace-v1"),
        "run_id": payload.get("run_id", ""),
        "platform_family": payload.get("platform_family", "openshift"),
        "report_mode": payload.get("report_mode", "live"),
        "kind": "run-timing",
        "generated_at": payload.get("generated_at", ""),
        "status": payload.get("status", "in-progress"),
        "total_duration_seconds": total_duration,
        "stages": stages,
        "live_collectors": summarize_live_collectors(payload.get("live_support_data") or {}),
        "events": events,
    }
    print(json.dumps(artifact, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
