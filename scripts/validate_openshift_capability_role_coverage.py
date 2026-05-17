#!/usr/bin/env python3
"""Validate OpenShift capability role coverage against the profile and playbook."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


EXPECTED_PLAYBOOK_WIRING_COUNT = 4
ROLE_PREFIX = "capability_"
IGNORED_ROLE_DIRS = {
    "capability_artifact_from_builder",
    "capability_enabled_day2_sections",
}


def load_profile_capabilities(profile_path: Path) -> list[str]:
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    profile = data.get("cluster_health_profile", {})
    capabilities = profile.get("capabilities", {})
    if not isinstance(capabilities, dict):
      raise SystemExit(f"{profile_path}: cluster_health_profile.capabilities must be a mapping")
    return list(capabilities.keys())


def load_role_backed_capabilities(roles_dir: Path) -> list[str]:
    keys: list[str] = []
    for path in sorted(roles_dir.glob(f"{ROLE_PREFIX}*")):
        if not path.is_dir() or path.name in IGNORED_ROLE_DIRS:
            continue
        keys.append(path.name.removeprefix(ROLE_PREFIX))
    return keys


def load_playbook_wiring_counts(playbook_path: Path) -> dict[str, int]:
    text = playbook_path.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for match in re.finditer(r"name:\s+capability_([a-z0-9_]+)", text):
        key = match.group(1)
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_path", type=Path)
    parser.add_argument("roles_dir", type=Path)
    parser.add_argument("playbook_path", type=Path)
    args = parser.parse_args()

    profile_keys = load_profile_capabilities(args.profile_path)
    role_keys = load_role_backed_capabilities(args.roles_dir)
    wiring_counts = load_playbook_wiring_counts(args.playbook_path)

    profile_set = set(profile_keys)
    role_set = set(role_keys)
    wired_set = set(wiring_counts)

    catalog_only = sorted(profile_set - role_set)
    missing_from_profile = sorted(role_set - profile_set)
    unwired_role_backed = sorted(key for key in role_keys if wiring_counts.get(key, 0) == 0)
    short_wired_role_backed = sorted(
        key
        for key in role_keys
        if 0 < wiring_counts.get(key, 0) < EXPECTED_PLAYBOOK_WIRING_COUNT
    )
    wired_without_role = sorted(key for key in wired_set if key not in role_set)
    wired_without_profile = sorted(key for key in wired_set if key not in profile_set)

    errors: list[str] = []
    if missing_from_profile:
        errors.append(
            "Role-backed capabilities missing from the OpenShift profile: "
            + ", ".join(missing_from_profile)
        )
    if unwired_role_backed:
        errors.append(
            "Role-backed capabilities missing playbook wiring: "
            + ", ".join(unwired_role_backed)
        )
    if short_wired_role_backed:
        errors.append(
            "Role-backed capabilities missing one or more OpenShift wiring paths: "
            + ", ".join(
                f"{key}({wiring_counts.get(key, 0)}/{EXPECTED_PLAYBOOK_WIRING_COUNT})"
                for key in short_wired_role_backed
            )
        )
    if wired_without_role:
        errors.append(
            "Capabilities wired in the OpenShift playbook without dedicated capability roles: "
            + ", ".join(wired_without_role)
        )
    if wired_without_profile:
        errors.append(
            "Capabilities wired in the OpenShift playbook but missing from the OpenShift profile: "
            + ", ".join(wired_without_profile)
        )

    summary = (
        f"{args.profile_path}: capability role coverage ok "
        f"(profile={len(profile_keys)} role_backed={len(role_keys)} catalog_only={len(catalog_only)})"
    )

    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        print(summary, file=sys.stderr)
        return 1

    print(summary)
    if catalog_only:
        print("catalog_only=" + ",".join(catalog_only))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
