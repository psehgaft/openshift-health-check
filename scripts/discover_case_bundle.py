#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def first_match(root: Path, predicate, want_dir=None):
    matches = []
    if (want_dir is None or (want_dir is True and root.is_dir()) or (want_dir is False and root.is_file())) and predicate(root):
        matches.append(root)
    for path in root.rglob("*"):
        if want_dir is True and not path.is_dir():
            continue
        if want_dir is False and not path.is_file():
            continue
        if predicate(path):
            matches.append(path)
    return str(sorted(matches)[0]) if matches else ""


def all_matches(root: Path, predicate, want_dir=None):
    matches = []
    if (want_dir is None or (want_dir is True and root.is_dir()) or (want_dir is False and root.is_file())) and predicate(root):
        matches.append(str(root))
    for path in root.rglob("*"):
        if want_dir is True and not path.is_dir():
            continue
        if want_dir is False and not path.is_file():
            continue
        if predicate(path):
            matches.append(str(path))
    return sorted(matches)


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: discover_case_bundle.py <case-bundle-path>"}))
        return 1

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": "case bundle path not found", "path": str(root)}))
        return 2

    payload = {
        "must_gather_path": first_match(root, lambda p: p.name.startswith("must-gather.local") or p.name == "must-gather", want_dir=True),
        "cluster_compare_path": first_match(root, lambda p: "cluster-compare" in p.name and p.suffix.lower() in {".json", ".yaml", ".yml", ".txt"}, want_dir=False),
        "managed_gates_path": first_match(root, lambda p: "managed-gates" in str(p).lower().replace("_", "-") and p.suffix.lower() in {".json", ".yaml", ".yml", ".txt"}, want_dir=False),
        "inspect_path": first_match(root, lambda p: p.is_dir() and p.name.startswith("inspect"), want_dir=True),
        "advisor_export_path": first_match(root, lambda p: "advisor" in p.name and p.suffix.lower() == ".json", want_dir=False),
        "insights_archive_path": first_match(
            root,
            lambda p: p.is_dir() and (
                p.name == "insights-archive"
                or p.name.startswith("insights-archive")
                or p.name == "insights_archive"
                or p.name.startswith("insights_archive")
            ),
            want_dir=True,
        ),
        "sosreport_paths": all_matches(
            root,
            lambda p: (
                p.name.startswith("sosreport")
                or "oc-debug-node-sosreport" in str(p.parent).lower().replace("\\", "/")
            ),
            want_dir=True,
        ),
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
