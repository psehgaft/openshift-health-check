#!/usr/bin/env python3
import json
import sys
from collections import Counter


def derive_machineset_failure_domain(item):
    spec = item.get("spec", {}) or {}
    tmpl = (spec.get("template", {}) or {})
    tmpl_meta = (tmpl.get("metadata", {}) or {})
    labels = tmpl_meta.get("labels", {}) or {}
    direct_candidates = [
        labels.get("topology.kubernetes.io/zone"),
        labels.get("failure-domain.beta.kubernetes.io/zone"),
        labels.get("machine.openshift.io/zone"),
        ((item.get("metadata", {}) or {}).get("labels", {}) or {}).get("topology.kubernetes.io/zone"),
        ((item.get("metadata", {}) or {}).get("labels", {}) or {}).get("failure-domain.beta.kubernetes.io/zone"),
        ((item.get("metadata", {}) or {}).get("labels", {}) or {}).get("machine.openshift.io/zone"),
    ]
    for candidate in direct_candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    provider_value = ((((tmpl.get("spec", {}) or {}).get("providerSpec") or {}).get("value")) or {})
    for path in [("placement", "availabilityZone"), ("placement", "zone"), ("zone",), ("zones", 0), ("failureDomain",), ("failureDomains", 0), ("subnet",), ("workspace", "server")]:
        current = provider_value
        valid = True
        for key in path:
            if isinstance(key, int):
                if not isinstance(current, list) or len(current) <= key:
                    valid = False
                    break
                current = current[key]
            else:
                if not isinstance(current, dict):
                    valid = False
                    break
                current = current.get(key)
        if valid:
            text = str(current or "").strip()
            if text:
                return text
    return ""


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
    worker_zone_counts = Counter()
    unlabeled_worker_nodes = 0
    for node in data.get("nodes", []):
        meta = node.get("metadata", {}) or {}
        labels = meta.get("labels", {}) or {}
        roles = []
        for key in labels:
            if key.startswith("node-role.kubernetes.io/"):
                roles.append(key.replace("node-role.kubernetes.io/", "", 1) or "worker")
        primary_role = "worker"
        if "master" in roles:
            primary_role = "master"
        elif "control-plane" in roles:
            primary_role = "control-plane"
        elif "infra" in roles:
            primary_role = "infra"
        elif "worker" in roles:
            primary_role = "worker"
        elif roles:
            primary_role = sorted(roles)[0]
        if primary_role != "worker":
            continue
        zone = labels.get("topology.kubernetes.io/zone") or labels.get("failure-domain.beta.kubernetes.io/zone")
        if zone:
            worker_zone_counts[str(zone)] += 1
        else:
            unlabeled_worker_nodes += 1
    worker_pools = data.get("worker_pools", []) or []
    single_zone_pools = [p for p in worker_pools if len(p.get("zones", []) or []) <= 1]
    zone_counts = list(worker_zone_counts.values())
    zone_spread_unbalanced = (max(zone_counts) - min(zone_counts) > 1) if len(zone_counts) > 1 else False
    machineset_summary = []
    machine_set_zone_counts = Counter()
    machinesets_without_zone = 0
    replicas = []
    for item in data.get("machinesets", []):
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        zone = derive_machineset_failure_domain(item)
        replicas_value = int(spec.get("replicas", 0) or 0)
        replicas.append(replicas_value)
        if zone:
            machine_set_zone_counts[str(zone)] += replicas_value
        else:
            machinesets_without_zone += 1
        machineset_summary.append({"namespace": meta.get("namespace", "openshift-machine-api"), "name": meta.get("name", "unknown"), "replicas": replicas_value, "zone": zone or "not-assessed"})
    machineset_replica_unbalanced = (max(replicas) - min(replicas) > 1) if len(replicas) > 1 else False
    print(json.dumps({"worker_failure_domains_observed": sorted(worker_zone_counts.keys()), "worker_zone_counts": [{"zone": z, "nodes": worker_zone_counts[z]} for z in sorted(worker_zone_counts.keys())], "worker_nodes_without_zone_label": unlabeled_worker_nodes, "single_zone_worker_pools": [{"type": p.get("type", "unknown"), "nodes": p.get("nodes", 0), "zones": p.get("zones", [])} for p in single_zone_pools], "single_zone_worker_pool_count": len(single_zone_pools), "worker_zone_spread_unbalanced": zone_spread_unbalanced, "machineset_summary": machineset_summary, "machine_set_failure_domains_observed": sorted(machine_set_zone_counts.keys()), "machine_set_zone_counts": [{"zone": z, "replicas": machine_set_zone_counts[z]} for z in sorted(machine_set_zone_counts.keys())], "machinesets_without_zone_label": machinesets_without_zone, "machineset_replica_unbalanced": machineset_replica_unbalanced}))


if __name__ == "__main__":
    main()
