#!/usr/bin/env python3
"""Guard the OpenShift health report template structure."""

import re
import sys
from pathlib import Path


EXPECTED_SECTIONS = [
    "Cluster Health Overview",
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

REQUIRED_SUBSECTIONS = [
    "### Health Score",
    "### Findings Summary",
    "### Findings",
]

ALLOWED_POSTURE_SUBSECTIONS = [
    "Health Score",
    "Findings Summary",
    "Findings",
]

POSTURE_SECTIONS = {
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
}

FORBIDDEN_PATTERNS = [
    (r"\{% if false %\}", "disabled legacy blocks must be removed"),
    (r"^#### Execution Context$", "execution context must not render in the report"),
    (r"^### Recommendations$", "legacy Recommendations subsections must not render"),
    (r"^### Operating Questions$", "legacy Operating Questions subsections must not render"),
    (r"^### Capability Assessments$", "legacy Capability Assessments heading must not render"),
    (r"^##### Assessment Summary$", "capability sections must use Findings Summary instead of Assessment Summary"),
    (r"^\*\*Leadership view\*\*", "capability sections must not render separate Leadership view labels"),
    (r"^\*\*Technical focus\*\*", "capability sections must not render separate Technical focus labels"),
    (r"Run time (seconds|minutes)", "execution runtime stats must not render in the report"),
    (r"\baro-gitops\b", "customer report must not mention aro-gitops"),
    (r"\baro-classic-terraform/", "customer report must not mention aro-classic-terraform"),
    (r"Collection notes:\s*\|", "collection notes must not collapse into an inline table"),
    (r"Operating model note:\s+\S", "operating model note must not collapse into an inline line"),
]

REQUIRED_RUNTIME_SIGNAL_MARKERS = [
    ("{% macro runtime_signal_basis(entry) -%}", "runtime signal provenance macro must exist"),
    ("{% macro pct_with_basis(value, kind, is_approximation) -%}", "runtime percentage rendering macro must exist"),
    ("Pods By Requested CPU Pressure", "template must support request-derived CPU labeling"),
    ("Pods By Requested Memory Pressure", "template must support request-derived memory labeling"),
]


def fail(message: str) -> None:
    print(f"template validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: validate_openshift_report_template.py <template>")

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    sections = []  # type: list
    for line_no, line in enumerate(lines, 1):
        if line.startswith("## "):
            sections.append((line_no, line[3:].strip()))

    non_appendix_sections = [
        (line_no, title)
        for line_no, title in sections
        if title != "Appendix" and not title.startswith("Appendix:")
    ]
    titles = [title for _, title in non_appendix_sections]

    if titles != EXPECTED_SECTIONS:
        fail(
            "unexpected non-appendix section order: "
            + ", ".join(titles)
        )

    if len(set(titles)) != len(titles):
        duplicates = sorted({title for title in titles if titles.count(title) > 1})
        fail("duplicate non-appendix sections: " + ", ".join(duplicates))

    for idx, (start, title) in enumerate(sections):
        if title == "Appendix" or title.startswith("Appendix:"):
            continue
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines) + 1
        block = "\n".join(lines[start - 1 : end - 1])
        missing = [heading for heading in REQUIRED_SUBSECTIONS if heading not in block]
        if missing:
            fail(f"{title!r} at line {start} missing {', '.join(missing)}")
        if title not in POSTURE_SECTIONS:
            continue
        direct_subsections = [
            line[4:].strip()
            for line in lines[start : end - 1]
            if line.startswith("### ") and not line.startswith("#### ")
        ]
        if direct_subsections != ALLOWED_POSTURE_SUBSECTIONS:
            fail(
                f"{title!r} at line {start} must contain only "
                + ", ".join(ALLOWED_POSTURE_SUBSECTIONS)
                + "; found "
                + ", ".join(direct_subsections)
            )

    for pattern, message in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            fail(message)

    for marker, message in REQUIRED_RUNTIME_SIGNAL_MARKERS:
        if marker not in text:
            fail(message)

    print(f"{path}: report template validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
