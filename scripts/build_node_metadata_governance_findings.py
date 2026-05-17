#!/usr/bin/env python3
import json
import re
import sys


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
]
OWNER_ANNOTATION_KEYS = [
    "owner.email",
    "owner.contact",
    "description",
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


def labels_of(obj):
    return ((obj.get("metadata") or {}).get("labels")) or {}


def annotations_of(obj):
    return ((obj.get("metadata") or {}).get("annotations")) or {}


def present_pairs(keys, values):
    results = []
    for key in keys:
        raw = str(values.get(key, "")).strip()
        if raw:
            results.append(f"{key}={raw}")
    return results


def node_roles(labels):
    roles = []
    for key in labels:
        if key.startswith("node-role.kubernetes.io/"):
            suffix = key.replace("node-role.kubernetes.io/", "", 1).strip() or "worker"
            roles.append(suffix)
    return sorted(set(roles)) or ["worker"]


def normalize_slug(text):
    return re.sub(r"[^a-zA-Z0-9-]+", "-", str(text or "").strip()).strip("-").lower()


def first_label(labels, keys):
    for key in keys:
        raw = str(labels.get(key, "")).strip()
        if raw:
            return raw
    return ""


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    findings = []
    for item in data.get("nodes") or []:
        metadata = item.get("metadata") or {}
        labels = labels_of(item)
        annotations = annotations_of(item)
        name = str(metadata.get("name") or "").strip()
        if not name:
            continue

        roles = node_roles(labels)
        primary_role = roles[0]
        role_slug = normalize_slug(primary_role or "worker") or "worker"
        provider = (
            first_label(
                labels,
                [
                    "node.kubernetes.io/instance-type",
                    "beta.kubernetes.io/instance-type",
                    "machine.openshift.io/instance-type",
                ],
            )
            or "platform-node"
        )
        zone = (
            first_label(
                labels,
                [
                    "topology.kubernetes.io/zone",
                    "failure-domain.beta.kubernetes.io/zone",
                ],
            )
            or "shared-zone"
        )
        present_owner_labels = present_pairs(OWNER_LABEL_KEYS, labels)
        present_owner_annotations = present_pairs(OWNER_ANNOTATION_KEYS, annotations)
        present_cost_labels = present_pairs(COST_LABEL_KEYS, labels)

        missing_metadata = []
        if not present_owner_labels and not present_owner_annotations:
            missing_metadata.append("node ownership metadata")
        if not present_cost_labels:
            missing_metadata.append("node cost chargeback metadata")
        if not missing_metadata:
            continue

        owner_team_hint = f"platform-{role_slug}"
        owner_email_hint = f"platform-{role_slug}@example.com"
        owner_contact_hint = f"#platform-{role_slug}"
        description_hint = f"{primary_role} node in {zone} for {provider}"
        cost_center_hint = f"cc-{normalize_slug(provider).upper() or 'PLATFORM'}"
        business_unit_hint = "PLATFORM"

        findings.append(
            {
                "node": name,
                "roles": roles,
                "missing_metadata": missing_metadata,
                "present_owner_labels": present_owner_labels,
                "present_owner_annotations": present_owner_annotations,
                "present_cost_labels": present_cost_labels,
                "recommended_owner_values": [
                    f"team={owner_team_hint}",
                    f"owner={owner_team_hint}",
                    f"owner.email={owner_email_hint}",
                    f"owner.contact={owner_contact_hint}",
                    f"description={description_hint}",
                ],
                "recommended_cost_values": [
                    f"cost-center={cost_center_hint}",
                    f"business-unit={business_unit_hint}",
                ],
                "detail": "; ".join(missing_metadata),
                "expected_owner_label_keys": OWNER_LABEL_KEYS,
                "expected_owner_annotation_keys": OWNER_ANNOTATION_KEYS,
                "expected_cost_label_keys": COST_LABEL_KEYS,
            }
        )

    print(json.dumps({"node_metadata_governance_findings": findings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
