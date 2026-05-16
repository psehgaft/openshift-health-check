#!/usr/bin/env python3
import json
import sys
from collections import Counter


def primary_role(labels):
    roles = []
    for key in labels:
        if key.startswith("node-role.kubernetes.io/"):
            roles.append(key.replace("node-role.kubernetes.io/", "", 1) or "worker")
    if "master" in roles:
        return "master"
    if "control-plane" in roles:
        return "control-plane"
    if "infra" in roles:
        return "infra"
    if "worker" in roles:
        return "worker"
    if roles:
        return sorted(roles)[0]
    return "worker"


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_kubernetes_topology_resilience.py <input.json>"}))
        return 1

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    worker_zone_counts = Counter()
    unlabeled_worker_nodes = 0
    for node in data.get("nodes") or []:
        meta = node.get("metadata", {}) or {}
        labels = meta.get("labels", {}) or {}
        if primary_role(labels) != "worker":
            continue
        zone = labels.get("topology.kubernetes.io/zone") or labels.get("failure-domain.beta.kubernetes.io/zone")
        if zone:
            worker_zone_counts[str(zone)] += 1
        else:
            unlabeled_worker_nodes += 1

    worker_pools = data.get("worker_pools") or []
    single_zone_pools = [pool for pool in worker_pools if len(pool.get("zones", []) or []) <= 1]
    zone_counts = list(worker_zone_counts.values())
    zone_spread_unbalanced = (max(zone_counts) - min(zone_counts) > 1) if len(zone_counts) > 1 else False

    print(
        json.dumps(
            {
                "worker_failure_domains_observed": sorted(worker_zone_counts.keys()),
                "worker_zone_counts": [
                    {"zone": zone, "nodes": worker_zone_counts[zone]}
                    for zone in sorted(worker_zone_counts.keys())
                ],
                "worker_nodes_without_zone_label": unlabeled_worker_nodes,
                "single_zone_worker_pools": [
                    {
                        "type": pool.get("type", "unknown"),
                        "nodes": pool.get("nodes", 0),
                        "zones": pool.get("zones", []),
                    }
                    for pool in single_zone_pools
                ],
                "single_zone_worker_pool_count": len(single_zone_pools),
                "worker_zone_spread_unbalanced": zone_spread_unbalanced,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
