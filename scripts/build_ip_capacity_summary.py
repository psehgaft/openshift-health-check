#!/usr/bin/env python3
import ipaddress
import json
import sys

from openshift_network_extract import dedupe_preserve_order, extract_install_config_networks, normalize_cidrs


def infer_network_from_ips(ip_texts):
    ip_objects = []
    for ip_text in ip_texts:
        try:
            ip_objects.append(ipaddress.ip_address(ip_text))
        except Exception:
            pass
    if not ip_objects:
        return []

    families = {}
    for ip_obj in ip_objects:
        families.setdefault(ip_obj.version, []).append(ip_obj)

    inferred = []
    for family_ips in families.values():
        min_int = min(int(ip) for ip in family_ips)
        max_int = max(int(ip) for ip in family_ips)
        max_prefixlen = family_ips[0].max_prefixlen
        differing_bits = min_int ^ max_int
        prefixlen = max_prefixlen
        while differing_bits:
            differing_bits >>= 1
            prefixlen -= 1
        network_int = min_int & ~((1 << (max_prefixlen - prefixlen)) - 1) if prefixlen < max_prefixlen else min_int
        inferred.append(str(ipaddress.ip_network((network_int, prefixlen), strict=False)))
    return inferred


def collect_cidrs_by_keys(raw, key_names):
    cidrs = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            if str(key).lower() in key_names:
                cidrs.extend(normalize_cidrs(value if isinstance(value, list) else [value]))
            cidrs.extend(collect_cidrs_by_keys(value, key_names))
    elif isinstance(raw, list):
        for item in raw:
            cidrs.extend(collect_cidrs_by_keys(item, key_names))
    return cidrs


def parse_networks(cidrs):
    parsed = []
    for cidr in cidrs:
        try:
            parsed.append(ipaddress.ip_network(cidr, strict=False))
        except Exception:
            pass
    return parsed


def unique_service_ips(services):
    values = set()
    for item in services:
        spec = item.get("spec", {}) or {}
        cluster_ip = spec.get("clusterIP")
        if cluster_ip and cluster_ip not in {"None", "none", ""}:
            values.add(str(cluster_ip))
        for ip in spec.get("clusterIPs", []) or []:
            if ip and ip not in {"None", "none", ""}:
                values.add(str(ip))
    return sorted(values)


def unique_pod_ips(pods):
    values = set()
    for item in pods:
        status = item.get("status", {}) or {}
        pod_ip = status.get("podIP")
        if pod_ip:
            values.add(str(pod_ip))
        for ip_entry in status.get("podIPs", []) or []:
            ip = (ip_entry or {}).get("ip")
            if ip:
                values.add(str(ip))
    return sorted(values)


def unique_node_internal_ips(nodes):
    values = set()
    for item in nodes:
        status = item.get("status", {}) or {}
        for entry in status.get("addresses", []) or []:
            if (entry or {}).get("type") == "InternalIP":
                ip = (entry or {}).get("address")
                if ip:
                    values.add(str(ip))
    return sorted(values)


def extract_node_cidrs(data):
    cluster_profile = data.get("cluster_profile", {}) or {}
    cluster_profile_cidrs = normalize_cidrs(cluster_profile.get("machine_networks", []))
    if cluster_profile_cidrs:
        return dedupe_preserve_order(cluster_profile_cidrs), "cluster_profile.machine_networks"

    install_config_networks = extract_install_config_networks(
        [data.get("configmaps", []), data.get("secrets", [])]
    )
    install_config_machine_networks = normalize_cidrs(install_config_networks.get("machine_networks", []))
    if install_config_machine_networks:
        return dedupe_preserve_order(install_config_machine_networks), "install-config.machine_networks"

    key_names = {"machinenetwork", "machinenetworks", "machinecidr", "machinecidrs"}
    for source_name in ("infrastructure", "network_config", "machinesets", "configmaps", "secrets"):
        cluster_defined_cidrs = dedupe_preserve_order(
            collect_cidrs_by_keys(data.get(source_name, {}), key_names)
        )
        if cluster_defined_cidrs:
            return cluster_defined_cidrs, source_name

    inferred_node_cidrs = infer_network_from_ips(unique_node_internal_ips(data.get("nodes", [])))
    if inferred_node_cidrs:
        return inferred_node_cidrs, "observed-node-ips"

    return [], "not-found"


def summarize(cidrs, observed_ips, source="unknown"):
    networks = parse_networks(cidrs)
    entries = []
    observed_inside = set()
    observed_outside = []

    for ip_text in observed_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except Exception:
            continue
        matched = False
        for network in networks:
            if ip_obj in network:
                observed_inside.add(ip_text)
                matched = True
                break
        if not matched:
            observed_outside.append(ip_text)

    for network in networks:
        taken = 0
        for ip_text in observed_inside:
            try:
                if ipaddress.ip_address(ip_text) in network:
                    taken += 1
            except Exception:
                pass
        total = int(network.num_addresses)
        entries.append({
            "cidr": str(network),
            "total_ips": total,
            "taken_ips": taken,
            "available_ips": max(total - taken, 0),
        })

    return {
        "source": source,
        "ranges": entries,
        "range_count": len(entries),
        "range_list": [item["cidr"] for item in entries],
        "total_ips": sum(item["total_ips"] for item in entries) if entries else "unknown",
        "taken_ips": len(observed_inside),
        "available_ips": (sum(item["total_ips"] for item in entries) - len(observed_inside)) if entries else "unknown",
        "observed_ips": len(observed_ips),
        "observed_out_of_range_count": len(observed_outside),
        "observed_out_of_range_sample": observed_outside[:10],
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_ip_capacity_summary.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    install_config_networks = extract_install_config_networks(
        [data.get("configmaps", []), data.get("secrets", [])]
    )
    cluster_profile = data.get("cluster_profile", {}) or {}
    service_cidrs = normalize_cidrs(cluster_profile.get("service_networks", []))
    service_cidr_source = "cluster_profile.service_networks"
    if not service_cidrs:
        service_cidrs = normalize_cidrs(install_config_networks.get("service_networks", []))
        service_cidr_source = "install-config.service_networks"
    pod_cidrs = normalize_cidrs(cluster_profile.get("cluster_networks", []))
    pod_cidr_source = "cluster_profile.cluster_networks"
    if not pod_cidrs:
        pod_cidrs = normalize_cidrs(install_config_networks.get("cluster_networks", []))
        pod_cidr_source = "install-config.cluster_networks"
    node_cidrs, node_cidr_source = extract_node_cidrs(data)

    result = {
        "service_ip_capacity_summary": summarize(service_cidrs, unique_service_ips(data.get("services", [])), source=service_cidr_source),
        "pod_ip_capacity_summary": summarize(pod_cidrs, unique_pod_ips(data.get("pods", [])), source=pod_cidr_source),
        "node_ip_capacity_summary": summarize(node_cidrs, unique_node_internal_ips(data.get("nodes", [])), source=node_cidr_source),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
