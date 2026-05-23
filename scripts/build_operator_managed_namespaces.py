#!/usr/bin/env python3
import json
import re
import sys


OPERATOR_MARKER_RE = re.compile(r"^(operators\.coreos\.com/|olm\.|operatorframework\.io/)")
OPERATOR_NAMESPACE_SUFFIX_RE = re.compile(r".*-(operator|operators)$")


def metadata(item):
    return item.get("metadata") if isinstance(item, dict) else {}


def spec(item):
    return item.get("spec") if isinstance(item, dict) else {}


def labels_and_annotations(item):
    meta = metadata(item) or {}
    labels = meta.get("labels") if isinstance(meta.get("labels"), dict) else {}
    annotations = meta.get("annotations") if isinstance(meta.get("annotations"), dict) else {}
    return labels, annotations


def has_operator_marker_keys(labels, annotations):
    for source in (labels or {}, annotations or {}):
        for key in source.keys():
            if OPERATOR_MARKER_RE.match(str(key)):
                return True
    return False


def lower_text(value):
    return str(value or "").lower()


def owner_refs(item):
    refs = (metadata(item) or {}).get("ownerReferences") or []
    return refs if isinstance(refs, list) else []


def has_csv_owner(item):
    return any(isinstance(ref, dict) and ref.get("kind") == "ClusterServiceVersion" for ref in owner_refs(item))


def append_unique(target, value):
    text = str(value or "")
    if text and text not in target:
        target.append(text)


def namespace_is_operator_managed(item):
    meta = metadata(item) or {}
    ns_name = str(meta.get("name") or "")
    labels, annotations = labels_and_annotations(item)
    managed_by_value = lower_text(labels.get("app.kubernetes.io/managed-by", annotations.get("app.kubernetes.io/managed-by", "")))
    ns_lower = ns_name.lower()
    return bool(
        ns_name
        and (
            has_operator_marker_keys(labels, annotations)
            or managed_by_value in {"olm", "operator-lifecycle-manager"}
            or "operator" in managed_by_value
            or ns_lower == "operators"
            or OPERATOR_NAMESPACE_SUFFIX_RE.search(ns_lower)
        )
    )


def workload_is_operator_managed(item):
    meta = metadata(item) or {}
    ns_name = str(meta.get("namespace") or "")
    labels, annotations = labels_and_annotations(item)
    workload_name_lower = lower_text(meta.get("name"))
    managed_by_value = lower_text(labels.get("app.kubernetes.io/managed-by", annotations.get("app.kubernetes.io/managed-by", "")))
    app_name_lower = lower_text(labels.get("app.kubernetes.io/name", ""))
    return bool(
        ns_name
        and (
            has_operator_marker_keys(labels, annotations)
            or managed_by_value in {"olm", "operator-lifecycle-manager"}
            or "operator" in managed_by_value
            or "-operator" in workload_name_lower
            or "operator-" in workload_name_lower
            or "controller-manager" in workload_name_lower
            or "-operator" in app_name_lower
            or "operator-" in app_name_lower
            or has_csv_owner(item)
        )
    )


def build(data):
    namespaces = []

    for item in data.get("namespaces") or []:
        if namespace_is_operator_managed(item):
            append_unique(namespaces, (metadata(item) or {}).get("name"))

    for key in ("deployments", "statefulsets", "daemonsets", "deploymentconfigs"):
        for item in data.get(key) or []:
            if workload_is_operator_managed(item):
                append_unique(namespaces, (metadata(item) or {}).get("namespace"))

    for item in data.get("subscriptions") or []:
        append_unique(namespaces, (metadata(item) or {}).get("namespace"))

    return {"operator_managed_namespace_names": namespaces}


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_operator_managed_namespaces.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
