#!/usr/bin/env python3
from __future__ import annotations


def _normalize_str_map(raw):
    return {
        str(key): str(value)
        for key, value in (raw or {}).items()
        if key not in (None, "") and value not in (None, "")
    }


def metadata_of(obj):
    return (obj or {}).get("metadata", {}) or {}


def labels_of(obj):
    return _normalize_str_map(metadata_of(obj).get("labels"))


def annotations_of(obj):
    return _normalize_str_map(metadata_of(obj).get("annotations"))


def namespace_of(obj):
    return str(metadata_of(obj).get("namespace") or "").strip()


def _name_looks_operator_managed(value):
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(
        marker in text
        for marker in [
            "-operator",
            "operator-",
            "controller-manager",
            "gitlab-runner",
            "github-runner",
            "actions-runner",
            "azure-pipelines-agent",
            "azp-agent",
            "jenkins-agent",
            "jenkins-inbound-agent",
            "tekton-task",
            "buildkite-agent",
        ]
    )


def namespace_name_looks_operator_managed(namespace_name):
    text = str(namespace_name or "").strip().lower()
    if not text:
        return False
    return text == "operators" or text.endswith("-operator") or text.endswith("-operators")


def _has_operator_marker_keys(labels, annotations):
    all_keys = list((labels or {}).keys()) + list((annotations or {}).keys())
    return any(
        key.startswith("operators.coreos.com/")
        or key.startswith("olm.")
        or key.startswith("operatorframework.io/")
        for key in all_keys
    )


def _managed_by_looks_operator(labels, annotations):
    managed_by = str(
        (labels or {}).get(
            "app.kubernetes.io/managed-by",
            (annotations or {}).get("app.kubernetes.io/managed-by", ""),
        )
        or ""
    ).strip().lower()
    return managed_by in {"olm", "operator-lifecycle-manager"} or "operator" in managed_by


def is_operator_managed_object(obj, operator_managed_namespaces=None):
    operator_managed_namespaces = set(operator_managed_namespaces or [])
    metadata = metadata_of(obj)
    labels = labels_of(obj)
    annotations = annotations_of(obj)
    namespace_name = namespace_of(obj)
    object_name = str(metadata.get("name") or "").strip()
    service_account_name = str(((obj or {}).get("spec") or {}).get("serviceAccountName") or "").strip()
    owner_refs = metadata.get("ownerReferences") or []

    if namespace_name in operator_managed_namespaces:
        return True
    if namespace_name_looks_operator_managed(namespace_name):
        return True
    if _has_operator_marker_keys(labels, annotations):
        return True
    if _managed_by_looks_operator(labels, annotations):
        return True
    if any(str((ref or {}).get("kind") or "") == "ClusterServiceVersion" for ref in owner_refs):
        return True
    if _name_looks_operator_managed(object_name):
        return True
    if _name_looks_operator_managed(labels.get("app.kubernetes.io/name", "")):
        return True
    if _name_looks_operator_managed(labels.get("app", "")):
        return True
    if _name_looks_operator_managed(service_account_name):
        return True
    return False
