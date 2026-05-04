#!/usr/bin/env python3
import ipaddress
import json
import sys
from collections import Counter, defaultdict


def parse_cpu(value):
    if value in (None, ""):
        return 0.0
    s = str(value).strip()
    if s.endswith("m"):
        return float(s[:-1]) / 1000.0
    return float(s)


def parse_binary_bytes(value):
    if value in (None, ""):
        return 0.0
    s = str(value).strip()
    multipliers = {
        "Ki": 1024,
        "Mi": 1024 ** 2,
        "Gi": 1024 ** 3,
        "Ti": 1024 ** 4,
        "Pi": 1024 ** 5,
        "Ei": 1024 ** 6,
        "K": 1000,
        "M": 1000 ** 2,
        "G": 1000 ** 3,
        "T": 1000 ** 4,
        "P": 1000 ** 5,
        "E": 1000 ** 6,
    }
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            return float(s[:-len(suffix)]) * mult
    return float(s)


def summarize_counter(counter, key_name, value_name="count", limit=10):
    return [
        {key_name: key, value_name: value}
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    ][:limit]


def choose_primary_role(roles):
    if "master" in roles:
        return "master"
    if "control-plane" in roles:
        return "control-plane"
    if "infra" in roles:
        return "infra"
    if "worker" in roles:
        return "worker"
    return sorted(roles)[0] if roles else "worker"


def classify_provider(provider_id):
    text = str(provider_id or "").lower()
    if text.startswith("aws://"):
        return "aws"
    if text.startswith("azure://"):
        return "azure"
    if text.startswith("gce://"):
        return "gcp"
    if text.startswith("vsphere://"):
        return "vsphere"
    if text.startswith("openstack://"):
        return "openstack"
    if text.startswith("ibm://"):
        return "ibmcloud"
    if text.startswith("nutanix://"):
        return "nutanix"
    if text.startswith("oirt://") or text.startswith("ovirt://"):
        return "ovirt"
    if text.startswith("libvirt://"):
        return "libvirt"
    return "unknown"


def build_node_growth_capacity(cluster_profile, node_count, node_ip_capacity):
    cluster_networks = (cluster_profile or {}).get("cluster_networks", []) or []
    network_slot_details = []
    total_node_slots = 0

    for item in cluster_networks:
        if isinstance(item, dict):
            cidr = item.get("cidr") or item.get("CIDR")
            host_prefix = item.get("hostPrefix")
        else:
            cidr = str(item)
            host_prefix = None
        try:
            network = ipaddress.ip_network(str(cidr), strict=False)
        except Exception:
            continue
        try:
            host_prefix_int = int(host_prefix)
        except Exception:
            host_prefix_int = None
        node_slots = "unknown"
        if host_prefix_int is not None and host_prefix_int >= network.prefixlen:
            node_slots = int(2 ** (host_prefix_int - network.prefixlen))
            total_node_slots += node_slots
        network_slot_details.append({
            "cidr": str(network),
            "host_prefix": host_prefix if host_prefix is not None else "unknown",
            "node_slots": node_slots,
        })

    max_nodes_by_pod_network = total_node_slots if total_node_slots > 0 else "unknown"
    additional_nodes_by_pod_network = max(total_node_slots - node_count, 0) if total_node_slots > 0 else "unknown"
    pod_network_headroom_pct = round((max(total_node_slots - node_count, 0) / total_node_slots) * 100.0, 1) if total_node_slots > 0 else "unknown"

    node_ip_available = (node_ip_capacity or {}).get("available_ips", "unknown")
    if isinstance(node_ip_available, bool):
        node_ip_available = "unknown"
    if isinstance(node_ip_available, (int, float)):
        effective_additional_nodes = min(max(total_node_slots - node_count, 0), int(node_ip_available)) if total_node_slots > 0 else int(node_ip_available)
    else:
        effective_additional_nodes = additional_nodes_by_pod_network if total_node_slots > 0 else "unknown"

    return {
        "current_nodes": int(node_count),
        "max_nodes_by_pod_network": max_nodes_by_pod_network,
        "additional_nodes_by_pod_network": additional_nodes_by_pod_network,
        "pod_network_headroom_pct": pod_network_headroom_pct,
        "node_ip_ranges": (node_ip_capacity or {}).get("range_list", []) or [],
        "node_ips_taken": (node_ip_capacity or {}).get("taken_ips", 0),
        "node_ips_available": node_ip_available,
        "effective_additional_nodes": effective_additional_nodes,
        "network_slot_details": network_slot_details,
    }


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    role_counts = Counter()
    arch_counts = Counter()
    os_image_counts = Counter()
    runtime_counts = Counter()
    kubelet_counts = Counter()
    provider_counts = Counter()
    total_cpu_cores = 0.0
    total_memory_bytes = 0.0
    total_disk_bytes = 0.0
    total_pods_scheduled = 0
    worker_pool_counts = defaultdict(int)
    worker_pool_zones = defaultdict(set)

    for node in data["nodes"]:
        meta = node.get("metadata", {}) or {}
        labels = meta.get("labels", {}) or {}
        status = node.get("status", {}) or {}
        spec = node.get("spec", {}) or {}
        node_info = status.get("nodeInfo", {}) or {}
        roles = []
        for key in labels:
            if key.startswith("node-role.kubernetes.io/"):
                roles.append(key.replace("node-role.kubernetes.io/", "", 1) or "worker")
        primary_role = choose_primary_role(roles)
        role_counts[primary_role] += 1
        arch = node_info.get("architecture", "unknown")
        arch_counts[arch] += 1
        os_image_counts[node_info.get("osImage", "unknown")] += 1
        runtime_counts[node_info.get("containerRuntimeVersion", "unknown")] += 1
        kubelet_counts[node_info.get("kubeletVersion", "unknown")] += 1
        provider = classify_provider(spec.get("providerID"))
        provider_counts[provider] += 1

        allocatable = status.get("allocatable", {}) or {}
        total_cpu_cores += parse_cpu(allocatable.get("cpu", "0"))
        total_memory_bytes += parse_binary_bytes(allocatable.get("memory", "0"))
        total_disk_bytes += parse_binary_bytes(allocatable.get("ephemeral-storage", "0"))
        total_pods_scheduled += int(data["node_pod_counts"].get(meta.get("name", ""), 0) or 0)

        if primary_role == "worker":
            instance_type = (
                labels.get("node.kubernetes.io/instance-type")
                or labels.get("beta.kubernetes.io/instance-type")
                or "unknown"
            )
            zone = (
                labels.get("topology.kubernetes.io/zone")
                or labels.get("failure-domain.beta.kubernetes.io/zone")
                or "unknown"
            )
            pool_key = (instance_type, arch, provider)
            worker_pool_counts[pool_key] += 1
            worker_pool_zones[pool_key].add(zone)

    worker_pools = []
    for (instance_type, arch, provider), count in sorted(worker_pool_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2])):
        worker_pools.append({
            "type": instance_type,
            "architecture": arch,
            "provider": provider,
            "nodes": count,
            "zones": sorted(worker_pool_zones[(instance_type, arch, provider)]),
        })

    running_pods = 0
    for pod in data["pods"]:
        if ((pod.get("status", {}) or {}).get("phase", "Unknown")) == "Running":
            running_pods += 1

    node_growth_capacity = build_node_growth_capacity(
        data.get("cluster_profile", {}) or {},
        len(data["nodes"]),
        data.get("node_ip_capacity_summary", {}) or {},
    )

    result = {
        "kubernetes_version": (summarize_counter(kubelet_counts, "version", "count", limit=10)[0]["version"] if kubelet_counts else "unknown"),
        "cluster_visibility": "unknown",
        "api_visibility": "unknown",
        "ingress_visibility": "unknown",
        "installed_at": "unknown",
        "uptime_days": "unknown",
        "uptime_human": "unknown",
        "worker_pool_count": len(worker_pools),
        "node_counts": {
            "total": len(data["nodes"]),
            "control_plane": role_counts.get("master", 0) + role_counts.get("control-plane", 0),
            "worker": role_counts.get("worker", 0),
            "infra": role_counts.get("infra", 0),
            "other": sum(v for k, v in role_counts.items() if k not in {"master", "control-plane", "worker", "infra"}),
        },
        "object_counts": {
            "namespaces": len(data["namespaces"]),
            "pods": len(data["pods"]),
            "running_pods": running_pods,
            "deployments": len(data["deployments"]),
            "statefulsets": len(data["statefulsets"]),
            "daemonsets": len(data["daemonsets"]),
            "ingresses": len(data["ingresses"]),
            "storageclasses": len(data["storageclasses"]),
        },
        "resources": {
            "total_cpu_cores": round(total_cpu_cores, 1),
            "total_cpu_millicores": int(round(total_cpu_cores * 1000.0)),
            "total_memory_gib": round(total_memory_bytes / (1024 ** 3), 1),
            "total_memory_mib": int(round(total_memory_bytes / (1024 ** 2))),
            "total_ephemeral_storage_gib": round(total_disk_bytes / (1024 ** 3), 1),
            "average_cpu_cores_per_node": round(total_cpu_cores / len(data["nodes"]), 1) if data["nodes"] else 0,
            "average_cpu_millicores_per_node": int(round((total_cpu_cores / len(data["nodes"])) * 1000.0)) if data["nodes"] else 0,
            "average_memory_gib_per_node": round((total_memory_bytes / (1024 ** 3)) / len(data["nodes"]), 1) if data["nodes"] else 0,
            "average_memory_mib_per_node": int(round((total_memory_bytes / (1024 ** 2)) / len(data["nodes"]))) if data["nodes"] else 0,
            "average_ephemeral_storage_gib_per_node": round((total_disk_bytes / (1024 ** 3)) / len(data["nodes"]), 1) if data["nodes"] else 0,
            "average_pods_per_node": round(total_pods_scheduled / len(data["nodes"]), 1) if data["nodes"] else 0,
        },
        "ip_capacity": {
            "services": data.get("service_ip_capacity_summary", {}) or {},
            "pods": data.get("pod_ip_capacity_summary", {}) or {},
            "nodes": data.get("node_ip_capacity_summary", {}) or {},
        },
        "node_growth_capacity": node_growth_capacity,
        "node_architectures": summarize_counter(arch_counts, "architecture", "count", limit=10),
        "provider_types": summarize_counter(provider_counts, "provider", "count", limit=10),
        "os_images": summarize_counter(os_image_counts, "os_image", "count", limit=10),
        "container_runtimes": summarize_counter(runtime_counts, "runtime", "count", limit=10),
        "node_roles": summarize_counter(role_counts, "role", "count", limit=10),
        "worker_pools": worker_pools[:15],
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
