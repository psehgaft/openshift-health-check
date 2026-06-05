#!/usr/bin/env python3
"""Validate unified cluster health profile files and optional override files."""

import sys
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"cluster health profile validation failed: PyYAML is required: {exc}", file=sys.stderr)
    raise SystemExit(1)


REQUIRED_POSTURE_FIELDS = {
    "enabled",
    "required",
    "owner",
    "notes",
    "docs",
    "verification",
    "includes",
    "satisfied_by_all",
}
REQUIRED_CAPABILITY_FIELDS = {
    "enabled",
    "required",
    "criticality",
    "expected_state",
    "owner",
    "evidence_required",
    "notes",
    "docs",
    "verification",
}
OPTIONAL_CAPABILITY_FIELDS = {
    "standards",
}
VALID_CRITICALITY = {"critical", "high", "medium", "low", "info"}
VALID_EXPECTED_STATE = {"present", "absent", "configured", "healthy", "not_applicable"}
VALID_OWNERS = {
    "supportability",
    "platform",
    "node",
    "backup",
    "operations",
    "observability",
    "security",
    "storage",
    "network",
    "release",
    "workload",
    "lifecycle",
    "capacity",
    "extensions",
    "day2",
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

MIN_NOTES_WORDS = 10
MIN_VERIFICATION_WORDS = 4
FORBIDDEN_QUALITY_FRAGMENTS = (
    "when this capability is in scope",
    "when this posture is in scope",
    "configured when this capability is in scope",
    "configured when this posture is in scope",
    "if this capability is in scope",
    "if this posture is in scope",
)
POSTURE_BUILDER_DIR = Path("roles")


def fail(message: str) -> None:
    print(f"cluster health profile validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path) -> Any:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        fail(f"{path}: expected YAML content")
    return data


def normalize_string_list(value: Any, path: str) -> List[str]:
    if not isinstance(value, list) or not value:
        fail(f"{path} must be a non-empty list")
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        fail(f"{path} must contain at least one non-empty string")
    return items


def validate_override_string_list(value: Any, path: str) -> List[str]:
    if not isinstance(value, list):
        fail(f"{path} must be a list")
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        fail(f"{path} must contain at least one non-empty string when provided")
    return items


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def validate_quality_text(value: str, path: str, *, min_words: int) -> None:
    normalized = normalize_whitespace(value)
    if len(normalized.split()) < min_words:
        fail(f"{path} must be at least {min_words} words so the guidance is specific enough")
    lowered = normalized.lower()
    for fragment in FORBIDDEN_QUALITY_FRAGMENTS:
        if fragment in lowered:
            fail(f"{path} uses vague placeholder wording: {fragment!r}")


def validate_quality_list(values: List[str], path: str, *, min_words: int) -> None:
    for idx, item in enumerate(values, 1):
        validate_quality_text(item, f"{path}[{idx}]", min_words=min_words)


def discover_posture_builder_capability_references(repo_root: Path) -> Dict[str, Set[str]]:
    references: Dict[str, Set[str]] = {}
    posture_builder_pattern = re.compile(
        r"day2_capability_sections_by_key\s*\|\s*default\(\{\}\)\)\.get\('([^']+)'"
    )
    for builder_path in sorted((repo_root / POSTURE_BUILDER_DIR).glob("posture_*/tasks/*.yml")):
        posture_key = builder_path.parts[-3].replace("posture_", "", 1)
        matches = set(posture_builder_pattern.findall(builder_path.read_text(encoding="utf-8")))
        if matches:
            references.setdefault(posture_key, set()).update(matches)
    return references


def validate_profile_mapping(
    path: Path,
    profile: Dict[str, Any],
    *,
    strict: bool,
    reference_capabilities: Optional[Set[str]] = None,
    repo_root: Optional[Path] = None,
) -> Set[str]:
    if not isinstance(profile, dict):
        fail(f"{path}: cluster_health_profile must be a mapping")
    postures = profile.get("postures", {})
    capabilities = profile.get("capabilities", {})
    if strict:
        if not isinstance(postures, dict) or not postures:
            fail(f"{path}: cluster_health_profile.postures must be a non-empty mapping")
        if not isinstance(capabilities, dict) or not capabilities:
            fail(f"{path}: cluster_health_profile.capabilities must be a non-empty mapping")
    else:
        if "postures" in profile and not isinstance(postures, dict):
            fail(f"{path}: cluster_health_profile.postures must be a mapping when provided")
        if "capabilities" in profile and not isinstance(capabilities, dict):
            fail(f"{path}: cluster_health_profile.capabilities must be a mapping when provided")
        if not postures and not capabilities:
            fail(f"{path}: cluster_health_profile override must define at least one posture or capability override")

    known_capabilities = set(capabilities)
    if reference_capabilities:
        known_capabilities |= set(reference_capabilities)
    assignments = {}  # type: Dict[str, List[str]]
    posture_assignments: Dict[str, Set[str]] = {}

    for name, spec in sorted(postures.items()):
        if not isinstance(spec, dict):
            fail(f"{path}: posture {name} must be a mapping")
        missing = REQUIRED_POSTURE_FIELDS - set(spec) if strict else set()
        extra = set(spec) - REQUIRED_POSTURE_FIELDS
        if strict and missing:
            fail(f"{path}: posture {name} missing fields: {', '.join(sorted(missing))}")
        if extra:
            fail(f"{path}: posture {name} has unsupported fields: {', '.join(sorted(extra))}")
        if "enabled" in spec and not isinstance(spec["enabled"], bool):
            fail(f"{path}: posture {name}.enabled must be boolean")
        if "required" in spec and not isinstance(spec["required"], bool):
            fail(f"{path}: posture {name}.required must be boolean")
        if "owner" in spec and spec["owner"] not in VALID_OWNERS:
            fail(f"{path}: posture {name}.owner must be one of {sorted(VALID_OWNERS)}")
        if "notes" in spec and (not isinstance(spec["notes"], str) or not spec["notes"].strip()):
            fail(f"{path}: posture {name}.notes must be a non-empty string")
        if strict and "notes" in spec:
            validate_quality_text(spec["notes"], f"{path}: posture {name}.notes", min_words=MIN_NOTES_WORDS)
        if "docs" in spec:
            docs = normalize_string_list(spec["docs"], f"{path}: posture {name}.docs") if strict else validate_override_string_list(spec["docs"], f"{path}: posture {name}.docs")
            if any(not item.startswith(("https://", "http://")) for item in docs):
                fail(f"{path}: posture {name}.docs entries must start with http:// or https://")
        if "verification" in spec:
            if strict:
                verification_items = normalize_string_list(spec["verification"], f"{path}: posture {name}.verification")
                validate_quality_list(verification_items, f"{path}: posture {name}.verification", min_words=MIN_VERIFICATION_WORDS)
            else:
                validate_override_string_list(spec["verification"], f"{path}: posture {name}.verification")
        if "includes" in spec:
            if not isinstance(spec["includes"], list):
                fail(f"{path}: posture {name}.includes must be a list")
            includes = [str(item).strip() for item in spec["includes"] if str(item).strip()]
            unknown_includes = sorted(set(includes) - known_capabilities) if known_capabilities else []
            if unknown_includes:
                fail(f"{path}: posture {name}.includes references unknown capabilities: {', '.join(unknown_includes)}")
            if strict:
                for item in includes:
                    assignments.setdefault(item, []).append(f"{name}.includes")
                    posture_assignments.setdefault(name, set()).add(item)
        if "satisfied_by_all" in spec:
            if not isinstance(spec["satisfied_by_all"], list):
                fail(f"{path}: posture {name}.satisfied_by_all must be a list")
            alt_caps = [str(item).strip() for item in spec["satisfied_by_all"] if str(item).strip()]
            unknown_alt_caps = sorted(set(alt_caps) - known_capabilities) if known_capabilities else []
            if unknown_alt_caps:
                fail(
                    f"{path}: posture {name}.satisfied_by_all references unknown capabilities: "
                    f"{', '.join(unknown_alt_caps)}"
                )
            if strict:
                for item in alt_caps:
                    assignments.setdefault(item, []).append(f"{name}.satisfied_by_all")
                    posture_assignments.setdefault(name, set()).add(item)

    for name, spec in sorted(capabilities.items()):
        if not isinstance(spec, dict):
            fail(f"{path}: capability {name} must be a mapping")
        missing = REQUIRED_CAPABILITY_FIELDS - set(spec) if strict else set()
        extra = set(spec) - (REQUIRED_CAPABILITY_FIELDS | OPTIONAL_CAPABILITY_FIELDS)
        if strict and missing:
            fail(f"{path}: capability {name} missing fields: {', '.join(sorted(missing))}")
        if extra:
            fail(f"{path}: capability {name} has unsupported fields: {', '.join(sorted(extra))}")
        if "enabled" in spec and not isinstance(spec["enabled"], bool):
            fail(f"{path}: capability {name}.enabled must be boolean")
        if "required" in spec and not isinstance(spec["required"], bool):
            fail(f"{path}: capability {name}.required must be boolean")
        if "criticality" in spec and spec["criticality"] not in VALID_CRITICALITY:
            fail(f"{path}: capability {name}.criticality must be one of {sorted(VALID_CRITICALITY)}")
        if "expected_state" in spec and spec["expected_state"] not in VALID_EXPECTED_STATE:
            fail(f"{path}: capability {name}.expected_state must be one of {sorted(VALID_EXPECTED_STATE)}")
        if "owner" in spec and spec["owner"] not in VALID_OWNERS:
            fail(f"{path}: capability {name}.owner must be one of {sorted(VALID_OWNERS)}")
        if "evidence_required" in spec:
            evidence = normalize_string_list(spec["evidence_required"], f"{path}: capability {name}.evidence_required") if strict else validate_override_string_list(spec["evidence_required"], f"{path}: capability {name}.evidence_required")
            invalid_evidence = sorted(set(evidence) - VALID_EVIDENCE)
            if invalid_evidence:
                fail(f"{path}: capability {name}.evidence_required has unsupported values: {', '.join(invalid_evidence)}")
        if "notes" in spec and (not isinstance(spec["notes"], str) or not spec["notes"].strip()):
            fail(f"{path}: capability {name}.notes must be a non-empty string")
        if strict and "notes" in spec:
            validate_quality_text(spec["notes"], f"{path}: capability {name}.notes", min_words=MIN_NOTES_WORDS)
        if "docs" in spec:
            docs = normalize_string_list(spec["docs"], f"{path}: capability {name}.docs") if strict else validate_override_string_list(spec["docs"], f"{path}: capability {name}.docs")
            if any(not item.startswith(("https://", "http://")) for item in docs):
                fail(f"{path}: capability {name}.docs entries must start with http:// or https://")
        if "verification" in spec:
            if strict:
                verification_items = normalize_string_list(spec["verification"], f"{path}: capability {name}.verification")
                validate_quality_list(verification_items, f"{path}: capability {name}.verification", min_words=MIN_VERIFICATION_WORDS)
            else:
                validate_override_string_list(spec["verification"], f"{path}: capability {name}.verification")

    if strict:
        required_assignment = {
            name
            for name, spec in capabilities.items()
            if bool(spec.get("enabled", True)) or bool(spec.get("required", False))
        }
        unassigned = sorted(required_assignment - set(assignments))
        if unassigned:
            fail(
                f"{path}: enabled or required capabilities must be mapped by a posture include or satisfied_by_all: "
                f"{', '.join(unassigned)}"
            )
        duplicate_assignments = {key: value for key, value in assignments.items() if len(value) > 1}
        if duplicate_assignments:
            rendered = ", ".join(f"{key} -> {', '.join(value)}" for key, value in sorted(duplicate_assignments.items()))
            fail(f"{path}: capabilities may not be assigned to multiple posture paths: {rendered}")
        if repo_root is not None:
            builder_refs = discover_posture_builder_capability_references(repo_root)
            mismatches = []
            for posture_key, capability_keys in sorted(builder_refs.items()):
                assigned_keys = posture_assignments.get(posture_key, set())
                missing = sorted(capability_keys - assigned_keys)
                if missing:
                    mismatches.append(f"{posture_key} -> {', '.join(missing)}")
            if mismatches:
                fail(
                    f"{path}: posture builder capability references must be owned by the same posture via includes or "
                    f"satisfied_by_all: {'; '.join(mismatches)}"
                )
    return set(capabilities)


def main() -> int:
    if len(sys.argv) < 2:
        fail("usage: validate_cluster_health_profile.py <profile.yml> [<profile.yml> ...]")

    defaults_capabilities = None  # type: Optional[Set[str]]
    repo_root = Path(__file__).resolve().parent.parent
    for index, raw_path in enumerate(sys.argv[1:], 1):
        path = Path(raw_path)
        payload = load_yaml(path)
        if not isinstance(payload, dict):
            fail(f"{path}: expected a YAML mapping")
        profile = payload.get("cluster_health_profile")
        strict = index == 1
        returned_capabilities = validate_profile_mapping(
            path,
            profile,
            strict=strict,
            reference_capabilities=defaults_capabilities,
            repo_root=repo_root,
        )
        if strict:
            defaults_capabilities = returned_capabilities
        print(f"{path}: cluster health profile validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
