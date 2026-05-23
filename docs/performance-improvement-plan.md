# OpenShift Report Performance Improvement Plan

## Objective

Reduce end-to-end runtime for live OpenShift health report generation while preserving report accuracy, evidence traceability, collected-state support, and profile-gated rendering.

Current observed runtime is approximately 5 hours against a small-to-medium OpenShift cluster:

- 3 worker nodes
- about 100 namespaces
- about 30 installed operators

For this cluster size, the target runtime should be measured in tens of minutes for a normal live assessment run. Full support evidence collection may still take longer, but that cost must be intentional, visible, and tied to explicit inputs.

## Non-Negotiable Accuracy Rules

Performance changes must not introduce false positives, false negatives, or unsupported report language.

- Do not drop evidence silently. If evidence is skipped, filtered, capped, or unavailable, the report must say so.
- Do not convert missing evidence into `OK`, `pass`, or healthy wording.
- Do not weaken severity simply because a faster path was used.
- Do not infer that a control is absent unless the required evidence for that conclusion was actually collected and assessed.
- Do not infer that a control is present unless the matching evidence is explicit and traceable.
- Preserve profile-gated rendering from `inputs/openshift-cluster-health-profile.yml`.
- Preserve live and collected-state parity for the OpenShift report contract.
- Preserve selector-scoped execution behavior.
- Keep posture-specific logic inside the owning `roles/posture_<key>/` role where possible.
- Keep capability-specific logic inside the owning `roles/capability_<key>/` role where possible.

Every optimization must identify whether it changes:

- collection scope
- evidence fidelity
- analysis semantics
- report rendering
- only execution mechanics

## Success Metrics

Primary runtime targets:

- Fast live report: 20-45 minutes
- Standard live report: under 60 minutes
- Full support-heavy report: under 90 minutes when feasible, with clear visibility into optional collector cost

Quality targets:

- no new rendered-report validation failures
- no profile-gating regressions
- no live vs collected contract regressions
- no customer-visible wording that overstates health when evidence is partial
- no new `/tmp`, `/private`, or non-repo-local controller temp writes
- no Ansible worker crashes from large artifact handling

## Phase 1: Measure Before Changing Semantics

Goal: produce trustworthy timing data for the actual slow paths.

Add timing visibility for these stages:

- preflight
- OpenShift API validation
- core collection
- optional live support collection
- evidence loading
- OpenShift analysis
- posture artifact generation
- capability artifact generation
- shared payload build
- report rendering
- HTML generation
- PDF generation

Add per-collector duration reporting for live collectors:

- core `oc get` groups
- must-gather
- inspect
- cluster-compare
- insights archive
- managed-gates
- advisor export
- sosreport

Implementation guidance:

- Prefer a shared timing helper or existing callback extension.
- Persist timing data into `.run-state/openshift/<mode>-artifacts/shared/`.
- Render a concise timing summary in debug/log output first.
- Add report rendering only after the timing payload is stable.

Acceptance criteria:

- A completed run shows total time by stage.
- Live support collector timing is visible.
- Timing output does not change report findings.

Validation:

- `python3 -m py_compile` for changed helpers.
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`.
- OpenShift fixture or nearest realistic collected-state render.

## Phase 2: Define Performance Profiles

Goal: make expensive optional evidence explicit instead of hidden in the default path.

Add a profile variable:

```yaml
report_performance_profile: standard
```

Recommended profiles:

- `fast`: minimum evidence required for a normal health report.
- `standard`: balanced default for customer assessments.
- `full`: includes expensive optional support evidence.

Initial profile behavior:

- `fast`
  - disable sosreport
  - disable must-gather
  - disable inspect
  - disable cluster-compare unless explicitly requested
  - disable PDF generation by default
  - keep required API evidence for enabled postures and capabilities
- `standard`
  - collect API evidence
  - collect selected low-cost support artifacts
  - avoid node debug diagnostics unless requested
  - generate Markdown and JSON first
- `full`
  - allow all enabled support analyzers
  - allow PDF generation
  - preserve current deep support behavior

Accuracy guardrail:

- The rendered report must identify when optional support evidence was not collected.
- Missing optional support evidence must reduce diagnostic confidence, not produce failure findings by itself.

Acceptance criteria:

- `report_performance_profile=fast` reduces live collection scope.
- `report_performance_profile=standard` preserves current expected report breadth except clearly optional support paths.
- `report_performance_profile=full` preserves the deepest collection path.

Validation:

- Syntax check.
- Selector-scoped run for at least one posture.
- Full collected fixture render.

## Phase 3: Optimize API Collection

Goal: reduce redundant and expensive cluster API calls.

Actions:

- Inventory all `oc get` and `kubectl get` calls used by the OpenShift path.
- Identify duplicate collection of pods, namespaces, events, secrets, configmaps, RBAC, routes, CSVs, subscriptions, and operator resources.
- Prefer one collection source per resource family.
- Reuse `analysis_graph` instead of re-querying.
- Add explicit caps only for inherently noisy evidence such as events, and report the cap.
- Avoid namespace-by-namespace loops when a cluster-wide list is accurate and permitted.

Accuracy guardrail:

- Capping is acceptable for samples and noisy evidence.
- Capping is not acceptable for controls that require full inventory unless the report marks the result as partial.

Acceptance criteria:

- The collection plan has one owner per resource family.
- Per-collector timing shows reduced duplicate collection.
- Report findings still map to collected evidence.

Validation:

- Compare rendered JSON summary counts before and after on the same fixture.
- Check high-risk sections manually: node capacity, workload health, security governance, observability, Day 2 capabilities.

## Phase 4: Reduce Ansible Large-Object Overhead

Goal: keep Ansible as the orchestrator and move large JSON aggregation into focused helper scripts.

Target patterns:

- large `set_fact` loops
- repeated `from_json` / `to_json` transformations
- list building inside Ansible loops
- repeated filtering of pods, events, namespaces, and RBAC objects

Preferred pattern:

- pass large structured input to a helper through stdin
- return compact summary JSON
- keep detailed evidence in artifact files when traceability is needed
- keep helper ownership aligned with the role that owns the finding

Candidate areas:

- namespace governance summaries
- event reason aggregation
- pod health aggregation
- workload ownership mapping
- operator inventory summaries
- RBAC and reference usage
- route and ingress exposure summaries

Accuracy guardrail:

- Helper scripts must be deterministic.
- Helper output must preserve enough detail to support the rendered finding.
- Do not collapse distinct conditions into one generic warning.

Acceptance criteria:

- Hot Ansible loops are replaced only where the helper output matches or improves existing semantics.
- Fixture output is equivalent or intentionally improved.
- No new generic report noise is introduced.

Validation:

- `python3 -m py_compile` for new or changed helpers.
- Targeted helper tests or smoke input checks.
- Rendered report validation.

## Phase 5: Avoid Large Payloads In Ansible Variables

Goal: prevent controller memory pressure and worker crashes.

Actions:

- Continue removing `slurp` for large local JSON artifacts.
- Avoid `copy: content=` for large JSON payloads.
- Load summaries through helper scripts.
- Persist large artifacts as files.
- Pass only compact summary maps through Ansible variables.

High-risk artifacts:

- `analysis-graph.json`
- `payload.json`
- posture artifacts
- capability artifacts
- event and pod inventories

Accuracy guardrail:

- Artifact hash and resume invalidation logic must still detect stale or changed evidence.
- Resume behavior must not skip recomputation when dependencies changed.

Acceptance criteria:

- No large report artifact is base64-loaded through Ansible.
- Resume planning reads only the fields it needs.
- Dead-worker risk is reduced under live cluster payload sizes.

Validation:

- Resume from a live failure.
- Resume from a collected failure.
- Full fixture run.

## Phase 6: Defer Expensive Rendering

Goal: prevent PDF and HTML generation from blocking assessment feedback.

Actions:

- Generate Markdown and JSON first.
- Validate Markdown and JSON.
- Generate HTML and PDF as optional final steps.
- Allow PDF-only rerender from existing report payload.

Recommended variables:

```yaml
report_generate_html: true
report_generate_pdf: false
```

for fast or standard runs.

Accuracy guardrail:

- Markdown and JSON are the source report artifacts.
- HTML and PDF rendering must not change findings or section order.

Acceptance criteria:

- Report data can be generated and validated without PDF.
- PDF can be rendered later without recollecting cluster evidence.

Validation:

- Markdown/JSON-only render.
- PDF rerender from existing payload.

## Phase 7: Tune Parallelism With Resource Awareness

Goal: improve throughput without causing controller instability.

Current default resource budget:

```yaml
local_resource_budget_cpu_pct: 80
local_resource_budget_mem_pct: 80
```

Expected effective caps:

- 4 vCPU / 16 GiB RAM: about 3 workers
- 8 vCPU / 24 GiB RAM: about 6 workers

Actions:

- Keep resource-aware caps.
- Separate collection parallelism from analysis parallelism where useful.
- Reduce parallelism automatically during large local artifact loading if memory pressure is detected.
- Log effective worker counts at startup.

Accuracy guardrail:

- Parallel execution must not introduce ordering-dependent findings.
- Any helper that writes artifacts must write to unique paths or use atomic output.

Acceptance criteria:

- Effective worker count is visible.
- Higher parallelism improves runtime without worker death.
- Repeated fixture runs produce stable report output.

Validation:

- Run fixture twice and compare rendered JSON for stable findings.
- Run live resume path after an interrupted run.

## Phase 8: Add Regression Checks For Report Accuracy

Goal: protect against performance changes altering findings incorrectly.

Add or extend checks for:

- enabled profile sections appear
- disabled profile sections do not appear
- missing evidence does not render as healthy
- optional absent capabilities do not render as required gaps
- collected-state and live payloads preserve the same report contract
- workload health and node capacity summaries do not change unexpectedly

Candidate validation approach:

- keep existing rendered report validator
- add focused JSON assertions for high-risk posture summaries
- compare fixture summary counts before and after optimization work

Acceptance criteria:

- Performance changes must pass report contract validation.
- Any changed finding count must be explained by a deliberate semantics change.

## Work Order

Recommended implementation order:

1. Add stage and collector timing.
2. Add `report_performance_profile`.
3. Separate fast, standard, and full support collection behavior.
4. Optimize duplicate API collection.
5. Replace remaining hot Ansible loops with role-owned helpers.
6. Remove remaining large artifact variable paths.
7. Defer PDF rendering by profile.
8. Add accuracy regression assertions for high-risk sections.

## First Pass Deliverables

The first implementation pass should produce:

- timing artifact under `.run-state`
- clear log summary of slow stages
- no report finding changes
- no profile contract changes
- validation evidence from syntax checks and the closest fixture path

After that first pass, optimization should be driven by measured runtime data rather than assumptions.
