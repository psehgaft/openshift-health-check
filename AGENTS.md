# Repository Instructions

This repository builds one cluster health report per run. Treat it as a report-contract codebase, not just a collection of scripts. Small changes in playbooks, templates, profiles, or validators can break report shape, cluster-type routing, or collected-state support.

## Source Of Truth

- Start with [README.md](README.md) for supported cluster types, run modes, commands, and validation flow.
- Use [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md) for report design intent and section-order rationale.
- Preserve the current contract unless the task explicitly asks to change it.

## Supported Cluster Types

The repo currently supports:

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

Cluster-type playbooks live under `playbooks/`. Keep one playbook family per cluster type. Do not introduce parallel report families for the same cluster type unless the user explicitly asks for a new contract.

## Cluster-Type Boundaries

Avoid cross-contamination between playbooks, input profiles, and report formats.

- `playbooks/openshift_cluster_health_report.yml`
  - Only for OpenShift clusters.
  - Uses `inputs/openshift-cluster-health-profile.yml`.
  - Must generate the OpenShift report contract.
  - Supports both `live` and `collected` paths through one playbook.
- `playbooks/k8s_cluster_health_report.yml`
  - Only for generic Kubernetes clusters.
  - Must not render the OpenShift report contract.
  - Uses the Kubernetes/provider profile resolution path.
- Provider wrappers such as `aks`, `eks`, `gke`, `rancher`, `minikube`
  - Must use the matching provider profile.
  - Must fail closed rather than silently using the wrong family.
- `playbooks/development_k8s_cluster_health_report.yml`
  - Kubernetes-only development profile path.
  - Not an OpenShift wrapper.

If you change cluster detection or profile loading, preserve the rule that the wrong wrapper should fail rather than produce a mixed report.

## OpenShift Contract

OpenShift is the deepest path in the repo. Preserve these rules:

- One primary OpenShift playbook:
  - `playbooks/openshift_cluster_health_report.yml`
- One OpenShift report model for both:
  - live cluster collection
  - collected-state reprocessing
- Collected-state mode is first-class, not a degraded side path.
- Optional support analyzers such as `cluster-compare`, `omc`, `etcd-ocp-diag`, and `sosreport` may enrich the report, but they must not create a second OpenShift report family.

Current OpenShift report order comes from the design notes and template. Keep it aligned:

1. Evidence And Supportability
2. Platform Health
3. Node Health And Capacity
4. Backup And Disaster Recovery
5. Application Access And Network Isolation
6. Observability
7. Security And Governance
8. Workload Health
9. Platform Architecture And Lifecycle
10. Capacity Planning Snapshot
11. Declarative Operations
12. Container Platform Adoption And Release Engineering
13. Day 2 Production Readiness

## Profile-Gated Rendering

For OpenShift, the final report must obey `inputs/openshift-cluster-health-profile.yml`.

- Posture presence is controlled by:
  - `cluster_health_profile.postures.<key>.enabled`
- Capability presence is controlled by:
  - `cluster_health_profile.capabilities.<key>.enabled`
- `required` is not a render-presence flag.
  - It affects priority, expectation, and severity semantics once included.

Current enforced behavior:

- `enabled=false` means the posture or capability section must not appear in the final OpenShift report.
- `enabled=true` means it must be present in the final report.
- Capability order in Day 2 may be assessment-priority order, not raw profile order.

Files that currently enforce this contract:

- `templates/openshift_cluster_health_report.md.j2`
- `roles/analyze_openshift/tasks/day2.yml`
- `scripts/validate_openshift_report_output.py`

When changing any of those files, verify the other two still agree.

## OpenShift Live Vs Collected Mode

The OpenShift playbook supports:

- `report_mode=live`
- `report_mode=collected`
- `report_mode=auto`

Rules to preserve:

- `report_mode=auto` resolves to `collected` when collected-state inputs are provided.
- OpenShift API surface validation applies only to live runs.
- Collected-state fixture and case-bundle runs must not require a live OpenShift API probe.
- Resume/checkpoint behavior must work for both live and collected runs.

Sensitive files for this:

- `playbooks/openshift_cluster_health_report.yml`
- `roles/report_common/tasks/save_run_checkpoint.yml`
- `roles/report_common/tasks/main.yml`

## Node Debug And Support Collection

Current OpenShift support-collection contract:

- `collect_live_sosreport=true` by default.
- `collect_live_sosreport=false` must disable node-debug-backed sosreport collection even when the live support profile is broad.
- Node diagnostics are optional and should target symptom-derived nodes when enabled.
- RBAC enforcement for the custom service account is informative by default:
  - `rbac_check_fail_on_gap=false`

Do not reintroduce behavior where `live_support_collection_profile=all` implicitly overrides `collect_live_sosreport=false`.

Relevant files:

- `playbooks/openshift_cluster_health_report.yml`
- `roles/collect_live_support_evidence/tasks/main.yml`
- `roles/preflight_openshift/tasks/main.yml`
- `docs/ocp-health-check-sa-rbac.md`

## Report Naming

Report filenames are part of the contract.

Current format is:

`<report_basename>-<cluster_type>-<cluster_name>-<report_timestamp>.<ext>`

Naming logic lives in:

- `roles/report_common/tasks/main.yml`

If you change naming, update the README and any scripts or tests that look for generated files.

## Common Collector Semantics

Do not treat every Ansible `skipping` line as a bug.

In `roles/collect_common/tasks/main.yml`:

- the main collection commands still run first
- `Capture common optional permission skips` only records optional collectors that failed in ignorable ways
- when items show as `skipping` there, it usually means the follow-up bookkeeping condition was false, not that data collection was skipped

If you change collector failure handling, preserve the distinction between:

- hard failures
- optional access-denied skips
- optional not-installed skips

## Key Sensitive Files

Be careful in these areas because they control top-level behavior:

- `playbooks/openshift_cluster_health_report.yml`
- `playbooks/k8s_cluster_health_report.yml`
- `templates/openshift_cluster_health_report.md.j2`
- `roles/analyze_openshift/tasks/day2.yml`
- `roles/analyze_openshift/tasks/core.yml`
- `roles/analyze_openshift/tasks/summary.yml`
- `roles/report_common/tasks/main.yml`
- `roles/report_common/tasks/build_openshift_report_payload.yml`
- `scripts/validate_openshift_report_output.py`
- `scripts/validate_repo.sh`
- `inputs/openshift-cluster-health-profile.yml`

## Validation Requirements

After changing playbooks, roles, templates, scripts, or input profiles, run the repo validator:

```bash
scripts/validate_repo.sh
```

At minimum, preserve passing results for:

- YAML parsing
- `ansible-playbook --syntax-check` for playbooks
- Python compilation
- OpenShift report template validation
- cluster health profile validation
- rendered OpenShift report validation
- OpenShift CI fixture report generation

If a change affects only a narrow path, targeted checks are still expected before the full validator:

```bash
ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml
python3 -m py_compile scripts/validate_openshift_report_output.py
```

## Change Discipline

- Prefer changing the smallest layer that owns the behavior.
- If you change a report contract, update:
  - implementation
  - validator
  - README or design docs when the user-facing behavior changed
- Do not add workaround wrappers that duplicate an existing cluster-type playbook contract.
- Preserve collected-state fixture support when adding live-cluster guardrails.
- Fail closed on wrong cluster type or wrong wrapper selection instead of producing a mixed report.
