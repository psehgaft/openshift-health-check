#!/usr/bin/env python3
import json
import re
import sys
from collections import defaultdict


OWNER_LABEL_KEYS = [
    "team",
    "owner",
    "owner.team",
    "team-name",
    "team_name",
    "app.kubernetes.io/team",
    "app.kubernetes.io/owner",
    "ops.team",
    "ops.owner",
    "contact",
    "owner.email",
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


def present_pairs(keys, labels):
    values = []
    for key in keys:
        raw = str(labels.get(key, "")).strip()
        if raw:
            values.append(f"{key}={raw}")
    return values


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_regex = str(data.get("user_namespaces_exclude_regex") or "")
    namespace_items = data.get("namespaces") or []
    namespace_objects = defaultdict(list)

    for collection_name in [
        "deployments",
        "statefulsets",
        "daemonsets",
        "deploymentconfigs",
        "pods",
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
    for item in namespace_items:
        ns_name = str((((item.get("metadata") or {}).get("name")) or "")).strip()
        if not ns_name or re.match(exclude_regex, ns_name):
            continue

        labels = labels_of(item)
        annotations = annotations_of(item)
        related_objects = namespace_objects.get(ns_name, [])

        owner_value_hint = first_present_value(OWNER_LABEL_KEYS, labels, annotations, related_objects) or ns_name
        owner_email_hint = (
            first_present_value(["owner.email"], labels, annotations, related_objects)
            or f"team-{ns_name}@example.com"
        )
        owner_contact_hint = (
            first_present_value(["contact"], labels, annotations, related_objects)
            or f"#team-{re.sub(r'[^a-zA-Z0-9-]+', '-', ns_name)}"
        )
        cost_value_hint = (
            first_present_value(COST_LABEL_KEYS, labels, annotations, related_objects)
            or f"cc-{re.sub(r'[^A-Z0-9]+', '-', ns_name.upper())}"
        )
        business_unit_hint = (
            first_present_value(
                ["business-unit", "business_unit", "department"],
                labels,
                annotations,
                related_objects,
            )
            or re.sub(r"^([^-]+).*", r"\1", ns_name).upper()
        )
        present_owner_labels = present_pairs(OWNER_LABEL_KEYS, labels)
        present_cost_labels = present_pairs(COST_LABEL_KEYS, labels)

        missing_metadata = []
        if not present_owner_labels:
            missing_metadata.append("team ownership metadata")
        if not present_cost_labels:
            missing_metadata.append("cost chargeback metadata")
        if not missing_metadata:
            continue

        findings.append(
            {
                "namespace": ns_name,
                "missing_metadata": missing_metadata,
                "present_owner_labels": present_owner_labels,
                "present_cost_labels": present_cost_labels,
                "recommended_owner_values": [
                    f"team={owner_value_hint}",
                    f"owner.email={owner_email_hint}",
                    f"contact={owner_contact_hint}",
                ],
                "recommended_cost_values": [
                    f"cost-center={cost_value_hint}",
                    f"business-unit={business_unit_hint}",
                ],
                "detail": "; ".join(missing_metadata),
                "expected_owner_label_keys": OWNER_LABEL_KEYS,
                "expected_cost_label_keys": COST_LABEL_KEYS,
            }
        )

    print(json.dumps({"namespace_metadata_governance_findings": findings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
