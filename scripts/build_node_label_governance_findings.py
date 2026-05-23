#!/usr/bin/env python3
import json
import re
import sys


LABEL_KEYS = [
    "team",
    "owner",
    "cost-center",
    "cost_center",
    "costcenter",
    "business-unit",
    "business_unit",
    "department",
]
ANNOTATION_KEYS = [
    "owner.email",
    "owner.contact",
    "description",
]


def labels_of(obj):
    return ((obj.get("metadata") or {}).get("labels")) or {}


def annotations_of(obj):
    return ((obj.get("metadata") or {}).get("annotations")) or {}


def first_label(labels, keys):
    for key in keys:
        value = str(labels.get(key, "")).strip()
        if value:
            return value
    return ""


def first_annotation(annotations, keys):
    for key in keys:
        value = str(annotations.get(key, "")).strip()
        if value:
            return value
    return ""


def normalize_slug(text):
    return re.sub(r"[^a-zA-Z0-9-]+", "-", str(text or "").strip()).strip("-").lower()


def node_roles(labels):
    roles = []
    for key in labels:
        if key.startswith("node-role.kubernetes.io/"):
            role = key.replace("node-role.kubernetes.io/", "", 1).strip() or "worker"
            roles.append(role)
    return sorted(set(roles)) or ["worker"]


def build(data):
    findings = []
    for node in data.get("nodes") or []:
        metadata = node.get("metadata") or {}
        labels = labels_of(node)
        annotations = annotations_of(node)
        node_name = str(metadata.get("name") or "").strip()
        if not node_name:
            continue

        roles = node_roles(labels)
        primary_role = roles[0]
        role_slug = normalize_slug(primary_role) or "worker"
        zone_hint = (
            first_label(labels, ["topology.kubernetes.io/zone", "failure-domain.beta.kubernetes.io/zone"])
            or "shared-zone"
        )
        instance_type_hint = (
            first_label(labels, ["node.kubernetes.io/instance-type", "beta.kubernetes.io/instance-type", "machine.openshift.io/instance-type"])
            or "platform-node"
        )

        owner_present = bool(first_label(labels, ["team", "owner"]))
        cost_present = bool(first_label(labels, ["cost-center", "cost_center", "costcenter", "business-unit", "business_unit", "department"]))
        email_present = bool(first_annotation(annotations, ["owner.email"]))
        contact_present = bool(first_annotation(annotations, ["owner.contact"]))
        description_present = bool(first_annotation(annotations, ["description"]))

        missing_parts = []
        if not owner_present:
            missing_parts.extend(["team", "owner"])
        if not cost_present:
            if not first_label(labels, ["cost-center", "cost_center", "costcenter"]):
                missing_parts.append("cost-center")
            if not first_label(labels, ["business-unit", "business_unit", "department"]):
                missing_parts.append("business-unit")
        if not email_present:
            missing_parts.append("owner.email")
        if not contact_present:
            missing_parts.append("owner.contact")
        if not description_present:
            missing_parts.append("description")
        if not missing_parts:
            continue

        team_hint = f"platform-{role_slug}"
        cost_center_hint = f"cc-{(normalize_slug(instance_type_hint) or 'platform-node').upper()}"
        recommended_labels = (
            ([] if "team" not in missing_parts else [f"team={team_hint}"])
            + ([] if "owner" not in missing_parts else [f"owner={team_hint}"])
            + ([] if "cost-center" not in missing_parts else [f"cost-center={cost_center_hint}"])
            + ([] if "business-unit" not in missing_parts else ["business-unit=PLATFORM"])
        )
        recommended_annotations = (
            ([] if "owner.email" not in missing_parts else [f"owner.email=platform-{role_slug}@example.com"])
            + ([] if "owner.contact" not in missing_parts else [f"owner.contact=#platform-{role_slug}"])
            + ([] if "description" not in missing_parts else [f"description={primary_role} node in {zone_hint} for {instance_type_hint}"])
        )
        findings.append(
            {
                "kind": "Node",
                "namespace": "cluster-scoped",
                "name": node_name,
                "roles": roles,
                "roles_display": ", ".join(roles),
                "primary_role": primary_role,
                "zone": zone_hint,
                "instance_type": instance_type_hint,
                "missing_governance_metadata": missing_parts,
                "recommended_label_values": recommended_labels,
                "recommended_annotation_values": recommended_annotations,
            }
        )

    return {"node_label_governance_findings": findings}


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
