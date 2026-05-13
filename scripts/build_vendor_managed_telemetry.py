#!/usr/bin/env python3
import json
import sys


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    def crd_has(group_fragment):
        target = str(group_fragment).lower()
        for item in data.get("crds", []) or []:
            spec = item.get("spec", {}) or {}
            group = str(spec.get("group") or "").lower()
            if target in group:
                return True
        return False

    def namespace_has(fragment):
        target = str(fragment).lower()
        return any(target in str((item.get("metadata", {}) or {}).get("name") or "").lower() for item in data.get("namespaces", []) or [] if isinstance(item, dict))

    def workload_has_any(keywords):
        needles = [str(item).lower() for item in keywords]
        for kind in ("pods", "deployments", "daemonsets", "statefulsets"):
            for item in data.get(kind, []) or []:
                meta = item.get("metadata", {}) or {}
                text = " ".join([str(meta.get("namespace") or ""), str(meta.get("name") or "")]).lower()
                if any(needle in text for needle in needles):
                    return True
        return False

    dynatrace_present = bool(
        (data.get("dynakubes") or [])
        or (data.get("edgeconnects") or [])
        or crd_has("dynatrace.com")
        or namespace_has("dynatrace")
        or workload_has_any(
            [
                "dynatrace-operator",
                "dynakube",
                "oneagent",
                "activegate",
                "dynatrace-webhook",
                "dynatrace-otel-collector",
                "dynatrace-logmonitoring",
                "dynatrace-extension-controller",
                "dynatrace-extensions-collector",
                "dynatrace-node-config-collector",
            ]
        )
    )
    datadog_present = bool((data.get("datadogagents") or []) or crd_has("datadoghq.com") or namespace_has("datadog") or workload_has_any(["datadog"]))
    appdynamics_present = bool((data.get("clusteragents") or []) or (data.get("infravizs") or []) or crd_has("appdynamics.com") or namespace_has("appdynamics"))
    splunk_present = bool(crd_has("enterprise.splunk.com") or crd_has("monitoring.splunk.com") or namespace_has("splunk") or workload_has_any(["splunk-otel-collector", "splunk-connect-for-kubernetes", "splunk-cluster-receiver", "splunk-kubernetes-objects", "splunk-enterprise", "splunk-indexer", "splunk-search-head"]))
    loki_present = bool((data.get("lokistacks") or []) or crd_has("loki.grafana.com") or namespace_has("openshift-logging") or namespace_has("logging-loki"))
    metrics_vendors = []
    log_vendors = []
    if dynatrace_present:
        metrics_vendors.append("dynatrace")
        log_vendors.append("dynatrace")
    if datadog_present:
        metrics_vendors.append("datadog")
        log_vendors.append("datadog")
    if appdynamics_present:
        metrics_vendors.append("appdynamics")
    if splunk_present:
        metrics_vendors.append("splunk")
        log_vendors.append("splunk")
    if loki_present:
        log_vendors.append("loki")
    print(json.dumps({"vendor_managed_metrics_forwarding_present": len(metrics_vendors) > 0, "vendor_managed_log_forwarding_present": len(log_vendors) > 0, "metrics_vendor_names": metrics_vendors, "log_vendor_names": log_vendors}))


if __name__ == "__main__":
    main()
