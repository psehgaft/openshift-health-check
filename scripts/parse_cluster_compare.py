#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def parse_structured(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    if suffix in {".yaml", ".yml"} and yaml is not None:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if isinstance(data, dict):
            return data
    return None


def parse_text(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    reference_files = [line for line in lines if "Reference File:" in line]
    diff_outputs = [line for line in lines if "Diff Output:" in line]
    missing = [line for line in lines if re.search(r"\bmissing\b", line, re.IGNORECASE)]
    errors = [line for line in lines if re.search(r"\b(error|failed|failure)\b", line, re.IGNORECASE)]
    warnings = [line for line in lines if re.search(r"\bwarn(ing)?\b", line, re.IGNORECASE)]
    return {
        "summary": {
            "format": "text",
            "comparison_count": len(reference_files),
            "diff_count": len(diff_outputs),
            "missing_count": len(missing),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "samples": {
            "reference_files": reference_files[:15],
            "diff_outputs": diff_outputs[:15],
            "missing_lines": missing[:15],
            "error_lines": errors[:15],
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_cluster_compare.py <cluster-compare-path>"}))
        return 1
    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists() or not path.is_file():
        print(json.dumps({"error": "cluster-compare path not found", "path": str(path)}))
        return 2
    structured = parse_structured(path)
    if structured is not None:
        payload = {
            "summary": {
                "format": "structured",
                "comparison_count": int(structured.get("comparison_count", structured.get("comparisons", 0)) or 0),
                "diff_count": int(structured.get("diff_count", structured.get("diffs", 0)) or 0),
                "missing_count": int(structured.get("missing_count", structured.get("missing", 0)) or 0),
                "error_count": int(structured.get("error_count", structured.get("errors", 0)) or 0),
                "warning_count": int(structured.get("warning_count", structured.get("warnings", 0)) or 0),
            },
            "raw": structured,
        }
    else:
        payload = parse_text(path)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
