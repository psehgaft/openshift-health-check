#!/usr/bin/env python3
import json
import re
import sys
from collections import defaultdict

from workload_noise_filters import is_operator_managed_object


WORKLOAD_OWNER_LABEL_KEYS = [
    "team",
    "owner",
    "owner.team",
    "team-name",
    "team_name",
    "app.kubernetes.io/team",
    "app.kubernetes.io/owner",
    "ops.team",
    "ops.owner",
]
COST_LABEL_KEYS = [
    "cost-center",
    "cost_center",
    "costcenter",
    "billing-code",
    "billing_code",
    "chargeback",
    "chargeback-code",
    "chargeback_code",
    "business-unit",
    "business_unit",
    "department",
]


def namespace_of(obj):
    return str(((obj.get("metadata") or {}).get("namespace")) or "").strip()


def destination_namespace_of(app):
    return str(((((app.get("spec") or {}).get("destination")) or {}).get("namespace")) or "").strip()


def labels_of(obj):
    return ((obj.get("metadata") or {}).get("labels")) or {}


def annotations_of(obj):
    return ((obj.get("metadata") or {}).get("annotations")) or {}


def normalize_slug(text):
    return re.sub(r"[^a-zA-Z0-9-]+", "-", str(text or "").strip()).strip("-").lower()


def normalize_token(text):
    return re.sub(r"[^a-zA-Z0-9-]+", "-", str(text or "").strip()).strip("-")


def first_present_value(keys, labels, annotations, related_objects):
    for key in keys:
        value = str(labels.get(key, "")).strip()
        if value:
            return value
        value = str(annotations.get(key, "")).strip()
        if value:
            return value
    for obj in related_objects:
        obj_labels = labels_of(obj)
        obj_annotations = annotations_of(obj)
        for key in keys:
            value = str(obj_labels.get(key, "")).strip()
            if value:
                return value
            value = str(obj_annotations.get(key, "")).strip()
            if value:
                return value
    return ""


def present_owner_keys(labels):
    keys = []
    for key in WORKLOAD_OWNER_LABEL_KEYS:
        if str(labels.get(key, "")).strip():
            keys.append(key)
    return keys


def managed_by_hint(labels, annotations, related_objects, owner_value):
    for key in ["app.kubernetes.io/managed-by"]:
        value = str(labels.get(key, "")).strip() or str(annotations.get(key, "")).strip()
        if value:
            return value
    for obj in related_objects:
        obj_labels = labels_of(obj)
        obj_annotations = annotations_of(obj)
        for key in ["app.kubernetes.io/managed-by"]:
            value = str(obj_labels.get(key, "")).strip() or str(obj_annotations.get(key, "")).strip()
            if value:
                return value
    return owner_value or "platform-team"


def owner_email_hint(owner_value, ns_name):
    owner_slug = normalize_slug(owner_value or ns_name) or "platform-team"
    return f"{owner_slug}@example.com"


def owner_contact_hint(owner_value, workload_name_hint):
    contact_slug = normalize_slug(owner_value or workload_name_hint) or "platform-team"
    return f"#team-{contact_slug}"


def cost_center_hint(namespace_cost_value, ns_name):
    if namespace_cost_value:
        return namespace_cost_value
    return f"cc-{normalize_token(ns_name).upper() or 'PLATFORM'}"


def business_unit_hint(namespace_business_unit_value, ns_name):
    if namespace_business_unit_value:
        return namespace_business_unit_value
    return re.sub(r"^([^-]+).*", r"\1", ns_name).upper() or "PLATFORM"


def description_hint(workload_name_hint, ns_name):
    return f"Workload {workload_name_hint} in namespace {ns_name}"


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_regex = str(data.get("user_namespaces_exclude_regex") or "")
    operator_managed_namespace_names = data.get("operator_managed_namespace_names") or []
    namespace_map = {}
    namespace_objects = defaultdict(list)

    for namespace_obj in data.get("namespaces") or []:
        ns_name = str((((namespace_obj.get("metadata") or {}).get("name")) or "")).strip()
        if ns_name:
            namespace_map[ns_name] = namespace_obj

    for collection_name in [
        "deployments",
        "statefulsets",
        "daemonsets",
        "deploymentconfigs",
        "serviceaccounts",
    ]:
        for obj in data.get(collection_name) or []:
            ns = namespace_of(obj)
            if ns:
                namespace_objects[ns].append(obj)

    for app in data.get("gitops_applications") or []:
        ns = destination_namespace_of(app)
        if ns:
            namespace_objects[ns].append(app)

    findings = []
    for pod in data.get("pods") or []:
        ns_name = namespace_of(pod)
        if not ns_name or re.match(exclude_regex, ns_name):
            continue
        if is_operator_managed_object(pod, operator_managed_namespace_names):
            continue

        pod_phase = str((((pod.get("status") or {}).get("phase")) or "Unknown")).strip()
        if pod_phase in {"Succeeded", "Completed"}:
            continue

        labels = labels_of(pod)
        present_keys = present_owner_keys(labels)
        if present_keys:
            continue

        pod_name = str((((pod.get("metadata") or {}).get("name")) or "unknown")).strip() or "unknown"
        workload_name_hint = str(labels.get("app.kubernetes.io/name", labels.get("app", pod_name))).strip() or pod_name

        namespace_obj = namespace_map.get(ns_name) or {}
        namespace_labels = labels_of(namespace_obj)
        namespace_annotations = annotations_of(namespace_obj)
        related_objects = namespace_objects.get(ns_name, [])

        namespace_owner_value = (
            first_present_value(
                WORKLOAD_OWNER_LABEL_KEYS,
                namespace_labels,
                namespace_annotations,
                related_objects,
            )
            or ns_name
        )
        namespace_owner_email = first_present_value(
            ["owner.email"], namespace_labels, namespace_annotations, related_objects
        )
        namespace_owner_contact = first_present_value(
            ["owner.contact", "contact"], namespace_labels, namespace_annotations, related_objects
        )
        namespace_cost_value = first_present_value(
            COST_LABEL_KEYS, namespace_labels, namespace_annotations, related_objects
        )
        namespace_business_unit_value = first_present_value(
            ["business-unit", "business_unit", "department"],
            namespace_labels,
            namespace_annotations,
            related_objects,
        )

        findings.append(
            {
                "kind": "Pod",
                "namespace": ns_name,
                "name": pod_name,
                "recommended_label_values": [
                    f"team={namespace_owner_value}",
                    f"app.kubernetes.io/managed-by={managed_by_hint(labels, {}, related_objects, namespace_owner_value)}",
                    f"app.kubernetes.io/owner={namespace_owner_value}",
                    f"app.kubernetes.io/team={namespace_owner_value}",
                    f"cost-center={cost_center_hint(namespace_cost_value, ns_name)}",
                    f"business-unit={business_unit_hint(namespace_business_unit_value, ns_name)}",
                ],
                "recommended_annotation_values": [
                    f"owner.email={namespace_owner_email or owner_email_hint(namespace_owner_value, ns_name)}",
                    f"owner.contact={namespace_owner_contact or owner_contact_hint(namespace_owner_value, workload_name_hint)}",
                    f"description={description_hint(workload_name_hint, ns_name)}",
                ],
                "present_label_keys": present_keys,
            }
        )

    print(json.dumps({"workload_label_governance_findings": findings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
