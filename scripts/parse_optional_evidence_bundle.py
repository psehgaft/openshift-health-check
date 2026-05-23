#!/usr/bin/env python3
"""Parse optional collected evidence in one controller-side helper call.

The helper intentionally delegates parsing to the existing parser scripts so
that evidence interpretation stays identical to the single-parser tasks it
replaces. Its responsibility is limited to preserving Ansible merge semantics
while reducing task/register/set_fact overhead in large collected runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


OPTIONAL_SOURCES = {
    "cluster_compare": {
        "script": "parse_cluster_compare.py",
        "source": {
            "name": "cluster-compare",
            "type": "report-file",
            "mode": "offline",
            "parser": "parse_cluster_compare.py",
        },
        "path_key": "cluster_compare_path",
        "summary_path_key": "cluster_compare_path",
        "data_key": "cluster_compare_data",
        "label": "cluster-compare",
        "requires_key": "requires_cluster_compare",
    },
    "inspect": {
        "script": "parse_inspect.py",
        "source": {
            "name": "inspect",
            "type": "resource-directory",
            "mode": "offline",
            "parser": "parse_inspect.py",
        },
        "path_key": "inspect_path",
        "summary_path_key": "inspect_path",
        "data_key": "inspect_data",
        "label": "inspect",
        "requires_key": "requires_inspect",
    },
    "managed_gates": {
        "script": "parse_managed_gates.py",
        "source": {
            "name": "managed-gates",
            "type": "report-file",
            "mode": "offline",
            "parser": "parse_managed_gates.py",
        },
        "path_key": "managed_gates_path",
        "summary_path_key": "managed_gates_path",
        "data_key": "managed_gates_data",
        "label": "managed-gates",
        "requires_key": "requires_managed_gates",
    },
    "advisor_export": {
        "script": "parse_advisor_export.py",
        "source": {
            "name": "advisor-export",
            "type": "report-file",
            "mode": "offline",
            "parser": "parse_advisor_export.py",
        },
        "path_key": "advisor_export_path",
        "summary_path_key": "advisor_export_path",
        "data_key": "advisor_export_data",
        "label": "advisor-export",
        "requires_key": "requires_advisor_export",
    },
    "insights_archive": {
        "script": "parse_insights_archive.py",
        "source": {
            "name": "insights-archive",
            "type": "archive-directory",
            "mode": "offline",
            "parser": "parse_insights_archive.py",
        },
        "path_key": "insights_archive_path",
        "summary_path_key": "insights_archive_path",
        "data_key": "insights_archive_data",
        "label": "insights-archive",
        "requires_key": "requires_insights_archive",
    },
}


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_path(value: Any) -> str:
    return str(value or "").strip()


def _load_stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("stdin JSON must be an object")
    return data


def _run_parser(script_name: str, args: list[str]) -> dict[str, Any]:
    cmd = [sys.executable, str(SCRIPT_DIR / script_name), *args]
    result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def _append_source(
    evidence_sources: list[dict[str, Any]],
    evidence_summary: dict[str, Any],
    source: dict[str, Any],
    label: str,
    source_increment: int = 1,
) -> None:
    evidence_sources.append(source)
    evidence_summary["source_count"] = int(evidence_summary.get("source_count") or 0) + source_increment
    evidence_summary["source_labels"] = list(evidence_summary.get("source_labels") or []) + [label]


def _resolve_mode(data: dict[str, Any]) -> str:
    evidence_mode = str(data.get("evidence_mode") or "auto")
    if evidence_mode != "auto":
        return evidence_mode
    must_gather_path = _clean_path(data.get("must_gather_path"))
    inspect_path = _clean_path(data.get("inspect_path"))
    if must_gather_path and inspect_path:
        return "hybrid"
    return "must_gather" if must_gather_path else "inspect"


def build_bundle(data: dict[str, Any]) -> dict[str, Any]:
    evidence_summary = dict(data.get("evidence_summary") or {"source_count": 0, "source_labels": []})
    evidence_sources = list(data.get("evidence_sources") or [])
    payload: dict[str, Any] = {
        "cluster_compare_data": {},
        "inspect_data": {},
        "managed_gates_data": {},
        "sosreport_data": {},
        "advisor_export_data": {},
        "insights_archive_data": {},
        "evidence_limitations": list(data.get("evidence_limitations") or []),
    }

    for key, spec in OPTIONAL_SOURCES.items():
        if not _as_bool(data.get(spec["requires_key"]), True):
            continue
        source_path = _clean_path(data.get(spec["path_key"]))
        if not source_path:
            continue
        parsed = _run_parser(str(spec["script"]), [source_path])
        payload[str(spec["data_key"])] = parsed
        if parsed:
            source = dict(spec["source"])
            source["path"] = source_path
            _append_source(evidence_sources, evidence_summary, source, str(spec["label"]))
        evidence_summary[str(spec["summary_path_key"])] = source_path

    sos_paths = data.get("sosreport_paths") or []
    if isinstance(sos_paths, str):
        sos_paths = [sos_paths] if sos_paths.strip() else []
    if _as_bool(data.get("requires_sosreport"), True) and sos_paths:
        parsed_sos = _run_parser("parse_sosreport.py", [str(path) for path in sos_paths])
        payload["sosreport_data"] = parsed_sos
        reports = parsed_sos.get("reports") if isinstance(parsed_sos, dict) else []
        sos_sources = []
        if isinstance(reports, list):
            for report in reports:
                if isinstance(report, dict):
                    source = dict(report)
                    source.update(
                        {
                            "name": "sosreport",
                            "type": "node-archive",
                            "mode": "offline",
                            "parser": "parse_sosreport.py",
                        }
                    )
                    sos_sources.append(source)
        if sos_sources:
            evidence_sources.extend(sos_sources)
            evidence_summary["source_count"] = int(evidence_summary.get("source_count") or 0) + len(sos_sources)
            evidence_summary["source_labels"] = list(evidence_summary.get("source_labels") or []) + ["sosreport"]
        summary = parsed_sos.get("summary") if isinstance(parsed_sos, dict) else {}
        evidence_summary["sosreport_count"] = (summary or {}).get("count", 0)

    evidence_mode_resolved = _resolve_mode(data)
    evidence_summary["mode"] = evidence_mode_resolved
    payload["evidence_mode_resolved"] = evidence_mode_resolved
    payload["evidence_sources"] = evidence_sources
    payload["evidence_summary"] = evidence_summary
    return payload


def main() -> int:
    try:
        data = _load_stdin()
        print(json.dumps(build_bundle(data), separators=(",", ":")))
        return 0
    except SystemExit as exc:
        return int(exc.code or 1)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
