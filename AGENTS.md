# Repository Instructions

This repository builds one cluster health report per run. Treat it as a report-contract codebase, not just a collection of scripts. Small changes in playbooks, templates, profiles, or validators can break report shape, cluster-type routing, or collected-state support.

## Source Of Truth

- Start with [README.md](README.md) for supported cluster types, run modes, commands, and validation flow.
- Use [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md) for report design intent and section-order rationale.
- Use [docs/cluster-health-extension-guide.md](docs/cluster-health-extension-guide.md) for the current extension workflow and repo layout conventions.
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

## Current Ownership Pattern

The repo no longer uses one large shared OpenShift analysis owner per concern. Preserve the current ownership split:

- OpenShift posture sections live under dedicated roles:
  - `roles/posture_<key>/tasks/main.yml`
  - optional `roles/posture_<key>/tasks/analysis.yml`
  - `roles/posture_<key>/tasks/builder.yml`
- OpenShift capability artifacts live under dedicated roles:
  - `roles/capability_<key>/tasks/main.yml`
  - `roles/capability_<key>/tasks/builder.yml`
- Shared artifact plumbing is centralized in:
  - `roles/posture_artifact_from_builder`
  - `roles/capability_artifact_from_builder`
  - `roles/report_common`

Prefer changing the posture or capability role that owns the behavior before touching shared report plumbing.

Current rule of thumb:

- posture-specific synthesis belongs in the matching `roles/posture_<key>/`
- capability-specific artifact mapping belongs in the matching `roles/capability_<key>/`
- shared persistence, payload assembly, resume planning, and report rendering belong in `roles/report_common` or `roles/report_openshift`
- avoid re-centralizing posture or capability business logic back into one shared task file

## Helper Script Pattern

Do not embed Python in Ansible task heredocs.

Current repo pattern:

- keep Python helpers in `scripts/`
- call them from Ansible with `ansible.builtin.command`
- validate changed helpers with `python3 -m py_compile`

This rule applies to:

- analysis helpers
- collected-state parsing helpers
- supportability/evidence helpers
- report validators

If logic is non-trivial enough to tempt an inline Python block, it should almost always become a helper script under `scripts/` instead.

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

## Extending Postures And Capabilities

Users must be able to extend this repo with additional OpenShift postures or capabilities. Support that workflow deliberately instead of hard-coding today's list in only one place.

When adding a new OpenShift posture:

- Add it to `inputs/openshift-cluster-health-profile.yml` under `cluster_health_profile.postures`.
- Add the matching section title mapping to `scripts/validate_openshift_report_output.py` in `POSTURE_SECTION_TITLES`.
- Add or extend the section in `templates/openshift_cluster_health_report.md.j2`.
- Create or extend the owning role:
  - `roles/posture_<key>/tasks/main.yml`
  - `roles/posture_<key>/tasks/builder.yml`
  - `roles/posture_<key>/tasks/analysis.yml` when the posture owns synthesis logic
- Preserve the five-question section contract from the design notes:
  - what is the gap
  - why it matters
  - what should be done
  - who owns it
  - how to tell it is fixed
- Make sure the new posture obeys `.enabled` gating in the final report.

When adding a new OpenShift capability:

- Add it to `inputs/openshift-cluster-health-profile.yml` under `cluster_health_profile.capabilities`.
- Create or extend the owning role:
  - `roles/capability_<key>/tasks/main.yml`
  - `roles/capability_<key>/tasks/builder.yml`
- Make sure `roles/analyze_openshift/tasks/day2.yml` can account for it in either:
  - collected assessment output, or
  - the fallback capability-section builder
- Make sure `templates/openshift_cluster_health_report.md.j2` renders it through the profile-gated Day 2 capability section path.
- Make sure `scripts/validate_openshift_report_output.py` still passes with the new enabled capability set.
- Provide non-empty `docs`, `verification`, `owner`, `recommended_action`, and `top_detail` semantics for rendered validation.

Extension rules:

- New postures and capabilities should default to profile-driven inclusion, not template-only inclusion.
- Do not add a posture or capability in analysis code without also updating the profile and validator contract.
- Do not add a validator expectation for a posture or capability that cannot be enabled or disabled from the profile.
- Preserve backward compatibility for existing profiles unless the task explicitly asks for a contract change.

## OpenShift Live Vs Collected Mode

The OpenShift playbook supports:

- `report_mode=live`
- `report_mode=collected`
- `report_mode=auto`
- `report_mode=offline` as an alias to `collected`

Rules to preserve:

- `report_mode=auto` resolves to `collected` when collected-state inputs are provided.
- `report_mode=offline` must resolve to `collected`, not a separate report family.
- OpenShift API surface validation applies only to live runs.
- Collected-state fixture and case-bundle runs must not require a live OpenShift API probe.
- Resume/checkpoint behavior must work for both live and collected runs.

## Selector-Scoped Execution

OpenShift scoped runs are now first-class. Preserve the distinction between:

- requested render scope
  - `report_requested_postures`
  - `report_requested_capabilities`
- effective rendered scope
  - `report_effective_selected_postures`
  - `report_effective_selected_capabilities`
- execution prerequisite scope
  - `report_execution_selected_postures`
  - `cluster_health_profile_execution`

Rules to preserve:

- `selected_postures` and `selected_capabilities` control rendered scope, not only collection hints.
- capability-only runs may auto-include prerequisite posture execution facts, but should not broaden rendered scope beyond the requested capabilities plus any intentional owning posture render contract.
- selector dependency decisions come from:
  - `roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml`
- optional evidence reduction must be driven from that resolver, not from ad hoc `when` conditions scattered through loaders.

If you change selector behavior, verify:

- the scoped profile shape
- the dependency resolver
- the rendered report sections
- the manifest fields persisted by the checkpoint layer

## Artifact Workspace And Resume Contract

OpenShift report runs are artifact-first. The `.run-state` workspace is part of the contract.

Current workspace layout under `report_output_dir`:

- `.run-state/openshift/<mode>-artifacts/shared/`
- `.run-state/openshift/<mode>-artifacts/postures/`
- `.run-state/openshift/<mode>-artifacts/capabilities/`
- `.run-state/openshift/<mode>-artifacts/report/`

Important persisted artifacts include:

- `shared/collection.json`
- `shared/analysis-graph.json`
- `report/payload.json`
- final report Markdown and JSON

Resume behavior is artifact-granular, not just stage-granular. Preserve:

- `roles/report_common/tasks/save_run_checkpoint.yml`
- `roles/report_common/tasks/resolve_openshift_resume_artifact_plan.yml`
- `roles/report_common/tasks/load_openshift_shared_artifacts.yml`
- `roles/report_common/tasks/load_openshift_posture_artifacts.yml`
- `roles/report_common/tasks/load_openshift_capability_artifacts.yml`
- `roles/report_common/tasks/load_openshift_report_payload_artifact.yml`

When changing artifact metadata or report payload structure, keep the persisted manifest, payload loader, and resume invalidation logic aligned.

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

For selector-scoped OpenShift runs, also preserve the current optional-evidence reduction behavior:

- broad optional support inputs should be blanked before parse-time when the dependency resolver says they are out of scope
- do not force narrow runs to parse `cluster-compare`, `inspect`, `managed-gates`, `advisor`, `insights`, `omc`, or `sosreport` unless the resolved dependency contract actually requires them
- keep the loader gates aligned with `roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml`

## Key Sensitive Files

Be careful in these areas because they control top-level behavior:

- `playbooks/openshift_cluster_health_report.yml`
- `playbooks/k8s_cluster_health_report.yml`
- `templates/openshift_cluster_health_report.md.j2`
- `roles/analyze_openshift/tasks/day2.yml`
- `roles/analyze_openshift/tasks/core/`
- `roles/analyze_openshift/tasks/day2/`
- `roles/analyze_openshift/tasks/observability/`
- `roles/analyze_openshift/tasks/review_domains/`
- `roles/analyze_openshift/tasks/summary/`
- `roles/analyze_openshift/tasks/supportability_evidence/`
- `roles/analyze_openshift/tasks/collected_state_health/`
- `roles/analyze_common/tasks/security/`
- `roles/analyze_common/tasks/workload/`
- `roles/load_evidence_common/tasks/`
- `roles/load_evidence_openshift/tasks/`
- `roles/load_evidence_openshift_products/tasks/`
- `roles/load_evidence_openshift_product_slices/tasks/`
- `roles/report_common/tasks/main.yml`
- `roles/report_common/tasks/build_openshift_report_payload.yml`
- `roles/report_common/tasks/render_report_artifacts.yml`
- `roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml`
- `roles/report_common/tasks/resolve_openshift_resume_artifact_plan.yml`
- `roles/report_common/tasks/load_openshift_report_payload_artifact.yml`
- `roles/report_openshift/tasks/render_collected_state_report.yml`
- `roles/posture_*/tasks/`
- `roles/capability_*/tasks/`
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

Be mindful about verification. Code edits are not complete until the changed area has been checked at the right level.

- Always do syntax or compile validation for the files you changed when such checks exist.
- Run runtime validation when it makes sense for the touched path.
- Prefer proving the behavior with the nearest real execution path instead of relying only on static inspection.
- If a full runtime check is too expensive, run the narrowest realistic fixture, validator, or playbook path that exercises the changed behavior.
- If you cannot run an expected validation step, say so explicitly and state what remains unverified.

Expected verification by change type:

- Playbooks or Ansible task files:
  - run `ansible-playbook --syntax-check` for affected playbooks
  - run the relevant fixture or `scripts/validate_repo.sh` when behavior changed
- Python scripts:
  - run `python3 -m py_compile` on touched scripts
  - run the owning validator, helper, or fixture when behavior changed
- Report templates:
  - run template validation
  - run rendered-report validation through the relevant fixture when section content or gating changed
- Input profiles:
  - run profile validation
  - run rendered-report validation if posture or capability presence changed
- Shell scripts:
  - run `bash -n`
  - run the script or the narrowest safe invocation if behavior changed

For OpenShift runtime validation, prefer the narrowest realistic path first:

- selector-scoped collected-state runs for changed postures or capabilities
- synthetic resume or payload harnesses for artifact-first report/resume logic
- full `scripts/validate_repo.sh` before closing out broad contract changes

The goal is not just “syntax clean”. The goal is “unlikely to break the latest working repo behavior”.

## Change Discipline

- Prefer changing the smallest layer that owns the behavior.
- If you change a report contract, update:
  - implementation
  - validator
  - README or design docs when the user-facing behavior changed
- Do not add workaround wrappers that duplicate an existing cluster-type playbook contract.
- Preserve collected-state fixture support when adding live-cluster guardrails.
- Fail closed on wrong cluster type or wrong wrapper selection instead of producing a mixed report.
