#!/usr/bin/env python3
"""Build the OpenShift storage and resilience domain payload."""

import json
import sys


MISSING = object()
RECOMMENDATION = (
    "Review backup tooling, successful backup evidence, restore evidence, and "
    "machine remediation posture before treating disaster recovery as credible."
)


def get(data, key, default=None):
    if isinstance(data, dict) and key in data:
        return data[key]
    return default


def nested_get(data, *keys, default=MISSING):
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def first_defined(*values, default=None):
    for value in values:
        if value is not MISSING:
            return value
    return default


def build_payload(data):
    mode = data.get("mode") or "live"
    artifact = data.get("backup_recovery_posture_artifact") or {}
    render_inputs = data.get("backup_recovery_posture_render_inputs") or {}
    summary = data.get("backup_recovery_summary") or {}

    collected = mode == "collected"
    pv_issues_key = "pv_issues" if collected else "top_pv_issues"
    pvc_issues_key = "pvc_issues" if collected else "top_pvc_issues"
    backup_findings_key = (
        "backup_posture_findings" if collected else "top_backup_posture_findings"
    )
    machine_findings_key = (
        "machine_healthcheck_findings"
        if collected
        else "top_machine_healthcheck_findings"
    )

    return {
        "summary": first_defined(nested_get(artifact, "summary"), default=summary),
        "recommendations": first_defined(
            nested_get(artifact, "recommendations"),
            default=get(summary, "recommendation", RECOMMENDATION),
        ),
        "storage": {
            "pv_issues": first_defined(
                nested_get(artifact, "storage", "pv_issues"),
                nested_get(render_inputs, "pv_issues"),
                default=data.get(pv_issues_key) or [],
            ),
            "pvc_issues": first_defined(
                nested_get(artifact, "storage", "pvc_issues"),
                nested_get(render_inputs, "pvc_issues"),
                default=data.get(pvc_issues_key) or [],
            ),
        },
        "backup": {
            "findings": first_defined(
                nested_get(artifact, "backup", "findings"),
                nested_get(render_inputs, "backup_posture_findings"),
                default=data.get(backup_findings_key) or [],
            ),
            "storage_locations": first_defined(
                nested_get(artifact, "backup", "storage_locations"),
                nested_get(render_inputs, "backup_storage_locations"),
                default=data.get("backup_storage_location_summary") or [],
            ),
            "schedules": first_defined(
                nested_get(artifact, "backup", "schedules"),
                nested_get(render_inputs, "backup_schedules"),
                default=data.get("backup_schedule_summary") or [],
            ),
            "recent_backups": first_defined(
                nested_get(artifact, "backup", "recent_backups"),
                nested_get(render_inputs, "recent_backups"),
                default=data.get("backup_summary") or [],
            ),
            "recent_restores": first_defined(
                nested_get(artifact, "backup", "recent_restores"),
                nested_get(render_inputs, "recent_restores"),
                default=data.get("restore_summary") or [],
            ),
        },
        "machine_remediation": {
            "summary": first_defined(
                nested_get(artifact, "machine_remediation", "summary"),
                nested_get(render_inputs, "machinehealthcheck_summary"),
                default=data.get("machinehealthcheck_summary") or [],
            ),
            "findings": first_defined(
                nested_get(artifact, "machine_remediation", "findings"),
                nested_get(render_inputs, "machine_healthcheck_findings"),
                default=data.get(machine_findings_key) or [],
            ),
        },
    }


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
