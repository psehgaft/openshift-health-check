#!/usr/bin/env python3
"""Normalize rendered Markdown Findings tables.

The report template intentionally keeps the source sections readable. This
helper applies report-wide table contract rules after render so every standard
Findings table is ordered and formatted consistently.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


FINDINGS_HEADER = (
    "| Finding | Severity | Current State | Business Impact | Technical Evidence | "
    "Action Plan | Suggested Owner | Done When |"
)
FINDINGS_SEPARATOR = "| --- | --- | --- | --- | --- | --- | --- | --- |"
FINDINGS_PROSE_COLUMN_INDEXES = {0, 1, 3, 5, 6, 7}
TEXTUAL_TABLE_HEADERS = {
    "action",
    "action plan",
    "apiservice",
    "area",
    "backing service",
    "business impact",
    "capability",
    "capability gap",
    "component",
    "crd",
    "current state",
    "detail",
    "done when",
    "domain",
    "finding",
    "group",
    "image",
    "issue",
    "kind",
    "level",
    "message",
    "name",
    "namespace",
    "observed cluster state",
    "owner",
    "product",
    "reason",
    "recommended action",
    "resource",
    "role",
    "service",
    "severity",
    "source",
    "source alignment",
    "suggested owner",
    "type",
    "version",
}
TEXTUAL_SIGNAL_LABEL_PATTERNS = (
    "action",
    "classification source",
    "confidence source",
    "detail",
    "evidence required",
    "finding",
    "gap status",
    "health reason summary",
    "images",
    "install model",
    "instance types",
    "kubernetes versions",
    "lifecycle support phase",
    "machine networks source",
    "node providers",
    "node shapes",
    "os images",
    "primary risk themes",
    "reason summary",
    "recommendation",
    "recommended",
    "risk themes",
    "runtimes",
    "source",
    "status reason",
    "summary",
    "support phase",
    "top blockers",
    "verdict",
)

SEVERITY_RANK = {
    "critical": 0,
    "failed": 0,
    "fail": 0,
    "error": 0,
    "unsupported-risk": 0,
    "warning": 1,
    "warn": 1,
    "review-required": 1,
    "info": 2,
    "partial": 2,
    "unknown": 3,
    "not-assessed": 3,
    "not-collected": 3,
    "insufficient-evidence": 3,
    "ok": 4,
    "pass": 4,
    "passed": 4,
    "healthy": 4,
    "supported": 4,
}


def split_markdown_row(row: str) -> list[str]:
    if not row.startswith("|"):
        return []
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def format_markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def strip_outer_backticks(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return value


def strip_outer_backticks_from_prose(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        inner = stripped[1:-1].strip()
        if " " in inner or ";" in inner:
            return inner
    return value


def normalize_prose_cells(row: str) -> str:
    cells = split_markdown_row(row)
    if len(cells) != 8:
        return row
    for idx in FINDINGS_PROSE_COLUMN_INDEXES:
        cells[idx] = strip_outer_backticks(cells[idx])
    return format_markdown_row(cells)


def normalize_textual_table_cells(header_cells: list[str], row: str) -> str:
    cells = split_markdown_row(row)
    if len(cells) != len(header_cells):
        return row
    lower_headers = [header.strip().lower() for header in header_cells]
    for idx, header in enumerate(header_cells):
        header_key = header.strip().lower()
        if header_key in TEXTUAL_TABLE_HEADERS:
            cells[idx] = strip_outer_backticks(cells[idx])
        elif header_key == "technical evidence":
            cells[idx] = strip_outer_backticks_from_prose(cells[idx])
    if len(cells) >= 2 and lower_headers[0] in {"signal", "item", "check"} and lower_headers[1] in {"value", "result"}:
        label = cells[0].replace("`", "").strip().lower()
        if any(pattern in label for pattern in TEXTUAL_SIGNAL_LABEL_PATTERNS):
            cells[1] = strip_outer_backticks(cells[1])
    cells = [strip_outer_backticks_from_prose(cell) for cell in cells]
    return format_markdown_row(cells)


def severity_key(row: str, original_index: int) -> tuple[int, int]:
    cells = split_markdown_row(row)
    if len(cells) < 2:
        return (99, original_index)
    severity = re.sub(r"<[^>]+>", "", cells[1])
    severity = severity.replace("`", "").strip().lower()
    return (SEVERITY_RANK.get(severity, 98), original_index)


def normalize_findings_tables(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        if (
            lines[index].strip() == FINDINGS_HEADER
            and index + 1 < len(lines)
            and lines[index + 1].strip() == FINDINGS_SEPARATOR
        ):
            output.append(lines[index])
            output.append(lines[index + 1])
            index += 2

            rows: list[str] = []
            while index < len(lines) and lines[index].startswith("| "):
                rows.append(normalize_prose_cells(lines[index]))
                index += 1

            output.extend(
                row
                for _, row in sorted(
                    enumerate(rows),
                    key=lambda item: severity_key(item[1], item[0]),
                )
            )
            continue

        output.append(lines[index])
        index += 1

    trailing_newline = "\n" if markdown.endswith("\n") else ""
    return "\n".join(output) + trailing_newline


def normalize_textual_table_columns(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        if (
            lines[index].startswith("|")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("|")
        ):
            header_cells = split_markdown_row(lines[index])
            separator_cells = split_markdown_row(lines[index + 1])
            if header_cells and len(header_cells) == len(separator_cells) and all(
                re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in separator_cells
            ):
                output.append(lines[index])
                output.append(lines[index + 1])
                index += 2
                while index < len(lines) and lines[index].startswith("|"):
                    output.append(normalize_textual_table_cells(header_cells, lines[index]))
                    index += 1
                continue

        output.append(lines[index])
        index += 1

    trailing_newline = "\n" if markdown.endswith("\n") else ""
    return "\n".join(output) + trailing_newline


def normalize_file(path: Path) -> None:
    markdown = path.read_text(encoding="utf-8")
    normalized = normalize_textual_table_columns(normalize_findings_tables(markdown))
    if normalized != markdown:
        path.write_text(normalized, encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: normalize_findings_tables.py <markdown-path> [<markdown-path> ...]", file=sys.stderr)
        return 2
    for raw_path in sys.argv[1:]:
        normalize_file(Path(raw_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
