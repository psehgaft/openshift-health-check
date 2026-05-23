#!/usr/bin/env python3
import ipaddress
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

from openshift_network_extract import extract_install_config_networks


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


def sum_runtime_metric(data, result_key, signal_name, multiplier=1.0):
    total = 0.0
    seen = False
    for item in runtime_signal_rows(data, result_key, signal_name):
        value = metric_value_float(item, multiplier=multiplier)
        if value is None:
            continue
        total += value
        seen = True
    return total if seen else None


def runtime_signal_entry(data, name):
    return ((data.get("runtime_signal_resolution_map") or {}).get(name)) or {}


def runtime_signal_rows(data, result_key, signal_name):
    rows = data.get(result_key, []) or []
    if rows:
        return rows
    entry = runtime_signal_entry(data, signal_name)
    value = entry.get("value", []) if isinstance(entry, dict) else []
    return value if isinstance(value, list) else []


def normalize_items(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            return items
    return []


def is_pod_healthy(pod):
    status = (pod.get("status", {}) or {}) if isinstance(pod, dict) else {}
    phase = str(status.get("phase") or "Unknown")
    if phase == "Succeeded":
        return True
    if phase != "Running":
        return False
    statuses = status.get("containerStatuses") or []
    if not isinstance(statuses, list) or not statuses:
        return False
    return all(bool((item or {}).get("ready")) for item in statuses)


def signal_kind(entry, observed_label="utilization", derived_label="requested-pressure"):
    if (entry or {}).get("status") == "observed":
        return observed_label
    if (entry or {}).get("status") == "derived":
        return derived_label
    return "unavailable"


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
    pod_cpu_signal = runtime_signal_entry(data, "pod_cpu_usage_all")
    pod_memory_signal = runtime_signal_entry(data, "pod_memory_usage_all")
    cpu_usage_by_ns = defaultdict(float)
    for item in runtime_signal_rows(data, "pod_cpu_usage_all_results", "pod_cpu_usage_all"):
        namespace = (item.get("metric", {}) or {}).get("namespace") or ""
        if not namespace:
            continue
        value = metric_value_float(item, multiplier=1000.0)
        if value is not None:
            cpu_usage_by_ns[namespace] += value

    memory_usage_by_ns = defaultdict(float)
    for item in runtime_signal_rows(data, "pod_memory_usage_all_results", "pod_memory_usage_all"):
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
                "cpu_signal_status": "observed" if cpu_usage_observed else "derived",
                "cpu_signal_kind": (
                    "usage" if cpu_usage_observed else "requested-pressure"
                ),
                "cpu_signal_method": (
                    (pod_cpu_signal.get("method") or "prometheus-query")
                    if cpu_usage_observed
                    else "request-derived-namespace-sum"
                ),
                "cpu_is_approximation": not cpu_usage_observed,
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
                "memory_signal_status": "observed" if memory_usage_observed else "derived",
                "memory_signal_kind": (
                    "usage" if memory_usage_observed else "requested-pressure"
                ),
                "memory_signal_method": (
                    (pod_memory_signal.get("method") or "prometheus-query")
                    if memory_usage_observed
                    else "request-derived-namespace-sum"
                ),
                "memory_is_approximation": not memory_usage_observed,
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


def build_node_growth_capacity(cluster_profile, node_count, node_ip_capacity, fallback_cluster_networks=None):
    cluster_networks = (cluster_profile or {}).get("cluster_networks", []) or []
    if not cluster_networks:
        cluster_networks = fallback_cluster_networks or []
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


def compute_effective_ip_growth(
    service_ip_capacity,
    pod_ip_capacity,
    workload_node_pod_capacity,
    workload_node_scheduled_pods,
):
    service_summary = dict(service_ip_capacity or {})
    pod_summary = dict(pod_ip_capacity or {})

    service_available = service_summary.get("available_ips", "unknown")
    if isinstance(service_available, bool):
        service_available = "unknown"
    effective_additional_services = int(service_available) if isinstance(service_available, (int, float)) else "unknown"

    remaining_workload_pod_slots = "unknown"
    if (
        isinstance(workload_node_pod_capacity, int)
        and workload_node_pod_capacity >= 0
        and isinstance(workload_node_scheduled_pods, int)
        and workload_node_scheduled_pods >= 0
    ):
        remaining_workload_pod_slots = max(workload_node_pod_capacity - workload_node_scheduled_pods, 0)

    pod_available = pod_summary.get("available_ips", "unknown")
    if isinstance(pod_available, bool):
        pod_available = "unknown"
    if isinstance(pod_available, (int, float)) and isinstance(remaining_workload_pod_slots, int):
        effective_additional_pods = min(int(pod_available), remaining_workload_pod_slots)
    elif isinstance(pod_available, (int, float)):
        effective_additional_pods = int(pod_available)
    else:
        effective_additional_pods = (
            remaining_workload_pod_slots if isinstance(remaining_workload_pod_slots, int) else "unknown"
        )

    service_summary["effective_additional_services"] = effective_additional_services
    pod_summary["workload_node_pod_capacity"] = (
        workload_node_pod_capacity
        if isinstance(workload_node_pod_capacity, int) and workload_node_pod_capacity >= 0
        else "unknown"
    )
    pod_summary["workload_node_scheduled_pods"] = (
        workload_node_scheduled_pods
        if isinstance(workload_node_scheduled_pods, int) and workload_node_scheduled_pods >= 0
        else "unknown"
    )
    pod_summary["remaining_workload_pod_slots"] = remaining_workload_pod_slots
    pod_summary["max_additional_hostable_pods"] = effective_additional_pods
    return service_summary, pod_summary


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as fh:
        data = json.load(fh)

    pod_items = normalize_items(data.get("pods"))
    resourcequota_items = normalize_items(data.get("resourcequotas"))
    try:
        cluster_max_pods_per_node_default = int(data.get("cluster_max_pods_per_node_default", 250) or 250)
    except Exception:
        cluster_max_pods_per_node_default = 250
    node_pod_count_map = dict(data.get("node_pod_counts") or {})
    derived_node_pod_counts = Counter()
    for pod in pod_items:
        node_name = (((pod.get("spec", {}) or {}).get("nodeName")) or "").strip()
        if node_name:
            derived_node_pod_counts[node_name] += 1
    for node_name, count in derived_node_pod_counts.items():
        node_pod_count_map[node_name] = max(int(node_pod_count_map.get(node_name, 0) or 0), int(count))

    pod_total_count = len(pod_items)
    running_pod_count = sum(
        1 for pod in pod_items if (((pod.get("status", {}) or {}).get("phase")) == "Running")
    )
    healthy_pod_count = sum(1 for pod in pod_items if is_pod_healthy(pod))
    unhealthy_pod_count = max(0, pod_total_count - healthy_pod_count)
    healthy_pod_ratio_pct = round((healthy_pod_count / pod_total_count) * 100.0, 1) if pod_total_count > 0 else None
    unhealthy_pod_ratio_pct = round((unhealthy_pod_count / pod_total_count) * 100.0, 1) if pod_total_count > 0 else None

    node_cpu_signal = runtime_signal_entry(data, "node_cpu_utilization")
    node_memory_signal = runtime_signal_entry(data, "node_memory_utilization")
    node_disk_signal = runtime_signal_entry(data, "node_disk_utilization")
    pod_density_signal = runtime_signal_entry(data, "kubelet_pod_density")

    cpu_util_by_node = {}
    for item in runtime_signal_rows(data, "node_cpu_utilization_results", "node_cpu_utilization"):
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
    for item in runtime_signal_rows(data, "node_memory_utilization_results", "node_memory_utilization"):
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
    for item in runtime_signal_rows(data, "node_disk_utilization_results", "node_disk_utilization"):
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
    for item in runtime_signal_rows(data, "kubelet_pod_density_results", "kubelet_pod_density"):
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
    total_pod_capacity = 0
    workload_node_pod_capacity = 0
    workload_node_scheduled_pods = 0
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
        try:
            pods_allocatable = int(allocatable.get("pods", cluster_max_pods_per_node_default) or cluster_max_pods_per_node_default)
        except Exception:
            pods_allocatable = int(cluster_max_pods_per_node_default)
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
        node_is_workload_hosting = (
            primary_role not in {"master", "control-plane", "infra"}
            and not bool(spec.get("unschedulable", False))
            and any(
                (condition or {}).get("type") == "Ready" and (condition or {}).get("status") == "True"
                for condition in (status.get("conditions") or [])
            )
        )
        try:
            total_pod_capacity += pods_allocatable
            if node_is_workload_hosting:
                workload_node_pod_capacity += pods_allocatable
        except Exception:
            pass
        scheduled_pods = int(node_pod_count_map.get(node_name, 0) or 0)
        total_pods_scheduled += scheduled_pods
        if node_is_workload_hosting:
            workload_node_scheduled_pods += scheduled_pods
        cpu_util_pct = cpu_util_by_node.get(node_name)
        memory_util_pct = mem_util_by_node.get(node_name)
        cpu_available_millicores = None
        memory_available_mib = None
        if cpu_util_pct is not None:
            cpu_available_millicores = max((cpu_cores * 1000.0) * (1.0 - (cpu_util_pct / 100.0)), 0.0)
        if memory_util_pct is not None:
            memory_available_mib = max((memory_bytes / (1024 ** 2)) * (1.0 - (memory_util_pct / 100.0)), 0.0)
        disk_util_pct = disk_util_by_node.get(node_name)
        pod_density_pct = density_by_node.get(node_name)
        node_resource_rows.append(
            {
                "node": node_name,
                "role": primary_role,
                "cpu_allocatable_millicores": int(round(cpu_cores * 1000.0)),
                "cpu_available_millicores": round(cpu_available_millicores, 1) if cpu_available_millicores is not None else None,
                "cpu_utilization_pct": round(cpu_util_pct, 1) if cpu_util_pct is not None else None,
                "cpu_signal_status": node_cpu_signal.get("status", "not-collected"),
                "cpu_signal_source": node_cpu_signal.get("source", "unavailable"),
                "cpu_signal_method": node_cpu_signal.get("method", "not-collected"),
                "cpu_signal_kind": signal_kind(node_cpu_signal),
                "cpu_is_approximation": bool(node_cpu_signal.get("is_approximation", False)),
                "memory_allocatable_mib": int(round(memory_bytes / (1024 ** 2))),
                "memory_available_mib": round(memory_available_mib, 1) if memory_available_mib is not None else None,
                "memory_utilization_pct": round(memory_util_pct, 1) if memory_util_pct is not None else None,
                "memory_signal_status": node_memory_signal.get("status", "not-collected"),
                "memory_signal_source": node_memory_signal.get("source", "unavailable"),
                "memory_signal_method": node_memory_signal.get("method", "not-collected"),
                "memory_signal_kind": signal_kind(node_memory_signal),
                "memory_is_approximation": bool(node_memory_signal.get("is_approximation", False)),
                "disk_utilization_pct": round(disk_util_pct, 1) if disk_util_pct is not None else None,
                "disk_signal_status": node_disk_signal.get("status", "not-collected"),
                "disk_signal_source": node_disk_signal.get("source", "unavailable"),
                "disk_signal_method": node_disk_signal.get("method", "not-collected"),
                "disk_signal_kind": signal_kind(node_disk_signal),
                "disk_is_approximation": bool(node_disk_signal.get("is_approximation", False)),
                "pod_count": scheduled_pods,
                "pod_density_pct": round(pod_density_pct, 1) if pod_density_pct is not None else None,
                "pod_density_signal_status": pod_density_signal.get("status", "not-collected"),
                "pod_density_signal_source": pod_density_signal.get("source", "unavailable"),
                "pod_density_signal_method": pod_density_signal.get("method", "not-collected"),
                "pod_density_signal_kind": signal_kind(pod_density_signal, observed_label="density", derived_label="density"),
                "pod_density_is_approximation": bool(pod_density_signal.get("is_approximation", False)),
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

    install_config_networks = extract_install_config_networks(
        [data.get("configmaps", []), data.get("secrets", [])]
    )
    node_growth_capacity = build_node_growth_capacity(
        data.get("cluster_profile") or {},
        len(data.get("nodes", [])),
        data.get("node_ip_capacity_summary") or {},
        install_config_networks.get("cluster_networks", []),
    )
    service_ip_capacity, pod_ip_capacity = compute_effective_ip_growth(
        data.get("service_ip_capacity_summary") or {},
        data.get("pod_ip_capacity_summary") or {},
        workload_node_pod_capacity,
        workload_node_scheduled_pods,
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
    average_cpu_signal_kind = signal_kind(node_cpu_signal)
    average_cpu_signal_status = node_cpu_signal.get("status", "not-collected")
    average_cpu_signal_source = node_cpu_signal.get("source", "unavailable")
    average_cpu_signal_method = node_cpu_signal.get("method", "not-collected")
    average_cpu_is_approximation = bool(node_cpu_signal.get("is_approximation", False))
    average_memory_signal_kind = signal_kind(node_memory_signal)
    average_memory_signal_status = node_memory_signal.get("status", "not-collected")
    average_memory_signal_source = node_memory_signal.get("source", "unavailable")
    average_memory_signal_method = node_memory_signal.get("method", "not-collected")
    average_memory_is_approximation = bool(node_memory_signal.get("is_approximation", False))
    if average_cpu_utilization_pct is None and total_cpu_cores > 0:
        pod_cpu_signal = runtime_signal_entry(data, "pod_cpu_usage_all")
        pod_cpu_usage_cores = sum_runtime_metric(data, "pod_cpu_usage_all_results", "pod_cpu_usage_all")
        if pod_cpu_usage_cores is not None:
            average_cpu_utilization_pct = round((pod_cpu_usage_cores / total_cpu_cores) * 100.0, 1)
            pod_cpu_status = pod_cpu_signal.get("status", "observed")
            average_cpu_signal_status = pod_cpu_status
            average_cpu_signal_source = pod_cpu_signal.get("source", "pod_cpu_usage_all")
            average_cpu_signal_method = pod_cpu_signal.get("method", "pod-usage-sum")
            average_cpu_signal_kind = "workload-usage" if pod_cpu_status == "observed" else "requested-pressure"
            average_cpu_is_approximation = True
    if average_memory_utilization_pct is None and total_memory_bytes > 0:
        pod_memory_signal = runtime_signal_entry(data, "pod_memory_usage_all")
        pod_memory_usage_bytes = sum_runtime_metric(data, "pod_memory_usage_all_results", "pod_memory_usage_all")
        if pod_memory_usage_bytes is not None:
            average_memory_utilization_pct = round((pod_memory_usage_bytes / total_memory_bytes) * 100.0, 1)
            pod_memory_status = pod_memory_signal.get("status", "observed")
            average_memory_signal_status = pod_memory_status
            average_memory_signal_source = pod_memory_signal.get("source", "pod_memory_usage_all")
            average_memory_signal_method = pod_memory_signal.get("method", "pod-usage-sum")
            average_memory_signal_kind = "workload-usage" if pod_memory_status == "observed" else "requested-pressure"
            average_memory_is_approximation = True
    namespace_data = dict(data)
    namespace_data["pods"] = pod_items
    namespace_data["resourcequotas"] = resourcequota_items
    namespace_resource_rows = build_namespace_resource_summary(namespace_data, total_cpu_cores, total_memory_bytes)

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
            "pods": max(int((data.get("pod_object_counts") or {}).get("total", 0) or 0), pod_total_count),
            "running_pods": max(int((data.get("pod_object_counts") or {}).get("running", 0) or 0), running_pod_count),
            "healthy_pods": healthy_pod_count,
            "unhealthy_pods": unhealthy_pod_count,
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
            "average_pod_density_signal_status": pod_density_signal.get("status", "not-collected"),
            "average_pod_density_signal_source": pod_density_signal.get("source", "unavailable"),
            "average_pod_density_signal_method": pod_density_signal.get("method", "not-collected"),
            "average_pod_density_signal_kind": signal_kind(pod_density_signal, observed_label="density", derived_label="density"),
            "average_pod_density_is_approximation": bool(pod_density_signal.get("is_approximation", False)),
            "average_cpu_utilization_pct": average_cpu_utilization_pct,
            "average_cpu_signal_status": average_cpu_signal_status,
            "average_cpu_signal_source": average_cpu_signal_source,
            "average_cpu_signal_method": average_cpu_signal_method,
            "average_cpu_signal_kind": average_cpu_signal_kind,
            "average_cpu_is_approximation": average_cpu_is_approximation,
            "average_memory_utilization_pct": average_memory_utilization_pct,
            "average_memory_signal_status": average_memory_signal_status,
            "average_memory_signal_source": average_memory_signal_source,
            "average_memory_signal_method": average_memory_signal_method,
            "average_memory_signal_kind": average_memory_signal_kind,
            "average_memory_is_approximation": average_memory_is_approximation,
            "average_disk_utilization_pct": average_disk_utilization_pct,
            "average_disk_signal_status": node_disk_signal.get("status", "not-collected"),
            "average_disk_signal_source": node_disk_signal.get("source", "unavailable"),
            "average_disk_signal_method": node_disk_signal.get("method", "not-collected"),
            "average_disk_signal_kind": signal_kind(node_disk_signal),
            "average_disk_is_approximation": bool(node_disk_signal.get("is_approximation", False)),
            "healthy_pod_ratio_pct": healthy_pod_ratio_pct,
            "unhealthy_pod_ratio_pct": unhealthy_pod_ratio_pct,
        },
        "ip_capacity": {
            "services": service_ip_capacity,
            "pods": pod_ip_capacity,
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
