#!/usr/bin/env python3
"""Compose existing health engines and architecture tooling without changing contracts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / "toolkits/openshift-healthcheck"
GENERATOR = ROOT / "tools/arch-design-doc-generator"


def run(command, *, cwd=ROOT, env=None):
    subprocess.run([str(item) for item in command], cwd=cwd, env=env, check=True)


def read_report(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("metadata"), dict):
        raise ValueError("Expected a canonical health report with metadata")
    if data["metadata"].get("cluster_type") not in {"openshift", "openshift_sno", "aro", "rosa", "rosa_hcp"}:
        # Canonical engine can use provider names in the profile; platform family is authoritative.
        if data["metadata"].get("platform_family") != "openshift":
            raise ValueError("Architecture bridge requires an OpenShift report")
    return data


def findings_from_report(report):
    """Preserve source paths; do not invent severities for heuristic collections."""
    rows = []

    def walk(value, path):
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    rows.append({"source": "canonical", "source_path": f"{path}[{index}]", "details": item})
                elif isinstance(item, (list, dict)):
                    walk(item, f"{path}[{index}]")
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}")

    walk(report.get("findings", {}), "$.findings")
    def domain_findings(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "findings":
                    walk(item, f"{path}.{key}")
                else:
                    domain_findings(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                domain_findings(item, f"{path}[{index}]")
    domain_findings(report.get("domains", {}), "$.domains")
    return rows


def normalize_shell_evidence(shell_run, output):
    """Expand oc JSON lists to single objects for the canonical offline extractor."""
    raw = shell_run / "raw"
    if not raw.is_dir():
        raise ValueError(f"Missing shell raw evidence: {raw}")
    output.mkdir(parents=True, exist_ok=False)
    objects, invalid, skipped = {}, [], []
    for path in sorted(raw.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            invalid.append({"path": str(path.relative_to(shell_run)), "error": str(exc)})
            continue
        items = value if isinstance(value, list) else value.get("items", [value]) if isinstance(value, dict) else []
        for item in items:
            if not isinstance(item, dict) or not item.get("kind") or not item.get("apiVersion"):
                skipped.append(str(path.relative_to(shell_run)))
                continue
            metadata = item.get("metadata", {})
            key = (item["apiVersion"], item["kind"], metadata.get("namespace", ""), metadata.get("name", ""))
            # Secret contents must never enter the architecture evidence pipeline.
            item = dict(item)
            if item["kind"] == "Secret":
                item.pop("data", None)
                item.pop("stringData", None)
            objects.setdefault(key, item)
    if not objects:
        raise ValueError("Shell evidence contains no valid Kubernetes objects")
    for index, item in enumerate(objects.values()):
        (output / f"resource-{index:06d}.json").write_text(json.dumps(item) + "\n", encoding="utf-8")
    summary = {"objects": len(objects), "invalid_files": invalid, "skipped_non_resource_records": skipped}
    (output / "normalization-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def build_architecture(report_path, output, client, shell_run=None):
    report = read_report(report_path)
    rows = findings_from_report(report)
    shell_sources = {}
    if shell_run is not None:
        for filename in ("findings.csv", "backlog.csv", "errors-criticality.csv"):
            path = shell_run / "csv" / filename
            if not path.is_file():
                raise ValueError(f"Missing shell evidence register: {path}")
            shell_sources[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
            with path.open(newline="", encoding="utf-8") as handle:
                for index, item in enumerate(csv.DictReader(handle), start=2):
                    rows.append({"source": "shell", "source_path": f"csv/{filename}:{index}", "details": item})
    # Validate all input before creating a workspace. Never overwrite an engagement.
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "generator"
    shutil.copytree(GENERATOR, workspace, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache", "project.yaml", "slot_map.json", "output"))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(workspace / "scripts/shared/lib")
    run([sys.executable, workspace / "scripts/setup_project.py", workspace, client, "OCP-V"], cwd=workspace, env=env)
    evidence = {
        "schema_version": 1,
        "review_status": "DRAFT_REQUIRES_ARCHITECT_REVIEW",
        "health_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "metadata": report["metadata"],
        "cluster_current_state": report.get("cluster_current_state", {}),
        "cluster_profile": report.get("cluster_profile", {}),
        "health_summary": report.get("health_summary", {}),
        "audit": report.get("audit", {}),
        "coverage": report.get("evidence", {}),
        "shell_register_sha256": shell_sources,
        "findings": rows,
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(report_path, output / "health-report.json")
    adr_files = list((workspace / "ADR").glob("*.md"))
    if len(adr_files) != 1:
        raise ValueError("Generator setup must create exactly one ADR working copy")
    appendix = "\n\n## Health assessment evidence — review input\n\n"
    appendix += "Status: DRAFT. Findings are observations, not approved design decisions.\n\n"
    appendix += "Evidence: `../../evidence.json`; canonical report: `../../health-report.json`.\n\n"
    appendix += "Do not infer compliance, RTO/RPO, capacity targets, or migration approval from this snapshot.\n\n"
    for index, row in enumerate(rows, start=1):
        appendix += f"### HC-{index:04d} — {row['source']}\n\n"
        appendix += f"Source: `{row['source_path']}`\n\n"
        # Indented code cannot be terminated by Markdown fences in cluster-controlled strings.
        appendix += "\n".join("    " + line for line in json.dumps(row["details"], indent=2).splitlines()) + "\n\n"
        appendix += "Decision: pending review. Owner: pending assignment. Acceptance criteria: pending validation.\n\n"
    with adr_files[0].open("a", encoding="utf-8") as handle:
        handle.write(appendix)
    with (output / "remediation-review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "source", "source_path", "status", "observed_details", "owner", "acceptance_criteria"])
        for index, row in enumerate(rows, start=1):
            details = json.dumps(row["details"], ensure_ascii=True)
            writer.writerow([f"HC-{index:04d}", row["source"], row["source_path"], "Pending review", details, "", ""])
    manifest = {
        "schema_version": 1, "client": client,
        "canonical_report": str(report_path),
        "shell_run": str(shell_run) if shell_run else None,
        "architecture_adr": str(adr_files[0].relative_to(output)),
        "source_repositories": json.loads((ROOT / "integration/sources.json").read_text()),
        "finding_rows": len(rows), "status": "DRAFT_REQUIRES_ARCHITECT_REVIEW",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# Health assessment and architecture review\n\n"
        "Review evidence.json and remediation-review.csv, then complete the ADR in generator/ADR/.\n"
        "The imported generator templates are specific to OpenShift Virtualization; adapt scope before building.\n"
        "No AI service has been called by this export.\n\n"
        "From generator/, after approving the ADR and configuring your AI tool:\n\n"
        "```bash\nmake build-hld-from-adr\nmake publish\nmake build-lld\nmake workitems\n```\n\n"
        "These commands require the generator prerequisites and may send ADR content to the selected AI service.\n",
        encoding="utf-8")
    print(f"Architecture review packet: {output}")
    return manifest


def ansible(extra):
    binary = ROOT / ".venv/bin/ansible-playbook"
    if not binary.is_file():
        raise ValueError("Run scripts/setup-ansible-venv.sh first")
    env = os.environ.copy()
    env["PATH"] = str(ROOT / ".venv/bin") + os.pathsep + env.get("PATH", "")
    run([binary, ROOT / "playbooks/openshift_cluster_health_report.yml", *extra], env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report", help="Run the canonical OpenShift Ansible playbook (arguments after --)")
    sub.add_parser("shell", help="Run the imported shell diagnostics (arguments after --)")
    normalize = sub.add_parser("normalize-shell", help="Convert shell JSON evidence for canonical collected reporting")
    normalize.add_argument("--shell-run", type=Path, required=True)
    normalize.add_argument("--output", type=Path, required=True)
    architecture = sub.add_parser("architecture", help="Create an evidence-backed native generator workspace")
    architecture.add_argument("--report-json", type=Path, required=True)
    architecture.add_argument("--shell-run", type=Path)
    architecture.add_argument("--output", type=Path, required=True)
    architecture.add_argument("--client", required=True)
    suite = sub.add_parser("suite", help="Shell collection → canonical collected report → architecture packet")
    suite.add_argument("--output", type=Path, required=True)
    suite.add_argument("--client", required=True)
    suite.add_argument("--cluster-name", required=True)
    suite.add_argument("--must-gather", action="store_true", help="Enable temporary must-gather resources")
    args, extra = parser.parse_known_args()
    if extra[:1] == ["--"]:
        extra = extra[1:]
    if args.command in {"architecture", "suite", "normalize-shell"} and extra:
        parser.error(f"Unexpected arguments: {extra}")
    if args.command == "report":
        ansible(extra)
    elif args.command == "shell":
        run(["bash", TOOLKIT / "Shell/ocp-healthcheck.sh", *extra])
    elif args.command == "normalize-shell":
        print(json.dumps(normalize_shell_evidence(args.shell_run.resolve(), args.output.resolve())))
    elif args.command == "architecture":
        build_architecture(args.report_json.resolve(), args.output.resolve(), args.client,
                           args.shell_run.resolve() if args.shell_run else None)
    else:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.cluster_name):
            raise ValueError("Cluster name must be a logical name containing letters, digits, dots, hyphens, or underscores")
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        shell_output = output / "shell"
        run(["bash", TOOLKIT / "Shell/ocp-healthcheck.sh", "--output", shell_output,
             "--client-label", args.client, "--cluster-name", args.cluster_name,
             "--must-gather" if args.must_gather else "--no-must-gather"])
        runs = list(shell_output.iterdir())
        if len(runs) != 1 or not (runs[0] / "raw").is_dir():
            raise ValueError("Expected one shell evidence run")
        report_output = output / "canonical"
        normalized = output / "normalized-evidence"
        normalize_shell_evidence(runs[0], normalized)
        overrides = output / "report-input.json"
        overrides.write_text(json.dumps({"report_mode": "collected", "inspect_path": str(normalized),
            "report_output_dir": str(report_output), "report_basename": "integrated-health",
            "collect_live_missing_api_evidence": False,
            "must_gather_path": str(runs[0] / "must-gather") if args.must_gather else "",
            "collect_live_support_artifacts": False, "collect_live_sosreport": False}))
        ansible(["-e", f"@{overrides}"])
        reports = list(report_output.glob("integrated-health-*.json"))
        if len(reports) != 1:
            raise ValueError("Expected exactly one canonical JSON health report")
        build_architecture(reports[0], output / "architecture", args.client, runs[0])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Integration failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
