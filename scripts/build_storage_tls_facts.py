#!/usr/bin/env python3
import json
import sys


def parse_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def metadata_of(obj: dict) -> dict:
    return (obj or {}).get("metadata") or {}


def spec_of(obj: dict) -> dict:
    return (obj or {}).get("spec") or {}


def status_of(obj: dict) -> dict:
    return (obj or {}).get("status") or {}


def name_of(obj: dict) -> str:
    return str(metadata_of(obj).get("name") or "")


def namespace_of(obj: dict) -> str:
    return str(metadata_of(obj).get("namespace") or "")


def build_storageclass_summary(storageclasses: list[dict]) -> list[dict]:
    summary = []
    for storageclass in storageclasses or []:
        metadata = metadata_of(storageclass)
        annotations = metadata.get("annotations") or {}
        default_value = annotations.get(
            "storageclass.kubernetes.io/is-default-class",
            annotations.get("storageclass.beta.kubernetes.io/is-default-class", False),
        )
        summary.append(
            {
                "name": name_of(storageclass),
                "provisioner": str(storageclass.get("provisioner") or "unknown"),
                "is_default": str(default_value).lower() == "true",
                "volume_binding_mode": str(storageclass.get("volumeBindingMode") or "Immediate"),
                "reclaim_policy": str(storageclass.get("reclaimPolicy") or "Delete"),
            }
        )
    return summary


def claim_ref_of(pv: dict) -> str:
    claim_ref = spec_of(pv).get("claimRef")
    if not isinstance(claim_ref, dict):
        return ""
    namespace = str(claim_ref.get("namespace") or "")
    name = str(claim_ref.get("name") or "")
    return f"{namespace}/{name}"


def build_pv_summary(persistentvolumes: list[dict]) -> tuple[dict, list[dict]]:
    phase_counts = {}
    issues = []
    for pv in persistentvolumes or []:
        phase = str(status_of(pv).get("phase") or "Unknown")
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        if phase not in ["Bound", "Available"]:
            issues.append(
                {
                    "name": name_of(pv),
                    "phase": phase,
                    "storageClassName": str(spec_of(pv).get("storageClassName") or ""),
                    "claimRef": claim_ref_of(pv),
                }
            )
    return phase_counts, issues


def build_pvc_summary(persistentvolumeclaims: list[dict]) -> tuple[dict, list[dict]]:
    phase_counts = {}
    issues = []
    for pvc in persistentvolumeclaims or []:
        phase = str(status_of(pvc).get("phase") or "Unknown")
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        if phase != "Bound":
            issues.append(
                {
                    "namespace": namespace_of(pvc),
                    "name": name_of(pvc),
                    "phase": phase,
                    "storageClassName": str(spec_of(pvc).get("storageClassName") or ""),
                    "volumeName": str(spec_of(pvc).get("volumeName") or ""),
                }
            )
    return phase_counts, issues


def build_tls_secret_expiry_targets(secrets: list[dict]) -> list[dict]:
    targets = []
    for secret in secrets or []:
        data = secret.get("data")
        if secret.get("type") != "kubernetes.io/tls" or not isinstance(data, dict) or "tls.crt" not in data:
            continue
        targets.append(
            {
                "namespace": namespace_of(secret),
                "name": name_of(secret),
                "type": str(secret.get("type") or ""),
                "tls_crt": str(data.get("tls.crt") or ""),
            }
        )
    return targets


def build_certificate_expiry_findings(results: list[dict]) -> list[dict]:
    findings = []
    for item in results or []:
        try:
            rc = int(item.get("rc", 1) or 0)
        except (TypeError, ValueError):
            rc = 1
        not_after = str(item.get("not_after") or "")
        if rc == 0 and not_after:
            findings.append(
                {
                    "namespace": str(item.get("namespace") or ""),
                    "name": str(item.get("name") or ""),
                    "type": str(item.get("type") or ""),
                    "not_after": not_after,
                }
            )
    return findings


def build(data: dict) -> dict:
    pv_phase_counts, pv_issues = build_pv_summary(data.get("persistentvolumes") or [])
    pvc_phase_counts, pvc_issues = build_pvc_summary(data.get("persistentvolumeclaims") or [])
    return {
        "storageclass_summary": build_storageclass_summary(data.get("storageclasses") or []),
        "pv_phase_counts": pv_phase_counts,
        "pv_issues": pv_issues,
        "pvc_phase_counts": pvc_phase_counts,
        "pvc_issues": pvc_issues,
        "tls_secret_expiry_targets": build_tls_secret_expiry_targets(data.get("secrets") or []),
        "certificate_expiry_findings": build_certificate_expiry_findings(
            data.get("certificate_expiry_results") or []
        ),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_storage_tls_facts.py <input-json-path>"}))
        return 2

    data = parse_json(sys.argv[1])
    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
