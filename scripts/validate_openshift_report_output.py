#!/usr/bin/env python3
"""Validate rendered OpenShift report artifacts for common regressions."""

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


POSTURE_SECTION_TITLES = [
    ("platform_health", "Platform Health"),
    ("node_health_and_capacity", "Node Health And Capacity"),
    ("backup_and_disaster_recovery", "Backup And Disaster Recovery"),
    ("application_access_and_network_isolation", "Application Access And Network Isolation"),
    ("observability", "Observability"),
    ("security_and_governance", "Security And Governance"),
    ("workload_health", "Workload Health"),
    ("platform_architecture_and_lifecycle", "Platform Architecture And Lifecycle"),
    ("capacity_planning_snapshot", "Capacity Planning Snapshot"),
    ("declarative_operations", "Declarative Operations"),
    ("container_platform_adoption_and_release_engineering", "Container Platform Adoption And Release Engineering"),
    ("day2_production_readiness", "Day 2 Production Readiness"),
]

REQUIRED_CLUSTER_SUBSECTIONS = [
    "### Health Score",
    "### Findings Summary",
    "### Findings",
]

ALLOWED_SECTION_LABELS = [
    "Health Score",
    "Findings Summary",
    "Findings",
]

ALLOWED_DAY2_SECTION_LABELS = [
    "Health Score",
    "Findings Summary",
    "Findings",
]

REQUIRED_CAPABILITY_SUBSECTIONS = [
    "#### Health Score",
    "#### Findings Summary",
    "#### Findings",
]

REQUIRED_APPENDIX_SUPPORTABILITY_SUBSECTIONS = [
    "#### Health Score",
    "#### Findings Summary",
    "#### Findings",
]

FORBIDDEN_MARKDOWN_PATTERNS = [
    (r"\b(?:UNKONWN|UNKNWON|UNKNONW|UNKNOWN|Unknown|unknown)\b", "unknown-state labels must be normalized"),
    (r"^#### Execution Context$", "execution context must not render in the report"),
    (r"^### Recommendations$", "legacy Recommendations subsections must not render"),
    (r"^### Operating Questions$", "legacy Operating Questions subsections must not render"),
    (r"^### Capability Assessment$", "legacy Capability Assessment heading must not render"),
    (r"^##### Assessment Summary$", "capability sections must use Findings Summary instead of Assessment Summary"),
    (r"^\*\*Leadership view\*\*", "capability sections must not render separate Leadership view labels"),
    (r"^\*\*Technical focus\*\*", "capability sections must not render separate Technical focus labels"),
    (r"Run time (seconds|minutes)", "execution runtime stats must not render in the report"),
    (r"\baro-gitops\b", "customer report must not mention aro-gitops"),
    (r"\baro-classic-terraform/", "customer report must not mention aro-classic-terraform"),
    (r"Collection notes:\s*\|", "collection notes must not collapse into an inline table"),
    (r"\| Signal \| Value \| \s*\| --- \| --- \|", "finding tables must not collapse onto one line"),
]

REQUIRED_DAY2_MARKERS = []

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
DECIMAL_NUMBER_RE = re.compile(r"[-+]?\d+\.\d+")

BAD_SUMMARY_CLEAN_PHRASES = [
    "no remediation is currently required",
    "no remediation was identified",
    "no material gap",
    "no material gaps",
    "no gaps detected",
    "no gap detected",
    "fully healthy",
    "posture is healthy",
    "capability is healthy",
    "area is healthy",
]

CRITICAL_SUMMARY_TERMS = [
    "critical",
    "blocking",
    "blocker",
    "failure",
    "failed",
    "outage",
    "degraded",
    "unavailable",
    "unhealthy",
    "already be degraded",
]

WARNING_SUMMARY_TERMS = [
    "warning",
    "gap",
    "risk",
    "review",
    "remediat",
    "not fully evidenced",
    "not in the expected healthy state",
    "not collected",
    "missing",
    "incomplete",
    "needs",
    "should",
]

FINDING_TABLE_HEADER = [
    "finding",
    "severity",
    "current state",
    "business impact",
    "technical evidence",
    "action plan",
    "suggested owner",
    "done when",
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


def expected_cluster_sections() -> list:
    profile_path = Path(__file__).resolve().parent.parent / "inputs" / "openshift-cluster-health-profile.yml"
    profile_payload = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    posture_profile = ((profile_payload.get("cluster_health_profile") or {}).get("postures") or {})
    capability_profile = ((profile_payload.get("cluster_health_profile") or {}).get("capabilities") or {})
    titles = ["Cluster Health Overview"]
    for key, title in POSTURE_SECTION_TITLES:
        value = posture_profile.get(key, {})
        if not isinstance(value, dict) or bool(value.get("enabled", True)):
            titles.append(title)
    if any(isinstance(value, dict) and bool(value.get("enabled", False)) for value in capability_profile.values()):
        titles.append("Capabilities Assessments")
    return titles


def expected_enabled_capability_titles() -> list:
    profile_path = Path(__file__).resolve().parent.parent / "inputs" / "openshift-cluster-health-profile.yml"
    profile_payload = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    capability_profile = ((profile_payload.get("cluster_health_profile") or {}).get("capabilities") or {})
    return [
        str(key).replace("_", " ").strip().title()
        for key, value in capability_profile.items()
        if str(key).strip() and isinstance(value, dict) and bool(value.get("enabled", False))
    ]


def validate_cluster_posture_sections(markdown: str) -> None:
    lines = markdown.splitlines()
    sections = []  # type: list
    for line_no, line in enumerate(lines, 1):
        if line.startswith("## "):
            sections.append((line_no, line[3:].strip()))

    non_appendix_sections = [
        (line_no, title)
        for line_no, title in sections
        if title != "Appendix" and not title.startswith("Appendix:")
    ]
    expected_sections = expected_cluster_sections()
    titles = [title for _, title in non_appendix_sections]
    if titles != expected_sections:
        fail("unexpected cluster section order: " + ", ".join(titles))

    for idx, (start, title) in enumerate(sections):
        if title == "Appendix" or title.startswith("Appendix:"):
            continue
        if title == "Capabilities Assessments":
            continue
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines) + 1
        block = "\n".join(lines[start - 1 : end - 1])
        missing = [heading for heading in REQUIRED_CLUSTER_SUBSECTIONS if heading not in block]
        if missing:
            fail(f"{title!r} at line {start} missing {', '.join(missing)}")
        if title not in {section_title for _, section_title in POSTURE_SECTION_TITLES}:
            continue
        direct_subsections = [
            line[4:].strip()
            for line in lines[start : end - 1]
            if line.startswith("### ") and not line.startswith("#### ")
        ]
        allowed_labels = ALLOWED_DAY2_SECTION_LABELS if title == "Day 2 Production Readiness" else ALLOWED_SECTION_LABELS
        if direct_subsections != allowed_labels:
            fail(
                f"{title!r} at line {start} must contain only "
                + ", ".join(allowed_labels)
                + "; found "
                + ", ".join(direct_subsections)
            )


def validate_day2_capability_markdown_sections(markdown: str) -> None:
    lines = markdown.splitlines()
    start_idx = None
    end_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Capabilities Assessments":
            start_idx = idx + 1
            continue
        if start_idx is not None and line.startswith("## "):
            end_idx = idx
            break
    if start_idx is None:
        fail("missing Capabilities Assessments section")
    if end_idx is None:
        end_idx = len(lines)
    block = lines[start_idx:end_idx]
    rendered_titles = [line[4:].strip() for line in block if line.startswith("### ") and not line.startswith("#### ")]
    expected_titles = expected_enabled_capability_titles()
    missing = sorted(set(expected_titles) - set(rendered_titles))
    extra = sorted(set(rendered_titles) - set(expected_titles))
    if missing or extra:
        fail(
            "unexpected Day 2 capability section set: "
            + (
                ("missing=" + ", ".join(missing)) if missing else ""
            )
            + (
                ("; " if missing and extra else "")
                + ("extra=" + ", ".join(extra) if extra else "")
            )
        )
    for idx, line in enumerate(block):
        if not line.startswith("### ") or line.startswith("#### "):
            continue
        title = line[4:].strip()
        next_idx = len(block)
        for probe_idx in range(idx + 1, len(block)):
            if block[probe_idx].startswith("### ") and not block[probe_idx].startswith("#### "):
                next_idx = probe_idx
                break
        capability_block = block[idx:next_idx]
        missing_subsections = [
            heading for heading in REQUIRED_CAPABILITY_SUBSECTIONS if heading not in capability_block
        ]
        if missing_subsections:
            fail(f"capability {title!r} missing {', '.join(missing_subsections)}")
        direct_subsections = [
            item[5:].strip()
            for item in capability_block
            if item.startswith("#### ") and not item.startswith("##### ")
        ]
        if direct_subsections != ALLOWED_SECTION_LABELS:
            fail(
                f"capability {title!r} must contain only "
                + ", ".join(ALLOWED_SECTION_LABELS)
                + "; found "
                + ", ".join(direct_subsections)
            )


def validate_appendix_heading_hierarchy(markdown: str) -> None:
    lines = markdown.splitlines()
    appendix_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Appendix":
            appendix_idx = idx
            break
    if appendix_idx is None:
        return

    appendix_block = lines[appendix_idx + 1 :]
    for idx, line in enumerate(appendix_block):
        if idx > 0 and line.startswith("## "):
            appendix_block = appendix_block[:idx]
            break

    direct_appendix_subsections = [
        line[4:].strip()
        for line in appendix_block
        if line.startswith("### ") and not line.startswith("#### ")
    ]
    forbidden_direct = {"Health Score", "Findings Summary", "Findings"}
    misplaced = [title for title in direct_appendix_subsections if title in forbidden_direct]
    if misplaced:
        fail(
            "Appendix contains posture child headings at level 3; "
            "Evidence And Supportability children must use level 4: "
            + ", ".join(misplaced)
        )

    try:
        supportability_idx = next(
            idx
            for idx, line in enumerate(appendix_block)
            if line.strip() == "### Evidence And Supportability"
        )
    except StopIteration:
        return

    supportability_end = len(appendix_block)
    for idx in range(supportability_idx + 1, len(appendix_block)):
        if appendix_block[idx].startswith("### ") and not appendix_block[idx].startswith("#### "):
            supportability_end = idx
            break
    supportability_block = appendix_block[supportability_idx:supportability_end]
    missing = [
        heading
        for heading in REQUIRED_APPENDIX_SUPPORTABILITY_SUBSECTIONS
        if heading not in supportability_block
    ]
    if missing:
        fail("Evidence And Supportability appendix subsection missing " + ", ".join(missing))

    direct_children = [
        line[5:].strip()
        for line in supportability_block
        if line.startswith("#### ") and not line.startswith("##### ")
    ]
    if direct_children != ALLOWED_SECTION_LABELS:
        fail(
            "Evidence And Supportability appendix subsection must contain only "
            + ", ".join(ALLOWED_SECTION_LABELS)
            + "; found "
            + ", ".join(direct_children)
        )


def split_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_markdown_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def extract_finding_rows(block: list[str], findings_heading: str) -> list[dict[str, str]]:
    try:
        start_idx = next(idx for idx, line in enumerate(block) if line.strip() == findings_heading)
    except StopIteration:
        return []

    table_start = None
    for idx in range(start_idx + 1, len(block)):
        if block[idx].startswith("#"):
            return []
        if block[idx].startswith("|"):
            table_start = idx
            break
    if table_start is None or table_start + 1 >= len(block):
        return []

    headers = [cell.lower() for cell in split_markdown_table_row(block[table_start])]
    separator = split_markdown_table_row(block[table_start + 1])
    if headers != FINDING_TABLE_HEADER or not is_markdown_separator_row(separator):
        return []

    rows = []
    for line in block[table_start + 2 :]:
        if not line.startswith("|"):
            break
        cells = split_markdown_table_row(line)
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def extract_summary_text(
    block: list[str],
    summary_heading: str,
    findings_heading: str,
    stop_before_headings: tuple[str, ...] = (),
) -> str:
    try:
        start_idx = next(idx for idx, line in enumerate(block) if line.strip() == summary_heading)
    except StopIteration:
        return ""
    end_idx = len(block)
    for idx in range(start_idx + 1, len(block)):
        if block[idx].strip() == findings_heading:
            end_idx = idx
            break
        if stop_before_headings and block[idx].startswith(stop_before_headings):
            end_idx = idx
            break
    return "\n".join(line.strip() for line in block[start_idx + 1 : end_idx]).strip()


def severity_rank(value: str) -> str:
    severity = re.sub(r"[^A-Za-z]", "", str(value or "")).upper()
    if severity in {"CRITICAL", "ERROR", "FAILED", "FAIL", "BLOCKED"}:
        return "critical"
    if severity in {"WARNING", "WARN"}:
        return "warning"
    return ""


def validate_summary_matches_findings(section_name: str, summary: str, rows: list[dict[str, str]]) -> None:
    if not rows:
        return

    lowered_summary = summary.lower()
    severities = [severity_rank(row.get("severity", "")) for row in rows]
    has_critical = "critical" in severities
    has_warning = "warning" in severities
    has_non_ok = has_critical or has_warning

    if has_non_ok:
        for phrase in BAD_SUMMARY_CLEAN_PHRASES:
            if phrase in lowered_summary:
                fail(
                    f"{section_name}: Findings Summary uses clean-state wording "
                    f"{phrase!r} while Findings table contains warning or critical rows"
                )

    if has_critical and not any(term in lowered_summary for term in CRITICAL_SUMMARY_TERMS):
        fail(
            f"{section_name}: Findings Summary must call out critical or blocking risk "
            "when the Findings table contains critical rows"
        )

    if has_warning and not any(term in lowered_summary for term in WARNING_SUMMARY_TERMS):
        fail(
            f"{section_name}: Findings Summary must call out warning-level risk, gaps, "
            "review needs, or evidence limits when the Findings table contains warning rows"
        )


def validate_posture_summary_accuracy(markdown: str) -> None:
    lines = markdown.splitlines()
    sections = []  # type: list[tuple[int, str]]
    for line_no, line in enumerate(lines, 1):
        if line.startswith("## "):
            sections.append((line_no, line[3:].strip()))

    posture_titles = {section_title for _, section_title in POSTURE_SECTION_TITLES}
    for idx, (start, title) in enumerate(sections):
        if title not in posture_titles:
            continue
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(lines) + 1
        block = lines[start - 1 : end - 1]
        summary = extract_summary_text(block, "### Findings Summary", "### Findings", ("#### ",))
        findings = extract_finding_rows(block, "### Findings")
        validate_summary_matches_findings(title, summary, findings)


def validate_capability_summary_accuracy(markdown: str) -> None:
    lines = markdown.splitlines()
    start_idx = None
    end_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Capabilities Assessments":
            start_idx = idx + 1
            continue
        if start_idx is not None and line.startswith("## "):
            end_idx = idx
            break
    if start_idx is None:
        return
    if end_idx is None:
        end_idx = len(lines)
    block = lines[start_idx:end_idx]
    capability_indexes = [
        (idx, line[4:].strip())
        for idx, line in enumerate(block)
        if line.startswith("### ") and not line.startswith("#### ")
    ]
    for pos, (idx, title) in enumerate(capability_indexes):
        next_idx = capability_indexes[pos + 1][0] if pos + 1 < len(capability_indexes) else len(block)
        capability_block = block[idx:next_idx]
        summary = extract_summary_text(capability_block, "#### Findings Summary", "#### Findings")
        findings = extract_finding_rows(capability_block, "#### Findings")
        validate_summary_matches_findings(f"capability {title}", summary, findings)


def validate_markdown_tables(markdown: str) -> None:
    lines = markdown.splitlines()
    for idx, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        if line.count("|") < 3:
            fail(f"malformed markdown table row at line {idx + 1}: {line}")
        if line.rstrip().endswith("| |"):
            fail(f"collapsed markdown table row at line {idx + 1}: {line}")


def decimal_context_is_identifier(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return (
        before.isalnum()
        or after.isalnum()
        or (bool(before) and before in "._/-:")
        or (bool(after) and after in "._/-:")
    )


def validate_decimal_precision(markdown: str) -> None:
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        for match in DECIMAL_NUMBER_RE.finditer(line):
            if decimal_context_is_identifier(line, *match.span()):
                continue
            decimal_part = match.group(0).split(".", 1)[1]
            if len(decimal_part) > 2:
                fail(
                    "rendered decimal value has more than two places at "
                    f"line {line_number}: {match.group(0)}"
                )


def validate_markdown(path: Path) -> None:
    markdown = path.read_text(encoding="utf-8")
    for pattern, message in FORBIDDEN_MARKDOWN_PATTERNS:
        if re.search(pattern, markdown, flags=re.IGNORECASE | re.MULTILINE):
            fail(f"{path}: {message}")

    validate_markdown_tables(markdown)
    validate_decimal_precision(markdown)

    validate_cluster_posture_sections(markdown)
    validate_day2_capability_markdown_sections(markdown)
    validate_appendix_heading_hierarchy(markdown)
    validate_posture_summary_accuracy(markdown)
    validate_capability_summary_accuracy(markdown)

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


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def domain_summary(domain: dict[str, Any]) -> dict[str, Any]:
    summary = domain.get("summary") if isinstance(domain, dict) else {}
    return summary if isinstance(summary, dict) else {}


def require_summary_count(
    path: Path,
    domain_name: str,
    summary: dict[str, Any],
    count_key: str,
    rows: Any,
) -> None:
    if not isinstance(rows, list):
        fail(f"{path}: {domain_name}.{count_key} source list must be a list")
    expected = len(rows)
    actual = as_int(summary.get(count_key), default=-1)
    if actual != expected:
        fail(
            f"{path}: {domain_name}.summary.{count_key}={actual} "
            f"does not match rendered payload list length {expected}"
        )


def validate_high_risk_json_summaries(path: Path, payload: dict[str, Any]) -> None:
    domains = payload.get("domains") or {}
    if not isinstance(domains, dict):
        fail(f"{path}: domains must be a JSON object")

    workload = domains.get("workload_health") or {}
    workload_summary = domain_summary(workload)
    if workload_summary:
        require_summary_count(
            path,
            "workload_health",
            workload_summary,
            "unhealthy_user_pod_count",
            workload.get("unhealthy_user_pods") or [],
        )
        require_summary_count(
            path,
            "workload_health",
            workload_summary,
            "high_restart_pod_count",
            workload.get("restart_hotspots") or [],
        )
        require_summary_count(
            path,
            "workload_health",
            workload_summary,
            "workload_health_issue_count",
            workload.get("workload_health_issues") or [],
        )
        workload_status = str(workload_summary.get("status") or "").strip().upper()
        if (
            as_int(workload_summary.get("unhealthy_user_pod_count")) > 0
            or as_int(workload_summary.get("workload_health_issue_count")) > 0
        ) and workload_status not in {"CRITICAL", "FAILED", "FAIL", "ERROR", "BLOCKED"}:
            fail(
                f"{path}: workload_health summary must not hide unhealthy pods or rollout issues "
                f"behind status {workload_status!r}"
            )

    node = domains.get("node_health_and_capacity") or {}
    node_summary = domain_summary(node)
    if node_summary:
        require_summary_count(
            path,
            "node_health_and_capacity",
            node_summary,
            "high_pod_density_node_count",
            node.get("high_pod_density_nodes") or [],
        )
        node_rows = node.get("nodes") or []
        if isinstance(node_rows, list) and as_int(node_summary.get("nodes"), len(node_rows)) != len(node_rows):
            fail(
                f"{path}: node_health_and_capacity.summary.nodes does not match "
                f"node list length {len(node_rows)}"
            )
        node_status = str(node_summary.get("status") or "").strip().upper()
        if (
            as_int(node_summary.get("not_ready_node_count")) > 0
            or as_int(node_summary.get("node_pressure_count")) > 0
            or as_int(node_summary.get("critical_pod_density_node_count")) > 0
        ) and node_status in {"OK", "HEALTHY"}:
            fail(
                f"{path}: node_health_and_capacity summary must not be healthy when "
                "not-ready, pressured, or critical-density nodes are present"
            )

    capacity = domains.get("capacity_planning_snapshot") or {}
    capacity_summary = domain_summary(capacity)
    if capacity_summary:
        capacity_status = str(capacity_summary.get("status") or "").strip().lower()
        if bool(capacity_summary.get("zero_allocatable_suspect")) and capacity_status in {"healthy", "ok"}:
            fail(
                f"{path}: capacity_planning_snapshot summary must not be healthy when "
                "zero allocatable resource data is suspect"
            )
        if bool(capacity_summary.get("object_count_partial")) and capacity_status in {"healthy", "ok"}:
            fail(
                f"{path}: capacity_planning_snapshot summary must not be healthy when "
                "object-count evidence is partial"
            )

    day2 = domains.get("production_day2_readiness") or {}
    day2_summary = domain_summary(day2)
    if day2_summary:
        top_blockers = day2_summary.get("top_blockers") or []
        day2_status = str(day2_summary.get("status") or "").strip().upper()
        if isinstance(top_blockers, list) and top_blockers and day2_status in {"OK", "HEALTHY"}:
            fail(
                f"{path}: production_day2_readiness summary must not be healthy when "
                "top blockers are present"
            )


def validate_json(path: Path) -> None:
    payload = read_json(path)
    text = json.dumps(payload, sort_keys=True)
    for pattern, message in FORBIDDEN_JSON_PATTERNS:
        if re.search(pattern, text):
            fail(f"{path}: {message}")

    metadata = payload.get("metadata", {})
    if metadata.get("platform_family") != "openshift":
        fail(f"{path}: metadata.platform_family must be openshift")

    validate_high_risk_json_summaries(path, payload)

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
    if not enabled_keys:
        fail(f"{profile_path}: cluster_health_profile.capabilities must be present for validation")
    missing = sorted(enabled_keys - set(capability_keys))
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
