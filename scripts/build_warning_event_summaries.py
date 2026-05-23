#!/usr/bin/env python3
import json
import sys


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def nested_get(data, path, default=None):
    value = data
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return value if value is not None else default


def event_timestamp(item):
    for path in (["lastTimestamp"], ["eventTime"], ["metadata", "creationTimestamp"]):
        value = nested_get(item, path, "")
        if value not in (None, ""):
            return str(value)
    return ""


def build(data):
    events = as_list(data.get("events"))
    try:
        limit = int(data.get("warning_event_limit") or 0)
    except (TypeError, ValueError):
        limit = 0

    reason_counts = {}
    items = []
    for event in events:
        if not isinstance(event, dict):
            continue
        reason = str(event.get("reason") or "Unknown")
        reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
        enriched = dict(event)
        enriched["_sort_timestamp"] = event_timestamp(event)
        items.append(enriched)

    sorted_items = sorted(items, key=lambda item: str(item.get("_sort_timestamp") or ""), reverse=True)
    return {
        "warning_event_reason_counts": reason_counts,
        "warning_event_items": sorted_items,
        "recent_warning_events": sorted_items[:limit] if limit > 0 else [],
    }


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_warning_event_summaries.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(as_dict(data))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
