#!/usr/bin/env python3
"""Build OpenShift platform component health facts."""

import json
import sys


def get_path(data, *path, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def condition_status(conditions, condition_type, default="Unknown"):
    for condition in conditions or []:
        if str((condition or {}).get("type") or "") == condition_type:
            return str((condition or {}).get("status") or default)
    return default


def operator_version(item):
    versions = get_path(item, "status", "versions", default=[]) or []
    if versions and isinstance(versions[0], dict):
        return str(versions[0].get("version") or "unknown")
    return "unknown"


def operator_status(item):
    conditions = get_path(item, "status", "conditions", default=[]) or []
    return {
        "available": condition_status(conditions, "Available"),
        "degraded": condition_status(conditions, "Degraded"),
        "progressing": condition_status(conditions, "Progressing"),
        "version": operator_version(item),
    }


def build_clusteroperator_facts(clusteroperators, desired_version):
    degraded = []
    unavailable = []
    progressing = []
    status_map = {}
    version_mismatches = []

    for item in clusteroperators:
        if not isinstance(item, dict):
            continue
        name = str(get_path(item, "metadata", "name", default="") or "")
        if not name:
            continue
        status = operator_status(item)
        status_map[name] = status
        if status["degraded"] == "True":
            degraded.append(name)
        if status["available"] == "False":
            unavailable.append(name)
        if status["progressing"] == "True":
            progressing.append(name)
        version = status["version"]
        if desired_version not in {"unknown", ""} and version not in {"unknown", ""} and version != desired_version:
            version_mismatches.append(
                {
                    "name": name,
                    "operator_version": version,
                    "cluster_version": desired_version,
                    "available": status["available"],
                    "progressing": status["progressing"],
                    "degraded": status["degraded"],
                }
            )

    return degraded, unavailable, progressing, status_map, version_mismatches


def build_ingresscontroller_facts(ingresscontrollers, control_plane_topology):
    summary = []
    issues = []
    default_replicas = 1 if control_plane_topology == "SingleReplica" else 2

    for item in ingresscontrollers:
        if not isinstance(item, dict):
            continue
        name = str(get_path(item, "metadata", "name", default="unknown") or "unknown")
        desired_replicas = int(get_path(item, "spec", "replicas", default=default_replicas) or 0)
        available_replicas = int(get_path(item, "status", "availableReplicas", default=0) or 0)
        unavailable_replicas = int(get_path(item, "status", "unavailableReplicas", default=0) or 0)
        conditions = get_path(item, "status", "conditions", default=[]) or []
        available_status = condition_status(conditions, "Available")
        progressing_status = condition_status(conditions, "Progressing")
        degraded_status = condition_status(conditions, "Degraded")
        summary.append(
            {
                "name": name,
                "domain": get_path(item, "status", "domain", default=get_path(item, "spec", "domain", default="unknown")),
                "available": available_status,
                "progressing": progressing_status,
                "degraded": degraded_status,
                "desired_replicas": desired_replicas,
                "available_replicas": available_replicas,
                "unavailable_replicas": unavailable_replicas,
            }
        )
        if available_status == "False" or available_replicas < desired_replicas:
            issues.append(
                {
                    "component": f"ingresscontroller/{name}",
                    "issue": "ingresscontroller-unavailable",
                    "detail": f"available={available_status} availableReplicas={available_replicas}/{desired_replicas}",
                }
            )
        if degraded_status == "True":
            issues.append(
                {
                    "component": f"ingresscontroller/{name}",
                    "issue": "ingresscontroller-degraded",
                    "detail": f"degraded={degraded_status}",
                }
            )

    return summary, issues


def component_entry(name, status_map, detail):
    status = status_map.get(name, {})
    return {
        "component": name,
        "available": status.get("available", "Unknown"),
        "progressing": status.get("progressing", "Unknown"),
        "degraded": status.get("degraded", "Unknown"),
        "version": status.get("version", "unknown"),
        "detail": detail,
    }


def build_infrastructure_components(graph, cluster_profile, status_map, ingresscontroller_summary):
    entries = [
        component_entry("authentication", status_map, f"identityProviders={len(get_path(graph, 'oauth_config', 'spec', 'identityProviders', default=[]) or [])}"),
        component_entry("console", status_map, "console operator health"),
        component_entry("dns", status_map, f"baseDomain={get_path(graph, 'dns_config', 'spec', 'baseDomain', default='unknown')}"),
        component_entry("etcd", status_map, "etcd operator health"),
        component_entry("image-registry", status_map, f"managementState={get_path(graph, 'image_registry_config', 'spec', 'managementState', default='unknown')}"),
        component_entry("ingress", status_map, f"controllers={len(ingresscontroller_summary)}"),
        component_entry("kube-apiserver", status_map, f"apiServerURL={cluster_profile.get('api_url', 'unknown') if isinstance(cluster_profile, dict) else 'unknown'}"),
        component_entry("monitoring", status_map, "monitoring operator health"),
        component_entry("network", status_map, f"networkType={get_path(graph, 'network_config', 'status', 'networkType', default='unknown')}"),
    ]
    issues = []
    for entry in entries:
        if entry["available"] == "False":
            issues.append(
                {
                    "component": entry["component"],
                    "issue": "component-unavailable",
                    "detail": f"available={entry['available']}",
                }
            )
        if entry["degraded"] == "True":
            issues.append(
                {
                    "component": entry["component"],
                    "issue": "component-degraded",
                    "detail": f"degraded={entry['degraded']}",
                }
            )
    return entries, issues


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    graph = data.get("analysis_graph") or {}
    cluster_profile = data.get("cluster_profile") or {}
    clusterversion = graph.get("clusterversion") or {}
    conditions = get_path(clusterversion, "status", "conditions", default=[]) or []
    desired_version = str(get_path(clusterversion, "status", "desired", "version", default="unknown") or "unknown")

    clusteroperators = get_path(graph, "clusteroperators", "items", default=[]) or []
    degraded, unavailable, progressing, status_map, version_mismatches = build_clusteroperator_facts(
        clusteroperators,
        desired_version,
    )
    ingress_summary, ingress_issues = build_ingresscontroller_facts(
        get_path(graph, "ingresscontrollers", "items", default=[]) or [],
        str(cluster_profile.get("control_plane_topology", "unknown") if isinstance(cluster_profile, dict) else "unknown"),
    )
    infrastructure_summary, infrastructure_issues = build_infrastructure_components(
        graph,
        cluster_profile,
        status_map,
        ingress_summary,
    )

    print(
        json.dumps(
            {
                "cluster_update_history": get_path(clusterversion, "status", "history", default=[]) or [],
                "available_updates": get_path(clusterversion, "status", "availableUpdates", default=[]) or [],
                "conditional_updates": get_path(clusterversion, "status", "conditionalUpdates", default=[]) or [],
                "cv_available": condition_status(conditions, "Available"),
                "cv_progressing": condition_status(conditions, "Progressing"),
                "cv_failing": condition_status(conditions, "Failing"),
                "degraded_operators": degraded,
                "unavailable_operators": unavailable,
                "progressing_operators": progressing,
                "clusteroperator_status_map": status_map,
                "cluster_operator_version_mismatches": version_mismatches,
                "ingresscontroller_summary": ingress_summary,
                "ingresscontroller_issues": ingress_issues,
                "infrastructure_component_summary": infrastructure_summary,
                "infrastructure_component_issues": infrastructure_issues,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
