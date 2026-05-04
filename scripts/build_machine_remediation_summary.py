#!/usr/bin/env python3
import json
import sys


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    machine_sets = data.get("machinesets", []) or []
    mhcs = data.get("machinehealthchecks", []) or []
    findings = []
    summary = []

    if machine_sets and not mhcs:
        findings.append({
            "issue": "machinehealthcheck-missing",
            "detail": "Machine API-managed worker pools were found but no MachineHealthCheck resource was collected"
        })

    for item in mhcs:
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        paused = bool((meta.get("annotations") or {}).get("cluster.x-k8s.io/paused") == "true" or spec.get("paused", False))
        selector = spec.get("selector") or {}
        empty_selector = not ((selector.get("matchLabels") or {}) or (selector.get("matchExpressions") or []))
        entry = {
            "namespace": meta.get("namespace", ""),
            "name": meta.get("name", ""),
            "paused": paused,
            "max_unhealthy": spec.get("maxUnhealthy", ""),
            "expected_machines": status.get("expectedMachines", "unknown"),
            "current_healthy": status.get("currentHealthy", "unknown"),
            "selector_empty": empty_selector,
        }
        summary.append(entry)
        if paused:
            findings.append({
                "issue": "machinehealthcheck-paused",
                "detail": f"{entry['namespace']}/{entry['name']} is paused"
            })
        if empty_selector:
            findings.append({
                "issue": "machinehealthcheck-selector-empty",
                "detail": f"{entry['namespace']}/{entry['name']} has no selector"
            })

    print(json.dumps({
        "machinehealthcheck_summary": sorted(summary, key=lambda item: (item["namespace"], item["name"])),
        "machine_healthcheck_findings": findings,
    }))


if __name__ == "__main__":
    main()
