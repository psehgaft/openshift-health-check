#!/usr/bin/env python3
"""Validate rendered OpenShift report artifacts for common regressions."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


EXPECTED_CLUSTER_SECTIONS = [
    "Report Context",
    "At A Glance",
    "Evidence And Supportability",
    "Platform Health",
    "Node Health And Capacity",
    "Backup And Disaster Recovery",
    "Networking Architecture And Application Access",
    "Observability",
    "Security And Governance",
    "Workload Health",
    "Platform Architecture And Lifecycle",
    "Cluster Capacity Snapshot",
    "Operations Maturity",
    "Container Platform Adoption And Release Engineering",
    "Workload Capability Extensions",
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

FORBIDDEN_JSON_PATTERNS = [
    (r"\b(?:UNKONWN|UNKNWON|UNKNONW|UNKNOWN)\b", "JSON payload must not contain misspelled or uppercase unknown labels"),
    (r"\baro-gitops\b", "JSON payload must not mention aro-gitops"),
    (r"\baro-classic-terraform/", "JSON payload must not mention aro-classic-terraform"),
]


def fail(message: str) -> None:
    print(f"rendered report validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path} is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path} must contain a JSON object")
    return payload


def validate_source_priority(markdown: str) -> None:
    required = [
        "oc adm must-gather",
        "oc adm inspect",
        "oc get",
        "insights",
    ]
    positions = []
    for item in required:
        pos = markdown.find(item)
        if pos < 0:
            fail(f"missing evidence source priority item: {item}")
        positions.append(pos)
    if positions != sorted(positions):
        fail("evidence source priority is not in the required order")


def validate_cluster_posture_sections(markdown: str) -> None:
    lines = markdown.splitlines()
    sections: list[tuple[int, str]] = []
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

    validate_source_priority(markdown)
    validate_markdown_tables(markdown)

    if "## Report Context" in markdown:
        validate_cluster_posture_sections(markdown)


def validate_json(path: Path) -> None:
    payload = read_json(path)
    text = json.dumps(payload, sort_keys=True)
    for pattern, message in FORBIDDEN_JSON_PATTERNS:
        if re.search(pattern, text):
            fail(f"{path}: {message}")

    metadata = payload.get("metadata", {})
    if metadata.get("platform_family") != "openshift":
        fail(f"{path}: metadata.platform_family must be openshift")


def main() -> int:
    if len(sys.argv) != 3:
        fail("usage: validate_openshift_report_output.py <markdown-report> <json-report>")

    markdown_path = Path(sys.argv[1])
    json_path = Path(sys.argv[2])
    validate_markdown(markdown_path)
    validate_json(json_path)
    print(f"{markdown_path}: rendered report validation ok")
    print(f"{json_path}: rendered JSON validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
