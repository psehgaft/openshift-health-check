#!/usr/bin/env python3
import json
import sys


def labels(obj):
    return {str(k): str(v) for k, v in ((obj.get("metadata") or {}).get("labels") or {}).items()}


def template_labels(obj):
    return {
        str(k): str(v)
        for k, v in ((((obj.get("spec") or {}).get("template") or {}).get("metadata") or {}).get("labels") or {}).items()
    }


def selector_parts(obj):
    selector = (obj.get("spec") or {}).get("selector") or {}
    match_labels = {str(k): str(v) for k, v in (selector.get("matchLabels") or {}).items()}
    match_expressions = [item for item in (selector.get("matchExpressions") or []) if isinstance(item, dict)]
    return match_labels, match_expressions


def selector_is_empty(obj):
    match_labels, match_expressions = selector_parts(obj)
    return not match_labels and not match_expressions


def selector_description(obj):
    match_labels, match_expressions = selector_parts(obj)
    if not match_labels and not match_expressions:
        return "all machines"
    parts = []
    if match_labels:
        parts.append(",".join(f"{key}={value}" for key, value in sorted(match_labels.items())))
    if match_expressions:
        parts.append(f"{len(match_expressions)} expression(s)")
    return "; ".join(parts)


def labels_match(labels_map, match_labels, match_expressions):
    for key, value in (match_labels or {}).items():
        if str(labels_map.get(key) or "") != str(value):
            return False
    for expression in (match_expressions or []):
        key = str(expression.get("key") or "")
        operator = str(expression.get("operator") or "")
        values = [str(item) for item in (expression.get("values") or [])]
        current = str(labels_map.get(key) or "")
        if operator == "In" and current not in values:
            return False
        if operator == "NotIn" and current in values:
            return False
        if operator == "Exists" and key not in labels_map:
            return False
        if operator == "DoesNotExist" and key in labels_map:
            return False
    return True


def worker_machinesets(machine_sets):
    workers = []
    for item in machine_sets:
        combined = {}
        combined.update(labels(item))
        combined.update(template_labels(item))
        role_value = str(combined.get("machine.openshift.io/cluster-api-machine-role") or "").strip().lower()
        type_value = str(combined.get("machine.openshift.io/cluster-api-machine-type") or "").strip().lower()
        role_blob = " ".join([role_value, type_value, json.dumps(combined)]).lower()
        if "worker" in role_blob and "infra" not in role_blob and "master" not in role_blob and "control-plane" not in role_blob:
            workers.append({
                "name": str(((item.get("metadata") or {}).get("name")) or "").strip(),
                "namespace": str(((item.get("metadata") or {}).get("namespace")) or "").strip(),
                "labels": combined,
            })
    return workers


def bool_value(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    machine_sets = data.get("machinesets", []) or []
    mhcs = data.get("machinehealthchecks", []) or []
    cluster_profile = data.get("cluster_profile") or {}
    findings = []
    summary = []
    workers = worker_machinesets(machine_sets)
    worker_names = {item["name"] for item in workers if item.get("name")}
    remediation_expected = (
        not bool_value(cluster_profile.get("is_sno"))
        and not bool_value(cluster_profile.get("is_hosted_control_plane"))
        and (
            bool_value(cluster_profile.get("machine_api_managed_worker_pools"))
            or len(workers) > 0
        )
    )
    covered_worker_names = set()

    if remediation_expected and not mhcs:
        findings.append({
            "issue": "machinehealthcheck-missing",
            "detail": "Machine API-managed worker pools were found where automated worker remediation is expected, but no MachineHealthCheck resource was collected"
        })

    for item in mhcs:
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        paused = bool((meta.get("annotations") or {}).get("cluster.x-k8s.io/paused") == "true" or spec.get("paused", False))
        unhealthy_conditions = spec.get("unhealthyConditions") or []
        match_labels, match_expressions = selector_parts(item)
        covered_workers = []
        for machineset in workers:
            if selector_is_empty(item) or labels_match(machineset.get("labels") or {}, match_labels, match_expressions):
                covered_workers.append(machineset.get("name", ""))
                if machineset.get("name"):
                    covered_worker_names.add(machineset["name"])
        usable = bool(unhealthy_conditions) and not paused
        entry_status = (
            "paused"
            if paused else (
                ("conditions-missing" if remediation_expected else "review")
                if not unhealthy_conditions else (
                    "ok"
                    if (not remediation_expected or len(covered_workers) > 0 or len(workers) == 0)
                    else "not-covering-workers"
                )
            )
        )
        entry = {
            "namespace": meta.get("namespace", ""),
            "name": meta.get("name", ""),
            "paused": paused,
            "max_unhealthy": spec.get("maxUnhealthy", ""),
            "expected_machines": status.get("expectedMachines", "unknown"),
            "current_healthy": status.get("currentHealthy", "unknown"),
            "selector_scope": "all-machines" if selector_is_empty(item) else "filtered",
            "selector": selector_description(item),
            "unhealthy_condition_count": len(unhealthy_conditions),
            "covered_worker_machinesets": sorted([name for name in covered_workers if name]),
            "covered_worker_machineset_count": len([name for name in covered_workers if name]),
            "status": entry_status,
            "usable": usable,
        }
        summary.append(entry)
        if paused:
            findings.append({
                "issue": "machinehealthcheck-paused",
                "detail": f"{entry['namespace']}/{entry['name']} is paused"
            })
        if remediation_expected and not unhealthy_conditions:
            findings.append({
                "issue": "machinehealthcheck-unhealthyconditions-missing",
                "detail": f"{entry['namespace']}/{entry['name']} has no unhealthyConditions, so remediation trigger conditions were not confirmed"
            })

    if remediation_expected and mhcs and worker_names and covered_worker_names != worker_names:
        findings.append({
            "issue": "machinehealthcheck-coverage-incomplete",
            "detail": (
                "MachineHealthCheck coverage is incomplete for Machine API-managed worker pools: "
                f"coveredWorkerMachineSets={len(covered_worker_names)}/{len(worker_names)}"
            )
        })

    print(json.dumps({
        "machinehealthcheck_summary": sorted(summary, key=lambda item: (item["namespace"], item["name"])),
        "machine_healthcheck_findings": findings,
    }))


if __name__ == "__main__":
    main()
