#!/usr/bin/env python3
"""Verify OpenShift RBAC for the health-check playbook using `oc auth can-i`.

This script builds an authorization matrix from the repo's collection task files
and augments it with live-mode checks such as `/readyz`, Thanos route access,
Insights archive copy, `oc adm inspect`, `oc adm must-gather`, and optional
`oc debug node/<node>` support.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml


AUTH_CAN_I_TIMEOUT_SECONDS = 15


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def iter_argv_specs(node):
    if isinstance(node, dict):
        argv = node.get("argv")
        if isinstance(argv, list):
            yield argv
        for value in node.values():
            yield from iter_argv_specs(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_argv_specs(item)


def normalize_resource_token(token: str):
    resource = token
    name = ""
    if "/" in token and not token.startswith("/"):
        resource, name = token.split("/", 1)
    return resource, name


def parse_get_command(argv: List[str], source: str):
    if len(argv) < 3 or argv[1] != "get":
        return None
    if argv[2] == "--raw=/readyz?verbose":
        return {
            "label": "apiserver readyz",
            "kind": "nonresource",
            "verb": "get",
            "non_resource_url": "/readyz",
            "source": source,
            "required": True,
        }

    namespace = ""
    all_namespaces = False
    positionals = []  # type: List[str]
    i = 2
    while i < len(argv):
        token = argv[i]
        if token in {"-n", "--namespace"} and i + 1 < len(argv):
            namespace = argv[i + 1]
            i += 2
            continue
        if token in {"-A", "--all-namespaces"}:
            all_namespaces = True
            i += 1
            continue
        if token.startswith("-"):
            if token in {"-o", "--output", "--field-selector", "--selector", "-l"} and i + 1 < len(argv):
                i += 2
            else:
                i += 1
            continue
        positionals.append(token)
        i += 1

    if not positionals:
        return None
    if positionals[0] == "api-resources":
        return None

    resource, embedded_name = normalize_resource_token(positionals[0])
    name = embedded_name
    if len(positionals) > 1 and not positionals[1].startswith("-"):
        name = positionals[1]

    verb = "get" if name else "list"
    label = " ".join(part for part in ["oc get", resource, name or ("-A" if all_namespaces else namespace)] if part)
    return {
        "label": label,
        "kind": "resource",
        "verb": verb,
        "resource": resource,
        "name": name,
        "namespace": namespace,
        "all_namespaces": all_namespaces,
        "source": source,
        "required": True,
    }


def add_unique(checks: List[dict], seen: Set[Tuple], check: dict):
    key = (
        check.get("kind"),
        check.get("verb"),
        check.get("resource", ""),
        check.get("name", ""),
        check.get("namespace", ""),
        bool(check.get("all_namespaces")),
        check.get("non_resource_url", ""),
    )
    if key not in seen:
        seen.add(key)
        checks.append(check)


def build_checks(repo_root: Path, include_live_support: bool, include_sosreport: bool):
    checks = []  # type: List[dict]
    seen = set()  # type: Set[Tuple]

    for rel_path in (
        "roles/collect_common/tasks/main.yml",
        "roles/collect_openshift/tasks/main.yml",
        "roles/analyze_openshift/tasks/observability.yml",
    ):
        path = repo_root / rel_path
        data = load_yaml(path)
        for argv in iter_argv_specs(data):
            if not argv:
                continue
            check = parse_get_command(argv, rel_path)
            if check:
                add_unique(checks, seen, check)

    # Observability and direct API access.
    add_unique(
        checks,
        seen,
        {
            "label": "thanos querier route",
            "kind": "resource",
            "verb": "get",
            "resource": "route",
            "name": "thanos-querier",
            "namespace": "openshift-monitoring",
            "all_namespaces": False,
            "source": "roles/analyze_openshift/tasks/observability.yml",
            "required": True,
        },
    )
    add_unique(
        checks,
        seen,
        {
            "label": "apiserver readyz",
            "kind": "nonresource",
            "verb": "get",
            "non_resource_url": "/readyz",
            "source": "roles/analyze_openshift/tasks/observability.yml",
            "required": True,
        },
    )

    if include_live_support:
        synthetic_checks = [
            {
                "label": "live inspect nodes",
                "kind": "resource",
                "verb": "list",
                "resource": "nodes",
                "namespace": "",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "live inspect clusteroperators",
                "kind": "resource",
                "verb": "list",
                "resource": "clusteroperators",
                "namespace": "",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "live inspect machineconfigpools",
                "kind": "resource",
                "verb": "list",
                "resource": "machineconfigpools",
                "namespace": "",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "live inspect routes",
                "kind": "resource",
                "verb": "list",
                "resource": "routes",
                "namespace": "",
                "all_namespaces": True,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "insights archive pods",
                "kind": "resource",
                "verb": "list",
                "resource": "pods",
                "namespace": "openshift-insights",
                "all_namespaces": False,
                "source": "scripts/collect_insights_archive.py",
                "required": True,
            },
            {
                "label": "insights archive pod exec",
                "kind": "resource",
                "verb": "create",
                "resource": "pods/exec",
                "namespace": "openshift-insights",
                "all_namespaces": False,
                "source": "scripts/collect_insights_archive.py",
                "required": True,
            },
            {
                "label": "must-gather namespaces create",
                "kind": "resource",
                "verb": "create",
                "resource": "namespaces",
                "namespace": "",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "must-gather serviceaccounts create",
                "kind": "resource",
                "verb": "create",
                "resource": "serviceaccounts",
                "namespace": "openshift-must-gather",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "must-gather pods create",
                "kind": "resource",
                "verb": "create",
                "resource": "pods",
                "namespace": "openshift-must-gather",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "must-gather pods exec",
                "kind": "resource",
                "verb": "create",
                "resource": "pods/exec",
                "namespace": "openshift-must-gather",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "must-gather pods logs",
                "kind": "resource",
                "verb": "get",
                "resource": "pods/log",
                "namespace": "openshift-must-gather",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
            {
                "label": "must-gather clusterrolebindings create",
                "kind": "resource",
                "verb": "create",
                "resource": "clusterrolebindings.rbac.authorization.k8s.io",
                "namespace": "",
                "all_namespaces": False,
                "source": "roles/collect_live_support_evidence/tasks/main.yml",
                "required": True,
            },
        ]
        for check in synthetic_checks:
            add_unique(checks, seen, check)

    if include_sosreport:
        for check in (
            {
                "label": "node debug nodes get",
                "kind": "resource",
                "verb": "get",
                "resource": "nodes",
                "namespace": "",
                "all_namespaces": False,
                "source": "scripts/collect_node_sosreports.py",
                "required": True,
            },
            {
                "label": "node debug nodes list",
                "kind": "resource",
                "verb": "list",
                "resource": "nodes",
                "namespace": "",
                "all_namespaces": False,
                "source": "scripts/collect_node_sosreports.py",
                "required": True,
            },
            {
                "label": "node debug pods create",
                "kind": "resource",
                "verb": "create",
                "resource": "pods",
                "namespace": "",
                "all_namespaces": True,
                "source": "scripts/collect_node_sosreports.py",
                "required": True,
            },
            {
                "label": "node debug pods exec",
                "kind": "resource",
                "verb": "create",
                "resource": "pods/exec",
                "namespace": "",
                "all_namespaces": True,
                "source": "scripts/collect_node_sosreports.py",
                "required": True,
            },
            {
                "label": "node debug privileged scc",
                "kind": "resource",
                "verb": "use",
                "resource": "securitycontextconstraints.security.openshift.io",
                "name": "privileged",
                "namespace": "",
                "all_namespaces": False,
                "source": "scripts/collect_node_sosreports.py",
                "required": True,
            },
        ):
            add_unique(checks, seen, check)

    return checks


def run_can_i(kube_cli: str, subject: str, current_user: str, check: dict):
    argv = [kube_cli, "auth", "can-i"]
    use_impersonation = subject and subject != current_user
    if use_impersonation:
        argv.extend(["--as", subject])
    argv.append(check["verb"])
    if check["kind"] == "nonresource":
        argv.append(check["non_resource_url"])
    else:
        argv.append(check["resource"])
        if check.get("name"):
            argv.append(check["name"])
        if check.get("all_namespaces"):
            argv.append("--all-namespaces")
        elif check.get("namespace"):
            argv.extend(["-n", check["namespace"]])

    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=AUTH_CAN_I_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "label": check["label"],
            "command": argv,
            "ok": False,
            "rc": 124,
            "stdout": "",
            "stderr": f"timed out after {AUTH_CAN_I_TIMEOUT_SECONDS} seconds",
            "source": check.get("source", ""),
            "required": bool(check.get("required", True)),
            "used_impersonation": use_impersonation,
        }
    # If the current user is already the target service account, retry without --as
    # because some clusters deny SAR impersonation even for self-checks.
    if use_impersonation and current_user == subject and proc.returncode != 0:
        argv = [part for part in argv if part not in {"--as", subject}]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=AUTH_CAN_I_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "label": check["label"],
                "command": argv,
                "ok": False,
                "rc": 124,
                "stdout": "",
                "stderr": f"timed out after {AUTH_CAN_I_TIMEOUT_SECONDS} seconds",
                "source": check.get("source", ""),
                "required": bool(check.get("required", True)),
                "used_impersonation": False,
            }
        use_impersonation = False

    stdout = (proc.stdout or "").strip().lower()
    ok = proc.returncode == 0 and stdout == "yes"
    return {
        "label": check["label"],
        "command": argv,
        "ok": ok,
        "rc": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "source": check.get("source", ""),
        "required": bool(check.get("required", True)),
        "used_impersonation": use_impersonation,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--kube-cli", default="oc")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--current-user", default="")
    parser.add_argument("--include-live-support", action="store_true")
    parser.add_argument("--include-sosreport", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    checks = build_checks(
        repo_root=repo_root,
        include_live_support=args.include_live_support,
        include_sosreport=args.include_sosreport,
    )
    results = [run_can_i(args.kube_cli, args.subject, args.current_user, check) for check in checks]
    failed = [item for item in results if not item["ok"]]
    payload = {
        "subject": args.subject,
        "current_user": args.current_user,
        "include_live_support": args.include_live_support,
        "include_sosreport": args.include_sosreport,
        "checks": results,
        "summary": {
            "check_count": len(results),
            "passed_count": sum(1 for item in results if item["ok"]),
            "failed_count": len(failed),
            "failed_labels": [item["label"] for item in failed],
        },
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
