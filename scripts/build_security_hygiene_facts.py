#!/usr/bin/env python3
import json
import re
import sys


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def nested_defined(data, path):
    value = data
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return False
        value = value.get(part)
    return True


def nested_get(data, path, default=None):
    value = data
    for part in path:
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return value if value is not None else default


def increment(counter, key, amount=1):
    counter[key] = int(counter.get(key, 0)) + int(amount)


SCC_PRIVILEGE_RANKS = {
    "privileged": 100,
    "hostmount-anyuid": 90,
    "hostnetwork": 80,
    "hostaccess": 70,
    "anyuid": 60,
    "nonroot-v2": 30,
    "nonroot": 30,
    "restricted-v2": 10,
    "restricted": 10,
    "not-collected": 0,
}


def pod_scc(metadata):
    annotations = as_dict(as_dict(metadata).get("annotations"))
    return str(
        annotations.get("openshift.io/scc")
        or annotations.get("security.openshift.io/scc.podSecurityLabelSync")
        or "not-collected"
    )


def scc_privilege_rank(scc):
    name = str(scc or "not-collected").strip()
    if not name:
        return 0
    return SCC_PRIVILEGE_RANKS.get(name, 40)


def pod_security_finding(namespace, pod_name, scc, issue, detail):
    return {
        "namespace": namespace,
        "pod": pod_name,
        "scc": scc,
        "scc_privilege_rank": scc_privilege_rank(scc),
        "issue": issue,
        "detail": detail,
    }


def namespace_counts(items):
    counts = {}
    for item in as_list(items):
        namespace = str(nested_get(item, ["metadata", "namespace"], "") or "")
        increment(counts, namespace)
    return counts


def networkpolicy_counts(items):
    networkpolicy_namespace_counts = {}
    ingress_policy_namespace_counts = {}
    egress_policy_namespace_counts = {}

    for item in as_list(items):
        namespace = str(nested_get(item, ["metadata", "namespace"], "") or "")
        policy_types = nested_get(item, ["spec", "policyTypes"], ["Ingress"])
        if not isinstance(policy_types, list):
            policy_types = ["Ingress"]
        increment(networkpolicy_namespace_counts, namespace)
        increment(ingress_policy_namespace_counts, namespace, 1 if "Ingress" in policy_types else 0)
        increment(egress_policy_namespace_counts, namespace, 1 if "Egress" in policy_types else 0)

    return {
        "networkpolicy_namespace_counts": networkpolicy_namespace_counts,
        "ingress_policy_namespace_counts": ingress_policy_namespace_counts,
        "egress_policy_namespace_counts": egress_policy_namespace_counts,
    }


def namespace_hygiene(data, network_counts, quota_counts, limitrange_counts):
    namespace_pod_counts = as_dict(data.get("namespace_pod_counts"))
    user_namespace_names = as_list(data.get("user_namespace_names"))

    result = {
        "namespaces_without_networkpolicy": [],
        "namespaces_without_resourcequota": [],
        "namespaces_without_limitrange": [],
        "empty_user_namespaces": [],
        "namespaces_missing_ingress_policies": [],
        "namespaces_missing_egress_policies": [],
    }

    ingress_counts = as_dict(network_counts.get("ingress_policy_namespace_counts"))
    egress_counts = as_dict(network_counts.get("egress_policy_namespace_counts"))
    policy_counts = as_dict(network_counts.get("networkpolicy_namespace_counts"))

    for namespace in user_namespace_names:
        policy_count = int(policy_counts.get(namespace, 0) or 0)
        if policy_count == 0:
            result["namespaces_without_networkpolicy"].append(namespace)
        if int(quota_counts.get(namespace, 0) or 0) == 0:
            result["namespaces_without_resourcequota"].append(namespace)
        if int(limitrange_counts.get(namespace, 0) or 0) == 0:
            result["namespaces_without_limitrange"].append(namespace)
        if int(namespace_pod_counts.get(namespace, 0) or 0) == 0:
            result["empty_user_namespaces"].append(namespace)
        if policy_count > 0 and int(ingress_counts.get(namespace, 0) or 0) == 0:
            result["namespaces_missing_ingress_policies"].append(namespace)
        if policy_count > 0 and int(egress_counts.get(namespace, 0) or 0) == 0:
            result["namespaces_missing_egress_policies"].append(namespace)

    return result


def basic_pod_findings(data):
    pods = as_list(data.get("pods"))
    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    security_findings = []
    workload_practice_findings = []

    for item in pods:
        metadata = as_dict(item.get("metadata"))
        namespace = str(metadata.get("namespace") or "")
        pod_name = metadata.get("name")
        scc = pod_scc(metadata)
        if exclude_re.match(namespace):
            continue

        spec = as_dict(item.get("spec"))
        containers = as_list(spec.get("containers")) + as_list(spec.get("initContainers"))

        privileged_names = []
        run_as_root_names = []
        containers_without_requests = []
        containers_without_limits = []
        for container in containers:
            name = nested_get(container, ["name"], None)
            security_context = as_dict(container.get("securityContext"))
            if "privileged" in security_context and security_context.get("privileged") is True:
                privileged_names.append(name)
            if "runAsUser" in security_context and security_context.get("runAsUser") == 0:
                run_as_root_names.append(name)
            if not nested_defined(container, ["resources", "requests"]):
                containers_without_requests.append(name)
            if not nested_defined(container, ["resources", "limits"]):
                containers_without_limits.append(name)

        hostpath_volume_names = []
        for volume in as_list(spec.get("volumes")):
            if isinstance(volume, dict) and "hostPath" in volume:
                hostpath_volume_names.append(volume.get("name"))

        if privileged_names:
            security_findings.append(pod_security_finding(
                namespace,
                pod_name,
                scc,
                "privileged-containers",
                ", ".join(str(value) for value in privileged_names),
            ))
        if spec.get("hostNetwork", False):
            security_findings.append(pod_security_finding(namespace, pod_name, scc, "host-network", "hostNetwork=true"))
        if spec.get("hostPID", False):
            security_findings.append(pod_security_finding(namespace, pod_name, scc, "host-pid", "hostPID=true"))
        if spec.get("hostIPC", False):
            security_findings.append(pod_security_finding(namespace, pod_name, scc, "host-ipc", "hostIPC=true"))
        if hostpath_volume_names:
            security_findings.append(pod_security_finding(
                namespace,
                pod_name,
                scc,
                "hostpath-volume",
                ", ".join(str(value) for value in hostpath_volume_names),
            ))
        if run_as_root_names:
            security_findings.append(pod_security_finding(
                namespace,
                pod_name,
                scc,
                "run-as-root",
                ", ".join(str(value) for value in run_as_root_names),
            ))

        if containers_without_requests:
            workload_practice_findings.append({
                "namespace": namespace,
                "pod": pod_name,
                "issue": "missing-resource-requests",
                "detail": ", ".join(str(value) for value in containers_without_requests),
            })
        if containers_without_limits:
            workload_practice_findings.append({
                "namespace": namespace,
                "pod": pod_name,
                "issue": "missing-resource-limits",
                "detail": ", ".join(str(value) for value in containers_without_limits),
            })

    return {
        "security_findings": security_findings,
        "workload_practice_findings": workload_practice_findings,
    }


def build(data):
    network_counts = networkpolicy_counts(data.get("networkpolicies"))
    quota_counts = namespace_counts(data.get("resourcequotas"))
    limitrange_counts = namespace_counts(data.get("limitranges"))
    hygiene = namespace_hygiene(data, network_counts, quota_counts, limitrange_counts)
    findings = basic_pod_findings(data)

    result = {}
    result.update(network_counts)
    result["resourcequota_namespace_counts"] = quota_counts
    result["limitrange_namespace_counts"] = limitrange_counts
    result.update(hygiene)
    result.update(findings)
    return result


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_security_hygiene_facts.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
