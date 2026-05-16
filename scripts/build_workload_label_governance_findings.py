#!/usr/bin/env python3
import json
import re
import sys
from collections import defaultdict


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


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_regex = str(data.get("user_namespaces_exclude_regex") or "")
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
            ["contact"], namespace_labels, namespace_annotations, related_objects
        )
        namespace_cost_value = first_present_value(
            COST_LABEL_KEYS, namespace_labels, namespace_annotations, related_objects
        )

        findings.append(
            {
                "kind": "Pod",
                "namespace": ns_name,
                "name": pod_name,
                "recommended_label_values": [
                    f"team={namespace_owner_value}",
                    f"app.kubernetes.io/owner={namespace_owner_value}",
                    (
                        f"cost-center={namespace_cost_value}"
                        if namespace_cost_value
                        else f"cost-center=<set-cost-center-for-{ns_name}>"
                    ),
                ],
                "recommended_annotation_values": [
                    (
                        f"owner.email={namespace_owner_email}"
                        if namespace_owner_email
                        else f"owner.email=<set-email-for-{namespace_owner_value}>"
                    ),
                    (
                        f"owner.contact={namespace_owner_contact}"
                        if namespace_owner_contact
                        else f"owner.contact=<set-contact-for-{workload_name_hint}>"
                    ),
                ],
                "present_label_keys": present_keys,
            }
        )

    print(json.dumps({"workload_label_governance_findings": findings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
