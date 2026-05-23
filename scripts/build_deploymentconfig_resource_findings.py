#!/usr/bin/env python3
import json
import re
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


def nested_defined(data, path):
    value = data
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return False
        value = value.get(part)
    return True


def text(value):
    return str(value or "")


def container_names_without(containers, path):
    names = []
    for container in as_list(containers):
        if not nested_defined(container, path):
            names.append(nested_get(container, ["name"], None))
    return names


def build(data):
    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    findings = []

    for item in as_list(data.get("deploymentconfigs")):
        namespace = text(nested_get(item, ["metadata", "namespace"], ""))
        if exclude_re.match(namespace):
            continue

        pod_spec = as_dict(nested_get(item, ["spec", "template", "spec"], {}))
        containers = as_list(pod_spec.get("containers")) + as_list(pod_spec.get("initContainers"))
        if not containers:
            continue

        containers_without_requests = container_names_without(containers, ["resources", "requests"])
        containers_without_limits = container_names_without(containers, ["resources", "limits"])
        common = {
            "kind": "DeploymentConfig",
            "namespace": namespace,
            "name": text(nested_get(item, ["metadata", "name"], "unknown") or "unknown"),
        }

        if containers_without_requests:
            entry = dict(common)
            entry.update({
                "issue": "workload-missing-resource-requests",
                "detail": ", ".join(text(value) for value in containers_without_requests),
            })
            findings.append(entry)

        if containers_without_limits:
            entry = dict(common)
            entry.update({
                "issue": "workload-missing-resource-limits",
                "detail": ", ".join(text(value) for value in containers_without_limits),
            })
            findings.append(entry)

    return {"deploymentconfig_resource_findings": findings}


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_deploymentconfig_resource_findings.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
