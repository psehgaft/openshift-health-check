#!/usr/bin/env python3
"""Guard the OpenShift health report template structure."""

from __future__ import annotations

import re
import sys
from pathlib import Path


EXPECTED_SECTIONS = [
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

REQUIRED_SUBSECTIONS = [
    "### Health Score",
    "### Recommendations",
    "### Findings",
]

FORBIDDEN_PATTERNS = [
    (r"\{% if false %\}", "disabled legacy blocks must be removed"),
    (r"^#### Execution Context$", "execution context must not render in the report"),
    (r"Run time (seconds|minutes)", "execution runtime stats must not render in the report"),
    (r"\baro-gitops\b", "customer report must not mention aro-gitops"),
    (r"\baro-classic-terraform/", "customer report must not mention aro-classic-terraform"),
    (r"Collection notes:\s*\|", "collection notes must not collapse into an inline table"),
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

    if titles != EXPECTED_SECTIONS:
        fail(
            "unexpected non-appendix section order: "
            + ", ".join(titles)
        )

    if len(set(titles)) != len(titles):
        duplicates = sorted({title for title in titles if titles.count(title) > 1})
        fail("duplicate non-appendix sections: " + ", ".join(duplicates))

    for idx, (start, title) in enumerate(sections):
        if title.startswith("Appendix:"):
            continue
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines) + 1
        block = "\n".join(lines[start - 1 : end - 1])
        missing = [heading for heading in REQUIRED_SUBSECTIONS if heading not in block]
        if missing:
            fail(f"{title!r} at line {start} missing {', '.join(missing)}")

    for pattern, message in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            fail(message)

    print(f"{path}: report template validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
