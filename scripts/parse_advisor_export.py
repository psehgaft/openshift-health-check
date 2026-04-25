#!/usr/bin/env python3
import json
import sys
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def load_structured(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    if suffix in {".yaml", ".yml"} and yaml is not None:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    return None


def normalize_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "recommendations", "reports", "hits", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def item_value(item, keys):
    if not isinstance(item, dict):
        return ""
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def normalize_item(item):
    if not isinstance(item, dict):
        return {"title": str(item), "severity": "unknown", "category": "unknown"}
    return {
        "id": item_value(item, ("id", "rule_id", "rule", "recommendation_id")),
        "title": item_value(item, ("title", "description", "name", "rule", "recommendation")),
        "severity": item_value(item, ("severity", "total_risk", "impact", "status")).lower() or "unknown",
        "category": item_value(item, ("category", "service", "topic", "type")).lower() or "unknown",
        "resolution": item_value(item, ("resolution", "summary", "details")),
        "url": item_value(item, ("url", "link", "permalink")),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_advisor_export.py <advisor-export-path>"}))
        return 1

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists() or not path.is_file():
        print(json.dumps({"error": "advisor export path not found", "path": str(path)}))
        return 2

    data = load_structured(path)
    if data is None:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        items = [{"title": line} for line in lines[:200]]
    else:
        items = normalize_list(data)

    normalized_items = [normalize_item(item) for item in items]
    statuses = [item.get("severity", "unknown") for item in normalized_items]
    categories = {}
    for item in normalized_items:
        category = item.get("category", "unknown") or "unknown"
        categories[category] = categories.get(category, 0) + 1
    payload = {
        "summary": {
            "path": str(path),
            "item_count": len(normalized_items),
            "critical_count": sum(1 for s in statuses if "critical" in s),
            "high_count": sum(1 for s in statuses if "high" in s),
            "moderate_count": sum(1 for s in statuses if "moderate" in s or "medium" in s),
            "low_count": sum(1 for s in statuses if "low" in s),
            "top_categories": [
                {"name": key, "count": value}
                for key, value in sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:10]
            ],
        },
        "items": normalized_items[:50],
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
