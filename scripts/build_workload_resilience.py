#!/usr/bin/env python3
import json
import re
import sys


def normalize_labels(raw):
    return {
        str(key): str(value)
        for key, value in (raw or {}).items()
        if key not in (None, "") and value not in (None, "")
    }


def match_expression(labels, expr):
    key = str((expr or {}).get("key") or "")
    if not key:
        return False
    operator = str((expr or {}).get("operator") or "")
    values = [str(value) for value in ((expr or {}).get("values") or [])]
    present = key in labels
    label_value = str(labels.get(key, ""))
    if operator == "In":
        return present and label_value in values
    if operator == "NotIn":
        return (not present) or label_value not in values
    if operator == "Exists":
        return present
    if operator == "DoesNotExist":
        return not present
    return False


def selector_matches(selector, labels):
    selector = selector or {}
    match_labels = normalize_labels(selector.get("matchLabels"))
    expressions = selector.get("matchExpressions") or []
    if not match_labels and not expressions:
        return True
    for key, value in match_labels.items():
        if labels.get(key) != value:
            return False
    return all(match_expression(labels, expr) for expr in expressions)


def has_spread_policy(pod_spec):
    pod_spec = pod_spec or {}
    spread_constraints = pod_spec.get("topologySpreadConstraints") or []
    if spread_constraints:
        return True
    affinity = (pod_spec.get("affinity") or {}).get("podAntiAffinity") or {}
    return bool(
        (affinity.get("requiredDuringSchedulingIgnoredDuringExecution") or [])
        or (affinity.get("preferredDuringSchedulingIgnoredDuringExecution") or [])
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_workload_resilience.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_re = re.compile(data.get("exclude_regex") or r"^$")

    workloads = []
    for collection_name, kind in (("deployments", "Deployment"), ("statefulsets", "StatefulSet")):
        for item in data.get(collection_name, []):
            metadata = item.get("metadata", {}) or {}
            namespace = str(metadata.get("namespace") or "")
            if exclude_re.search(namespace):
                continue
            desired_replicas = int(((item.get("spec", {}) or {}).get("replicas", 1)) or 1)
            if desired_replicas < 2:
                continue
            template = ((item.get("spec", {}) or {}).get("template", {}) or {})
            template_metadata = template.get("metadata", {}) or {}
            template_spec = template.get("spec", {}) or {}
            workloads.append(
                {
                    "kind": kind,
                    "namespace": namespace,
                    "name": str(metadata.get("name") or "unknown"),
                    "replicas": desired_replicas,
                    "labels": normalize_labels(template_metadata.get("labels")),
                    "has_spread_policy": has_spread_policy(template_spec),
                }
            )

    pdbs_by_namespace = {}
    for item in data.get("poddisruptionbudgets", []):
        metadata = item.get("metadata", {}) or {}
        namespace = str(metadata.get("namespace") or "")
        pdbs_by_namespace.setdefault(namespace, []).append(
            {
                "name": str(metadata.get("name") or "unknown"),
                "selector": ((item.get("spec", {}) or {}).get("selector") or {}),
            }
        )

    findings = []
    for workload in workloads:
        matching_pdbs = [
            pdb["name"]
            for pdb in pdbs_by_namespace.get(workload["namespace"], [])
            if selector_matches(pdb.get("selector"), workload["labels"])
        ]
        if not matching_pdbs:
            findings.append(
                {
                    "kind": workload["kind"],
                    "namespace": workload["namespace"],
                    "name": workload["name"],
                    "issue": "missing-pod-disruption-budget",
                    "detail": f"replicas={workload['replicas']}; no matching PodDisruptionBudget",
                }
            )
        if not workload["has_spread_policy"]:
            findings.append(
                {
                    "kind": workload["kind"],
                    "namespace": workload["namespace"],
                    "name": workload["name"],
                    "issue": "missing-workload-spread-policy",
                    "detail": f"replicas={workload['replicas']}; no topology spread constraints or pod anti-affinity",
                }
            )

    print(
        json.dumps(
            {
                "findings": findings,
                "multi_replica_workload_count": len(workloads),
                "multi_replica_workloads_without_pdb": sum(
                    1 for item in findings if item["issue"] == "missing-pod-disruption-budget"
                ),
                "multi_replica_workloads_without_spread_policy": sum(
                    1 for item in findings if item["issue"] == "missing-workload-spread-policy"
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
