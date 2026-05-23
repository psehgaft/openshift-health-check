#!/usr/bin/env python3
import json
import math
import re
import sys

from workload_noise_filters import is_operator_managed_object


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


NODE_OR_ZONE_TOPOLOGY_KEYS = {
    "topology.kubernetes.io/zone",
    "failure-domain.beta.kubernetes.io/zone",
    "kubernetes.io/hostname",
}


def classify_spread_policy(pod_spec):
    pod_spec = pod_spec or {}
    spread_constraints = pod_spec.get("topologySpreadConstraints") or []
    spread_topology_keys = [
        str(item.get("topologyKey") or "").strip()
        for item in spread_constraints
        if str(item.get("topologyKey") or "").strip()
    ]
    if any(key in NODE_OR_ZONE_TOPOLOGY_KEYS for key in spread_topology_keys):
        return {
            "present": True,
            "node_or_zone_aware": True,
            "basis": "topologySpreadConstraints",
            "topology_keys": spread_topology_keys,
        }
    if spread_topology_keys:
        return {
            "present": True,
            "node_or_zone_aware": False,
            "basis": "topologySpreadConstraints",
            "topology_keys": spread_topology_keys,
        }
    affinity = (pod_spec.get("affinity") or {}).get("podAntiAffinity") or {}
    anti_affinity_terms = (affinity.get("requiredDuringSchedulingIgnoredDuringExecution") or []) + (
        affinity.get("preferredDuringSchedulingIgnoredDuringExecution") or []
    )
    anti_affinity_topology_keys = [
        str(((item or {}).get("topologyKey") or "")).strip()
        for item in anti_affinity_terms
        if str(((item or {}).get("topologyKey") or "")).strip()
    ]
    if any(key in NODE_OR_ZONE_TOPOLOGY_KEYS for key in anti_affinity_topology_keys):
        return {
            "present": True,
            "node_or_zone_aware": True,
            "basis": "podAntiAffinity",
            "topology_keys": anti_affinity_topology_keys,
        }
    if anti_affinity_terms:
        return {
            "present": True,
            "node_or_zone_aware": False,
            "basis": "podAntiAffinity",
            "topology_keys": anti_affinity_topology_keys,
        }
    return {
        "present": False,
        "node_or_zone_aware": False,
        "basis": "none",
        "topology_keys": [],
    }


def parse_int_or_percent(value, replicas):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        try:
            return int(math.ceil((replicas * float(text[:-1])) / 100.0))
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        return None


def evaluate_pdb_usable(pdb_spec, replicas):
    spec = pdb_spec or {}
    max_unavailable = parse_int_or_percent(spec.get("maxUnavailable"), replicas)
    min_available = parse_int_or_percent(spec.get("minAvailable"), replicas)
    if max_unavailable is not None:
        return (
            max_unavailable >= 1,
            f"maxUnavailable={spec.get('maxUnavailable')}",
        )
    if min_available is not None:
        return (
            min_available <= max(replicas - 1, 0),
            f"minAvailable={spec.get('minAvailable')}",
        )
    return (False, "no minAvailable or maxUnavailable was set")


def pdb_review_detail(workload, matching_pdbs):
    pdb_descriptions = ", ".join(
        f"{item['name']}({item['usability_reason']})"
        for item in matching_pdbs
    )
    return (
        f"replicas={workload['replicas']}; matching PDBs require review: {pdb_descriptions}"
    )


def build(data):
    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    operator_managed_namespace_names = data.get("operator_managed_namespace_names") or []

    workloads = []
    for collection_name, kind in (
        ("deployments", "Deployment"),
        ("statefulsets", "StatefulSet"),
        ("deploymentconfigs", "DeploymentConfig"),
    ):
        for item in data.get(collection_name, []):
            metadata = item.get("metadata", {}) or {}
            namespace = str(metadata.get("namespace") or "")
            if exclude_re.search(namespace):
                continue
            if is_operator_managed_object(item, operator_managed_namespace_names):
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
                    "spread_policy": classify_spread_policy(template_spec),
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
                "spec": (item.get("spec", {}) or {}),
            }
        )

    findings = []
    pdb_review_findings = []
    for workload in workloads:
        matching_pdbs = [
            {
                "name": pdb["name"],
                "spec": pdb.get("spec") or {},
            }
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
        else:
            evaluated_pdbs = []
            has_usable_pdb = False
            for pdb in matching_pdbs:
                usable, usability_reason = evaluate_pdb_usable(
                    pdb.get("spec") or {},
                    workload["replicas"],
                )
                evaluated_pdbs.append(
                    {
                        "name": pdb["name"],
                        "usable": usable,
                        "usability_reason": usability_reason,
                    }
                )
                if usable:
                    has_usable_pdb = True
            if not has_usable_pdb:
                pdb_review_findings.append(
                    {
                        "kind": workload["kind"],
                        "namespace": workload["namespace"],
                        "name": workload["name"],
                        "issue": "pod-disruption-budget-requires-review",
                        "detail": pdb_review_detail(workload, evaluated_pdbs),
                        "matching_pdb_names": [item["name"] for item in evaluated_pdbs],
                    }
                )
        if not workload["spread_policy"]["present"]:
            findings.append(
                {
                    "kind": workload["kind"],
                    "namespace": workload["namespace"],
                    "name": workload["name"],
                    "issue": "missing-workload-spread-policy",
                    "detail": f"replicas={workload['replicas']}; no topology spread constraints or pod anti-affinity",
                }
            )

    return {
        "findings": findings,
        "pdb_review_findings": pdb_review_findings,
        "multi_replica_workload_count": len(workloads),
        "multi_replica_workloads_without_pdb": sum(
            1 for item in findings if item["issue"] == "missing-pod-disruption-budget"
        ),
        "multi_replica_workloads_without_usable_pdb": len(pdb_review_findings),
        "multi_replica_workloads_without_spread_policy": sum(
            1 for item in findings if item["issue"] == "missing-workload-spread-policy"
        ),
        "multi_replica_workloads_with_node_or_zone_spread_policy": sum(
            1
            for workload in workloads
            if workload["spread_policy"]["present"]
            and workload["spread_policy"]["node_or_zone_aware"]
        ),
        "multi_replica_workloads_with_other_spread_policy": sum(
            1
            for workload in workloads
            if workload["spread_policy"]["present"]
            and not workload["spread_policy"]["node_or_zone_aware"]
        ),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_workload_resilience.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
