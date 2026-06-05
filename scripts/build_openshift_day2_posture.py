import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

platform = str((((data.get("cluster_profile") or {}).get("platform")) or "unknown")).strip()
deployment_type = str((((data.get("cluster_profile") or {}).get("deployment_type")) or "openshift")).strip().lower()
cluster_classification_label = str((((data.get("cluster_profile") or {}).get("cluster_classification_label")) or deployment_type or "openshift")).strip().lower()
service_model = str((((data.get("cluster_profile") or {}).get("service_model")) or "unknown")).strip().lower()
install_model = str((((data.get("cluster_profile") or {}).get("install_model")) or "unknown")).strip().lower()
install_model_confidence = str((((data.get("cluster_profile") or {}).get("install_model_confidence")) or "low")).strip().lower()
public_cloud = bool(((data.get("cluster_profile") or {}).get("public_cloud")) or False)
cloud_managed = service_model == "managed"
is_sno = bool(((data.get("cluster_profile") or {}).get("is_sno")) or False)
is_hosted_control_plane = bool(((data.get("cluster_profile") or {}).get("is_hosted_control_plane")) or False)

cmc = data.get("cluster_monitoring_config") or {}
clusterversion = data.get("clusterversion") or {}
network_config = data.get("network_config") or {}
apiserver_config = data.get("apiserver_config") or {}
openshift_apiserver = data.get("openshift_apiserver") or {}
kube_apiserver = data.get("kube_apiserver") or {}
authentication_operator = data.get("authentication_operator") or {}
project_config = data.get("project_config") or {}
proxy_config = data.get("proxy_config") or {}
image_config = data.get("image_config") or {}
imagedigestmirrorsets = data.get("imagedigestmirrorsets") or []
imagetagmirrorsets = data.get("imagetagmirrorsets") or []
imagecontentsourcepolicies = data.get("imagecontentsourcepolicies") or []
catalogsources = data.get("catalogsources") or []
clustercatalogs = data.get("clustercatalogs") or []
updateservices = data.get("updateservices") or []
subscriptions = data.get("subscriptions") or []
flowcollectors = data.get("flowcollectors") or []
control_plane_backup_evidence = data.get("control_plane_backup_evidence") or {}
nodes = data.get("nodes") or []
ingresscontrollers = data.get("ingresscontrollers") or []
uwm = data.get("user_workload_monitoring_config") or {}
auth_posture_summary = data.get("auth_posture_summary") or {}
prom_k8s = (cmc.get("prometheusK8s") or {})
alertmanager_main = (cmc.get("alertmanagerMain") or {})
thanos_ruler = (cmc.get("thanosRuler") or {})
enable_user_workload = bool(cmc.get("enableUserWorkload", False))
is_multi_node_cluster = len(nodes) > 1
prometheus_storage_request = str((((prom_k8s.get("volumeClaimTemplate") or {}).get("spec") or {}).get("resources") or {}).get("requests", {}).get("storage") or "").strip()
alertmanager_storage_request = str((((alertmanager_main.get("volumeClaimTemplate") or {}).get("spec") or {}).get("resources") or {}).get("requests", {}).get("storage") or "").strip()
thanos_ruler_storage_request = str((((thanos_ruler.get("volumeClaimTemplate") or {}).get("spec") or {}).get("resources") or {}).get("requests", {}).get("storage") or "").strip()
prometheus_persistent = bool(prom_k8s.get("volumeClaimTemplate")) and bool(prometheus_storage_request)
alertmanager_persistent = bool(alertmanager_main.get("volumeClaimTemplate")) and bool(alertmanager_storage_request)
thanos_ruler_persistent = bool(thanos_ruler.get("volumeClaimTemplate")) and bool(thanos_ruler_storage_request)
monitoring_persistence_present = bool(
    prometheus_persistent
    or alertmanager_persistent
    or thanos_ruler_persistent
)
monitoring_persistent = bool(
    prometheus_persistent
    and alertmanager_persistent
    and ((not is_multi_node_cluster) or thanos_ruler_persistent)
)
default_network = ((network_config.get("spec") or {}).get("defaultNetwork") or {})
ovn_config = default_network.get("ovnKubernetesConfig") or {}
ipsec_config = ovn_config.get("ipsecConfig")
network_type = str(((network_config.get("status") or {}).get("networkType") or default_network.get("type") or "unknown"))
ovn_network = network_type.lower() == "ovnkubernetes"
ipsec_mode = str((ipsec_config or {}).get("mode") or ("Full" if isinstance(ipsec_config, dict) else "Disabled")).strip()
ipsec_mode_normalized = ipsec_mode.lower()
ipsec_config_present = isinstance(ipsec_config, dict)
ovn_ipsec_external_only = bool(
    ovn_network
    and ipsec_config_present
    and ipsec_mode_normalized == "external"
)
ovn_ipsec_encryption = bool(
    ovn_network
    and ipsec_config_present
    and ipsec_mode_normalized == "full"
)
etcd_encryption_type = str((((apiserver_config.get("spec") or {}).get("encryption") or {}).get("type") or "identity")).strip().lower()
etcd_encryption = etcd_encryption_type in {"aescbc", "aesgcm"}
def encrypted_condition_details(obj):
    condition = next(
        (
            item for item in ((obj.get("status") or {}).get("conditions") or [])
            if str(item.get("type") or "").strip().lower() == "encrypted"
        ),
        {},
    )
    status = str(condition.get("status") or "").strip()
    reason = str(condition.get("reason") or "").strip()
    return {
        "status": status,
        "status_normalized": status.lower(),
        "reason": reason,
        "reason_normalized": reason.lower(),
        "message": str(condition.get("message") or "").strip(),
        "reported": bool(condition),
        "complete": status.lower() == "true" and "completed" in reason.lower(),
    }

etcd_encryption_conditions = {
    "openshift_apiserver": encrypted_condition_details(openshift_apiserver),
    "kube_apiserver": encrypted_condition_details(kube_apiserver),
    "authentication_operator": encrypted_condition_details(authentication_operator),
}
etcd_encryption_reported_components = [
    name for name, details in etcd_encryption_conditions.items()
    if details.get("reported")
]
etcd_encryption_completed_components = [
    name for name, details in etcd_encryption_conditions.items()
    if details.get("complete")
]
etcd_encryption_missing_components = [
    name for name, details in etcd_encryption_conditions.items()
    if not details.get("complete")
]
etcd_encryption_evidence_complete = bool(etcd_encryption_reported_components) and len(etcd_encryption_missing_components) == 0
etcd_encryption_complete = bool(etcd_encryption) and etcd_encryption_evidence_complete

def format_etcd_encryption_details():
    component_labels = {
        "openshift_apiserver": "openshift-apiserver",
        "kube_apiserver": "kube-apiserver",
        "authentication_operator": "authentication",
    }
    parts = [f"apiserver_encryption_type={etcd_encryption_type}"]
    parts.append(
        "rolloutEvidenceReported="
        + f"{len(etcd_encryption_reported_components)}/{len(etcd_encryption_conditions)}"
    )
    for key in ["openshift_apiserver", "kube_apiserver", "authentication_operator"]:
        details = etcd_encryption_conditions.get(key) or {}
        status = details.get("status") or "not-reported"
        reason = details.get("reason") or "not-reported"
        parts.append(f"{component_labels[key]}={status}/{reason}")
    return " ".join(parts)

def format_etcd_encryption_component_names(items):
    component_labels = {
        "apiserver": "apiserver.config",
        "openshift_apiserver": "openshift-apiserver",
        "kube_apiserver": "kube-apiserver",
        "authentication_operator": "authentication",
    }
    return [component_labels.get(item, item) for item in items]

etcd_encryption_detail_text = format_etcd_encryption_details()
proxy_spec = proxy_config.get("spec") or {}
image_spec = image_config.get("spec") or {}
cluster_proxy_configured = bool(proxy_spec.get("httpProxy") or proxy_spec.get("httpsProxy"))
proxy_no_proxy_entries = [
    item.strip()
    for item in str(proxy_spec.get("noProxy") or "").split(",")
    if item.strip()
]
proxy_required_internal_no_proxy_entries = [".svc", ".cluster.local"]
proxy_missing_internal_no_proxy_entries = (
    []
    if not cluster_proxy_configured
    else [item for item in proxy_required_internal_no_proxy_entries if item not in proxy_no_proxy_entries]
)
cluster_proxy_healthy = bool(
    cluster_proxy_configured
    and len(proxy_missing_internal_no_proxy_entries) == 0
)
custom_ca_configured = bool(
    ((proxy_spec.get("trustedCA") or {}).get("name"))
    or ((image_spec.get("additionalTrustedCA") or {}).get("name"))
)
registry_sources = image_spec.get("registrySources") or {}
mirror_resource_count = len(imagedigestmirrorsets) + len(imagetagmirrorsets) + len(imagecontentsourcepolicies)
restricted_registry_sources = bool(registry_sources.get("allowedRegistries") or registry_sources.get("blockedRegistries"))
allowed_imports = [
    item for item in (image_spec.get("allowedRegistriesForImport") or [])
    if str(item or "").strip()
]
insecure_registries = [
    item for item in (registry_sources.get("insecureRegistries") or [])
    if str(item or "").strip()
]
public_registry_hints = ["registry.redhat.io", "quay.io", "registry.connect.redhat.com", "registry.access.redhat.com"]

def is_public_image_ref(value):
    text = str(value or "").strip().lower()
    registry = text.split("/", 1)[0]
    return bool(registry) and registry in public_registry_hints

def collect_mirror_pairs(items, key):
    pairs = []
    for item in items:
        spec = item.get("spec") or {}
        for entry in spec.get(key) or []:
            source = str(entry.get("source") or "").strip()
            for mirror in entry.get("mirrors") or []:
                mirror_text = str(mirror or "").strip()
                if mirror_text:
                    pairs.append({"source": source, "mirror": mirror_text})
    return pairs

def collect_mirror_targets(items, key):
    targets = []
    for pair in collect_mirror_pairs(items, key):
        mirror_text = pair.get("mirror")
        if mirror_text:
            targets.append(mirror_text)
    return targets

digest_mirror_pairs = collect_mirror_pairs(imagedigestmirrorsets, "imageDigestMirrors")
tag_mirror_pairs = collect_mirror_pairs(imagetagmirrorsets, "imageTagMirrors")
icsp_mirror_pairs = collect_mirror_pairs(imagecontentsourcepolicies, "repositoryDigestMirrors")
all_mirror_pairs = digest_mirror_pairs + tag_mirror_pairs + icsp_mirror_pairs
digest_mirror_targets = collect_mirror_targets(imagedigestmirrorsets, "imageDigestMirrors")
tag_mirror_targets = collect_mirror_targets(imagetagmirrorsets, "imageTagMirrors")
icsp_mirror_targets = collect_mirror_targets(imagecontentsourcepolicies, "repositoryDigestMirrors")
all_mirror_targets = sorted({item for item in (digest_mirror_targets + tag_mirror_targets + icsp_mirror_targets) if item})
local_mirror_targets = [item for item in all_mirror_targets if not is_public_image_ref(item)]
release_payload_source_hints = [
    "quay.io/openshift-release-dev",
    "quay.io/okd",
    "registry.ci.openshift.org",
    "registry.redhat.io/openshift4",
]
release_image_mirror_configured = any(
    any(hint in str(pair.get("source") or "").lower() for hint in release_payload_source_hints)
    and not is_public_image_ref(pair.get("mirror"))
    for pair in all_mirror_pairs
)
disconnected_catalog_count = len([
    item for item in catalogsources
    if str((((item.get("spec") or {}).get("image")) or "")).strip()
    and not is_public_image_ref(((item.get("spec") or {}).get("image")))
])
disconnected_clustercatalog_count = len([
    item for item in clustercatalogs
    if not is_public_image_ref((((item.get("spec") or {}).get("source") or {}).get("image") or {}).get("ref"))
])
public_catalogsource_count = len([
    item for item in catalogsources
    if is_public_image_ref(((item.get("spec") or {}).get("image")))
])
public_clustercatalog_count = len([
    item for item in clustercatalogs
    if is_public_image_ref((((item.get("spec") or {}).get("source") or {}).get("image") or {}).get("ref"))
])
release_image = str((((clusterversion.get("status") or {}).get("desired") or {}).get("image") or "")).strip()
release_image_mirrored = bool(release_image) and (not is_public_image_ref(release_image) or release_image_mirror_configured)
updateservice_present = len(updateservices) > 0
deprecated_icsp_only = len(imagecontentsourcepolicies) > 0 and len(imagedigestmirrorsets) == 0 and len(imagetagmirrorsets) == 0
cluster_image_mirror_configuration_present = mirror_resource_count > 0
disconnected_cluster_image_sources_present = mirror_resource_count > 0 or disconnected_catalog_count > 0 or disconnected_clustercatalog_count > 0 or updateservice_present
disconnected_operator_sources_ready = (len(subscriptions) == 0) or (disconnected_catalog_count + disconnected_clustercatalog_count) > 0
disconnected_cluster_image_sources_healthy = bool(
    mirror_resource_count > 0
    and len(local_mirror_targets) > 0
    and release_image_mirrored
    and disconnected_operator_sources_ready
)

argocds = data.get("argocds") or []
templates = data.get("templates") or []
gitops_apps = data.get("gitops_applications") or []
gitops_projects = data.get("gitops_appprojects") or []
clustersecretstores = data.get("clustersecretstores") or []
secretstores = data.get("secretstores") or []
externalsecrets = data.get("externalsecrets") or []
secretproviderclasses = data.get("secretproviderclasses") or []
clusterautoscalers = data.get("clusterautoscalers") or []
kubeletconfigs = data.get("kubeletconfigs") or []
hostedclusters = data.get("hostedclusters") or []
nodepools = data.get("nodepools") or []
checlusters = data.get("checlusters") or []
backstages = data.get("backstages") or []
devworkspaces = data.get("devworkspaces") or []
devworkspaceoperatorconfigs = data.get("devworkspaceoperatorconfigs") or []
devworkspaceroutings = data.get("devworkspaceroutings") or []
dynakubes = data.get("dynakubes") or []
edgeconnects = data.get("edgeconnects") or []
datadogagents = data.get("datadogagents") or []
clusteragents = data.get("clusteragents") or []
infravizs = data.get("infravizs") or []
ansibleautomationplatforms = data.get("ansibleautomationplatforms") or []
automationcontrollers = data.get("automationcontrollers") or []
automationhubs = data.get("automationhubs") or []
edas = data.get("edas") or []
kedacontrollers = data.get("kedacontrollers") or []
scaledobjects = data.get("scaledobjects") or []
scaledjobs = data.get("scaledjobs") or []
triggerauthentications = data.get("triggerauthentications") or []
clustertriggerauthentications = data.get("clustertriggerauthentications") or []
costmanagementmetricsconfigs = data.get("costmanagementmetricsconfigs") or []
klusterlets = data.get("klusterlets") or []
managedclusteraddons = data.get("managedclusteraddons") or []
namespaces = data.get("namespaces") or []
pods = data.get("pods") or []
deployments = data.get("deployments") or []
statefulsets = data.get("statefulsets") or []
daemonsets = data.get("daemonsets") or []
serviceaccounts = data.get("serviceaccounts") or []
rolebindings = data.get("rolebindings") or []
clusterrolebindings = data.get("clusterrolebindings") or []
networkpolicies = data.get("networkpolicies") or []
resourcequotas = data.get("resourcequotas") or []
limitranges = data.get("limitranges") or []
secrets = data.get("secrets") or []
configmaps = data.get("configmaps") or []
crds = data.get("crds") or []
servicemonitors = data.get("servicemonitors") or []
podmonitors = data.get("podmonitors") or []
ingresscontroller_summary = data.get("ingresscontroller_summary") or []
ingresscontroller_issues = data.get("ingresscontroller_issues") or []
clusterlogforwarders = data.get("clusterlogforwarders") or []
lokistacks = data.get("lokistacks") or []
grafanadashboards = data.get("grafanadashboards") or []
backupstoragelocations = data.get("backupstoragelocations") or []
schedules = data.get("schedules") or []
dataprotectionapplications = data.get("dataprotectionapplications") or []
drpolicies = data.get("drpolicies") or []
drclusters = data.get("drclusters") or []
drplacementcontrols = data.get("drplacementcontrols") or []
volumereplicationgroups = data.get("volumereplicationgroups") or []
volumereplications = data.get("volumereplications") or []
volumereplicationclasses = data.get("volumereplicationclasses") or []
volumegroupreplications = data.get("volumegroupreplications") or []
compliancesuites = data.get("compliancesuites") or []
compliance_operator_summary = data.get("compliance_operator_summary") or {}
compliance_standards_summary = data.get("compliance_standards_summary") or []
compliance_standards_findings = data.get("compliance_standards_findings") or []
machinehealthchecks = data.get("machinehealthchecks") or []
machineautoscalers = data.get("machineautoscalers") or []
egressfirewalls = data.get("egressfirewalls") or []
validatingadmissionpolicies = data.get("validatingadmissionpolicies") or []
validatingadmissionpolicybindings = data.get("validatingadmissionpolicybindings") or []
kyverno_policies = data.get("kyverno_policies") or []
kyverno_clusterpolicies = data.get("kyverno_clusterpolicies") or []
machinesets = data.get("machinesets") or []
backup_posture_findings = data.get("backup_posture_findings") or []
pipelines = data.get("pipelines") or []
pipelineruns = data.get("pipelineruns") or []
storageclusters = data.get("storageclusters") or []
cephclusters = data.get("cephclusters") or []
noobaas = data.get("noobaas") or []
storageclasses = data.get("storageclasses") or data.get("storage_classes") or []
kubevirts = data.get("kubevirts") or []
hyperconvergeds = data.get("hyperconvergeds") or []
ssps = data.get("ssps") or []
cdis = data.get("cdis") or []
datavolumes = data.get("datavolumes") or []
virtualmachines = data.get("virtualmachines") or []
virtualmachineinstances = data.get("virtualmachineinstances") or []
datascienceclusters = data.get("datascienceclusters") or []
dscinitializations = data.get("dscinitializations") or []
icp4aclusters = data.get("icp4aclusters") or []
notebooks = data.get("notebooks") or []
servingruntimes = data.get("servingruntimes") or []
inferenceservices = data.get("inferenceservices") or []
modelmeshservings = data.get("modelmeshservings") or []
acceleratorprofiles = data.get("acceleratorprofiles") or []
servicemeshcontrolplanes = data.get("servicemeshcontrolplanes") or []
servicemeshmemberrolls = data.get("servicemeshmemberrolls") or []
servicemeshmembers = data.get("servicemeshmembers") or []
knativeservings = data.get("knativeservings") or []
knativeeventings = data.get("knativeeventings") or []
knativeservices = data.get("knativeservices") or []
nvidiaclusterpolicies = data.get("nvidiaclusterpolicies") or []
kataconfigs = data.get("kataconfigs") or []
tuneds = data.get("tuneds") or []
tunedprofiles = data.get("tunedprofiles") or []
performanceprofiles = data.get("performanceprofiles") or []
nmstates = data.get("nmstates") or []
nodenetworkconfigurationpolicies = data.get("nodenetworkconfigurationpolicies") or []
nodenetworkstates = data.get("nodenetworkstates") or []
deschedulers = data.get("deschedulers") or []
operators = data.get("clusteroperators") or {}
obs = data.get("observability_forwarding_summary") or {}
backup_posture = data.get("backup_posture") or {}
platform_health_summary = data.get("platform_health_summary") or {}
groups = data.get("groups") or []

insights = operators.get("insights", {}) or {}
insights_healthy = insights.get("available") == "True" and insights.get("degraded") != "True"
namespace_names = {((item.get("metadata") or {}).get("name") or "") for item in namespaces}
user_namespace_names = {
    name for name in namespace_names
    if name
    and name not in {"default", "kube-node-lease", "kube-public", "kube-system"}
    and not name.startswith("openshift")
}
acm_agent_namespaces = sorted(
    name for name in namespace_names
    if name in {"open-cluster-management-agent", "open-cluster-management-agent-addon"}
)
group_names = {
    str(((item.get("metadata") or {}).get("name")) or "").strip()
    for item in groups
    if str(((item.get("metadata") or {}).get("name")) or "").strip()
}
subscription_packages = {
    str((((item.get("spec") or {}).get("name")) or "")).strip()
    for item in subscriptions
    if str((((item.get("spec") or {}).get("name")) or "")).strip()
}
subscription_namespaces = {
    str((((item.get("metadata") or {}).get("namespace")) or "")).strip()
    for item in subscriptions
    if str((((item.get("metadata") or {}).get("namespace")) or "")).strip()
}

def pod_spec_from(obj):
    spec = obj.get("spec") or {}
    return ((spec.get("template") or {}).get("spec") or spec)

def normalized_image_tokens(image):
    value = str(image or "").strip().lower()
    if not value:
        return []
    image_no_digest = value.split("@", 1)[0]
    leaf = image_no_digest.rsplit("/", 1)[-1]
    image_no_tag = image_no_digest.rsplit(":", 1)[0] if ":" in leaf else image_no_digest
    path_parts = [part for part in image_no_tag.split("/") if part]
    tokens = {value, image_no_digest, image_no_tag}
    if path_parts:
        tokens.add(path_parts[-1])
        tokens.update(path_parts)
    return [token for token in tokens if token]

def text_blob(obj):
    meta = obj.get("metadata") or {}
    labels = meta.get("labels") or {}
    spec = pod_spec_from(obj)
    parts = [meta.get("name") or "", meta.get("namespace") or ""]
    parts.extend([str(k) for k in labels.keys()])
    parts.extend([str(v) for v in labels.values()])
    for container in (spec.get("containers") or []) + (spec.get("initContainers") or []):
        parts.extend([container.get("name") or "", container.get("image") or ""])
        parts.extend(normalized_image_tokens(container.get("image")))
    return " ".join(parts).lower()

def any_keyword(keywords, values):
    return any(any(keyword in value for keyword in keywords) for value in values)

crd_names = {((item.get("metadata") or {}).get("name") or "").lower() for item in crds}

def crd_has(*needles):
    return any(any(needle in name for needle in needles) for name in crd_names)

def status_conditions(obj):
    return ((obj.get("status") or {}).get("conditions") or [])

def status_text(obj, *keys):
    status = obj.get("status") or {}
    for key in keys:
        value = status.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""

def policy_types(obj):
    return {
        str(item).strip()
        for item in (((obj.get("spec") or {}).get("policyTypes")) or [])
        if str(item).strip()
    }

def has_match_all_pod_selector(obj):
    selector = ((obj.get("spec") or {}).get("podSelector"))
    return isinstance(selector, dict) and len(selector) == 0

def policy_rule_declared(obj, rule_key):
    spec = obj.get("spec") or {}
    return rule_key in spec and isinstance(spec.get(rule_key), list)

def metadata_labels(obj):
    return {
        str(key): str(value)
        for key, value in (((obj.get("metadata") or {}).get("labels")) or {}).items()
    }

def template_labels(obj):
    template_meta = (((obj.get("spec") or {}).get("template")) or {}).get("metadata") or {}
    return {
        str(key): str(value)
        for key, value in (template_meta.get("labels") or {}).items()
    }

def selector_match_labels(obj):
    selector = ((obj.get("spec") or {}).get("selector")) or {}
    return {
        str(key): str(value)
        for key, value in (selector.get("matchLabels") or {}).items()
    }

def selector_match_expressions(obj):
    selector = ((obj.get("spec") or {}).get("selector")) or {}
    return [
        item for item in (selector.get("matchExpressions") or [])
        if isinstance(item, dict)
    ]

def labels_match_selector(labels, match_labels, match_expressions):
    for key, value in (match_labels or {}).items():
        if str(labels.get(key) or "") != str(value):
            return False
    for expression in (match_expressions or []):
        key = str(expression.get("key") or "")
        operator = str(expression.get("operator") or "")
        values = [str(item) for item in (expression.get("values") or [])]
        current = str(labels.get(key) or "")
        if operator == "In" and current not in values:
            return False
        if operator == "NotIn" and current in values:
            return False
        if operator == "Exists" and key not in labels:
            return False
        if operator == "DoesNotExist" and key in labels:
            return False
    return True

def has_true_condition(obj, *condition_types):
    wanted = {item.lower() for item in condition_types}
    for condition in status_conditions(obj):
        condition_type = str(condition.get("type") or "").strip().lower()
        condition_status = str(condition.get("status") or "").strip().lower()
        if condition_type in wanted and condition_status == "true":
            return True
    return False

def has_problem_condition(obj):
    for condition in status_conditions(obj):
        condition_status = str(condition.get("status") or "").strip().lower()
        condition_text = " ".join([
            str(condition.get("type") or ""),
            str(condition.get("reason") or ""),
            str(condition.get("message") or ""),
        ]).lower()
        if (
            ("error" in condition_text or "failed" in condition_text or "critical" in condition_text or "degraded" in condition_text)
            and condition_status != "false"
        ):
            return True
    return False

def has_problem_status(obj):
    status_blob = " ".join([
        status_text(obj, "phase", "state", "progression"),
        str(((obj.get("status") or {}).get("message")) or ""),
        str(((obj.get("status") or {}).get("reason")) or ""),
    ]).lower()
    return any(token in status_blob for token in ["error", "failed", "critical", "degraded"])

def image_registry(image):
    value = str(image or "").strip()
    first = value.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first.lower()
    return "docker.io"

all_workloads = pods + deployments + statefulsets + daemonsets
all_workload_blobs = [text_blob(item) for item in all_workloads]
all_workload_object_blobs = [
    json.dumps(item, sort_keys=True, default=str).lower()
    for item in all_workloads
]
all_configuration_object_blobs = all_workload_object_blobs + [
    json.dumps(item, sort_keys=True, default=str).lower()
    for item in configmaps + secrets + serviceaccounts
]
backup_provider_inventory_blobs = all_workload_blobs + [
    json.dumps(item, sort_keys=True, default=str).lower()
    for item in namespaces + subscriptions + crds + serviceaccounts + rolebindings + clusterrolebindings
]
velero_component_blobs = backup_provider_inventory_blobs + [
    json.dumps(item, sort_keys=True, default=str).lower()
    for item in backupstoragelocations + schedules
]
oadp_backup_provider_present = bool(
    dataprotectionapplications
    or any("oadp" in package.lower() for package in subscription_packages)
    or "openshift-adp" in namespace_names
    or crd_has("dataprotectionapplications.oadp.openshift.io")
)
velero_backup_provider_present = bool(
    backupstoragelocations
    or schedules
    or any("velero" in package.lower() for package in subscription_packages)
    or any("velero" in name.lower() for name in namespace_names)
    or crd_has("velero.io")
    or any_keyword(["velero"], velero_component_blobs)
)
commvault_backup_provider_present = bool(
    any("commvault" in package.lower() for package in subscription_packages)
    or any("commvault" in name.lower() for name in namespace_names)
    or crd_has("commvault")
    or any_keyword(["commvault"], backup_provider_inventory_blobs)
)
workload_backup_provider_present = bool(
    oadp_backup_provider_present
    or velero_backup_provider_present
    or commvault_backup_provider_present
)
worker_machinesets = []
for item in machinesets:
    combined_labels = {}
    combined_labels.update(metadata_labels(item))
    combined_labels.update(template_labels(item))
    role_value = str(combined_labels.get("machine.openshift.io/cluster-api-machine-role") or "").strip().lower()
    type_value = str(combined_labels.get("machine.openshift.io/cluster-api-machine-type") or "").strip().lower()
    role_blob = " ".join([role_value, type_value, json.dumps(combined_labels)]).lower()
    if "worker" in role_blob and "infra" not in role_blob and "master" not in role_blob and "control-plane" not in role_blob:
        worker_machinesets.append({
            "name": str((((item.get("metadata") or {}).get("name")) or "")).strip(),
            "namespace": str((((item.get("metadata") or {}).get("namespace")) or "")).strip(),
            "labels": combined_labels,
        })
internal_registry_markers = [
    ".svc", ".cluster.local", "image-registry.openshift-image-registry.svc",
    "quay.io/openshift", "registry.redhat.io", "registry.access.redhat.com",
]
public_registry_names = {"docker.io", "index.docker.io", "quay.io", "ghcr.io", "gcr.io", "registry.k8s.io", "k8s.gcr.io"}
external_image_registries = set()
credentialed_public_image_registries = set()
workloads_with_pull_secret = 0
external_private_registry_workload_count = 0
external_private_registry_workloads_with_pull_secret = 0
external_private_registry_workloads_with_serviceaccount_pull_secret = 0
serviceaccount_pull_secret_refs = {
    (
        str(((item.get("metadata") or {}).get("namespace")) or "").strip(),
        str(((item.get("metadata") or {}).get("name")) or "").strip(),
    ): item.get("imagePullSecrets") or []
    for item in serviceaccounts
}
for obj in all_workloads:
    spec = pod_spec_from(obj)
    metadata = obj.get("metadata") or {}
    namespace = str(metadata.get("namespace") or "").strip()
    service_account_name = str(spec.get("serviceAccountName") or "default").strip() or "default"
    pull_secrets = spec.get("imagePullSecrets") or []
    if pull_secrets:
        workloads_with_pull_secret += 1
    serviceaccount_pull_secrets = serviceaccount_pull_secret_refs.get((namespace, service_account_name), [])
    workload_uses_external_private_registry = False
    for container in (spec.get("containers") or []) + (spec.get("initContainers") or []):
        registry = image_registry(container.get("image"))
        if registry and registry not in public_registry_names and not any(marker in registry for marker in internal_registry_markers):
            external_image_registries.add(registry)
            workload_uses_external_private_registry = True
        elif registry in public_registry_names and pull_secrets:
            credentialed_public_image_registries.add(registry)
    if workload_uses_external_private_registry:
        external_private_registry_workload_count += 1
        if pull_secrets:
            external_private_registry_workloads_with_pull_secret += 1
        elif serviceaccount_pull_secrets:
            external_private_registry_workloads_with_serviceaccount_pull_secret += 1
dockerconfig_secret_count = len([item for item in secrets if item.get("type") in ["kubernetes.io/dockerconfigjson", "kubernetes.io/dockercfg"]])
serviceaccount_pull_secret_count = sum(len((item.get("imagePullSecrets") or [])) for item in serviceaccounts)
external_private_registry_workloads_present = len(external_image_registries) > 0
workloads_using_external_private_registries_present = (external_private_registry_workloads_present and (
    external_private_registry_workloads_with_pull_secret > 0
    or external_private_registry_workloads_with_serviceaccount_pull_secret > 0
)) or len(credentialed_public_image_registries) > 0
windows_nodes = [
    node for node in nodes
    if "windows" in str((((node.get("metadata") or {}).get("labels") or {}).get("kubernetes.io/os") or "")).lower()
]
windows_workload_objects = []
for obj in all_workloads:
    spec = pod_spec_from(obj)
    selectors = spec.get("nodeSelector") or {}
    os_name = ((spec.get("os") or {}).get("name") or "")
    affinity_blob = json.dumps(spec.get("affinity") or {}).lower()
    blob = text_blob(obj)
    if (
        str(selectors.get("kubernetes.io/os") or "").lower() == "windows"
        or str(selectors.get("beta.kubernetes.io/os") or "").lower() == "windows"
        or str(os_name).lower() == "windows"
        or "windows" in affinity_blob
        or "windows" in blob
    ):
        windows_workload_objects.append(obj)
dashboard_configmaps = [
    item for item in configmaps
    if (
        any("grafana_dashboard" in str(k).lower() or "grafana_dashboard" in str(v).lower() for k, v in ((item.get("metadata") or {}).get("labels") or {}).items())
        or any(str(key).lower().endswith(".json") and "dashboard" in str(value).lower() for key, value in ((item.get("data") or {}).items()))
    )
]
grafana_present = any_keyword(["grafana"], all_workload_blobs) or "grafana" in namespace_names
grafana_dashboard_crd_present = crd_has("grafanadashboards", "grafana.integreatly.org", "grafana.com")
grafana_dashboard_present = bool(len(dashboard_configmaps) > 0 or len(grafanadashboards) > 0)
workload_vulnerability_report_crd_present = crd_has("aquasecurity.github.io", "vulnerabilityreports")
admission_policy_engine_present = bool(
    "gatekeeper-system" in namespace_names
    or "kyverno" in namespace_names
    or crd_has("gatekeeper.sh", "kyverno.io", "validatingadmissionpolicy")
)
trusted_image_policy_keywords = [
    "image",
    "registry",
    "repository",
    "digest",
    "signature",
    "signed",
    "cosign",
    "notary",
    "allowedregistries",
    "blockedregistries",
]
image_admission_policy_resources = [
    item
    for item in (
        validatingadmissionpolicies
        + validatingadmissionpolicybindings
        + kyverno_policies
        + kyverno_clusterpolicies
    )
    if any(keyword in text_blob(item) for keyword in trusted_image_policy_keywords)
]
active_trusted_image_policy_present = bool(
    len(allowed_imports) > 0
    or restricted_registry_sources
    or len(image_admission_policy_resources) > 0
)
image_signature_and_admission_policy_present = bool(
    active_trusted_image_policy_present
)
image_signature_and_admission_policy_healthy = bool(
    image_signature_and_admission_policy_present
    and len(insecure_registries) == 0
)
workload_scanner_subscription_present = any(
    package in subscription_packages
    for package in {
        "trivy-operator",
        "container-security-operator",
        "aqua",
        "aqua-operator",
        "qualys-cloud-agent-operator",
        "prisma-cloud-compute",
        "sysdig-secure",
    }
)
workload_scanner_workload_present = any_keyword(
    [
        "trivy-operator",
        "starboard",
        "trivy-scanner",
        "aqua",
        "enforcer",
        "kube-enforcer",
        "qualys",
        "qualys-cloud-agent",
        "defender",
        "twistlock",
        "sysdig-agent",
        "sysdig-secure",
        "secure-runtime",
        "vulnerability-scanner",
    ],
    all_workload_blobs,
)
workload_scanner_namespace_present = any(
    name in namespace_names
    for name in {
        "trivy-system",
        "starboard-system",
        "twistlock",
        "sysdig-agent",
        "aqua",
        "qualys",
        "qualys-agent",
    }
)
workload_scanner_context_present = bool(
    workload_scanner_subscription_present
    or
    workload_vulnerability_report_crd_present
    or workload_scanner_workload_present
    or workload_scanner_namespace_present
)
workload_scanner_present = bool(workload_scanner_workload_present)
dynatrace_operator_subscription_present = "dynatrace-operator" in subscription_packages
dynatrace_namespace_present = "dynatrace" in namespace_names
dynatrace_crd_present = crd_has(
    "dynakubes.dynatrace.com",
    "dynakube.dynatrace.com",
    "edgeconnects.dynatrace.com",
    "edgeconnect.dynatrace.com",
)
dynatrace_operator_workload_present = any_keyword(
    ["dynatrace-operator", "dynatrace-webhook"],
    all_workload_blobs,
)
dynatrace_observability_workload_present = any_keyword(
    [
        "dynakube",
        "oneagent",
        "activegate",
        "dynatrace-otel-collector",
        "dynatrace-logmonitoring",
        "dynatrace-extension-controller",
        "dynatrace-extensions-collector",
        "dynatrace-node-config-collector",
        "dynatrace-oneagent-csi-driver",
    ],
    all_workload_blobs,
)
dynatrace_dynakube_present = len(dynakubes) > 0
dynatrace_edgeconnect_present = len(edgeconnects) > 0
dynatrace_context_present = bool(
    dynatrace_operator_subscription_present
    or dynatrace_namespace_present
    or dynatrace_crd_present
    or dynatrace_operator_workload_present
    or dynatrace_edgeconnect_present
)
dynatrace_observability_present = bool(
    dynatrace_dynakube_present
    or dynatrace_edgeconnect_present
    or dynatrace_observability_workload_present
)
qualys_subscription_present = "qualys-cloud-agent-operator" in subscription_packages
qualys_namespace_present = "qualys" in namespace_names or "qualys-agent" in namespace_names
qualys_crd_present = crd_has("qualys")
qualys_operator_workload_present = any_keyword(
    [
        "qualys-cloud-agent-operator",
    ],
    all_workload_blobs,
)
qualys_workload_present = any_keyword(
    [
        "qualys-cloud-agent",
        "qualys-agent",
        "qualys-container-sensor",
        "qcs-sensor",
        "qualys/qcs-sensor",
        "cluster-sensor",
        "qualys/cluster-sensor",
    ],
    all_workload_blobs,
)
qualys_k8s_mode_arg_present = any(
    any(token in blob for token in ['"--k8s-mode"', '"--registry-sensor"', '"--cicd-deployed-sensor"', '"--sensor-without-persistent-storage"'])
    for blob in all_workload_object_blobs
)
qualys_privileged_security_context_present = any(
    '"privileged": true' in blob
    for blob in all_workload_object_blobs
)
qualys_service_account_config_present = any(
    '"serviceaccountname": "qualysuser"' in blob or '"serviceaccountname": "qualys' in blob
    for blob in all_workload_object_blobs
)
qualys_activation_config_present = any(
    any(token in blob for token in ["activationid", "customerid", "activation id", "customer id"])
    for blob in all_configuration_object_blobs
)
qualys_required_deployment_configuration_present = bool(
    qualys_k8s_mode_arg_present
    and (
        qualys_privileged_security_context_present
        or qualys_service_account_config_present
        or qualys_activation_config_present
    )
)
qualys_scanning_agents_present = bool(
    qualys_workload_present
)
qualys_scanning_agents_context_present = bool(
    qualys_subscription_present
    or qualys_namespace_present
    or qualys_crd_present
    or qualys_operator_workload_present
    or qualys_workload_present
)
trivy_subscription_present = "trivy-operator" in subscription_packages
trivy_namespace_present = "trivy-system" in namespace_names or "starboard-system" in namespace_names
trivy_crd_present = crd_has(
    "vulnerabilityreports.aquasecurity.github.io",
    "configauditreports.aquasecurity.github.io",
    "rbacassessmentreports.aquasecurity.github.io",
    "exposedsecretreports.aquasecurity.github.io",
    "clustercompliancereports.aquasecurity.github.io",
)
trivy_workload_present = any_keyword(
    [
        "trivy-operator",
        "starboard",
        "trivy-scanner",
    ],
    all_workload_blobs,
)
trivy_operator_context_present = bool(
    trivy_subscription_present
    or trivy_namespace_present
    or trivy_crd_present
)
prisma_subscription_present = "prisma-cloud-compute" in subscription_packages or "prisma-cloud-operator" in subscription_packages
prisma_namespace_present = "twistlock" in namespace_names or "prisma-cloud" in namespace_names
prisma_crd_present = crd_has("twistlock", "defenders.compute.paloaltonetworks.com", "prismacloud")
prisma_workload_present = any_keyword(
    [
        "twistlock",
        "twistlock-defender",
        "twistlock-console",
        "prisma-cloud",
        "prisma-cloud-defender",
        "prisma-cloud-console",
        "defenders.compute.paloaltonetworks.com",
    ],
    all_workload_blobs,
)
prisma_twistlock_context_present = bool(
    prisma_subscription_present
    or prisma_namespace_present
    or prisma_crd_present
)
prisma_twistlock_defenders_present = bool(prisma_workload_present)
aqua_subscription_present = "aqua" in subscription_packages or "aqua-operator" in subscription_packages
aqua_namespace_present = "aqua" in namespace_names
aqua_crd_present = crd_has("aqua.security", "aquasecurity.github.io/v1alpha1")
aqua_workload_present = any_keyword(
    [
        "aqua-operator",
        "aqua-console",
        "aqua-gateway",
        "aqua-enforcer",
        "kube-enforcer",
        "microenforcer",
    ],
    all_workload_blobs,
)
aqua_platform_context_present = bool(
    aqua_subscription_present
    or aqua_namespace_present
    or aqua_crd_present
)
aqua_security_platform_present = bool(aqua_workload_present)
splunk_namespace_present = "splunk" in namespace_names
splunk_crd_present = crd_has(
    "enterprise.splunk.com",
    "monitoring.splunk.com",
    "collectors.splunk.com",
    "opentelemetrycollectors.opentelemetry.io",
    "otelcollectors.opentelemetry.io",
)
splunk_operator_workload_present = any_keyword(
    [
        "splunk-otel-operator",
    ],
    all_workload_blobs,
)
splunk_workload_present = any_keyword(
    [
        "splunk-otel-collector",
        "splunk-connect-for-kubernetes",
        "splunk-cluster-receiver",
        "splunk-kubernetes-objects",
        "splunk-enterprise",
        "splunk-indexer",
        "splunk-search-head",
        "signalfx-agent",
        "splunk-otel-agent",
        "splunk-otel-k8s-cluster-receiver",
    ],
    all_workload_blobs,
)
splunk_cluster_name_config_present = any(
    "clustername" in blob
    for blob in all_configuration_object_blobs
)
splunk_destination_config_present = any(
    any(
        token in blob
        for token in [
            "splunkobservability",
            "splunkplatform",
            "accesstoken",
            "realm",
            "signalfxendpoint",
            "hec_token",
            "hec.token",
            "services/collector",
            "splunkplatform.endpoint",
            "splunkplatform.token",
        ]
    )
    for blob in all_configuration_object_blobs
)
splunk_required_deployment_configuration_present = bool(
    splunk_cluster_name_config_present and splunk_destination_config_present
)
splunk_context_present = bool(
    splunk_namespace_present
    or splunk_crd_present
    or splunk_operator_workload_present
    or splunk_workload_present
)
splunk_observability_present = bool(splunk_workload_present)
loki_namespace_present = "openshift-logging" in namespace_names or "loki" in namespace_names or "logging-loki" in namespace_names
loki_crd_present = crd_has("lokistacks.loki.grafana.com", "rulerconfigs.loki.grafana.com")
loki_workload_present = any_keyword(
    [
        "lokistack",
        "/loki",
        "loki:",
        "loki@",
        "loki-",
        "-loki",
        "promtail",
        "logcli",
        "loki-distributor",
        "loki-gateway",
        "loki-querier",
        "loki-compactor",
        "loki-ingester",
        "loki-ruler",
        "loki-canary",
    ],
    all_workload_blobs,
)
loki_stack_context_present = bool(
    loki_namespace_present
    or loki_crd_present
)
loki_stack_logging_present = bool(
    len(lokistacks) > 0
    or loki_workload_present
)
datadog_subscription_present = "datadog-operator" in subscription_packages
datadog_namespace_present = "datadog" in namespace_names
datadog_crd_present = crd_has("datadoghq.com", "datadogagents")
datadog_workload_present = any_keyword(
    ["datadog", "datadog-agent", "datadog-cluster-agent", "dogstatsd", "trace-agent"],
    all_workload_blobs,
)
datadog_context_present = bool(
    datadog_subscription_present
    or datadog_namespace_present
    or datadog_crd_present
)
datadog_observability_present = bool(
    len(datadogagents) > 0
    or datadog_workload_present
)
cluster_network_observability_subscription_present = any(
    package in subscription_packages
    for package in {
        "netobserv-operator",
        "network-observability-operator",
    }
)
cluster_network_observability_namespace_present = any(
    name in namespace_names
    for name in {
        "netobserv",
        "openshift-netobserv",
        "network-observability",
    }
)
cluster_network_observability_crd_present = crd_has(
    "flows.netobserv.io",
    "flowcollectors.flows.netobserv.io",
    "consoleplugins.observability.openshift.io",
    "flowmetrics.flows.netobserv.io",
)
cluster_network_observability_flowcollector_count = len(flowcollectors)
cluster_network_observability_flowcollector_present = cluster_network_observability_flowcollector_count > 0
cluster_network_observability_workload_present = any_keyword(
    [
        "netobserv",
        "flowlogs-pipeline",
        "flowlogs-reader",
        "network-observability-operator",
        "console-plugin-netobserv",
    ],
    all_workload_blobs,
)
cluster_network_observability_present = bool(
    cluster_network_observability_subscription_present
    or cluster_network_observability_namespace_present
    or cluster_network_observability_crd_present
    or cluster_network_observability_flowcollector_present
    or cluster_network_observability_workload_present
)
cluster_network_observability_healthy = bool(
    cluster_network_observability_present
    and (
        cluster_network_observability_flowcollector_present
        or cluster_network_observability_workload_present
    )
)
openshift_developer_hub_subscription_present = "rhdh" in subscription_packages
openshift_developer_hub_namespace_present = "rhdh-operator" in namespace_names
openshift_developer_hub_crd_present = crd_has(
    "backstages.rhdh.redhat.com",
    "rhdh.redhat.com",
)
openshift_developer_hub_backstage_count = len(backstages)
openshift_developer_hub_ready_backstage_count = len(
    [
        item
        for item in backstages
        if (
            has_true_condition(item, "Ready", "Available", "Deployed")
            or status_text(item, "phase").lower() in {"ready", "available", "deployed", "running"}
        )
        and not has_problem_condition(item)
        and not has_problem_status(item)
    ]
)
openshift_developer_hub_backstage_present = openshift_developer_hub_backstage_count > 0
openshift_developer_hub_workload_present = any_keyword(
    [
        "developer-hub",
        "red-hat-developer-hub",
        "backstage",
        "rhdh",
    ],
    all_workload_blobs,
)
openshift_developer_hub_context_present = bool(
    openshift_developer_hub_subscription_present
    or openshift_developer_hub_namespace_present
    or openshift_developer_hub_crd_present
)
openshift_developer_hub_present = bool(
    openshift_developer_hub_backstage_present
    or openshift_developer_hub_workload_present
)
openshift_developer_hub_healthy = bool(
    openshift_developer_hub_present
    and (
        openshift_developer_hub_ready_backstage_count > 0
        or openshift_developer_hub_workload_present
    )
)
openshift_dev_spaces_subscription_present = any(
    package in subscription_packages
    for package in {
        "devspaces",
        "devspacesoperator",
        "devworkspace-operator",
    }
)
openshift_dev_spaces_namespace_present = "openshift-devspaces" in namespace_names
openshift_dev_spaces_checluster_present = bool(len(checlusters) > 0)
openshift_dev_spaces_devworkspace_present = bool(len(devworkspaces) > 0)
openshift_dev_spaces_workspace_operator_config_present = bool(len(devworkspaceoperatorconfigs) > 0)
openshift_dev_spaces_routing_present = bool(len(devworkspaceroutings) > 0) or any_keyword(
    [
        "devworkspace-routing",
        "devworkspace-webhook-server",
        "che-gateway",
        "devspaces-dashboard",
        "openvsx",
    ],
    all_workload_blobs,
)
openshift_dev_spaces_context_present = bool(
    openshift_dev_spaces_subscription_present
    or openshift_dev_spaces_namespace_present
)
openshift_dev_spaces_present = bool(
    openshift_dev_spaces_checluster_present
    or openshift_dev_spaces_devworkspace_present
    or openshift_dev_spaces_workspace_operator_config_present
    or openshift_dev_spaces_routing_present
)
openshift_dev_spaces_healthy = bool(
    openshift_dev_spaces_present
    and (
        openshift_dev_spaces_checluster_present
        or openshift_dev_spaces_devworkspace_present
        or (
            openshift_dev_spaces_workspace_operator_config_present
            and openshift_dev_spaces_routing_present
        )
    )
)
appdynamics_subscription_present = "appdynamics-operator" in subscription_packages
appdynamics_namespace_present = "appdynamics" in namespace_names
appdynamics_crd_present = crd_has("clusteragents.appdynamics.com", "infravizs.appdynamics.com", "appdynamics.com")
appdynamics_workload_present = any_keyword(
    [
        "appdynamics",
        "appdynamics-cluster-agent",
        "appdynamics-operator",
        "appdynamics-infraviz",
        "infraviz",
        "machine-agent",
        "netviz",
    ],
    all_workload_blobs,
)
appdynamics_context_present = bool(
    appdynamics_subscription_present
    or appdynamics_namespace_present
    or appdynamics_crd_present
)
appdynamics_observability_present = bool(
    len(clusteragents) > 0
    or len(infravizs) > 0
    or appdynamics_workload_present
)
aap_subscription_present = any(
    package in subscription_packages
    for package in {
        "ansible-automation-platform-operator",
        "ansible-automation-platform",
    }
)
aap_namespace_present = any(
    name in namespace_names
    for name in {
        "ansible-automation-platform",
        "aap",
    }
)
aap_crd_present = crd_has(
    "aap.ansible.com",
    "automationcontroller.ansible.com",
    "automationhub.ansible.com",
    "eda.ansible.com",
)
aap_workload_present = any_keyword(
    [
        "automation-controller",
        "automation-hub",
        "automation-eda",
        "ansible-automation-platform-gateway",
        "eda-api",
        "eda-scheduler",
        "receptor",
    ],
    all_workload_blobs,
)
openshift_aap_context_present = bool(
    aap_subscription_present
    or aap_namespace_present
    or aap_crd_present
)
openshift_aap_present = bool(
    len(ansibleautomationplatforms) > 0
    or len(automationcontrollers) > 0
    or len(automationhubs) > 0
    or len(edas) > 0
    or aap_workload_present
)
keda_subscription_present = any(
    package in subscription_packages
    for package in {
        "custom-metrics-autoscaler-operator",
        "keda",
    }
)
keda_namespace_present = any(
    name in namespace_names
    for name in {
        "openshift-keda",
        "keda",
    }
)
keda_crd_present = crd_has(
    "kedacontrollers.keda.sh",
    "scaledobjects.keda.sh",
    "scaledjobs.keda.sh",
    "triggerauthentications.keda.sh",
    "clustertriggerauthentications.keda.sh",
)
keda_workload_present = any_keyword(
    [
        "keda-operator",
        "keda-operator-metrics-apiserver",
        "keda-admission-webhooks",
        "custom-metrics-autoscaler-operator",
    ],
    all_workload_blobs,
)
openshift_custom_metrics_autoscaler_context_present = bool(
    keda_subscription_present
    or keda_namespace_present
    or keda_crd_present
)
openshift_custom_metrics_autoscaler_present = bool(
    len(kedacontrollers) > 0
    or len(scaledobjects) > 0
    or len(scaledjobs) > 0
    or len(triggerauthentications) > 0
    or len(clustertriggerauthentications) > 0
    or keda_workload_present
)
acs_operator_subscription_present = "container-security-operator" in subscription_packages
acs_namespace_present = "stackrox" in namespace_names or "rhacs-operator" in namespace_names
acs_crd_present = crd_has(
    "platform.stackrox.io",
    "central.stackrox.io",
    "securedcluster.stackrox.io",
    "stackrox.io",
)
acs_workload_present = any_keyword(
    ["stackrox-central", "central-db", "stackrox-scanner", "stackrox-scanner-db", "secured-cluster-services", "admission-control", "stackrox-sensor"],
    all_workload_blobs,
)
advanced_cluster_security_present = bool(
    acs_workload_present
)
advanced_cluster_security_context_present = bool(
    acs_operator_subscription_present
    or acs_namespace_present
    or acs_crd_present
)
gitops_application_names = {
    str((((item.get("metadata") or {}).get("name")) or "")).strip()
    for item in gitops_apps
    if str((((item.get("metadata") or {}).get("name")) or "")).strip()
}
def gitops_sources(app):
    spec = app.get("spec") or {}
    sources = []
    source = spec.get("source") or {}
    if isinstance(source, dict) and source:
        sources.append(source)
    for item in spec.get("sources") or []:
        if isinstance(item, dict) and item:
            sources.append(item)
    return sources

gitops_apps_with_repo_source = [
    item for item in gitops_apps
    if any(str(source.get("repoURL") or "").strip() for source in gitops_sources(item))
]
gitops_apps_healthy_and_synced = [
    item for item in gitops_apps
    if (
        str((((item.get("status") or {}).get("sync") or {}).get("status") or "")).strip().lower() == "synced"
        and str((((item.get("status") or {}).get("health") or {}).get("status") or "")).strip().lower() == "healthy"
    )
]
gitops_apps_with_automated_sync = [
    item for item in gitops_apps
    if isinstance(((item.get("spec") or {}).get("syncPolicy") or {}).get("automated"), dict)
]
onboarding_name_tokens = ("namespace", "project", "tenant", "team")
onboarding_purpose_tokens = ("onboard", "request", "self-provision", "selfprovision", "bootstrap", "factory")
onboarding_gitops_app_names = sorted([
    name for name in gitops_application_names
    if any(token in name.lower() for token in onboarding_name_tokens)
    and any(token in name.lower() for token in onboarding_purpose_tokens)
])
project_spec = project_config.get("spec") or {}
project_request_template_name = str(((project_spec.get("projectRequestTemplate") or {}).get("name")) or "").strip()
project_request_message_configured = bool(str(project_spec.get("projectRequestMessage") or "").strip())
project_request_templates = [
    item for item in templates
    if ((item.get("metadata") or {}).get("namespace") or "") == "openshift-config"
    and (not project_request_template_name or ((item.get("metadata") or {}).get("name") == project_request_template_name))
]
project_request_template_present = bool(project_request_template_name and project_request_templates)
project_template_objects = []
for template in project_request_templates:
    project_template_objects.extend((template.get("objects") or []) + ((template.get("template") or {}).get("objects") or []))
project_template_kind_counts = {}
for obj in project_template_objects:
    kind = str((obj or {}).get("kind") or "").strip()
    if kind:
        project_template_kind_counts[kind] = project_template_kind_counts.get(kind, 0) + 1
project_template_guardrail_count = sum(project_template_kind_counts.get(kind, 0) for kind in ["ResourceQuota", "LimitRange", "NetworkPolicy", "RoleBinding", "Role"])
self_provisioners = next(
    (
        item for item in clusterrolebindings
        if ((item.get("metadata") or {}).get("name") == "self-provisioners")
        or (((item.get("roleRef") or {}).get("name")) == "self-provisioner")
    ),
    {},
)
self_provisioner_subjects = self_provisioners.get("subjects") or []
self_provisioner_public_subject_present = any(
    subject.get("kind") == "Group" and subject.get("name") in {"system:authenticated", "system:authenticated:oauth"}
    for subject in self_provisioner_subjects
)
self_provisioner_autoupdate_false = (
    str(((self_provisioners.get("metadata") or {}).get("annotations") or {}).get("rbac.authorization.kubernetes.io/autoupdate") or "").lower()
    == "false"
)
self_provisioning_restricted = bool(self_provisioners) and not self_provisioner_public_subject_present
namespace_self_provisioning_governed = bool(
    self_provisioning_restricted and self_provisioner_autoupdate_false
)
team_rbac_bindings = []
for binding in rolebindings:
    namespace = str(((binding.get("metadata") or {}).get("namespace")) or "").strip()
    role_name = str(((binding.get("roleRef") or {}).get("name")) or "").strip()
    if namespace not in user_namespace_names or role_name not in {"admin", "edit", "view"}:
        continue
    for subject in binding.get("subjects") or []:
        group_name = str(subject.get("name") or "").strip()
        if subject.get("kind") == "Group" and group_name and not group_name.startswith("system:"):
            team_rbac_bindings.append((namespace, group_name, role_name))
team_rbac_namespace_count = len({item[0] for item in team_rbac_bindings})
team_rbac_group_count = len({item[1] for item in team_rbac_bindings})
known_team_group_count = len({item[1] for item in team_rbac_bindings if item[1] in group_names})
namespaces_with_networkpolicy = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in networkpolicies
    if str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
}
namespaces_with_default_deny_networkpolicy = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in networkpolicies
    if (
        str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
        and has_match_all_pod_selector(item)
        and ("Ingress" in policy_types(item) or policy_rule_declared(item, "ingress"))
    )
}
namespaces_with_egress_networkpolicy = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in networkpolicies
    if (
        str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
        and "Egress" in (((item.get("spec") or {}).get("policyTypes")) or [])
    )
}
namespaces_with_baseline_egress_networkpolicy = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in networkpolicies
    if (
        str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
        and has_match_all_pod_selector(item)
        and ("Egress" in policy_types(item) or policy_rule_declared(item, "egress"))
    )
}
namespaces_with_egressfirewall = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in egressfirewalls
    if str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
}
namespaces_with_egress_controls = namespaces_with_baseline_egress_networkpolicy | namespaces_with_egressfirewall
namespaces_with_resourcequota = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in resourcequotas
    if str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
}
namespaces_with_limitrange = {
    str(((item.get("metadata") or {}).get("namespace")) or "").strip()
    for item in limitranges
    if str(((item.get("metadata") or {}).get("namespace")) or "").strip() in user_namespace_names
}
namespaces_with_all_baseline_guardrails = (
    namespaces_with_default_deny_networkpolicy & namespaces_with_resourcequota & namespaces_with_limitrange
)
namespaces_with_all_namespace_governance_guardrails = (
    namespaces_with_all_baseline_guardrails & namespaces_with_egress_controls
)
namespace_onboarding_controls_present = bool(
    project_request_template_present
    or onboarding_gitops_app_names
    or (namespace_self_provisioning_governed and project_request_message_configured)
)
drpolicy_cluster_membership = {
    str(((item.get("metadata") or {}).get("name")) or "").strip(): sorted({
        str(cluster_name).strip()
        for cluster_name in (((item.get("spec") or {}).get("drClusters")) or [])
        if str(cluster_name).strip()
    })
    for item in drpolicies
    if str(((item.get("metadata") or {}).get("name")) or "").strip()
}
valid_drpolicy_names = sorted([
    name for name, clusters in drpolicy_cluster_membership.items()
    if len(clusters) >= 2
])
protected_drpolicy_names = sorted({
    str((((item.get("spec") or {}).get("drPolicyRef") or {}).get("name")) or "").strip()
    for item in drplacementcontrols
    if str((((item.get("spec") or {}).get("drPolicyRef") or {}).get("name")) or "").strip()
})
drclusters_with_problem_status = [
    item for item in drclusters
    if has_problem_condition(item) or has_problem_status(item)
]
drpcs_with_problem_status = [
    item for item in drplacementcontrols
    if has_problem_condition(item) or has_problem_status(item)
]
vrgs_with_problem_status = [
    item for item in volumereplicationgroups
    if has_problem_condition(item) or has_problem_status(item)
]
secondary_site_dr_topology_ready = len(valid_drpolicy_names) > 0 and len(drclusters) >= 2
secondary_site_dr_replication_ready = (
    len(volumereplicationclasses) > 0
    or len(volumereplications) > 0
    or len(volumereplicationgroups) > 0
    or len(volumegroupreplications) > 0
)
secondary_site_dr_protected_workloads_ready = (
    len(drplacementcontrols) > 0
    or len(volumereplicationgroups) > 0
    or len(volumegroupreplications) > 0
)
secondary_site_dr_present = bool(
    len(drpolicies) > 0
    or len(drclusters) > 0
    or len(drplacementcontrols) > 0
    or len(volumereplicationgroups) > 0
    or len(volumereplications) > 0
    or len(volumereplicationclasses) > 0
    or len(volumegroupreplications) > 0
)
secondary_site_dr_healthy = bool(
    secondary_site_dr_topology_ready
    and secondary_site_dr_replication_ready
    and secondary_site_dr_protected_workloads_ready
    and len(drclusters_with_problem_status) == 0
    and len(drpcs_with_problem_status) == 0
    and len(vrgs_with_problem_status) == 0
)
acm_managed = bool(klusterlets or managedclusteraddons or acm_agent_namespaces)
acm_registration_present = acm_managed
acm_registration_healthy = bool(klusterlets or acm_agent_namespaces)
external_alert_delivery_present = bool(
    obs.get("external_alert_delivery_configured")
    or obs.get("alert_routing_to_external_receiver_configured")
    or int(obs.get("external_alert_receiver_count") or 0) > 0
    or int(obs.get("alert_delivery_source_count") or 0) > 0
)
external_alert_delivery_healthy = bool(
    int(obs.get("external_alert_receiver_count") or 0) > 0
    and bool(obs.get("alert_routing_to_external_receiver_configured"))
)
log_collection_present = bool(
    obs.get("application_logs_collected")
    or obs.get("infrastructure_logs_collected")
    or obs.get("audit_logs_collected")
    or len(clusterlogforwarders) > 0
    or bool(obs.get("vendor_managed_log_forwarding_present"))
)
cluster_log_forwarding_healthy = bool(
    (
        obs.get("application_logs_collected")
        and obs.get("application_logs_exported_external")
        and obs.get("infrastructure_logs_collected")
        and obs.get("infrastructure_logs_exported_external")
        and obs.get("audit_logs_collected")
        and obs.get("audit_logs_exported_external")
    )
    or bool(obs.get("vendor_managed_log_forwarding_present"))
)
runner_keywords = ["gitlab-runner", "github-runner", "actions-runner", "azure-pipelines-agent", "azp-agent", "jenkins-agent", "jenkins-inbound-agent", "tekton-task"]
cicd_runner_present = any_keyword(runner_keywords, all_workload_blobs)
odf_operator_subscription_present = (
    "odf-operator" in subscription_packages
    or "ocs-operator" in subscription_packages
)
odf_namespace_present = "openshift-storage" in namespace_names
openshift_data_foundation_present = bool(
    len(storageclusters) > 0
    or len(cephclusters) > 0
    or len(noobaas) > 0
)
odf_storageclass_names = []
for sc in storageclasses:
    if not isinstance(sc, dict):
        continue
    meta = sc.get("metadata") or {}
    sc_name = str(meta.get("name") or "").strip()
    provisioner = str(sc.get("provisioner") or "").strip()
    blob = f"{sc_name} {provisioner}".lower()
    if (
        "ocs-storagecluster" in blob
        or "openshift-storage.noobaa.io" in blob
        or "cephfs.csi.ceph.com" in blob
        or "rbd.csi.ceph.com" in blob
        or "ceph.rook.io/bucket" in blob
    ):
        odf_storageclass_names.append(sc_name or provisioner)
odf_storageclass_count = len(set(odf_storageclass_names))
openshift_data_foundation_present = bool(
    openshift_data_foundation_present
    or odf_storageclass_count > 0
)
openshift_data_foundation_healthy = bool(
    (
        len(storageclusters) > 0
        and (len(cephclusters) > 0 or len(noobaas) > 0)
    )
    or odf_storageclass_count > 0
)
cp4ba_operator_subscription_present = "ibm-cp4a-operator" in subscription_packages
cp4ba_namespace_present = bool(
    any(
        ("cp4ba" in name or "ibm-baw" in name or "ibm-ba" in name)
        for name in namespace_names
    )
)
cp4ba_crd_present = crd_has("icp4aclusters.icp4a.ibm.com")
ready_icp4aclusters = [
    item for item in icp4aclusters
    if (
        has_true_condition(item, "Ready", "Available", "Successful", "Completed")
        or status_text(item, "phase").lower() in {"ready", "available", "successful", "completed", "running", "deployed"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
ibm_cloud_pak_business_automation_present = bool(
    len(icp4aclusters) > 0
    or cp4ba_operator_subscription_present
    or cp4ba_namespace_present
    or cp4ba_crd_present
)
ibm_cloud_pak_business_automation_healthy = bool(len(ready_icp4aclusters) > 0)
virtualization_operator_subscription_present = "kubevirt-hyperconverged" in subscription_packages
virtualization_namespace_present = "openshift-cnv" in namespace_names
virtualization_platform_present = bool(len(kubevirts) > 0 or len(hyperconvergeds) > 0)
virtualization_workload_present = bool(
    len(virtualmachines) > 0
    or len(virtualmachineinstances) > 0
    or len(datavolumes) > 0
)
virtualization_supporting_stack_present = bool(len(ssps) > 0 or len(cdis) > 0)
ready_kubevirts = [
    item for item in kubevirts
    if (
        has_true_condition(item, "Available", "Ready", "Created")
        or status_text(item, "phase").lower() in {"deployed", "available", "ready"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
ready_hyperconvergeds = [
    item for item in hyperconvergeds
    if (
        has_true_condition(item, "Available", "Ready")
        or status_text(item, "phase").lower() in {"deployed", "available", "ready"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
openshift_virtualization_present = bool(
    virtualization_platform_present
    or virtualization_workload_present
    or virtualization_supporting_stack_present
)
openshift_virtualization_context_present = bool(
    openshift_virtualization_present
    or virtualization_operator_subscription_present
    or virtualization_namespace_present
)
openshift_virtualization_healthy = bool(
    len(ready_kubevirts) > 0
    or len(ready_hyperconvergeds) > 0
)
openshift_ai_subscription_present = "rhods-operator" in subscription_packages
openshift_ai_namespace_present = "redhat-ods-operator" in namespace_names
openshift_ai_present = bool(
    len(datascienceclusters) > 0
    or len(dscinitializations) > 0
    or len(notebooks) > 0
    or len(servingruntimes) > 0
    or len(inferenceservices) > 0
    or len(modelmeshservings) > 0
    or len(acceleratorprofiles) > 0
)
openshift_ai_context_present = bool(
    openshift_ai_present
    or openshift_ai_subscription_present
    or openshift_ai_namespace_present
)
ready_datascienceclusters = [
    item for item in datascienceclusters
    if (
        has_true_condition(item, "Ready", "Available", "Completed")
        or status_text(item, "phase").lower() in {"ready", "installed", "available", "completed"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
ready_dscinitializations = [
    item for item in dscinitializations
    if (
        has_true_condition(item, "Ready", "Available", "Completed")
        or status_text(item, "phase").lower() in {"ready", "installed", "available", "completed"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
openshift_ai_healthy = bool(
    len(ready_datascienceclusters) > 0
    or len(ready_dscinitializations) > 0
)
service_mesh_subscription_present = bool(
    "servicemeshoperator" in subscription_packages or "kiali-ossm" in subscription_packages
)
service_mesh_crd_present = crd_has(
    "servicemeshcontrolplanes.maistra.io",
    "servicemeshmemberrolls.maistra.io",
    "servicemeshmembers.maistra.io",
)
service_mesh_control_plane_present = len(servicemeshcontrolplanes) > 0
service_mesh_membership_present = bool(len(servicemeshmemberrolls) > 0 or len(servicemeshmembers) > 0)
ready_service_mesh_control_planes = [
    item for item in servicemeshcontrolplanes
    if (
        has_true_condition(item, "Ready", "Installed", "Reconciled")
        or status_text(item, "phase").lower() in {"ready", "installed", "reconciled"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
service_mesh_present = bool(
    service_mesh_control_plane_present
    or service_mesh_membership_present
)
service_mesh_context_present = bool(
    service_mesh_present
    or service_mesh_subscription_present
    or service_mesh_crd_present
)
service_mesh_healthy = bool(len(ready_service_mesh_control_planes) > 0)
serverless_subscription_present = "serverless-operator" in subscription_packages
serverless_namespace_present = bool(
    "openshift-serverless" in namespace_names
    or "knative-serving" in namespace_names
    or "knative-eventing" in namespace_names
)
serverless_crd_present = crd_has(
    "knativeservings.operator.knative.dev",
    "knativeeventings.operator.knative.dev",
    "services.serving.knative.dev",
)
serverless_control_plane_present = bool(len(knativeservings) > 0 or len(knativeeventings) > 0)
serverless_workload_present = len(knativeservices) > 0
ready_knativeservings = [
    item for item in knativeservings
    if (
        has_true_condition(item, "Ready", "InstallSucceeded")
        or status_text(item, "phase").lower() in {"ready", "installed", "running"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
ready_knativeeventings = [
    item for item in knativeeventings
    if (
        has_true_condition(item, "Ready", "InstallSucceeded")
        or status_text(item, "phase").lower() in {"ready", "installed", "running"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
serverless_present = bool(
    serverless_control_plane_present
    or serverless_workload_present
)
serverless_context_present = bool(
    serverless_present
    or serverless_subscription_present
    or serverless_namespace_present
    or serverless_crd_present
)
serverless_healthy = bool(
    (
        len(knativeservings) == 0
        or len(ready_knativeservings) > 0
    )
    and (
        len(knativeeventings) == 0
        or len(ready_knativeeventings) > 0
    )
    and (
        len(ready_knativeservings) > 0
        or len(ready_knativeeventings) > 0
    )
)
windows_operator_subscription_present = "windows-machine-config-operator" in subscription_packages
windows_operator_namespace_present = "openshift-windows-machine-config-operator" in namespace_names
windows_nodes_present = len(windows_nodes) > 0
windows_workload_present = len(windows_workload_objects) > 0
windows_workloads_present = bool(
    windows_nodes_present
    or windows_workload_present
)
windows_workloads_context_present = bool(
    windows_workloads_present
    or windows_operator_namespace_present
    or windows_operator_subscription_present
)
windows_workloads_healthy = bool(windows_nodes_present or windows_workload_present)
gpu_operator_subscription_present = "nvidia-gpu-operator" in subscription_packages
gpu_operator_workload_present = any_keyword(["nvidia", "gpu-operator", "dcgm-exporter"], all_workload_blobs)
gpu_nodes = [
    node for node in nodes
    if "nvidia.com/gpu" in json.dumps((node.get("status") or {}).get("allocatable") or {}).lower()
]
gpu_workload_objects = []
for obj in all_workloads:
    spec = pod_spec_from(obj)
    containers = (spec.get("containers") or []) + (spec.get("initContainers") or [])
    for container in containers:
        resources = container.get("resources") or {}
        requests = resources.get("requests") or {}
        limits = resources.get("limits") or {}
        resource_blob = json.dumps({"requests": requests, "limits": limits}).lower()
        if "nvidia.com/gpu" in resource_blob:
            gpu_workload_objects.append(obj)
            break
gpu_capacity_present = len(gpu_nodes) > 0
gpu_workload_present = len(gpu_workload_objects) > 0
gpu_workloads_present = bool(
    gpu_capacity_present
    or gpu_workload_present
)
gpu_workloads_context_present = bool(
    gpu_workloads_present
    or len(nvidiaclusterpolicies) > 0
    or gpu_operator_subscription_present
    or gpu_operator_workload_present
)
gpu_workloads_healthy = bool(gpu_capacity_present or gpu_workload_present)
sandboxed_operator_subscription_present = "sandboxed-containers-operator" in subscription_packages
sandboxed_operator_namespace_present = "openshift-sandboxed-containers-operator" in namespace_names
kata_config_present = len(kataconfigs) > 0
ready_kataconfigs = [
    item for item in kataconfigs
    if (
        has_true_condition(item, "Available", "Ready", "Completed", "Installed")
        or status_text(item, "phase", "state", "installationStatus").lower() in {
            "completed",
            "complete",
            "installed",
            "ready",
            "available",
        }
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
kata_workload_objects = []
for obj in all_workloads:
    spec = pod_spec_from(obj)
    runtime_class_name = str(spec.get("runtimeClassName") or "").strip().lower()
    if runtime_class_name and ("kata" in runtime_class_name or "sandbox" in runtime_class_name):
        kata_workload_objects.append(obj)
sandboxed_containers_present = bool(
    kata_config_present
    or len(kata_workload_objects) > 0
)
sandboxed_containers_context_present = bool(
    sandboxed_containers_present
    or sandboxed_operator_namespace_present
    or sandboxed_operator_subscription_present
)
sandboxed_containers_healthy = bool(len(ready_kataconfigs) > 0 or len(kata_workload_objects) > 0)
node_tuning_namespace_present = "openshift-cluster-node-tuning-operator" in namespace_names
node_tuning_crd_present = crd_has("tuneds.tuned.openshift.io", "profiles.tuned.openshift.io")
node_tuning_default_names = {
    "default",
    "openshift",
    "openshift-node",
    "openshift-control-plane",
    "openshift-realtime",
    "openshift-node-es",
    "openshift-control-plane-es",
}
custom_tuned_config_resources = [
    item for item in tuneds
    if str(((item.get("metadata") or {}).get("name")) or "").strip().lower() not in node_tuning_default_names
]
ready_performanceprofiles = [
    item for item in performanceprofiles
    if not has_problem_condition(item) and not has_problem_status(item)
]
node_tuning_present = bool(
    len(custom_tuned_config_resources) > 0
    or len(performanceprofiles) > 0
)
node_tuning_context_present = bool(
    node_tuning_present
    or len(tuneds) > 0
    or len(tunedprofiles) > 0
    or node_tuning_namespace_present
    or node_tuning_crd_present
)
tuned_config_resources = [
    item for item in custom_tuned_config_resources
    if (
        len((((item.get("spec") or {}).get("recommend")) or [])) > 0
        or len((((item.get("spec") or {}).get("profile")) or [])) > 0
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
node_tuning_healthy = bool(len(tuned_config_resources) > 0 or len(ready_performanceprofiles) > 0)
nmstate_namespace_present = "openshift-nmstate" in namespace_names
nmstate_operator_subscription_present = "kubernetes-nmstate-operator" in subscription_packages
nmstate_present = bool(
    len(nmstates) > 0
    or len(nodenetworkconfigurationpolicies) > 0
    or len(nodenetworkstates) > 0
)
nmstate_context_present = bool(
    nmstate_present
    or nmstate_namespace_present
    or nmstate_operator_subscription_present
)
ready_nodenetworkconfigurationpolicies = [
    item for item in nodenetworkconfigurationpolicies
    if (
        has_true_condition(item, "Available", "SuccessfullyConfigured")
        or status_text(item, "phase").lower() in {"available", "configured", "ready", "success"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
configured_nmstates = [
    item for item in nmstates
    if not has_problem_condition(item) and not has_problem_status(item)
]
nmstate_healthy = bool(
    len(ready_nodenetworkconfigurationpolicies) > 0
    or len(configured_nmstates) > 0
)
cost_management_subscription_present = "costmanagement-metrics-operator" in subscription_packages
cost_management_namespace_present = "costmanagement-metrics-operator" in namespace_names
cost_management_crd_present = crd_has("costmanagementmetricsconfigs.costmanagement-metrics-cfg.openshift.io")
cost_management_config_present = len(costmanagementmetricsconfigs) > 0
ready_cost_management_configs = [
    item for item in costmanagementmetricsconfigs
    if not has_problem_condition(item) and not has_problem_status(item)
]
cost_management_present = bool(
    cost_management_config_present
)
cost_management_context_present = bool(
    cost_management_present
    or cost_management_subscription_present
    or cost_management_namespace_present
    or cost_management_crd_present
)
cost_management_healthy = bool(len(ready_cost_management_configs) > 0)
descheduler_namespace_present = "openshift-kube-descheduler-operator" in namespace_names
descheduler_subscription_present = "cluster-kube-descheduler-operator" in subscription_packages
descheduler_present = bool(
    len(deschedulers) > 0
)
descheduler_context_present = bool(
    descheduler_present
    or descheduler_namespace_present
    or descheduler_subscription_present
)
configured_deschedulers = [
    item for item in deschedulers
    if (
        len((item.get("spec") or {})) > 0
        or has_true_condition(item, "Available", "Ready", "Deployed")
        or status_text(item, "phase").lower() in {"ready", "available", "deployed"}
    ) and not has_problem_condition(item) and not has_problem_status(item)
]
descheduler_healthy = bool(len(configured_deschedulers) > 0)

checks = []
findings = []
capability_profile = data.get("capability_profile") or {}

def level_rank(value):
    return {"required": 3, "recommended": 2, "informational": 1}.get(value, 2)

def normalize_level(value):
    if value in {"required", "recommended", "informational"}:
        return value
    return "recommended"

def choose_level(*values):
    normalized = [normalize_level(v) for v in values if v]
    return max(normalized, key=level_rank) if normalized else "recommended"

def cap(key):
    value = capability_profile.get(key) or {}
    return value if isinstance(value, dict) else {}

def cap_enabled(key):
    return bool(cap(key).get("enabled", True))

def cap_required(key):
    return cap_enabled(key) and bool(cap(key).get("required", False))

def cap_expected_state(key, fallback="present"):
    value = str(cap(key).get("expected_state") or fallback).strip().lower()
    return value if value in {"present", "absent", "configured", "healthy", "not_applicable"} else fallback

def cap_owner(key, fallback="platform"):
    return str(cap(key).get("owner") or fallback).strip() or fallback

def cap_criticality(key, fallback="medium"):
    value = str(cap(key).get("criticality") or fallback).strip().lower()
    return value if value in {"critical", "high", "medium", "low", "info"} else fallback

def cap_level(key, fallback):
    if cap_expected_state(key) == "not_applicable":
        return "informational"
    if cap_required(key):
        return "required"
    return normalize_level(fallback)

def cap_failure_severity(key, fallback="warning"):
    if not cap_required(key):
        return "info"
    criticality = cap_criticality(key)
    return "critical" if criticality == "critical" else fallback

def cap_standards(key):
    value = cap(key).get("standards") or []
    return [str(item).strip() for item in value if str(item).strip()]

def cap_status_for_presence(key, present, healthy=True):
    expected = cap_expected_state(key)
    if expected == "not_applicable":
        return "INFO"
    if expected == "absent":
        return "WARN" if present else "OK"
    if expected == "configured":
        return "OK" if present and healthy else ("WARN" if cap_required(key) else "INFO")
    if expected == "healthy":
        return "OK" if present and healthy else ("WARN" if cap_required(key) else "INFO")
    return "OK" if present and healthy else ("WARN" if cap_required(key) else "INFO")

cluster_shape = "single-node" if is_sno else ("hosted-control-plane" if is_hosted_control_plane else "multi-node")
provider_baseline = cluster_classification_label if cloud_managed else ("public-cloud" if public_cloud else "self-managed")
control_plane_mode = str((((data.get("cluster_profile") or {}).get("control_plane_model")) or ("hosted" if is_hosted_control_plane else ("single-node" if is_sno else "standalone")))).strip().lower()
hostedcluster_autoscaling_present = any(
    str((((item.get("spec") or {}).get("autoscaling") or {}).get("scaling") or "")).strip() not in {"", "None", "none"}
    for item in hostedclusters
    if isinstance(item, dict)
)
nodepool_autoscaling_present = any(
    isinstance(((item.get("spec") or {}).get("autoScaling")), dict)
    and len(((item.get("spec") or {}).get("autoScaling") or {})) > 0
    for item in nodepools
    if isinstance(item, dict)
)
hcp_management_autoscaling_evidence = len(hostedclusters) > 0 or len(nodepools) > 0
hcp_autoscaling_present = hostedcluster_autoscaling_present or nodepool_autoscaling_present or (cloud_managed and len(clusterautoscalers) > 0)
day2_baseline_profile = {
    "provider": provider_baseline,
    "cluster_shape": cluster_shape,
    "control_plane_mode": control_plane_mode,
}

base_required_level = "recommended" if is_sno else "required"
telemetry_level = "required" if cloud_managed else "recommended"
external_secrets_level = cap_level("external_secrets_operator", "required" if platform == "Azure" else ("recommended" if cloud_managed else "informational"))
compliance_level = cap_level("compliance_requirements_validation", "informational" if is_sno else "recommended")
insights_level = "recommended" if cloud_managed else "informational"
namespace_guardrails_level = cap_level("multi_tenant_namespace_governance", "informational" if is_sno else "recommended")
pipelines_level = cap_level("openshift_pipeline_workflows", "informational" if is_sno else "recommended")
cert_manager_level = cap_level("cert_manager_operator", "informational" if is_sno else "recommended")
acs_level = cap_level("advanced_cluster_security", "recommended" if cloud_managed and not is_sno else "informational")
machine_remediation_level = cap_level("machine_health_check_remediation", "recommended" if (len(machinesets) > 0 and not is_sno and not is_hosted_control_plane) else "informational")
autoscaler_level = cap_level("cluster_autoscaler_configuration", "recommended" if ((public_cloud or install_model == "ipi") and len(machinesets) > 0 and not is_sno and not is_hosted_control_plane) else "informational")

def add_check(capability, status, detail, source, level="recommended", scored=True, capability_key=None):
    normalized_level = normalize_level(level)
    capability_key_map = {
        "GitOps controller and application inventory": "declarative_gitops_operations",
        "Cluster logging app footprint": "cluster_log_forwarding",
        "External Secrets Operator app footprint": "external_secrets_operator",
        "Workload backup and restore provider footprint": "application_backup_and_restore_readiness",
        "Compliance validation footprint": "compliance_requirements_validation",
        "OpenShift pipeline workflow footprint": "openshift_pipeline_workflows",
        "OpenShift Developer Hub footprint": "openshift_developer_hub",
        "OpenShift Dev Spaces footprint": "openshift_dev_spaces",
        "cert-manager operator footprint": "cert_manager_operator",
        "Advanced Cluster Security operator footprint": "advanced_cluster_security",
        "Dynatrace observability footprint": "dynatrace_observability",
        "Qualys scanning agent footprint": "qualys_scanning_agents",
        "Prisma Cloud Defender footprint": "prisma_twistlock_defenders",
        "Aqua security platform footprint": "aqua_security_platform",
        "Splunk observability footprint": "splunk_observability",
        "LokiStack logging footprint": "loki_stack_logging",
        "Datadog observability footprint": "datadog_observability",
        "AppDynamics observability footprint": "appdynamics_observability",
        "OpenShift AAP footprint": "openshift_aap",
        "OpenShift KEDA custom metrics footprint": "openshift_custom_metrics_autoscaler",
        "OpenShift Data Foundation footprint": "openshift_data_foundation",
        "IBM Cloud Pak for Business Automation footprint": "ibm_cloud_pak_business_automation",
        "OpenShift Virtualization footprint": "openshift_virtualization",
        "OpenShift AI footprint": "openshift_ai",
        "Service mesh control plane footprint": "service_mesh_control_plane",
        "OpenShift Serverless footprint": "openshift_serverless",
        "Windows container workload footprint": "windows_container_workloads",
        "GPU accelerated workload footprint": "gpu_accelerated_workloads",
        "Sandboxed container workload footprint": "sandboxed_container_workloads",
        "Node tuning operator configuration": "node_tuning_operator",
        "Kubernetes NMState networking footprint": "kubernetes_nmstate_networking",
        "Descheduler operator footprint": "descheduler_operator",
        "Team project onboarding controls": "multi_tenant_namespace_governance",
        "Cost management operator configuration": "cost_management_operator",
        "External secrets integration": "external_secrets_operator",
        "CyberArk Conjur secrets management footprint": "cyberark_conjur_secrets_management",
        "User workload monitoring configuration path": "user_workload_metrics_monitoring",
        "User workload metrics scrape inventory": "user_workload_metrics_monitoring",
        "User workload metrics coverage path": "user_workload_metrics_monitoring",
        "User workload monitoring enabled": "user_workload_metrics_monitoring",
        "User workload alerting and SLOs": "user_workload_alerting_and_slos",
        "Grafana dashboard inventory": "grafana_metrics_dashboards",
        "Prometheus persistent storage": "persistent_monitoring_storage",
        "Alertmanager persistent storage": "persistent_monitoring_storage",
        "Thanos Ruler persistent storage": "persistent_monitoring_storage",
        "Persistent cluster monitoring storage": "persistent_monitoring_storage",
        "Cluster log forwarding collection path": "cluster_log_forwarding",
        "Cluster log forwarding external destinations": "cluster_log_forwarding",
        "Cluster log forwarding log coverage": "cluster_log_forwarding",
        "External log forwarding": "cluster_log_forwarding",
        "Cluster metrics remote write configuration": "cluster_metrics_remote_write",
        "External cluster metrics destination": "cluster_metrics_remote_write",
        "User workload metrics export context": "cluster_metrics_remote_write",
        "Cluster metrics remote write": "cluster_metrics_remote_write",
        "External alert receiver inventory": "external_alert_delivery",
        "Alert routing to external receiver": "external_alert_delivery",
        "External alert delivery verification": "external_alert_delivery",
        "External alert delivery": "external_alert_delivery",
        "Cluster network observability operator subscription": "cluster_network_observability",
        "Cluster network observability namespace": "cluster_network_observability",
        "Cluster network observability CRD inventory": "cluster_network_observability",
        "Cluster network observability FlowCollector or workload footprint": "cluster_network_observability",
        "Cluster network observability footprint": "cluster_network_observability",
        "API server audit logging and retention": "api_server_audit_and_log_retention",
        "Application backup and restore baseline": "application_backup_and_restore_readiness",
        "Control plane backup and recovery baseline": "control_plane_backup_and_recovery_readiness",
        "Secondary-site disaster recovery": "secondary_site_disaster_recovery",
        "ACM multicluster disaster recovery": "acm_multicluster_disaster_recovery",
        "Compliance requirements validation": "compliance_requirements_validation",
        "Central identity provider integration": "oauth_external_identity_provider",
        "Worker machine remediation": "machine_health_check_remediation",
        "Cluster autoscaler": "cluster_autoscaler_configuration",
        "Kubelet configuration governance": "kubelet_configuration_governance",
        "Registry governance baseline": "image_registry_policy_governance",
        "Trusted image admission policy": "image_signature_and_admission_policy",
        "Cluster image mirror configuration": "cluster_image_mirror_configuration",
        "Disconnected installation image sources": "disconnected_cluster_image_sources",
        "OVN-Kubernetes network context": "ovn_ipsec_encryption",
        "OVN IPsec configuration presence": "ovn_ipsec_encryption",
        "OVN IPsec pod-to-pod encryption configured": "ovn_ipsec_encryption",
        "OVN IPsec pod-to-pod mode": "ovn_ipsec_encryption",
        "APIServer etcd encryption configuration": "etcd_encryption",
        "etcd encryption rollout evidence": "etcd_encryption",
        "etcd encryption rollout completion": "etcd_encryption",
        "etcd encryption enabled": "etcd_encryption",
        "Cluster proxy configuration": "cluster_proxy_configuration",
        "Custom trust bundle configuration": "custom_ca_trust_bundle",
        "Ingress controller topology and sharding": "ingress_controller_topology_and_sharding",
        "Application external private registry usage": "workloads_using_external_private_registries",
        "Cluster-hosted CI/CD runners": "cluster_hosted_cicd_runners",
        "RHACS vulnerability scanning": "workload_vulnerability_scanning",
        "Qualys workload scanning": "workload_vulnerability_scanning",
        "Prisma Cloud Compute or Twistlock vulnerability scanning": "workload_vulnerability_scanning",
        "Aqua workload scanning": "workload_vulnerability_scanning",
        "Trivy Operator vulnerability scanning": "workload_vulnerability_scanning",
        "Workload vulnerability scanner agents": "workload_vulnerability_scanning",
        "Namespace network policy baseline": "namespace_network_policy_baseline",
        "Namespace egress controls": "namespace_egress_controls",
        "ACM managed-cluster context": "advanced_cluster_management",
        "ACM Klusterlet registration configuration": "advanced_cluster_management",
        "ACM managed-cluster add-on or agent footprint": "advanced_cluster_management",
        "ACM managed-cluster registration": "advanced_cluster_management",
    }
    capability_key = capability_key if capability_key is not None else capability_key_map.get(capability, "")
    if capability_key and not cap_enabled(capability_key):
        return
    checks.append({
        "capability_key": capability_key,
        "capability": capability,
        "status": status,
        "detail": detail,
        "source": source,
        "level": normalized_level,
        "scored": bool(scored and normalized_level != "informational"),
    })

def docs_for_capability(key):
    return str(cap(key).get("docs") or "").strip()

def finding_capability_key(issue, source):
    issue_map = {
        "prod-day2-gitops-missing": "declarative_gitops_operations",
        "prod-day2-gitops-applications-missing": "declarative_gitops_operations",
        "prod-day2-gitops-applications-unhealthy": "declarative_gitops_operations",
        "prod-day2-gitops-repo-source-missing": "declarative_gitops_operations",
        "prod-day2-gitops-automated-sync-missing": "declarative_gitops_operations",
        "prod-day2-external-secrets-missing": "external_secrets_operator",
        "prod-day2-cyberark-conjur-secrets-management-missing": "cyberark_conjur_secrets_management",
        "prod-day2-user-workload-monitoring-disabled": "user_workload_metrics_monitoring",
        "prod-day2-user-workload-alerting-slos-missing": "user_workload_alerting_and_slos",
        "prod-day2-grafana-dashboards-missing": "grafana_metrics_dashboards",
        "prod-day2-monitoring-persistence-missing": "persistent_monitoring_storage",
        "prod-day2-external-log-forwarding-missing": "cluster_log_forwarding",
        "prod-day2-cluster-metrics-remote-write-missing": "cluster_metrics_remote_write",
        "prod-day2-api-server-audit-and-log-retention-missing": "api_server_audit_and_log_retention",
        "prod-day2-api-server-audit-retention-path-missing": "api_server_audit_and_log_retention",
        "prod-day2-application-backup-baseline-incomplete": "application_backup_and_restore_readiness",
        "prod-day2-control-plane-backup-evidence-missing": "control_plane_backup_and_recovery_readiness",
        "prod-day2-control-plane-runtime-unhealthy-for-recovery": "control_plane_backup_and_recovery_readiness",
        "prod-day2-compliance-requirements-missing": "compliance_requirements_validation",
        "prod-day2-identity-provider-missing": "oauth_external_identity_provider",
        "prod-day2-machinehealthcheck-missing": "machine_health_check_remediation",
        "prod-day2-machinehealthcheck-coverage-incomplete": "machine_health_check_remediation",
        "prod-day2-cluster-autoscaler-missing": "cluster_autoscaler_configuration",
        "prod-day2-kubelet-configuration-governance-missing": "kubelet_configuration_governance",
        "prod-day2-cluster-image-mirror-configuration-missing": "cluster_image_mirror_configuration",
        "prod-day2-cluster-image-mirror-configuration-legacy-icsp-only": "cluster_image_mirror_configuration",
        "prod-day2-cluster-image-mirror-configuration-targets-missing": "cluster_image_mirror_configuration",
        "prod-day2-proxy-no-proxy-incomplete": "cluster_proxy_configuration",
        "prod-day2-ingress-controller-topology-and-sharding-missing": "ingress_controller_topology_and_sharding",
        "prod-day2-ingress-controller-topology-and-sharding-unhealthy": "ingress_controller_topology_and_sharding",
        "prod-day2-disconnected-installation-evidence-missing": "disconnected_cluster_image_sources",
        "prod-day2-disconnected-release-image-not-mirrored": "disconnected_cluster_image_sources",
        "prod-day2-disconnected-operator-catalog-missing": "disconnected_cluster_image_sources",
        "prod-day2-disconnected-legacy-icsp-only": "disconnected_cluster_image_sources",
        "prod-day2-ipsec-not-enabled": "ovn_ipsec_encryption",
        "prod-day2-etcd-encryption-not-enabled": "etcd_encryption",
        "prod-day2-etcd-encryption-rollout-incomplete": "etcd_encryption",
        "prod-day2-proxy-configuration-missing": "cluster_proxy_configuration",
        "prod-day2-custom-ca-trust-missing": "custom_ca_trust_bundle",
        "prod-day2-external-private-registry-missing": "workloads_using_external_private_registries",
        "prod-day2-workload-vulnerability-scanner-missing": "workload_vulnerability_scanning",
        "prod-day2-dynatrace-observability-missing": "dynatrace_observability",
        "prod-day2-qualys-scanning-agents-missing": "qualys_scanning_agents",
        "prod-day2-prisma-twistlock-defenders-missing": "prisma_twistlock_defenders",
        "prod-day2-aqua-security-platform-missing": "aqua_security_platform",
        "prod-day2-splunk-observability-missing": "splunk_observability",
        "prod-day2-loki-stack-logging-missing": "loki_stack_logging",
        "prod-day2-datadog-observability-missing": "datadog_observability",
        "prod-day2-appdynamics-observability-missing": "appdynamics_observability",
        "prod-day2-openshift-aap-missing": "openshift_aap",
        "prod-day2-openshift-custom-metrics-autoscaler-missing": "openshift_custom_metrics_autoscaler",
        "prod-day2-platform-cluster-logging-missing": "cluster_log_forwarding",
        "prod-day2-platform-external-secrets-operator-missing": "external_secrets_operator",
        "prod-day2-workload-backup-provider-missing": "application_backup_and_restore_readiness",
        "prod-day2-platform-compliance-validation-missing": "compliance_requirements_validation",
        "prod-day2-platform-pipelines-operator-missing": "openshift_pipeline_workflows",
        "prod-day2-openshift-developer-hub-missing": "openshift_developer_hub",
        "prod-day2-openshift-dev-spaces-missing": "openshift_dev_spaces",
        "prod-day2-platform-cert-manager-missing": "cert_manager_operator",
        "prod-day2-platform-acs-missing": "advanced_cluster_security",
        "prod-day2-platform-namespace-governance-weak": "multi_tenant_namespace_governance",
        "prod-day2-platform-cost-management-missing": "cost_management_operator",
        "prod-day2-acm-management-missing": "advanced_cluster_management",
        "prod-day2-secondary-site-dr-missing": "secondary_site_disaster_recovery",
        "prod-day2-secondary-site-dr-topology-incomplete": "secondary_site_disaster_recovery",
        "prod-day2-secondary-site-dr-protected-workloads-missing": "secondary_site_disaster_recovery",
        "prod-day2-secondary-site-dr-replication-config-missing": "secondary_site_disaster_recovery",
        "prod-day2-secondary-site-dr-health-warnings": "secondary_site_disaster_recovery",
        "prod-day2-acm-dr-missing": "acm_multicluster_disaster_recovery",
        "prod-day2-acm-dr-registration-missing": "acm_multicluster_disaster_recovery",
        "prod-day2-acm-dr-topology-incomplete": "acm_multicluster_disaster_recovery",
        "prod-day2-acm-dr-protected-workloads-missing": "acm_multicluster_disaster_recovery",
        "prod-day2-acm-dr-replication-config-missing": "acm_multicluster_disaster_recovery",
        "prod-day2-acm-dr-health-warnings": "acm_multicluster_disaster_recovery",
        "prod-day2-external-alert-delivery-missing": "external_alert_delivery",
        "prod-day2-cicd-runners-missing": "cluster_hosted_cicd_runners",
        "prod-day2-namespace-network-policy-baseline-missing": "namespace_network_policy_baseline",
        "prod-day2-namespace-egress-controls-missing": "namespace_egress_controls",
        "prod-day2-openshift-data-foundation-missing": "openshift_data_foundation",
        "prod-day2-ibm-cloud-pak-business-automation-missing": "ibm_cloud_pak_business_automation",
        "prod-day2-openshift-virtualization-missing": "openshift_virtualization",
        "prod-day2-openshift-ai-missing": "openshift_ai",
        "prod-day2-image-registry-policy-governance-missing": "image_registry_policy_governance",
        "prod-day2-image-signature-and-admission-policy-missing": "image_signature_and_admission_policy",
        "prod-day2-image-signature-and-admission-policy-insecure-registries": "image_signature_and_admission_policy",
        "prod-day2-cluster-network-observability-missing": "cluster_network_observability",
        "prod-day2-service-mesh-missing": "service_mesh_control_plane",
        "prod-day2-serverless-missing": "openshift_serverless",
        "prod-day2-windows-container-workloads-missing": "windows_container_workloads",
        "prod-day2-gpu-accelerated-workloads-missing": "gpu_accelerated_workloads",
        "prod-day2-sandboxed-container-workloads-missing": "sandboxed_container_workloads",
        "prod-day2-node-tuning-operator-missing": "node_tuning_operator",
        "prod-day2-kubernetes-nmstate-networking-missing": "kubernetes_nmstate_networking",
        "prod-day2-descheduler-operator-missing": "descheduler_operator",
    }
    return issue_map.get(issue, "")

def add_finding(issue, detail, severity="warning", source="general", capability_key=None, recommended_action=None):
    capability_key = capability_key if capability_key is not None else finding_capability_key(issue, source)
    if capability_key and not cap_enabled(capability_key):
        return
    findings.append({
        "issue": issue,
        "detail": detail,
        "severity": severity,
        "source": source,
        "capability": capability_key,
        "docs": docs_for_capability(capability_key) if capability_key else "",
        "recommended_action": recommended_action or detail,
    })

gitops_present = bool(argocds or gitops_apps or gitops_projects)
gitops_controller_context_present = bool(
    len(argocds) > 0
    or len(gitops_projects) > 0
    or "openshift-gitops" in namespace_names
)
gitops_application_configuration_present = bool(
    len(gitops_apps_with_repo_source) > 0
)
gitops_operational = bool(
    len(gitops_apps_with_repo_source) > 0
    and len(gitops_apps_healthy_and_synced) == len(gitops_apps_with_repo_source)
)
gitops_automated_sync_present = len(gitops_apps_with_automated_sync) > 0
gitops_reconciliation_healthy = bool(
    len(gitops_apps_with_repo_source) > 0
    and len(gitops_apps_healthy_and_synced) == len(gitops_apps_with_repo_source)
    and len(gitops_apps_with_automated_sync) > 0
)
gitops_context_detail = (
    f"argocds={len(argocds)} "
    f"appprojects={len(gitops_projects)} "
    f"openshift_gitops_namespace={'openshift-gitops' in namespace_names}"
)
gitops_configuration_detail = (
    f"applications={len(gitops_apps)} "
    f"repoBackedApplications={len(gitops_apps_with_repo_source)}"
)
gitops_reconciliation_detail = (
    f"healthySyncedApplications={len(gitops_apps_healthy_and_synced)}/{len(gitops_apps_with_repo_source)} "
    f"automatedSyncApplications={len(gitops_apps_with_automated_sync)}"
)
add_check(
    "GitOps controller or chart context",
    ("OK" if gitops_controller_context_present else ("WARN" if cap_required("declarative_gitops_operations") else "INFO")),
    gitops_context_detail,
    "GitOps resource inventory",
    level=cap_level("declarative_gitops_operations", base_required_level),
    scored=False,
    capability_key="declarative_gitops_operations",
)
add_check(
    "GitOps declarative application configuration",
    ("OK" if gitops_application_configuration_present else ("WARN" if (gitops_controller_context_present or cap_required("declarative_gitops_operations")) else "INFO")),
    gitops_configuration_detail,
    "GitOps resource inventory",
    level=cap_level("declarative_gitops_operations", base_required_level),
    scored=False,
    capability_key="declarative_gitops_operations",
)
add_check(
    "GitOps reconciliation health and automation",
    ("OK" if gitops_reconciliation_healthy else ("WARN" if (gitops_present or cap_required("declarative_gitops_operations")) else "INFO")),
    gitops_reconciliation_detail,
    "GitOps resource inventory",
    level=cap_level("declarative_gitops_operations", base_required_level),
    scored=False,
    capability_key="declarative_gitops_operations",
)
if not gitops_present and cap_required("declarative_gitops_operations"):
    add_finding(
        "prod-day2-gitops-missing",
        "no Argo CD, Argo CD Application, or AppProject resources were found",
        severity=cap_failure_severity("declarative_gitops_operations"),
        source="GitOps resource inventory",
    )
if gitops_present and cap_required("declarative_gitops_operations") and len(gitops_apps_with_repo_source) > 0 and len(gitops_apps_healthy_and_synced) != len(gitops_apps_with_repo_source):
    add_finding(
        "prod-day2-gitops-applications-unhealthy",
        (
            "Argo CD Application resources were found with repository sources, but not all were healthy and synced: "
            f"healthySynced={len(gitops_apps_healthy_and_synced)}/{len(gitops_apps_with_repo_source)}"
        ),
        severity=cap_failure_severity("declarative_gitops_operations"),
        source="GitOps resource inventory",
    )
if gitops_present and cap_required("declarative_gitops_operations") and len(gitops_apps) == 0:
    add_finding(
        "prod-day2-gitops-applications-missing",
        "GitOps controller resources were found but no Argo CD Application resources were detected, so declarative managed workload or platform inventory was not demonstrated",
        severity=cap_failure_severity("declarative_gitops_operations"),
        source="GitOps resource inventory",
    )
if gitops_present and cap_required("declarative_gitops_operations") and len(gitops_apps) > 0 and not gitops_operational:
    add_finding(
        "prod-day2-gitops-repo-source-missing",
        "Argo CD Application resources were found but none exposed a Git repository source, so declarative reconciliation intent was not demonstrated from collected data",
        severity=cap_failure_severity("declarative_gitops_operations"),
        source="GitOps resource inventory",
    )
if gitops_present and len(gitops_apps) > 0 and not gitops_automated_sync_present:
    add_finding(
        "prod-day2-gitops-automated-sync-missing",
        "Argo CD Application resources were found but none showed syncPolicy.automated, so continuous reconciliation may rely on manual sync operations",
        severity="warning" if cap_required("declarative_gitops_operations") else "info",
        source="GitOps resource inventory",
    )

ext_secret_store_count = len(clustersecretstores) + len(secretstores)
ext_secrets_namespace_present = "external-secrets-operator" in namespace_names
ext_secrets_subscription_present = (
    "external-secrets-operator" in subscription_packages
    or "external-secrets" in subscription_packages
)
ext_secrets_crd_present = crd_has(
    "externalsecrets.external-secrets.io",
    "clustersecretstores.external-secrets.io",
    "secretstores.external-secrets.io",
)
ext_secrets_operator_workload_present = any_keyword(
    [
        "external-secrets-operator",
        "external-secrets",
        "external-secrets-webhook",
        "external-secrets-cert-controller",
    ],
    all_workload_blobs,
)
ext_secrets_present = bool(
    ext_secret_store_count > 0
    or len(externalsecrets) > 0
    or ext_secrets_namespace_present
)
ready_secret_stores = [
    item for item in (clustersecretstores + secretstores)
    if has_true_condition(item, "Ready") and not has_problem_condition(item) and not has_problem_status(item)
]
ready_external_secrets = [
    item for item in externalsecrets
    if has_true_condition(item, "Ready", "SecretSynced") and not has_problem_condition(item) and not has_problem_status(item)
]
ext_secrets_healthy = bool(
    ext_secret_store_count > 0
    and len(externalsecrets) > 0
    and len(ready_secret_stores) == ext_secret_store_count
    and len(ready_external_secrets) == len(externalsecrets)
)
ext_secrets_context_present = bool(
    ext_secrets_subscription_present
    or ext_secrets_namespace_present
    or ext_secrets_crd_present
    or ext_secrets_operator_workload_present
)
ext_secrets_configuration_present = bool(
    ext_secret_store_count > 0 and len(externalsecrets) > 0
)
ext_secrets_managed_sync_present = bool(
    len(ready_external_secrets) > 0 and len(ready_secret_stores) > 0
)
ext_secrets_context_detail = (
    f"subscription_present={ext_secrets_subscription_present} "
    f"namespace_present={ext_secrets_namespace_present} "
    f"crd_present={ext_secrets_crd_present} "
    f"operator_workload_present={ext_secrets_operator_workload_present}"
)
ext_secrets_configuration_detail = (
    f"clustersecretstores={len(clustersecretstores)} "
    f"secretstores={len(secretstores)} "
    f"externalsecrets={len(externalsecrets)}"
)
ext_secrets_sync_detail = (
    f"ready_stores={len(ready_secret_stores)}/{ext_secret_store_count} "
    f"ready_externalsecrets={len(ready_external_secrets)}/{len(externalsecrets)}"
)
add_check(
    "External Secrets Operator context",
    ("OK" if ext_secrets_context_present else ("WARN" if cap_required("external_secrets_operator") else "INFO")),
    ext_secrets_context_detail,
    "external secrets integration guidance",
    level=external_secrets_level,
    scored=False,
    capability_key="external_secrets_operator",
)
add_check(
    "External secret store and sync configuration",
    ("OK" if ext_secrets_configuration_present else ("WARN" if (ext_secrets_context_present or cap_required("external_secrets_operator")) else "INFO")),
    ext_secrets_configuration_detail,
    "external secrets integration guidance",
    level=external_secrets_level,
    scored=False,
    capability_key="external_secrets_operator",
)
add_check(
    "External secret managed sync footprint",
    ("OK" if ext_secrets_healthy else ("WARN" if (ext_secrets_configuration_present or cap_required("external_secrets_operator")) else "INFO")),
    ext_secrets_sync_detail,
    "external secrets integration guidance",
    level=external_secrets_level,
    scored=False,
    capability_key="external_secrets_operator",
)
if cap_required("external_secrets_operator") and not ext_secrets_present:
    add_finding(
        "prod-day2-external-secrets-missing",
        "no External Secrets Operator namespace, store, or ExternalSecret resources were found",
        severity=cap_failure_severity("external_secrets_operator"),
        source="external secrets integration guidance",
    )
elif cap_required("external_secrets_operator") and not ext_secrets_healthy:
    add_finding(
        "prod-day2-external-secrets-missing",
        (
            "external secret synchronization is only partially configured: "
            f"stores={ext_secret_store_count}, readyStores={len(ready_secret_stores)}, "
            f"externalsecrets={len(externalsecrets)}, readyExternalSecrets={len(ready_external_secrets)}"
        ),
        severity=cap_failure_severity("external_secrets_operator"),
        source="external secrets integration guidance",
    )

conjur_namespace_present = any(
    name in namespace_names
    for name in {
        "conjur",
        "conjur-server",
        "cyberark-conjur",
    }
)
conjur_workload_present = any_keyword(
    [
        "conjur",
        "conjur-oss",
        "conjur-follower",
        "conjur-appliance",
        "authn-k8s",
        "conjur-authn",
        "secretless",
        "secrets-provider-for-k8s",
        "conjur-csi-provider",
    ],
    all_workload_blobs,
)
conjur_secretproviderclass_resources = [
    item for item in secretproviderclasses
    if (
        str((((item.get("spec") or {}).get("provider")) or "")).strip().lower() == "conjur"
        or "conjur.org" in json.dumps(((item.get("spec") or {}).get("parameters")) or {}).lower()
        or "cyberark" in json.dumps(((item.get("spec") or {}).get("parameters")) or {}).lower()
    )
]
conjur_secretproviderclass_present = len(conjur_secretproviderclass_resources) > 0
conjur_context_present = bool(
    conjur_namespace_present
    or conjur_workload_present
    or conjur_secretproviderclass_present
)
cyberark_conjur_secrets_management_present = bool(
    conjur_workload_present
    or conjur_secretproviderclass_present
    or conjur_namespace_present
)
cyberark_conjur_secrets_management_healthy = bool(
    conjur_workload_present
    or conjur_secretproviderclass_present
)
add_check(
    "CyberArk Conjur deployment context",
    ("OK" if conjur_context_present else ("WARN" if cap_required("cyberark_conjur_secrets_management") else "INFO")),
    (
        f"namespace_present={conjur_namespace_present} "
        f"secretproviderclasses={len(conjur_secretproviderclass_resources)} "
        f"workload_present={conjur_workload_present}"
    ),
    "CyberArk Conjur workload and Secrets Provider inventory",
    level=cap_level("cyberark_conjur_secrets_management", "informational"),
    scored=False,
    capability_key="cyberark_conjur_secrets_management",
)
add_check(
    "Conjur-backed secret delivery configuration",
    ("OK" if conjur_secretproviderclass_present else ("WARN" if (conjur_context_present or cap_required("cyberark_conjur_secrets_management")) else "INFO")),
    f"conjur_secretproviderclasses={len(conjur_secretproviderclass_resources)}",
    "CyberArk Conjur workload and Secrets Provider inventory",
    level=cap_level("cyberark_conjur_secrets_management", "informational"),
    scored=False,
    capability_key="cyberark_conjur_secrets_management",
)
add_check(
    "CyberArk Conjur managed workload footprint",
    ("OK" if conjur_workload_present else ("WARN" if (conjur_context_present or cap_required("cyberark_conjur_secrets_management")) else "INFO")),
    f"conjur_workload_present={conjur_workload_present}",
    "CyberArk Conjur workload and Secrets Provider inventory",
    level=cap_level("cyberark_conjur_secrets_management", "informational"),
    scored=False,
    capability_key="cyberark_conjur_secrets_management",
)
if cap_required("cyberark_conjur_secrets_management") and not cyberark_conjur_secrets_management_present:
    add_finding(
        "prod-day2-cyberark-conjur-secrets-management-missing",
        "no CyberArk Conjur namespace, workload, or Conjur-backed SecretProviderClass footprint was detected",
        severity=cap_failure_severity("cyberark_conjur_secrets_management"),
        source="CyberArk Conjur workload and Secrets Provider inventory",
        recommended_action=(
            "If CyberArk Conjur is the intended secrets-management path, collect or deploy Conjur server, "
            "follower, authenticator, Secretless, Secrets Provider, or Conjur-backed SecretProviderClass evidence."
        ),
    )
elif cap_required("cyberark_conjur_secrets_management") and not cyberark_conjur_secrets_management_healthy:
    add_finding(
        "prod-day2-cyberark-conjur-secrets-management-missing",
        "partial CyberArk Conjur signals were found, but no Conjur workload footprint or Conjur-backed SecretProviderClass was detected to demonstrate an active secrets-management path",
        severity=cap_failure_severity("cyberark_conjur_secrets_management"),
        source="CyberArk Conjur workload and Secrets Provider inventory",
        recommended_action=(
            "Review the Conjur server, follower, authenticator, Secretless, Secrets Provider, or CSI provider rollout "
            "and confirm an application-facing secret delivery path is active."
        ),
    )

user_workload_vendor_metrics_present = bool(obs.get("vendor_managed_metrics_forwarding_present"))
user_workload_monitoring_context_present = (
    enable_user_workload
    or user_workload_vendor_metrics_present
)
user_workload_monitoring_scrape_present = (
    len(servicemonitors) > 0
    or len(podmonitors) > 0
    or bool(uwm)
)
user_workload_monitoring_healthy = (
    user_workload_monitoring_scrape_present
    or user_workload_vendor_metrics_present
)
add_check(
    "User workload monitoring configuration path",
    (
        "OK"
        if user_workload_monitoring_context_present
        else ("WARN" if cap_required("user_workload_metrics_monitoring") else "INFO")
    ),
    (
        f"enableUserWorkload={enable_user_workload} "
        f"vendor_managed={user_workload_vendor_metrics_present} "
        f"vendors={','.join(obs.get('metrics_forwarding_vendor_names') or []) or 'none'}"
    ),
    "user workload monitoring and platform monitoring guidance",
    level=cap_level("user_workload_metrics_monitoring", base_required_level),
)
add_check(
    "User workload metrics scrape inventory",
    (
        "OK"
        if (user_workload_monitoring_scrape_present or user_workload_vendor_metrics_present)
        else ("WARN" if (user_workload_monitoring_context_present or cap_required("user_workload_metrics_monitoring")) else "INFO")
    ),
    (
        f"servicemonitors={len(servicemonitors)} "
        f"podmonitors={len(podmonitors)} "
        f"user_workload_config_present={bool(uwm)}"
    ),
    "user workload monitoring and platform monitoring guidance",
    level=cap_level("user_workload_metrics_monitoring", base_required_level),
)
add_check(
    "User workload metrics coverage path",
    (
        "OK"
        if user_workload_monitoring_healthy
        else ("WARN" if (user_workload_monitoring_context_present or cap_required("user_workload_metrics_monitoring")) else "INFO")
    ),
    (
        f"native_scrape_present={user_workload_monitoring_scrape_present} "
        f"vendor_managed={user_workload_vendor_metrics_present} "
        f"vendors={','.join(obs.get('metrics_forwarding_vendor_names') or []) or 'none'}"
    ),
    "user workload monitoring and platform monitoring guidance",
    level=cap_level("user_workload_metrics_monitoring", base_required_level),
)
if not enable_user_workload and not user_workload_vendor_metrics_present:
    add_finding(
        "prod-day2-user-workload-monitoring-disabled",
        "cluster-monitoring-config does not enable user workload monitoring, and no approved vendor-managed workload metrics path was detected",
        severity=cap_failure_severity("user_workload_metrics_monitoring"),
        source="user workload monitoring and platform monitoring guidance",
    )

user_workload_alertmanager_additional_configs = (
    ((uwm.get("alertmanager") or {}).get("additionalAlertmanagerConfigs") or [])
    if isinstance(uwm, dict)
    else []
)
vendor_metrics_forwarding_present = bool(obs.get("vendor_managed_metrics_forwarding_present"))
vendor_metrics_forwarding_names = [
    str(item).strip()
    for item in (obs.get("metrics_forwarding_vendor_names") or [])
    if str(item).strip()
]
user_workload_scrape_present = len(servicemonitors) > 0 or len(podmonitors) > 0 or bool(uwm)
user_workload_alerting_present = (
    len(user_workload_alertmanager_additional_configs) > 0
    or len(servicemonitors) > 0
)
user_workload_native_alerting_healthy = (
    enable_user_workload
    and user_workload_scrape_present
    and user_workload_alerting_present
)
user_workload_vendor_managed_observability_present = bool(
    vendor_metrics_forwarding_present and vendor_metrics_forwarding_names
)
user_workload_alerting_delivery_model = (
    "hybrid"
    if (user_workload_native_alerting_healthy and user_workload_vendor_managed_observability_present)
    else (
        "vendor-managed"
        if user_workload_vendor_managed_observability_present
        else ("native" if user_workload_native_alerting_healthy else "none")
    )
)
user_workload_alerting_healthy = (
    user_workload_native_alerting_healthy
    or user_workload_vendor_managed_observability_present
)
add_check(
    "User workload alerting and SLOs",
    cap_status_for_presence(
        "user_workload_alerting_and_slos",
        user_workload_scrape_present or user_workload_vendor_managed_observability_present,
        user_workload_alerting_healthy,
    ),
    (
        (
            "meets criteria via vendor-managed observability evidence: "
            f"vendors={','.join(vendor_metrics_forwarding_names)} "
            f"deliveryModel={user_workload_alerting_delivery_model} "
            f"enableUserWorkload={enable_user_workload} "
            f"servicemonitors={len(servicemonitors)} "
            f"podmonitors={len(podmonitors)} "
            f"userAlertmanagerAdditionalConfigs={len(user_workload_alertmanager_additional_configs)}"
        )
        if (user_workload_vendor_managed_observability_present and not user_workload_native_alerting_healthy)
        else (
            f"enableUserWorkload={enable_user_workload} "
            f"servicemonitors={len(servicemonitors)} "
            f"podmonitors={len(podmonitors)} "
            f"userWorkloadConfigPresent={bool(uwm)} "
            f"userAlertmanagerAdditionalConfigs={len(user_workload_alertmanager_additional_configs)} "
            f"vendorManaged={user_workload_vendor_managed_observability_present} "
            f"vendors={','.join(vendor_metrics_forwarding_names) if vendor_metrics_forwarding_names else 'none'} "
            f"deliveryModel={user_workload_alerting_delivery_model}"
        )
    ),
    "user workload monitoring alerting and SLO guidance",
    level=cap_level("user_workload_alerting_and_slos", base_required_level),
)
if cap_required("user_workload_alerting_and_slos") and not user_workload_alerting_healthy:
    add_finding(
        "prod-day2-user-workload-alerting-slos-missing",
        (
            "no native user workload monitoring path or vendor-managed observability evidence was detected for user workload alerting and SLO support"
            if (not enable_user_workload and not user_workload_vendor_managed_observability_present)
            else (
                "user workload scrape or alert-routing evidence is incomplete and no qualifying vendor-managed observability path was detected for user workload alerting and SLO support"
            )
        ),
        severity=cap_failure_severity("user_workload_alerting_and_slos"),
        source="user workload monitoring alerting and SLO guidance",
    )

add_check(
    "Grafana dashboard inventory",
    cap_status_for_presence("grafana_metrics_dashboards", grafana_dashboard_present),
    (
        f"grafana_present={grafana_present} "
        f"dashboard_configmaps={len(dashboard_configmaps)} "
        f"grafanadashboards={len(grafanadashboards)} "
        f"grafana_dashboard_crds={grafana_dashboard_crd_present}"
    ),
    "Grafana dashboard configuration inventory",
    level=cap_level("grafana_metrics_dashboards", "informational"),
    scored=False,
)
if not grafana_dashboard_present and cap_required("grafana_metrics_dashboards"):
    add_finding(
        "prod-day2-grafana-dashboards-missing",
        (
            "no in-cluster Grafana dashboard inventory was detected from dashboard ConfigMaps or GrafanaDashboard resources"
            + (", and no Grafana workload footprint was found" if not grafana_present else "")
        ),
        severity=cap_failure_severity("grafana_metrics_dashboards"),
        source="Grafana dashboard configuration inventory",
    )

add_check(
    "Prometheus persistent storage",
    (
        "OK"
        if prometheus_persistent
        else ("WARN" if cap_required("persistent_monitoring_storage") else "INFO")
    ),
    f"storage_request={prometheus_storage_request or 'missing'}",
    "Red Hat monitoring + IBM/Azure guidance",
    level=cap_level("persistent_monitoring_storage", choose_level(base_required_level, telemetry_level)),
)
add_check(
    "Alertmanager persistent storage",
    (
        "OK"
        if alertmanager_persistent
        else ("WARN" if cap_required("persistent_monitoring_storage") else "INFO")
    ),
    f"storage_request={alertmanager_storage_request or 'missing'}",
    "Red Hat monitoring + IBM/Azure guidance",
    level=cap_level("persistent_monitoring_storage", choose_level(base_required_level, telemetry_level)),
)
add_check(
    "Thanos Ruler persistent storage",
    (
        "OK"
        if (thanos_ruler_persistent or not is_multi_node_cluster)
        else ("WARN" if cap_required("persistent_monitoring_storage") else "INFO")
    ),
    (
        f"storage_request={thanos_ruler_storage_request or ('not-required' if not is_multi_node_cluster else 'missing')} "
        f"multiNode={is_multi_node_cluster}"
    ),
    "Red Hat monitoring + IBM/Azure guidance",
    level=cap_level("persistent_monitoring_storage", choose_level(base_required_level, telemetry_level)),
)
if not monitoring_persistent:
    add_finding(
        "prod-day2-monitoring-persistence-missing",
        (
            "cluster monitoring persistent storage is incomplete: "
            f"prometheus={'configured' if prometheus_persistent else 'missing'}, "
            f"alertmanager={'configured' if alertmanager_persistent else 'missing'}, "
            f"thanosRuler={('configured' if thanos_ruler_persistent else ('not-required' if not is_multi_node_cluster else 'missing'))}"
        ),
        severity=cap_failure_severity("persistent_monitoring_storage"),
        source="Red Hat monitoring + IBM/Azure guidance",
    )

vendor_log_forwarding_present = bool(obs.get("vendor_managed_log_forwarding_present"))
vendor_log_forwarding_names = [
    str(item).strip()
    for item in (obs.get("log_forwarding_vendor_names") or [])
    if str(item).strip()
]
vendor_metrics_forwarding_present = bool(obs.get("vendor_managed_metrics_forwarding_present"))
vendor_metrics_forwarding_names = [
    str(item).strip()
    for item in (obs.get("metrics_forwarding_vendor_names") or [])
    if str(item).strip()
]
log_forwarding_present = (
    len(obs.get("external_log_forwarding_outputs") or []) > 0
    or len(clusterlogforwarders) > 0
    or vendor_log_forwarding_present
)
cluster_log_forwarding_external_outputs = len(obs.get("external_log_forwarding_outputs") or [])
add_check(
    "Cluster log forwarding collection path",
    (
        "OK"
        if log_collection_present
        else ("WARN" if cap_required("cluster_log_forwarding") else "INFO")
    ),
    (
        f"clusterlogforwarders={len(clusterlogforwarders)} "
        f"vendor_managed={vendor_log_forwarding_present} "
        f"vendors={','.join(vendor_log_forwarding_names) if vendor_log_forwarding_names else 'none'}"
    ),
    "cluster logging and external forwarding guidance",
    level=cap_level("cluster_log_forwarding", telemetry_level),
)
add_check(
    "Cluster log forwarding external destinations",
    (
        "OK"
        if (cluster_log_forwarding_external_outputs > 0 or vendor_log_forwarding_present)
        else ("WARN" if (log_collection_present or cap_required("cluster_log_forwarding")) else "INFO")
    ),
    (
        f"external_outputs={cluster_log_forwarding_external_outputs} "
        f"vendor_managed={vendor_log_forwarding_present} "
        f"vendors={','.join(vendor_log_forwarding_names) if vendor_log_forwarding_names else 'none'}"
    ),
    "cluster logging and external forwarding guidance",
    level=cap_level("cluster_log_forwarding", telemetry_level),
)
add_check(
    "Cluster log forwarding log coverage",
    (
        "OK"
        if cluster_log_forwarding_healthy
        else ("WARN" if (log_collection_present or cap_required("cluster_log_forwarding")) else "INFO")
    ),
    (
        f"application={obs.get('application_logs_delivery_state') or 'not-collected'} "
        f"infrastructure={obs.get('infrastructure_logs_delivery_state') or 'not-collected'} "
        f"audit={obs.get('audit_logs_delivery_state') or 'not-collected'}"
    ),
    "cluster logging and external forwarding guidance",
    level=cap_level("cluster_log_forwarding", telemetry_level),
)
if not log_collection_present and cap_required("cluster_log_forwarding"):
    add_finding(
        "prod-day2-external-log-forwarding-missing",
        "no native ClusterLogForwarder or vendor-managed log forwarding evidence was detected for application, infrastructure, or audit logs",
        severity=cap_failure_severity("cluster_log_forwarding"),
        source="cluster logging and external forwarding guidance",
    )
elif cap_required("cluster_log_forwarding") and not cluster_log_forwarding_healthy:
    add_finding(
        "prod-day2-external-log-forwarding-missing",
        (
            f"log forwarding is incomplete: "
            f"application={obs.get('application_logs_delivery_state') or 'not-collected'}, "
            f"infrastructure={obs.get('infrastructure_logs_delivery_state') or 'not-collected'}, "
            f"audit={obs.get('audit_logs_delivery_state') or 'not-collected'}, "
            f"vendorEvidence={','.join(vendor_log_forwarding_names) if vendor_log_forwarding_names else 'none'}"
        ),
        severity=cap_failure_severity("cluster_log_forwarding"),
        source="cluster logging and external forwarding guidance",
    )

cluster_remote_write_total = int(obs.get("cluster_metrics_remote_write_count") or 0)
cluster_remote_write = int(obs.get("external_cluster_metrics_remote_write_count") or 0)
user_remote_write_total = int(obs.get("user_workload_metrics_remote_write_count") or 0)
user_remote_write = int(obs.get("external_user_workload_metrics_remote_write_count") or 0)
add_check(
    "Cluster metrics remote write configuration",
    (
        "OK"
        if (cluster_remote_write_total > 0 or vendor_metrics_forwarding_present)
        else ("WARN" if cap_required("cluster_metrics_remote_write") else "INFO")
    ),
    (
        f"cluster_state={obs.get('cluster_metrics_delivery_state') or 'not-configured'} "
        f"cluster_remote_write_total={cluster_remote_write_total} "
        f"vendor_managed={vendor_metrics_forwarding_present} "
        f"vendors={','.join(vendor_metrics_forwarding_names) if vendor_metrics_forwarding_names else 'none'}"
    ),
    "Red Hat monitoring + vendor monitoring guidance",
    level=cap_level("cluster_metrics_remote_write", telemetry_level),
)
add_check(
    "External cluster metrics destination",
    (
        "OK"
        if (cluster_remote_write > 0 or vendor_metrics_forwarding_present)
        else ("WARN" if ((cluster_remote_write_total > 0) or cap_required("cluster_metrics_remote_write")) else "INFO")
    ),
    (
        f"cluster_remote_write_external={cluster_remote_write} "
        f"vendor_managed={vendor_metrics_forwarding_present} "
        f"vendors={','.join(vendor_metrics_forwarding_names) if vendor_metrics_forwarding_names else 'none'}"
    ),
    "Red Hat monitoring + vendor monitoring guidance",
    level=cap_level("cluster_metrics_remote_write", telemetry_level),
)
add_check(
    "User workload metrics export context",
    (
        "OK"
        if (user_remote_write_total == 0 or user_remote_write > 0 or vendor_metrics_forwarding_present)
        else ("WARN" if (cluster_remote_write_total > 0 or user_remote_write_total > 0 or cap_required("cluster_metrics_remote_write")) else "INFO")
    ),
    (
        f"user_workload_state={obs.get('user_workload_metrics_delivery_state') or 'not-configured'} "
        f"user_workload_remote_write_total={user_remote_write_total} "
        f"user_workload_remote_write_external={user_remote_write}"
    ),
    "Red Hat monitoring + vendor monitoring guidance",
    level=cap_level("cluster_metrics_remote_write", telemetry_level),
)
if cap_required("cluster_metrics_remote_write") and cluster_remote_write_total == 0 and not vendor_metrics_forwarding_present:
    add_finding(
        "prod-day2-cluster-metrics-remote-write-missing",
        "cluster-monitoring-config does not define any prometheusK8s.remoteWrite target and no vendor-managed metrics forwarding evidence was detected for cluster metrics export",
        severity=cap_failure_severity("cluster_metrics_remote_write"),
        source="Red Hat monitoring + vendor monitoring guidance",
    )
elif cap_required("cluster_metrics_remote_write") and cluster_remote_write == 0 and not vendor_metrics_forwarding_present:
    add_finding(
        "prod-day2-cluster-metrics-remote-write-missing",
        "prometheusK8s.remoteWrite is configured but all detected cluster metrics targets appear cluster-local only, and no vendor-managed metrics forwarding evidence was detected",
        severity=cap_failure_severity("cluster_metrics_remote_write"),
        source="Red Hat monitoring + vendor monitoring guidance",
    )

external_alert_receiver_count = int(obs.get("external_alert_receiver_count") or 0)
external_alert_source_count = int(obs.get("alert_delivery_source_count") or 0)
external_alert_routed = bool(obs.get("alert_routing_to_external_receiver_configured"))
external_alert_verification = str(obs.get("alert_delivery_verification_status") or "not-configured").strip().lower()
add_check(
    "External alert receiver inventory",
    (
        "OK"
        if external_alert_receiver_count > 0
        else ("WARN" if cap_required("external_alert_delivery") else "INFO")
    ),
    (
        f"external_receivers={external_alert_receiver_count} "
        f"alert_sources={external_alert_source_count}"
    ),
    "AlertmanagerConfig and monitoring alert delivery inventory",
    level=cap_level("external_alert_delivery", telemetry_level),
)
add_check(
    "Alert routing to external receiver",
    (
        "OK"
        if external_alert_routed
        else ("WARN" if (external_alert_receiver_count > 0 or cap_required("external_alert_delivery")) else "INFO")
    ),
    (
        f"routed={external_alert_routed} "
        f"external_receivers={external_alert_receiver_count}"
    ),
    "AlertmanagerConfig and monitoring alert delivery inventory",
    level=cap_level("external_alert_delivery", telemetry_level),
)
add_check(
    "External alert delivery verification",
    (
        "OK"
        if external_alert_verification in ["verified", "passed", "ok"]
        else ("WARN" if (external_alert_delivery_present or cap_required("external_alert_delivery")) else "INFO")
    ),
    (
        f"state={obs.get('alert_delivery_state') or 'not-configured'} "
        f"verification={obs.get('alert_delivery_verification_status') or 'not-configured'}"
    ),
    "AlertmanagerConfig and monitoring alert delivery inventory",
    level=cap_level("external_alert_delivery", telemetry_level),
)
if not external_alert_delivery_present and cap_required("external_alert_delivery"):
    add_finding(
        "prod-day2-external-alert-delivery-missing",
        "no AlertmanagerConfig external receiver or external Alertmanager routing evidence was detected",
        severity=cap_failure_severity("external_alert_delivery"),
        source="AlertmanagerConfig and monitoring alert delivery inventory",
    )
elif cap_required("external_alert_delivery") and not external_alert_delivery_healthy:
    add_finding(
        "prod-day2-external-alert-delivery-missing",
        (
            f"external alert delivery is incomplete: "
            f"state={obs.get('alert_delivery_state') or 'not-configured'}, "
            f"externalReceivers={int(obs.get('external_alert_receiver_count') or 0)}, "
            f"routed={bool(obs.get('alert_routing_to_external_receiver_configured'))}"
        ),
        severity=cap_failure_severity("external_alert_delivery"),
        source="AlertmanagerConfig and monitoring alert delivery inventory",
    )

add_check(
    "Cluster network observability operator subscription",
    (
        "OK"
        if cluster_network_observability_subscription_present
        else ("WARN" if (cluster_network_observability_present or cap_required("cluster_network_observability")) else "INFO")
    ),
    f"subscriptionPresent={cluster_network_observability_subscription_present}",
    "OpenShift network observability operator and workload inventory",
    level=cap_level("cluster_network_observability", "informational"),
    scored=False,
)
add_check(
    "Cluster network observability namespace",
    (
        "OK"
        if cluster_network_observability_namespace_present
        else ("WARN" if (cluster_network_observability_present or cap_required("cluster_network_observability")) else "INFO")
    ),
    f"namespacePresent={cluster_network_observability_namespace_present}",
    "OpenShift network observability operator and workload inventory",
    level=cap_level("cluster_network_observability", "informational"),
    scored=False,
)
add_check(
    "Cluster network observability CRD inventory",
    (
        "OK"
        if cluster_network_observability_crd_present
        else ("WARN" if (cluster_network_observability_present or cap_required("cluster_network_observability")) else "INFO")
    ),
    f"crdPresent={cluster_network_observability_crd_present}",
    "OpenShift network observability operator and workload inventory",
    level=cap_level("cluster_network_observability", "informational"),
    scored=False,
)
add_check(
    "Cluster network observability FlowCollector or workload footprint",
    (
        "OK"
        if (cluster_network_observability_flowcollector_present or cluster_network_observability_workload_present)
        else ("WARN" if (cluster_network_observability_present or cap_required("cluster_network_observability")) else "INFO")
    ),
    (
        f"flowCollectors={cluster_network_observability_flowcollector_count} "
        f"workloadPresent={cluster_network_observability_workload_present}"
    ),
    "OpenShift network observability operator and workload inventory",
    level=cap_level("cluster_network_observability", "informational"),
    scored=False,
)
if cap_required("cluster_network_observability") and not cluster_network_observability_present:
    add_finding(
        "prod-day2-cluster-network-observability-missing",
        "no network observability operator, CRD, FlowCollector, namespace, or workload footprint was detected",
        severity=cap_failure_severity("cluster_network_observability"),
        source="OpenShift network observability operator and workload inventory",
    )
elif cap_required("cluster_network_observability") and not cluster_network_observability_healthy:
    add_finding(
        "prod-day2-cluster-network-observability-incomplete",
        (
            "network observability context was detected, but no FlowCollector resource or "
            "network observability workload footprint was found"
        ),
        severity=cap_failure_severity("cluster_network_observability"),
        source="OpenShift network observability operator and workload inventory",
    )

add_check(
    "OpenShift Developer Hub footprint",
    cap_status_for_presence(
        "openshift_developer_hub",
        openshift_developer_hub_present,
        openshift_developer_hub_healthy,
    ),
    (
        f"subscriptionPresent={openshift_developer_hub_subscription_present} "
        f"namespacePresent={openshift_developer_hub_namespace_present} "
        f"crdPresent={openshift_developer_hub_crd_present} "
        f"contextPresent={openshift_developer_hub_context_present} "
        f"backstages={openshift_developer_hub_backstage_count} "
        f"readyBackstages={openshift_developer_hub_ready_backstage_count} "
        f"workloadPresent={openshift_developer_hub_workload_present}"
    ),
    "Red Hat Developer Hub operator and workload inventory",
    level=cap_level("openshift_developer_hub", "informational"),
    scored=False,
)
if cap_required("openshift_developer_hub") and not openshift_developer_hub_present:
    add_finding(
        "prod-day2-openshift-developer-hub-missing",
        "no Red Hat Developer Hub Backstage resource or portal workload footprint was detected; operator, namespace, or CRD context alone is not treated as an active Developer Hub deployment",
        severity=cap_failure_severity("openshift_developer_hub"),
        source="Red Hat Developer Hub operator and workload inventory",
    )

add_check(
    "OpenShift Dev Spaces footprint",
    cap_status_for_presence(
        "openshift_dev_spaces",
        openshift_dev_spaces_present,
        openshift_dev_spaces_healthy,
    ),
    (
        f"subscriptionPresent={openshift_dev_spaces_subscription_present} "
        f"namespacePresent={openshift_dev_spaces_namespace_present} "
        f"contextPresent={openshift_dev_spaces_context_present} "
        f"cheClusterPresent={openshift_dev_spaces_checluster_present} "
        f"devWorkspacePresent={openshift_dev_spaces_devworkspace_present} "
        f"workspaceOperatorConfigPresent={openshift_dev_spaces_workspace_operator_config_present} "
        f"routingPresent={openshift_dev_spaces_routing_present}"
    ),
    "OpenShift Dev Spaces operator and workspace inventory",
    level=cap_level("openshift_dev_spaces", "informational"),
    scored=False,
)
if cap_required("openshift_dev_spaces") and not openshift_dev_spaces_present:
    add_finding(
        "prod-day2-openshift-dev-spaces-missing",
        "no OpenShift Dev Spaces CheCluster, DevWorkspace, routing, or operator configuration footprint was detected; operator subscription or namespace context alone is not treated as an active Dev Spaces deployment",
        severity=cap_failure_severity("openshift_dev_spaces"),
        source="OpenShift Dev Spaces operator and workspace inventory",
    )

apiserver_audit_profile = str((((apiserver_config.get("spec") or {}).get("audit") or {}).get("profile") or "")).strip().lower()
api_audit_logs_collected = bool(obs.get("audit_logs_collected"))
api_audit_logs_exported_external = bool(obs.get("audit_logs_exported_external"))
api_audit_vendor_log_delivery_present = bool(vendor_log_forwarding_present)
api_audit_vendor_names = [
    str(item).strip()
    for item in (obs.get("log_forwarding_vendor_names") or [])
    if str(item).strip()
]
api_audit_logging_present = bool(
    apiserver_audit_profile
    or api_audit_logs_collected
    or api_audit_vendor_log_delivery_present
)
api_audit_retention_present = bool(
    api_audit_logs_exported_external
    or api_audit_vendor_log_delivery_present
)
add_check(
    "API server audit logging and retention",
    cap_status_for_presence(
        "api_server_audit_and_log_retention",
        api_audit_logging_present,
        api_audit_logging_present and api_audit_retention_present,
    ),
    (
        f"apiserverAuditProfile={apiserver_audit_profile or 'not-configured'} "
        f"auditLogsCollected={api_audit_logs_collected} "
        f"auditLogsExportedExternal={api_audit_logs_exported_external} "
        f"vendorManaged={api_audit_vendor_log_delivery_present} "
        f"vendors={','.join(api_audit_vendor_names) if api_audit_vendor_names else 'none'}"
    ),
    "OpenShift API server audit logging and external retention guidance",
    level=cap_level("api_server_audit_and_log_retention", "informational"),
    scored=False,
)
if cap_required("api_server_audit_and_log_retention") and not api_audit_logging_present:
    add_finding(
        "prod-day2-api-server-audit-and-log-retention-missing",
        "no API server audit profile, external audit log collection, or qualifying vendor-managed audit log delivery path was detected",
        severity=cap_failure_severity("api_server_audit_and_log_retention"),
        source="OpenShift API server audit logging and external retention guidance",
    )
elif cap_required("api_server_audit_and_log_retention") and not api_audit_retention_present:
    add_finding(
        "prod-day2-api-server-audit-retention-path-missing",
        "API server audit logging evidence exists, but no external audit log retention or qualifying vendor-managed audit-delivery path was detected",
        severity=cap_failure_severity("api_server_audit_and_log_retention"),
        source="OpenShift API server audit logging and external retention guidance",
    )

etcd_operator = operators.get("etcd") or {}
kube_apiserver_operator = operators.get("kube-apiserver") or {}
control_plane_runtime_from_platform = bool(
    int(platform_health_summary.get("apiserver_readyz_failed") or 0) == 0
    and int(platform_health_summary.get("apiserver_runtime_degraded") or 0) == 0
    and int(platform_health_summary.get("etcd_leader_unhealthy") or 0) == 0
    and int(platform_health_summary.get("etcd_runtime_degraded") or 0) == 0
)
control_plane_runtime_from_operators = bool(
    str(etcd_operator.get("available") or "").lower() == "true"
    and str(etcd_operator.get("degraded") or "").lower() != "true"
    and str(kube_apiserver_operator.get("available") or "").lower() == "true"
    and str(kube_apiserver_operator.get("degraded") or "").lower() != "true"
)
control_plane_runtime_operator_signal_available = bool(etcd_operator or kube_apiserver_operator)
control_plane_runtime_healthy = (
    control_plane_runtime_from_platform
    if platform_health_summary
    else control_plane_runtime_from_operators
)
control_plane_backup_evidence_scanned = bool(((control_plane_backup_evidence.get("summary") or {}).get("present")) or False)
control_plane_snapshot_evidence_collected = bool(((control_plane_backup_evidence.get("summary") or {}).get("healthy")) or False)
backup_tooling_present = bool(
    workload_backup_provider_present
    or backup_posture.get("successful_backup_count")
    or backup_posture.get("completed_restore_count")
)
successful_backups = int(backup_posture.get("successful_backup_count") or 0)
clean_successful_backups = int(backup_posture.get("clean_successful_backup_count") or 0)
clean_completed_restores = int(backup_posture.get("clean_completed_restore_count") or 0)
application_backup_evidence_present = bool(successful_backups > 0 or clean_successful_backups > 0)
application_restore_evidence_present = bool(clean_completed_restores > 0)
backup_critical_issues = {
    "backup-tooling-not-detected",
    "backup-storage-location-missing",
    "backup-storage-location-unavailable",
    "backup-schedule-missing",
    "successful-backup-missing",
}
backup_warning_issues = {
    "backup-schedule-paused",
    "successful-backup-has-warnings-or-errors",
    "successful-backup-stale",
    "restore-evidence-not-demonstrated",
    "restore-evidence-has-warnings-or-errors",
}
backup_findings_by_issue = {str(item.get("issue") or "") for item in backup_posture_findings if str(item.get("issue") or "")}
backup_ready = bool(
    backup_tooling_present
    and workload_backup_provider_present
    and application_backup_evidence_present
    and application_restore_evidence_present
    and not (backup_findings_by_issue & backup_critical_issues)
    and not (backup_findings_by_issue & backup_warning_issues)
)
add_check(
    "Application backup and restore baseline",
    cap_status_for_presence("application_backup_and_restore_readiness", backup_tooling_present, backup_ready),
    f"provider_present={workload_backup_provider_present} oadp_present={oadp_backup_provider_present} velero_present={velero_backup_provider_present} commvault_present={commvault_backup_provider_present} backup_evidence_present={application_backup_evidence_present} restore_evidence_present={application_restore_evidence_present} dpas={len(dataprotectionapplications)} backupstoragelocations={len(backupstoragelocations)} schedules={len(schedules)} successful_backups={successful_backups} clean_successful_backups={clean_successful_backups} clean_restores={clean_completed_restores} findings={','.join(sorted(backup_findings_by_issue)) or 'none'}",
    "workload backup and restore provider inventory",
    level=cap_level("application_backup_and_restore_readiness", base_required_level),
)
if not backup_ready:
    add_finding(
        "prod-day2-application-backup-baseline-incomplete",
        "workload backup posture is not healthy: verify Commvault, OADP, or upstream Velero is present for workload backup and restore, and provide backup plus restore evidence for the expected recovery path",
        severity=cap_failure_severity("application_backup_and_restore_readiness"),
        source="workload backup and restore provider inventory",
    )

if is_hosted_control_plane:
    add_check(
        "Control plane backup and recovery baseline",
        "INFO",
        "hostedControlPlane=true management cluster evidence is required to validate etcd snapshot and control-plane recovery readiness",
        "Hosted control plane recovery guidance",
        level="informational",
        scored=False,
    )
else:
    add_check(
        "Control plane backup and recovery baseline",
        cap_status_for_presence(
            "control_plane_backup_and_recovery_readiness",
            control_plane_runtime_healthy,
            control_plane_snapshot_evidence_collected,
        ),
        f"platformReadyzFailed={platform_health_summary.get('apiserver_readyz_failed', 'Unknown')} platformApiRuntimeDegraded={platform_health_summary.get('apiserver_runtime_degraded', 'Unknown')} platformEtcdLeaderUnhealthy={platform_health_summary.get('etcd_leader_unhealthy', 'Unknown')} platformEtcdRuntimeDegraded={platform_health_summary.get('etcd_runtime_degraded', 'Unknown')} etcd_available={etcd_operator.get('available', 'Unknown')} etcd_degraded={etcd_operator.get('degraded', 'Unknown')} kube_apiserver_available={kube_apiserver_operator.get('available', 'Unknown')} kube_apiserver_degraded={kube_apiserver_operator.get('degraded', 'Unknown')} snapshot_evidence_scanned={control_plane_backup_evidence_scanned} snapshot_evidence_collected={control_plane_snapshot_evidence_collected}",
        "OpenShift control plane backup and recovery guidance",
        level=cap_level("control_plane_backup_and_recovery_readiness", base_required_level),
    )
    if not control_plane_runtime_healthy:
        add_finding(
            "prod-day2-control-plane-runtime-unhealthy-for-recovery",
            (
                "control plane recovery readiness could not be validated because API or etcd runtime health signals are degraded"
                if platform_health_summary
                else "control plane recovery readiness could not be validated because the etcd or kube-apiserver operator is not healthy"
            ),
            severity=cap_failure_severity("control_plane_backup_and_recovery_readiness"),
            source="OpenShift control plane backup and recovery guidance",
        )
    elif cap_required("control_plane_backup_and_recovery_readiness") and not control_plane_snapshot_evidence_collected:
        add_finding(
            "prod-day2-control-plane-backup-evidence-missing",
            (
                "control plane backup readiness was not demonstrated from collected evidence: no etcd snapshot execution record or retained snapshot/static pod backup artifact inventory was provided to the report"
                if control_plane_backup_evidence_scanned
                else "control plane backup readiness could not be fully demonstrated from the collected evidence set because live node-level snapshot artifact scanning was not available to the report"
            ),
            severity=(
                cap_failure_severity("control_plane_backup_and_recovery_readiness")
                if control_plane_backup_evidence_scanned
                else "warning"
            ),
            source="OpenShift control plane backup and recovery guidance",
        )

add_check(
    "Secondary-site disaster recovery",
    cap_status_for_presence("secondary_site_disaster_recovery", secondary_site_dr_present, secondary_site_dr_healthy),
    (
        f"drpolicies={len(drpolicies)} validPolicies={len(valid_drpolicy_names)} "
        f"drclusters={len(drclusters)} drplacementcontrols={len(drplacementcontrols)} "
        f"volumereplicationgroups={len(volumereplicationgroups)} volumereplications={len(volumereplications)} "
        f"volumereplicationclasses={len(volumereplicationclasses)} volumegroupreplications={len(volumegroupreplications)} protectedPolicies={len(protected_drpolicy_names)}"
    ),
    "ODF DR topology and protected workload inventory",
    level=cap_level("secondary_site_disaster_recovery", "informational"),
    scored=False,
)
if not secondary_site_dr_present and cap_required("secondary_site_disaster_recovery"):
    add_finding(
        "prod-day2-secondary-site-dr-missing",
        "secondary-site disaster recovery was required but no DRPolicy, DRCluster, DRPlacementControl, VolumeReplicationGroup, VolumeReplication, VolumeReplicationClass, or VolumeGroupReplication resources were found",
        severity=cap_failure_severity("secondary_site_disaster_recovery"),
        source="ODF DR topology and protected workload inventory",
    )
if secondary_site_dr_present and cap_required("secondary_site_disaster_recovery") and not secondary_site_dr_topology_ready:
    add_finding(
        "prod-day2-secondary-site-dr-topology-incomplete",
        "secondary-site disaster recovery inventory was detected but the topology is incomplete: at least one DRPolicy referencing two clusters and at least two DRCluster resources are expected",
        severity=cap_failure_severity("secondary_site_disaster_recovery"),
        source="ODF DR topology and protected workload inventory",
    )
if secondary_site_dr_present and cap_required("secondary_site_disaster_recovery") and not secondary_site_dr_replication_ready:
    add_finding(
        "prod-day2-secondary-site-dr-replication-config-missing",
        "secondary-site disaster recovery inventory was detected but no VolumeReplicationClass, VolumeReplication, VolumeReplicationGroup, or VolumeGroupReplication evidence was found for storage replication",
        severity=cap_failure_severity("secondary_site_disaster_recovery"),
        source="ODF DR topology and protected workload inventory",
    )
if secondary_site_dr_present and cap_required("secondary_site_disaster_recovery") and not secondary_site_dr_protected_workloads_ready:
    add_finding(
        "prod-day2-secondary-site-dr-protected-workloads-missing",
        "secondary-site disaster recovery inventory was detected but no DRPlacementControl, VolumeReplicationGroup, or VolumeGroupReplication evidence was found for protected workloads",
        severity=cap_failure_severity("secondary_site_disaster_recovery"),
        source="ODF DR topology and protected workload inventory",
    )
if secondary_site_dr_present and (
    len(drclusters_with_problem_status) > 0
    or len(drpcs_with_problem_status) > 0
    or len(vrgs_with_problem_status) > 0
):
    add_finding(
        "prod-day2-secondary-site-dr-health-warnings",
        (
            f"secondary-site disaster recovery resources reported warning or error states: "
            f"drclusters={len(drclusters_with_problem_status)} "
            f"drplacementcontrols={len(drpcs_with_problem_status)} "
            f"volumereplicationgroups={len(vrgs_with_problem_status)}"
        ),
        severity="warning" if not cap_required("secondary_site_disaster_recovery") else cap_failure_severity("secondary_site_disaster_recovery"),
        source="ODF DR topology and protected workload inventory",
    )

acm_dr_present = bool(secondary_site_dr_present and (acm_registration_present or acm_managed))
acm_dr_healthy = bool(
    acm_dr_present
    and acm_registration_healthy
    and secondary_site_dr_topology_ready
    and secondary_site_dr_replication_ready
    and secondary_site_dr_protected_workloads_ready
    and len(drclusters_with_problem_status) == 0
    and len(drpcs_with_problem_status) == 0
    and len(vrgs_with_problem_status) == 0
)
add_check(
    "ACM multicluster disaster recovery",
    cap_status_for_presence("acm_multicluster_disaster_recovery", acm_dr_present, acm_dr_healthy),
    (
        f"acm_managed={acm_managed} "
        f"klusterlets={len(klusterlets)} "
        f"managedclusteraddons={len(managedclusteraddons)} "
        f"agent_namespaces={','.join(acm_agent_namespaces) or 'none'} "
        f"drpolicies={len(drpolicies)} validPolicies={len(valid_drpolicy_names)} "
        f"drclusters={len(drclusters)} drplacementcontrols={len(drplacementcontrols)} "
        f"volumereplicationgroups={len(volumereplicationgroups)} "
        f"volumereplicationclasses={len(volumereplicationclasses)} "
        f"volumegroupreplications={len(volumegroupreplications)}"
    ),
    "ACM registration plus multicluster DR topology inventory",
    level=cap_level("acm_multicluster_disaster_recovery", "informational"),
    scored=False,
)
if cap_required("acm_multicluster_disaster_recovery") and not secondary_site_dr_present:
    add_finding(
        "prod-day2-acm-dr-missing",
        "ACM multicluster disaster recovery was required but no DRPolicy, DRCluster, DRPlacementControl, VolumeReplicationGroup, VolumeReplication, VolumeReplicationClass, or VolumeGroupReplication resources were found",
        severity=cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )
elif cap_required("acm_multicluster_disaster_recovery") and not acm_registration_present:
    add_finding(
        "prod-day2-acm-dr-registration-missing",
        "multicluster DR resources were found, but no ACM managed-cluster registration evidence was detected from Klusterlet, ManagedClusterAddOn, or ACM agent namespaces",
        severity=cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )
elif cap_required("acm_multicluster_disaster_recovery") and not acm_registration_healthy:
    add_finding(
        "prod-day2-acm-dr-registration-missing",
        "partial ACM managed-cluster evidence was found, but managed-cluster registration health was incomplete for ACM-backed DR operations",
        severity=cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )
if acm_dr_present and cap_required("acm_multicluster_disaster_recovery") and not secondary_site_dr_topology_ready:
    add_finding(
        "prod-day2-acm-dr-topology-incomplete",
        "ACM multicluster disaster recovery inventory was detected but the topology is incomplete: at least one DRPolicy referencing two clusters and at least two DRCluster resources are expected",
        severity=cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )
if acm_dr_present and cap_required("acm_multicluster_disaster_recovery") and not secondary_site_dr_replication_ready:
    add_finding(
        "prod-day2-acm-dr-replication-config-missing",
        "ACM multicluster disaster recovery inventory was detected but no VolumeReplicationClass, VolumeReplication, VolumeReplicationGroup, or VolumeGroupReplication evidence was found for storage replication",
        severity=cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )
if acm_dr_present and cap_required("acm_multicluster_disaster_recovery") and not secondary_site_dr_protected_workloads_ready:
    add_finding(
        "prod-day2-acm-dr-protected-workloads-missing",
        "ACM multicluster disaster recovery inventory was detected but no DRPlacementControl, VolumeReplicationGroup, or VolumeGroupReplication evidence was found for protected workloads",
        severity=cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )
if acm_dr_present and (
    len(drclusters_with_problem_status) > 0
    or len(drpcs_with_problem_status) > 0
    or len(vrgs_with_problem_status) > 0
):
    add_finding(
        "prod-day2-acm-dr-health-warnings",
        (
            f"ACM multicluster disaster recovery resources reported warning or error states: "
            f"drclusters={len(drclusters_with_problem_status)} "
            f"drplacementcontrols={len(drpcs_with_problem_status)} "
            f"volumereplicationgroups={len(vrgs_with_problem_status)}"
        ),
        severity="warning" if not cap_required("acm_multicluster_disaster_recovery") else cap_failure_severity("acm_multicluster_disaster_recovery"),
        source="ACM registration plus multicluster DR topology inventory",
    )

compliance_standards_by_name = {
    str(item.get("standard") or "").strip(): item
    for item in compliance_standards_summary
    if str(item.get("standard") or "").strip()
}

def normalize_compliance_standard_name(value):
    text = str(value or "").strip().lower()
    aliases = {
        "fips": "FIPS",
        "fedramp": "FedRAMP",
        "fedramp moderate": "FedRAMP",
        "hipaa": "HIPAA",
        "pci": "PCI-DSS",
        "pci-dss": "PCI-DSS",
        "pcidss": "PCI-DSS",
        "soc": "SOC",
        "soc1": "SOC",
        "soc2": "SOC",
        "soc3": "SOC",
        "sox": "SOX",
        "nist": "NIST",
        "cis": "CIS",
    }
    return aliases.get(text, str(value or "").strip())

requested_compliance_standards = [
    normalize_compliance_standard_name(item)
    for item in cap_standards("compliance_requirements_validation")
]
requested_compliance_standards = [
    item for index, item in enumerate(requested_compliance_standards)
    if item and item not in requested_compliance_standards[:index]
]

def compliance_standard_supported(standard_name, summary):
    if standard_name == "FIPS":
        return str(summary.get("runtime_status") or "unknown") == "enabled"
    return str(summary.get("verdict") or "not-configured") == "supported"

def compliance_standard_status(standard_name, summary):
    if compliance_standard_supported(standard_name, summary):
        return "OK"
    return "WARN" if cap_required("compliance_requirements_validation") else "INFO"

def compliance_standard_detail(standard_name, summary):
    verdict = str(summary.get("verdict") or "not-configured")
    runtime_status = str(summary.get("runtime_status") or "not-applicable")
    detail = str(summary.get("detail") or "").strip()
    if standard_name == "FIPS":
        return (
            f"runtime={runtime_status} verdict={verdict}"
            + (f" detail={detail}" if detail else "")
        )
    return (
        f"verdict={verdict} configured={bool(summary.get('configured'))} "
        f"active={bool(summary.get('active_enabled'))} "
        f"scans={int(summary.get('scan_count') or 0)} "
        f"failedScans={int(summary.get('failing_scan_count') or 0)} "
        f"failedChecks={int(summary.get('failed_check_count') or 0)}"
        + (f" detail={detail}" if detail else "")
    )

compliance_present = bool(compliance_operator_summary.get("present") or len(compliancesuites) > 0)
compliance_scan_config_present = bool(
    int(compliance_operator_summary.get("scan_setting_binding_count") or 0) > 0
    or int(compliance_operator_summary.get("suite_count") or 0) > 0
    or int(compliance_operator_summary.get("scan_count") or 0) > 0
)
compliance_operator_healthy = bool(
    compliance_present
    and compliance_scan_config_present
    and int(compliance_operator_summary.get("invalid_profilebundle_count") or 0) == 0
)
requested_compliance_standard_gaps = []
requested_compliance_standard_status = []
requested_compliance_failed_scan_count = 0
requested_compliance_failed_check_count = 0
for standard_name in requested_compliance_standards:
    summary = compliance_standards_by_name.get(standard_name) or {}
    verdict = str(summary.get("verdict") or "not-configured")
    runtime_status = str(summary.get("runtime_status") or "not-applicable")
    requested_compliance_failed_scan_count += int(summary.get("failing_scan_count") or 0)
    requested_compliance_failed_check_count += int(summary.get("failed_check_count") or 0)
    add_check(
        f"Compliance standard {standard_name}",
        compliance_standard_status(standard_name, summary),
        compliance_standard_detail(standard_name, summary),
        "compliance requirements validation evidence",
        level=compliance_level,
        scored=False,
        capability_key="compliance_requirements_validation",
    )
    requested_compliance_standard_status.append(
        f"{standard_name}={runtime_status if standard_name == 'FIPS' else verdict}"
    )
    if standard_name == "FIPS":
        if runtime_status != "enabled":
            requested_compliance_standard_gaps.append({
                "standard": standard_name,
                "detail": (
                    "FIPS is an install-time cluster setting and runtime node evidence does not confirm full enablement"
                    if runtime_status == "unknown"
                    else (
                        "FIPS crypto policy evidence is partial and /proc/sys/crypto/fips_enabled confirmation was not collected"
                        if runtime_status == "crypto-policy-fips"
                        else f"runtime FIPS status is {runtime_status}"
                    )
                ),
            })
    elif verdict != "supported":
        requested_compliance_standard_gaps.append({
            "standard": standard_name,
            "detail": (
                "matching Compliance Operator content is available but no current binding, suite, or scan evidence shows it is configured"
                if verdict == "content-available"
                else (
                    "Compliance Operator resources are configured for this standard, but no active suite or scan evidence was found"
                    if verdict == "configured-no-scan"
                    else (
                        "active scans or checks for this standard need review"
                        if verdict == "review-required"
                        else "no matching Compliance Operator standard evidence was found"
                    )
                )
            ),
        })
compliance_healthy = (
    (
        len(requested_compliance_standard_gaps) == 0
        and int(compliance_operator_summary.get("invalid_profilebundle_count") or 0) == 0
    )
    if requested_compliance_standards
    else compliance_operator_healthy
)
add_check(
    "Compliance requirements validation",
    cap_status_for_presence("compliance_requirements_validation", compliance_present, compliance_healthy),
    (
        f"requested={','.join(requested_compliance_standards) or 'none'} "
        f"suites={int(compliance_operator_summary.get('suite_count') or len(compliancesuites))} "
        f"scans={int(compliance_operator_summary.get('scan_count') or 0)} "
        f"bindings={int(compliance_operator_summary.get('scan_setting_binding_count') or 0)} "
        f"failedChecks={requested_compliance_failed_check_count if requested_compliance_standards else int(compliance_operator_summary.get('failed_check_count') or 0)} "
        f"failingScans={requested_compliance_failed_scan_count if requested_compliance_standards else int(compliance_operator_summary.get('failing_scan_count') or 0)} "
        f"invalidProfileBundles={int(compliance_operator_summary.get('invalid_profilebundle_count') or 0)} "
        f"standards={';'.join(requested_compliance_standard_status) or 'not-requested'}"
    ),
    "compliance requirements validation evidence",
    level=compliance_level,
)
if cap_required("compliance_requirements_validation") and not compliance_present:
    add_finding(
        "prod-day2-compliance-requirements-missing",
        "no compliance validation evidence was found from requested runtime signals or Compliance Operator suites, scans, scan-setting bindings, profile content, and openshift-compliance resources",
        severity=cap_failure_severity("compliance_requirements_validation"),
        source="compliance requirements validation evidence",
    )
elif cap_required("compliance_requirements_validation") and requested_compliance_standards and requested_compliance_standard_gaps:
    add_finding(
        "prod-day2-compliance-requirements-missing",
        "requested compliance standards are not fully satisfied: "
        + "; ".join(f"{item['standard']}: {item['detail']}" for item in requested_compliance_standard_gaps),
        severity=cap_failure_severity("compliance_requirements_validation"),
        source="compliance requirements validation evidence",
    )
elif cap_required("compliance_requirements_validation") and requested_compliance_standards and int(compliance_operator_summary.get("invalid_profilebundle_count") or 0) > 0:
    add_finding(
        "prod-day2-compliance-requirements-missing",
        (
            "requested compliance standards cannot be trusted because Compliance Operator profile bundles are invalid: "
            f"invalidProfileBundles={int(compliance_operator_summary.get('invalid_profilebundle_count') or 0)}"
        ),
        severity=cap_failure_severity("compliance_requirements_validation"),
        source="compliance requirements validation evidence",
    )
elif cap_required("compliance_requirements_validation") and not requested_compliance_standards and not compliance_operator_healthy:
    add_finding(
        "prod-day2-compliance-requirements-missing",
        (
            "compliance validation evidence is present but scan-backed configuration is incomplete: "
            f"bindings={int(compliance_operator_summary.get('scan_setting_binding_count') or 0)}, "
            f"suites={int(compliance_operator_summary.get('suite_count') or 0)}, "
            f"scans={int(compliance_operator_summary.get('scan_count') or 0)}, "
            f"invalidProfileBundles={int(compliance_operator_summary.get('invalid_profilebundle_count') or 0)}"
        ),
        severity=cap_failure_severity("compliance_requirements_validation"),
        source="compliance requirements validation evidence",
    )

idp_count = int(data.get("identity_provider_count") or 0)
external_idp_count = int(auth_posture_summary.get("external_identity_provider_count") or 0)
local_idp_count = int(auth_posture_summary.get("local_identity_provider_count") or 0)
invalid_idp_count = int(auth_posture_summary.get("invalid_identity_provider_count") or 0)
kubeadmin_secret_present = bool(auth_posture_summary.get("kubeadmin_secret_present"))
auth_posture_status = str(auth_posture_summary.get("status") or "unknown").strip().lower()
add_check(
    "Central identity provider integration",
    cap_status_for_presence(
        "oauth_external_identity_provider",
        external_idp_count > 0,
        external_idp_count > 0 and auth_posture_status == "healthy" and not kubeadmin_secret_present and invalid_idp_count == 0,
    ),
    (
        f"identityProviders={idp_count} "
        f"externalProviders={external_idp_count} "
        f"localProviders={local_idp_count} "
        f"invalidProviders={invalid_idp_count} "
        f"kubeadminSecretPresent={kubeadmin_secret_present}"
    ),
    "identity provider and production authentication guidance",
    level=cap_level("oauth_external_identity_provider", base_required_level),
)
if idp_count == 0:
    add_finding(
        "prod-day2-identity-provider-missing",
        "oauth cluster has no configured identity provider",
        severity=cap_failure_severity("oauth_external_identity_provider"),
        source="identity provider and production authentication guidance",
    )
elif cap_required("oauth_external_identity_provider") and external_idp_count == 0:
    add_finding(
        "prod-day2-identity-provider-missing",
        (
            f"oauth cluster does not show a valid external identity provider: "
            f"identityProviders={idp_count}, externalProviders={external_idp_count}, localProviders={local_idp_count}, invalidProviders={invalid_idp_count}, kubeadminSecretPresent={kubeadmin_secret_present}"
        ),
        severity=cap_failure_severity("oauth_external_identity_provider"),
        source="identity provider and production authentication guidance",
    )
elif cap_required("oauth_external_identity_provider") and kubeadmin_secret_present:
    add_finding(
        "prod-day2-kubeadmin-fallback-still-present",
        "an external identity provider is configured, but kubeadmin fallback is still present and should be removed or tightly controlled",
        severity=cap_failure_severity("oauth_external_identity_provider"),
        source="identity provider and production authentication guidance",
    )
elif cap_required("oauth_external_identity_provider") and invalid_idp_count > 0:
    add_finding(
        "prod-day2-identity-provider-configuration-unclassified",
        (
            "one or more oauth identity provider entries could not be classified as a supported external provider configuration: "
            f"identityProviders={idp_count}, externalProviders={external_idp_count}, localProviders={local_idp_count}, invalidProviders={invalid_idp_count}"
        ),
        severity=cap_failure_severity("oauth_external_identity_provider"),
        source="identity provider and production authentication guidance",
    )

add_check(
    "Red Hat Insights connectivity",
    "OK" if insights_healthy else "WARN",
    f"available={insights.get('available', 'Unknown')} degraded={insights.get('degraded', 'Unknown')}",
    "Red Hat Insights guidance",
    level=insights_level,
    scored=False,
    capability_key="",
)
if not insights_healthy:
    add_finding(
        "prod-day2-insights-not-healthy",
        "the insights operator is not healthy",
        source="Red Hat Insights guidance",
        capability_key="",
    )

mhc_expected = len(worker_machinesets) > 0 and not is_sno and not is_hosted_control_plane
mhc_usable = [
    item for item in machinehealthchecks
    if len(((item.get("spec") or {}).get("unhealthyConditions") or [])) > 0
]
worker_machineset_names = [item["name"] for item in worker_machinesets if item.get("name")]
covered_worker_machinesets_by_mhc = set()
for mhc in mhc_usable:
    match_labels = selector_match_labels(mhc)
    match_expressions = selector_match_expressions(mhc)
    for machineset in worker_machinesets:
        if labels_match_selector(machineset["labels"], match_labels, match_expressions):
            covered_worker_machinesets_by_mhc.add(machineset["name"])
mhc_present = len(machinehealthchecks) > 0
mhc_healthy = bool(
    not mhc_expected
    or (
        len(worker_machinesets) > 0
        and len(mhc_usable) > 0
        and len(covered_worker_machinesets_by_mhc) == len(worker_machinesets)
    )
)
add_check(
    "Worker machine remediation",
    cap_status_for_presence("machine_health_check_remediation", mhc_present or not mhc_expected, mhc_healthy),
    (
        f"platform={platform} worker_machinesets={len(worker_machinesets)} "
        f"worker_machineset_names={','.join(worker_machineset_names) or 'none'} "
        f"machinehealthchecks={len(machinehealthchecks)} usable_machinehealthchecks={len(mhc_usable)} "
        f"covered_worker_machinesets={len(covered_worker_machinesets_by_mhc)} expected={mhc_expected}"
    ),
    "machine remediation posture for Machine API worker pools",
    level=machine_remediation_level,
)
if (mhc_expected or cap_required("machine_health_check_remediation")) and not mhc_present:
    add_finding(
        "prod-day2-machinehealthcheck-missing",
        (
            "no MachineHealthCheck resources were found for Machine API-managed worker pools "
            "where worker auto-remediation is expected"
        ),
        severity=cap_failure_severity("machine_health_check_remediation"),
        source="machine remediation posture for Machine API worker pools",
    )
elif (mhc_expected or cap_required("machine_health_check_remediation")) and not mhc_healthy:
    add_finding(
        "prod-day2-machinehealthcheck-coverage-incomplete",
        (
            "MachineHealthCheck coverage is incomplete for Machine API-managed worker pools: "
            f"usableMachineHealthChecks={len(mhc_usable)}, "
            f"coveredWorkerMachineSets={len(covered_worker_machinesets_by_mhc)}/{len(worker_machinesets)}"
        ),
        severity=cap_failure_severity("machine_health_check_remediation"),
        source="machine remediation posture for Machine API worker pools",
    )

autoscaler_expected = (
    hcp_management_autoscaling_evidence
    if is_hosted_control_plane
    else ((public_cloud or install_model == "ipi") and len(worker_machinesets) > 0 and not is_sno and not is_hosted_control_plane)
)
usable_machineautoscalers = [
    item for item in machineautoscalers
    if int((item.get("spec") or {}).get("maxReplicas") or 0) > 0
]
covered_worker_machinesets_by_autoscaler = set()
for autoscaler in usable_machineautoscalers:
    match_labels = selector_match_labels(autoscaler)
    match_expressions = selector_match_expressions(autoscaler)
    for machineset in worker_machinesets:
        if labels_match_selector(machineset["labels"], match_labels, match_expressions):
            covered_worker_machinesets_by_autoscaler.add(machineset["name"])
autoscaler_present = hcp_autoscaling_present if is_hosted_control_plane else (len(clusterautoscalers) > 0 or len(machineautoscalers) > 0)
autoscaler_healthy = bool(
    hcp_autoscaling_present
    if is_hosted_control_plane
    else (
        not autoscaler_expected
        or (
            len(clusterautoscalers) > 0
            and len(usable_machineautoscalers) > 0
            and len(covered_worker_machinesets_by_autoscaler) == len(worker_machinesets)
        )
    )
)
kubeletconfig_targeted = [
    item for item in kubeletconfigs
    if len((((item.get("spec") or {}).get("machineConfigPoolSelector")) or {})) > 0
]
kubeletconfig_density_tuned = [
    item for item in kubeletconfigs
    if any(
        key in (((item.get("spec") or {}).get("kubeletConfig")) or {})
        for key in ("maxPods", "podsPerCore")
    )
]
kubeletconfig_reservation_tuned = [
    item for item in kubeletconfigs
    if any(
        key in (((item.get("spec") or {}).get("kubeletConfig")) or {})
        for key in ("systemReserved", "kubeReserved", "reservedSystemCPUs")
    )
]
kubeletconfig_eviction_tuned = [
    item for item in kubeletconfigs
    if any(
        key in (((item.get("spec") or {}).get("kubeletConfig")) or {})
        for key in ("evictionHard", "evictionSoft", "evictionSoftGracePeriod", "evictionPressureTransitionPeriod")
    )
]
kubeletconfig_runtime_policy_tuned = [
    item for item in kubeletconfigs
    if any(
        key in (((item.get("spec") or {}).get("kubeletConfig")) or {})
        for key in ("cpuManagerPolicy", "topologyManagerPolicy", "memoryManagerPolicy")
    )
]
kubelet_configuration_governance_present = len(kubeletconfigs) > 0
kubelet_configuration_governance_healthy = bool(
    kubelet_configuration_governance_present
    and len(kubeletconfig_targeted) > 0
    and (
        len(kubeletconfig_density_tuned) > 0
        or len(kubeletconfig_reservation_tuned) > 0
        or len(kubeletconfig_eviction_tuned) > 0
        or len(kubeletconfig_runtime_policy_tuned) > 0
    )
)
add_check(
    "Cluster autoscaler",
    cap_status_for_presence(
        "cluster_autoscaler_configuration",
        autoscaler_present or not autoscaler_expected,
        autoscaler_healthy,
    ),
    (
        f"classification={cluster_classification_label or deployment_type or 'unknown'} "
        f"serviceModel={service_model or 'unknown'} publicCloud={public_cloud} "
        f"installModel={install_model or 'unknown'} installModelConfidence={install_model_confidence or 'unknown'} "
        f"worker_machinesets={len(worker_machinesets)} hostedclusters={len(hostedclusters)} nodepools={len(nodepools)} "
        f"hcpHostedClusterAutoscaling={hostedcluster_autoscaling_present} hcpNodePoolAutoscaling={nodepool_autoscaling_present} "
        f"expected={autoscaler_expected} clusterautoscalers={len(clusterautoscalers)} "
        f"machineautoscalers={len(machineautoscalers)} usable_machineautoscalers={len(usable_machineautoscalers)} "
        f"covered_worker_machinesets={len(covered_worker_machinesets_by_autoscaler)}"
    ),
    "cluster autoscaler guidance for Machine API worker pools",
    level=autoscaler_level,
)
add_check(
    "Kubelet configuration governance",
    cap_status_for_presence(
        "kubelet_configuration_governance",
        kubelet_configuration_governance_present,
        kubelet_configuration_governance_healthy,
    ),
    (
        f"kubeletConfigs={len(kubeletconfigs)} "
        f"targetedConfigs={len(kubeletconfig_targeted)} "
        f"densityTuned={len(kubeletconfig_density_tuned)} "
        f"reservationTuned={len(kubeletconfig_reservation_tuned)} "
        f"evictionTuned={len(kubeletconfig_eviction_tuned)} "
        f"runtimePolicyTuned={len(kubeletconfig_runtime_policy_tuned)}"
    ),
    "KubeletConfig resource inventory",
    level=cap_level("kubelet_configuration_governance", "informational"),
)
if (autoscaler_expected or cap_required("cluster_autoscaler_configuration")) and not autoscaler_present:
    add_finding(
        "prod-day2-cluster-autoscaler-missing",
        (
            "no hosted control plane autoscaling configuration was found in HostedCluster or NodePool resources"
            if is_hosted_control_plane
            else
            "no ClusterAutoscaler resource was found for Machine API-managed worker pools "
            "on a public-cloud or IPI-classified cluster where worker autoscaling is expected"
        ),
        severity=cap_failure_severity("cluster_autoscaler_configuration"),
        source="cluster autoscaler guidance for Machine API worker pools",
    )
elif (autoscaler_expected or cap_required("cluster_autoscaler_configuration")) and not autoscaler_healthy:
    add_finding(
        "prod-day2-cluster-autoscaler-missing",
        (
            "worker autoscaling coverage is incomplete: "
            f"clusterAutoscalers={len(clusterautoscalers)}, "
            f"usableMachineAutoscalers={len(usable_machineautoscalers)}, "
            f"coveredWorkerMachineSets={len(covered_worker_machinesets_by_autoscaler)}/{len(worker_machinesets)}"
        ),
        severity=cap_failure_severity("cluster_autoscaler_configuration"),
        source="cluster autoscaler guidance for Machine API worker pools",
    )
if cap_required("kubelet_configuration_governance") and not kubelet_configuration_governance_present:
    add_finding(
        "prod-day2-kubelet-configuration-governance-missing",
        "no KubeletConfig resource footprint was detected for explicit kubelet tuning governance",
        severity=cap_failure_severity("kubelet_configuration_governance"),
        source="KubeletConfig resource inventory",
    )
elif cap_required("kubelet_configuration_governance") and not kubelet_configuration_governance_healthy:
    add_finding(
        "prod-day2-kubelet-configuration-governance-missing",
        "KubeletConfig resources were detected, but no targeted pod-density, reservation, eviction, or runtime-policy tuning signal was found",
        severity=cap_failure_severity("kubelet_configuration_governance"),
        source="KubeletConfig resource inventory",
    )

image_policy_clean = len(data.get("image_registry_findings") or []) == 0
add_check(
    "Registry governance baseline",
    cap_status_for_presence("image_registry_policy_governance", True, image_policy_clean),
    (
        f"image_registry_findings={len(data.get('image_registry_findings') or [])} "
        f"issues={','.join(sorted({str(item.get('issue') or '') for item in (data.get('image_registry_findings') or []) if str(item.get('issue') or '')})) or 'none'}"
    ),
    "registry governance guidance",
    level=cap_level("image_registry_policy_governance", "informational" if is_sno else "recommended"),
)
if cap_required("image_registry_policy_governance") and not image_policy_clean:
    add_finding(
        "prod-day2-image-registry-policy-governance-missing",
        (
            "image registry governance findings require review: "
            + "; ".join(
                sorted(
                    {
                        str(item.get("detail") or "").strip()
                        for item in (data.get("image_registry_findings") or [])
                        if str(item.get("detail") or "").strip()
                    }
                )
            )
        ),
        severity=cap_failure_severity("image_registry_policy_governance"),
        source="registry governance guidance",
    )

add_check(
    "Trusted image admission policy",
    cap_status_for_presence(
        "image_signature_and_admission_policy",
        image_signature_and_admission_policy_present,
        image_signature_and_admission_policy_healthy,
    ),
    (
        f"admissionPolicyEnginePresent={admission_policy_engine_present} "
        f"allowedRegistriesForImport={len(allowed_imports)} "
        f"registryFilterPolicyPresent={restricted_registry_sources} "
        f"imageAdmissionPolicyResources={len(image_admission_policy_resources)} "
        f"activeTrustedImagePolicy={active_trusted_image_policy_present} "
        f"insecureRegistries={len(insecure_registries)}"
    ),
    "trusted image policy and admission guardrail inventory",
    level=cap_level("image_signature_and_admission_policy", "recommended"),
    scored=False,
)
if cap_required("image_signature_and_admission_policy") and not image_signature_and_admission_policy_present:
    add_finding(
        "prod-day2-image-signature-and-admission-policy-missing",
        "no active trusted-image policy signal was detected; policy engine namespaces or CRDs alone are not treated as admission enforcement",
        severity=cap_failure_severity("image_signature_and_admission_policy"),
        source="trusted image policy and admission guardrail inventory",
    )
elif cap_required("image_signature_and_admission_policy") and not image_signature_and_admission_policy_healthy:
    add_finding(
        "prod-day2-image-signature-and-admission-policy-insecure-registries",
        (
            "trusted-image policy is incomplete because insecure registries are configured: "
            + ", ".join(insecure_registries)
        ),
        severity=cap_failure_severity("image_signature_and_admission_policy"),
        source="trusted image policy and admission guardrail inventory",
    )

add_check(
    "Cluster image mirror configuration",
    cap_status_for_presence(
        "cluster_image_mirror_configuration",
        cluster_image_mirror_configuration_present,
        (len(local_mirror_targets) > 0 and not deprecated_icsp_only),
    ),
    (
        f"imagedigestmirrorsets={len(imagedigestmirrorsets)} "
        f"imagetagmirrorsets={len(imagetagmirrorsets)} "
        f"imagecontentsourcepolicies={len(imagecontentsourcepolicies)} "
        f"localMirrorTargets={len(local_mirror_targets)} "
        f"deprecatedIcspOnly={deprecated_icsp_only} "
        f"registry_sources_policy={restricted_registry_sources}"
    ),
    "OpenShift image mirror configuration",
    level=cap_level("cluster_image_mirror_configuration", "informational"),
    scored=False,
)
if not cluster_image_mirror_configuration_present and cap_required("cluster_image_mirror_configuration"):
    add_finding(
        "prod-day2-cluster-image-mirror-configuration-missing",
        "no ImageDigestMirrorSet, ImageTagMirrorSet, or ImageContentSourcePolicy resources were found",
        severity=cap_failure_severity("cluster_image_mirror_configuration"),
        source="OpenShift image mirror configuration",
    )
elif cap_required("cluster_image_mirror_configuration") and len(local_mirror_targets) == 0:
    add_finding(
        "prod-day2-cluster-image-mirror-configuration-targets-missing",
        "image mirror resources were found but no non-public mirror targets were derived from ImageDigestMirrorSet, ImageTagMirrorSet, or ImageContentSourcePolicy resources",
        severity=cap_failure_severity("cluster_image_mirror_configuration"),
        source="OpenShift image mirror configuration",
    )
elif cap_required("cluster_image_mirror_configuration") and deprecated_icsp_only:
    add_finding(
        "prod-day2-cluster-image-mirror-configuration-legacy-icsp-only",
        "cluster image mirroring relies only on deprecated ImageContentSourcePolicy resources; migrate to ImageDigestMirrorSet and ImageTagMirrorSet",
        severity=cap_failure_severity("cluster_image_mirror_configuration"),
        source="OpenShift image mirror configuration",
    )

add_check(
    "Disconnected installation image sources",
    cap_status_for_presence("disconnected_cluster_image_sources", disconnected_cluster_image_sources_present, disconnected_cluster_image_sources_healthy),
    f"mirror_resources={mirror_resource_count} local_mirror_targets={len(local_mirror_targets)} release_image_mirror_configured={release_image_mirror_configured} desired_release_image_mirrored={release_image_mirrored} non_public_catalogsources={disconnected_catalog_count} non_public_clustercatalogs={disconnected_clustercatalog_count} updateservices={len(updateservices)} deprecated_icsp_only={deprecated_icsp_only}",
    "OpenShift disconnected installation mirror inventory",
    level=cap_level("disconnected_cluster_image_sources", "informational"),
    scored=False,
)
if cap_required("disconnected_cluster_image_sources") and mirror_resource_count == 0:
    add_finding(
        "prod-day2-disconnected-installation-evidence-missing",
        "no ImageDigestMirrorSet, ImageTagMirrorSet, or ImageContentSourcePolicy resources were found for disconnected image mirroring",
        severity=cap_failure_severity("disconnected_cluster_image_sources"),
        source="OpenShift disconnected installation mirror inventory",
    )
if cap_required("disconnected_cluster_image_sources") and not release_image_mirrored:
    add_finding(
        "prod-day2-disconnected-release-image-not-mirrored",
        "ClusterVersion desired release image still points to a public registry and no release-payload mirror mapping was found for disconnected operation",
        severity=cap_failure_severity("disconnected_cluster_image_sources"),
        source="OpenShift disconnected installation mirror inventory",
    )
if cap_required("disconnected_cluster_image_sources") and not disconnected_operator_sources_ready:
    add_finding(
        "prod-day2-disconnected-operator-catalog-missing",
        "subscriptions are present but no non-public CatalogSource or ClusterCatalog image source was found for disconnected operator delivery",
        severity=cap_failure_severity("disconnected_cluster_image_sources"),
        source="OpenShift disconnected installation mirror inventory",
    )
if deprecated_icsp_only:
    add_finding(
        "prod-day2-disconnected-legacy-icsp-only",
        "repository mirroring relies only on deprecated ImageContentSourcePolicy resources; migrate to ImageDigestMirrorSet and ImageTagMirrorSet for new disconnected configurations",
        severity="info" if not cap_required("disconnected_cluster_image_sources") else "warning",
        source="OpenShift disconnected installation mirror inventory",
    )

add_check(
    "OVN-Kubernetes network context",
    ("OK" if ovn_network else ("WARN" if cap_required("ovn_ipsec_encryption") else "INFO")),
    f"network.operator.openshift.io/cluster.status.networkType={network_type} ovnNetwork={ovn_network}",
    "OVN-Kubernetes IPsec configuration",
    level=cap_level("ovn_ipsec_encryption", "informational"),
    scored=False,
)
add_check(
    "OVN IPsec configuration presence",
    ("OK" if ipsec_config_present else ("WARN" if (ovn_network or cap_required("ovn_ipsec_encryption")) else "INFO")),
    "network.operator.openshift.io/cluster.spec.defaultNetwork.ovnKubernetesConfig.ipsecConfig present="
    + str(ipsec_config_present),
    "OVN-Kubernetes IPsec configuration",
    level=cap_level("ovn_ipsec_encryption", "informational"),
    scored=False,
)
add_check(
    "OVN IPsec pod-to-pod mode",
    ("OK" if ovn_ipsec_encryption else ("WARN" if (ovn_network or cap_required("ovn_ipsec_encryption")) else "INFO")),
    "network.operator.openshift.io/cluster.spec.defaultNetwork.ovnKubernetesConfig.ipsecConfig.mode="
    + str(ipsec_mode),
    "OVN-Kubernetes IPsec configuration",
    level=cap_level("ovn_ipsec_encryption", "informational"),
    scored=False,
)
if not ovn_ipsec_encryption and cap_required("ovn_ipsec_encryption"):
    ipsec_missing_detail = (
        f"networkType={network_type} does not use OVNKubernetes"
        if not ovn_network
        else (
            f"OVN-Kubernetes IPsec is configured for external traffic only (mode={ipsec_mode}); pod-to-pod IPsec requires mode=Full."
            if ovn_ipsec_external_only
            else (
                "network.operator.openshift.io/cluster.spec.defaultNetwork."
                f"ovnKubernetesConfig.ipsecConfig is missing or disabled (mode={ipsec_mode})"
            )
        )
    )
    add_finding(
        "prod-day2-ipsec-not-enabled",
        "OVN-Kubernetes pod-to-pod IPsec is not fully configured: " + ipsec_missing_detail,
        severity=cap_failure_severity("ovn_ipsec_encryption"),
        source="OVN-Kubernetes IPsec configuration",
        recommended_action=(
            "Use OVN-Kubernetes and configure "
            "network.operator.openshift.io/cluster.spec.defaultNetwork."
            "ovnKubernetesConfig.ipsecConfig.mode=Full when inter-node "
            "pod-network encryption is required."
        ),
    )

add_check(
    "APIServer etcd encryption configuration",
    ("OK" if etcd_encryption else ("WARN" if cap_required("etcd_encryption") else "INFO")),
    "apiserver.config.openshift.io/cluster.spec.encryption.type=" + etcd_encryption_type,
    "OpenShift APIServer etcd encryption configuration",
    level=cap_level("etcd_encryption", "informational"),
    scored=False,
)
add_check(
    "etcd encryption rollout evidence",
    (
        "OK"
        if (etcd_encryption and len(etcd_encryption_reported_components) > 0)
        else ("WARN" if etcd_encryption else "INFO")
    ),
    (
        f"reportedComponents={len(etcd_encryption_reported_components)}/{len(etcd_encryption_conditions)}"
    ),
    "OpenShift APIServer etcd encryption configuration",
    level=cap_level("etcd_encryption", "informational"),
    scored=False,
)
add_check(
    "etcd encryption rollout completion",
    (
        "OK"
        if etcd_encryption_complete
        else ("WARN" if etcd_encryption else "INFO")
    ),
    (
        f"completedComponents={len(etcd_encryption_completed_components)}/{len(etcd_encryption_conditions)}"
    ),
    "OpenShift APIServer etcd encryption configuration",
    level=cap_level("etcd_encryption", "informational"),
    scored=False,
)
if not etcd_encryption and cap_required("etcd_encryption"):
    add_finding(
        "prod-day2-etcd-encryption-not-enabled",
        "apiserver.config.openshift.io/cluster.spec.encryption.type is not set to aescbc or aesgcm",
        severity=cap_failure_severity("etcd_encryption"),
        source="OpenShift APIServer etcd encryption configuration",
    )
elif etcd_encryption and not etcd_encryption_complete and cap_required("etcd_encryption"):
    if len(etcd_encryption_reported_components) == 0:
        detail = (
            "etcd encryption is configured, but no rollout status was reported by "
            "openshift-apiserver, kube-apiserver, or authentication resources"
        )
    else:
        detail = (
            "etcd encryption is configured but rollout is not completed across the reported API server components; "
            f"incomplete components: {', '.join(format_etcd_encryption_component_names(etcd_encryption_missing_components)) or 'none'}"
        )
    add_finding(
        "prod-day2-etcd-encryption-rollout-incomplete",
        detail,
        severity=cap_failure_severity("etcd_encryption"),
        source="OpenShift APIServer etcd encryption configuration",
    )

add_check(
    "Cluster proxy configuration",
    cap_status_for_presence("cluster_proxy_configuration", cluster_proxy_configured, cluster_proxy_healthy),
    (
        f"httpProxy={bool(proxy_spec.get('httpProxy'))} "
        f"httpsProxy={bool(proxy_spec.get('httpsProxy'))} "
        f"noProxyEntries={len(proxy_no_proxy_entries)} "
        f"missingInternalNoProxy={','.join(proxy_missing_internal_no_proxy_entries) or 'none'}"
    ),
    "OpenShift cluster-wide Proxy configuration",
    level=cap_level("cluster_proxy_configuration", "informational"),
    scored=False,
)
if not cluster_proxy_configured and cap_required("cluster_proxy_configuration"):
    add_finding(
        "prod-day2-proxy-configuration-missing",
        "proxy.config.openshift.io/cluster.spec.httpProxy and proxy.config.openshift.io/cluster.spec.httpsProxy are both empty",
        severity=cap_failure_severity("cluster_proxy_configuration"),
        source="OpenShift cluster-wide Proxy configuration",
    )
elif cap_required("cluster_proxy_configuration") and len(proxy_missing_internal_no_proxy_entries) > 0:
    add_finding(
        "prod-day2-proxy-no-proxy-incomplete",
        "proxy.config.openshift.io/cluster is configured but noProxy is missing required internal entries: " + ", ".join(proxy_missing_internal_no_proxy_entries),
        severity=cap_failure_severity("cluster_proxy_configuration"),
        source="OpenShift cluster-wide Proxy configuration",
    )

add_check(
    "Custom trust bundle configuration",
    cap_status_for_presence("custom_ca_trust_bundle", custom_ca_configured),
    f"proxy_trustedCA={((proxy_spec.get('trustedCA') or {}).get('name') or 'none')} image_additionalTrustedCA={((image_spec.get('additionalTrustedCA') or {}).get('name') or 'none')}",
    "OpenShift Proxy and Image trust configuration",
    level=cap_level("custom_ca_trust_bundle", "informational"),
    scored=False,
)
if not custom_ca_configured and cap_required("custom_ca_trust_bundle"):
    add_finding(
        "prod-day2-custom-ca-trust-missing",
        "neither proxy.config.openshift.io/cluster.spec.trustedCA nor image.config.openshift.io/cluster.spec.additionalTrustedCA references a ConfigMap",
        severity=cap_failure_severity("custom_ca_trust_bundle"),
        source="OpenShift Proxy and Image trust configuration",
    )

default_ingresscontroller_issue_count = len([
    item for item in ingresscontroller_issues
    if str(item.get("component") or "").strip() == "ingresscontroller/default"
])
nondefault_ingresscontroller_count = len([
    item for item in ingresscontroller_summary
    if str(item.get("name") or "").strip() and str(item.get("name") or "").strip() != "default"
])
ingress_topology_signals = []
for item in ingresscontrollers:
    metadata = item.get("metadata") or {}
    spec = item.get("spec") or {}
    node_placement = spec.get("nodePlacement") or {}
    if (
        str(metadata.get("name") or "").strip() != "default"
        or bool(spec.get("routeSelector"))
        or bool(spec.get("namespaceSelector"))
        or bool(spec.get("domain"))
        or bool(node_placement.get("nodeSelector"))
        or bool(node_placement.get("tolerations"))
    ):
        ingress_topology_signals.append(item)
ingress_topology_present = bool(ingresscontroller_summary or ingresscontrollers)
ingress_topology_configured = bool(
    nondefault_ingresscontroller_count > 0
    or len(ingress_topology_signals) > 0
)
ingress_topology_healthy = bool(
    ingress_topology_configured
    and len(ingresscontroller_issues) == 0
)
add_check(
    "Ingress controller topology and sharding",
    cap_status_for_presence(
        "ingress_controller_topology_and_sharding",
        ingress_topology_present,
        ingress_topology_healthy,
    ),
    (
        f"ingresscontrollers={len(ingresscontroller_summary)} "
        f"nondefaultIngresscontrollers={nondefault_ingresscontroller_count} "
        f"topologySignals={len(ingress_topology_signals)} "
        f"defaultIngresscontrollerIssues={default_ingresscontroller_issue_count} "
        f"totalIngresscontrollerIssues={len(ingresscontroller_issues)}"
    ),
    "OpenShift ingress controller topology and sharding guidance",
    level=cap_level("ingress_controller_topology_and_sharding", "informational"),
    scored=False,
)
if cap_required("ingress_controller_topology_and_sharding") and not ingress_topology_configured:
    add_finding(
        "prod-day2-ingress-controller-topology-and-sharding-missing",
        "only the default ingress controller footprint was detected and no dedicated ingress topology or sharding signals were found",
        severity=cap_failure_severity("ingress_controller_topology_and_sharding"),
        source="OpenShift ingress controller topology and sharding guidance",
    )
elif cap_required("ingress_controller_topology_and_sharding") and ingress_topology_configured and not ingress_topology_healthy:
    add_finding(
        "prod-day2-ingress-controller-topology-and-sharding-unhealthy",
        "ingress topology or sharding signals were detected, but ingress controller health findings still require review",
        severity=cap_failure_severity("ingress_controller_topology_and_sharding"),
        source="OpenShift ingress controller topology and sharding guidance",
    )

add_check(
    "Application external private registry usage",
    cap_status_for_presence(
        "workloads_using_external_private_registries",
        workloads_using_external_private_registries_present,
        workloads_using_external_private_registries_present,
    ),
    (
        f"external_registries={len(external_image_registries)} "
        f"external_registry_workloads={external_private_registry_workload_count} "
        f"external_registry_workloads_with_imagePullSecrets={external_private_registry_workloads_with_pull_secret} "
        f"external_registry_workloads_with_serviceAccountPullSecrets={external_private_registry_workloads_with_serviceaccount_pull_secret} "
        f"credentialed_public_registries={len(credentialed_public_image_registries)} "
        f"workloads_with_imagePullSecrets={workloads_with_pull_secret} "
        f"docker_registry_secrets={dockerconfig_secret_count} "
        f"serviceaccount_pull_secrets={serviceaccount_pull_secret_count}"
    ),
    "Kubernetes imagePullSecrets and workload image inventory",
    level=cap_level("workloads_using_external_private_registries", "informational"),
    scored=False,
)
if cap_required("workloads_using_external_private_registries") and not (
    external_private_registry_workloads_present or len(credentialed_public_image_registries) > 0
):
    add_finding(
        "prod-day2-external-private-registry-missing",
        "no workload evidence showed external private registry usage or credentialed public-registry pulls",
        severity=cap_failure_severity("workloads_using_external_private_registries"),
        source="Kubernetes imagePullSecrets and workload image inventory",
    )
elif cap_required("workloads_using_external_private_registries") and not workloads_using_external_private_registries_present:
    add_finding(
        "prod-day2-external-private-registry-missing",
        (
            "external registry workloads were detected but pull-credential evidence is incomplete: "
            f"external_registries={len(external_image_registries)}, "
            f"external_registry_workloads={external_private_registry_workload_count}, "
            f"external_registry_workloads_with_imagePullSecrets={external_private_registry_workloads_with_pull_secret}, "
            f"external_registry_workloads_with_serviceAccountPullSecrets={external_private_registry_workloads_with_serviceaccount_pull_secret}"
        ),
        severity=cap_failure_severity("workloads_using_external_private_registries"),
        source="Kubernetes imagePullSecrets and workload image inventory",
    )

add_check(
    "Cluster-hosted CI/CD runners",
    cap_status_for_presence("cluster_hosted_cicd_runners", cicd_runner_present),
    f"runner_keywords_detected={cicd_runner_present} workloads_scanned={len(all_workloads)}",
    "workload inventory for GitLab, Jenkins, Azure DevOps, GitHub Actions, and Tekton runner agents",
    level=cap_level("cluster_hosted_cicd_runners", "informational"),
    scored=False,
)
if not cicd_runner_present and cap_required("cluster_hosted_cicd_runners"):
    add_finding(
        "prod-day2-cicd-runners-missing",
        "no cluster-hosted CI/CD runner or agent workload footprint was detected",
        severity=cap_failure_severity("cluster_hosted_cicd_runners"),
        source="workload inventory for GitLab, Jenkins, Azure DevOps, GitHub Actions, and Tekton runner agents",
    )

workload_vulnerability_scanner_vendor_rows = [
    {
        "label": "RHACS vulnerability scanning",
        "context_present": advanced_cluster_security_context_present,
        "configuration_present": False,
        "workload_present": acs_workload_present,
        "source": "RHACS operator and secured-cluster inventory",
        "detail": (
            f"subscription_present={acs_operator_subscription_present} "
            f"namespace_present={acs_namespace_present} "
            f"crd_present={acs_crd_present} "
            f"configuration_present=False "
            f"workload_present={acs_workload_present}; "
            "required Central or SecuredCluster custom resource configuration could not be confirmed from current live evidence"
        ),
    },
    {
        "label": "Qualys workload scanning",
        "context_present": qualys_scanning_agents_context_present,
        "configuration_present": qualys_required_deployment_configuration_present,
        "workload_present": qualys_workload_present,
        "source": "Qualys agent inventory",
        "detail": (
            f"subscription_present={qualys_subscription_present} "
            f"namespace_present={qualys_namespace_present} "
            f"crd_present={qualys_crd_present} "
            f"configuration_present={qualys_required_deployment_configuration_present} "
            f"workload_present={qualys_workload_present}; "
            "required deployment configuration is verified from documented Qualys OpenShift sensor signals when present"
        ),
    },
    {
        "label": "Prisma Cloud Compute or Twistlock vulnerability scanning",
        "context_present": prisma_twistlock_context_present,
        "configuration_present": False,
        "workload_present": prisma_workload_present,
        "source": "Prisma Cloud Compute inventory",
        "detail": (
            f"subscription_present={prisma_subscription_present} "
            f"namespace_present={prisma_namespace_present} "
            f"crd_present={prisma_crd_present} "
            f"configuration_present=False "
            f"workload_present={prisma_workload_present}; "
            "required Prisma Cloud Compute custom resource configuration could not be confirmed from current live evidence"
        ),
    },
    {
        "label": "Aqua workload scanning",
        "context_present": aqua_platform_context_present,
        "configuration_present": False,
        "workload_present": aqua_workload_present,
        "source": "Aqua operator and enforcer inventory",
        "detail": (
            f"subscription_present={aqua_subscription_present} "
            f"namespace_present={aqua_namespace_present} "
            f"crd_present={aqua_crd_present} "
            f"configuration_present=False "
            f"workload_present={aqua_workload_present}; "
            "required Aqua custom resource configuration could not be confirmed from current live evidence"
        ),
    },
    {
        "label": "Trivy Operator vulnerability scanning",
        "context_present": trivy_operator_context_present,
        "configuration_present": False,
        "workload_present": trivy_workload_present,
        "source": "Trivy operator inventory",
        "detail": (
            f"subscription_present={trivy_subscription_present} "
            f"namespace_present={trivy_namespace_present} "
            f"crd_present={trivy_crd_present} "
            f"configuration_present=False "
            f"workload_present={trivy_workload_present}; "
            "no first-class Trivy custom resource configuration is modeled in current live evidence; active coverage is confirmed from operator-managed scanner workloads"
        ),
    },
]
workload_vulnerability_scanner_present_vendors = [
    row["label"] for row in workload_vulnerability_scanner_vendor_rows if row["workload_present"]
]
workload_vulnerability_scanner_context_only_vendors = [
    row["label"] for row in workload_vulnerability_scanner_vendor_rows
    if row["context_present"] and not row["workload_present"]
]
for row in workload_vulnerability_scanner_vendor_rows:
    add_check(
        row["label"],
        (
            "OK"
            if row["workload_present"]
            else ("WARN" if (row["context_present"] or cap_required("workload_vulnerability_scanning")) else "INFO")
        ),
        row["detail"],
        row["source"],
        level=cap_level("workload_vulnerability_scanning", "informational"),
        scored=False,
        capability_key="workload_vulnerability_scanning",
    )
if not workload_scanner_present and cap_required("workload_vulnerability_scanning"):
    add_finding(
        "prod-day2-workload-vulnerability-scanner-missing",
        (
            "no active RHACS, Qualys, Prisma Cloud Compute, Aqua, or Trivy workload scanner footprint was detected"
            if not workload_vulnerability_scanner_context_only_vendors
            else (
                "scanner context was detected for: "
                + ", ".join(workload_vulnerability_scanner_context_only_vendors)
                + "; no active scanner workload footprint was confirmed for those products"
            )
        ),
        severity=cap_failure_severity("workload_vulnerability_scanning"),
        source="live workload scanner operator, agent, and report inventory",
        recommended_action=(
            "Deploy or document an approved workload vulnerability scanning product such as RHACS, Qualys, Prisma Cloud Compute, Aqua, or Trivy Operator, then confirm active scanner workload rollout."
            if not workload_vulnerability_scanner_context_only_vendors
            else (
                "Complete the required product configuration and confirm managed scanner workloads for: "
                + ", ".join(workload_vulnerability_scanner_context_only_vendors)
                + "."
            )
        ),
    )

namespaces_missing_networkpolicy = sorted(user_namespace_names - namespaces_with_default_deny_networkpolicy)
network_policy_baseline_present = len(namespaces_with_default_deny_networkpolicy) > 0
network_policy_baseline_healthy = len(user_namespace_names) == 0 or len(namespaces_missing_networkpolicy) == 0
namespaces_missing_egress_controls = sorted(user_namespace_names - namespaces_with_egress_controls)
egress_control_present = len(namespaces_with_egress_controls) > 0
egress_control_healthy = len(user_namespace_names) == 0 or len(namespaces_missing_egress_controls) == 0
quota_governance_present = len(namespaces_with_resourcequota) > 0
namespaces_missing_resourcequota = sorted(user_namespace_names - namespaces_with_resourcequota)
quota_governance_healthy = len(user_namespace_names) == 0 or len(namespaces_missing_resourcequota) == 0
multi_tenant_namespace_governance_present = bool(
    bool(self_provisioners)
    or project_request_message_configured
    or namespace_onboarding_controls_present
    or len(namespaces_with_all_namespace_governance_guardrails) > 0
)
multi_tenant_namespace_governance_healthy = bool(
    namespace_self_provisioning_governed
    and namespace_onboarding_controls_present
    and network_policy_baseline_healthy
    and egress_control_healthy
    and quota_governance_healthy
    and (len(user_namespace_names) == 0 or len(user_namespace_names - namespaces_with_limitrange) == 0)
)
add_check(
    "Namespace network policy baseline",
    cap_status_for_presence("namespace_network_policy_baseline", network_policy_baseline_present, network_policy_baseline_healthy),
    (
        f"user_namespaces={len(user_namespace_names)} "
        f"namespaces_with_default_deny_networkpolicy={len(namespaces_with_default_deny_networkpolicy)} "
        f"namespaces_with_any_networkpolicy={len(namespaces_with_networkpolicy)} "
        f"missing_namespaces={len(namespaces_missing_networkpolicy)}"
    ),
    "namespace default-deny NetworkPolicy inventory for user namespaces",
    level=cap_level("namespace_network_policy_baseline", namespace_guardrails_level),
)
if cap_required("namespace_network_policy_baseline") and not network_policy_baseline_present:
    add_finding(
        "prod-day2-namespace-network-policy-baseline-missing",
        "no namespace-wide default-deny NetworkPolicy baseline was found in user namespaces",
        severity=cap_failure_severity("namespace_network_policy_baseline"),
        source="namespace default-deny NetworkPolicy inventory for user namespaces",
    )
elif cap_required("namespace_network_policy_baseline") and not network_policy_baseline_healthy:
    add_finding(
        "prod-day2-namespace-network-policy-baseline-missing",
        (
            "namespace-wide default-deny NetworkPolicy baseline coverage is incomplete for user namespaces: "
            f"missing={', '.join(namespaces_missing_networkpolicy[:15])}"
            + (" ..." if len(namespaces_missing_networkpolicy) > 15 else "")
        ),
        severity=cap_failure_severity("namespace_network_policy_baseline"),
        source="namespace default-deny NetworkPolicy inventory for user namespaces",
    )
add_check(
    "Namespace egress controls",
    cap_status_for_presence("namespace_egress_controls", egress_control_present, egress_control_healthy),
    (
        f"user_namespaces={len(user_namespace_names)} "
        f"baseline_egress_networkpolicy_namespaces={len(namespaces_with_baseline_egress_networkpolicy)} "
        f"egressfirewall_namespaces={len(namespaces_with_egressfirewall)} "
        f"missing_namespaces={len(namespaces_missing_egress_controls)}"
    ),
    "namespace baseline egress NetworkPolicy and EgressFirewall inventory for user namespaces",
    level=cap_level("namespace_egress_controls", namespace_guardrails_level),
)
if not egress_control_present and cap_required("namespace_egress_controls"):
    add_finding(
        "prod-day2-namespace-egress-controls-missing",
        "no namespace baseline egress restriction was found in user namespaces from match-all Egress NetworkPolicy or EgressFirewall resources",
        severity=cap_failure_severity("namespace_egress_controls"),
        source="namespace baseline egress NetworkPolicy and EgressFirewall inventory for user namespaces",
    )
elif cap_required("namespace_egress_controls") and not egress_control_healthy:
    add_finding(
        "prod-day2-namespace-egress-controls-missing",
        (
            "namespace baseline egress control coverage is incomplete for user namespaces: "
            f"missing={', '.join(namespaces_missing_egress_controls[:15])}"
            + (" ..." if len(namespaces_missing_egress_controls) > 15 else "")
        ),
        severity=cap_failure_severity("namespace_egress_controls"),
        source="namespace baseline egress NetworkPolicy and EgressFirewall inventory for user namespaces",
    )

platform_app_catalog = [
    {
        "key": "cluster_log_forwarding",
        "capability": "Cluster logging app footprint",
        "level": cap_level("cluster_log_forwarding", telemetry_level),
        "source": "cluster logging inventory",
        "present": bool(clusterlogforwarders or "openshift-logging" in namespace_names),
        "detail": f"clusterlogforwarders={len(clusterlogforwarders)} openshift_logging_namespace={'openshift-logging' in namespace_names}",
        "issue": "prod-day2-platform-cluster-logging-missing",
        "finding": "no cluster logging app footprint was detected from ClusterLogForwarder resources or openshift-logging namespace",
    },
    {
        "key": "external_secrets_operator",
        "capability": "External Secrets Operator app footprint",
        "level": external_secrets_level,
        "source": "external secrets inventory",
        "present": ext_secrets_present,
        "detail": (
            f"stores={ext_secret_store_count} "
            f"externalsecrets={len(externalsecrets)} "
            f"namespace_present={ext_secrets_namespace_present}"
        ),
        "issue": "prod-day2-platform-external-secrets-operator-missing",
        "finding": "no External Secrets Operator namespace, store, or ExternalSecret footprint was detected",
    },
    {
        "key": "application_backup_and_restore_readiness",
        "capability": "Workload backup and restore provider footprint",
        "level": cap_level("application_backup_and_restore_readiness", base_required_level),
        "source": "backup and recovery inventory",
        "present": workload_backup_provider_present,
        "detail": f"oadp_present={oadp_backup_provider_present} velero_present={velero_backup_provider_present} commvault_present={commvault_backup_provider_present} dpas={len(dataprotectionapplications)} backupstoragelocations={len(backupstoragelocations)} schedules={len(schedules)} openshift_adp_namespace={'openshift-adp' in namespace_names}",
        "issue": "prod-day2-workload-backup-provider-missing",
        "finding": "no Commvault, OADP, or upstream Velero workload backup and restore footprint was detected",
    },
    {
        "key": "compliance_requirements_validation",
        "capability": "Compliance validation footprint",
        "level": compliance_level,
        "source": "compliance validation inventory",
        "present": compliance_present,
        "detail": (
            f"suites={int(compliance_operator_summary.get('suite_count') or len(compliancesuites))} "
            f"scans={int(compliance_operator_summary.get('scan_count') or 0)} "
            f"bindings={int(compliance_operator_summary.get('scan_setting_binding_count') or 0)} "
            f"openshift_compliance_namespace={bool(compliance_operator_summary.get('namespace_present'))}"
        ),
        "issue": "prod-day2-platform-compliance-validation-missing",
        "finding": "no compliance validation footprint was detected from standards evidence, Compliance Operator resources, or openshift-compliance namespace",
    },
    {
        "key": "openshift_pipeline_workflows",
        "capability": "OpenShift pipeline workflow footprint",
        "level": pipelines_level,
        "source": "pipeline operator inventory",
        "present": bool("openshift-pipelines-operator-rh" in subscription_packages or "openshift-pipelines" in namespace_names or "openshift-pipelines-operator-bootstrap" in gitops_application_names),
        "detail": f"subscription_present={'openshift-pipelines-operator-rh' in subscription_packages} openshift_pipelines_namespace={'openshift-pipelines' in namespace_names} gitops_app_present={'openshift-pipelines-operator-bootstrap' in gitops_application_names}",
        "issue": "prod-day2-platform-pipelines-operator-missing",
        "finding": "no OpenShift Pipelines operator footprint was detected",
    },
    {
        "key": "openshift_dev_spaces",
        "capability": "OpenShift Dev Spaces footprint",
        "level": cap_level("openshift_dev_spaces", "informational"),
        "source": "OpenShift Dev Spaces operator and workspace inventory",
        "present": openshift_dev_spaces_present,
        "detail": (
            f"subscriptionPresent={openshift_dev_spaces_subscription_present} "
            f"namespacePresent={openshift_dev_spaces_namespace_present} "
            f"contextPresent={openshift_dev_spaces_context_present} "
            f"cheClusterPresent={openshift_dev_spaces_checluster_present} "
            f"devWorkspacePresent={openshift_dev_spaces_devworkspace_present} "
            f"workspaceOperatorConfigPresent={openshift_dev_spaces_workspace_operator_config_present} "
            f"routingPresent={openshift_dev_spaces_routing_present}"
        ),
        "issue": "prod-day2-openshift-dev-spaces-missing",
        "finding": "no OpenShift Dev Spaces CheCluster, DevWorkspace, routing, or operator configuration footprint was detected; operator subscription or namespace context alone is not treated as an active Dev Spaces deployment",
    },
    {
        "key": "cert_manager_operator",
        "capability": "cert-manager operator footprint",
        "level": cert_manager_level,
        "source": "certificate management inventory",
        "present": bool("openshift-cert-manager-operator" in subscription_packages or "cert-manager-operator" in namespace_names or "cert-manager" in namespace_names),
        "detail": f"subscription_present={'openshift-cert-manager-operator' in subscription_packages} cert_manager_operator_namespace={'cert-manager-operator' in namespace_names} cert_manager_namespace={'cert-manager' in namespace_names}",
        "issue": "prod-day2-platform-cert-manager-missing",
        "finding": "no cert-manager operator footprint was detected",
    },
    {
        "key": "openshift_aap",
        "capability": "OpenShift AAP footprint",
        "level": cap_level("openshift_aap", "informational"),
        "source": "Ansible Automation Platform operator and custom resource inventory",
        "present": openshift_aap_present,
        "detail": (
            f"subscription_present={aap_subscription_present} "
            f"namespace_present={aap_namespace_present} "
            f"crd_present={aap_crd_present} "
            f"aap_crs={len(ansibleautomationplatforms)} "
            f"automationcontrollers={len(automationcontrollers)} "
            f"automationhubs={len(automationhubs)} "
            f"edas={len(edas)} "
            f"workload_present={aap_workload_present}"
        ),
        "issue": "prod-day2-openshift-aap-missing",
        "finding": "no Ansible Automation Platform custom resource or AAP-managed workload footprint was detected",
    },
    {
        "key": "openshift_custom_metrics_autoscaler",
        "capability": "OpenShift KEDA custom metrics footprint",
        "level": cap_level("openshift_custom_metrics_autoscaler", "informational"),
        "source": "KEDA controller and custom autoscaling resource inventory",
        "present": openshift_custom_metrics_autoscaler_present,
        "context_present": openshift_custom_metrics_autoscaler_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"subscription_present={keda_subscription_present} "
            f"namespace_present={keda_namespace_present} "
            f"crd_present={keda_crd_present} "
            f"kedacontrollers={len(kedacontrollers)} "
            f"scaledobjects={len(scaledobjects)} "
            f"scaledjobs={len(scaledjobs)} "
            f"triggerauthentications={len(triggerauthentications)} "
            f"clustertriggerauthentications={len(clustertriggerauthentications)} "
            f"workload_present={keda_workload_present}"
        ),
        "issue": "prod-day2-openshift-custom-metrics-autoscaler-missing",
        "finding": "no KedaController, ScaledObject, ScaledJob, trigger authentication, or KEDA-managed workload footprint was detected",
    },
    {
        "key": "openshift_data_foundation",
        "capability": "OpenShift Data Foundation footprint",
        "level": cap_level("openshift_data_foundation", "informational"),
        "source": "ODF and storage resource inventory",
        "present": openshift_data_foundation_present,
        "healthy": openshift_data_foundation_healthy,
        "detail": (
            f"storageclusters={len(storageclusters)} "
            f"cephclusters={len(cephclusters)} "
            f"noobaas={len(noobaas)} "
            f"odf_storageclasses={odf_storageclass_count} "
            f"odf_subscription_present={odf_operator_subscription_present} "
            f"openshift_storage_namespace={odf_namespace_present}"
        ),
        "issue": "prod-day2-openshift-data-foundation-missing",
        "finding": "no OpenShift Data Foundation StorageCluster, CephCluster, NooBaa, or ODF storage-class resource was detected",
        "finding_when_unhealthy": "OpenShift Data Foundation context was detected, but no healthy ODF storage-service footprint was derived from StorageCluster with Ceph/NooBaa backing resources or ODF storage classes",
    },
    {
        "key": "ibm_cloud_pak_business_automation",
        "capability": "IBM Cloud Pak for Business Automation footprint",
        "level": cap_level("ibm_cloud_pak_business_automation", "informational"),
        "source": "IBM Cloud Pak for Business Automation operator and custom resource inventory",
        "present": ibm_cloud_pak_business_automation_present,
        "healthy": ibm_cloud_pak_business_automation_healthy,
        "detail": (
            f"icp4aclusters={len(icp4aclusters)} "
            f"ready_icp4aclusters={len(ready_icp4aclusters)} "
            f"subscription_present={cp4ba_operator_subscription_present} "
            f"namespace_present={cp4ba_namespace_present} "
            f"crd_present={cp4ba_crd_present}"
        ),
        "issue": "prod-day2-ibm-cloud-pak-business-automation-missing",
        "finding": "no IBM Cloud Pak for Business Automation Icp4aCluster custom resource or operator footprint was detected",
        "finding_when_unhealthy": "IBM Cloud Pak for Business Automation resources were detected, but no Icp4aCluster resource reported a ready, available, successful, or completed state",
    },
    {
        "key": "openshift_virtualization",
        "capability": "OpenShift Virtualization footprint",
        "level": cap_level("openshift_virtualization", "informational"),
        "source": "OpenShift Virtualization resource inventory",
        "present": openshift_virtualization_present,
        "healthy": openshift_virtualization_healthy,
        "detail": (
            f"kubevirts={len(kubevirts)} "
            f"hyperconvergeds={len(hyperconvergeds)} "
            f"ready_kubevirts={len(ready_kubevirts)} "
            f"ready_hyperconvergeds={len(ready_hyperconvergeds)} "
            f"ssps={len(ssps)} "
            f"cdis={len(cdis)} "
            f"datavolumes={len(datavolumes)} "
            f"virtualmachines={len(virtualmachines)} "
            f"virtualmachineinstances={len(virtualmachineinstances)} "
            f"subscription_present={virtualization_operator_subscription_present} "
            f"openshift_cnv_namespace={virtualization_namespace_present}"
        ),
        "issue": "prod-day2-openshift-virtualization-missing",
        "finding": "no OpenShift Virtualization KubeVirt, HyperConverged, VM, VMI, or supporting CNV resource was detected",
    },
    {
        "key": "openshift_ai",
        "capability": "OpenShift AI footprint",
        "level": cap_level("openshift_ai", "informational"),
        "source": "OpenShift AI resource inventory",
        "present": openshift_ai_present,
        "healthy": openshift_ai_healthy,
        "detail": (
            f"datascienceclusters={len(datascienceclusters)} "
            f"ready_datascienceclusters={len(ready_datascienceclusters)} "
            f"dscinitializations={len(dscinitializations)} "
            f"ready_dscinitializations={len(ready_dscinitializations)} "
            f"notebooks={len(notebooks)} "
            f"servingruntimes={len(servingruntimes)} "
            f"inferenceservices={len(inferenceservices)} "
            f"modelmeshservings={len(modelmeshservings)} "
            f"acceleratorprofiles={len(acceleratorprofiles)} "
            f"subscription_present={openshift_ai_subscription_present} "
            f"redhat_ods_operator_namespace={openshift_ai_namespace_present}"
        ),
        "issue": "prod-day2-openshift-ai-missing",
        "finding": "no OpenShift AI DataScienceCluster, DSCInitialization, notebook, serving runtime, InferenceService, ModelMesh, or accelerator profile resource was detected",
    },
    {
        "key": "service_mesh_control_plane",
        "capability": "Service mesh control plane footprint",
        "level": cap_level("service_mesh_control_plane", "informational"),
        "source": "OpenShift Service Mesh control plane and membership inventory",
        "present": service_mesh_present,
        "healthy": service_mesh_healthy,
        "context_present": service_mesh_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"servicemeshcontrolplanes={len(servicemeshcontrolplanes)} "
            f"ready_control_planes={len(ready_service_mesh_control_planes)} "
            f"servicemeshmemberrolls={len(servicemeshmemberrolls)} "
            f"servicemeshmembers={len(servicemeshmembers)} "
            f"context_present={service_mesh_context_present} "
            f"subscription_present={service_mesh_subscription_present} "
            f"crd_present={service_mesh_crd_present}"
        ),
        "issue": "prod-day2-service-mesh-missing",
        "finding": "no active ServiceMeshControlPlane or service mesh membership footprint was detected",
    },
    {
        "key": "openshift_serverless",
        "capability": "OpenShift Serverless footprint",
        "level": cap_level("openshift_serverless", "informational"),
        "source": "OpenShift Serverless control plane and Knative workload inventory",
        "present": serverless_present,
        "healthy": serverless_healthy,
        "context_present": serverless_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"knativeservings={len(knativeservings)} "
            f"ready_knativeservings={len(ready_knativeservings)} "
            f"knativeeventings={len(knativeeventings)} "
            f"ready_knativeeventings={len(ready_knativeeventings)} "
            f"knativeservices={len(knativeservices)} "
            f"context_present={serverless_context_present} "
            f"subscription_present={serverless_subscription_present} "
            f"namespace_present={serverless_namespace_present} "
            f"crd_present={serverless_crd_present}"
        ),
        "issue": "prod-day2-serverless-missing",
        "finding": "no active KnativeServing, KnativeEventing, or Knative Service footprint was detected",
    },
    {
        "key": "windows_container_workloads",
        "capability": "Windows container workload footprint",
        "level": cap_level("windows_container_workloads", "informational"),
        "source": "node, workload, and Windows Machine Config Operator inventory",
        "present": windows_workloads_present,
        "healthy": windows_workloads_healthy,
        "context_present": windows_workloads_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"windows_nodes={len(windows_nodes)} "
            f"windows_workloads={len(windows_workload_objects)} "
            f"context_present={windows_workloads_context_present} "
            f"wmco_namespace={windows_operator_namespace_present} "
            f"wmco_subscription={windows_operator_subscription_present}"
        ),
        "issue": "prod-day2-windows-container-workloads-missing",
        "finding": "no Windows node or Windows-targeted workload footprint was detected",
    },
    {
        "key": "gpu_accelerated_workloads",
        "capability": "GPU accelerated workload footprint",
        "level": cap_level("gpu_accelerated_workloads", "informational"),
        "source": "GPU node, operator, and workload inventory",
        "present": gpu_workloads_present,
        "healthy": gpu_workloads_healthy,
        "context_present": gpu_workloads_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"gpu_nodes={len(gpu_nodes)} "
            f"gpu_workloads={len(gpu_workload_objects)} "
            f"context_present={gpu_workloads_context_present} "
            f"clusterpolicies={len(nvidiaclusterpolicies)} "
            f"gpu_operator_subscription={gpu_operator_subscription_present} "
            f"gpu_operator_workloads={gpu_operator_workload_present}"
        ),
        "issue": "prod-day2-gpu-accelerated-workloads-missing",
        "finding": "no node with allocatable GPU capacity or GPU-requesting workload was detected",
    },
    {
        "key": "sandboxed_container_workloads",
        "capability": "Sandboxed container workload footprint",
        "level": cap_level("sandboxed_container_workloads", "informational"),
        "source": "OpenShift sandboxed containers inventory",
        "present": sandboxed_containers_present,
        "healthy": sandboxed_containers_healthy,
        "context_present": sandboxed_containers_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"kataconfigs={len(kataconfigs)} "
            f"ready_kataconfigs={len(ready_kataconfigs)} "
            f"kata_workloads={len(kata_workload_objects)} "
            f"context_present={sandboxed_containers_context_present} "
            f"sandboxed_namespace={sandboxed_operator_namespace_present} "
            f"sandboxed_subscription={sandboxed_operator_subscription_present}"
        ),
        "issue": "prod-day2-sandboxed-container-workloads-missing",
        "finding": "no KataConfig or kata/sandbox runtime workload footprint was detected",
    },
    {
        "key": "kubelet_configuration_governance",
        "capability": "Kubelet configuration governance",
        "level": cap_level("kubelet_configuration_governance", "informational"),
        "source": "KubeletConfig resource inventory",
        "present": kubelet_configuration_governance_present,
        "healthy": kubelet_configuration_governance_healthy,
        "detail": (
            f"kubeletConfigs={len(kubeletconfigs)} "
            f"targetedConfigs={len(kubeletconfig_targeted)} "
            f"densityTuned={len(kubeletconfig_density_tuned)} "
            f"reservationTuned={len(kubeletconfig_reservation_tuned)} "
            f"evictionTuned={len(kubeletconfig_eviction_tuned)} "
            f"runtimePolicyTuned={len(kubeletconfig_runtime_policy_tuned)}"
        ),
        "issue": "prod-day2-kubelet-configuration-governance-missing",
        "finding": "no KubeletConfig resource footprint was detected for explicit kubelet tuning governance",
    },
    {
        "key": "openshift_developer_hub",
        "capability": "OpenShift Developer Hub footprint",
        "level": cap_level("openshift_developer_hub", "informational"),
        "source": "Red Hat Developer Hub operator and workload inventory",
        "present": openshift_developer_hub_present,
        "healthy": openshift_developer_hub_healthy,
        "detail": (
            f"subscriptionPresent={openshift_developer_hub_subscription_present} "
            f"namespacePresent={openshift_developer_hub_namespace_present} "
            f"crdPresent={openshift_developer_hub_crd_present} "
            f"contextPresent={openshift_developer_hub_context_present} "
            f"backstages={openshift_developer_hub_backstage_count} "
            f"readyBackstages={openshift_developer_hub_ready_backstage_count} "
            f"workloadPresent={openshift_developer_hub_workload_present}"
        ),
        "issue": "prod-day2-openshift-developer-hub-missing",
        "finding": "no Red Hat Developer Hub Backstage resource or portal workload footprint was detected; operator, namespace, or CRD context alone is not treated as an active Developer Hub deployment",
    },
    {
        "key": "openshift_dev_spaces",
        "capability": "OpenShift Dev Spaces footprint",
        "level": cap_level("openshift_dev_spaces", "informational"),
        "source": "OpenShift Dev Spaces operator and workspace inventory",
        "present": openshift_dev_spaces_present,
        "healthy": openshift_dev_spaces_healthy,
        "detail": (
            f"subscriptionPresent={openshift_dev_spaces_subscription_present} "
            f"namespacePresent={openshift_dev_spaces_namespace_present} "
            f"cheClusterPresent={openshift_dev_spaces_checluster_present} "
            f"devWorkspacePresent={openshift_dev_spaces_devworkspace_present} "
            f"workspaceOperatorConfigPresent={openshift_dev_spaces_workspace_operator_config_present} "
            f"routingPresent={openshift_dev_spaces_routing_present}"
        ),
        "issue": "prod-day2-openshift-dev-spaces-missing",
        "finding": "no OpenShift Dev Spaces operator, CheCluster, DevWorkspace, namespace, or routing footprint was detected",
    },
    {
        "key": "node_tuning_operator",
        "capability": "Node tuning operator configuration",
        "level": cap_level("node_tuning_operator", "informational"),
        "source": "Node Tuning Operator inventory",
        "present": node_tuning_present,
        "healthy": node_tuning_healthy,
        "context_present": node_tuning_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"tuneds={len(tuneds)} "
            f"custom_tuneds={len(custom_tuned_config_resources)} "
            f"tunedprofiles={len(tunedprofiles)} "
            f"performanceprofiles={len(performanceprofiles)} "
            f"ready_performanceprofiles={len(ready_performanceprofiles)} "
            f"context_present={node_tuning_context_present} "
            f"namespace_present={node_tuning_namespace_present} "
            f"crd_present={node_tuning_crd_present}"
        ),
        "issue": "prod-day2-node-tuning-operator-missing",
        "finding": "no custom Tuned or PerformanceProfile resource footprint was detected",
    },
    {
        "key": "kubernetes_nmstate_networking",
        "capability": "Kubernetes NMState networking footprint",
        "level": cap_level("kubernetes_nmstate_networking", "informational"),
        "source": "Kubernetes NMState inventory",
        "present": nmstate_present,
        "healthy": nmstate_healthy,
        "context_present": nmstate_context_present,
        "detail": (
            f"nmstates={len(nmstates)} "
            f"nodenetworkconfigurationpolicies={len(nodenetworkconfigurationpolicies)} "
            f"ready_nodenetworkconfigurationpolicies={len(ready_nodenetworkconfigurationpolicies)} "
            f"nodenetworkstates={len(nodenetworkstates)} "
            f"context_present={nmstate_context_present} "
            f"openshift_nmstate_namespace={nmstate_namespace_present} "
            f"subscription_present={nmstate_operator_subscription_present}"
        ),
        "issue": "prod-day2-kubernetes-nmstate-networking-missing",
        "finding": "no NMState, NodeNetworkConfigurationPolicy, NodeNetworkState, operator namespace, or subscription footprint was detected",
    },
    {
        "key": "descheduler_operator",
        "capability": "Descheduler operator footprint",
        "level": cap_level("descheduler_operator", "informational"),
        "source": "Descheduler Operator inventory",
        "present": descheduler_present,
        "healthy": descheduler_healthy,
        "context_present": descheduler_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"deschedulers={len(deschedulers)} "
            f"configured_deschedulers={len(configured_deschedulers)} "
            f"context_present={descheduler_context_present} "
            f"namespace_present={descheduler_namespace_present} "
            f"subscription_present={descheduler_subscription_present}"
        ),
        "issue": "prod-day2-descheduler-operator-missing",
        "finding": "no KubeDescheduler custom resource footprint was detected",
    },
    {
        "key": "multi_tenant_namespace_governance",
        "capability": "Team project onboarding controls",
        "level": namespace_guardrails_level,
        "source": "project configuration, GitOps, RBAC, and namespace guardrail inventory",
        "present": multi_tenant_namespace_governance_present,
        "healthy": multi_tenant_namespace_governance_healthy,
        "detail": (
            f"project_request_template={project_request_template_name or 'none'} "
            f"template_present={project_request_template_present} "
            f"template_guardrails={project_template_guardrail_count} "
            f"self_provisioning_restricted={self_provisioning_restricted} "
            f"self_provisioner_autoupdate_false={self_provisioner_autoupdate_false} "
            f"project_request_message={project_request_message_configured} "
            f"gitops_onboarding_apps={','.join(onboarding_gitops_app_names) or 'none'} "
            f"team_rbac_namespaces={team_rbac_namespace_count} "
            f"team_rbac_groups={team_rbac_group_count} "
            f"known_team_groups={known_team_group_count} "
            f"user_namespaces={len(user_namespace_names)} "
            f"default_deny_networkpolicy_namespaces={len(namespaces_with_default_deny_networkpolicy)} "
            f"networkpolicy_namespaces={len(namespaces_with_networkpolicy)} "
            f"egress_control_namespaces={len(namespaces_with_egress_controls)} "
            f"resourcequota_namespaces={len(namespaces_with_resourcequota)} "
            f"limitrange_namespaces={len(namespaces_with_limitrange)} "
            f"namespaces_with_all_guardrails={len(namespaces_with_all_namespace_governance_guardrails)}"
        ),
        "issue": "prod-day2-platform-namespace-governance-weak",
        "finding": (
            "no tenant onboarding or namespace-governance controls were detected for shared user namespaces"
        ),
        "finding_when_unhealthy": (
            "multi-tenant namespace governance is incomplete: "
            "non-admin namespace self-provisioning is not fully governed or project onboarding controls or tenant baseline guardrails are missing "
            f"(selfProvisioningRestricted={self_provisioning_restricted}, "
            f"selfProvisionerAutoupdateFalse={self_provisioner_autoupdate_false}, "
            f"networkPolicyMissing={len(namespaces_missing_networkpolicy)}, "
            f"egressControlMissing={len(namespaces_missing_egress_controls)}, "
            f"resourceQuotaMissing={len(namespaces_missing_resourcequota)}, "
            f"limitRangeMissing={len(sorted(user_namespace_names - namespaces_with_limitrange))})"
        ),
    },
    {
        "key": "cost_management_operator",
        "capability": "Cost management operator configuration",
        "level": cap_level("cost_management_operator", "informational"),
        "source": "cost management inventory",
        "present": cost_management_present,
        "healthy": cost_management_healthy,
        "context_present": cost_management_context_present,
        "defer_missing_finding_to_context": True,
        "detail": (
            f"costmanagementmetricsconfigs={len(costmanagementmetricsconfigs)} "
            f"ready_costmanagementmetricsconfigs={len(ready_cost_management_configs)} "
            f"context_present={cost_management_context_present} "
            f"subscription_present={cost_management_subscription_present} "
            f"namespace_present={cost_management_namespace_present} "
            f"crd_present={cost_management_crd_present}"
        ),
        "issue": "prod-day2-platform-cost-management-missing",
        "finding": "no CostManagementMetricsConfig resource footprint was detected",
    },
]

dynatrace_context_detail = (
    f"subscription_present={dynatrace_operator_subscription_present} "
    f"namespace_present={dynatrace_namespace_present} "
    f"crd_present={dynatrace_crd_present} "
    f"operator_workload_present={dynatrace_operator_workload_present} "
    f"edgeconnects={len(edgeconnects)}"
)
dynatrace_configuration_detail = f"dynakubes={len(dynakubes)}"
dynatrace_workload_detail = f"observability_workload_present={dynatrace_observability_workload_present}"
dynatrace_missing_detail = (
    "Dynatrace operator or chart context was detected, but no DynaKube custom resource configuration was found and no Dynatrace-managed workload footprint was detected"
    if dynatrace_context_present
    else "no Dynatrace DynaKube custom resource configuration or Dynatrace-managed workload footprint was detected"
)
dynatrace_recommended_action = (
    "Validate that cluster metrics, logs, and alert routing reach Dynatrace through the intended telemetry path."
    if dynatrace_observability_present
    else (
        "Dynatrace operator or chart context was detected, but no DynaKube custom resource configuration was found. Create and validate dynakubes.dynatrace.com resources, then confirm the OneAgent, ActiveGate, CSI driver, OpenTelemetry collector, log-monitoring, or other managed observability workload footprint."
        if dynatrace_context_present
        else "If Dynatrace-managed observability is intended, confirm operator or chart installation, DynaKube custom resource configuration, and managed workload rollout."
    )
)
add_check(
    "Dynatrace operator or chart context",
    ("OK" if dynatrace_context_present else ("WARN" if cap_required("dynatrace_observability") else "INFO")),
    dynatrace_context_detail,
    "Dynatrace operator and workload inventory",
    level=cap_level("dynatrace_observability", "informational"),
    scored=False,
    capability_key="dynatrace_observability",
)
add_check(
    "DynaKube custom resource configuration",
    ("OK" if dynatrace_dynakube_present else ("WARN" if (dynatrace_context_present or cap_required("dynatrace_observability")) else "INFO")),
    dynatrace_configuration_detail,
    "Dynatrace operator and workload inventory",
    level=cap_level("dynatrace_observability", "informational"),
    scored=False,
    capability_key="dynatrace_observability",
)
add_check(
    "Dynatrace managed workload footprint",
    ("OK" if dynatrace_observability_workload_present else ("WARN" if (dynatrace_context_present or cap_required("dynatrace_observability")) else "INFO")),
    dynatrace_workload_detail,
    "Dynatrace operator and workload inventory",
    level=cap_level("dynatrace_observability", "informational"),
    scored=False,
    capability_key="dynatrace_observability",
)
if not dynatrace_observability_present:
    add_finding(
        "prod-day2-dynatrace-observability-missing",
        dynatrace_missing_detail,
        severity=cap_failure_severity("dynatrace_observability"),
        source="Dynatrace operator and workload inventory",
        recommended_action=dynatrace_recommended_action,
    )

acs_context_detail = (
    f"subscription_present={acs_operator_subscription_present} "
    f"namespace_present={acs_namespace_present} "
    f"crd_present={acs_crd_present}"
)
acs_configuration_detail = "required Central or SecuredCluster custom resource configuration could not be confirmed from current collected evidence"
acs_workload_detail = f"workload_present={acs_workload_present}"
acs_missing_detail = (
    f"{acs_context_detail}; required Central or SecuredCluster custom resource configuration could not be confirmed and no RHACS-managed workload footprint was detected"
    if advanced_cluster_security_context_present
    else f"{acs_context_detail}; no RHACS operator/chart footprint or RHACS-managed workload footprint was detected"
)
acs_recommended_action = (
    "Confirm the RHACS footprint is healthy and that the intended workload-security services remain in service."
    if advanced_cluster_security_present
    else (
        "RHACS operator or chart context was detected, but the required Central or SecuredCluster custom resource configuration could not be confirmed and no active RHACS workload footprint was found. Create and validate Central or SecuredCluster resources, then confirm Central, Scanner, Sensor, admission-control, and secured-cluster rollout."
        if advanced_cluster_security_context_present
        else "If RHACS is the intended workload-security platform, install the operator or chart, apply the required Central or SecuredCluster custom resource configuration, and confirm active workload rollout."
    )
)
add_check(
    "RHACS operator or chart context",
    ("OK" if advanced_cluster_security_context_present else ("WARN" if cap_enabled("advanced_cluster_security") else "INFO")),
    acs_context_detail,
    "RHACS operator and secured-cluster inventory",
    level=acs_level,
    scored=False,
    capability_key="advanced_cluster_security",
)
add_check(
    "RHACS custom resource configuration",
    ("OK" if False else ("WARN" if (advanced_cluster_security_context_present or cap_enabled("advanced_cluster_security")) else "INFO")),
    acs_configuration_detail,
    "RHACS operator and secured-cluster inventory",
    level=acs_level,
    scored=False,
    capability_key="advanced_cluster_security",
)
add_check(
    "RHACS managed workload footprint",
    ("OK" if acs_workload_present else ("WARN" if (advanced_cluster_security_context_present or cap_enabled("advanced_cluster_security")) else "INFO")),
    acs_workload_detail,
    "RHACS operator and secured-cluster inventory",
    level=acs_level,
    scored=False,
    capability_key="advanced_cluster_security",
)
if not advanced_cluster_security_present and cap_enabled("advanced_cluster_security"):
    add_finding(
        "prod-day2-platform-acs-missing",
        acs_missing_detail,
        severity=cap_failure_severity("advanced_cluster_security"),
        source="RHACS operator and secured-cluster inventory",
        recommended_action=acs_recommended_action,
    )

prisma_context_detail = (
    f"subscription_present={prisma_subscription_present} "
    f"namespace_present={prisma_namespace_present} "
    f"crd_present={prisma_crd_present}"
)
prisma_configuration_detail = "required Prisma Cloud Compute custom resource configuration could not be confirmed from current collected evidence"
prisma_workload_detail = f"workload_present={prisma_workload_present}"
prisma_missing_detail = (
    f"{prisma_context_detail}; required Prisma Cloud Compute custom resource configuration could not be confirmed and no Console or Defender workload footprint was detected"
    if prisma_twistlock_context_present
    else f"{prisma_context_detail}; no Prisma Cloud Compute or Twistlock operator/chart footprint or Console or Defender workload footprint was detected"
)
prisma_recommended_action = (
    "Confirm the Prisma Cloud Compute footprint is healthy and that the intended Console and Defender services remain in service."
    if prisma_twistlock_defenders_present
    else (
        "Prisma Cloud Compute or Twistlock operator or chart context was detected, but the required custom resource configuration could not be confirmed and no Console or Defender workload footprint was found. Review the Prisma Cloud custom resource rollout and Defender deployment state."
        if prisma_twistlock_context_present
        else "If Prisma Cloud Compute or Twistlock is intended, confirm that the operator or chart is installed, then apply the required custom resource configuration and Console or Defender workload footprint."
    )
)
add_check(
    "Prisma Cloud Compute or Twistlock operator or chart context",
    ("OK" if prisma_twistlock_context_present else ("WARN" if cap_enabled("prisma_twistlock_defenders") else "INFO")),
    prisma_context_detail,
    "Prisma Cloud Compute inventory",
    level=cap_level("prisma_twistlock_defenders", "informational"),
    scored=False,
    capability_key="prisma_twistlock_defenders",
)
add_check(
    "Prisma Cloud Compute custom resource configuration",
    ("OK" if False else ("WARN" if (prisma_twistlock_context_present or cap_enabled("prisma_twistlock_defenders")) else "INFO")),
    prisma_configuration_detail,
    "Prisma Cloud Compute inventory",
    level=cap_level("prisma_twistlock_defenders", "informational"),
    scored=False,
    capability_key="prisma_twistlock_defenders",
)
add_check(
    "Prisma Cloud Compute managed workload footprint",
    ("OK" if prisma_workload_present else ("WARN" if (prisma_twistlock_context_present or cap_enabled("prisma_twistlock_defenders")) else "INFO")),
    prisma_workload_detail,
    "Prisma Cloud Compute inventory",
    level=cap_level("prisma_twistlock_defenders", "informational"),
    scored=False,
    capability_key="prisma_twistlock_defenders",
)
if not prisma_twistlock_defenders_present and cap_enabled("prisma_twistlock_defenders"):
    add_finding(
        "prod-day2-prisma-twistlock-defenders-missing",
        prisma_missing_detail,
        severity=cap_failure_severity("prisma_twistlock_defenders"),
        source="Prisma Cloud Compute inventory",
        recommended_action=prisma_recommended_action,
    )

aqua_context_detail = (
    f"subscription_present={aqua_subscription_present} "
    f"namespace_present={aqua_namespace_present} "
    f"crd_present={aqua_crd_present}"
)
aqua_configuration_detail = "required Aqua custom resource configuration could not be confirmed from current collected evidence"
aqua_workload_detail = f"workload_present={aqua_workload_present}"
aqua_missing_detail = (
    f"{aqua_context_detail}; required Aqua custom resource configuration could not be confirmed and no Aqua-managed workload footprint was detected"
    if aqua_platform_context_present
    else f"{aqua_context_detail}; no Aqua operator/chart footprint or Aqua-managed workload footprint was detected"
)
aqua_recommended_action = (
    "Confirm the Aqua footprint is healthy and that the intended Console, Gateway, and Enforcer services remain in service."
    if aqua_security_platform_present
    else (
        "Aqua operator or chart context was detected, but the required Aqua custom resource configuration could not be confirmed and no Aqua Console, Gateway, Enforcer, kube-enforcer, or other managed workload footprint was found. Review the Aqua custom resource rollout and enforcement deployment state."
        if aqua_platform_context_present
        else "If Aqua security is intended, confirm that the Aqua operator or chart is installed, then apply the required Aqua custom resource configuration and managed workload footprint."
    )
)
add_check(
    "Aqua operator or chart context",
    ("OK" if aqua_platform_context_present else ("WARN" if cap_enabled("aqua_security_platform") else "INFO")),
    aqua_context_detail,
    "Aqua operator and enforcer inventory",
    level=cap_level("aqua_security_platform", "informational"),
    scored=False,
    capability_key="aqua_security_platform",
)
add_check(
    "Aqua custom resource configuration",
    ("OK" if False else ("WARN" if (aqua_platform_context_present or cap_enabled("aqua_security_platform")) else "INFO")),
    aqua_configuration_detail,
    "Aqua operator and enforcer inventory",
    level=cap_level("aqua_security_platform", "informational"),
    scored=False,
    capability_key="aqua_security_platform",
)
add_check(
    "Aqua managed workload footprint",
    ("OK" if aqua_workload_present else ("WARN" if (aqua_platform_context_present or cap_enabled("aqua_security_platform")) else "INFO")),
    aqua_workload_detail,
    "Aqua operator and enforcer inventory",
    level=cap_level("aqua_security_platform", "informational"),
    scored=False,
    capability_key="aqua_security_platform",
)
if not aqua_security_platform_present and cap_enabled("aqua_security_platform"):
    add_finding(
        "prod-day2-aqua-security-platform-missing",
        aqua_missing_detail,
        severity=cap_failure_severity("aqua_security_platform"),
        source="Aqua operator and enforcer inventory",
        recommended_action=aqua_recommended_action,
    )

qualys_context_detail = (
    f"subscription_present={qualys_subscription_present} "
    f"namespace_present={qualys_namespace_present} "
    f"crd_present={qualys_crd_present} "
    f"operator_workload_present={qualys_operator_workload_present}"
)
qualys_configuration_detail = (
    f"k8s_mode_arg_present={qualys_k8s_mode_arg_present} "
    f"privileged_security_context_present={qualys_privileged_security_context_present} "
    f"service_account_config_present={qualys_service_account_config_present} "
    f"activation_config_present={qualys_activation_config_present}"
)
qualys_workload_detail = f"workload_present={qualys_workload_present}"
qualys_missing_detail = (
    "Qualys operator or chart context was detected, but the documented deployment configuration for a Qualys OpenShift sensor could not be confirmed and no managed scanner workload footprint was detected"
    if qualys_scanning_agents_context_present
    else "no Qualys documented deployment configuration or managed scanner workload footprint was detected"
)
qualys_recommended_action = (
    "Confirm the Qualys scanner footprint is healthy and that the intended sensor coverage remains in service."
    if qualys_scanning_agents_present
    else (
        "Qualys operator or chart context was detected, but the documented deployment configuration for a Qualys OpenShift sensor could not be confirmed. Review the DaemonSet or unified Helm deployment for the required --k8s-mode arguments, service account, privileged security context, and activation settings, then confirm active sensor rollout."
        if qualys_scanning_agents_context_present
        else "If Qualys scanning is intended, deploy the documented OpenShift sensor path with the required deployment configuration and confirm active managed scanner workloads."
    )
)
add_check(
    "Qualys operator or chart context",
    ("OK" if qualys_scanning_agents_context_present else ("WARN" if cap_enabled("qualys_scanning_agents") else "INFO")),
    qualys_context_detail,
    "Qualys agent inventory",
    level=cap_level("qualys_scanning_agents", "informational"),
    scored=False,
    capability_key="qualys_scanning_agents",
)
add_check(
    "Qualys required deployment configuration",
    ("OK" if qualys_required_deployment_configuration_present else ("WARN" if (qualys_scanning_agents_context_present or cap_enabled("qualys_scanning_agents")) else "INFO")),
    qualys_configuration_detail,
    "Qualys agent inventory",
    level=cap_level("qualys_scanning_agents", "informational"),
    scored=False,
    capability_key="qualys_scanning_agents",
)
add_check(
    "Qualys managed workload footprint",
    ("OK" if qualys_workload_present else ("WARN" if (qualys_scanning_agents_context_present or cap_enabled("qualys_scanning_agents")) else "INFO")),
    qualys_workload_detail,
    "Qualys agent inventory",
    level=cap_level("qualys_scanning_agents", "informational"),
    scored=False,
    capability_key="qualys_scanning_agents",
)
if not qualys_scanning_agents_present and cap_enabled("qualys_scanning_agents"):
    add_finding(
        "prod-day2-qualys-scanning-agents-missing",
        qualys_missing_detail,
        severity=cap_failure_severity("qualys_scanning_agents"),
        source="Qualys agent inventory",
        recommended_action=qualys_recommended_action,
    )

splunk_context_detail = (
    f"namespace_present={splunk_namespace_present} "
    f"crd_present={splunk_crd_present} "
    f"operator_workload_present={splunk_operator_workload_present}"
)
splunk_configuration_detail = (
    f"cluster_name_config_present={splunk_cluster_name_config_present} "
    f"destination_config_present={splunk_destination_config_present}"
)
splunk_workload_detail = f"workload_present={splunk_workload_present}"
splunk_missing_detail = (
    "Splunk operator or chart context was detected, but the documented deployment configuration for Splunk OpenTelemetry on OpenShift could not be confirmed and no managed collector workload footprint was detected"
    if splunk_context_present
    else "no Splunk documented deployment configuration or managed collector workload footprint was detected"
)
splunk_recommended_action = (
    "Validate that cluster metrics, logs, and traces reach Splunk through the intended telemetry path."
    if splunk_observability_present
    else (
        "Splunk operator or chart context was detected, but the documented deployment configuration for Splunk OpenTelemetry on OpenShift could not be confirmed. Review the Helm or operator-backed deployment for clusterName and destination settings, then confirm active collector rollout."
        if splunk_context_present
        else "If Splunk-managed observability is intended, deploy the documented Helm or operator-backed collector path with clusterName and destination settings, then confirm active managed collector workloads."
    )
)
add_check(
    "Splunk operator or chart context",
    ("OK" if splunk_context_present else ("WARN" if cap_enabled("splunk_observability") else "INFO")),
    splunk_context_detail,
    "Splunk OpenTelemetry and logging inventory",
    level=cap_level("splunk_observability", "informational"),
    scored=False,
    capability_key="splunk_observability",
)
add_check(
    "Splunk required deployment configuration",
    ("OK" if splunk_required_deployment_configuration_present else ("WARN" if (splunk_context_present or cap_enabled("splunk_observability")) else "INFO")),
    splunk_configuration_detail,
    "Splunk OpenTelemetry and logging inventory",
    level=cap_level("splunk_observability", "informational"),
    scored=False,
    capability_key="splunk_observability",
)
add_check(
    "Splunk managed workload footprint",
    ("OK" if splunk_workload_present else ("WARN" if (splunk_context_present or cap_enabled("splunk_observability")) else "INFO")),
    splunk_workload_detail,
    "Splunk OpenTelemetry and logging inventory",
    level=cap_level("splunk_observability", "informational"),
    scored=False,
    capability_key="splunk_observability",
)
if not splunk_observability_present and cap_enabled("splunk_observability"):
    add_finding(
        "prod-day2-splunk-observability-missing",
        splunk_missing_detail,
        severity=cap_failure_severity("splunk_observability"),
        source="Splunk OpenTelemetry and logging inventory",
        recommended_action=splunk_recommended_action,
    )

loki_context_detail = (
    f"namespace_present={loki_namespace_present} "
    f"crd_present={loki_crd_present}"
)
loki_configuration_detail = f"lokistacks={len(lokistacks)}"
loki_workload_detail = f"workload_present={loki_workload_present}"
loki_missing_detail = (
    "Loki operator or chart context was detected, but no LokiStack custom resource configuration was found and no Loki-managed workload footprint was detected"
    if loki_stack_context_present
    else "no LokiStack custom resource configuration or Loki-managed workload footprint was detected"
)
loki_recommended_action = (
    "Confirm the Loki footprint is healthy and that the intended centralized logging services remain in service."
    if loki_stack_logging_present
    else (
        "Loki operator or chart context was detected, but no LokiStack custom resource configuration was found. Create and validate lokistacks.loki.grafana.com resources, then confirm the managed Loki workload footprint."
        if loki_stack_context_present
        else "If LokiStack-based centralized logging is intended, confirm the LokiStack custom resource configuration or managed Loki workload footprint."
    )
)
add_check(
    "Loki operator or chart context",
    ("OK" if loki_stack_context_present else ("WARN" if cap_enabled("loki_stack_logging") else "INFO")),
    loki_context_detail,
    "LokiStack and Loki workload inventory",
    level=cap_level("loki_stack_logging", "informational"),
    scored=False,
    capability_key="loki_stack_logging",
)
add_check(
    "LokiStack custom resource configuration",
    ("OK" if len(lokistacks) > 0 else ("WARN" if (loki_stack_context_present or cap_enabled("loki_stack_logging")) else "INFO")),
    loki_configuration_detail,
    "LokiStack and Loki workload inventory",
    level=cap_level("loki_stack_logging", "informational"),
    scored=False,
    capability_key="loki_stack_logging",
)
add_check(
    "Loki managed workload footprint",
    ("OK" if loki_workload_present else ("WARN" if (loki_stack_context_present or cap_enabled("loki_stack_logging")) else "INFO")),
    loki_workload_detail,
    "LokiStack and Loki workload inventory",
    level=cap_level("loki_stack_logging", "informational"),
    scored=False,
    capability_key="loki_stack_logging",
)
if not loki_stack_logging_present and cap_enabled("loki_stack_logging"):
    add_finding(
        "prod-day2-loki-stack-logging-missing",
        loki_missing_detail,
        severity=cap_failure_severity("loki_stack_logging"),
        source="LokiStack and Loki workload inventory",
        recommended_action=loki_recommended_action,
    )

datadog_context_detail = (
    f"subscription_present={datadog_subscription_present} "
    f"namespace_present={datadog_namespace_present} "
    f"crd_present={datadog_crd_present}"
)
datadog_configuration_detail = f"datadogagents={len(datadogagents)}"
datadog_workload_detail = f"workload_present={datadog_workload_present}"
datadog_missing_detail = (
    "Datadog operator or chart context was detected, but no DatadogAgent custom resource configuration was found and no Datadog-managed agent workload footprint was detected"
    if datadog_context_present
    else "no DatadogAgent custom resource configuration or Datadog-managed agent workload footprint was detected"
)
datadog_recommended_action = (
    "Validate that cluster metrics, logs, and traces reach Datadog through the intended telemetry path."
    if datadog_observability_present
    else (
        "Datadog operator or chart context was detected, but no DatadogAgent custom resource configuration was found. Create and validate datadogagents.datadoghq.com resources, then confirm the managed agent footprint and telemetry delivery path."
        if datadog_context_present
        else "If Datadog-managed observability is intended, confirm the DatadogAgent custom resource configuration, agent footprint, and telemetry delivery path."
    )
)
add_check(
    "Datadog operator or chart context",
    ("OK" if datadog_context_present else ("WARN" if cap_enabled("datadog_observability") else "INFO")),
    datadog_context_detail,
    "Datadog operator and agent inventory",
    level=cap_level("datadog_observability", "informational"),
    scored=False,
    capability_key="datadog_observability",
)
add_check(
    "DatadogAgent custom resource configuration",
    ("OK" if len(datadogagents) > 0 else ("WARN" if (datadog_context_present or cap_enabled("datadog_observability")) else "INFO")),
    datadog_configuration_detail,
    "Datadog operator and agent inventory",
    level=cap_level("datadog_observability", "informational"),
    scored=False,
    capability_key="datadog_observability",
)
add_check(
    "Datadog managed workload footprint",
    ("OK" if datadog_workload_present else ("WARN" if (datadog_context_present or cap_enabled("datadog_observability")) else "INFO")),
    datadog_workload_detail,
    "Datadog operator and agent inventory",
    level=cap_level("datadog_observability", "informational"),
    scored=False,
    capability_key="datadog_observability",
)
if not datadog_observability_present and cap_enabled("datadog_observability"):
    add_finding(
        "prod-day2-datadog-observability-missing",
        datadog_missing_detail,
        severity=cap_failure_severity("datadog_observability"),
        source="Datadog operator and agent inventory",
        recommended_action=datadog_recommended_action,
    )

appdynamics_context_detail = (
    f"subscription_present={appdynamics_subscription_present} "
    f"namespace_present={appdynamics_namespace_present} "
    f"crd_present={appdynamics_crd_present}"
)
appdynamics_configuration_detail = f"clusteragents={len(clusteragents)} infravizs={len(infravizs)}"
appdynamics_workload_detail = f"workload_present={appdynamics_workload_present}"
appdynamics_missing_detail = (
    "AppDynamics operator or chart context was detected, but no ClusterAgent or InfraViz custom resource configuration was found and no AppDynamics-managed workload footprint was detected"
    if appdynamics_context_present
    else "no AppDynamics ClusterAgent or InfraViz custom resource configuration or AppDynamics-managed workload footprint was detected"
)
appdynamics_recommended_action = (
    "Validate that cluster visibility data reaches the intended AppDynamics destination."
    if appdynamics_observability_present
    else (
        "AppDynamics operator or chart context was detected, but no ClusterAgent or InfraViz custom resource configuration was found. Create and validate clusteragents.appdynamics.com or infravizs.appdynamics.com resources, then confirm the supporting managed workload footprint."
        if appdynamics_context_present
        else "If AppDynamics cluster visibility is intended, confirm the ClusterAgent or InfraViz custom resource configuration and supporting workload footprint."
    )
)
add_check(
    "AppDynamics operator or chart context",
    ("OK" if appdynamics_context_present else ("WARN" if cap_enabled("appdynamics_observability") else "INFO")),
    appdynamics_context_detail,
    "AppDynamics cluster agent inventory",
    level=cap_level("appdynamics_observability", "informational"),
    scored=False,
    capability_key="appdynamics_observability",
)
add_check(
    "AppDynamics custom resource configuration",
    ("OK" if (len(clusteragents) > 0 or len(infravizs) > 0) else ("WARN" if (appdynamics_context_present or cap_enabled("appdynamics_observability")) else "INFO")),
    appdynamics_configuration_detail,
    "AppDynamics cluster agent inventory",
    level=cap_level("appdynamics_observability", "informational"),
    scored=False,
    capability_key="appdynamics_observability",
)
add_check(
    "AppDynamics managed workload footprint",
    ("OK" if appdynamics_workload_present else ("WARN" if (appdynamics_context_present or cap_enabled("appdynamics_observability")) else "INFO")),
    appdynamics_workload_detail,
    "AppDynamics cluster agent inventory",
    level=cap_level("appdynamics_observability", "informational"),
    scored=False,
    capability_key="appdynamics_observability",
)
if not appdynamics_observability_present and cap_enabled("appdynamics_observability"):
    add_finding(
        "prod-day2-appdynamics-observability-missing",
        appdynamics_missing_detail,
        severity=cap_failure_severity("appdynamics_observability"),
        source="AppDynamics cluster agent inventory",
        recommended_action=appdynamics_recommended_action,
    )

for item in platform_app_catalog:
    present = bool(item["present"])
    key = item["key"]
    healthy = bool(item.get("healthy", True))
    required_or_present = (
        present
        or cap_required(key)
        or (key == "advanced_cluster_security" and cap_enabled(key))
    )
    if not required_or_present:
        continue
    add_check(
        item["capability"],
        cap_status_for_presence(key, present, healthy),
        item["detail"],
        item["source"],
        level=item["level"],
        scored=False,
    )
    missing_finding_deferred = bool(item.get("defer_missing_finding_to_context")) and bool(item.get("context_present"))
    if not present and required_or_present and not missing_finding_deferred:
        add_finding(
            item["issue"],
            item["finding"],
            severity=cap_failure_severity(key),
            source=item["source"],
        )
    elif present and not healthy and item.get("finding_when_unhealthy"):
        add_finding(
            item["issue"],
            item["finding_when_unhealthy"],
            severity=cap_failure_severity(key),
            source=item["source"],
        )

if cap_required("service_mesh_control_plane") and service_mesh_context_present and not service_mesh_control_plane_present:
    add_finding(
        "prod-day2-service-mesh-missing",
        "service mesh operator or CRD footprint was detected, but no ServiceMeshControlPlane resource was found",
        severity=cap_failure_severity("service_mesh_control_plane"),
        source="OpenShift Service Mesh control plane and membership inventory",
    )
elif cap_required("service_mesh_control_plane") and service_mesh_control_plane_present and not service_mesh_healthy:
    add_finding(
        "prod-day2-service-mesh-missing",
        "ServiceMeshControlPlane resources were found, but no control plane reported a ready, installed, or reconciled state",
        severity=cap_failure_severity("service_mesh_control_plane"),
        source="OpenShift Service Mesh control plane and membership inventory",
    )

if cap_required("openshift_serverless") and serverless_context_present and not serverless_control_plane_present:
    add_finding(
        "prod-day2-serverless-missing",
        "serverless operator, namespace, CRD, or workload footprint was detected, but no KnativeServing or KnativeEventing control plane resource was found",
        severity=cap_failure_severity("openshift_serverless"),
        source="OpenShift Serverless control plane and Knative workload inventory",
    )
elif cap_required("openshift_serverless") and serverless_control_plane_present and not serverless_healthy:
    add_finding(
        "prod-day2-serverless-missing",
        "KnativeServing or KnativeEventing resources were found, but no serverless control plane reported a ready or installed state",
        severity=cap_failure_severity("openshift_serverless"),
        source="OpenShift Serverless control plane and Knative workload inventory",
    )

if cap_required("windows_container_workloads") and windows_workloads_context_present and not windows_workloads_present:
    add_finding(
        "prod-day2-windows-container-workloads-missing",
        "Windows Machine Config Operator footprint was detected, but no Windows node or Windows-targeted workload was found",
        severity=cap_failure_severity("windows_container_workloads"),
        source="node, workload, and Windows Machine Config Operator inventory",
    )
if cap_required("openshift_custom_metrics_autoscaler") and openshift_custom_metrics_autoscaler_context_present and not openshift_custom_metrics_autoscaler_present:
    add_finding(
        "prod-day2-openshift-custom-metrics-autoscaler-missing",
        "KEDA operator, namespace, or CRD footprint was detected, but no KedaController, ScaledObject, ScaledJob, trigger authentication, or KEDA-managed workload footprint was found",
        severity=cap_failure_severity("openshift_custom_metrics_autoscaler"),
        source="KEDA controller and custom autoscaling resource inventory",
    )
if cap_required("gpu_accelerated_workloads") and gpu_workloads_context_present and not gpu_workloads_present:
    add_finding(
        "prod-day2-gpu-accelerated-workloads-missing",
        "GPU operator or ClusterPolicy footprint was detected, but no node with allocatable GPU capacity or GPU-requesting workload was found",
        severity=cap_failure_severity("gpu_accelerated_workloads"),
        source="GPU node, operator, and workload inventory",
    )
if cap_required("sandboxed_container_workloads") and sandboxed_containers_context_present and not sandboxed_containers_present:
    add_finding(
        "prod-day2-sandboxed-container-workloads-missing",
        "sandboxed containers operator footprint was detected, but no KataConfig resource or kata runtime workload was found",
        severity=cap_failure_severity("sandboxed_container_workloads"),
        source="OpenShift sandboxed containers inventory",
    )
elif cap_required("sandboxed_container_workloads") and sandboxed_containers_present and not sandboxed_containers_healthy:
    add_finding(
        "prod-day2-sandboxed-container-workloads-missing",
        "sandboxed container resources were detected, but no KataConfig reported a completed/installed state and no kata runtime workload was found",
        severity=cap_failure_severity("sandboxed_container_workloads"),
        source="OpenShift sandboxed containers inventory",
    )
if cap_required("openshift_virtualization") and openshift_virtualization_present and not openshift_virtualization_healthy:
    add_finding(
        "prod-day2-openshift-virtualization-missing",
        "OpenShift Virtualization resources were detected, but no KubeVirt or HyperConverged control plane reported a ready or available state",
        severity=cap_failure_severity("openshift_virtualization"),
        source="OpenShift Virtualization resource inventory",
    )
if cap_required("openshift_ai") and openshift_ai_present and not openshift_ai_healthy:
    add_finding(
        "prod-day2-openshift-ai-missing",
        "OpenShift AI resources were detected, but no DataScienceCluster or DSCInitialization resource reported a ready or available state",
        severity=cap_failure_severity("openshift_ai"),
        source="OpenShift AI resource inventory",
    )
if cap_required("node_tuning_operator") and node_tuning_context_present and not node_tuning_present:
    add_finding(
        "prod-day2-node-tuning-operator-missing",
        "Node Tuning Operator context was detected, but no custom Tuned or PerformanceProfile resource was found",
        severity=cap_failure_severity("node_tuning_operator"),
        source="Node Tuning Operator inventory",
    )
elif cap_required("node_tuning_operator") and node_tuning_present and not node_tuning_healthy:
    add_finding(
        "prod-day2-node-tuning-operator-missing",
        "Node Tuning Operator tuning resources were detected, but no usable custom Tuned recommendation/profile or healthy PerformanceProfile was found",
        severity=cap_failure_severity("node_tuning_operator"),
        source="Node Tuning Operator inventory",
    )
if cap_required("openshift_developer_hub") and openshift_developer_hub_present and not openshift_developer_hub_healthy:
    add_finding(
        "prod-day2-openshift-developer-hub-missing",
        "Red Hat Developer Hub footprint was detected, but no ready Backstage resource or portal workload was found",
        severity=cap_failure_severity("openshift_developer_hub"),
        source="Red Hat Developer Hub operator and workload inventory",
    )
if cap_required("openshift_dev_spaces") and openshift_dev_spaces_present and not openshift_dev_spaces_healthy:
    add_finding(
        "prod-day2-openshift-dev-spaces-missing",
        (
            "OpenShift Dev Spaces footprint was detected, but no healthy CheCluster, DevWorkspace, or supporting routing/configuration path was found "
            f"(subscriptionPresent={openshift_dev_spaces_subscription_present}, "
            f"namespacePresent={openshift_dev_spaces_namespace_present}, "
            f"cheClusterPresent={openshift_dev_spaces_checluster_present}, "
            f"devWorkspacePresent={openshift_dev_spaces_devworkspace_present}, "
            f"workspaceOperatorConfigPresent={openshift_dev_spaces_workspace_operator_config_present}, "
            f"routingPresent={openshift_dev_spaces_routing_present})"
        ),
        severity=cap_failure_severity("openshift_dev_spaces"),
        source="OpenShift Dev Spaces operator and workspace inventory",
    )
if cap_required("kubernetes_nmstate_networking") and nmstate_present and not nmstate_healthy:
    add_finding(
        "prod-day2-kubernetes-nmstate-networking-missing",
        "Kubernetes NMState footprint was detected, but no NMState or NodeNetworkConfigurationPolicy resource was found to show managed node-network intent",
        severity=cap_failure_severity("kubernetes_nmstate_networking"),
        source="Kubernetes NMState inventory",
    )
if cap_required("cost_management_operator") and cost_management_context_present and not cost_management_present:
    add_finding(
        "prod-day2-platform-cost-management-missing",
        "cost management metrics operator footprint was detected, but no CostManagementMetricsConfig resource was found",
        severity=cap_failure_severity("cost_management_operator"),
        source="cost management inventory",
    )
elif cap_required("cost_management_operator") and cost_management_present and not cost_management_healthy:
    add_finding(
        "prod-day2-platform-cost-management-missing",
        "CostManagementMetricsConfig resources were detected, but their status includes a problem condition or status",
        severity=cap_failure_severity("cost_management_operator"),
        source="cost management inventory",
    )
if cap_required("descheduler_operator") and descheduler_context_present and not descheduler_present:
    add_finding(
        "prod-day2-descheduler-operator-missing",
        "descheduler operator footprint was detected, but no KubeDescheduler custom resource was found",
        severity=cap_failure_severity("descheduler_operator"),
        source="Descheduler Operator inventory",
    )
elif cap_required("descheduler_operator") and descheduler_present and not descheduler_healthy:
    add_finding(
        "prod-day2-descheduler-operator-missing",
        "KubeDescheduler resources were detected, but no configured resource in a ready or non-problem state was found",
        severity=cap_failure_severity("descheduler_operator"),
        source="Descheduler Operator inventory",
    )

if cap_enabled("advanced_cluster_management"):
    add_check(
        "ACM managed-cluster context",
        ("OK" if acm_registration_present else ("WARN" if cap_required("advanced_cluster_management") else "INFO")),
        (
            f"klusterlets={len(klusterlets)} "
            f"managedclusteraddons={len(managedclusteraddons)} "
            f"agent_namespaces={','.join(acm_agent_namespaces) or 'none'}"
        ),
        "managed-cluster registration inventory",
        level=cap_level("advanced_cluster_management", "informational"),
        scored=False,
        capability_key="advanced_cluster_management",
    )
    add_check(
        "ACM Klusterlet registration configuration",
        ("OK" if len(klusterlets) > 0 else ("WARN" if (acm_registration_present or cap_required("advanced_cluster_management")) else "INFO")),
        f"klusterlets={len(klusterlets)}",
        "managed-cluster registration inventory",
        level=cap_level("advanced_cluster_management", "informational"),
        scored=False,
        capability_key="advanced_cluster_management",
    )
    add_check(
        "ACM managed-cluster add-on or agent footprint",
        (
            "OK"
            if (len(managedclusteraddons) > 0 or len(acm_agent_namespaces) > 0)
            else ("WARN" if (acm_registration_present or cap_required("advanced_cluster_management")) else "INFO")
        ),
        (
            f"managedclusteraddons={len(managedclusteraddons)} "
            f"agent_namespaces={','.join(acm_agent_namespaces) or 'none'}"
        ),
        "managed-cluster registration inventory",
        level=cap_level("advanced_cluster_management", "informational"),
        scored=False,
        capability_key="advanced_cluster_management",
    )
if cap_required("advanced_cluster_management") and not acm_registration_present:
    add_finding(
        "prod-day2-acm-management-missing",
        "no ACM managed-cluster signals were found from Klusterlet, ManagedClusterAddOn, or ACM agent namespaces",
        severity=cap_failure_severity("advanced_cluster_management"),
        source="managed-cluster registration inventory",
    )
elif cap_required("advanced_cluster_management") and not acm_registration_healthy:
    add_finding(
        "prod-day2-acm-management-missing",
        "partial ACM evidence was found from ManagedClusterAddOn objects, but no Klusterlet resource or ACM agent namespace was detected to demonstrate managed-cluster registration",
        severity=cap_failure_severity("advanced_cluster_management"),
        source="managed-cluster registration inventory",
    )

severity_rank = {"critical": 4, "warning": 3, "warn": 3, "info": 2, "ok": 1, "unknown": 0}
capability_sections = []
for cap_key, cap_value in capability_profile.items():
    if not isinstance(cap_value, dict) or not bool(cap_value.get("enabled", True)):
        continue
    cap_checks = [item for item in checks if item.get("capability_key") == cap_key]
    cap_findings = [item for item in findings if item.get("capability") == cap_key]
    finding_severities = [str(item.get("severity") or "info").lower() for item in cap_findings]
    check_statuses = [str(item.get("status") or "unknown").upper() for item in cap_checks]
    if any(item == "critical" for item in finding_severities):
        overall_status = "CRITICAL"
    elif any(item in {"warning", "warn"} for item in finding_severities):
        overall_status = "WARNING"
    elif "WARN" in check_statuses:
        overall_status = "WARNING"
    elif "OK" in check_statuses:
        overall_status = "OK"
    elif any(item == "info" for item in finding_severities) or "INFO" in check_statuses:
        overall_status = "INFO"
    elif bool(cap_value.get("required", False)):
        overall_status = "UNKNOWN"
    elif cap_checks or cap_findings:
        overall_status = "UNKNOWN"
    elif str(cap_value.get("expected_state") or "present").strip().lower() == "not_applicable":
        overall_status = "INFO"
    else:
        overall_status = "INFO"
    recommended_action = (
        cap_findings[0].get("recommended_action")
        if cap_findings
        else (
            "No remediation is currently required for this capability posture."
            if overall_status == "OK"
            else (
                "Collect or review the expected evidence for this capability and remediate any gaps."
                if overall_status in {"WARNING", "CRITICAL", "UNKNOWN"}
                else "Review this capability as informational context."
            )
        )
    )
    capability_sections.append({
        "key": cap_key,
        "title": cap_key.replace("_", " ").strip(),
        "required": bool(cap_value.get("required", False)),
        "criticality": str(cap_value.get("criticality") or "medium").strip().lower(),
        "expected_state": str(cap_value.get("expected_state") or "present").strip().lower(),
        "owner": str(cap_value.get("owner") or "platform").strip() or "platform",
        "evidence_required": [str(item).strip() for item in (cap_value.get("evidence_required") or []) if str(item).strip()],
        "notes": str(cap_value.get("notes") or "").strip(),
        "docs": (
            [str(item).strip() for item in (cap_value.get("docs") or []) if str(item).strip()]
            if isinstance(cap_value.get("docs"), list)
            else ([str(cap_value.get("docs") or "").strip()] if str(cap_value.get("docs") or "").strip() else [])
        ),
        "verification": (
            [str(item).strip() for item in (cap_value.get("verification") or []) if str(item).strip()]
            if isinstance(cap_value.get("verification"), list)
            else ([str(cap_value.get("verification") or "").strip()] if str(cap_value.get("verification") or "").strip() else [])
        ),
        "status": overall_status,
        "check_count": len(cap_checks),
        "finding_count": len(cap_findings),
        "checks": cap_checks,
        "findings": cap_findings,
        "recommended_action": recommended_action,
        "top_detail": (
            cap_findings[0].get("detail")
            if cap_findings
            else (
                cap_checks[0].get("detail")
                if cap_checks
                else (
                    "This capability is enabled in the cluster health profile, but the current analyzer did not map a specific collected check or finding to it yet."
                )
            )
        ),
        "accounting_state": (
            "assessed"
            if (cap_checks or cap_findings)
            else "profile-enabled-no-direct-check"
        ),
    })

capability_sections.sort(key=lambda item: (
    -int(item.get("required", False)),
    -severity_rank.get(str(item.get("status") or "unknown").lower(), 0),
    str(item.get("key") or ""),
))

print(json.dumps({
    "assessment_state": "completed",
    "assessment_error": "",
    "day2_posture_checks": checks,
    "day2_posture_findings": findings,
    "scored_day2_posture_findings": [item for item in findings if item.get("severity") != "info"],
    "capability_sections": capability_sections,
    "day2_posture_summary": {
        "capability_assessment_state": "completed",
        "capability_assessment_error": "",
        "checks_total": len(checks),
        "checks_warn": len([c for c in checks if c["status"] == "WARN"]),
        "scored_findings_count": len([item for item in findings if item.get("severity") != "info"]),
        "baseline_profile": day2_baseline_profile,
        "capability_profile": capability_profile,
        "gitops_present": gitops_present,
        "gitops_controller_context_present": gitops_controller_context_present,
        "gitops_application_configuration_present": gitops_application_configuration_present,
        "gitops_operational": gitops_operational,
        "gitops_automated_sync_present": gitops_automated_sync_present,
        "argocd_count": len(argocds),
        "gitops_application_count": len(gitops_apps),
        "gitops_repo_backed_application_count": len(gitops_apps_with_repo_source),
        "gitops_automated_sync_application_count": len(gitops_apps_with_automated_sync),
        "gitops_appproject_count": len(gitops_projects),
        "namespace_onboarding_controls_present": namespace_onboarding_controls_present,
        "project_request_template_name": project_request_template_name,
        "project_request_template_present": project_request_template_present,
        "project_request_template_guardrail_count": project_template_guardrail_count,
        "project_request_message_configured": project_request_message_configured,
        "self_provisioning_restricted": self_provisioning_restricted,
        "self_provisioner_autoupdate_false": self_provisioner_autoupdate_false,
        "onboarding_gitops_application_count": len(onboarding_gitops_app_names),
        "team_rbac_namespace_count": team_rbac_namespace_count,
        "team_rbac_group_count": team_rbac_group_count,
        "known_team_group_count": known_team_group_count,
        "namespaces_with_all_baseline_guardrails": len(namespaces_with_all_baseline_guardrails),
        "namespaces_with_all_namespace_governance_guardrails": len(namespaces_with_all_namespace_governance_guardrails),
        "external_secret_store_count": ext_secret_store_count,
        "external_secret_count": len(externalsecrets),
        "external_secret_ready_store_count": len(ready_secret_stores),
        "external_secret_ready_count": len(ready_external_secrets),
        "external_secrets_subscription_present": ext_secrets_subscription_present,
        "external_secrets_namespace_present": ext_secrets_namespace_present,
        "external_secrets_crd_present": ext_secrets_crd_present,
        "external_secrets_operator_workload_present": ext_secrets_operator_workload_present,
        "external_secrets_context_present": ext_secrets_context_present,
        "external_secrets_configuration_present": ext_secrets_configuration_present,
        "external_secrets_managed_sync_present": ext_secrets_managed_sync_present,
        "external_secrets_healthy": ext_secrets_healthy,
        "cyberark_conjur_namespace_present": conjur_namespace_present,
        "cyberark_conjur_workload_present": conjur_workload_present,
        "cyberark_conjur_secretproviderclass_count": len(conjur_secretproviderclass_resources),
        "cyberark_conjur_context_present": conjur_context_present,
        "cyberark_conjur_present": cyberark_conjur_secrets_management_present,
        "cyberark_conjur_healthy": cyberark_conjur_secrets_management_healthy,
        "clusterautoscaler_count": len(clusterautoscalers),
        "clusterautoscaler_expected": autoscaler_expected,
        "hostedcluster_count": len(hostedclusters),
        "nodepool_count": len(nodepools),
        "hostedcluster_autoscaling_present": hostedcluster_autoscaling_present,
        "nodepool_autoscaling_present": nodepool_autoscaling_present,
        "machinehealthcheck_count": len(machinehealthchecks),
        "machinehealthcheck_expected": mhc_expected,
        "acm_managed": acm_managed,
        "acm_klusterlet_count": len(klusterlets),
        "acm_managedclusteraddon_count": len(managedclusteraddons),
        "acm_agent_namespace_count": len(acm_agent_namespaces),
        "enable_user_workload_monitoring": enable_user_workload,
        "servicemonitor_count": len(servicemonitors),
        "podmonitor_count": len(podmonitors),
        "user_workload_metrics_vendor_managed": bool(obs.get("vendor_managed_metrics_forwarding_present")),
        "user_workload_alertmanager_additional_config_count": len(user_workload_alertmanager_additional_configs),
        "user_workload_alerting_signal_present": user_workload_alerting_present,
        "user_workload_vendor_managed_observability_present": user_workload_vendor_managed_observability_present,
        "user_workload_observability_vendor_names": vendor_metrics_forwarding_names,
        "user_workload_alerting_delivery_model": user_workload_alerting_delivery_model,
        "grafana_present": grafana_present,
        "grafana_dashboard_configmap_count": len(dashboard_configmaps),
        "grafana_dashboard_resource_count": len(grafanadashboards),
        "grafana_dashboard_present": grafana_dashboard_present,
        "workloads_using_external_private_registries_present": workloads_using_external_private_registries_present,
        "external_private_registry_count": len(external_image_registries),
        "external_private_registry_workload_count": external_private_registry_workload_count,
        "external_private_registry_workloads_with_pull_secret": external_private_registry_workloads_with_pull_secret,
        "external_private_registry_workloads_with_serviceaccount_pull_secret": external_private_registry_workloads_with_serviceaccount_pull_secret,
        "credentialed_public_registry_count": len(credentialed_public_image_registries),
        "workloads_with_image_pull_secret": workloads_with_pull_secret,
        "cluster_image_mirror_configuration_present": cluster_image_mirror_configuration_present,
        "image_mirror_resource_count": mirror_resource_count,
        "image_signature_and_admission_policy_present": image_signature_and_admission_policy_present,
        "image_signature_and_admission_policy_healthy": image_signature_and_admission_policy_healthy,
        "admission_policy_engine_present": admission_policy_engine_present,
        "image_registry_filter_policy_present": bool(len(allowed_imports) > 0 or restricted_registry_sources),
        "image_admission_policy_resource_count": len(image_admission_policy_resources),
        "active_trusted_image_policy_present": active_trusted_image_policy_present,
        "insecure_registry_count": len(insecure_registries),
        "disconnected_cluster_image_sources_present": disconnected_cluster_image_sources_present,
        "release_image_mirror_configured": release_image_mirror_configured,
        "release_image_mirrored": release_image_mirrored,
        "disconnected_catalogsource_count": disconnected_catalog_count,
        "ovn_ipsec_encryption": ovn_ipsec_encryption,
        "ovn_ipsec_external_only": ovn_ipsec_external_only,
        "ipsec_mode": ipsec_mode,
        "etcd_encryption": etcd_encryption,
        "etcd_encryption_type": etcd_encryption_type,
        "etcd_encryption_complete": etcd_encryption_complete,
        "etcd_encryption_reported_component_count": len(etcd_encryption_reported_components),
        "etcd_encryption_completed_component_count": len(etcd_encryption_completed_components),
        "cluster_proxy_configured": cluster_proxy_configured,
        "custom_ca_trust_configured": custom_ca_configured,
        "workload_vulnerability_scanning_present": workload_scanner_present,
        "monitoring_persistent_storage_configured": monitoring_persistent,
        "control_plane_runtime_healthy": control_plane_runtime_healthy,
        "external_log_forwarding_output_count": len(obs.get("external_log_forwarding_outputs") or []),
        "external_alert_delivery_configured": external_alert_delivery_present,
        "external_alert_receiver_count": int(obs.get("external_alert_receiver_count") or 0),
        "cluster_network_observability_present": cluster_network_observability_present,
        "cluster_network_observability_healthy": cluster_network_observability_healthy,
        "cluster_network_observability_subscription_present": cluster_network_observability_subscription_present,
        "cluster_network_observability_namespace_present": cluster_network_observability_namespace_present,
        "cluster_network_observability_crd_present": cluster_network_observability_crd_present,
        "cluster_network_observability_flowcollector_count": cluster_network_observability_flowcollector_count,
        "cluster_network_observability_flowcollector_present": cluster_network_observability_flowcollector_present,
        "cluster_network_observability_workload_present": cluster_network_observability_workload_present,
        "external_cluster_metrics_remote_write_count": cluster_remote_write,
        "external_user_workload_metrics_remote_write_count": user_remote_write,
        "apiserver_audit_profile": apiserver_audit_profile or "not-configured",
        "api_audit_logging_present": api_audit_logging_present,
        "api_audit_retention_present": api_audit_retention_present,
        "backup_schedule_count": len(schedules),
        "backup_storage_location_count": len(backupstoragelocations),
        "data_protection_application_count": len(dataprotectionapplications),
        "successful_backup_count": successful_backups,
        "clean_successful_backup_count": clean_successful_backups,
        "clean_completed_restore_count": clean_completed_restores,
        "application_backup_ready": backup_ready,
        "workload_backup_provider_present": workload_backup_provider_present,
        "oadp_backup_provider_present": oadp_backup_provider_present,
        "velero_backup_provider_present": velero_backup_provider_present,
        "commvault_backup_provider_present": commvault_backup_provider_present,
        "application_backup_evidence_present": application_backup_evidence_present,
        "application_restore_evidence_present": application_restore_evidence_present,
        "secondary_site_disaster_recovery_present": secondary_site_dr_present,
        "secondary_site_disaster_recovery_healthy": secondary_site_dr_healthy,
        "drpolicy_count": len(drpolicies),
        "valid_drpolicy_count": len(valid_drpolicy_names),
        "drcluster_count": len(drclusters),
        "drplacementcontrol_count": len(drplacementcontrols),
        "volumereplicationgroup_count": len(volumereplicationgroups),
        "volumereplicationclass_count": len(volumereplicationclasses),
        "volumegroupreplication_count": len(volumegroupreplications),
        "secondary_site_dr_problem_drcluster_count": len(drclusters_with_problem_status),
        "secondary_site_dr_problem_drpc_count": len(drpcs_with_problem_status),
        "secondary_site_dr_problem_vrg_count": len(vrgs_with_problem_status),
        "cluster_hosted_cicd_runners_present": cicd_runner_present,
        "openshift_pipeline_workflows_present": bool("openshift-pipelines-operator-rh" in subscription_packages or "openshift-pipelines" in namespace_names or "openshift-pipelines-operator-bootstrap" in gitops_application_names),
        "openshift_pipeline_subscription_present": "openshift-pipelines-operator-rh" in subscription_packages,
        "openshift_pipeline_namespace_present": "openshift-pipelines" in namespace_names,
        "openshift_pipeline_gitops_app_present": "openshift-pipelines-operator-bootstrap" in gitops_application_names,
        "openshift_developer_hub_present": openshift_developer_hub_present,
        "openshift_developer_hub_healthy": openshift_developer_hub_healthy,
        "openshift_developer_hub_subscription_present": openshift_developer_hub_subscription_present,
        "openshift_developer_hub_namespace_present": openshift_developer_hub_namespace_present,
        "openshift_developer_hub_crd_present": openshift_developer_hub_crd_present,
        "openshift_developer_hub_context_present": openshift_developer_hub_context_present,
        "openshift_developer_hub_backstage_count": openshift_developer_hub_backstage_count,
        "openshift_developer_hub_ready_backstage_count": openshift_developer_hub_ready_backstage_count,
        "openshift_developer_hub_backstage_present": openshift_developer_hub_backstage_present,
        "openshift_developer_hub_workload_present": openshift_developer_hub_workload_present,
        "openshift_dev_spaces_present": openshift_dev_spaces_present,
        "openshift_dev_spaces_healthy": openshift_dev_spaces_healthy,
        "openshift_dev_spaces_subscription_present": openshift_dev_spaces_subscription_present,
        "openshift_dev_spaces_namespace_present": openshift_dev_spaces_namespace_present,
        "openshift_dev_spaces_context_present": openshift_dev_spaces_context_present,
        "openshift_dev_spaces_checluster_present": openshift_dev_spaces_checluster_present,
        "openshift_dev_spaces_devworkspace_present": openshift_dev_spaces_devworkspace_present,
        "openshift_dev_spaces_workspace_operator_config_present": openshift_dev_spaces_workspace_operator_config_present,
        "openshift_dev_spaces_routing_present": openshift_dev_spaces_routing_present,
        "cert_manager_operator_present": bool("openshift-cert-manager-operator" in subscription_packages or "cert-manager-operator" in namespace_names or "cert-manager" in namespace_names),
        "cert_manager_subscription_present": "openshift-cert-manager-operator" in subscription_packages,
        "cert_manager_operator_namespace_present": "cert-manager-operator" in namespace_names,
        "cert_manager_namespace_present": "cert-manager" in namespace_names,
        "openshift_data_foundation_present": openshift_data_foundation_present,
        "openshift_virtualization_present": openshift_virtualization_present,
        "openshift_virtualization_healthy": openshift_virtualization_healthy,
        "openshift_virtualization_context_present": openshift_virtualization_context_present,
        "openshift_virtualization_subscription_present": virtualization_operator_subscription_present,
        "openshift_virtualization_namespace_present": virtualization_namespace_present,
        "openshift_virtualization_platform_present": virtualization_platform_present,
        "openshift_virtualization_workload_present": virtualization_workload_present,
        "openshift_virtualization_supporting_stack_present": virtualization_supporting_stack_present,
        "openshift_virtualization_ready_kubevirt_count": len(ready_kubevirts),
        "openshift_virtualization_ready_hyperconverged_count": len(ready_hyperconvergeds),
        "ingresscontroller_count": len(ingresscontroller_summary),
        "nondefault_ingresscontroller_count": nondefault_ingresscontroller_count,
        "ingress_topology_signal_count": len(ingress_topology_signals),
        "ingress_topology_healthy": ingress_topology_healthy,
        "openshift_ai_present": openshift_ai_present,
        "openshift_ai_healthy": openshift_ai_healthy,
        "openshift_ai_context_present": openshift_ai_context_present,
        "openshift_ai_subscription_present": openshift_ai_subscription_present,
        "openshift_ai_namespace_present": openshift_ai_namespace_present,
        "openshift_ai_ready_datasciencecluster_count": len(ready_datascienceclusters),
        "openshift_ai_ready_dscinitialization_count": len(ready_dscinitializations),
        "openshift_aap_present": openshift_aap_present,
        "openshift_custom_metrics_autoscaler_present": openshift_custom_metrics_autoscaler_present,
        "openshift_custom_metrics_autoscaler_context_present": openshift_custom_metrics_autoscaler_context_present,
        "openshift_custom_metrics_autoscaler_subscription_present": keda_subscription_present,
        "openshift_custom_metrics_autoscaler_namespace_present": keda_namespace_present,
        "openshift_custom_metrics_autoscaler_crd_present": keda_crd_present,
        "openshift_custom_metrics_autoscaler_workload_present": keda_workload_present,
        "ibm_cloud_pak_business_automation_present": ibm_cloud_pak_business_automation_present,
        "ibm_cloud_pak_business_automation_healthy": ibm_cloud_pak_business_automation_healthy,
        "service_mesh_control_plane_present": service_mesh_present,
        "service_mesh_control_plane_healthy": service_mesh_healthy,
        "service_mesh_control_plane_context_present": service_mesh_context_present,
        "service_mesh_control_plane_resource_present": service_mesh_control_plane_present,
        "service_mesh_membership_present": service_mesh_membership_present,
        "service_mesh_subscription_present": service_mesh_subscription_present,
        "service_mesh_crd_present": service_mesh_crd_present,
        "service_mesh_ready_control_plane_count": len(ready_service_mesh_control_planes),
        "openshift_serverless_present": serverless_present,
        "openshift_serverless_healthy": serverless_healthy,
        "openshift_serverless_context_present": serverless_context_present,
        "openshift_serverless_control_plane_present": serverless_control_plane_present,
        "openshift_serverless_workload_present": serverless_workload_present,
        "openshift_serverless_subscription_present": serverless_subscription_present,
        "openshift_serverless_namespace_present": serverless_namespace_present,
        "openshift_serverless_crd_present": serverless_crd_present,
        "openshift_serverless_ready_knativeserving_count": len(ready_knativeservings),
        "openshift_serverless_ready_knativeeventing_count": len(ready_knativeeventings),
        "advanced_cluster_security_present": advanced_cluster_security_present,
        "advanced_cluster_security_context_present": advanced_cluster_security_context_present,
        "qualys_subscription_present": qualys_subscription_present,
        "qualys_namespace_present": qualys_namespace_present,
        "qualys_crd_present": qualys_crd_present,
        "qualys_operator_workload_present": qualys_operator_workload_present,
        "qualys_workload_present": qualys_workload_present,
        "qualys_k8s_mode_arg_present": qualys_k8s_mode_arg_present,
        "qualys_privileged_security_context_present": qualys_privileged_security_context_present,
        "qualys_service_account_config_present": qualys_service_account_config_present,
        "qualys_activation_config_present": qualys_activation_config_present,
        "qualys_required_deployment_configuration_present": qualys_required_deployment_configuration_present,
        "qualys_scanning_agents_present": qualys_scanning_agents_present,
        "qualys_scanning_agents_context_present": qualys_scanning_agents_context_present,
        "prisma_subscription_present": prisma_subscription_present,
        "prisma_namespace_present": prisma_namespace_present,
        "prisma_crd_present": prisma_crd_present,
        "prisma_workload_present": prisma_workload_present,
        "aqua_subscription_present": aqua_subscription_present,
        "aqua_namespace_present": aqua_namespace_present,
        "aqua_crd_present": aqua_crd_present,
        "aqua_workload_present": aqua_workload_present,
        "splunk_namespace_present": splunk_namespace_present,
        "splunk_crd_present": splunk_crd_present,
        "splunk_operator_workload_present": splunk_operator_workload_present,
        "splunk_workload_present": splunk_workload_present,
        "splunk_cluster_name_config_present": splunk_cluster_name_config_present,
        "splunk_destination_config_present": splunk_destination_config_present,
        "splunk_required_deployment_configuration_present": splunk_required_deployment_configuration_present,
        "splunk_context_present": splunk_context_present,
        "splunk_observability_present": splunk_observability_present,
        "windows_container_workloads_present": windows_workloads_present,
        "windows_container_workloads_healthy": windows_workloads_healthy,
        "windows_container_workloads_context_present": windows_workloads_context_present,
        "windows_nodes_present": windows_nodes_present,
        "windows_workload_present": windows_workload_present,
        "windows_operator_namespace_present": windows_operator_namespace_present,
        "windows_operator_subscription_present": windows_operator_subscription_present,
        "gpu_accelerated_workloads_present": gpu_workloads_present,
        "gpu_accelerated_workloads_healthy": gpu_workloads_healthy,
        "gpu_accelerated_workloads_context_present": gpu_workloads_context_present,
        "gpu_capacity_present": gpu_capacity_present,
        "gpu_workload_present": gpu_workload_present,
        "gpu_operator_subscription_present": gpu_operator_subscription_present,
        "gpu_operator_workload_present": gpu_operator_workload_present,
        "gpu_nvidia_clusterpolicy_count": len(nvidiaclusterpolicies),
        "sandboxed_container_workloads_present": sandboxed_containers_present,
        "sandboxed_container_workloads_healthy": sandboxed_containers_healthy,
        "sandboxed_container_workloads_context_present": sandboxed_containers_context_present,
        "sandboxed_container_workloads_kataconfig_count": len(kataconfigs),
        "sandboxed_container_workloads_ready_kataconfig_count": len(ready_kataconfigs),
        "sandboxed_container_workload_count": len(kata_workload_objects),
        "sandboxed_container_operator_namespace_present": sandboxed_operator_namespace_present,
        "sandboxed_container_operator_subscription_present": sandboxed_operator_subscription_present,
        "kubelet_configuration_governance_present": kubelet_configuration_governance_present,
        "kubelet_configuration_governance_healthy": kubelet_configuration_governance_healthy,
        "kubeletconfig_count": len(kubeletconfigs),
        "kubeletconfig_targeted_count": len(kubeletconfig_targeted),
        "kubeletconfig_density_tuned_count": len(kubeletconfig_density_tuned),
        "kubeletconfig_reservation_tuned_count": len(kubeletconfig_reservation_tuned),
        "kubeletconfig_eviction_tuned_count": len(kubeletconfig_eviction_tuned),
        "kubeletconfig_runtime_policy_tuned_count": len(kubeletconfig_runtime_policy_tuned),
        "node_tuning_operator_present": node_tuning_present,
        "node_tuning_operator_healthy": node_tuning_healthy,
        "node_tuning_operator_context_present": node_tuning_context_present,
        "node_tuning_tuned_count": len(tuneds),
        "node_tuning_custom_tuned_count": len(custom_tuned_config_resources),
        "node_tuning_tunedprofile_count": len(tunedprofiles),
        "node_tuning_performanceprofile_count": len(performanceprofiles),
        "node_tuning_ready_performanceprofile_count": len(ready_performanceprofiles),
        "node_tuning_namespace_present": node_tuning_namespace_present,
        "node_tuning_crd_present": node_tuning_crd_present,
        "kubernetes_nmstate_networking_present": nmstate_present,
        "kubernetes_nmstate_networking_healthy": nmstate_healthy,
        "kubernetes_nmstate_networking_context_present": nmstate_context_present,
        "kubernetes_nmstate_nmstate_count": len(nmstates),
        "kubernetes_nmstate_nodenetworkconfigurationpolicy_count": len(nodenetworkconfigurationpolicies),
        "kubernetes_nmstate_ready_nodenetworkconfigurationpolicy_count": len(ready_nodenetworkconfigurationpolicies),
        "kubernetes_nmstate_nodenetworkstate_count": len(nodenetworkstates),
        "kubernetes_nmstate_namespace_present": nmstate_namespace_present,
        "kubernetes_nmstate_subscription_present": nmstate_operator_subscription_present,
        "cost_management_operator_present": cost_management_present,
        "cost_management_operator_healthy": cost_management_healthy,
        "cost_management_operator_context_present": cost_management_context_present,
        "cost_managementmetricsconfig_count": len(costmanagementmetricsconfigs),
        "ready_cost_managementmetricsconfig_count": len(ready_cost_management_configs),
        "cost_management_subscription_present": cost_management_subscription_present,
        "cost_management_namespace_present": cost_management_namespace_present,
        "cost_management_crd_present": cost_management_crd_present,
        "descheduler_operator_present": descheduler_present,
        "descheduler_operator_healthy": descheduler_healthy,
        "descheduler_operator_context_present": descheduler_context_present,
        "descheduler_count": len(deschedulers),
        "configured_descheduler_count": len(configured_deschedulers),
        "descheduler_namespace_present": descheduler_namespace_present,
        "descheduler_subscription_present": descheduler_subscription_present,
        "namespace_network_policy_baseline_present": network_policy_baseline_present,
        "namespace_egress_controls_present": egress_control_present,
        "namespace_egress_controls_healthy": egress_control_healthy,
        "compliancesuite_count": len(compliancesuites),
        "identity_provider_count": idp_count,
        "insights_healthy": insights_healthy,
    }
}))
