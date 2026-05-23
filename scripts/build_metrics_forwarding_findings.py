#!/usr/bin/env python3
import json
import sys


def is_external_url(url):
    if not url:
        return False
    s = str(url).lower()
    return not (".svc" in s or ".cluster.local" in s or s.startswith("http://localhost") or s.startswith("https://localhost"))


def build(data):
    findings = []
    cluster_external = [item for item in data["cluster_remote_write"] if is_external_url(item.get("url", ""))]
    user_external = [item for item in data["user_remote_write"] if is_external_url(item.get("url", ""))]

    if bool(data.get("require_external_metrics_remote_write")) and not data.get("vendor_managed_present"):
        if not data["cluster_remote_write"]:
            findings.append({
                "issue": "cluster-metrics-remote-write-missing",
                "detail": "cluster-monitoring-config has no prometheusK8s.remoteWrite target"
            })
        elif not cluster_external:
            findings.append({
                "issue": "cluster-metrics-not-forwarded-external",
                "detail": "prometheusK8s.remoteWrite targets appear cluster-local only"
            })

        if not data["user_remote_write"]:
            findings.append({
                "issue": "user-workload-metrics-remote-write-missing",
                "detail": "user-workload-monitoring-config has no prometheus.remoteWrite target"
            })
        elif not user_external:
            findings.append({
                "issue": "user-workload-metrics-not-forwarded-external",
                "detail": "user workload remoteWrite targets appear cluster-local only"
            })

    return {
        "findings": findings,
        "cluster_external_count": len(cluster_external),
        "user_external_count": len(user_external)
    }


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))


if __name__ == "__main__":
    main()
