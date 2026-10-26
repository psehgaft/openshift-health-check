# OpenShift Health Check and Architecture Toolkit

Ansible toolkit that builds a **cluster health report** for one cluster at a time (Markdown + JSON). Live runs use your current `oc`/`kubectl` session; collected runs reprocess support artifacts.

> [!TIP]
> **5-minute path:** see [docs/QUICKSTART.md](docs/QUICKSTART.md) for a production-safe first run (`report_performance_profile=standard`, `collect_live_sosreport=false`).


## Unified toolkit

This repository now includes the shell/ACM/certificate/DNS/Headlamp toolkit from `psehgaft/openshift-healthcheck` and a pinned architecture generator from `stratus-ss/arch-design-doc-generator`. The existing Ansible report remains the canonical report engine.

See [the integration guide](docs/three-repository-integration.md) for analysis, installation, the complete shell → canonical report → architecture workflow, module entry points, and license attribution.

```bash
python3 scripts/unified_healthcheck.py --help
```

This repo is an Ansible-based tool for building a health report for one cluster at a time.

It supports:

- OpenShift
- OpenShift SNO
- ARO
- ROSA
- ROSA HCP
- generic Kubernetes
- AKS
- EKS
- GKE
- Rancher-managed Kubernetes
- Minikube

For live runs, it uses your current `oc` or `kubectl` session. For collected runs, it reprocesses previously gathered support artifacts. In both cases it writes:

- a Markdown report for people
- a JSON report for automation

Default report file names include the cluster type and cluster name. The CI wrapper writes stable `ci-cluster-report.*` filenames instead.

It does not change cluster workload configuration. In live OpenShift runs, optional diagnostics such as `oc debug node/<node>` and `sosreport` can create temporary debug resources when that evidence path is enabled.

By default, it collects data in parallel so the run finishes faster. It also tells you about collection failures and timeouts, because a health report is only useful when you can see whether the data set is complete. Optional collectors that target APIs or config objects which are not installed on the cluster are tracked separately as not applicable, rather than counted as hard collection failures.

> [!IMPORTANT]
> This tool summarizes cluster health signals and likely risks. Review the findings before making operational decisions.

## Start Here

If you are new to this repo, use this reading order:

1. Stay in [README.md](README.md) to learn what the tool does and how to run it.
2. Read [docs/QUICKSTART.md](docs/QUICKSTART.md) for the shortest production-safe path.
3. Read [DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md) to understand why the report is structured the way it is.

## Design Notes

The check set in this repo follows the design in [DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md).

Use this `README.md` when you want to install, run, or use the tool.
Use the design notes when you want to understand why the checks exist and how the report is meant to be read.

## Quick Start

Run these commands from the repo root.

1. Set up the Ansible virtual environment:

```bash
./scripts/setup-ansible-venv.sh
```

2. Source the virtual environment:

```bash
source .venv/bin/activate
```

3. Log in to OpenShift:

```bash
oc login https://api.<cluster-name>.<domain>:6443
oc whoami
```

4. Run the report:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=live
```

The default OpenShift run uses `report_performance_profile=full`. For production clusters where node-level diagnostics are not approved, use the `collect_live_sosreport=false` variant below.

**Recommended first production-safe run** (also documented in [docs/QUICKSTART.md](docs/QUICKSTART.md)):

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=live \
  -e report_performance_profile=standard \
  -e collect_live_sosreport=false
```

### Common Arguments

Most users only need the Quick Start command. These arguments cover the common alternatives:

| Argument | Values | When to use it |
| --- | --- | --- |
| `report_mode` | `live`, `collected`, `auto`, `offline` | `live` reads from the current cluster. `collected` reprocesses existing support data. `auto` switches to collected mode when collected inputs are provided. `offline` is an alias for `collected`. |
| `collected_evidence_root` | path | Preferred collected-mode input. Point it at a case bundle, extracted `must-gather`, extracted `inspect`, or a directory that contains those artifacts. |
| `report_performance_profile` | `full`, `standard`, `fast` | `full` is the default and collects the broadest evidence set. `standard` skips expensive support collectors. `fast` keeps the run narrow. |
| `collect_live_sosreport` | `true`, `false` | Set this to `false` when node-level diagnostics are not approved. This disables `oc debug node/<node>` and `sosreport` even when `report_performance_profile=full`. |
| `report_run_mode` | `fresh`, `resume_last_failure` | Use `resume_last_failure` after a failed run to reuse completed artifacts. |
| `report_profile_path` | path | Load a profile override file on top of the built-in OpenShift profile. |
| `selected_postures` | comma-separated posture keys | Limit the rendered report to specific posture sections. |
| `selected_capabilities` | comma-separated capability keys | Limit the rendered report to specific capability sections. |
| `report_output_dir` | path | Write reports somewhere other than `reports/`. |
