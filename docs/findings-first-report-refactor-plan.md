# Findings-First Report Refactor Plan

## Purpose

Refactor the OpenShift customer report so posture and capability sections lead with an evidence-derived `Findings Summary`, then a detailed `Findings` table. Remove the separate `Recommendations` and `Operating Questions` subsections from customer-facing sections without losing the current remediation contract.

The goal is to make the report easier to read while preserving accuracy. The summary must not overstate health, hide missing evidence, or contradict the findings table.

## Target Section Contract

Each customer-facing posture and capability section must render with only these three subsection labels, in this order:

1. `Health Score`
2. `Findings Summary`
3. `Findings`

For top-level posture sections those labels render as `###` headings. For nested capability sections, the heading depth follows the nesting level, but the labels and order stay the same.

There should not be one report pattern for postures and a different report pattern for capabilities. Capability sections may include capability-specific rows and values inside the allowed tables or summary text, but they must still use only the same three-section structure and the same findings-table contract.

The `Findings` table must continue to answer the five operating questions:

| Operating question | Findings table field |
| --- | --- |
| What is the gap? | `Finding` and `Current State` |
| Why does it matter? | `Business Impact` |
| What should be done? | `Action Plan` |
| Who owns it? | `Suggested Owner` |
| How can the team tell it is fixed? | `Done When` |

The report should no longer render these customer-facing subsections:

- `### Recommendations`
- `### Operating Questions`

## Posture And Capability Consistency Rules

Postures and capabilities must follow the same customer-facing reporting shape.

Required structure:

- Each posture section renders `### Health Score`, `### Findings Summary`, and `### Findings`.
- Each capability section renders `Health Score`, `Findings Summary`, and `Findings` at the appropriate nested heading level.
- Posture and capability sections must not render any other customer-facing subsections.
- Capability sections should not use alternate headings such as `Leadership view`, `Technical focus`, `Assessment Summary`, `Checks`, or unheaded `Findings` blocks as substitutes for the standard structure.
- If a capability needs supporting checks, those checks should be summarized into the standard Findings table instead of being rendered as a separate subsection.
- The same table intent applies to both postures and capabilities: gap, current state, business impact, technical evidence, action plan, suggested owner, and done-when.
- Profile gating still controls whether a posture or capability appears; once rendered, the section shape should be consistent.

## Summary Accuracy Rules

The `Findings Summary` must be derived from the same finding state rendered in the table.

Rules:

- If any row is `CRITICAL`, the summary must call out critical risk in plain language.
- If any row is `WARNING`, the summary must call out the warning-level gap or evidence limitation.
- If evidence is missing or not collected, the summary must say the area is not fully evidenced instead of describing it as healthy.
- If all rows are `OK`, the summary may say no remediation was identified for this run, but should avoid implying future risk is impossible.
- If a row is `OK`, the action text should not recommend remediation unless it is framed as ongoing maintenance.
- The summary must not introduce a new finding that is absent from the table.
- The summary must not hide an owner, action, or done-when signal that exists in the table.

## Wording Principles

Use customer-facing language that is clear to junior engineers and useful to leadership:

- Prefer short, direct sentences.
- Explain why a finding matters before naming tools or implementation details.
- Avoid overly authoritative language when a finding is based on partial evidence.
- Avoid noisy generic text such as "review expected evidence" unless the evidence is actually missing.
- Use product recommendations only where the evidence supports them.
- Keep technical details in the `Technical Evidence` column, not in the summary narrative.

## Source Guidance

Use current authoritative guidance to keep wording accurate:

- Red Hat OpenShift documentation for ClusterOperator, update, lifecycle, backup, supportability, and OpenShift-specific behavior.
- Red Hat OpenShift GitOps documentation for GitOps and declarative application delivery language.
- Kubernetes documentation for workload probes, scheduling, node pressure, and portable workload health behavior.
- Red Hat OADP documentation for application backup language and for avoiding overstating OADP as full cluster or etcd disaster recovery.
- Existing repo design notes and profile metadata for report ownership, required/evidence semantics, and section order.

## Batch Plan

### Batch 1: Contract And Validators

Scope:

- Update `docs/DESIGN-PRINCIPLE.md` to document the findings-first section contract.
- Update `scripts/validate_openshift_report_template.py`.
- Update `scripts/validate_openshift_report_output.py`.
- Require `### Findings Summary` and `### Findings`.
- Stop requiring `### Recommendations` and `### Operating Questions`.
- Add forbidden checks for old customer-facing `### Recommendations` and `### Operating Questions` headings once the template refactor lands.

Validation:

- `python3 -m py_compile scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py`
- Template validation should be run after Batch 2 when the template has been refactored.

### Batch 2: Template And Data Refactor

Scope:

- Update `templates/openshift_cluster_health_report.md.j2`.
- Replace each `### Recommendations` block with `### Findings Summary`.
- Remove each `### Operating Questions` block.
- Preserve every `Findings` table row unless a row is demonstrably redundant or inaccurate.
- Refactor Day 2 capability sections so each rendered capability uses the same `Health Score`, `Findings Summary`, and `Findings` pattern as posture sections.
- Remove capability-only customer-facing patterns such as `Leadership view`, `Technical focus`, `Assessment Summary`, and standalone unheaded `Checks` / `Findings` blocks by folding their useful content into `Findings Summary` or the standard `Findings` table.
- Keep profile-gated rendering unchanged.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Template validator.
- Focused rendered-report validation if a narrow fixture path is available.

### Batch 3: Accuracy Hardening And Fixture Validation

Scope:

- Add or extend report validation checks that compare summary language against findings table severity.
- Prevent summaries from saying an area is healthy when findings include warning, critical, missing evidence, or not-collected states.
- Run the collected CI fixture.
- Compare rendered Markdown/JSON and explain intentional shape changes.
- Tune noisy or misleading summary wording found during fixture review.

Validation:

- `python3 -m py_compile` for touched Python scripts.
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered Markdown validation.
- Rendered JSON validation.
- Spot-check highest-risk sections: Platform Health, Backup And Disaster Recovery, Observability, Security And Governance, Workload Health, Declarative Operations, and Day 2 Production Readiness.

## Acceptance Criteria

- Customer-facing posture and capability sections no longer render `### Recommendations` or `### Operating Questions`.
- Each posture section renders `### Health Score`, `### Findings Summary`, and `### Findings`.
- Each capability section renders `### Health Score`, `### Findings Summary`, and `### Findings`.
- Posture and capability sections follow the same customer-facing reporting pattern and heading order.
- Posture and capability sections do not render any additional customer-facing subsections beyond `Health Score`, `Findings Summary`, and `Findings`.
- The five-question remediation contract remains present in the Findings table.
- Findings Summary does not contradict finding severities or evidence state.
- Missing evidence is not rendered as healthy.
- Existing profile gating still controls section presence.
- OpenShift collected-state fixture passes.
- Rendered report validator passes.

## Out Of Scope

- Changing section order.
- Adding or removing enabled postures or capabilities.
- Changing scoring semantics unless a contradiction or false positive is found.
- Adding new product recommendations without evidence-backed applicability.
- Changing Kubernetes/provider report contracts unless separately requested.
