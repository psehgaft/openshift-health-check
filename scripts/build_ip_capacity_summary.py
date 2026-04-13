#!/usr/bin/env python3
import ipaddress
import json
import sys


def normalize_cidrs(raw):
    cidrs = []
    for item in raw or []:
        if isinstance(item, str):
            value = item
        elif isinstance(item, dict):
            value = item.get("cidr") or item.get("CIDR")
        else:
            value = None
        if value:
            cidrs.append(str(value))
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


def summarize(cidrs, observed_ips):
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

    service_cidrs = normalize_cidrs((data.get("cluster_profile", {}) or {}).get("service_networks", []))
    pod_cidrs = normalize_cidrs((data.get("cluster_profile", {}) or {}).get("cluster_networks", []))
    node_cidrs = normalize_cidrs((data.get("cluster_profile", {}) or {}).get("machine_networks", []))

    result = {
        "service_ip_capacity_summary": summarize(service_cidrs, unique_service_ips(data.get("services", []))),
        "pod_ip_capacity_summary": summarize(pod_cidrs, unique_pod_ips(data.get("pods", []))),
        "node_ip_capacity_summary": summarize(node_cidrs, unique_node_internal_ips(data.get("nodes", []))),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
