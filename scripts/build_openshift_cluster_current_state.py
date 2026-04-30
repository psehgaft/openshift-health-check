#!/usr/bin/env python3
import ipaddress
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


def parse_cpu(value):
    if value in (None, ""):
        return 0.0
    s = str(value).strip()
    if s.endswith("m"):
        try:
            return float(s[:-1]) / 1000.0
        except Exception:
            return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


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
            try:
                return float(s[:-len(suffix)]) * mult
            except Exception:
                return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def iso_to_dt(value):
    if not value:
        return None
    try:
        if str(value).endswith("Z"):
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def avg(values):
    vals = [float(v) for v in values if v not in (None, "")]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


def summarize_counter(counter, key_name, value_name="count", limit=10):
    return [
        {key_name: key, value_name: value}
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))
    ][:limit]


def normalize_instance_name(raw):
    if not raw:
        return ""
    text = str(raw)
    if ":" in text:
        return text.split(":", 1)[0]
    return text


def metric_value_float(item, multiplier=1.0):
    try:
        return float((item.get("value") or [None, None])[1]) * multiplier
    except Exception:
        return None


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


def is_internal_lb_service(service):
    meta = service.get("metadata", {}) or {}
    annotations = meta.get("annotations", {}) or {}
    values = {str(v).lower() for v in annotations.values() if v not in (None, "")}
    keys = {str(k).lower() for k in annotations.keys()}

    if "true" in values and any(
        needle in key
        for key in keys
        for needle in [
            "aws-load-balancer-internal",
            "azure-load-balancer-internal",
            "gcp-load-balancer-type",
            "network-load-balancer-internal",
        ]
    ):
        return True
    if "internal" in values:
        return True
    return False


def classify_provider(provider_id, labels, platform):
    text = str(provider_id or "").lower()
    p = str(platform or "").lower()
    if text.startswith("aws://") or p == "aws":
        return "aws"
    if text.startswith("azure://") or p == "azure":
        return "azure"
    if text.startswith("gce://") or p == "gcp":
        return "gcp"
    if text.startswith("vsphere://") or p == "vsphere":
        return "vsphere"
    if text.startswith("openstack://") or p == "openstack":
        return "openstack"
    if text.startswith("ibm://") or p == "ibmcloud":
        return "ibmcloud"
    if text.startswith("nutanix://") or p == "nutanix":
        return "nutanix"
    if text.startswith("oirt://") or text.startswith("ovirt://") or p == "ovirt":
        return "ovirt"
    if text.startswith("libvirt://") or p == "libvirt":
        return "libvirt"
    if p == "baremetal":
        return "baremetal"
    if labels.get("node.openshift.io/os_id") == "rhcos":
        return "platform-managed-or-upi"
    return "unknown"


def build_node_shape(instance_type, cpu_cores, memory_gib, arch):
    if instance_type and instance_type != "unknown":
        return instance_type, "instance-type-label"
    cpu_part = int(round(cpu_cores)) if cpu_cores >= 1 else round(cpu_cores, 1)
    mem_part = int(round(memory_gib)) if memory_gib >= 1 else round(memory_gib, 1)
    return f"{cpu_part}cpu-{mem_part}gib-{arch}", "allocatable-shape"


def quota_value(quota, section_name, keys, parser):
    values = ((quota.get("status", {}) or {}).get(section_name, {}) or {})
    for key in keys:
        if key in values:
            return parser(values.get(key))
    return 0.0


def build_namespace_resource_summary(data, cluster_cpu_cores, cluster_memory_bytes):
    cpu_usage_by_ns = defaultdict(float)
    for item in data.get("pod_cpu_usage_all_results", []) or []:
        namespace = (item.get("metric", {}) or {}).get("namespace") or ""
        if not namespace:
            continue
        value = metric_value_float(item, multiplier=1000.0)
        if value is not None:
            cpu_usage_by_ns[namespace] += value

    memory_usage_by_ns = defaultdict(float)
    for item in data.get("pod_memory_usage_all_results", []) or []:
        namespace = (item.get("metric", {}) or {}).get("namespace") or ""
        if not namespace:
            continue
        value = metric_value_float(item)
        if value is not None:
            memory_usage_by_ns[namespace] += value

    requests_by_ns = defaultdict(lambda: {"cpu_millicores": 0.0, "memory_bytes": 0.0, "pods": 0})
    for pod in data.get("pods", []) or []:
        namespace = ((pod.get("metadata", {}) or {}).get("namespace")) or ""
        if not namespace:
            continue
        requests_by_ns[namespace]["pods"] += 1
        for container in (pod.get("spec", {}) or {}).get("containers", []) or []:
            requests = ((container.get("resources", {}) or {}).get("requests", {}) or {})
            requests_by_ns[namespace]["cpu_millicores"] += parse_cpu(requests.get("cpu")) * 1000.0
            requests_by_ns[namespace]["memory_bytes"] += parse_binary_bytes(requests.get("memory"))

    quota_by_ns = defaultdict(lambda: {"cpu_hard_millicores": 0.0, "cpu_used_millicores": 0.0, "memory_hard_bytes": 0.0, "memory_used_bytes": 0.0})
    for quota in data.get("resourcequotas", []) or []:
        namespace = ((quota.get("metadata", {}) or {}).get("namespace")) or ""
        if not namespace:
            continue
        quota_by_ns[namespace]["cpu_hard_millicores"] += quota_value(quota, "hard", ["requests.cpu", "limits.cpu", "cpu"], parse_cpu) * 1000.0
        quota_by_ns[namespace]["cpu_used_millicores"] += quota_value(quota, "used", ["requests.cpu", "limits.cpu", "cpu"], parse_cpu) * 1000.0
        quota_by_ns[namespace]["memory_hard_bytes"] += quota_value(quota, "hard", ["requests.memory", "limits.memory", "memory"], parse_binary_bytes)
        quota_by_ns[namespace]["memory_used_bytes"] += quota_value(quota, "used", ["requests.memory", "limits.memory", "memory"], parse_binary_bytes)

    namespaces = set(cpu_usage_by_ns) | set(memory_usage_by_ns) | set(requests_by_ns) | set(quota_by_ns)
    rows = []
    for namespace in namespaces:
        quota = quota_by_ns.get(namespace, {})
        requests = requests_by_ns.get(namespace, {})
        cpu_usage = cpu_usage_by_ns.get(namespace, 0.0)
        memory_usage = memory_usage_by_ns.get(namespace, 0.0)
        cpu_quota = float(quota.get("cpu_hard_millicores", 0.0) or 0.0)
        memory_quota = float(quota.get("memory_hard_bytes", 0.0) or 0.0)
        cpu_used_quota = float(quota.get("cpu_used_millicores", 0.0) or 0.0)
        memory_used_quota = float(quota.get("memory_used_bytes", 0.0) or 0.0)
        cpu_request = float(requests.get("cpu_millicores", 0.0) or 0.0)
        memory_request = float(requests.get("memory_bytes", 0.0) or 0.0)
        cpu_usage_observed = namespace in cpu_usage_by_ns
        memory_usage_observed = namespace in memory_usage_by_ns
        effective_cpu_millicores = cpu_usage if cpu_usage_observed else cpu_request
        effective_memory_bytes = memory_usage if memory_usage_observed else memory_request

        cpu_available = max(cpu_quota - cpu_used_quota, 0.0) if cpu_quota > 0 else None
        memory_available = max(memory_quota - memory_used_quota, 0.0) if memory_quota > 0 else None
        cpu_denominator = cpu_quota if cpu_quota > 0 else (cluster_cpu_cores * 1000.0 if cluster_cpu_cores > 0 else 0.0)
        memory_denominator = memory_quota if memory_quota > 0 else cluster_memory_bytes

        cpu_util = round((effective_cpu_millicores / cpu_denominator) * 100.0, 1) if cpu_denominator > 0 else None
        memory_util = round((effective_memory_bytes / memory_denominator) * 100.0, 1) if memory_denominator > 0 else None

        rows.append(
            {
                "namespace": namespace,
                "pod_count": int(requests.get("pods", 0) or 0),
                "cpu_usage_millicores": round(cpu_usage, 1),
                "cpu_requested_millicores": round(cpu_request, 1),
                "cpu_effective_millicores": round(effective_cpu_millicores, 1),
                "cpu_usage_source": "observed" if cpu_usage_observed else "requested",
                "cpu_usage_display": (
                    f"{round(effective_cpu_millicores, 1)}m"
                    if cpu_usage_observed
                    else f"{round(effective_cpu_millicores, 1)}m (requested)"
                ),
                "cpu_available_millicores": round(cpu_available, 1) if cpu_available is not None else None,
                "cpu_available_display": f"{round(cpu_available, 1)}m" if cpu_available is not None else "not quota-limited",
                "cpu_utilization_pct": cpu_util,
                "memory_usage_mib": round(memory_usage / (1024 ** 2), 1),
                "memory_requested_mib": round(memory_request / (1024 ** 2), 1),
                "memory_effective_mib": round(effective_memory_bytes / (1024 ** 2), 1),
                "memory_usage_source": "observed" if memory_usage_observed else "requested",
                "memory_usage_display": (
                    f"{round(effective_memory_bytes / (1024 ** 2), 1)}MiB"
                    if memory_usage_observed
                    else f"{round(effective_memory_bytes / (1024 ** 2), 1)}MiB (requested)"
                ),
                "memory_available_mib": round(memory_available / (1024 ** 2), 1) if memory_available is not None else None,
                "memory_available_display": f"{round(memory_available / (1024 ** 2), 1)}MiB" if memory_available is not None else "not quota-limited",
                "memory_utilization_pct": memory_util,
            }
        )

    rows.sort(
        key=lambda item: (
            -(item.get("memory_utilization_pct") if item.get("memory_utilization_pct") is not None else -1),
            -(item.get("cpu_utilization_pct") if item.get("cpu_utilization_pct") is not None else -1),
            -float(item.get("memory_effective_mib", 0.0) or 0.0),
            -float(item.get("cpu_effective_millicores", 0.0) or 0.0),
            str(item.get("namespace", "")),
        )
    )
    return rows[:50]


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
        network_slot_details.append(
            {
                "cidr": str(network),
                "host_prefix": host_prefix if host_prefix is not None else "unknown",
                "node_slots": node_slots,
            }
        )

    max_nodes_by_pod_network = total_node_slots if total_node_slots > 0 else "unknown"
    additional_nodes_by_pod_network = max(total_node_slots - node_count, 0) if total_node_slots > 0 else "unknown"
    pod_network_headroom_pct = (
        round((max(total_node_slots - node_count, 0) / total_node_slots) * 100.0, 1)
        if total_node_slots > 0
        else "unknown"
    )

    node_ip_available = (node_ip_capacity or {}).get("available_ips", "unknown")
    if isinstance(node_ip_available, bool):
        node_ip_available = "unknown"
    if isinstance(node_ip_available, (int, float)):
        effective_additional_nodes = (
            min(max(total_node_slots - node_count, 0), int(node_ip_available))
            if total_node_slots > 0
            else int(node_ip_available)
        )
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
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        data = json.load(fh)

    cpu_util_by_node = {}
    for item in data.get("node_cpu_utilization_results", []):
        node = normalize_instance_name(
            item.get("metric", {}).get("node")
            or item.get("metric", {}).get("kubernetes_node")
            or item.get("metric", {}).get("instance")
        )
        value = item.get("value", [None, None])[1]
        try:
            cpu_util_by_node[node] = float(value)
        except Exception:
            pass

    mem_util_by_node = {}
    for item in data.get("node_memory_utilization_results", []):
        node = normalize_instance_name(
            item.get("metric", {}).get("node")
            or item.get("metric", {}).get("kubernetes_node")
            or item.get("metric", {}).get("instance")
        )
        value = item.get("value", [None, None])[1]
        try:
            mem_util_by_node[node] = float(value)
        except Exception:
            pass

    disk_util_by_node = {}
    for item in data.get("node_disk_utilization_results", []):
        node = normalize_instance_name(
            item.get("metric", {}).get("node")
            or item.get("metric", {}).get("kubernetes_node")
            or item.get("metric", {}).get("instance")
        )
        value = item.get("value", [None, None])[1]
        try:
            disk_util_by_node[node] = float(value)
        except Exception:
            pass

    density_by_node = {}
    for item in data.get("kubelet_pod_density_results", []):
        node = normalize_instance_name(item.get("metric", {}).get("node") or item.get("metric", {}).get("instance"))
        value = item.get("value", [None, None])[1]
        try:
            density_by_node[node] = float(value)
        except Exception:
            pass

    role_counts = Counter()
    arch_counts = Counter()
    os_image_counts = Counter()
    kernel_counts = Counter()
    runtime_counts = Counter()
    kubelet_counts = Counter()
    instance_type_counts = Counter()
    node_shape_counts = Counter()
    provider_type_counts = Counter()
    operating_system_counts = Counter()
    feature_counts = Counter()
    worker_pool_counts = defaultdict(int)
    worker_pool_zones = defaultdict(set)
    total_cpu_cores = 0.0
    total_memory_bytes = 0.0
    total_disk_bytes = 0.0
    total_pods_scheduled = 0
    master_nodes = 0
    worker_nodes = 0
    infra_nodes = 0
    other_nodes = 0
    node_resource_rows = []

    for node in data.get("nodes", []):
        meta = node.get("metadata", {}) or {}
        labels = meta.get("labels", {}) or {}
        status = node.get("status", {}) or {}
        spec = node.get("spec", {}) or {}
        node_name = meta.get("name", "")
        roles = []
        for key in labels:
            if key.startswith("node-role.kubernetes.io/"):
                role = key.replace("node-role.kubernetes.io/", "", 1) or "worker"
                roles.append(role)
        primary_role = choose_primary_role(roles)
        role_counts[primary_role] += 1
        if primary_role in {"master", "control-plane"}:
            master_nodes += 1
        elif primary_role == "worker":
            worker_nodes += 1
        elif primary_role == "infra":
            infra_nodes += 1
        else:
            other_nodes += 1

        node_info = status.get("nodeInfo", {}) or {}
        arch_counts[node_info.get("architecture", "unknown")] += 1
        os_image_counts[node_info.get("osImage", "unknown")] += 1
        kernel_counts[node_info.get("kernelVersion", "unknown")] += 1
        runtime_counts[node_info.get("containerRuntimeVersion", "unknown")] += 1
        kubelet_counts[node_info.get("kubeletVersion", "unknown")] += 1
        operating_system_counts[node_info.get("operatingSystem", "unknown")] += 1

        instance_type = (
            labels.get("node.kubernetes.io/instance-type")
            or labels.get("beta.kubernetes.io/instance-type")
            or labels.get("machine.openshift.io/instance-type")
            or "unknown"
        )
        instance_type_counts[instance_type] += 1
        provider_type = classify_provider(spec.get("providerID"), labels, (data.get("cluster_profile") or {}).get("platform", ""))
        provider_type_counts[provider_type] += 1

        zone = labels.get("topology.kubernetes.io/zone") or labels.get("failure-domain.beta.kubernetes.io/zone") or "unknown"
        arch = node_info.get("architecture", "unknown")
        allocatable = status.get("allocatable", {}) or {}
        cpu_cores = parse_cpu(allocatable.get("cpu", "0"))
        memory_gib = parse_binary_bytes(allocatable.get("memory", "0")) / (1024 ** 3)
        node_shape, node_shape_source = build_node_shape(instance_type, cpu_cores, memory_gib, arch)
        node_shape_counts[node_shape] += 1
        if primary_role == "worker":
            pool_key = (primary_role, node_shape, node_shape_source, arch, provider_type)
            worker_pool_counts[pool_key] += 1
            worker_pool_zones[pool_key].add(zone)

        for key, value in labels.items():
            if key.startswith("feature.node.kubernetes.io/") and str(value).lower() not in {"false", "", "0"}:
                feature_counts[key.replace("feature.node.kubernetes.io/", "", 1)] += 1

        total_cpu_cores += cpu_cores
        memory_bytes = parse_binary_bytes(allocatable.get("memory", "0"))
        total_memory_bytes += memory_bytes
        total_disk_bytes += parse_binary_bytes(allocatable.get("ephemeral-storage", "0"))
        total_pods_scheduled += int((data.get("node_pod_counts") or {}).get(node_name, 0) or 0)
        cpu_util_pct = cpu_util_by_node.get(node_name)
        memory_util_pct = mem_util_by_node.get(node_name)
        cpu_available_millicores = None
        memory_available_mib = None
        if cpu_util_pct is not None:
            cpu_available_millicores = max((cpu_cores * 1000.0) * (1.0 - (cpu_util_pct / 100.0)), 0.0)
        if memory_util_pct is not None:
            memory_available_mib = max((memory_bytes / (1024 ** 2)) * (1.0 - (memory_util_pct / 100.0)), 0.0)
        node_resource_rows.append(
            {
                "node": node_name,
                "role": primary_role,
                "cpu_allocatable_millicores": int(round(cpu_cores * 1000.0)),
                "cpu_available_millicores": round(cpu_available_millicores, 1) if cpu_available_millicores is not None else None,
                "cpu_utilization_pct": round(cpu_util_pct, 1) if cpu_util_pct is not None else None,
                "memory_allocatable_mib": int(round(memory_bytes / (1024 ** 2))),
                "memory_available_mib": round(memory_available_mib, 1) if memory_available_mib is not None else None,
                "memory_utilization_pct": round(memory_util_pct, 1) if memory_util_pct is not None else None,
                "pod_count": int((data.get("node_pod_counts") or {}).get(node_name, 0) or 0),
            }
        )

    default_ingress = None
    for ic in data.get("ingresscontrollers", []):
        if (ic.get("metadata", {}) or {}).get("name") == "default":
            default_ingress = ic
            break
    if default_ingress is None and data.get("ingresscontrollers"):
        default_ingress = data["ingresscontrollers"][0]

    ingress_visibility = "unknown"
    ingress_strategy = "unknown"
    if default_ingress:
        strategy = ((default_ingress.get("spec", {}) or {}).get("endpointPublishingStrategy", {}) or {})
        ingress_strategy = strategy.get("type", "unknown")
        scope = ((strategy.get("loadBalancer", {}) or {}).get("scope") or "").lower()
        if scope == "internal":
            ingress_visibility = "private"
        elif ingress_strategy == "LoadBalancerService" and scope in {"external", ""}:
            ingress_visibility = "public"

    if ingress_visibility == "unknown":
        router_service = None
        for svc in data.get("services", []):
            meta = svc.get("metadata", {}) or {}
            if meta.get("namespace") == "openshift-ingress" and meta.get("name") == "router-default":
                router_service = svc
                break
        if router_service:
            service_type = str(((router_service.get("spec", {}) or {}).get("type")) or "")
            if service_type == "LoadBalancer":
                ingress_visibility = "private" if is_internal_lb_service(router_service) else "public"
            elif service_type == "NodePort":
                ingress_visibility = "public"

    api_url = (((data.get("cluster_profile") or {}).get("api_url")) or "").lower()
    api_internal_url = (((data.get("cluster_profile") or {}).get("api_internal_url")) or "").lower()
    api_visibility = "unknown"
    if api_url and api_internal_url:
        if api_url == api_internal_url or ".internal." in api_url or api_url.startswith("https://api-int."):
            api_visibility = "private"
        else:
            api_visibility = "public"
    elif api_url:
        api_visibility = "private" if (".internal." in api_url or api_url.startswith("https://api-int.")) else "public"
    elif api_internal_url:
        api_visibility = "private"

    cluster_visibility = "unknown"
    if api_visibility == "private" and ingress_visibility == "private":
        cluster_visibility = "private"
    elif api_visibility == "public" or ingress_visibility == "public":
        cluster_visibility = "public"
    elif api_visibility == "private" or ingress_visibility == "private":
        cluster_visibility = "mixed"

    install_candidates = []
    cv = data.get("clusterversion") or {}
    for entry in (((cv.get("status", {}) or {}).get("history", []) or [])):
        install_candidates.append(entry.get("startedTime"))
        install_candidates.append(entry.get("completionTime"))
    install_candidates.append((cv.get("metadata", {}) or {}).get("creationTimestamp"))
    install_candidates.append(((data.get("cluster_profile") or {}).get("infrastructure_creation_timestamp")))
    for node in data.get("nodes", []):
        install_candidates.append(((node.get("metadata", {}) or {}).get("creationTimestamp")))
    install_dt_values = [iso_to_dt(x) for x in install_candidates if x]
    install_dt_values = [x for x in install_dt_values if x is not None]
    installed_at = None
    uptime_days = None
    uptime_human = "unknown"
    now_dt = iso_to_dt(data.get("report_generated_at"))
    if install_dt_values and now_dt is not None:
        installed_at_dt = min(install_dt_values)
        installed_at = installed_at_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        uptime_seconds = max(0.0, (now_dt - installed_at_dt).total_seconds())
        uptime_days = round(uptime_seconds / 86400.0, 1)
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        uptime_human = f"{days}d {hours}h"

    kube_versions = summarize_counter(kubelet_counts, "version", "count", limit=10)
    primary_kube_version = kube_versions[0]["version"] if kube_versions else "unknown"
    kubernetes_version_state = "mixed" if len(kubelet_counts) > 1 else "uniform"

    insights_available = data.get("insights_available", "Unknown")
    insights_degraded = data.get("insights_degraded", "Unknown")
    if insights_available == "Unknown" and insights_degraded == "Unknown":
        insights_status = "unknown"
    elif insights_available == "True" and insights_degraded != "True":
        insights_status = "enabled and healthy"
    elif insights_degraded == "True":
        insights_status = "enabled but degraded"
    else:
        insights_status = "configured but not healthy"

    worker_pools = []
    for (role, node_shape, node_shape_source, arch, provider_type), count in sorted(
        worker_pool_counts.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2], item[0][3]),
    ):
        worker_pools.append(
            {
                "role": role,
                "type": node_shape,
                "type_source": node_shape_source,
                "architecture": arch,
                "provider": provider_type,
                "nodes": count,
                "zones": sorted(worker_pool_zones[(role, node_shape, node_shape_source, arch, provider_type)]),
            }
        )

    mcp_summary = []
    for item in (((data.get("machineconfigpools") or {}).get("items", [])) or []):
        status = item.get("status", {}) or {}
        mcp_summary.append(
            {
                "name": (item.get("metadata", {}) or {}).get("name", "unknown"),
                "machine_count": int(status.get("machineCount", 0) or 0),
                "ready_machine_count": int(status.get("readyMachineCount", 0) or 0),
                "updated_machine_count": int(status.get("updatedMachineCount", 0) or 0),
                "degraded_machine_count": int(status.get("degradedMachineCount", 0) or 0),
            }
        )
    mcp_summary.sort(key=lambda item: str(item.get("name", "unknown")))

    node_growth_capacity = build_node_growth_capacity(
        data.get("cluster_profile") or {},
        len(data.get("nodes", [])),
        data.get("node_ip_capacity_summary") or {},
    )
    node_resource_rows.sort(
        key=lambda item: (
            -(item.get("memory_utilization_pct") if item.get("memory_utilization_pct") is not None else -1),
            -(item.get("cpu_utilization_pct") if item.get("cpu_utilization_pct") is not None else -1),
            str(item.get("node", "")),
        )
    )
    average_pod_density_pct = avg(
        [item.get("pod_density_pct") for item in node_resource_rows if item.get("pod_density_pct") not in (None, "")]
    )
    average_cpu_utilization_pct = avg(
        [item.get("cpu_utilization_pct") for item in node_resource_rows if item.get("cpu_utilization_pct") not in (None, "")]
    )
    average_memory_utilization_pct = avg(
        [item.get("memory_utilization_pct") for item in node_resource_rows if item.get("memory_utilization_pct") not in (None, "")]
    )
    average_disk_utilization_pct = avg(
        [item.get("disk_utilization_pct") for item in node_resource_rows if item.get("disk_utilization_pct") not in (None, "")]
    )
    namespace_resource_rows = build_namespace_resource_summary(data, total_cpu_cores, total_memory_bytes)

    result = {
        "ocp_version": (((cv.get("status", {}) or {}).get("desired", {}) or {}).get("version", "unknown")),
        "cluster_version_available": data.get("cv_available"),
        "cluster_version_progressing": data.get("cv_progressing"),
        "cluster_version_failing": data.get("cv_failing"),
        "kubernetes_version": primary_kube_version,
        "deployment_type": data.get("openshift_deployment_type"),
        "cluster_classification_label": data.get("openshift_cluster_classification_label"),
        "cluster_classification_source": data.get("openshift_cluster_classification_source"),
        "cluster_classification_confidence": data.get("openshift_cluster_classification_confidence"),
        "service_model": data.get("openshift_service_model"),
        "service_variant": data.get("openshift_service_variant"),
        "install_model": data.get("openshift_install_model"),
        "install_model_confidence": data.get("openshift_install_model_confidence"),
        "control_plane_model": data.get("openshift_control_plane_model"),
        "platform_category": data.get("openshift_platform_category"),
        "public_cloud": bool(data.get("openshift_public_cloud")),
        "is_sno": bool(data.get("openshift_is_sno")),
        "is_hosted_control_plane": bool(data.get("openshift_is_hosted_control_plane")),
        "kubernetes_version_state": kubernetes_version_state,
        "kubernetes_versions": kube_versions,
        "insights_status": insights_status,
        "cluster_visibility": cluster_visibility,
        "api_visibility": api_visibility,
        "ingress_visibility": ingress_visibility,
        "default_ingress_strategy": ingress_strategy,
        "installed_at": installed_at or "unknown",
        "uptime_days": uptime_days if uptime_days is not None else "unknown",
        "uptime_human": uptime_human,
        "machineconfigpool_count": int(data.get("machineconfigpool_count", 0) or 0),
        "worker_pool_count": len(worker_pools),
        "node_counts": {
            "total": len(data.get("nodes", [])),
            "control_plane": master_nodes,
            "worker": worker_nodes,
            "infra": infra_nodes,
            "other": other_nodes,
        },
        "object_counts": {
            "namespaces": int(data.get("namespace_count", 0) or 0),
            "pods": int((data.get("pod_object_counts") or {}).get("total", 0) or 0),
            "running_pods": int((data.get("pod_object_counts") or {}).get("running", 0) or 0),
            "deployments": int(data.get("deployment_count", 0) or 0),
            "statefulsets": int(data.get("statefulset_count", 0) or 0),
            "daemonsets": int(data.get("daemonset_count", 0) or 0),
            "routes": int(data.get("route_count", 0) or 0),
            "ingresses": int(data.get("ingress_count", 0) or 0),
            "storageclasses": int(data.get("storageclass_count", 0) or 0),
        },
        "resources": {
            "total_cpu_cores": round(total_cpu_cores, 1),
            "total_cpu_millicores": int(round(total_cpu_cores * 1000.0)),
            "total_memory_gib": round(total_memory_bytes / (1024 ** 3), 1),
            "total_memory_mib": int(round(total_memory_bytes / (1024 ** 2))),
            "total_ephemeral_storage_gib": round(total_disk_bytes / (1024 ** 3), 1),
            "average_cpu_cores_per_node": round(total_cpu_cores / len(data.get("nodes", [])), 1) if data.get("nodes") else 0,
            "average_cpu_millicores_per_node": int(round((total_cpu_cores / len(data.get("nodes", []))) * 1000.0)) if data.get("nodes") else 0,
            "average_memory_gib_per_node": round((total_memory_bytes / (1024 ** 3)) / len(data.get("nodes", [])), 1) if data.get("nodes") else 0,
            "average_memory_mib_per_node": int(round((total_memory_bytes / (1024 ** 2)) / len(data.get("nodes", [])))) if data.get("nodes") else 0,
            "average_ephemeral_storage_gib_per_node": round((total_disk_bytes / (1024 ** 3)) / len(data.get("nodes", [])), 1) if data.get("nodes") else 0,
            "average_pods_per_node": round(total_pods_scheduled / len(data.get("nodes", [])), 1) if data.get("nodes") else 0,
            "average_pod_density_pct": average_pod_density_pct,
            "average_cpu_utilization_pct": average_cpu_utilization_pct,
            "average_memory_utilization_pct": average_memory_utilization_pct,
            "average_disk_utilization_pct": average_disk_utilization_pct,
        },
        "ip_capacity": {
            "services": data.get("service_ip_capacity_summary", {}) or {},
            "pods": data.get("pod_ip_capacity_summary", {}) or {},
            "nodes": data.get("node_ip_capacity_summary", {}) or {},
        },
        "node_growth_capacity": node_growth_capacity,
        "node_resource_utilization": node_resource_rows,
        "namespace_resource_utilization": namespace_resource_rows,
        "node_architectures": summarize_counter(arch_counts, "architecture", "count", limit=10),
        "instance_types": summarize_counter(Counter({k: v for k, v in instance_type_counts.items() if k != "unknown"}), "instance_type", "count", limit=10),
        "node_shapes": summarize_counter(node_shape_counts, "shape", "count", limit=12),
        "provider_types": summarize_counter(provider_type_counts, "provider", "count", limit=10),
        "operating_systems": summarize_counter(operating_system_counts, "operating_system", "count", limit=10),
        "os_images": summarize_counter(os_image_counts, "os_image", "count", limit=10),
        "kernel_versions": summarize_counter(kernel_counts, "kernel_version", "count", limit=10),
        "container_runtimes": summarize_counter(runtime_counts, "runtime", "count", limit=10),
        "node_roles": summarize_counter(role_counts, "role", "count", limit=10),
        "top_node_features": summarize_counter(feature_counts, "feature", "node_count", limit=12),
        "worker_pools": worker_pools[:15],
        "machineconfigpools": mcp_summary,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
