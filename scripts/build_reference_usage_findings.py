#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys


def compile_matcher(pattern: str):
    regex = re.compile(pattern or r"^$")
    return regex.match


def unique_append(target: list[str], values: list[str]):
    seen = set(target)
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            target.append(text)
            seen.add(text)


def ensure_bucket(store: dict[str, list[str]], namespace: str) -> list[str]:
    if namespace not in store:
        store[namespace] = []
    return store[namespace]


def pod_spec_from_item(item: dict, template: bool = False) -> dict:
    spec = item.get("spec") or {}
    if template:
        return ((spec.get("template") or {}).get("spec") or {})
    return spec


def collect_refs_from_pod_spec(pod_spec: dict) -> tuple[list[str], list[str], list[str]]:
    containers = (pod_spec.get("containers") or []) + (pod_spec.get("initContainers") or [])
    volumes = pod_spec.get("volumes") or []

    configmaps: list[str] = []
    secrets: list[str] = []

    for volume in volumes:
        config_map = volume.get("configMap") or {}
        secret = volume.get("secret") or {}
        unique_append(configmaps, [config_map.get("name")])
        unique_append(secrets, [secret.get("secretName")])

    for container in containers:
        for env_from in container.get("envFrom") or []:
            unique_append(configmaps, [((env_from.get("configMapRef") or {}).get("name"))])
            unique_append(secrets, [((env_from.get("secretRef") or {}).get("name"))])
        for env in container.get("env") or []:
            value_from = env.get("valueFrom") or {}
            unique_append(configmaps, [((value_from.get("configMapKeyRef") or {}).get("name"))])
            unique_append(secrets, [((value_from.get("secretKeyRef") or {}).get("name"))])

    service_account = str(pod_spec.get("serviceAccountName") or "default")
    return configmaps, secrets, [service_account]


def build_reference_maps(data: dict) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    referenced_configmaps: dict[str, list[str]] = {}
    referenced_secrets: dict[str, list[str]] = {}
    referenced_serviceaccounts: dict[str, list[str]] = {}

    for item in data.get("pods", []) or []:
        namespace = str(((item.get("metadata") or {}).get("namespace")) or "")
        cm_names, secret_names, serviceaccounts = collect_refs_from_pod_spec(pod_spec_from_item(item, template=False))
        unique_append(ensure_bucket(referenced_configmaps, namespace), cm_names)
        unique_append(ensure_bucket(referenced_secrets, namespace), secret_names)
        unique_append(ensure_bucket(referenced_serviceaccounts, namespace), serviceaccounts)

    for collection_name in ("deployments", "statefulsets", "daemonsets"):
        for item in data.get(collection_name, []) or []:
            namespace = str(((item.get("metadata") or {}).get("namespace")) or "")
            cm_names, secret_names, serviceaccounts = collect_refs_from_pod_spec(pod_spec_from_item(item, template=True))
            unique_append(ensure_bucket(referenced_configmaps, namespace), cm_names)
            unique_append(ensure_bucket(referenced_secrets, namespace), secret_names)
            unique_append(ensure_bucket(referenced_serviceaccounts, namespace), serviceaccounts)

    return referenced_configmaps, referenced_secrets, referenced_serviceaccounts


def collect_unused_findings(data: dict, exclude_match, referenced_configmaps, referenced_secrets, referenced_serviceaccounts):
    likely_unused_configmaps = []
    likely_unused_serviceaccounts = []
    likely_unused_secrets = []

    for item in data.get("configmaps", []) or []:
        metadata = item.get("metadata") or {}
        namespace = str(metadata.get("namespace") or "")
        name = str(metadata.get("name") or "")
        if not exclude_match(namespace) and name not in referenced_configmaps.get(namespace, []):
            likely_unused_configmaps.append({"namespace": namespace, "name": name})

    for item in data.get("serviceaccounts", []) or []:
        metadata = item.get("metadata") or {}
        namespace = str(metadata.get("namespace") or "")
        name = str(metadata.get("name") or "")
        if (
            not exclude_match(namespace)
            and name not in {"default", "builder", "deployer"}
            and name not in referenced_serviceaccounts.get(namespace, [])
        ):
            likely_unused_serviceaccounts.append({"namespace": namespace, "name": name})

    skip_secret_re = re.compile(r"^builder-|^default-token-|^deployer-token-|^pipeline-|^sh\.helm\.release\.v1\.")
    for item in data.get("secrets", []) or []:
        metadata = item.get("metadata") or {}
        namespace = str(metadata.get("namespace") or "")
        name = str(metadata.get("name") or "")
        secret_type = str(item.get("type") or "")
        if (
            not exclude_match(namespace)
            and secret_type not in {"kubernetes.io/service-account-token", "kubernetes.io/dockercfg", "kubernetes.io/dockerconfigjson"}
            and not skip_secret_re.search(name)
            and name not in referenced_secrets.get(namespace, [])
        ):
            likely_unused_secrets.append({"namespace": namespace, "name": name, "type": secret_type})

    return likely_unused_configmaps, likely_unused_serviceaccounts, likely_unused_secrets


def collect_privileged_access(data: dict, exclude_match):
    privileged_serviceaccount_access = []
    privileged_user_access = []
    privileged_group_access = []

    for item in (data.get("clusterrolebindings", []) or []) + (data.get("rolebindings", []) or []):
        role_ref = item.get("roleRef") or {}
        if str(role_ref.get("kind") or "") != "ClusterRole" or str(role_ref.get("name") or "") != "cluster-admin":
            continue

        metadata = item.get("metadata") or {}
        binding_kind = str(item.get("kind") or "Binding")
        binding_name = str(metadata.get("name") or "unknown")
        binding_namespace = str(metadata.get("namespace") or "")
        binding_scope = "cluster-wide" if not binding_namespace else f"namespace {binding_namespace}"
        grant_source = f"{binding_kind}/{binding_name}" if not binding_namespace else f"{binding_kind}/{binding_namespace}/{binding_name}"

        for subject in item.get("subjects") or []:
            entry = {
                "binding_name": binding_name,
                "grant_source": grant_source,
                "binding_scope": binding_scope,
                "access_role": "cluster-admin",
                "access_level": "privileged",
            }
            kind = str(subject.get("kind") or "")
            name = str(subject.get("name") or "")
            if kind == "ServiceAccount":
                namespace = str(subject.get("namespace") or "")
                if namespace and not exclude_match(namespace):
                    privileged_serviceaccount_access.append({"kind": kind, "name": name, "namespace": namespace, **entry})
            elif kind == "User":
                if not re.match(r"^(system:|kube:|openshift:)", name):
                    privileged_user_access.append({"kind": kind, "name": name, **entry})
            elif kind == "Group":
                if not re.match(r"^(system:|kube:|openshift:)", name):
                    privileged_group_access.append({"kind": kind, "name": name, **entry})

    return privileged_serviceaccount_access, privileged_user_access, privileged_group_access


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_reference_usage_findings.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_match = compile_matcher(data.get("user_namespaces_exclude_regex") or r"^$")
    referenced_configmaps, referenced_secrets, referenced_serviceaccounts = build_reference_maps(data)
    likely_unused_configmaps, likely_unused_serviceaccounts, likely_unused_secrets = collect_unused_findings(
        data,
        exclude_match,
        referenced_configmaps,
        referenced_secrets,
        referenced_serviceaccounts,
    )
    privileged_serviceaccount_access, privileged_user_access, privileged_group_access = collect_privileged_access(
        data,
        exclude_match,
    )

    print(
        json.dumps(
            {
                "referenced_configmaps": referenced_configmaps,
                "referenced_secrets": referenced_secrets,
                "referenced_serviceaccounts": referenced_serviceaccounts,
                "likely_unused_configmaps": likely_unused_configmaps,
                "likely_unused_serviceaccounts": likely_unused_serviceaccounts,
                "likely_unused_secrets": likely_unused_secrets,
                "privileged_serviceaccount_access": privileged_serviceaccount_access,
                "privileged_user_access": privileged_user_access,
                "privileged_group_access": privileged_group_access,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
