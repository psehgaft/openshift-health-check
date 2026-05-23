#!/usr/bin/env python3
"""Build common storage facts and storage posture summary in one helper call."""

import json
import sys

from build_storage_posture_summary import build as build_storage_posture_summary
from build_storage_tls_facts import build as build_storage_tls_facts


EMPTY_STORAGE_TLS = {
    "storageclass_summary": [],
    "pv_phase_counts": {},
    "pv_issues": [],
    "pvc_phase_counts": {},
    "pvc_issues": [],
    "tls_secret_expiry_targets": [],
    "certificate_expiry_findings": [],
}

EMPTY_STORAGE_POSTURE = {
    "external_storageclass_count": 0,
    "local_storageclass_count": 0,
    "default_external_storageclass_count": 0,
    "external_storageclass_names": [],
    "local_storageclass_names": [],
    "external_pv_count": 0,
    "local_pv_count": 0,
    "hostpath_workload_count": 0,
    "ephemeral_workload_count": 0,
    "has_external_storage_provider": False,
    "local_or_ephemeral_only_risk": False,
    "findings": [],
}


def build(data):
    storage_tls = build_storage_tls_facts(data) or dict(EMPTY_STORAGE_TLS)
    storage_posture = build_storage_posture_summary(
        {
            "storageclasses": storage_tls.get("storageclass_summary", []),
            "persistentvolumes": data.get("persistentvolumes") or [],
            "security_findings": data.get("security_findings") or [],
            "workload_practice_findings": data.get("workload_practice_findings") or [],
        }
    ) or dict(EMPTY_STORAGE_POSTURE)
    return {
        "storage_tls_input_facts": storage_tls,
        "storageclass_summary": storage_tls.get("storageclass_summary", []),
        "pv_phase_counts": storage_tls.get("pv_phase_counts", {}),
        "pv_issues": storage_tls.get("pv_issues", []),
        "pvc_phase_counts": storage_tls.get("pvc_phase_counts", {}),
        "pvc_issues": storage_tls.get("pvc_issues", []),
        "tls_secret_expiry_targets": storage_tls.get("tls_secret_expiry_targets", []),
        "certificate_expiry_findings": storage_tls.get("certificate_expiry_findings", []),
        "storage_posture_summary": storage_posture,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_common_storage_tls_bundle.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
