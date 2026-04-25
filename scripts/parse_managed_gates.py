#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def load_structured(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
        return yaml.safe_load(text)
    return None


def normalize_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "gates", "data", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def normalize_gate(item):
    status = str(
        item.get("status")
        or item.get("state")
        or item.get("result")
        or item.get("verdict")
        or "unknown"
    ).strip()
    category = str(item.get("category") or item.get("type") or item.get("group") or "general").strip()
    return {
        "id": str(item.get("id") or item.get("name") or item.get("gate") or "unknown").strip(),
        "status": status.lower(),
        "category": category.lower(),
        "reason": str(item.get("reason") or item.get("message") or item.get("detail") or "").strip(),
        "cluster": str(item.get("cluster") or item.get("cluster_id") or item.get("cluster_name") or "").strip(),
        "raw": item,
    }


def parse_text(text: str):
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "|" in stripped:
            parts = [part.strip() for part in stripped.split("|") if part.strip()]
            if len(parts) >= 2:
                items.append(
                    {
                        "id": parts[0],
                        "status": parts[1].lower(),
                        "category": parts[2].lower() if len(parts) > 2 else "general",
                        "reason": parts[3] if len(parts) > 3 else "",
                        "cluster": "",
                        "raw": {"line": stripped},
                    }
                )
                continue
        match = re.match(r"^(?P<id>[A-Za-z0-9._:/-]+)\s+(?P<status>allowed|blocked|pending|warning|warn|ok|pass|passed|fail|failed|unknown)\b(.*)$", stripped, re.IGNORECASE)
        if match:
            items.append(
                {
                    "id": match.group("id"),
                    "status": match.group("status").lower(),
                    "category": "general",
                    "reason": stripped[match.end("status"):].strip(" -:"),
                    "cluster": "",
                    "raw": {"line": stripped},
                }
            )
    return items


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: parse_managed_gates.py <managed-gates-path>"}))
        return 1

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists() or not path.is_file():
        print(json.dumps({"error": "managed gates path not found", "path": str(path)}))
        return 2

    items = []
    try:
        structured = load_structured(path)
    except Exception:
        structured = None

    if structured is not None:
        items = [normalize_gate(item) for item in normalize_items(structured) if isinstance(item, dict)]
    if not items:
        text = path.read_text(encoding="utf-8")
        items = parse_text(text)

    blocked_count = sum(1 for item in items if item["status"] in {"blocked", "fail", "failed"})
    pending_count = sum(1 for item in items if item["status"] in {"pending"})
    warning_count = sum(1 for item in items if item["status"] in {"warning", "warn"})
    allowed_count = sum(1 for item in items if item["status"] in {"allowed", "ok", "pass", "passed"})
    categories = {}
    for item in items:
        categories[item["category"]] = categories.get(item["category"], 0) + 1

    payload = {
        "summary": {
            "path": str(path),
            "format": path.suffix.lower().lstrip(".") or "text",
            "item_count": len(items),
            "blocked_count": blocked_count,
            "pending_count": pending_count,
            "warning_count": warning_count,
            "allowed_count": allowed_count,
            "top_categories": [{"name": key, "count": value} for key, value in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))[:10]],
        },
        "items": items,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
