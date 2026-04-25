#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def normalize_gather_items(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("items", "gathers", "records", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def item_name(item):
    if not isinstance(item, dict):
        return str(item)
    for key in ("name", "gather", "id", "rule", "title"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return "unknown"


def item_status(item):
    if not isinstance(item, dict):
        return "unknown"
    for key in ("status", "state", "result", "outcome"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value).lower()
    if item.get("ok") is True:
        return "ok"
    if item.get("ok") is False:
        return "failed"
    return "unknown"


def item_error_count(item):
    if not isinstance(item, dict):
        return 0
    for key in ("error_count", "errors", "failures"):
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)
    return 0


def item_panic_count(item):
    if not isinstance(item, dict):
        return 0
    value = item.get("panics")
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return len(value)
    return 0


def item_duration(item):
    if not isinstance(item, dict):
        return ""
    for key in ("duration", "duration_ms", "elapsed", "time"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_insights_archive.py <insights-archive-root>"}))
        return 1

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": "insights archive root not found", "path": str(root)}))
        return 2

    gathers_path = next(iter(sorted(root.rglob("gathers.json"))), None)
    gathers_data = load_json(gathers_path) if gathers_path else None
    gather_items = normalize_gather_items(gathers_data)
    archive_files = sorted(
        [
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.name != "gathers.json"
            and (
                path.suffix.lower() in {".tar", ".tgz", ".gz", ".zip"}
                or path.parent.name == "archives"
            )
        ]
    )

    normalized = []
    for item in gather_items:
        normalized.append(
            {
                "name": item_name(item),
                "status": item_status(item),
                "duration": item_duration(item),
                "error_count": item_error_count(item),
                "panic_count": item_panic_count(item),
            }
        )

    failed_items = [
        item
        for item in normalized
        if item["status"] in {"failed", "error", "warn", "warning"} or item["error_count"] > 0 or item["panic_count"] > 0
    ]
    present = bool(gathers_path or archive_files)
    payload = {
        "summary": {
            "present": present,
            "path": str(root),
            "gathers_path": str(gathers_path) if gathers_path else "",
            "archive_count": len(archive_files),
            "gather_count": len(normalized),
            "failed_gather_count": len(failed_items),
            "error_count": sum(item["error_count"] for item in normalized),
            "panic_count": sum(item["panic_count"] for item in normalized),
            "sample_archives": [str(path.relative_to(root)) for path in archive_files[:10]],
            "verdict": (
                "not-collected"
                if not present
                else ("review-required" if failed_items else "supported")
            ),
        },
        "gathers": normalized[:50],
        "findings": [
            {
                "severity": "warning",
                "area": "insights-archive",
                "detail": f"Insights gather {item['name']} status={item['status']} errors={item['error_count']} panics={item['panic_count']}",
            }
            for item in failed_items[:15]
        ],
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
