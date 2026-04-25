#!/usr/bin/env python3
import json
import sys
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


RESOURCE_KEYS = {
    "clusterversion": ("ClusterVersion", "version", None),
    "infrastructure": ("Infrastructure", "cluster", None),
    "network_config": ("Network", "cluster", None),
    "proxy_config": ("Proxy", "cluster", None),
    "ingress_config": ("Ingress", "cluster", None),
    "dns_config": ("DNS", "default", None),
    "oauth_config": ("OAuth", "cluster", None),
    "clusteroperators": ("ClusterOperator", None, None),
    "machineconfigpools": ("MachineConfigPool", None, None),
    "cluster_version_operators": ("ClusterVersionOperator", None, None),
    "image_config": ("Image", "cluster", None),
    "image_registry_config": ("Config", "cluster", "openshift-image-registry"),
    "image_pruner_config": ("ImagePruner", "cluster", None),
    "apiservices": ("APIService", None, None),
    "securitycontextconstraints": ("SecurityContextConstraints", None, None),
    "buildconfigs": ("BuildConfig", None, None),
    "deploymentconfigs": ("DeploymentConfig", None, None),
    "builds": ("Build", None, None),
    "imagestreams": ("ImageStream", None, None),
    "pipelines": ("Pipeline", None, None),
    "pipelineruns": ("PipelineRun", None, None),
    "volumesnapshotclasses": ("VolumeSnapshotClass", None, None),
    "dataprotectionapplications": ("DataProtectionApplication", None, None),
    "backupstoragelocations": ("BackupStorageLocation", None, None),
    "schedules": ("Schedule", None, None),
    "backups": ("Backup", None, None),
    "restores": ("Restore", None, None),
    "compliancesuites": ("ComplianceSuite", None, None),
    "compliancescans": ("ComplianceScan", None, None),
    "scansettings": ("ScanSetting", None, None),
    "scansettingbindings": ("ScanSettingBinding", None, None),
    "tailoredprofiles": ("TailoredProfile", None, None),
    "profiles": ("Profile", None, None),
    "profilebundles": ("ProfileBundle", None, None),
    "compliancecheckresults": ("ComplianceCheckResult", None, None),
    "users": ("User", None, None),
    "groups": ("Group", None, None),
    "machinesets": ("MachineSet", None, None),
    "machinehealthchecks": ("MachineHealthCheck", None, None),
    "ingresscontrollers": ("IngressController", None, None),
    "clusterlogforwarders": ("ClusterLogForwarder", None, None),
    "alertmanagerconfigs": ("AlertmanagerConfig", None, None),
    "subscriptions": ("Subscription", None, None),
    "argocds": ("ArgoCD", None, None),
    "gitops_applications": ("Application", None, None),
    "gitops_appprojects": ("AppProject", None, None),
    "clusterautoscalers": ("ClusterAutoscaler", None, None),
    "klusterlets": ("Klusterlet", None, None),
    "managedclusteraddons": ("ManagedClusterAddOn", None, None),
    "clustersecretstores": ("ClusterSecretStore", None, None),
    "secretstores": ("SecretStore", None, None),
    "externalsecrets": ("ExternalSecret", None, None),
    "storageclusters": ("StorageCluster", None, None),
    "cephclusters": ("CephCluster", None, None),
    "cephblockpools": ("CephBlockPool", None, None),
    "cephfilesystems": ("CephFilesystem", None, None),
    "noobaas": ("NooBaa", None, None),
    "kubevirts": ("KubeVirt", None, None),
    "hyperconvergeds": ("HyperConverged", None, None),
    "ssps": ("SSP", None, None),
    "cdis": ("CDI", None, None),
    "datavolumes": ("DataVolume", None, None),
    "virtualmachines": ("VirtualMachine", None, None),
    "virtualmachineinstances": ("VirtualMachineInstance", None, None),
    "datascienceclusters": ("DataScienceCluster", None, None),
    "dscinitializations": ("DSCInitialization", None, None),
    "notebooks": ("Notebook", None, None),
    "servingruntimes": ("ServingRuntime", None, None),
    "inferenceservices": ("InferenceService", None, None),
    "modelmeshservings": ("ModelMeshServing", None, None),
    "acceleratorprofiles": ("AcceleratorProfile", None, None),
    "nodes": ("Node", None, None),
    "routes": ("Route", None, None),
    "namespaces": ("Namespace", None, None),
    "pods": ("Pod", None, None),
    "deployments": ("Deployment", None, None),
    "statefulsets": ("StatefulSet", None, None),
    "daemonsets": ("DaemonSet", None, None),
    "networkpolicies": ("NetworkPolicy", None, None),
    "resourcequotas": ("ResourceQuota", None, None),
    "limitranges": ("LimitRange", None, None),
    "persistentvolumes": ("PersistentVolume", None, None),
    "persistentvolumeclaims": ("PersistentVolumeClaim", None, None),
    "events": ("Event", None, None),
    "poddisruptionbudgets": ("PodDisruptionBudget", None, None),
    "services": ("Service", None, None),
    "endpoints": ("Endpoints", None, None),
    "crds": ("CustomResourceDefinition", None, None),
    "storageclasses": ("StorageClass", None, None),
    "serviceaccounts": ("ServiceAccount", None, None),
    "rolebindings": ("RoleBinding", None, None),
    "clusterrolebindings": ("ClusterRoleBinding", None, None),
    "ingresses": ("Ingress", None, None),
    "configmaps": ("ConfigMap", None, None),
    "secrets": ("Secret", None, None),
}


def iter_docs(path: Path):
    if path.suffix.lower() == ".json":
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                yield from data
            else:
                yield data
        except Exception:
            return
    elif path.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                for item in yaml.safe_load_all(handle):
                    if item:
                        yield item
        except Exception:
            return


def normalize_items(items):
    return {"apiVersion": "v1", "kind": "List", "items": items}


def object_key(doc):
    meta = doc.get("metadata") or {}
    uid = meta.get("uid")
    if uid:
        return f"uid:{uid}"
    return "|".join(
        [
            str(doc.get("apiVersion") or ""),
            str(doc.get("kind") or ""),
            str(meta.get("namespace") or ""),
            str(meta.get("name") or ""),
        ]
    )


def annotate(doc, source_name: str, path: Path, root: Path):
    data = dict(doc)
    existing_sources = list(data.get("_evidence_sources") or [])
    if source_name not in existing_sources:
        existing_sources.append(source_name)
    data["_evidence_source"] = existing_sources[0] if existing_sources else source_name
    data["_evidence_sources"] = existing_sources
    data["_evidence_path"] = str(path.relative_to(root))
    return data


def parse_args(argv):
    if len(argv) < 3 or len(argv[1:]) % 2 != 0:
        print(
            json.dumps(
                {
                    "error": "usage: extract_offline_resources.py <source-name> <path> [<source-name> <path> ...]"
                }
            )
        )
        return None
    pairs = []
    args = argv[1:]
    for idx in range(0, len(args), 2):
        source_name = args[idx].strip()
        root = Path(args[idx + 1]).expanduser().resolve()
        if not source_name:
            print(json.dumps({"error": "source name must not be empty"}))
            return None
        if not root.exists() or not root.is_dir():
            print(json.dumps({"error": "source path not found", "path": str(root), "source": source_name}))
            return None
        pairs.append((source_name, root))
    return pairs


def main() -> int:
    source_pairs = parse_args(sys.argv)
    if source_pairs is None:
        return 1

    collected = {key: {} for key in RESOURCE_KEYS}
    singles = {}
    source_file_counts = {}

    for source_name, root in source_pairs:
        source_file_counts[source_name] = 0
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            source_file_counts[source_name] += 1
            for raw_doc in iter_docs(path):
                if not isinstance(raw_doc, dict):
                    continue
                kind = str(raw_doc.get("kind") or "")
                meta = raw_doc.get("metadata") or {}
                name = meta.get("name")
                namespace = meta.get("namespace")
                doc = annotate(raw_doc, source_name, path, root)

                for key, (expected_kind, expected_name, expected_namespace) in RESOURCE_KEYS.items():
                    if kind != expected_kind:
                        continue
                    if expected_name is not None and name != expected_name:
                        continue
                    if expected_namespace is not None and namespace != expected_namespace:
                        continue
                    if expected_name is None:
                        obj_id = object_key(doc)
                        if obj_id not in collected[key]:
                            collected[key][obj_id] = doc
                        else:
                            prior_sources = list(collected[key][obj_id].get("_evidence_sources") or [])
                            for item in doc.get("_evidence_sources") or []:
                                if item not in prior_sources:
                                    prior_sources.append(item)
                            collected[key][obj_id]["_evidence_sources"] = prior_sources
                    elif key not in singles:
                        singles[key] = doc

    payload = {
        "clusterversion": singles.get("clusterversion", {}),
        "infrastructure": singles.get("infrastructure", {}),
        "network_config": singles.get("network_config", {}),
        "proxy_config": singles.get("proxy_config", {}),
        "ingress_config": singles.get("ingress_config", {}),
        "dns_config": singles.get("dns_config", {}),
        "oauth_config": singles.get("oauth_config", {}),
        "clusteroperators": normalize_items(list(collected["clusteroperators"].values())),
        "machineconfigpools": normalize_items(list(collected["machineconfigpools"].values())),
        "cluster_version_operators": normalize_items(list(collected["cluster_version_operators"].values())),
        "image_config": singles.get("image_config", {}),
        "image_registry_config": singles.get("image_registry_config", {}),
        "image_pruner_config": singles.get("image_pruner_config", {}),
        "apiservices": normalize_items(list(collected["apiservices"].values())),
        "securitycontextconstraints": normalize_items(list(collected["securitycontextconstraints"].values())),
        "buildconfigs": normalize_items(list(collected["buildconfigs"].values())),
        "deploymentconfigs": normalize_items(list(collected["deploymentconfigs"].values())),
        "builds": normalize_items(list(collected["builds"].values())),
        "imagestreams": normalize_items(list(collected["imagestreams"].values())),
        "pipelines": normalize_items(list(collected["pipelines"].values())),
        "pipelineruns": normalize_items(list(collected["pipelineruns"].values())),
        "volumesnapshotclasses": normalize_items(list(collected["volumesnapshotclasses"].values())),
        "dataprotectionapplications": normalize_items(list(collected["dataprotectionapplications"].values())),
        "backupstoragelocations": normalize_items(list(collected["backupstoragelocations"].values())),
        "schedules": normalize_items(list(collected["schedules"].values())),
        "backups": normalize_items(list(collected["backups"].values())),
        "restores": normalize_items(list(collected["restores"].values())),
        "compliancesuites": normalize_items(list(collected["compliancesuites"].values())),
        "compliancescans": normalize_items(list(collected["compliancescans"].values())),
        "scansettings": normalize_items(list(collected["scansettings"].values())),
        "scansettingbindings": normalize_items(list(collected["scansettingbindings"].values())),
        "tailoredprofiles": normalize_items(list(collected["tailoredprofiles"].values())),
        "profiles": normalize_items(list(collected["profiles"].values())),
        "profilebundles": normalize_items(list(collected["profilebundles"].values())),
        "compliancecheckresults": normalize_items(list(collected["compliancecheckresults"].values())),
        "users": normalize_items(list(collected["users"].values())),
        "groups": normalize_items(list(collected["groups"].values())),
        "machinesets": normalize_items(list(collected["machinesets"].values())),
        "machinehealthchecks": normalize_items(list(collected["machinehealthchecks"].values())),
        "ingresscontrollers": normalize_items(list(collected["ingresscontrollers"].values())),
        "clusterlogforwarders": normalize_items(list(collected["clusterlogforwarders"].values())),
        "alertmanagerconfigs": normalize_items(list(collected["alertmanagerconfigs"].values())),
        "subscriptions": normalize_items(list(collected["subscriptions"].values())),
        "argocds": normalize_items(list(collected["argocds"].values())),
        "gitops_applications": normalize_items(list(collected["gitops_applications"].values())),
        "gitops_appprojects": normalize_items(list(collected["gitops_appprojects"].values())),
        "clusterautoscalers": normalize_items(list(collected["clusterautoscalers"].values())),
        "klusterlets": normalize_items(list(collected["klusterlets"].values())),
        "managedclusteraddons": normalize_items(list(collected["managedclusteraddons"].values())),
        "clustersecretstores": normalize_items(list(collected["clustersecretstores"].values())),
        "secretstores": normalize_items(list(collected["secretstores"].values())),
        "externalsecrets": normalize_items(list(collected["externalsecrets"].values())),
        "storageclusters": normalize_items(list(collected["storageclusters"].values())),
        "cephclusters": normalize_items(list(collected["cephclusters"].values())),
        "cephblockpools": normalize_items(list(collected["cephblockpools"].values())),
        "cephfilesystems": normalize_items(list(collected["cephfilesystems"].values())),
        "noobaas": normalize_items(list(collected["noobaas"].values())),
        "kubevirts": normalize_items(list(collected["kubevirts"].values())),
        "hyperconvergeds": normalize_items(list(collected["hyperconvergeds"].values())),
        "ssps": normalize_items(list(collected["ssps"].values())),
        "cdis": normalize_items(list(collected["cdis"].values())),
        "datavolumes": normalize_items(list(collected["datavolumes"].values())),
        "virtualmachines": normalize_items(list(collected["virtualmachines"].values())),
        "virtualmachineinstances": normalize_items(list(collected["virtualmachineinstances"].values())),
        "datascienceclusters": normalize_items(list(collected["datascienceclusters"].values())),
        "dscinitializations": normalize_items(list(collected["dscinitializations"].values())),
        "notebooks": normalize_items(list(collected["notebooks"].values())),
        "servingruntimes": normalize_items(list(collected["servingruntimes"].values())),
        "inferenceservices": normalize_items(list(collected["inferenceservices"].values())),
        "modelmeshservings": normalize_items(list(collected["modelmeshservings"].values())),
        "acceleratorprofiles": normalize_items(list(collected["acceleratorprofiles"].values())),
        "nodes": normalize_items(list(collected["nodes"].values())),
        "routes": normalize_items(list(collected["routes"].values())),
        "namespaces": normalize_items(list(collected["namespaces"].values())),
        "pods": normalize_items(list(collected["pods"].values())),
        "deployments": normalize_items(list(collected["deployments"].values())),
        "statefulsets": normalize_items(list(collected["statefulsets"].values())),
        "daemonsets": normalize_items(list(collected["daemonsets"].values())),
        "networkpolicies": normalize_items(list(collected["networkpolicies"].values())),
        "resourcequotas": normalize_items(list(collected["resourcequotas"].values())),
        "limitranges": normalize_items(list(collected["limitranges"].values())),
        "persistentvolumes": normalize_items(list(collected["persistentvolumes"].values())),
        "persistentvolumeclaims": normalize_items(list(collected["persistentvolumeclaims"].values())),
        "events": normalize_items(list(collected["events"].values())),
        "poddisruptionbudgets": normalize_items(list(collected["poddisruptionbudgets"].values())),
        "services": normalize_items(list(collected["services"].values())),
        "endpoints": normalize_items(list(collected["endpoints"].values())),
        "crds": normalize_items(list(collected["crds"].values())),
        "storageclasses": normalize_items(list(collected["storageclasses"].values())),
        "serviceaccounts": normalize_items(list(collected["serviceaccounts"].values())),
        "rolebindings": normalize_items(list(collected["rolebindings"].values())),
        "clusterrolebindings": normalize_items(list(collected["clusterrolebindings"].values())),
        "ingresses": normalize_items(list(collected["ingresses"].values())),
        "configmaps": normalize_items(list(collected["configmaps"].values())),
        "secrets": normalize_items(list(collected["secrets"].values())),
    }
    payload["resource_counts"] = {
        key: (len(value) if isinstance(value, dict) else (1 if value else 0))
        for key, value in {**collected, **singles}.items()
    }
    payload["source_summary"] = {
        "sources": [name for name, _ in source_pairs],
        "file_counts": source_file_counts,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
