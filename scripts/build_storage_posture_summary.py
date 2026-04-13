#!/usr/bin/env python3
import json
import sys


LOCAL_SC_MARKERS = [
    "kubernetes.io/no-provisioner",
    "rancher.io/local-path",
    "microk8s.io/hostpath",
    "hostpath.csi.k8s.io",
    "k8s.io/minikube-hostpath",
]

EXTERNAL_SC_MARKERS = [
    ".csi.",
    "ebs.csi.aws.com",
    "efs.csi.aws.com",
    "disk.csi.azure.com",
    "file.csi.azure.com",
    "pd.csi.storage.gke.io",
    "filestore.csi.storage.gke.io",
    "cephfs.csi.ceph.com",
    "rbd.csi.ceph.com",
    "nfs.csi.k8s.io",
    "openshift-storage.",
    "portworx",
    "pure",
    "netapp",
    "trident",
    "vsphere",
    "openstack",
    "linstor",
    "longhorn",
    "powermax",
    "powerstore",
    "unity",
    "iscsi",
    "fc",
    "ceph",
    "nfs",
]


def is_local_storageclass(provisioner):
    text = str(provisioner or "").lower()
    return any(marker in text for marker in LOCAL_SC_MARKERS)


def is_external_storageclass(provisioner):
    text = str(provisioner or "").lower()
    if not text or is_local_storageclass(text):
        return False
    return any(marker in text for marker in EXTERNAL_SC_MARKERS) or text not in {"unknown", ""}


def classify_pv_source(spec):
    spec = spec or {}
    if spec.get("hostPath") is not None or spec.get("local") is not None:
        return "local"
    external_keys = [
        "awsElasticBlockStore", "gcePersistentDisk", "azureDisk", "azureFile",
        "csi", "nfs", "cephfs", "rbd", "iscsi", "fc", "vsphereVolume",
        "photonPersistentDisk", "portworxVolume", "scaleIO", "storageos",
        "glusterfs", "quobyte", "cinder",
    ]
    if any(spec.get(key) is not None for key in external_keys):
        return "external"
    return "unknown"


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_storage_posture_summary.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    external_storageclasses = []
    local_storageclasses = []
    default_external_storageclasses = []
    for storageclass in data.get("storageclasses", []):
        provisioner = storageclass.get("provisioner", "")
        if is_local_storageclass(provisioner):
            local_storageclasses.append(storageclass)
        elif is_external_storageclass(provisioner):
            external_storageclasses.append(storageclass)
            if storageclass.get("is_default"):
                default_external_storageclasses.append(storageclass)

    external_pvs = []
    local_pvs = []
    for pv in data.get("persistentvolumes", []):
        source = classify_pv_source((pv.get("spec", {}) or {}))
        if source == "external":
            external_pvs.append(pv)
        elif source == "local":
            local_pvs.append(pv)

    hostpath_findings = [
        item for item in data.get("security_findings", [])
        if item.get("issue") == "hostpath-volume"
    ]
    ephemeral_findings = [
        item for item in data.get("workload_practice_findings", [])
        if item.get("issue") == "ephemeral-storage-volume"
    ]

    has_external_storage = bool(external_storageclasses or external_pvs)
    local_or_ephemeral_only_risk = (
        not has_external_storage and bool(local_storageclasses or local_pvs or hostpath_findings or ephemeral_findings)
    )

    findings = []
    if not has_external_storage:
        findings.append({
            "issue": "external-storage-provider-not-detected",
            "detail": "no external persistent storage provider was detected from StorageClass provisioners or PV backends",
        })
    if local_or_ephemeral_only_risk:
        findings.append({
            "issue": "cluster-relies-on-local-or-ephemeral-storage-only",
            "detail": "local storage or ephemeral volume usage was detected without any external persistent storage provider",
        })

    print(json.dumps({
        "external_storageclass_count": len(external_storageclasses),
        "local_storageclass_count": len(local_storageclasses),
        "default_external_storageclass_count": len(default_external_storageclasses),
        "external_storageclass_names": [item.get("name", "unknown") for item in external_storageclasses],
        "local_storageclass_names": [item.get("name", "unknown") for item in local_storageclasses],
        "external_pv_count": len(external_pvs),
        "local_pv_count": len(local_pvs),
        "hostpath_workload_count": len(hostpath_findings),
        "ephemeral_workload_count": len(ephemeral_findings),
        "has_external_storage_provider": has_external_storage,
        "local_or_ephemeral_only_risk": local_or_ephemeral_only_risk,
        "findings": findings,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
