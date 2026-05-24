#!/usr/bin/env python3
import json
import re
import sys
from collections import Counter


ZONE_PATTERN = re.compile(r"(?<![a-z0-9])([a-z]{2}-[a-z]+-[0-9][a-z])(?![a-z0-9])")


def text_value(value):
    text = str(value or "").strip()
    return text if text and text.lower() not in {"none", "null", "unknown", "not-assessed", "not-derived"} else ""


def first_text(*values):
    for value in values:
        text = text_value(value)
        if text:
            return text
    return ""


def zone_from_text(*values):
    for value in values:
        text = text_value(value)
        if not text:
            continue
        match = ZONE_PATTERN.search(text)
        if match:
            return match.group(1)
    return ""


def labels_from(item, *paths):
    values = []
    for path in paths:
        current = item
        for key in path:
            if not isinstance(current, dict):
                current = {}
                break
            current = current.get(key, {})
        if isinstance(current, dict):
            values.append(current)
    merged = {}
    for labels in values:
        merged.update(labels)
    return merged


def zone_from_labels(labels):
    return first_text(
        labels.get("topology.kubernetes.io/zone"),
        labels.get("failure-domain.beta.kubernetes.io/zone"),
        labels.get("machine.openshift.io/zone"),
        labels.get("topology.ebs.csi.aws.com/zone"),
    )


def derive_node_failure_domain(item):
    meta = item.get("metadata", {}) or {}
    labels = meta.get("labels", {}) or {}
    spec = item.get("spec", {}) or {}
    return (
        zone_from_labels(labels)
        or zone_from_text(spec.get("providerID"), meta.get("name"))
    )


def replica_value(item):
    spec = item.get("spec", {}) or {}
    status = item.get("status", {}) or {}
    for value in [spec.get("replicas"), status.get("replicas"), status.get("availableReplicas"), status.get("readyReplicas")]:
        if value in [None, ""]:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def derive_machineset_failure_domain(item):
    spec = item.get("spec", {}) or {}
    tmpl = (spec.get("template", {}) or {})
    tmpl_meta = (tmpl.get("metadata", {}) or {})
    tmpl_spec = (tmpl.get("spec", {}) or {})
    labels = labels_from(item, ("metadata", "labels"), ("spec", "selector", "matchLabels"), ("spec", "template", "metadata", "labels"))
    zone = zone_from_labels(labels)
    if zone:
        return zone
    provider_value = ((((tmpl.get("spec", {}) or {}).get("providerSpec") or {}).get("value")) or {})
    for path in [
        ("placement", "availabilityZone"),
        ("placement", "zone"),
        ("zone",),
        ("zones", 0),
        ("failureDomain",),
        ("failureDomains", 0),
        ("providerSpec", "value", "placement", "availabilityZone"),
        ("subnet",),
        ("workspace", "server"),
    ]:
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
            text = text_value(current)
            if text:
                return text
    return zone_from_text(
        tmpl_spec.get("providerID"),
        ((item.get("metadata", {}) or {}).get("name")),
        ((item.get("metadata", {}) or {}).get("generateName")),
    )


def derive_machine_failure_domain(item):
    meta = item.get("metadata", {}) or {}
    spec = item.get("spec", {}) or {}
    labels = labels_from(item, ("metadata", "labels"), ("spec", "metadata", "labels"))
    zone = zone_from_labels(labels)
    if zone:
        return zone
    provider_value = ((spec.get("providerSpec") or {}).get("value") or {})
    return first_text(
        provider_value.get("zone") if isinstance(provider_value, dict) else "",
        ((provider_value.get("placement") or {}).get("availabilityZone") if isinstance(provider_value, dict) else ""),
        zone_from_text(spec.get("providerID"), meta.get("name")),
    )


def worker_pool_zone_counts(worker_pools):
    counts = Counter()
    for pool in worker_pools:
        for zone in pool.get("zones", []) or []:
            text = text_value(zone)
            if text:
                counts[text] += int(pool.get("nodes", 0) or 0)
    return counts


def worker_pool_single_zone_pools(worker_pools):
    return [
        {"type": p.get("type", "unknown"), "nodes": p.get("nodes", 0), "zones": p.get("zones", []), "evidence_source": "cluster current-state worker pools"}
        for p in worker_pools
        if len(p.get("zones", []) or []) == 1 and int(p.get("nodes", 0) or 0) > 1
    ]


def machine_set_pool_name(name, zone):
    text = text_value(name)
    if zone and text.endswith("-" + zone):
        return text[: -(len(zone) + 1)] or text
    return text or "unknown"


def build_single_zone_machine_pools(machine_sets):
    pools = {}
    for item in machine_sets:
        zone = item.get("zone", "")
        pool = machine_set_pool_name(item.get("name"), zone)
        pools.setdefault(pool, {"type": pool, "nodes": 0, "zones": set()})
        replicas = item.get("replicas")
        if isinstance(replicas, int):
            pools[pool]["nodes"] += replicas
        if zone:
            pools[pool]["zones"].add(zone)
    rows = []
    for pool in pools.values():
        zones = sorted(pool["zones"])
        if len(zones) == 1 and pool["nodes"] > 1:
            rows.append({"type": pool["type"], "nodes": pool["nodes"], "zones": zones, "evidence_source": "Machine API worker-pool resources"})
    return rows


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
        zone = derive_node_failure_domain(node)
        if zone:
            worker_zone_counts[str(zone)] += 1
        else:
            unlabeled_worker_nodes += 1
    worker_pools = data.get("worker_pools", []) or []
    worker_pool_counts = worker_pool_zone_counts(worker_pools)
    worker_failure_domain_source = "node-labels-or-provider-id" if worker_zone_counts else "not-derived"
    if not worker_zone_counts and worker_pool_counts:
        worker_zone_counts.update(worker_pool_counts)
        worker_failure_domain_source = "cluster-current-state-worker-pools"
    single_zone_pools = worker_pool_single_zone_pools(worker_pools)
    zone_counts = list(worker_zone_counts.values())
    zone_spread_unbalanced = (max(zone_counts) - min(zone_counts) > 1) if len(zone_counts) > 1 else False
    machineset_summary = []
    machine_set_zone_counts = Counter()
    machine_set_domains = set()
    machinesets_without_zone = 0
    replicas = []
    for item in data.get("machinesets", []):
        meta = item.get("metadata", {}) or {}
        zone = derive_machineset_failure_domain(item)
        replicas_value = replica_value(item)
        if replicas_value is not None:
            replicas.append(replicas_value)
        if zone:
            machine_set_domains.add(str(zone))
            machine_set_zone_counts[str(zone)] += replicas_value if replicas_value is not None else 0
        else:
            machinesets_without_zone += 1
        machineset_summary.append({"namespace": meta.get("namespace", "openshift-machine-api"), "name": meta.get("name", "unknown"), "replicas": replicas_value if replicas_value is not None else "unknown", "zone": zone or "not-assessed"})
    machine_zone_counts = Counter()
    for item in data.get("machines", []) or []:
        zone = derive_machine_failure_domain(item)
        if zone:
            machine_zone_counts[str(zone)] += 1
    if not machine_set_zone_counts and machine_zone_counts:
        machine_set_zone_counts.update(machine_zone_counts)
        machine_set_domains.update(machine_zone_counts.keys())
    if not worker_zone_counts and machine_set_domains:
        worker_zone_counts.update({zone: machine_set_zone_counts.get(zone, 0) for zone in machine_set_domains})
        worker_failure_domain_source = "machine-api"
    if not single_zone_pools and machineset_summary:
        single_zone_pools = build_single_zone_machine_pools(machineset_summary)
    machine_zone_values = list(machine_set_zone_counts.values())
    machineset_replica_unbalanced = (max(machine_zone_values) - min(machine_zone_values) > 1) if len(machine_zone_values) > 1 and any(machine_zone_values) else False
    print(json.dumps({
        "worker_failure_domains_observed": sorted(worker_zone_counts.keys()),
        "worker_failure_domain_source": worker_failure_domain_source,
        "worker_zone_counts": [{"zone": z, "nodes": worker_zone_counts[z]} for z in sorted(worker_zone_counts.keys())],
        "worker_nodes_without_zone_label": unlabeled_worker_nodes,
        "single_zone_worker_pools": single_zone_pools,
        "single_zone_worker_pool_count": len(single_zone_pools),
        "worker_zone_spread_unbalanced": zone_spread_unbalanced,
        "machineset_summary": machineset_summary,
        "machine_set_failure_domains_observed": sorted(machine_set_domains),
        "machine_set_zone_counts": [{"zone": z, "replicas": machine_set_zone_counts[z]} for z in sorted(machine_set_zone_counts.keys())],
        "machinesets_without_zone_label": machinesets_without_zone,
        "machineset_replica_unbalanced": machineset_replica_unbalanced,
        "machine_api_evidence_source": "machinesets" if machineset_summary else ("machines" if machine_zone_counts else "not-collected"),
    }))


if __name__ == "__main__":
    main()
