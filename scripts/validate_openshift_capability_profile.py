#!/usr/bin/env python3
"""Validate Kubernetes-family cluster health profile input files."""

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"capability profile validation failed: PyYAML is required: {exc}", file=sys.stderr)
    raise SystemExit(1)


REQUIRED_FIELDS = {
    "required",
    "criticality",
    "expected_state",
    "owner",
    "evidence_required",
    "notes",
    "docs",
}
OPTIONAL_FIELDS = {"standards"}

VALID_CRITICALITY = {"critical", "high", "medium", "low", "info"}
VALID_EXPECTED_STATE = {"present", "absent", "configured", "healthy", "not_applicable"}
VALID_OWNERS = {
    "platform",
    "security",
    "network",
    "app",
    "storage",
    "observability",
    "operations",
    "delivery",
}
VALID_EVIDENCE = {
    "must-gather",
    "inspect",
    "oc-get",
    "oc-debug-node",
    "kubectl-get",
    "insights",
    "prometheus",
    "metrics",
    "provider-api",
}
VALID_COMPLIANCE_STANDARDS = {"FIPS", "FedRAMP", "HIPAA", "PCI-DSS", "SOC", "SOX", "NIST", "CIS"}


def fail(message: str) -> None:
    print(f"capability profile validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> Any:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        fail(f"{path}: expected YAML content")
    return data


def profile_from_file(path: Path, profile_var: str) -> dict:
    data = load_yaml(path)
    if not isinstance(data, dict):
        fail(f"{path}: expected a YAML mapping")
    profile = data.get(profile_var)
    if not isinstance(profile, dict):
        fail(f"{path}: missing {profile_var} mapping")
    return profile


def validate_profile(path: Path, profile: dict) -> None:
    for name, spec in sorted(profile.items()):
        if not isinstance(spec, dict):
            fail(f"{path}: {name} must be a mapping")
        missing = REQUIRED_FIELDS - set(spec)
        extra = set(spec) - (REQUIRED_FIELDS | OPTIONAL_FIELDS)
        if missing:
            fail(f"{path}: {name} missing fields: {', '.join(sorted(missing))}")
        if extra:
            fail(f"{path}: {name} has unsupported fields: {', '.join(sorted(extra))}")
        if not isinstance(spec["required"], bool):
            fail(f"{path}: {name}.required must be boolean")
        if spec["criticality"] not in VALID_CRITICALITY:
            fail(f"{path}: {name}.criticality must be one of {sorted(VALID_CRITICALITY)}")
        if spec["expected_state"] not in VALID_EXPECTED_STATE:
            fail(f"{path}: {name}.expected_state must be one of {sorted(VALID_EXPECTED_STATE)}")
        if spec["owner"] not in VALID_OWNERS:
            fail(f"{path}: {name}.owner must be one of {sorted(VALID_OWNERS)}")
        evidence = spec["evidence_required"]
        if not isinstance(evidence, list) or not evidence:
            fail(f"{path}: {name}.evidence_required must be a non-empty list")
        invalid_evidence = sorted(set(evidence) - VALID_EVIDENCE)
        if invalid_evidence:
            fail(f"{path}: {name}.evidence_required has unsupported values: {', '.join(invalid_evidence)}")
        if not isinstance(spec["notes"], str) or not spec["notes"].strip():
            fail(f"{path}: {name}.notes must be a non-empty string")
        if not isinstance(spec["docs"], str) or not spec["docs"].strip():
            fail(f"{path}: {name}.docs must be a non-empty URL string")
        if not spec["docs"].startswith(("https://", "http://")):
            fail(f"{path}: {name}.docs must start with http:// or https://")
        standards = spec.get("standards", [])
        if standards is not None:
            if not isinstance(standards, list):
                fail(f"{path}: {name}.standards must be a list when provided")
            invalid_standards = [item for item in standards if item not in VALID_COMPLIANCE_STANDARDS]
            if invalid_standards:
                fail(
                    f"{path}: {name}.standards has unsupported values: "
                    f"{', '.join(sorted(set(invalid_standards)))}"
                )


def main() -> int:
    if len(sys.argv) not in [2, 3]:
        fail("usage: validate_openshift_capability_profile.py <profile-input> [profile-var]")

    input_path = Path(sys.argv[1])
    profile_var = sys.argv[2] if len(sys.argv) == 3 else "kubernetes_report_capability_profile"
    input_profile = profile_from_file(input_path, profile_var)
    validate_profile(input_path, input_profile)

    print(f"{input_path}: capability profile validation ok ({len(input_profile)} capabilities)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
