#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

import analyze_evidence_hygiene as hygiene


PLACEHOLDER_TEMPLATE = """REDACTED FILE
original_relative_path: {relative_path}
category: {category}
reason: {reason}
redaction_action: replaced-with-placeholder
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Write redaction manifest and optional sanitized bundle.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--manifest-path", required=True)
    parser.add_argument("--redacted-root", default="")
    return parser.parse_args()


def write_manifest(source_root: Path, manifest_path: Path, payload):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source_root": str(source_root),
        "summary": payload.get("summary", {}),
        "findings": payload.get("findings", []),
        "sensitive_candidates": payload.get("sensitive_candidates", []),
        "redaction_guidance": payload.get("redaction_guidance", []),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_redacted_bundle(source_root: Path, redacted_root: Path, payload):
    sensitive_map = {
        item["relative_path"]: item for item in payload.get("sensitive_candidates", [])
    }
    if redacted_root.exists():
        shutil.rmtree(redacted_root)
    redacted_root.mkdir(parents=True, exist_ok=True)
    copied_files = 0
    redacted_files = 0

    for path in source_root.rglob("*"):
        relative_path = path.relative_to(source_root)
        destination = redacted_root / relative_path
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if not path.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        candidate = sensitive_map.get(str(relative_path))
        if candidate:
            destination.write_text(
                PLACEHOLDER_TEMPLATE.format(
                    relative_path=candidate["relative_path"],
                    category=candidate["category"],
                    reason=candidate["reason"],
                ),
                encoding="utf-8",
            )
            redacted_files += 1
        else:
            shutil.copy2(path, destination)
            copied_files += 1

    return {
        "path": str(redacted_root),
        "copied_file_count": copied_files,
        "redacted_file_count": redacted_files,
    }


def main():
    args = parse_args()
    source_root = Path(args.source_root).expanduser().resolve()
    manifest_path = Path(args.manifest_path).expanduser().resolve()
    redacted_root = Path(args.redacted_root).expanduser().resolve() if args.redacted_root else None

    payload = hygiene.scan_roots([("case-bundle", source_root)])
    write_manifest(source_root, manifest_path, payload)

    result = {
        "manifest_path": str(manifest_path),
        "manifest_written": True,
        "redacted_bundle_written": False,
    }
    if redacted_root is not None:
        result["redacted_bundle"] = write_redacted_bundle(source_root, redacted_root, payload)
        result["redacted_bundle_written"] = True

    print(json.dumps(result))


if __name__ == "__main__":
    main()
