# Cluster Health Extension Guide

This guide is the maintainer workflow for extending the repo without drifting away from the current report contract, execution model, or artifact model.

Use it when you need to:

- add a new OpenShift posture
- add a new OpenShift capability
- extend collection or analysis scope
- wire a new product integration into the report
- make selector-scoped execution honor new dependencies
- preserve collected-state and resume behavior while changing report logic

This guide focuses on the current architecture, not the earlier migration plan.

## Core Design Rules

Treat this repo as a report-contract codebase.

- profiles define what is in scope, expected, required, documented, and renderable
- collection and analysis roles define how evidence is gathered and interpreted
- posture and capability roles own section-specific synthesis and artifact mapping
- shared report roles own persistence, payload assembly, rendering, and resume logic
- templates render normalized report data; they should not become the only place where business logic lives

Current bias:

- prefer the smallest owning layer
- prefer role-local builders over shared one-off branches
- prefer helper scripts under `scripts/` over embedded Python in Ansible
- prefer selector-aware evidence reduction over broad always-on collection
- preserve both `live` and `collected` paths when adding behavior

## Current Architecture

### OpenShift Playbook

Primary entrypoint:

- [playbooks/openshift_cluster_health_report.yml](/Users/luqman/workspace/guides/openshift-health-check/playbooks/openshift_cluster_health_report.yml:1)

It supports:

- `report_mode=live`
- `report_mode=collected`
- `report_mode=auto`
- `report_mode=offline`

Current mode rules:

- `auto` resolves to `collected` when collected-state inputs are present
- `offline` is an alias to `collected`
- live OpenShift API validation runs only for `live`
- collected-state is first-class and must not require a live API probe

### Profile Contract

Canonical OpenShift catalog:

- [inputs/openshift-cluster-health-profile.yml](/Users/luqman/workspace/guides/openshift-health-check/inputs/openshift-cluster-health-profile.yml:1)

This file controls:

- enabled postures
- enabled capabilities
- `required` semantics
- owners
- docs
- verification text
- posture-to-capability relationships

If analysis or rendering can emit a posture or capability key, that key must exist in the profile.

### Posture Ownership

OpenShift posture sections now live under dedicated roles:

- `roles/posture_<key>/tasks/main.yml`
- optional `roles/posture_<key>/tasks/analysis.yml`
- `roles/posture_<key>/tasks/builder.yml`

Pattern:

- `analysis.yml`
  - owns posture-specific synthesis when that posture needs local summary logic
- `builder.yml`
  - maps already-computed facts into the persisted posture artifact contract
- `main.yml`
  - usually calls:
    - local analysis tasks when needed
    - `roles/posture_artifact_from_builder`

Shared posture artifact wrapper:

- [roles/posture_artifact_from_builder/tasks/main.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/posture_artifact_from_builder/tasks/main.yml:1)

### Capability Ownership

OpenShift capabilities now live under dedicated roles:

- `roles/capability_<key>/tasks/main.yml`
- `roles/capability_<key>/tasks/builder.yml`

Pattern:

- `builder.yml`
  - maps evidence and existing summaries into the capability artifact contract
- `main.yml`
  - usually delegates to:
    - `roles/capability_artifact_from_builder`

Shared capability artifact wrapper:

- [roles/capability_artifact_from_builder/tasks/main.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/capability_artifact_from_builder/tasks/main.yml:1)

### Shared Analysis And Evidence Layers

Large shared owners have been decomposed. Current task trees are intentionally split:

- `roles/analyze_common/tasks/security/`
- `roles/analyze_common/tasks/workload/`
- `roles/analyze_openshift/tasks/core/`
- `roles/analyze_openshift/tasks/day2/`
- `roles/analyze_openshift/tasks/observability/`
- `roles/analyze_openshift/tasks/review_domains/`
- `roles/analyze_openshift/tasks/summary/`
- `roles/analyze_openshift/tasks/supportability_evidence/`
- `roles/analyze_openshift/tasks/collected_state_health/`
- `roles/load_evidence_common/tasks/`
- `roles/load_evidence_openshift/tasks/`
- `roles/load_evidence_openshift_products/tasks/`
- `roles/load_evidence_openshift_product_slices/tasks/`

Do not collapse those back into one large file unless the contract explicitly changes.

### Shared Report Layer

Shared report ownership sits in:

- `roles/report_common/tasks/`
- `roles/report_openshift/tasks/`

Important responsibilities there:

- artifact persistence
- selector dependency resolution
- resume artifact planning
- artifact loading
- payload assembly
- report rendering
- final report path/status output

Key files:

- [roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml:1)
- [roles/report_common/tasks/resolve_openshift_resume_artifact_plan.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/resolve_openshift_resume_artifact_plan.yml:1)
- [roles/report_common/tasks/build_openshift_report_payload.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/build_openshift_report_payload.yml:1)
- [roles/report_common/tasks/load_openshift_report_payload_artifact.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/load_openshift_report_payload_artifact.yml:1)
- [roles/report_common/tasks/render_report_artifacts.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/render_report_artifacts.yml:1)
- [roles/report_openshift/tasks/render_collected_state_report.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_openshift/tasks/render_collected_state_report.yml:1)

## Artifact Workspace Contract

OpenShift runs are artifact-first.

Current workspace under `report_output_dir`:

- `.run-state/openshift/<mode>-artifacts/shared/`
- `.run-state/openshift/<mode>-artifacts/postures/`
- `.run-state/openshift/<mode>-artifacts/capabilities/`
- `.run-state/openshift/<mode>-artifacts/report/`

Important persisted files:

- `shared/collection.json`
- `shared/analysis-graph.json`
- `postures/<key>.json`
- `capabilities/<key>.json`
- `report/payload.json`
- final report Markdown
- final report JSON
- manifest/checkpoint JSON

Artifact metadata now matters. Posture and capability artifacts persist contract hints such as:

- section scope
- dependency keys
- shared inputs used
- upstream shared artifact hashes
- schema/repo contract metadata

If you change artifact shape, keep these aligned:

- persistence
- payload builder
- payload loader
- resume invalidation logic
- rendered output validators

## Selector-Scoped Execution

OpenShift selector scope is first-class.

User-facing inputs:

- `selected_postures`
- `selected_capabilities`

Current conceptual layers:

- requested scope
  - what the user explicitly asked for
- effective rendered scope
  - what should appear in the final report
- execution prerequisite scope
  - what must run to support the selected output safely

Important playbook facts:

- `report_requested_postures`
- `report_requested_capabilities`
- `report_effective_selected_postures`
- `report_effective_selected_capabilities`
- `report_execution_selected_postures`
- `cluster_health_profile_execution`

Rules:

- do not widen final rendered scope just because execution needed prerequisite facts
- do not assume all capabilities require their owning posture to render
- only add execution prerequisites where a capability truly depends on posture-owned synthesis
- dependency resolution must stay centralized in:
  - [roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml:1)

If you add a posture, capability, or evidence family that changes scoped behavior, update:

- profile/catalog entries
- selector dependency map
- loader gates
- runtime validation for the scoped path

## Resume Contract

Resume behavior is artifact-granular, not just stage-granular.

Current resume behavior checks:

- artifact presence on disk
- `completed_artifacts`
- `failed_artifacts`
- selector scope metadata
- dependency metadata
- shared-input metadata
- schema/repo contract metadata
- upstream shared artifact hashes

Shared resume files:

- [roles/report_common/tasks/save_run_checkpoint.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/save_run_checkpoint.yml:1)
- [roles/report_common/tasks/resolve_openshift_resume_artifact_plan.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/resolve_openshift_resume_artifact_plan.yml:1)

Payload-backed render resumes also rely on:

- `report/payload.json`
- [roles/report_common/tasks/load_openshift_report_payload_artifact.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/load_openshift_report_payload_artifact.yml:1)

Do not add new report-stage facts in a way that only exists in memory for fresh runs. If a resumed payload-backed render needs it, it should be restorable from `payload.json` or rebuilt intentionally.

## Helper Script Pattern

Current rule:

- do not embed Python heredocs in Ansible for non-trivial logic
- use helper scripts under `scripts/`
- call them with `ansible.builtin.command`

Typical use cases:

- evidence parsers
- analysis transforms
- report validators
- collected-state resource extraction
- supportability diagnostics helpers

When you add a helper:

1. place it under `scripts/`
2. make the Ansible task call it explicitly
3. validate with `python3 -m py_compile`
4. prefer JSON in and JSON out when practical

## Extending A Posture

Add a new posture only when you are introducing a real top-level operating domain.

### Required changes

1. Add the posture entry under `cluster_health_profile.postures`.
2. Populate at least:
   - `enabled`
   - `required`
   - `owner`
   - `notes`
   - `docs`
   - `verification`
   - `includes`
   - `satisfied_by_all` when appropriate
3. Add the section title mapping to:
   - [scripts/validate_openshift_report_output.py](/Users/luqman/workspace/guides/openshift-health-check/scripts/validate_openshift_report_output.py:1)
4. Add or extend the rendered section in:
   - [templates/openshift_cluster_health_report.md.j2](/Users/luqman/workspace/guides/openshift-health-check/templates/openshift_cluster_health_report.md.j2:1)
5. Create the owning role:
   - `roles/posture_<key>/tasks/main.yml`
   - `roles/posture_<key>/tasks/builder.yml`
   - `roles/posture_<key>/tasks/analysis.yml` when posture-specific synthesis is needed
6. Wire the posture into the OpenShift playbook execution chain if it is a renderable section.

### Design rules

- keep posture-specific synthesis in the posture role
- avoid putting new posture-specific business logic into one shared summary file
- do not create a posture for one narrow product integration
- use a new posture only when the report is answering a new operating question

## Extending A Capability

Add a capability when you need a checkable production expectation or a supported optional platform extension.

### Required changes

1. Add the capability entry under `cluster_health_profile.capabilities`.
2. Populate at least:
   - `enabled`
   - `required`
   - `criticality`
   - `expected_state`
   - `owner`
   - `evidence_required`
   - `notes`
   - `docs`
   - `verification`
3. Map it into a posture via `includes` or `satisfied_by_all`.
4. Create the owning role:
   - `roles/capability_<key>/tasks/main.yml`
   - `roles/capability_<key>/tasks/builder.yml`
5. Update the Day 2 path if needed:
   - [roles/analyze_openshift/tasks/day2.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/analyze_openshift/tasks/day2.yml:1)
   - related split tasks under `roles/analyze_openshift/tasks/day2/`
6. Make sure the report template renders it through the profile-gated Day 2 path.
7. Make sure the rendered output validator still passes.

### Design rules

- capability-specific artifact mapping belongs in the capability role builder
- do not rely on generic fallback remediation text
- do not leave `docs`, `verification`, `owner`, `recommended_action`, or `top_detail` empty
- if the capability can be satisfied from existing shared facts, do not force a posture execution prerequisite just for artifact convenience

## Decide Whether Collection Scope Must Change

Use this decision rule:

- profile-only change
  - existing evidence and analysis already support the new entry
- analyzer-only change
  - evidence already exists, but interpretation does not
- collection change
  - evidence does not exist yet in live or collected mode

Examples:

- adding `docs` or `verification`:
  - profile-only
- turning existing analysis graph facts into a new capability artifact:
  - analyzer-only
- adding a new `oc get`, must-gather parse, or support artifact parser:
  - collection change

## Extending Collection Safely

Treat collection changes as code changes, not as profile edits with extra steps.

1. Add the new collection path in the owning collector or loader role.
2. Add parsing or normalization, preferably through a helper script when the transform is non-trivial.
3. Add the parsed data to shared facts, analysis graph, or another intentional intermediate contract.
4. Update the owning analyzer, posture role, or capability role to consume it.
5. Update selector dependency resolution if the new evidence is optional or scope-dependent.
6. Update profile metadata only after the evidence path exists.
7. Document RBAC expectations if the command needs more than standard reader access.

Prefer existing collected resources first. Do not add a new live command when the same evidence already exists in must-gather, inspect, or another collected-state input.

## Evidence And Optional Support Sources

Optional support evidence is intentionally scoped now.

Potential sources include:

- `cluster-compare`
- `inspect`
- `managed-gates`
- `advisor export`
- Insights archive
- `omc`
- `etcd-ocp-diag`
- `sosreport`

Rules:

- narrow selector-scoped runs should not parse optional support inputs they do not need
- gate those inputs through:
  - [roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/report_common/tasks/resolve_openshift_selector_scope_dependencies.yml:1)
  - `roles/load_evidence_common/tasks/`
- if a new posture or capability needs an optional support source, add the dependency in the resolver instead of bypassing the loader gates

## RBAC And Privileged Collection

When extending live collection:

- prefer read-only `oc get` or `kubectl get`
- document custom RBAC requirements
- document when node debug or cluster-admin is required
- do not make privileged collection silently mandatory for normal report generation

OpenShift live support rules to preserve:

- `collect_live_sosreport=false` must disable node-debug-backed sosreport collection
- do not let `live_support_collection_profile=all` override that flag implicitly
- when privileged evidence is absent, degrade clearly instead of pretending the capability was assessed

Relevant references:

- [docs/ocp-health-check-sa-rbac.md](/Users/luqman/workspace/guides/openshift-health-check/docs/ocp-health-check-sa-rbac.md:1)
- [roles/collect_live_support_evidence/tasks/main.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/collect_live_support_evidence/tasks/main.yml:1)

## Scaffolding New Entries

Use the scaffolder when you want a clean profile snippet instead of rebuilding the YAML shape by hand.

Scaffold a capability:

```bash
python3 scripts/scaffold_cluster_health_entry.py capability external_dns_operator \
  --owner network \
  --criticality info \
  --expected-state present
```

Scaffold a posture:

```bash
python3 scripts/scaffold_cluster_health_entry.py posture ingress_and_dns \
  --owner network \
  --includes external_dns_operator,application_access_and_network_isolation
```

What it does:

- prints a YAML snippet to stdout
- fills required schema fields
- emits placeholder docs and verification text when omitted
- does not modify the profile automatically

Recommended workflow:

1. Run the scaffolder.
2. Paste the snippet into `inputs/openshift-cluster-health-profile.yml`.
3. Replace placeholders with real content.
4. Map the capability or posture relationship correctly.
5. Create the owning role-local builder and analysis files as needed.
6. Run narrow validation, then the full repo validator.

## Validation Workflow

### Full gate

Run this before closing out behavior changes:

```bash
scripts/validate_repo.sh
```

That validator is expected to preserve:

- YAML parsing
- playbook syntax checks
- Python compilation
- OpenShift report template validation
- profile validation
- rendered report validation
- OpenShift CI fixture render

### Narrow local loop

These are useful before the full gate:

```bash
python3 scripts/validate_cluster_health_profile.py \
  inputs/openshift-cluster-health-profile.yml

python3 scripts/validate_openshift_report_template.py \
  templates/openshift_cluster_health_report.md.j2

python3 -m py_compile scripts/validate_openshift_report_output.py

.venv/bin/ansible-playbook --syntax-check \
  playbooks/openshift_cluster_health_report.yml
```

### Runtime validation guidance

Prefer the narrowest realistic runtime path first:

- selector-scoped collected-state run for changed postures
- selector-scoped collected-state run for changed capabilities
- synthetic resume or payload harness for artifact-first report/resume changes
- full `tests/run_ci_report_fixture.sh` or `scripts/validate_repo.sh` for broader contract changes

Example scoped collected-state run:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=collected \
  -e case_bundle_path=tests/fixtures \
  -e selected_postures=platform_health,security_and_governance \
  -e report_output_dir=/private/tmp/ohc-scope-test \
  -e report_basename=scope-test
```

Example scoped capability run:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=collected \
  -e case_bundle_path=tests/fixtures \
  -e selected_capabilities=oauth_external_identity_provider,external_alert_delivery \
  -e report_output_dir=/private/tmp/ohc-cap-test \
  -e report_basename=cap-test
```

When changing vendor-managed telemetry detection or observability replacement semantics, also run:

```bash
python3 scripts/validate_vendor_managed_telemetry.py \
  tests/fixtures/vendor-managed-telemetry/mock-vendor-managed-telemetry.json
```

## End-To-End Checklist For A New Capability

Use this sequence:

1. Add the capability to the OpenShift profile.
2. Map it to a posture.
3. Create the owning `roles/capability_<key>/`.
4. Add analysis or Day 2 logic if needed.
5. Add or extend collection only if evidence is missing.
6. Update selector dependency resolution if the new capability introduces optional evidence needs.
7. Render a narrow scoped report from collected fixtures or another safe test bundle.
8. Run `scripts/validate_repo.sh`.

If the capability is optional or vendor-specific:

- keep it disabled or non-required by default unless it is part of the standard production baseline
- avoid `satisfied_by_all` unless it truly replaces a whole posture outcome
- do not treat partial metrics/logging tools as full posture replacements unless the contract explicitly says so
- update the vendor telemetry fixture and validator if the change affects observability vendor detection

## Common Mistakes

- adding a capability to the profile without mapping it to a posture
- adding a posture or capability entry without creating the owning role-local builder
- putting posture-specific synthesis back into a shared summary file
- putting capability-specific artifact logic in the template instead of the capability role
- changing rendered scope and execution scope as if they were the same thing
- bypassing selector dependency resolution with a local `when` shortcut
- adding a new optional support source without updating loader gates
- changing artifact metadata without updating resume invalidation logic
- storing important fresh-run-only facts in memory but not in `payload.json`
- hardcoding docs or remediation text in the template when profile or artifact metadata should own it
- adding a live command when the same evidence already exists in collected-state inputs
