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
    "apiserver_config": ("APIServer", "cluster", None),
    "proxy_config": ("Proxy", "cluster", None),
    "ingress_config": ("Ingress", "cluster", None),
    "dns_config": ("DNS", "default", None),
    "oauth_config": ("OAuth", "cluster", None),
    "clusteroperators": ("ClusterOperator", None, None),
    "machineconfigpools": ("MachineConfigPool", None, None),
    "cluster_version_operators": ("ClusterVersionOperator", None, None),
    "image_config": ("Image", "cluster", None),
    "imagedigestmirrorsets": ("ImageDigestMirrorSet", None, None),
    "imagetagmirrorsets": ("ImageTagMirrorSet", None, None),
    "imagecontentsourcepolicies": ("ImageContentSourcePolicy", None, None),
    "catalogsources": ("CatalogSource", None, None),
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
                for item in data:
                    yield item
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


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: extract_must_gather_resources.py <must-gather-path>"}))
        return 1

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": "must-gather path not found", "path": str(root)}))
        return 2

    collected = {key: [] for key in RESOURCE_KEYS}
    singles = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        for doc in iter_docs(path):
            if not isinstance(doc, dict):
                continue
            kind = str(doc.get("kind") or "")
            meta = doc.get("metadata") or {}
            name = meta.get("name")
            namespace = meta.get("namespace")

            for key, (expected_kind, expected_name, expected_namespace) in RESOURCE_KEYS.items():
                if kind != expected_kind:
                    continue
                if expected_name is not None and name != expected_name:
                    continue
                if expected_namespace is not None and namespace != expected_namespace:
                    continue
                if expected_name is None:
                    collected[key].append(doc)
                else:
                    singles[key] = doc

    payload = {
        "clusterversion": singles.get("clusterversion", {}),
        "infrastructure": singles.get("infrastructure", {}),
        "network_config": singles.get("network_config", {}),
        "apiserver_config": singles.get("apiserver_config", {}),
        "proxy_config": singles.get("proxy_config", {}),
        "ingress_config": singles.get("ingress_config", {}),
        "dns_config": singles.get("dns_config", {}),
        "oauth_config": singles.get("oauth_config", {}),
        "clusteroperators": normalize_items(collected["clusteroperators"]),
        "machineconfigpools": normalize_items(collected["machineconfigpools"]),
        "cluster_version_operators": normalize_items(collected["cluster_version_operators"]),
        "image_config": singles.get("image_config", {}),
        "imagedigestmirrorsets": normalize_items(collected["imagedigestmirrorsets"]),
        "imagetagmirrorsets": normalize_items(collected["imagetagmirrorsets"]),
        "imagecontentsourcepolicies": normalize_items(collected["imagecontentsourcepolicies"]),
        "catalogsources": normalize_items(collected["catalogsources"]),
        "image_registry_config": singles.get("image_registry_config", {}),
        "image_pruner_config": singles.get("image_pruner_config", {}),
        "apiservices": normalize_items(collected["apiservices"]),
        "securitycontextconstraints": normalize_items(collected["securitycontextconstraints"]),
        "buildconfigs": normalize_items(collected["buildconfigs"]),
        "deploymentconfigs": normalize_items(collected["deploymentconfigs"]),
        "builds": normalize_items(collected["builds"]),
        "imagestreams": normalize_items(collected["imagestreams"]),
        "pipelines": normalize_items(collected["pipelines"]),
        "pipelineruns": normalize_items(collected["pipelineruns"]),
        "volumesnapshotclasses": normalize_items(collected["volumesnapshotclasses"]),
        "dataprotectionapplications": normalize_items(collected["dataprotectionapplications"]),
        "backupstoragelocations": normalize_items(collected["backupstoragelocations"]),
        "schedules": normalize_items(collected["schedules"]),
        "backups": normalize_items(collected["backups"]),
        "restores": normalize_items(collected["restores"]),
        "compliancesuites": normalize_items(collected["compliancesuites"]),
        "compliancescans": normalize_items(collected["compliancescans"]),
        "scansettings": normalize_items(collected["scansettings"]),
        "scansettingbindings": normalize_items(collected["scansettingbindings"]),
        "tailoredprofiles": normalize_items(collected["tailoredprofiles"]),
        "profiles": normalize_items(collected["profiles"]),
        "profilebundles": normalize_items(collected["profilebundles"]),
        "compliancecheckresults": normalize_items(collected["compliancecheckresults"]),
        "users": normalize_items(collected["users"]),
        "groups": normalize_items(collected["groups"]),
        "machinesets": normalize_items(collected["machinesets"]),
        "machinehealthchecks": normalize_items(collected["machinehealthchecks"]),
        "ingresscontrollers": normalize_items(collected["ingresscontrollers"]),
        "clusterlogforwarders": normalize_items(collected["clusterlogforwarders"]),
        "alertmanagerconfigs": normalize_items(collected["alertmanagerconfigs"]),
        "subscriptions": normalize_items(collected["subscriptions"]),
        "argocds": normalize_items(collected["argocds"]),
        "gitops_applications": normalize_items(collected["gitops_applications"]),
        "gitops_appprojects": normalize_items(collected["gitops_appprojects"]),
        "clusterautoscalers": normalize_items(collected["clusterautoscalers"]),
        "klusterlets": normalize_items(collected["klusterlets"]),
        "managedclusteraddons": normalize_items(collected["managedclusteraddons"]),
        "clustersecretstores": normalize_items(collected["clustersecretstores"]),
        "secretstores": normalize_items(collected["secretstores"]),
        "externalsecrets": normalize_items(collected["externalsecrets"]),
        "nodes": normalize_items(collected["nodes"]),
        "routes": normalize_items(collected["routes"]),
        "namespaces": normalize_items(collected["namespaces"]),
        "pods": normalize_items(collected["pods"]),
        "deployments": normalize_items(collected["deployments"]),
        "statefulsets": normalize_items(collected["statefulsets"]),
        "daemonsets": normalize_items(collected["daemonsets"]),
        "networkpolicies": normalize_items(collected["networkpolicies"]),
        "resourcequotas": normalize_items(collected["resourcequotas"]),
        "limitranges": normalize_items(collected["limitranges"]),
        "persistentvolumes": normalize_items(collected["persistentvolumes"]),
        "persistentvolumeclaims": normalize_items(collected["persistentvolumeclaims"]),
        "events": normalize_items(collected["events"]),
        "poddisruptionbudgets": normalize_items(collected["poddisruptionbudgets"]),
        "services": normalize_items(collected["services"]),
        "endpoints": normalize_items(collected["endpoints"]),
        "crds": normalize_items(collected["crds"]),
        "storageclasses": normalize_items(collected["storageclasses"]),
        "serviceaccounts": normalize_items(collected["serviceaccounts"]),
        "rolebindings": normalize_items(collected["rolebindings"]),
        "clusterrolebindings": normalize_items(collected["clusterrolebindings"]),
        "ingresses": normalize_items(collected["ingresses"]),
        "configmaps": normalize_items(collected["configmaps"]),
        "secrets": normalize_items(collected["secrets"]),
        "resource_counts": {
            key: (len(value) if isinstance(value, list) else (1 if value else 0))
            for key, value in {**collected, **singles}.items()
        },
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
