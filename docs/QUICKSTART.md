# Quick Start — OpenShift Health Check

Short path to a useful report. For full reference see the [root README](../README.md).

## Prerequisites

- `git`, Python 3.11+ recommended
- `oc` (OpenShift) or `kubectl` (generic Kubernetes paths)
- Cluster login with permission to read cluster-scoped resources (see [ocp-health-check-sa-rbac.md](ocp-health-check-sa-rbac.md) for a dedicated ServiceAccount)

## OpenShift live report (recommended first run)

```bash
git clone https://github.com/psehgaft/openshift-health-check.git
cd openshift-health-check

./scripts/setup-ansible-venv.sh
source .venv/bin/activate

oc login https://api.<cluster-name>.<domain>:6443
oc whoami

# Production-friendly: broad API evidence, no node sosreport
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=live \
  -e report_performance_profile=standard \
  -e collect_live_sosreport=false
```

Outputs:

- `reports/` — Markdown and JSON reports (names include cluster type and name)
- `<report_output_dir>/.run-state/openshift/` — intermediate artifacts (collection, postures, payload)

## Choose a performance profile

| Profile | Use when |
| --- | --- |
| `fast` | First try, narrow evidence, shortest runtime |
| `standard` | Day-to-day ops review without expensive support collectors |
| `full` (default if omitted) | Deepest evidence: must-gather, inspect, Insights, optional node diagnostics |

Disable node-level diagnostics explicitly on production clusters:

```bash
-e collect_live_sosreport=false
```

## Collected mode (offline / case bundle)

When you already have must-gather, inspect, or a support case bundle:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=collected \
  -e collected_evidence_root=/path/to/case-bundle-or-must-gather
```

## Resume a failed run

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_run_mode=resume_last_failure
```

## Scope the report

```bash
# Only selected postures
-e selected_postures=platform_health,security_and_governance

# Only selected capabilities
-e selected_capabilities=oauth_external_identity_provider,external_alert_delivery
```

## Other cluster types

Activate `.venv`, then run the matching playbook under [`playbooks/`](../playbooks). OpenShift remains the deepest path.

## Validate local changes

```bash
scripts/validate_repo.sh openshift
```

## CI-stable filenames

```bash
scripts/run_ci_report.sh playbooks/openshift_cluster_health_report.yml
# → reports/ci-cluster-report.md and reports/ci-cluster-report.json
```

## What good looks like

A useful report answers, for each major gap:

1. What is the gap?
2. Why does it matter?
3. What should be done?
4. Who likely owns it?
5. How do we know it is fixed?

See [DESIGN-PRINCIPLE.md](DESIGN-PRINCIPLE.md) for the full reading contract.
