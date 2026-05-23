#!/usr/bin/env python3
import json
import re
import sys


SYSTEM_CRD_GROUP_RE = re.compile(
    r"^(openshift\.io|operator\.openshift\.io|config\.openshift\.io|machine\.openshift\.io|"
    r"monitoring\.coreos\.com|apiextensions\.k8s\.io|rbac\.authorization\.k8s\.io|"
    r"authorization\.openshift\.io|route\.openshift\.io|image\.openshift\.io|"
    r"build\.openshift\.io|apps\.openshift\.io|project\.openshift\.io|"
    r"template\.openshift\.io|k8s\.io)$"
)


def nested_get(data, path, default=None):
    value = data
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return value if value is not None else default


def int_value(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_targets(crds):
    targets = []
    for item in crds or []:
        spec = item.get("spec") if isinstance(item, dict) else {}
        names = spec.get("names") if isinstance(spec, dict) else {}
        if not isinstance(spec, dict) or not isinstance(names, dict):
            continue
        if "group" not in spec:
            continue
        if str(spec.get("scope") or "Namespaced") != "Namespaced":
            continue
        targets.append(
            {
                "name": str(nested_get(item, ["metadata", "name"], "") or ""),
                "group": str(spec.get("group") or ""),
                "plural": str(names.get("plural") or ""),
            }
        )
    return targets


def build_likely_unused_crds(results):
    findings = []
    for item in results or []:
        group = str(item.get("group") or "")
        count = int_value(item.get("count"), 0)
        rc = int_value(item.get("rc"), 1)
        if rc == 0 and count == 0 and not SYSTEM_CRD_GROUP_RE.match(group):
            findings.append(
                {
                    "name": str(item.get("name") or ""),
                    "group": group,
                    "plural": str(item.get("plural") or ""),
                    "count": count,
                }
            )
    return findings


def build(data):
    return {
        "namespaced_crd_count_targets": build_targets(data.get("crds") or []),
        "likely_unused_crds": build_likely_unused_crds(data.get("results") or []),
    }


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_crd_usage_facts.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
