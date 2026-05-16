#!/usr/bin/env python3
import json
import sys


def is_platform_namespace(ns):
    return ns.startswith("openshift-") or ns.startswith("kube-") or ns in {"default", "openshift"}


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    sccs = data.get("sccs") or []
    pods = data.get("pods") or []
    summary = []
    findings = []
    pod_findings = []

    risky_sccs = {}
    for scc in sccs:
        meta = scc.get("metadata", {}) or {}
        users = scc.get("users") or []
        groups = scc.get("groups") or []
        volumes = scc.get("volumes") or []
        run_as_user = ((scc.get("runAsUser") or {}).get("type") or "Unknown")
        name = meta.get("name", "unknown")
        privileged = bool(scc.get("allowPrivilegedContainer", False))
        host_dir = bool(scc.get("allowHostDirVolumePlugin", False))
        host_network = bool(scc.get("allowHostNetwork", False))
        host_pid = bool(scc.get("allowHostPID", False))
        host_ipc = bool(scc.get("allowHostIPC", False))
        anyuid = run_as_user == "RunAsAny"
        all_volumes = "*" in volumes
        risk_flags = []
        if privileged:
            risk_flags.append("privileged")
        if anyuid:
            risk_flags.append("runAsAny")
        if host_dir:
            risk_flags.append("hostPath")
        if host_network:
            risk_flags.append("hostNetwork")
        if host_pid:
            risk_flags.append("hostPID")
        if host_ipc:
            risk_flags.append("hostIPC")
        if all_volumes:
            risk_flags.append("allVolumes")
        summary.append(
            {
                "name": name,
                "priority": meta.get("annotations", {}).get("kubernetes.io/description", ""),
                "privileged": privileged,
                "anyuid": anyuid,
                "host_network": host_network,
                "host_pid": host_pid,
                "host_ipc": host_ipc,
                "host_dir": host_dir,
                "all_volumes": all_volumes,
                "user_count": len(users),
                "group_count": len(groups),
                "risk_summary": ", ".join(risk_flags) if risk_flags else "restricted",
            }
        )
        if risk_flags:
            risky_sccs[name] = ", ".join(risk_flags)
        if not risk_flags:
            continue
        for subject in users:
            if subject.startswith("system:serviceaccount:"):
                parts = subject.split(":")
                if len(parts) >= 4:
                    ns = parts[2]
                    sa = parts[3]
                    if not is_platform_namespace(ns):
                        findings.append(
                            {
                                "scc": name,
                                "subject_kind": "ServiceAccount",
                                "subject": f"{ns}/{sa}",
                                "risk_summary": ", ".join(risk_flags),
                            }
                        )
            elif not subject.startswith("system:"):
                findings.append(
                    {
                        "scc": name,
                        "subject_kind": "User",
                        "subject": subject,
                        "risk_summary": ", ".join(risk_flags),
                    }
                )
        for subject in groups:
            if subject.startswith("system:serviceaccounts:"):
                parts = subject.split(":")
                if len(parts) >= 3:
                    ns = parts[2]
                    if not is_platform_namespace(ns):
                        findings.append(
                            {
                                "scc": name,
                                "subject_kind": "ServiceAccount group",
                                "subject": ns,
                                "risk_summary": ", ".join(risk_flags),
                            }
                        )
            elif not subject.startswith("system:"):
                findings.append(
                    {
                        "scc": name,
                        "subject_kind": "Group",
                        "subject": subject,
                        "risk_summary": ", ".join(risk_flags),
                    }
                )

    for pod in pods:
        meta = pod.get("metadata", {}) or {}
        ns = str(meta.get("namespace") or "")
        if is_platform_namespace(ns):
            continue
        annotations = meta.get("annotations", {}) or {}
        scc_name = annotations.get("openshift.io/scc") or annotations.get("security.openshift.io/scc.podSecurityLabelSync") or ""
        if scc_name not in risky_sccs:
            continue
        pod_findings.append(
            {
                "namespace": ns,
                "pod": str(meta.get("name") or "unknown"),
                "service_account": str(((pod.get("spec") or {}).get("serviceAccountName")) or "default"),
                "scc": scc_name,
                "risk_summary": risky_sccs[scc_name],
            }
        )

    print(
        json.dumps(
            {
                "scc_posture_summary": sorted(summary, key=lambda item: item["name"]),
                "scc_grant_findings": sorted(
                    findings, key=lambda item: (item["scc"], item["subject_kind"], item["subject"])
                ),
                "scc_pod_findings": sorted(
                    pod_findings, key=lambda item: (item["scc"], item["namespace"], item["pod"])
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
