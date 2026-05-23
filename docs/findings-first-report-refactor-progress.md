# Findings-First Report Refactor Progress

## Current Status

Status: `batch-3-complete`

Batch 3 is complete. The implementation plan is saved in `docs/findings-first-report-refactor-plan.md`.

## Resume Instructions

The findings-first refactor plan is complete. If more work is needed, start with targeted report quality improvements rather than changing the section contract again.

Suggested follow-ups:

1. Review generated report prose for customer tone and remove any remaining low-value detail.
2. Add narrow unit fixtures for the summary/findings validator edge cases.
3. Run `scripts/validate_repo.sh` before merge if a full validation gate is required.

## Batch Tracking

| Batch | Status | Notes |
| --- | --- | --- |
| Batch 1: Contract And Validators | `complete` | Design contract and validator required-heading expectations have been updated. Static validation passed. |
| Batch 2: Template And Data Refactor | `complete` | OpenShift postures and Day 2 capabilities now render with the shared findings-first section pattern. |
| Batch 3: Accuracy Hardening And Fixture Validation | `complete` | Legacy-heading checks and summary/findings consistency checks were added and validated through the collected CI fixture. |

## Validation Log

- Passed: `python3 -m py_compile scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py`
- Passed: `git diff --check -- docs/DESIGN-PRINCIPLE.md scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py docs/findings-first-report-refactor-progress.md docs/findings-first-report-refactor-plan.md`
- Passed after Batch 1 redo: `python3 -m py_compile scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py`
- Passed after Batch 1 redo: `git diff --check -- docs/DESIGN-PRINCIPLE.md docs/findings-first-report-refactor-plan.md docs/findings-first-report-refactor-progress.md scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py`
- Passed after Batch 2: `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- Passed after Batch 2: `python3 -m py_compile scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py`
- Passed after Batch 2: `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Passed after Batch 2: `bash -n tests/run_ci_report_fixture.sh`
- Passed after Batch 2: `bash tests/run_ci_report_fixture.sh`
- Passed after Batch 2: rendered Markdown and JSON validation through `scripts/validate_openshift_report_output.py`
- Passed after Batch 3: `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- Passed after Batch 3: `python3 -m py_compile scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py`
- Passed after Batch 3: `python3 scripts/validate_openshift_report_output.py reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Passed after Batch 3: `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Passed after Batch 3: `bash -n tests/run_ci_report_fixture.sh`
- Passed after Batch 3: `bash tests/run_ci_report_fixture.sh`

## Decisions Captured

- The report should move to `Health Score`, `Findings Summary`, and `Findings`.
- `Recommendations` should be removed as a heading.
- `Operating Questions` should be merged into the Findings table fields.
- The five-question remediation contract must remain intact.
- Findings Summary must be evidence-derived and must not contradict the Findings table.
- The implementation should happen in three batches.
- Each posture and each capability must follow the same customer-facing section pattern: `Health Score`, `Findings Summary`, and `Findings`.
- Each posture and capability must use only those three customer-facing subsections.
- Capability sections should not keep a separate reporting shape with `Leadership view`, `Technical focus`, `Assessment Summary`, or standalone unheaded `Checks` / `Findings` blocks as substitutes for the standard pattern.

## Batch 1 Changes

- Updated `docs/DESIGN-PRINCIPLE.md` to describe the findings-first section contract.
- Updated `scripts/validate_openshift_report_template.py` so the required section headings are `### Health Score`, `### Findings Summary`, and `### Findings`.
- Removed the template-validator requirement for `### Operating Questions`.
- Updated `scripts/validate_openshift_report_output.py` so rendered cluster sections require `### Findings Summary` instead of `### Recommendations`.
- Redone Batch 1 validator contract to require postures to contain only `Health Score`, `Findings Summary`, and `Findings` direct subsections.
- Redone Batch 1 rendered-report validator contract so capability sections must contain only `Health Score`, `Findings Summary`, and `Findings` at nested capability heading level.
- Did not add forbidden-heading checks for `### Recommendations` or `### Operating Questions` yet; that should happen after Batch 2 migrates the template.

## Batch 2 Changes

- Removed the OpenShift template `operating_questions` macro and stopped rendering `### Operating Questions`.
- Replaced posture `### Recommendations` sections with `### Findings Summary`.
- Converted posture detail headings under each posture to bold labels where needed, so direct posture subsections remain limited to `Health Score`, `Findings Summary`, and `Findings`.
- Refactored Day 2 capability rendering so each capability uses nested `Health Score`, `Findings Summary`, and `Findings` sections.
- Removed the legacy Day 2 `### Capability Assessments` wrapper heading.
- Merged capability checks and findings into one standard Findings table with owner, action, evidence, impact, and done-when fields.
- Updated the CI report fixture assertions so they expect the new nested capability section pattern and reject the legacy `### Capability Assessments` heading.

## Batch 3 Changes

- Added template and rendered-report validator checks that reject legacy `Recommendations`, `Operating Questions`, `Capability Assessments`, and capability assessment-summary headings.
- Added rendered-report validator checks that reject legacy capability labels such as `Leadership view` and `Technical focus`.
- Added Markdown parsing for standard Findings tables so validator checks can compare Findings Summary text against warning and critical rows.
- Added conservative contradiction checks so summaries cannot use clean-state language when the corresponding Findings table has warning or critical rows.
- Added checks requiring summaries to acknowledge critical or warning-level risk, gaps, review needs, or evidence limitations when the Findings table contains those severities.
- Scoped posture summary parsing so nested Day 2 capability summaries do not pollute the Day 2 posture-level summary validation.

## Risks To Watch

- Removing `Operating Questions` can accidentally remove owner or done-when guidance if the corresponding table rows are incomplete.
- Rewriting summaries manually can create contradictions with the Findings table.
- Overly broad validator changes can break the repo before the template migration is complete.
- Capability sections have a different rendering structure from posture sections and need separate review.
- Capability sections must be normalized to the same section structure as postures, not only lightly renamed.
- Missing evidence must remain distinct from healthy evidence.
