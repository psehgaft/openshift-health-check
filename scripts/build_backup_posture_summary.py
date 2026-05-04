#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone, timedelta


def parse_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def bsl_available(item):
    for condition in ((item.get("status") or {}).get("conditions") or []):
        if condition.get("type") == "Available":
            return str(condition.get("status") or "Unknown")
    return "Unknown"


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    dpas = data.get("dataprotectionapplications", []) or []
    bsl_items = data.get("backupstoragelocations", []) or []
    schedule_items = data.get("schedules", []) or []
    backup_items = data.get("backups", []) or []
    restore_items = data.get("restores", []) or []

    backup_storage_location_summary = []
    for item in bsl_items:
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        backup_storage_location_summary.append({
            "namespace": meta.get("namespace", ""),
            "name": meta.get("name", ""),
            "provider": spec.get("provider", "unknown"),
            "default": bool((meta.get("labels") or {}).get("velero.io/default-backup-storage-location") == "true"),
            "available": bsl_available(item),
            "bucket": ((spec.get("objectStorage") or {}).get("bucket") or spec.get("bucket") or ""),
            "prefix": ((spec.get("objectStorage") or {}).get("prefix") or ""),
        })

    backup_schedule_summary = []
    paused_schedules = []
    for item in schedule_items:
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        paused = bool(spec.get("paused", False))
        if paused:
            paused_schedules.append(f"{meta.get('namespace', '')}/{meta.get('name', '')}")
        backup_schedule_summary.append({
            "namespace": meta.get("namespace", ""),
            "name": meta.get("name", ""),
            "paused": paused,
            "schedule": spec.get("schedule", ""),
            "last_backup": status.get("lastBackup", ""),
            "storage_location": ((spec.get("template") or {}).get("storageLocation") or ""),
        })

    successful_backups = []
    clean_successful_backups = []
    backup_summary = []
    for item in backup_items:
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        phase = str(status.get("phase") or "Unknown")
        completion = status.get("completionTimestamp") or meta.get("creationTimestamp") or ""
        backup_summary.append({
            "namespace": meta.get("namespace", ""),
            "name": meta.get("name", ""),
            "phase": phase,
            "storage_location": spec.get("storageLocation", ""),
            "completion_timestamp": completion,
            "warnings": int(status.get("warnings", 0) or 0),
            "errors": int(status.get("errors", 0) or 0),
        })
        if phase == "Completed":
            successful_backups.append(parse_time(completion))
            if int(status.get("warnings", 0) or 0) == 0 and int(status.get("errors", 0) or 0) == 0:
                clean_successful_backups.append(parse_time(completion))

    completed_restores = []
    clean_completed_restores = []
    restore_summary = []
    for item in restore_items:
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        phase = str(status.get("phase") or "Unknown")
        completion = status.get("completionTimestamp") or meta.get("creationTimestamp") or ""
        restore_summary.append({
            "namespace": meta.get("namespace", ""),
            "name": meta.get("name", ""),
            "phase": phase,
            "backup_name": spec.get("backupName", ""),
            "completion_timestamp": completion,
            "warnings": int(status.get("warnings", 0) or 0),
            "errors": int(status.get("errors", 0) or 0),
        })
        if phase == "Completed":
            completed_restores.append(parse_time(completion))
            if int(status.get("warnings", 0) or 0) == 0 and int(status.get("errors", 0) or 0) == 0:
                clean_completed_restores.append(parse_time(completion))

    findings = []
    if dpas or bsl_items or schedule_items or backup_items or restore_items:
        if not bsl_items:
            findings.append({"issue": "backup-storage-location-missing", "detail": "no BackupStorageLocation resource was found"})
        elif not any(item["available"] == "True" for item in backup_storage_location_summary):
            findings.append({"issue": "backup-storage-location-unavailable", "detail": "no BackupStorageLocation reported Available=True"})

        if not schedule_items:
            findings.append({"issue": "backup-schedule-missing", "detail": "no Velero Schedule resource was found"})
        elif paused_schedules:
            findings.append({"issue": "backup-schedule-paused", "detail": ", ".join(paused_schedules[:10])})

        successful_count = len([item for item in successful_backups if item is not None])
        clean_successful_count = len([item for item in clean_successful_backups if item is not None])
        if successful_count == 0:
            findings.append({"issue": "successful-backup-missing", "detail": "no Velero Backup resource reported phase=Completed"})
        elif clean_successful_count == 0:
            findings.append({"issue": "successful-backup-has-warnings-or-errors", "detail": "completed backups were found, but all recent completed backups reported warnings or errors"})
        else:
            latest_success = max(item for item in clean_successful_backups if item is not None)
            if latest_success < datetime.now(timezone.utc) - timedelta(days=7):
                findings.append({"issue": "successful-backup-stale", "detail": latest_success.isoformat()})

        completed_restore_count = len([item for item in completed_restores if item is not None])
        clean_completed_restore_count = len([item for item in clean_completed_restores if item is not None])
        if completed_restore_count == 0:
            findings.append({"issue": "restore-evidence-not-demonstrated", "detail": "no Velero Restore resource reported phase=Completed"})
        elif clean_completed_restore_count == 0:
            findings.append({"issue": "restore-evidence-has-warnings-or-errors", "detail": "completed restores were found, but all reported warnings or errors"})
    else:
        findings.append({
            "issue": "backup-tooling-not-detected",
            "detail": "no DataProtectionApplication, BackupStorageLocation, Schedule, Backup, or Restore resources were found"
        })

    print(json.dumps({
        "backup_storage_location_summary": sorted(backup_storage_location_summary, key=lambda item: (item["namespace"], item["name"])),
        "backup_schedule_summary": sorted(backup_schedule_summary, key=lambda item: (item["namespace"], item["name"])),
        "backup_summary": sorted(backup_summary, key=lambda item: (item["completion_timestamp"], item["namespace"], item["name"]), reverse=True)[:15],
        "restore_summary": sorted(restore_summary, key=lambda item: (item["completion_timestamp"], item["namespace"], item["name"]), reverse=True)[:15],
        "backup_posture_findings": findings,
        "successful_backup_count": len([item for item in successful_backups if item is not None]),
        "clean_successful_backup_count": len([item for item in clean_successful_backups if item is not None]),
        "completed_restore_count": len([item for item in completed_restores if item is not None]),
        "clean_completed_restore_count": len([item for item in clean_completed_restores if item is not None]),
    }))


if __name__ == "__main__":
    main()

