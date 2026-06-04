#!/usr/bin/env python3
import json
import sys
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))
from extract_offline_resources import RESOURCE_KEYS, RESOURCE_STEM_ALIASES  # noqa: E402


def load_json(path_str):
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def nested_get(data, dotted_path):
    current = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def conditions_of(data):
    if not isinstance(data, dict):
        return []
    return (((data.get("status") or {}).get("conditions")) or [])


def is_sufficient(payload, rule):
    if not payload:
        return False
    mode = str((rule or {}).get("mode") or "auto").strip().lower()
    if mode == "field_nonempty":
        value = nested_get(payload, str(rule.get("field_path") or ""))
        return bool(str(value or "").strip())
    if mode == "condition_present":
        expected = str(rule.get("condition_type") or "").strip()
        return any(str(item.get("type") or "") == expected for item in conditions_of(payload))
    if isinstance(payload, dict) and "items" in payload:
        return True
    if isinstance(payload, dict):
        return any(key in payload for key in ("kind", "apiVersion", "metadata", "spec", "status"))
    return bool(payload)


def build_argv(resource_key, cluster_scoped):
    expected_kind, expected_name, expected_namespace = RESOURCE_KEYS[resource_key]
    resource_stem = RESOURCE_STEM_ALIASES.get(resource_key, resource_key)
    argv = ["oc", "get", resource_stem]
    if expected_name:
        argv.append(expected_name)
        if expected_namespace:
            argv.extend(["-n", expected_namespace])
    elif not cluster_scoped:
        argv.append("-A")
    argv.extend(["-o", "json", "--ignore-not-found"])
    return argv


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_live_api_fallback_plan.py <manifest.yml> <context.json>")

    manifest = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
    config = manifest.get("openshift_live_api_fallback") or {}
    context = load_json(sys.argv[2])

    graph = context.get("collected_resource_graph") or {}
    selector_active = bool(context.get("selector_active"))
    selected_postures = context.get("selected_postures") or []
    selected_capabilities = context.get("selected_capabilities") or []
    enabled_postures = context.get("enabled_postures") or []

    posture_scope = selected_postures if selector_active else enabled_postures
    capability_scope = selected_capabilities

    posture_resources = config.get("posture_resources") or {}
    capability_resources = config.get("capability_resources") or {}
    cluster_scoped = set(config.get("cluster_scoped_resource_keys") or [])
    sufficiency_rules = config.get("sufficiency_rules") or {}

    candidate_keys = []
    for posture_key in posture_scope:
        candidate_keys.extend(posture_resources.get(posture_key) or [])
    for capability_key in capability_scope:
        candidate_keys.extend(capability_resources.get(capability_key) or [])

    planned = []
    for resource_key in sorted(set(candidate_keys)):
        if resource_key not in RESOURCE_KEYS:
            continue
        payload = graph.get(resource_key)
        rule = sufficiency_rules.get(resource_key) or {}
        if is_sufficient(payload, rule):
            continue
        planned.append(
            {
                "key": resource_key,
                "argv": build_argv(resource_key, resource_key in cluster_scoped),
                "reason": str(rule.get("mode") or "missing_or_empty"),
            }
        )

    print(json.dumps({"items": planned}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
