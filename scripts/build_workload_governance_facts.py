#!/usr/bin/env python3
import json
import re
import sys


OPERATOR_MARKER_RE = re.compile(r"^(operators\.coreos\.com/|olm\.|operatorframework\.io/)")
NON_ALNUM_UPPER_RE = re.compile(r"[^A-Z0-9]+")
NON_ALNUM_DASH_RE = re.compile(r"[^a-zA-Z0-9-]+")
TRIM_DASH_RE = re.compile(r"(^-+|-+$)")
RUNNER_NOISE_TOKENS = (
    "gitlab-runner",
    "github-runner",
    "actions-runner",
    "azure-pipelines-agent",
    "azp-agent",
    "jenkins-agent",
    "jenkins-inbound-agent",
    "tekton-task",
    "buildkite-agent",
)


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


def lower_text(value):
    return text(value).lower()


def metadata(item):
    return as_dict(item.get("metadata")) if isinstance(item, dict) else {}


def spec(item):
    return as_dict(item.get("spec")) if isinstance(item, dict) else {}


def labels_and_annotations(item):
    meta = metadata(item)
    return as_dict(meta.get("labels")), as_dict(meta.get("annotations"))


def owner_refs(item):
    return as_list(metadata(item).get("ownerReferences"))


def has_csv_owner(item):
    return any(isinstance(ref, dict) and ref.get("kind") == "ClusterServiceVersion" for ref in owner_refs(item))


def has_operator_marker_keys(labels, annotations):
    for source in (labels, annotations):
        for key in source:
            if OPERATOR_MARKER_RE.match(text(key)):
                return True
    return False


def is_user_namespace(namespace, exclude_re):
    return not exclude_re.match(text(namespace))


def is_runner_noise_pod(item, labels):
    meta = metadata(item)
    pod_name_lower = lower_text(meta.get("name"))
    app_name_lower = lower_text(labels.get("app.kubernetes.io/name"))
    app_label_lower = lower_text(labels.get("app"))
    service_account_lower = lower_text(nested_get(item, ["spec", "serviceAccountName"], ""))
    return any(
        token in pod_name_lower
        or token in app_name_lower
        or token in app_label_lower
        or token in service_account_lower
        for token in RUNNER_NOISE_TOKENS
    )


def is_operator_managed(item, operator_namespaces, include_runner_noise=False):
    meta = metadata(item)
    namespace = text(meta.get("namespace"))
    labels, annotations = labels_and_annotations(item)
    managed_by_value = lower_text(labels.get("app.kubernetes.io/managed-by", annotations.get("app.kubernetes.io/managed-by", "")))
    name_lower = lower_text(meta.get("name"))
    app_name_lower = lower_text(labels.get("app.kubernetes.io/name"))
    result = bool(
        namespace in operator_namespaces
        or has_operator_marker_keys(labels, annotations)
        or managed_by_value in {"olm", "operator-lifecycle-manager"}
        or "operator" in managed_by_value
        or "-operator" in name_lower
        or "operator-" in name_lower
        or "controller-manager" in name_lower
        or "-operator" in app_name_lower
        or "operator-" in app_name_lower
        or has_csv_owner(item)
    )
    if include_runner_noise:
        result = result or is_runner_noise_pod(item, labels)
    return result


def namespace_metadata_by_name(namespaces):
    index = {}
    for item in as_list(namespaces):
        name = text(nested_get(item, ["metadata", "name"], ""))
        if name and name not in index:
            labels, annotations = labels_and_annotations(item)
            index[name] = {"labels": labels, "annotations": annotations}
    return index


def slug(value):
    return TRIM_DASH_RE.sub("", NON_ALNUM_DASH_RE.sub("-", text(value)).lower())


def business_unit_from_namespace(namespace):
    return text(namespace).split("-", 1)[0].upper()


def cost_center_from_namespace(namespace):
    return "cc-" + NON_ALNUM_UPPER_RE.sub("-", text(namespace).upper())


def build_orphan_pods(pods, exclude_re, operator_namespaces):
    findings = []
    for item in as_list(pods):
        meta = metadata(item)
        namespace = text(meta.get("namespace"))
        phase = text(nested_get(item, ["status", "phase"], "Unknown") or "Unknown")
        refs = owner_refs(item)
        if (
            is_user_namespace(namespace, exclude_re)
            and not is_operator_managed(item, operator_namespaces, include_runner_noise=True)
            and phase not in {"Succeeded", "Completed"}
            and len(refs) == 0
        ):
            findings.append({
                "namespace": namespace,
                "name": text(meta.get("name") or "unknown"),
                "phase": phase,
            })
    return findings


def missing_label_parts(labels):
    parts = []
    for key in (
        "app.kubernetes.io/name",
        "app.kubernetes.io/instance",
        "app.kubernetes.io/component",
        "app.kubernetes.io/part-of",
        "app.kubernetes.io/managed-by",
        "app.kubernetes.io/owner",
        "app.kubernetes.io/team",
    ):
        if len(text(labels.get(key))) == 0:
            parts.append(key)
    if all(len(text(labels.get(key))) == 0 for key in (
        "cost-center",
        "cost_center",
        "costcenter",
        "billing-code",
        "billing_code",
        "chargeback",
        "chargeback-code",
        "chargeback_code",
    )):
        parts.append("cost-center")
    if all(len(text(labels.get(key))) == 0 for key in ("business-unit", "business_unit", "department")):
        parts.append("business-unit")
    return parts


def first_value(*values):
    for value in values:
        if value:
            return value
    return ""


def build_label_governance_findings(workloads, namespaces, exclude_re, operator_namespaces):
    findings = []
    namespace_index = namespace_metadata_by_name(namespaces)

    for item in as_list(workloads):
        meta = metadata(item)
        namespace = text(meta.get("namespace"))
        if not is_user_namespace(namespace, exclude_re) or is_operator_managed(item, operator_namespaces):
            continue

        labels, annotations = labels_and_annotations(item)
        ns_meta = namespace_index.get(namespace, {})
        namespace_labels = as_dict(ns_meta.get("labels"))
        namespace_annotations = as_dict(ns_meta.get("annotations"))
        workload_name = text(meta.get("name") or "unknown")
        workload_kind = text(item.get("kind") or "Workload")
        missing_parts = missing_label_parts(labels)
        if not missing_parts:
            continue

        owner_label_hint = first_value(
            labels.get("app.kubernetes.io/owner"),
            labels.get("app.kubernetes.io/team"),
            labels.get("team"),
            labels.get("owner"),
            annotations.get("owner.team"),
            namespace_labels.get("app.kubernetes.io/owner"),
            namespace_labels.get("app.kubernetes.io/team"),
            namespace_labels.get("team"),
            namespace_labels.get("owner"),
            namespace_annotations.get("owner.team"),
            namespace,
        )
        managed_by_hint = first_value(
            labels.get("app.kubernetes.io/managed-by"),
            annotations.get("app.kubernetes.io/managed-by"),
            namespace_labels.get("app.kubernetes.io/managed-by"),
            namespace_annotations.get("app.kubernetes.io/managed-by"),
            owner_label_hint,
        )
        cost_center_hint = first_value(
            labels.get("cost-center"),
            labels.get("cost_center"),
            labels.get("costcenter"),
            labels.get("billing-code"),
            labels.get("billing_code"),
            labels.get("chargeback"),
            labels.get("chargeback-code"),
            labels.get("chargeback_code"),
            namespace_labels.get("cost-center"),
            namespace_labels.get("cost_center"),
            namespace_labels.get("costcenter"),
            namespace_labels.get("billing-code"),
            namespace_labels.get("billing_code"),
            namespace_labels.get("chargeback"),
            namespace_labels.get("chargeback-code"),
            namespace_labels.get("chargeback_code"),
            cost_center_from_namespace(namespace),
        )
        business_unit_hint = first_value(
            labels.get("business-unit"),
            labels.get("business_unit"),
            labels.get("department"),
            namespace_labels.get("business-unit"),
            namespace_labels.get("business_unit"),
            namespace_labels.get("department"),
            business_unit_from_namespace(namespace),
        )
        owner_email_hint = first_value(
            annotations.get("owner.email"),
            namespace_annotations.get("owner.email"),
            slug(owner_label_hint) + "@example.com",
        )
        owner_contact_hint = first_value(
            annotations.get("owner.contact"),
            annotations.get("contact"),
            namespace_annotations.get("owner.contact"),
            namespace_annotations.get("contact"),
            "#team-" + slug(owner_label_hint),
        )
        description_hint = first_value(
            annotations.get("description"),
            "Workload " + workload_name + " in namespace " + namespace,
        )

        label_context_values = []
        for key in (
            "app",
            "app.kubernetes.io/name",
            "app.kubernetes.io/instance",
            "app.kubernetes.io/component",
            "app.kubernetes.io/part-of",
            "app.kubernetes.io/managed-by",
        ):
            if len(text(labels.get(key))) > 0:
                label_context_values.append(key + "=" + text(labels.get(key)))
        if namespace:
            label_context_values.append("namespace=" + namespace)
        if workload_name:
            label_context_values.append("workload=" + workload_name)

        annotation_context_values = []
        for key in ("owner.email", "owner.contact", "contact", "description"):
            if len(text(annotations.get(key))) > 0:
                annotation_context_values.append(key + "=" + text(annotations.get(key)))
        if workload_kind:
            annotation_context_values.append("kind=" + workload_kind)

        recommended_label_values = []
        if "app.kubernetes.io/name" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/name=" + text(labels.get("app.kubernetes.io/name") or workload_name))
        if "app.kubernetes.io/instance" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/instance=" + text(labels.get("app.kubernetes.io/instance") or namespace))
        if "app.kubernetes.io/component" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/component=" + text(labels.get("app.kubernetes.io/component") or workload_kind.lower()))
        if "app.kubernetes.io/part-of" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/part-of=" + text(labels.get("app.kubernetes.io/part-of") or namespace))
        if "app.kubernetes.io/managed-by" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/managed-by=" + text(managed_by_hint))
        if "app.kubernetes.io/owner" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/owner=" + text(owner_label_hint))
        if "app.kubernetes.io/team" in missing_parts:
            recommended_label_values.append("app.kubernetes.io/team=" + text(owner_label_hint))
        if "cost-center" in missing_parts:
            recommended_label_values.append("cost-center=" + text(cost_center_hint))
        if "business-unit" in missing_parts:
            recommended_label_values.append("business-unit=" + text(business_unit_hint))

        findings.append({
            "kind": workload_kind,
            "namespace": namespace,
            "name": workload_name,
            "detail": "; ".join(missing_parts),
            "label_values": label_context_values,
            "annotation_values": annotation_context_values,
            "recommended_label_values": recommended_label_values,
            "recommended_annotation_values": [
                "owner.email=" + text(owner_email_hint),
                "owner.contact=" + text(owner_contact_hint),
                "description=" + text(description_hint),
            ],
        })

    return findings


def missing_resource_parts(container, resource_type):
    resources = as_dict(container.get("resources"))
    resource_block = as_dict(resources.get(resource_type))
    missing = []
    for key in ("cpu", "memory"):
        if text(resource_block.get(key)).strip() == "":
            missing.append(key)
    return missing


def container_names_without_resources(containers, resource_type):
    names = []
    for container in as_list(containers):
        missing = missing_resource_parts(container, resource_type)
        if missing:
            name = text(nested_get(container, ["name"], None) or "unknown")
            names.append(f"{name} ({', '.join(missing)})")
    return names


def resource_finding(common, containers_without_requests, containers_without_limits):
    issues = []
    detail_parts = []
    if containers_without_requests:
        issues.append("workload-missing-resource-requests")
        detail_parts.append("requests: " + ", ".join(text(value) for value in containers_without_requests))
    if containers_without_limits:
        issues.append("workload-missing-resource-limits")
        detail_parts.append("limits: " + ", ".join(text(value) for value in containers_without_limits))
    if not issues:
        return None

    entry = dict(common)
    entry.update({
        "issue": ", ".join(issues),
        "issues": issues,
        "missing_requests_containers": [text(value) for value in containers_without_requests],
        "missing_limits_containers": [text(value) for value in containers_without_limits],
        "detail": "; ".join(detail_parts),
    })
    return entry


def build_resource_findings(workloads, exclude_re, operator_namespaces):
    findings = []
    for item in as_list(workloads):
        meta = metadata(item)
        namespace = text(meta.get("namespace"))
        if not is_user_namespace(namespace, exclude_re) or is_operator_managed(item, operator_namespaces):
            continue

        pod_spec = as_dict(nested_get(item, ["spec", "template", "spec"], {}))
        containers = as_list(pod_spec.get("containers")) + as_list(pod_spec.get("initContainers"))
        if not containers:
            continue

        containers_without_requests = container_names_without_resources(containers, "requests")
        containers_without_limits = container_names_without_resources(containers, "limits")
        common = {
            "kind": text(item.get("kind") or "Workload"),
            "namespace": namespace,
            "name": text(meta.get("name") or "unknown"),
        }
        entry = resource_finding(common, containers_without_requests, containers_without_limits)
        if entry:
            findings.append(entry)

    return findings


def build(data):
    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    operator_namespaces = set(text(value) for value in as_list(data.get("operator_managed_namespace_names")) if text(value))
    workloads = (
        as_list(data.get("deployments"))
        + as_list(data.get("statefulsets"))
        + as_list(data.get("daemonsets"))
    )

    return {
        "orphan_pods": build_orphan_pods(data.get("pods"), exclude_re, operator_namespaces),
        "workload_label_governance_findings": build_label_governance_findings(
            workloads,
            data.get("namespaces"),
            exclude_re,
            operator_namespaces,
        ),
        "workload_resource_findings": build_resource_findings(workloads, exclude_re, operator_namespaces),
    }


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_workload_governance_facts.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
