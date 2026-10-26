# OpenShift Health Check and Architecture Toolkit

Ansible toolkit that builds a **cluster health report** for one cluster at a time.
Live runs use your current `oc` / `kubectl` session; collected runs reprocess support artifacts (must-gather, inspect, case bundles). Output is Markdown (humans) and JSON (automation).

**Does not change cluster workload configuration.** Optional node diagnostics (`oc debug`, `sosreport`) may create temporary debug resources when enabled.

> [!IMPORTANT]
> This tool summarizes health signals and likely risks. Review findings before operational decisions.

## 5-minute Quick Start (OpenShift live)

```bash
# 1. Clone and enter the repo
git clone https://github.com/psehgaft/openshift-health-check.git
cd openshift-health-check

# 2. Create the Ansible virtualenv
./scripts/setup-ansible-venv.sh
source .venv/bin/activate

# 3. Authenticate to the cluster
oc login https://api.<cluster-name>.<domain>:6443
oc whoami

# 4. Run a production-safe live report (no node sosreport)
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=live \
  -e report_performance_profile=standard \
  -e collect_live_sosreport=false
```

Reports land under `reports/` (Markdown + JSON). For the shortest first run use `report_performance_profile=fast`. Full depth is the default when you omit the profile override.

**More detail:** [docs/QUICKSTART.md](docs/QUICKSTART.md) · full options below under [Quick Start](#quick-start).

## Supported platforms

OpenShift · OpenShift SNO · ARO · ROSA · ROSA HCP · generic Kubernetes · AKS · EKS · GKE · Rancher-managed Kubernetes · Minikube

## Unified toolkit

This repository includes the shell/ACM/certificate/DNS/Headlamp toolkit from `psehgaft/openshift-healthcheck` and a pinned architecture generator from `stratus-ss/arch-design-doc-generator`. The Ansible report remains the canonical report engine.

See [the integration guide](docs/three-repository-integration.md) for the shell → report → architecture workflow.

```bash
python3 scripts/unified_healthcheck.py --help
```

## Start here (reading order)

1. This README — what the tool does and how to run it.
2. [docs/QUICKSTART.md](docs/QUICKSTART.md) — shortest path and common variants.
3. [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md) — why the report is structured the way it is.

## Design notes

The check set follows [DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md). Use this README to install and run; use the design notes to understand report structure and intent.

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

> **Tip:** Prefer the [5-minute Quick Start](#5-minute-quick-start-openshift-live) above for a production-safe first run (`standard` profile + `collect_live_sosreport=false`). See also [docs/QUICKSTART.md](docs/QUICKSTART.md).

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

The playbook still supports lower-level compatibility variables such as `case_bundle_path`, `must_gather_path`, `inspect_path`, `report_generate_html`, and `report_generate_pdf`, but they are no longer the preferred interface for routine runs.

For the complete reference (bastion bootstrap, collected mode, resume, CI wrappers, report structure, and all checks), continue with the remainder of this README and [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md).

---

_The sections below retain the full operational reference from the previous README layout (command variants, validate, report contract, checks, and advanced options)._
