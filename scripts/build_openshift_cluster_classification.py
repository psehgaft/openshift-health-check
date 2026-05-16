#!/usr/bin/env python3
import json
import re
import sys


def configmap_text(data_map, name, namespace):
    parts = [str(name or ""), str(namespace or "")]
    for key, value in (data_map or {}).items():
        parts.append(str(key))
        parts.append(str(value))
    return "\n".join(parts).lower()


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_openshift_cluster_classification.py <input.json>"}))
        return 1

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    cluster_profile = data.get("cluster_profile") or {}
    platform = str(cluster_profile.get("platform") or "unknown").strip()
    platform_lower = platform.lower()
    control_plane_topology = str(cluster_profile.get("control_plane_topology") or "unknown").strip()
    node_count = int(data.get("node_count") or 0)
    control_plane_node_count = int(data.get("control_plane_node_count") or 0)
    worker_node_count = int(data.get("worker_node_count") or 0)
    infra_node_count = int(data.get("infra_node_count") or 0)
    machine_api_worker_pool_count = int(data.get("machineset_count") or 0)
    machine_api_managed_worker_pools = machine_api_worker_pool_count > 0
    namespaces = {
        str(item or "").strip()
        for item in (data.get("namespace_names") or [])
        if str(item or "").strip()
    }

    public_cloud_platforms = {"aws", "azure", "gcp", "ibmcloud", "alibabacloud", "alibaba", "powervs"}
    virtualized_platforms = {"vsphere", "openstack", "ovirt", "nutanix", "kubevirt"}
    bare_metal_platforms = {"baremetal", "libvirt"}
    external_platforms = {"external", "none"}

    if platform_lower in public_cloud_platforms:
        platform_category = "public-cloud"
    elif platform_lower in virtualized_platforms:
        platform_category = "virtualized"
    elif platform_lower in bare_metal_platforms:
        platform_category = "bare-metal"
    elif platform_lower in external_platforms:
        platform_category = "external"
    elif platform_lower in {"unknown", ""}:
        platform_category = "unknown"
    else:
        platform_category = "other"

    public_cloud = platform_lower in public_cloud_platforms
    cluster_config_text = configmap_text(
        data.get("cluster_config_v1_data") or {},
        "cluster-config-v1",
        "kube-system",
    )
    install_manifests_text = configmap_text(
        data.get("openshift_install_manifests_data") or {},
        "openshift-install-manifests",
        "openshift-config",
    )
    combined_text = "\n".join(part for part in [cluster_config_text, install_manifests_text] if part)

    aro_markers = bool(re.search(r"(^|[^a-z])aro([^a-z]|$)", combined_text)) or ("openshift-aro" in namespaces)
    rosa_markers = bool(re.search(r"(^|[^a-z])rosa([^a-z]|$)", combined_text))
    osd_markers = bool(re.search(r"(^|[^a-z])osd([^a-z]|$)", combined_text))
    managed_namespace_hits = sorted(
        namespaces.intersection(
            {
                "openshift-ocm-agent-operator",
                "openshift-managed-upgrade-operator",
                "openshift-addon-operator",
            }
        )
    )

    is_sno = control_plane_topology == "SingleReplica" or (node_count == 1 and control_plane_node_count == 1)
    if control_plane_topology == "External":
        control_plane_model = "hosted"
        control_plane_model_source = "infrastructure.status.controlPlaneTopology"
        control_plane_model_confidence = "high"
        is_hosted_control_plane = True
    elif platform_lower == "aws" and control_plane_node_count == 0 and worker_node_count > 0:
        control_plane_model = "hosted"
        control_plane_model_source = "worker-only-node-inference"
        control_plane_model_confidence = "medium"
        is_hosted_control_plane = True
    elif is_sno:
        control_plane_model = "single-node"
        control_plane_model_source = "single-replica-topology-or-single-node"
        control_plane_model_confidence = "high"
        is_hosted_control_plane = False
    else:
        control_plane_model = "standalone"
        control_plane_model_source = (
            "infrastructure.status.controlPlaneTopology"
            if control_plane_topology not in {"", "unknown"}
            else "control-plane-node-inference"
        )
        control_plane_model_confidence = "high" if control_plane_topology not in {"", "unknown"} else "medium"
        is_hosted_control_plane = False

    service_model = "unknown"
    service_model_source = "not-derived"
    service_model_confidence = "low"
    service_variant = "unknown"
    if aro_markers:
        service_model = "managed"
        service_variant = "aro"
        service_model_source = "cluster-config-or-install-manifests-aro-marker"
        service_model_confidence = "high"
    elif platform_lower == "aws" and is_hosted_control_plane and rosa_markers:
        service_model = "managed"
        service_variant = "rosa-hcp"
        service_model_source = "hosted-control-plane-plus-rosa-marker"
        service_model_confidence = "high"
    elif platform_lower == "aws" and rosa_markers:
        service_model = "managed"
        service_variant = "rosa"
        service_model_source = "cluster-config-or-install-manifests-rosa-marker"
        service_model_confidence = "medium"
    elif osd_markers:
        service_model = "managed"
        service_variant = "osd"
        service_model_source = "cluster-config-or-install-manifests-osd-marker"
        service_model_confidence = "medium"
    elif len(managed_namespace_hits) >= 2:
        service_model = "managed"
        service_variant = "managed-openshift"
        service_model_source = "managed-service-namespaces"
        service_model_confidence = "medium"
    elif platform_lower not in {"", "unknown"}:
        service_model = "self-managed"
        service_variant = "self-managed-openshift"
        service_model_source = "no-managed-service-markers"
        service_model_confidence = "medium"

    if service_model == "managed":
        install_model = "ipi"
        install_model_source = "managed-service-classification"
        install_model_confidence = "medium"
    elif machine_api_managed_worker_pools and platform_category == "public-cloud":
        install_model = "ipi"
        install_model_source = "machine-api-worker-pools-on-public-cloud"
        install_model_confidence = "medium"
    elif machine_api_managed_worker_pools and platform_category in {"virtualized", "bare-metal"}:
        install_model = "ipi"
        install_model_source = "machine-api-worker-pool-inference"
        install_model_confidence = "low"
    else:
        install_model = "unknown"
        install_model_source = "not-reliably-derivable-from-cluster-apis"
        install_model_confidence = "low"

    if is_sno:
        cluster_classification_label = "single-node-openshift"
        cluster_classification_source = control_plane_model_source
        cluster_classification_confidence = control_plane_model_confidence
    elif service_variant not in {"", "unknown"}:
        cluster_classification_label = service_variant
        cluster_classification_source = service_model_source
        cluster_classification_confidence = service_model_confidence
    elif control_plane_model == "hosted":
        cluster_classification_label = "hosted-control-plane-openshift"
        cluster_classification_source = control_plane_model_source
        cluster_classification_confidence = control_plane_model_confidence
    elif service_model == "self-managed":
        cluster_classification_label = "self-managed-openshift"
        cluster_classification_source = service_model_source
        cluster_classification_confidence = service_model_confidence
    else:
        cluster_classification_label = "openshift"
        cluster_classification_source = "default-openshift-fallback"
        cluster_classification_confidence = "low"

    print(
        json.dumps(
            {
                "platform_category": platform_category,
                "public_cloud": public_cloud,
                "service_model": service_model,
                "service_model_source": service_model_source,
                "service_model_confidence": service_model_confidence,
                "service_variant": service_variant,
                "install_model": install_model,
                "install_model_source": install_model_source,
                "install_model_confidence": install_model_confidence,
                "control_plane_model": control_plane_model,
                "control_plane_model_source": control_plane_model_source,
                "control_plane_model_confidence": control_plane_model_confidence,
                "cluster_classification_label": cluster_classification_label,
                "cluster_classification_source": cluster_classification_source,
                "cluster_classification_confidence": cluster_classification_confidence,
                "deployment_type": cluster_classification_label,
                "deployment_type_source": cluster_classification_source,
                "deployment_type_confidence": cluster_classification_confidence,
                "is_sno": is_sno,
                "is_hosted_control_plane": is_hosted_control_plane,
                "machine_api_worker_pool_count": machine_api_worker_pool_count,
                "machine_api_managed_worker_pools": machine_api_managed_worker_pools,
                "control_plane_node_count": control_plane_node_count,
                "worker_node_count": worker_node_count,
                "infra_node_count": infra_node_count,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
