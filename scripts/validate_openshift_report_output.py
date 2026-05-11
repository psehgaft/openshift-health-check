#!/usr/bin/env python3
"""Validate rendered OpenShift report artifacts for common regressions."""

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


EXPECTED_CLUSTER_SECTIONS = [
    "Report Context",
    "Cluster Health Overview",
    "Evidence And Supportability",
    "Platform Health",
    "Node Health And Capacity",
    "Backup And Disaster Recovery",
    "Application Access And Network Isolation",
    "Observability",
    "Security And Governance",
    "Workload Health",
    "Platform Architecture And Lifecycle",
    "Capacity Planning Snapshot",
    "Declarative Operations",
    "Container Platform Adoption And Release Engineering",
    "Day 2 Production Readiness",
]

REQUIRED_CLUSTER_SUBSECTIONS = [
    "### Health Score",
    "### Recommendations",
    "### Findings",
]

FORBIDDEN_MARKDOWN_PATTERNS = [
    (r"\b(?:UNKONWN|UNKNWON|UNKNONW|UNKNOWN|Unknown|unknown)\b", "unknown-state labels must be normalized"),
    (r"^#### Execution Context$", "execution context must not render in the report"),
    (r"Run time (seconds|minutes)", "execution runtime stats must not render in the report"),
    (r"\baro-gitops\b", "customer report must not mention aro-gitops"),
    (r"\baro-classic-terraform/", "customer report must not mention aro-classic-terraform"),
    (r"Collection notes:\s*\|", "collection notes must not collapse into an inline table"),
    (r"\| Signal \| Value \| \s*\| --- \| --- \|", "finding tables must not collapse onto one line"),
]

RUNTIME_SIGNAL_OUTPUT_MARKERS = [
    "Runtime signal basis",
]

REQUIRED_DAY2_MARKERS = [
    "### Individual Capability Sections",
]

FORBIDDEN_CAPABILITY_ACTION_PATTERNS = (
    "Collect or review the expected evidence for this capability and remediate any gaps.",
    "Review the expected evidence for this capability.",
)
FORBIDDEN_CAPABILITY_DETAIL_PATTERNS = (
    "when this capability is in scope",
    "when this posture is in scope",
    "configured when this capability is in scope",
)

FORBIDDEN_JSON_PATTERNS = [
    (r"\b(?:UNKONWN|UNKNWON|UNKNONW|UNKNOWN)\b", "JSON payload must not contain misspelled or uppercase unknown labels"),
    (r"\baro-gitops\b", "JSON payload must not mention aro-gitops"),
    (r"\baro-classic-terraform/", "JSON payload must not mention aro-classic-terraform"),
]


def fail(message: str) -> None:
    print(f"rendered report validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path} is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path} must contain a JSON object")
    return payload


def validate_cluster_posture_sections(markdown: str) -> None:
    lines = markdown.splitlines()
    sections = []  # type: list
    for line_no, line in enumerate(lines, 1):
        if line.startswith("## "):
            sections.append((line_no, line[3:].strip()))

    non_appendix_sections = [
        (line_no, title)
        for line_no, title in sections
        if not title.startswith("Appendix:")
    ]
    titles = [title for _, title in non_appendix_sections]
    if titles != EXPECTED_CLUSTER_SECTIONS:
        fail("unexpected cluster section order: " + ", ".join(titles))

    for idx, (start, title) in enumerate(sections):
        if title.startswith("Appendix:"):
            continue
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines) + 1
        block = "\n".join(lines[start - 1 : end - 1])
        missing = [heading for heading in REQUIRED_CLUSTER_SUBSECTIONS if heading not in block]
        if missing:
            fail(f"{title!r} at line {start} missing {', '.join(missing)}")


def validate_markdown_tables(markdown: str) -> None:
    lines = markdown.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        if line.count("|") < 3:
            fail(f"malformed markdown table row at line {idx + 1}: {line}")
        if line.rstrip().endswith("| |"):
            fail(f"collapsed markdown table row at line {idx + 1}: {line}")


def validate_markdown(path: Path) -> None:
    markdown = path.read_text(encoding="utf-8")
    for pattern, message in FORBIDDEN_MARKDOWN_PATTERNS:
        if re.search(pattern, markdown, flags=re.IGNORECASE | re.MULTILINE):
            fail(f"{path}: {message}")

    validate_markdown_tables(markdown)

    if "## Report Context" in markdown:
        validate_cluster_posture_sections(markdown)

    for marker in RUNTIME_SIGNAL_OUTPUT_MARKERS:
        if marker not in markdown:
            fail(f"{path}: missing runtime signal provenance marker {marker!r}")

    for marker in REQUIRED_DAY2_MARKERS:
        if marker not in markdown:
            fail(f"{path}: missing required Day 2 capability marker {marker!r}")


def validate_markdown_matches_json(markdown_path: Path, json_path: Path) -> None:
    markdown = markdown_path.read_text(encoding="utf-8")
    payload = read_json(json_path)
    day2_domain = (
        ((payload.get("domains") or {}).get("production_day2_readiness") or {})
        or (((payload.get("audit_report") or {}).get("domains") or {}).get("production_day2_readiness") or {})
    )
    assessment_state = str(day2_domain.get("capability_assessment_state") or "").strip().lower()
    if assessment_state == "completed":
        if "Capability assessment did not complete cleanly in this run" in markdown:
            fail(f"{markdown_path}: markdown still renders fallback Day 2 assessment text even though JSON reports completed capability assessment")
        if "| Capability assessment state | `completed` |" not in markdown:
            fail(f"{markdown_path}: markdown must show completed Day 2 capability assessment state")


def validate_json(path: Path) -> None:
    payload = read_json(path)
    text = json.dumps(payload, sort_keys=True)
    for pattern, message in FORBIDDEN_JSON_PATTERNS:
        if re.search(pattern, text):
            fail(f"{path}: {message}")

    metadata = payload.get("metadata", {})
    if metadata.get("platform_family") != "openshift":
        fail(f"{path}: metadata.platform_family must be openshift")

    day2_domain = (
        ((payload.get("domains") or {}).get("production_day2_readiness") or {})
        or (((payload.get("audit_report") or {}).get("domains") or {}).get("production_day2_readiness") or {})
    )
    capability_sections = day2_domain.get("capability_sections") or []
    if not isinstance(capability_sections, list) or len(capability_sections) == 0:
        fail(f"{path}: production_day2_readiness.capability_sections must be present and non-empty")

    assessment_state = str(day2_domain.get("capability_assessment_state") or "").strip().lower()
    if assessment_state != "completed":
        fail(
            f"{path}: production_day2_readiness.capability_assessment_state must be completed "
            f"(got {day2_domain.get('capability_assessment_state')!r})"
        )

    capability_keys = [
        str((item or {}).get("key") or "").strip()
        for item in capability_sections
        if isinstance(item, dict)
    ]
    if any(not key for key in capability_keys):
        fail(f"{path}: every capability section must include a non-empty key")
    if len(set(capability_keys)) != len(capability_keys):
        fail(f"{path}: capability section keys must be unique")

    profile_path = Path(__file__).resolve().parent.parent / "inputs" / "openshift-cluster-health-profile.yml"
    profile_payload = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    enabled_keys = {
        str(key).strip()
        for key, value in (((profile_payload.get("cluster_health_profile") or {}).get("capabilities") or {}).items())
        if str(key).strip() and isinstance(value, dict) and bool(value.get("enabled", False))
    }
    required_keys = {
        str(key).strip()
        for key, value in (((profile_payload.get("cluster_health_profile") or {}).get("capabilities") or {}).items())
        if str(key).strip() and isinstance(value, dict) and bool(value.get("enabled", False)) and bool(value.get("required", False))
    }
    if not required_keys:
        fail(f"{profile_path}: cluster_health_profile.capabilities must be present for validation")
    missing = sorted(required_keys - set(capability_keys))
    extra = sorted(set(capability_keys) - enabled_keys)
    if missing:
        fail(f"{path}: missing capability sections for {', '.join(missing)}")
    if extra:
        fail(f"{path}: unexpected capability sections for {', '.join(extra)}")

    for section in capability_sections:
        key = str((section or {}).get("key") or "").strip()
        docs = section.get("docs") or []
        verification = section.get("verification") or []
        recommended_action = str(section.get("recommended_action") or "").strip()
        top_detail = str(section.get("top_detail") or "").strip()
        owner = str(section.get("owner") or "").strip()
        status = str(section.get("status") or "").strip().upper()
        check_count = int(section.get("check_count") or 0)

        if not recommended_action:
            fail(f"{path}: capability section {key} must define a non-empty recommended_action")
        if recommended_action in FORBIDDEN_CAPABILITY_ACTION_PATTERNS:
            fail(f"{path}: capability section {key} must not use a generic fallback recommended_action")
        if not top_detail:
            fail(f"{path}: capability section {key} must define a non-empty top_detail")
        if not owner:
            fail(f"{path}: capability section {key} must define a non-empty owner")
        if not isinstance(docs, list) or not docs or any(not str(item).strip() for item in docs):
            fail(f"{path}: capability section {key} must define non-empty docs")
        if not isinstance(verification, list) or not verification or any(not str(item).strip() for item in verification):
            fail(f"{path}: capability section {key} must define non-empty verification")
        lowered_detail = top_detail.lower()
        lowered_action = recommended_action.lower()
        lowered_verification = " ".join(str(item).strip().lower() for item in verification)
        for pattern in FORBIDDEN_CAPABILITY_DETAIL_PATTERNS:
            if pattern in lowered_detail:
                fail(f"{path}: capability section {key} top_detail uses vague placeholder wording: {pattern!r}")
            if pattern in lowered_action:
                fail(f"{path}: capability section {key} recommended_action uses vague placeholder wording: {pattern!r}")
            if pattern in lowered_verification:
                fail(f"{path}: capability section {key} verification uses vague placeholder wording: {pattern!r}")
        if status in {"OK", "HEALTHY", "WARNING", "WARN", "CRITICAL", "FAILED", "FAIL", "ERROR", "BLOCKED"} and check_count == 0:
            fail(f"{path}: capability section {key} must include at least one mapped check for status {status}")


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: validate_openshift_report_output.py <markdown-report> <json-report>")

    markdown_path = Path(sys.argv[1])
    json_path = Path(sys.argv[2])
    validate_markdown(markdown_path)
    validate_json(json_path)
    validate_markdown_matches_json(markdown_path, json_path)
    print(f"{markdown_path}: rendered report validation ok")
    print(f"{json_path}: rendered JSON validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
