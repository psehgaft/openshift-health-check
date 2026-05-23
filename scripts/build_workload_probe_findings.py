#!/usr/bin/env python3
"""Build workload probe coverage findings."""

import json
import re
import sys


OPERATOR_MARKER_RE = re.compile(r"^(operators\.coreos\.com/|olm\.|operatorframework\.io/)")


def get_path(data, *path, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def is_user_namespace(namespace, exclude_regex):
    if not namespace:
        return True
    if not exclude_regex:
        return True
    return re.match(exclude_regex, namespace) is None


def has_operator_marker(metadata):
    labels = (metadata.get("labels") or {}) if isinstance(metadata, dict) else {}
    annotations = (metadata.get("annotations") or {}) if isinstance(metadata, dict) else {}
    for key in list(labels) + list(annotations):
        if OPERATOR_MARKER_RE.match(str(key or "")):
            return True
    return False


def is_operator_managed(workload, operator_namespaces):
    metadata = workload.get("metadata") or {}
    labels = metadata.get("labels") or {}
    annotations = metadata.get("annotations") or {}
    namespace = str(metadata.get("namespace") or "")
    name = str(metadata.get("name") or "")
    managed_by = str(
        labels.get("app.kubernetes.io/managed-by", annotations.get("app.kubernetes.io/managed-by", ""))
        or ""
    ).lower()
    workload_name_lower = name.lower()
    app_name_lower = str(labels.get("app.kubernetes.io/name", "") or "").lower()
    owner_refs = metadata.get("ownerReferences") or []
    has_csv_owner = any((ref or {}).get("kind") == "ClusterServiceVersion" for ref in owner_refs)

    return (
        namespace in operator_namespaces
        or has_operator_marker(metadata)
        or managed_by in {"olm", "operator-lifecycle-manager"}
        or "operator" in managed_by
        or "-operator" in workload_name_lower
        or "operator-" in workload_name_lower
        or "controller-manager" in workload_name_lower
        or "-operator" in app_name_lower
        or "operator-" in app_name_lower
        or has_csv_owner
    )


def missing_container_names(containers, probe_name):
    result = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        if probe_name not in container:
            result.append(container.get("name"))
    return result


def build_probe_findings_for_kind(items, kind, exclude_regex, operator_namespaces):
    findings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") or {}
        namespace = str(metadata.get("namespace") or "")
        name = str(metadata.get("name") or "")
        containers = get_path(item, "spec", "template", "spec", "containers", default=[]) or []
        if not is_user_namespace(namespace, exclude_regex):
            continue
        if is_operator_managed(item, operator_namespaces):
            continue
        if not containers:
            continue

        for issue, probe_name in (
            ("missing-liveness-probe", "livenessProbe"),
            ("missing-readiness-probe", "readinessProbe"),
            ("missing-startup-probe", "startupProbe"),
        ):
            missing = missing_container_names(containers, probe_name)
            if missing:
                findings.append(
                    {
                        "kind": kind,
                        "namespace": namespace,
                        "name": name,
                        "issue": issue,
                        "containers": missing,
                        "detail": ", ".join(str(value) for value in missing),
                    }
                )
    return findings


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    graph = data.get("analysis_graph") or {}
    exclude_regex = str(data.get("user_namespaces_exclude_regex") or "")
    operator_namespaces = set(data.get("operator_managed_namespace_names") or [])
    existing = data.get("workload_probe_findings") or []
    findings = list(existing)
    findings.extend(
        build_probe_findings_for_kind(
            get_path(graph, "deployments", "items", default=[]) or [],
            "Deployment",
            exclude_regex,
            operator_namespaces,
        )
    )
    findings.extend(
        build_probe_findings_for_kind(
            get_path(graph, "statefulsets", "items", default=[]) or [],
            "StatefulSet",
            exclude_regex,
            operator_namespaces,
        )
    )
    findings.extend(
        build_probe_findings_for_kind(
            get_path(graph, "daemonsets", "items", default=[]) or [],
            "DaemonSet",
            exclude_regex,
            operator_namespaces,
        )
    )

    print(json.dumps({"workload_probe_findings": findings}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
