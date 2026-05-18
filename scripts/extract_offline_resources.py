#!/usr/bin/env python3
import json
import os
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
    "openshift_apiserver": ("OpenShiftAPIServer", "cluster", None),
    "kube_apiserver": ("KubeAPIServer", "cluster", None),
    "authentication_operator": ("Authentication", "cluster", None),
    "proxy_config": ("Proxy", "cluster", None),
    "ingress_config": ("Ingress", "cluster", None),
    "dns_config": ("DNS", "default", None),
    "oauth_config": ("OAuth", "cluster", None),
    "project_config": ("Project", "cluster", None),
    "clusteroperators": ("ClusterOperator", None, None),
    "machineconfigpools": ("MachineConfigPool", None, None),
    "cluster_version_operators": ("ClusterVersionOperator", None, None),
    "image_config": ("Image", "cluster", None),
    "imagedigestmirrorsets": ("ImageDigestMirrorSet", None, None),
    "imagetagmirrorsets": ("ImageTagMirrorSet", None, None),
    "imagecontentsourcepolicies": ("ImageContentSourcePolicy", None, None),
    "catalogsources": ("CatalogSource", None, None),
    "clustercatalogs": ("ClusterCatalog", None, None),
    "updateservices": ("UpdateService", None, None),
    "image_registry_config": ("Config", "cluster", "openshift-image-registry"),
    "image_pruner_config": ("ImagePruner", "cluster", None),
    "apiservices": ("APIService", None, None),
    "securitycontextconstraints": ("SecurityContextConstraints", None, None),
    "templates": ("Template", None, None),
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
    "drpolicies": ("DRPolicy", None, None),
    "drclusters": ("DRCluster", None, None),
    "drplacementcontrols": ("DRPlacementControl", None, None),
    "volumereplicationgroups": ("VolumeReplicationGroup", None, None),
    "volumereplications": ("VolumeReplication", None, None),
    "volumereplicationclasses": ("VolumeReplicationClass", None, None),
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
    "egressfirewalls": ("EgressFirewall", None, None),
    "ingresscontrollers": ("IngressController", None, None),
    "clusterlogforwarders": ("ClusterLogForwarder", None, None),
    "lokistacks": ("LokiStack", None, None),
    "alertmanagerconfigs": ("AlertmanagerConfig", None, None),
    "subscriptions": ("Subscription", None, None),
    "argocds": ("ArgoCD", None, None),
    "gitops_applications": ("Application", None, None),
    "gitops_appprojects": ("AppProject", None, None),
    "clusterautoscalers": ("ClusterAutoscaler", None, None),
    "hostedclusters": ("HostedCluster", None, None),
    "nodepools": ("NodePool", None, None),
    "checlusters": ("CheCluster", None, None),
    "devworkspaces": ("DevWorkspace", None, None),
    "devworkspaceoperatorconfigs": ("DevWorkspaceOperatorConfig", None, None),
    "devworkspaceroutings": ("DevWorkspaceRouting", None, None),
    "dynakubes": ("DynaKube", None, None),
    "edgeconnects": ("EdgeConnect", None, None),
    "datadogagents": ("DatadogAgent", None, None),
    "clusteragents": ("Clusteragent", None, None),
    "infravizs": ("InfraViz", None, None),
    "ansibleautomationplatforms": ("AnsibleAutomationPlatform", None, None),
    "automationcontrollers": ("AutomationController", None, None),
    "automationhubs": ("AutomationHub", None, None),
    "edas": ("EDA", None, None),
    "kedacontrollers": ("KedaController", None, None),
    "scaledobjects": ("ScaledObject", None, None),
    "scaledjobs": ("ScaledJob", None, None),
    "triggerauthentications": ("TriggerAuthentication", None, None),
    "clustertriggerauthentications": ("ClusterTriggerAuthentication", None, None),
    "costmanagementmetricsconfigs": ("CostManagementMetricsConfig", None, None),
    "klusterlets": ("Klusterlet", None, None),
    "managedclusteraddons": ("ManagedClusterAddOn", None, None),
    "clustersecretstores": ("ClusterSecretStore", None, None),
    "secretstores": ("SecretStore", None, None),
    "externalsecrets": ("ExternalSecret", None, None),
    "secretproviderclasses": ("SecretProviderClass", None, None),
    "storageclusters": ("StorageCluster", None, None),
    "cephclusters": ("CephCluster", None, None),
    "cephblockpools": ("CephBlockPool", None, None),
    "cephfilesystems": ("CephFilesystem", None, None),
    "noobaas": ("NooBaa", None, None),
    "servicemeshcontrolplanes": ("ServiceMeshControlPlane", None, None),
    "servicemeshmemberrolls": ("ServiceMeshMemberRoll", None, None),
    "servicemeshmembers": ("ServiceMeshMember", None, None),
    "knativeservings": ("KnativeServing", None, None),
    "knativeeventings": ("KnativeEventing", None, None),
    "kubevirts": ("KubeVirt", None, None),
    "hyperconvergeds": ("HyperConverged", None, None),
    "ssps": ("SSP", None, None),
    "cdis": ("CDI", None, None),
    "datavolumes": ("DataVolume", None, None),
    "virtualmachines": ("VirtualMachine", None, None),
    "virtualmachineinstances": ("VirtualMachineInstance", None, None),
    "datascienceclusters": ("DataScienceCluster", None, None),
    "dscinitializations": ("DSCInitialization", None, None),
    "icp4aclusters": ("Icp4aCluster", None, None),
    "notebooks": ("Notebook", None, None),
    "servingruntimes": ("ServingRuntime", None, None),
    "inferenceservices": ("InferenceService", None, None),
    "modelmeshservings": ("ModelMeshServing", None, None),
    "acceleratorprofiles": ("AcceleratorProfile", None, None),
    "nvidiaclusterpolicies": ("ClusterPolicy", None, None),
    "kataconfigs": ("KataConfig", None, None),
    "tuneds": ("Tuned", None, None),
    "tunedprofiles": ("Profile", None, None),
    "nmstates": ("NMState", None, None),
    "nodenetworkconfigurationpolicies": ("NodeNetworkConfigurationPolicy", None, None),
    "nodenetworkstates": ("NodeNetworkState", None, None),
    "deschedulers": ("Descheduler", None, None),
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

KIND_INDEX = {}
for resource_key, (expected_kind, expected_name, expected_namespace) in RESOURCE_KEYS.items():
    KIND_INDEX.setdefault(expected_kind, []).append((resource_key, expected_name, expected_namespace))

RESOURCE_STEM_ALIASES = {
    "network_config": "networks",
    "apiserver_config": "apiservers",
    "openshift_apiserver": "openshiftapiservers",
    "kube_apiserver": "kubeapiservers",
    "authentication_operator": "authentications",
    "proxy_config": "proxies",
    "ingress_config": "ingresses",
    "dns_config": "dnses",
    "oauth_config": "oauths",
    "project_config": "projects",
    "image_config": "images",
    "image_registry_config": "configs",
    "gitops_applications": "applications",
    "gitops_appprojects": "appprojects",
}
ALLOWED_RESOURCE_STEMS = {
    RESOURCE_STEM_ALIASES.get(key, key).lower()
    for key in RESOURCE_KEYS
}

SOURCE_PRIORITY = {
    "must-gather": 0,
    "inspect": 1,
    "oc get": 2,
    "oc-get": 2,
    "insights": 3,
    "insights-archive": 3,
}

SKIP_RESOURCE_STEMS = {
    "clusterserviceversions",
    "leases",
    "replicasets",
    "horizontalpodautoscalers",
    "cronjobs",
    "jobs",
    "endpointslices",
}


def source_rank(name: str):
    normalized = str(name or "").strip().lower()
    return (SOURCE_PRIORITY.get(normalized, 99), normalized)


def ordered_sources(items):
    seen = set()
    ordered = []
    for item in sorted((str(x or "").strip() for x in (items or [])), key=source_rank):
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


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
    existing_sources = ordered_sources(existing_sources)
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


def source_scan_roots(source_name: str, root: Path):
    if str(source_name).strip().lower() != "must-gather":
        return [root]
    candidates = []
    for top_level in root.iterdir():
        if not top_level.is_dir():
            continue
        for child_name in ("cluster-scoped-resources", "namespaces"):
            child = top_level / child_name
            if child.is_dir():
                candidates.append(child)
    return candidates or [root]


def should_parse_path(path: Path, scan_root: Path) -> bool:
    if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
        return False
    rel_parts = path.relative_to(scan_root).parts
    stem = path.stem.lower()
    if stem in SKIP_RESOURCE_STEMS:
        return False
    if "namespaces" in rel_parts:
        ns_index = rel_parts.index("namespaces")
        # Keep namespace aggregate resource list files and skip deeper per-object YAML,
        # such as pods/<name>/<name>.yaml, because the list files already carry the objects.
        if len(rel_parts) > ns_index + 4:
            return False
        if stem not in ALLOWED_RESOURCE_STEMS:
            return False
    elif "cluster-scoped-resources" in rel_parts:
        cs_index = rel_parts.index("cluster-scoped-resources")
        if len(rel_parts) > cs_index + 3:
            parent_resource = rel_parts[-2].lower()
            if parent_resource not in ALLOWED_RESOURCE_STEMS:
                return False
        elif stem not in ALLOWED_RESOURCE_STEMS:
            return False
    return True


def iter_candidate_paths(scan_root: Path):
    scan_root_name = scan_root.name
    for dirpath, dirnames, filenames in os.walk(scan_root, topdown=True):
        current = Path(dirpath)
        try:
            rel_parts = current.relative_to(scan_root).parts
        except ValueError:
            continue
        depth = len(rel_parts)

        if scan_root_name == "namespaces":
            if depth >= 3:
                dirnames[:] = []
            elif depth == 2:
                dirnames[:] = []
        elif scan_root_name == "cluster-scoped-resources":
            if depth >= 2:
                dirnames[:] = []

        for filename in filenames:
            path = current / filename
            if should_parse_path(path, scan_root):
                yield path


def main() -> int:
    source_pairs = parse_args(sys.argv)
    if source_pairs is None:
        return 1

    collected = {key: {} for key in RESOURCE_KEYS}
    singles = {}
    source_file_counts = {}

    for source_name, root in source_pairs:
        source_file_counts[source_name] = 0
        candidate_paths = set()
        for scan_root in source_scan_roots(source_name, root):
            candidate_paths.update(iter_candidate_paths(scan_root))
        for path in sorted(candidate_paths):
            source_file_counts[source_name] += 1
            for raw_doc in iter_docs(path):
                if not isinstance(raw_doc, dict):
                    continue
                kind = str(raw_doc.get("kind") or "")
                meta = raw_doc.get("metadata") or {}
                name = meta.get("name")
                namespace = meta.get("namespace")
                doc = annotate(raw_doc, source_name, path, root)

                for key, expected_name, expected_namespace in KIND_INDEX.get(kind, []):
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
                            prior_sources = ordered_sources(prior_sources)
                            collected[key][obj_id]["_evidence_sources"] = prior_sources
                            collected[key][obj_id]["_evidence_source"] = prior_sources[0] if prior_sources else source_name
                    elif key not in singles:
                        singles[key] = doc

    payload = {
        "clusterversion": singles.get("clusterversion", {}),
        "infrastructure": singles.get("infrastructure", {}),
        "network_config": singles.get("network_config", {}),
        "apiserver_config": singles.get("apiserver_config", {}),
        "openshift_apiserver": singles.get("openshift_apiserver", {}),
        "kube_apiserver": singles.get("kube_apiserver", {}),
        "authentication_operator": singles.get("authentication_operator", {}),
        "proxy_config": singles.get("proxy_config", {}),
        "ingress_config": singles.get("ingress_config", {}),
        "dns_config": singles.get("dns_config", {}),
        "oauth_config": singles.get("oauth_config", {}),
        "project_config": singles.get("project_config", {}),
        "clusteroperators": normalize_items(list(collected["clusteroperators"].values())),
        "machineconfigpools": normalize_items(list(collected["machineconfigpools"].values())),
        "cluster_version_operators": normalize_items(list(collected["cluster_version_operators"].values())),
        "image_config": singles.get("image_config", {}),
        "imagedigestmirrorsets": normalize_items(list(collected["imagedigestmirrorsets"].values())),
        "imagetagmirrorsets": normalize_items(list(collected["imagetagmirrorsets"].values())),
        "imagecontentsourcepolicies": normalize_items(list(collected["imagecontentsourcepolicies"].values())),
        "catalogsources": normalize_items(list(collected["catalogsources"].values())),
        "clustercatalogs": normalize_items(list(collected["clustercatalogs"].values())),
        "updateservices": normalize_items(list(collected["updateservices"].values())),
        "image_registry_config": singles.get("image_registry_config", {}),
        "image_pruner_config": singles.get("image_pruner_config", {}),
        "apiservices": normalize_items(list(collected["apiservices"].values())),
        "securitycontextconstraints": normalize_items(list(collected["securitycontextconstraints"].values())),
        "templates": normalize_items(list(collected["templates"].values())),
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
        "drpolicies": normalize_items(list(collected["drpolicies"].values())),
        "drclusters": normalize_items(list(collected["drclusters"].values())),
        "drplacementcontrols": normalize_items(list(collected["drplacementcontrols"].values())),
        "volumereplicationgroups": normalize_items(list(collected["volumereplicationgroups"].values())),
        "volumereplications": normalize_items(list(collected["volumereplications"].values())),
        "volumereplicationclasses": normalize_items(list(collected["volumereplicationclasses"].values())),
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
        "egressfirewalls": normalize_items(list(collected["egressfirewalls"].values())),
        "ingresscontrollers": normalize_items(list(collected["ingresscontrollers"].values())),
        "clusterlogforwarders": normalize_items(list(collected["clusterlogforwarders"].values())),
        "lokistacks": normalize_items(list(collected["lokistacks"].values())),
        "alertmanagerconfigs": normalize_items(list(collected["alertmanagerconfigs"].values())),
        "subscriptions": normalize_items(list(collected["subscriptions"].values())),
        "argocds": normalize_items(list(collected["argocds"].values())),
        "gitops_applications": normalize_items(list(collected["gitops_applications"].values())),
        "gitops_appprojects": normalize_items(list(collected["gitops_appprojects"].values())),
        "clusterautoscalers": normalize_items(list(collected["clusterautoscalers"].values())),
        "hostedclusters": normalize_items(list(collected["hostedclusters"].values())),
        "nodepools": normalize_items(list(collected["nodepools"].values())),
        "checlusters": normalize_items(list(collected["checlusters"].values())),
        "devworkspaces": normalize_items(list(collected["devworkspaces"].values())),
        "devworkspaceoperatorconfigs": normalize_items(list(collected["devworkspaceoperatorconfigs"].values())),
        "devworkspaceroutings": normalize_items(list(collected["devworkspaceroutings"].values())),
        "dynakubes": normalize_items(list(collected["dynakubes"].values())),
        "edgeconnects": normalize_items(list(collected["edgeconnects"].values())),
        "datadogagents": normalize_items(list(collected["datadogagents"].values())),
        "clusteragents": normalize_items(list(collected["clusteragents"].values())),
        "infravizs": normalize_items(list(collected["infravizs"].values())),
        "ansibleautomationplatforms": normalize_items(list(collected["ansibleautomationplatforms"].values())),
        "automationcontrollers": normalize_items(list(collected["automationcontrollers"].values())),
        "automationhubs": normalize_items(list(collected["automationhubs"].values())),
        "edas": normalize_items(list(collected["edas"].values())),
        "kedacontrollers": normalize_items(list(collected["kedacontrollers"].values())),
        "scaledobjects": normalize_items(list(collected["scaledobjects"].values())),
        "scaledjobs": normalize_items(list(collected["scaledjobs"].values())),
        "triggerauthentications": normalize_items(list(collected["triggerauthentications"].values())),
        "clustertriggerauthentications": normalize_items(list(collected["clustertriggerauthentications"].values())),
        "costmanagementmetricsconfigs": normalize_items(list(collected["costmanagementmetricsconfigs"].values())),
        "klusterlets": normalize_items(list(collected["klusterlets"].values())),
        "managedclusteraddons": normalize_items(list(collected["managedclusteraddons"].values())),
        "clustersecretstores": normalize_items(list(collected["clustersecretstores"].values())),
        "secretstores": normalize_items(list(collected["secretstores"].values())),
        "externalsecrets": normalize_items(list(collected["externalsecrets"].values())),
        "secretproviderclasses": normalize_items(list(collected["secretproviderclasses"].values())),
        "storageclusters": normalize_items(list(collected["storageclusters"].values())),
        "cephclusters": normalize_items(list(collected["cephclusters"].values())),
        "cephblockpools": normalize_items(list(collected["cephblockpools"].values())),
        "cephfilesystems": normalize_items(list(collected["cephfilesystems"].values())),
        "noobaas": normalize_items(list(collected["noobaas"].values())),
        "servicemeshcontrolplanes": normalize_items(list(collected["servicemeshcontrolplanes"].values())),
        "servicemeshmemberrolls": normalize_items(list(collected["servicemeshmemberrolls"].values())),
        "servicemeshmembers": normalize_items(list(collected["servicemeshmembers"].values())),
        "knativeservings": normalize_items(list(collected["knativeservings"].values())),
        "knativeeventings": normalize_items(list(collected["knativeeventings"].values())),
        "kubevirts": normalize_items(list(collected["kubevirts"].values())),
        "hyperconvergeds": normalize_items(list(collected["hyperconvergeds"].values())),
        "ssps": normalize_items(list(collected["ssps"].values())),
        "cdis": normalize_items(list(collected["cdis"].values())),
        "datavolumes": normalize_items(list(collected["datavolumes"].values())),
        "virtualmachines": normalize_items(list(collected["virtualmachines"].values())),
        "virtualmachineinstances": normalize_items(list(collected["virtualmachineinstances"].values())),
        "datascienceclusters": normalize_items(list(collected["datascienceclusters"].values())),
        "dscinitializations": normalize_items(list(collected["dscinitializations"].values())),
        "icp4aclusters": normalize_items(list(collected["icp4aclusters"].values())),
        "notebooks": normalize_items(list(collected["notebooks"].values())),
        "servingruntimes": normalize_items(list(collected["servingruntimes"].values())),
        "inferenceservices": normalize_items(list(collected["inferenceservices"].values())),
        "modelmeshservings": normalize_items(list(collected["modelmeshservings"].values())),
        "acceleratorprofiles": normalize_items(list(collected["acceleratorprofiles"].values())),
        "nvidiaclusterpolicies": normalize_items(list(collected["nvidiaclusterpolicies"].values())),
        "kataconfigs": normalize_items(list(collected["kataconfigs"].values())),
        "tuneds": normalize_items(list(collected["tuneds"].values())),
        "tunedprofiles": normalize_items(list(collected["tunedprofiles"].values())),
        "nmstates": normalize_items(list(collected["nmstates"].values())),
        "nodenetworkconfigurationpolicies": normalize_items(list(collected["nodenetworkconfigurationpolicies"].values())),
        "nodenetworkstates": normalize_items(list(collected["nodenetworkstates"].values())),
        "deschedulers": normalize_items(list(collected["deschedulers"].values())),
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
        "sources": ordered_sources([name for name, _ in source_pairs]),
        "file_counts": source_file_counts,
        "preferred_order": ["must-gather", "inspect", "oc get", "insights"],
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
