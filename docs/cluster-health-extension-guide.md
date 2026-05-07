# Cluster Health Extension Guide

This guide is the maintainer workflow for extending the OpenShift cluster health report without drifting away from the current model.

Use it when you need to:

- add a new posture
- add a new capability
- extend scan scope to collect new evidence
- wire a new capability into the report without breaking the default production baseline

## Design Rules

Keep this split:

- profile data controls what is expected, required, grouped, owned, documented, and verified
- analyzer code controls how evidence is collected, parsed, and scored
- report templates render normalized posture and capability output without capability-specific hardcoding

Treat `inputs/openshift-cluster-health-profile.yml` as the canonical OpenShift capability catalog. If analyzer logic can emit a capability key, that key must be declared there, even when the capability is optional and disabled by default.

If a change does not need new evidence or new analyzer logic, prefer a profile-only change.

## Repo Map

- Canonical OpenShift profile:
  [inputs/openshift-cluster-health-profile.yml](/Users/luqman/workspace/guides/openshift-health-check/inputs/openshift-cluster-health-profile.yml:1)
- OpenShift Day 2 analyzer:
  [roles/analyze_openshift/tasks/day2.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/analyze_openshift/tasks/day2.yml:1)
- OpenShift report template:
  [templates/openshift_cluster_health_report.md.j2](/Users/luqman/workspace/guides/openshift-health-check/templates/openshift_cluster_health_report.md.j2:1)
- Profile validator:
  [scripts/validate_cluster_health_profile.py](/Users/luqman/workspace/guides/openshift-health-check/scripts/validate_cluster_health_profile.py:1)
- Rendered report validator:
  [scripts/validate_openshift_report_output.py](/Users/luqman/workspace/guides/openshift-health-check/scripts/validate_openshift_report_output.py:1)
- Entry scaffolder:
  [scripts/scaffold_cluster_health_entry.py](/Users/luqman/workspace/guides/openshift-health-check/scripts/scaffold_cluster_health_entry.py:1)

## Scaffolding New Entries

Use the scaffolder when you want a clean starting snippet instead of rebuilding the YAML shape by hand.

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
- fills every required schema field
- emits placeholder `docs` and `verification` lines when you do not provide them
- does not modify the profile automatically

Recommended workflow:

1. Run the scaffolder.
2. Paste the snippet into `inputs/openshift-cluster-health-profile.yml`.
3. Replace placeholder notes, docs, and verification with real content.
4. Map the capability to a posture or add the new posture mapping.
5. Run `scripts/validate_repo.sh`.

## Add A Posture

Add a new posture only when you are introducing a real top-level operating domain.

1. Add the posture entry under `cluster_health_profile.postures`.
2. Populate:
   - `enabled`
   - `required`
   - `owner`
   - `notes`
   - `docs`
   - `verification`
   - `includes`
   - `satisfied_by_all`
3. If the posture is capability-backed, map capabilities through `includes`.
4. If a full alternate capability can satisfy the posture, list it in `satisfied_by_all`.
   Current safe examples are full observability replacements such as `dynatrace_observability`, `datadog_observability`, or `splunk_observability`.
5. Do not add template-only posture logic unless the posture is a synthesized summary section like Day 2 production readiness.

Use a new posture only when the section answers a distinct operating question. Do not create a new posture for a single product integration or a narrow implementation detail.

## Add A Capability

Add a capability when you need a checkable production expectation or a supported optional platform extension.

1. Add the capability entry under `cluster_health_profile.capabilities`.
2. Populate:
   - `enabled`
   - `required`
   - `criticality`
   - `expected_state`
   - `owner`
   - `evidence_required`
   - `notes`
   - `docs`
   - `verification`
3. Map the capability into a posture through `includes` or `satisfied_by_all`.
4. If the capability should be analyzed in Day 2 readiness, add or update the analyzer logic in [day2.yml](/Users/luqman/workspace/guides/openshift-health-check/roles/analyze_openshift/tasks/day2.yml:1).
5. Ensure the analyzer produces:
   - at least one check
   - specific findings when the capability is present but unhealthy
   - a concrete `recommended_action`

Do not rely on generic fallback action text. The rendered output validator will fail it.

## Decide Whether Scan Scope Must Change

Use this decision rule:

- Profile-only change:
  existing evidence already proves the capability or posture
- Analyzer-only change:
  evidence is already collected, but the repo does not interpret it yet
- Scan-scope change:
  the repo does not collect the evidence needed to evaluate the new capability

Examples:

- Add `docs` or `verification` to an existing capability:
  profile-only
- Score an already-collected CRD:
  analyzer-only
- Add a new `oc get` or parse a new support artifact:
  scan-scope change

## Extend Scan Scope Safely

Treat scan-scope changes as code changes, not as profile edits with extra steps.

1. Add the new collection path in the appropriate collector role.
2. Add the parsed data to the analysis graph or report payload.
3. Update the analyzer to consume the new evidence.
4. Update profile metadata only after the evidence path exists.
5. Document RBAC expectations for the new command if it needs more than reader access.

Prefer existing collected resources first. Add a new command only when the current evidence really is not enough.

## RBAC And Command Scope

When adding scan scope:

- prefer read-only `oc get` or `kubectl get`
- document when the command needs custom RBAC
- document when the command needs `cluster-admin` or node debug access
- avoid adding privileged collection to the default path unless it materially improves production-readiness coverage

If a capability depends on privileged evidence, the analyzer should degrade clearly when that evidence is absent instead of pretending the capability was assessed.

## Validation Workflow

Run these before committing:

```bash
scripts/validate_repo.sh
```

If you want a narrower local loop before the full repo gate, these remain useful:

```bash
python3 scripts/validate_cluster_health_profile.py \
  inputs/openshift-cluster-health-profile.yml

python3 scripts/validate_openshift_report_template.py \
  templates/openshift_cluster_health_report.md.j2

ANSIBLE_LOCAL_TEMP=/tmp/ansible-local \
ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote \
.venv/bin/ansible-playbook --syntax-check \
  playbooks/openshift_cluster_health_report.yml

bash tests/run_ci_report_fixture.sh

python3 scripts/validate_openshift_report_output.py <report.md> <report.json>
```

The standard `scripts/validate_repo.sh` path now includes the OpenShift fixture render plus rendered-output validation. The rendered-output validator checks that:

- required capability sections are present
- capability assessment completed
- capability sections have non-empty docs and verification
- capability sections do not fall back to generic remediation text
- capability sections include mapped checks

When changing vendor-managed telemetry detection or `satisfied_by_all` observability replacements, also run:

```bash
python3 scripts/validate_vendor_managed_telemetry.py \
  tests/fixtures/vendor-managed-telemetry/mock-vendor-managed-telemetry.json
```

## Adding A Capability End To End

Use this sequence:

1. Add the capability to the built-in profile.
2. Map it to a posture.
3. Add analyzer logic.
4. Add or extend evidence collection only if needed.
5. Render a report from a fixture or collected-state bundle.
6. Run `scripts/validate_repo.sh` or, at minimum, the fixture render plus output validator.

If the capability is optional or vendor-specific:

- keep it disabled or non-required by default unless it is part of the standard production baseline
- avoid using `satisfied_by_all` unless it truly replaces a whole posture outcome
- do not treat metrics-only or logs-only tools as full posture replacements; for example `appdynamics_observability` and `loki_stack_logging` are extension context, not full observability replacements
- update the vendor telemetry fixture and validator when the change affects metrics-vendor or log-vendor detection semantics
- for customer-specific optional platforms or vendor-managed extensions such as Dynatrace, Datadog, Splunk, ACM, or ODF, keep the built-in defaults off and use the OpenShift profile file to opt in explicitly when that platform is actually in scope

## Common Mistakes

- adding a capability to the profile but not mapping it to a posture
- adding a capability check without any finding path for the unhealthy case
- hardcoding docs in the template instead of using capability metadata
- adding a scan command when the evidence is already in must-gather
- using a vendor integration as a posture replacement when it only covers part of the posture
