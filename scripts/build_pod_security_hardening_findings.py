#!/usr/bin/env python3
import json
import re
import sys


def merged_security_context(pod_sc, container_sc):
    pod_sc = pod_sc or {}
    container_sc = container_sc or {}
    return {
        "seccompProfile": container_sc.get("seccompProfile", pod_sc.get("seccompProfile")),
        "runAsNonRoot": container_sc.get("runAsNonRoot", pod_sc.get("runAsNonRoot")),
        "runAsUser": container_sc.get("runAsUser", pod_sc.get("runAsUser")),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_pod_security_hardening_findings.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    findings = []

    for item in data.get("pods", []):
        metadata = item.get("metadata", {}) or {}
        namespace = str(metadata.get("namespace") or "")
        if exclude_re.search(namespace):
            continue

        pod = str(metadata.get("name") or "unknown")
        annotations = metadata.get("annotations", {}) or {}
        scc = str(annotations.get("openshift.io/scc") or "not-collected")
        spec = item.get("spec", {}) or {}
        pod_sc = spec.get("securityContext", {}) or {}
        containers = (spec.get("containers") or []) + (spec.get("initContainers") or [])

        missing_seccomp = []
        unconfined_seccomp = []
        privilege_escalation_not_disabled = []
        run_as_non_root_not_set = []
        read_only_rootfs_not_enabled = []
        capabilities_not_dropped = []

        for container in containers:
            name = str(container.get("name") or "unknown")
            container_sc = container.get("securityContext", {}) or {}
            effective = merged_security_context(pod_sc, container_sc)

            seccomp = effective.get("seccompProfile") or {}
            seccomp_type = str(seccomp.get("type") or "")
            if not seccomp_type:
                missing_seccomp.append(name)
            elif seccomp_type == "Unconfined":
                unconfined_seccomp.append(name)

            if container_sc.get("allowPrivilegeEscalation") is not False:
                privilege_escalation_not_disabled.append(name)

            run_as_non_root = effective.get("runAsNonRoot")
            run_as_user = effective.get("runAsUser")
            if run_as_non_root is not True and not (isinstance(run_as_user, int) and run_as_user > 0):
                run_as_non_root_not_set.append(name)

            if container_sc.get("readOnlyRootFilesystem") is not True:
                read_only_rootfs_not_enabled.append(name)

            drop_caps = [str(value) for value in (((container_sc.get("capabilities") or {}).get("drop") or []))]
            if "ALL" not in drop_caps:
                capabilities_not_dropped.append(name)

        issue_map = [
            ("missing-seccomp-profile", missing_seccomp),
            ("unconfined-seccomp-profile", unconfined_seccomp),
            ("allow-privilege-escalation-not-disabled", privilege_escalation_not_disabled),
            ("run-as-non-root-not-enforced", run_as_non_root_not_set),
            ("read-only-root-filesystem-not-enabled", read_only_rootfs_not_enabled),
            ("capabilities-not-fully-dropped", capabilities_not_dropped),
        ]
        for issue, names in issue_map:
            if names:
                findings.append(
                    {
                        "namespace": namespace,
                        "pod": pod,
                        "scc": scc,
                        "issue": issue,
                        "detail": ", ".join(names),
                    }
                )

    print(json.dumps({"security_findings": findings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
