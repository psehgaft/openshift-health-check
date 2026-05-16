#!/usr/bin/env python3
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: detect_kubernetes_cluster_type.py <input.json>"}))
        return 1

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    requested = str(data.get("requested_provider_family") or "generic").strip().lower()
    requested_profile_mode = str(data.get("requested_cluster_profile_mode") or "production").strip().lower() or "production"
    context = str(data.get("context") or "").strip().lower()
    nodes = data.get("nodes") or []
    namespaces = {
        (item.get("metadata", {}) or {}).get("name", "")
        for item in (data.get("namespaces") or [])
    }
    crd_names = {
        (item.get("metadata", {}) or {}).get("name", "")
        for item in (data.get("crds") or [])
    }

    provider_ids = []
    label_keys = set()
    node_names = set()

    for node in nodes:
        meta = node.get("metadata", {}) or {}
        spec = node.get("spec", {}) or {}
        labels = meta.get("labels", {}) or {}
        provider_ids.append(str(spec.get("providerID") or "").lower())
        label_keys.update(labels.keys())
        node_names.add(str(meta.get("name") or "").lower())

    observed_provider_family = "generic"
    observed_detected_from = "default"
    profile_mode = requested_profile_mode

    if (
        "minikube" in context
        or "minikube.k8s.io/name" in label_keys
        or any(name.startswith("minikube") for name in node_names)
    ):
        observed_provider_family = "minikube"
        observed_detected_from = "context-or-node-labels"
        profile_mode = "lightweight"
    elif (
        "cattle-system" in namespaces
        or "cattle-fleet-system" in namespaces
        or any("management.cattle.io" in name for name in crd_names)
        or "rancher" in context
    ):
        observed_provider_family = "rancher"
        observed_detected_from = "rancher-namespaces-or-crds"
    elif (
        any(pid.startswith("azure://") for pid in provider_ids)
        or "kubernetes.azure.com/cluster" in label_keys
        or "kubernetes.azure.com/agentpool" in label_keys
        or "aks" in context
    ):
        observed_provider_family = "aks"
        observed_detected_from = "azure-provider-or-labels"
    elif (
        any(pid.startswith("gce://") for pid in provider_ids)
        or "cloud.google.com/gke-nodepool" in label_keys
        or "iam.gke.io/gke-metadata-server-enabled" in label_keys
        or context.startswith("gke_")
        or " gke_" in context
    ):
        observed_provider_family = "gke"
        observed_detected_from = "gke-provider-or-labels"
    elif (
        any(pid.startswith("aws://") for pid in provider_ids)
        or "eks.amazonaws.com/nodegroup" in label_keys
        or "alpha.eksctl.io/nodegroup-name" in label_keys
        or "eks.amazonaws.com/capacityType" in label_keys
        or "eks" in context
    ):
        observed_provider_family = "eks"
        observed_detected_from = "aws-provider-or-labels"

    resolved_provider_family = requested if requested != "generic" else observed_provider_family
    resolved_detected_from = "playbook-wrapper" if requested != "generic" else observed_detected_from

    print(
        json.dumps(
            {
                "provider_family": resolved_provider_family,
                "detected_from": resolved_detected_from,
                "observed_provider_family": observed_provider_family,
                "observed_detected_from": observed_detected_from,
                "cluster_profile_mode": profile_mode,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
