# Performance Improvement Progress

## Current Phase

Phase 1 complete. Next phase should reduce duplicate artifact/payload load and render-time work without changing report semantics.

## Phase 1 Checklist

- [x] Create durable progress file for context recovery.
- [x] Add reusable timing-event task.
- [x] Add timing-artifact builder helper.
- [x] Add timing-artifact persistence task.
- [x] Wire timing events into the OpenShift live workflow.
- [x] Wire timing events into the OpenShift collected-state workflow.
- [x] Validate Python helpers.
- [x] Run OpenShift playbook syntax check.
- [x] Run nearest fixture/report validation.

## Accuracy Guardrails

- Timing instrumentation must not change collection scope.
- Timing instrumentation must not change analysis semantics.
- Timing instrumentation must not change report findings.
- Timing instrumentation must persist evidence about runtime only.

## Resume Notes

The timing artifact is intended to be written under:

```text
reports/.run-state/openshift/<mode>-artifacts/shared/timing.json
```

The first implementation pass should only add measurement. Optimization decisions should wait until timing data shows where the run is spending time.

## Phase 1 Validation Results

- `python3 -m py_compile scripts/build_report_timing_artifact.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`

The collected-state fixture completed with `failed=0` and rendered report validation passed.

Latest fixture timing artifact:

```text
reports/.run-state/openshift/collected-artifacts/shared/timing.json
```

Initial collected fixture stage timings:

- `evidence_loading`: 27.54 seconds
- `analysis_and_artifact_build`: 217.04 seconds
- `report_rendering`: 31.84 seconds
- `workflow`: 297.86 seconds

Granular timing validation:

- Confirmed the collected fixture writes granular sub-stage timings to `reports/.run-state/openshift/collected-artifacts/shared/timing.json`.
- The timing artifact contains 22 raw timing events and 11 stage summaries.

Latest granular collected fixture stage timings:

- `evidence_loading`: 27.98 seconds
- `collected_preparation`: 1.91 seconds
- `common_analysis`: 31.90 seconds
- `openshift_analysis`: 112.73 seconds
- `collected_health_synthesis`: 6.64 seconds
- `posture_artifact_build`: 140.59 seconds
- `capability_artifact_build`: 312.33 seconds
- `shared_artifact_persistence`: 48.95 seconds
- `analysis_and_artifact_build`: 696.91 seconds
- `report_rendering`: 355.96 seconds
- `workflow`: 1198.36 seconds

## Next Work

Phase 2 target:

- Reduce duplicate artifact and payload load/render work first, because the latest timing data shows report rendering and artifact persistence are significant controller-side costs.
- Start with the report assembly path in `roles/report_common` and `roles/report_openshift`; keep posture and capability findings unchanged.
- Use collected-state fixture validation after each optimization slice to verify report shape and findings stay stable.

## Phase 2 Slice 1

Change made:

- Serialize the final report payload once into workspace `report/payload.json`.
- Copy the canonical payload to the final JSON report and workspace JSON report instead of running duplicate large `to_nice_json` serializations.
- Applied to both live report rendering and collected-state report rendering paths.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Confirmed `report/payload.json`, output JSON, and workspace report JSON are byte-identical for the collected fixture.

Latest collected fixture timing after Slice 1:

- `evidence_loading`: 103.78 seconds
- `collected_preparation`: 4.62 seconds
- `common_analysis`: 73.77 seconds
- `openshift_analysis`: 202.13 seconds
- `collected_health_synthesis`: 9.91 seconds
- `posture_artifact_build`: 188.84 seconds
- `capability_artifact_build`: 264.01 seconds
- `shared_artifact_persistence`: 18.28 seconds
- `analysis_and_artifact_build`: 792.21 seconds
- `report_rendering`: 273.60 seconds
- `workflow`: 1326.70 seconds

Observed next hotspot:

- Per-posture and per-capability artifact persistence has high task overhead; each artifact currently pays for builder selection, directory checks, JSON write, and manifest tracking separately.
- Report rendering still spends substantial time loading/merging artifacts and rendering/copying Markdown; optimize this next without changing section content or profile gating.

## Phase 2 Slice 2

Change made:

- Added buffered posture and capability artifact persistence.
- Each posture/capability role still owns and builds its artifact payload locally.
- The shared writer now buffers artifact payloads in memory and flushes each group once to the existing individual JSON artifact files.
- Added `scripts/write_json_artifact_map.py` to write keyed artifact maps safely as `<key>.json` files.
- Added `report_artifact_persistence_mode: buffered` in `group_vars/all.yml`; immediate write mode is still available by overriding the variable.
- Added a precomputed Day 2 capability section lookup to avoid repeatedly scanning the full capability list for each capability artifact.

Validation:

- `python3 -m py_compile scripts/write_json_artifact_map.py scripts/build_report_timing_artifact.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Confirmed artifact files were written as individual files: 12 posture artifacts and 25 capability artifacts in the collected fixture.
- Confirmed `report/payload.json`, output JSON, and workspace report JSON are byte-identical for the collected fixture.

Latest collected fixture timing after Slice 2:

- `evidence_loading`: 27.25 seconds
- `collected_preparation`: 1.36 seconds
- `common_analysis`: 18.76 seconds
- `openshift_analysis`: 54.22 seconds
- `collected_health_synthesis`: 3.13 seconds
- `posture_artifact_build`: 47.86 seconds
- `capability_artifact_build`: 51.42 seconds
- `shared_artifact_persistence`: 5.03 seconds
- `analysis_and_artifact_build`: 190.65 seconds
- `report_rendering`: 31.46 seconds
- `workflow`: 270.77 seconds

Observed next hotspot:

- The fixture is back near the original fast baseline, but analysis still dominates.
- Next work should target repeated Ansible loop/set_fact transforms in OpenShift analysis and report-domain assembly, especially places that can move deterministic list/dict projection into helper scripts without changing findings.

## Phase 2 Slice 3

Change made:

- Moved OpenShift node baseline projection from an Ansible per-node `set_fact` loop into `scripts/build_node_baseline_facts.py`.
- The helper now resolves valid OpenShift nodes, NotReady nodes, pressure nodes, primary role counts, kubelet version counts, and control-plane/worker/infra counts.
- `roles/analyze_openshift/tasks/core/node_baseline.yml` still owns when the node baseline runs and still publishes the same Ansible facts for downstream analysis.

Validation:

- `python3 -m py_compile scripts/build_node_baseline_facts.py scripts/write_json_artifact_map.py scripts/build_report_timing_artifact.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Confirmed `report/payload.json`, output JSON, and workspace report JSON are byte-identical for the collected fixture.

Latest collected fixture timing after Slice 3:

- `evidence_loading`: 27.21 seconds
- `collected_preparation`: 1.56 seconds
- `common_analysis`: 19.12 seconds
- `openshift_analysis`: 52.58 seconds
- `collected_health_synthesis`: 2.97 seconds
- `posture_artifact_build`: 52.23 seconds
- `capability_artifact_build`: 49.98 seconds
- `shared_artifact_persistence`: 4.96 seconds
- `analysis_and_artifact_build`: 192.86 seconds
- `report_rendering`: 31.25 seconds
- `workflow`: 272.80 seconds

Observed next hotspot:

- OpenShift analysis still contains several per-item Ansible loops that are safe candidates for helper migration, especially platform component summaries and node capacity summaries.
- Next slice should target `roles/analyze_openshift/tasks/core/platform_components.yml` or `roles/analyze_openshift/tasks/core/node_capacity.yml`, with the same validation guardrail.

## Phase 2 Slice 4

Change made:

- Moved OpenShift platform component projection from multiple Ansible `set_fact` loops into `scripts/build_platform_component_facts.py`.
- The helper now builds cluster version update facts, ClusterOperator health lists, ClusterOperator status map, operator version mismatches, ingress controller summaries/issues, and infrastructure component summaries/issues.
- `roles/analyze_openshift/tasks/core/platform_components.yml` still owns when platform component analysis runs and still publishes the same Ansible facts for downstream report sections.
- Removed the later summary-stage ClusterOperator version mismatch loop because the helper now produces `cluster_operator_version_mismatches` from the same source evidence.

Validation:

- `python3 -m py_compile scripts/build_platform_component_facts.py scripts/build_node_baseline_facts.py scripts/write_json_artifact_map.py scripts/build_report_timing_artifact.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Confirmed `report/payload.json`, output JSON, and workspace report JSON are byte-identical for the collected fixture.

Latest collected fixture timing after Slice 4:

- `evidence_loading`: 26.35 seconds
- `collected_preparation`: 1.42 seconds
- `common_analysis`: 19.69 seconds
- `openshift_analysis`: 51.95 seconds
- `collected_health_synthesis`: 2.92 seconds
- `posture_artifact_build`: 47.45 seconds
- `capability_artifact_build`: 52.16 seconds
- `shared_artifact_persistence`: 5.13 seconds
- `analysis_and_artifact_build`: 189.83 seconds
- `report_rendering`: 31.80 seconds
- `workflow`: 269.72 seconds

Observed next hotspot:

- The fixture now spends most time in common analysis loops, OpenShift analysis loops, artifact builder fan-out, and final report rendering.
- Next safe slice should target `roles/analyze_openshift/tasks/core/node_capacity.yml` or common workload/security loops that iterate pods/workloads with repeated `set_fact`, preserving each section's current finding semantics.

## Phase 2 Slice 5

Change made:

- Moved OpenShift node capacity projection from the per-node Ansible loop in `roles/analyze_openshift/tasks/core/node_capacity.yml` into `scripts/build_node_capacity_facts.py`.
- The helper preserves the existing lookup precedence for scheduled pod count:
  - Prometheus/node pod count map
  - fallback node pod count map
  - direct pod evidence from the analysis graph or collected pod input
- The helper publishes the same downstream facts:
  - `node_capacity_summary`
  - `node_capacity_summary_by_density_desc`
  - `node_capacity_summary_by_density_asc`
- The role remains the owner of when node capacity analysis runs and only normalizes the helper output back into Ansible facts.

Validation:

- `python3 -m py_compile scripts/build_node_capacity_facts.py scripts/build_platform_component_facts.py scripts/build_node_baseline_facts.py scripts/write_json_artifact_map.py scripts/build_report_timing_artifact.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Confirmed `report/payload.json`, output JSON, and workspace report JSON are byte-identical for the collected fixture.
- Spot-checked rendered node density tables: `domains.node_health_and_capacity.node_capacity_summary_by_density_desc` and `node_capacity_summary_by_density_asc` contain the expected `master-0` and `worker-0` rows.

Latest collected fixture timing after Slice 5:

- This run was materially slower across all stages than the prior baseline, so it should be treated as validation timing rather than a clean performance comparison.
- `evidence_loading`: 70.70 seconds
- `collected_preparation`: 3.98 seconds
- `common_analysis`: 50.36 seconds
- `openshift_analysis`: 152.74 seconds
- `collected_health_synthesis`: 7.41 seconds
- `posture_artifact_build`: 114.07 seconds
- `capability_artifact_build`: 139.07 seconds
- `shared_artifact_persistence`: 14.00 seconds
- `analysis_and_artifact_build`: 505.26 seconds
- `report_rendering`: 83.04 seconds
- `workflow`: 715.26 seconds

Observed next hotspot:

- The next meaningful optimization target is no longer `node_capacity.yml`; it is the common workload/security analysis path where pod/workload loops still drive many repeated `set_fact` operations.
- Candidate files include `roles/analyze_common/tasks/workload/*.yml` and `roles/analyze_common/tasks/security/*.yml`, but those directly create findings, so each migration needs stricter before/after payload comparison for false positive and false negative protection.

## Phase 2 Slice 6

Change made:

- Moved common workload probe coverage finding generation from repeated Ansible `set_fact` loops in `roles/analyze_common/tasks/workload/probe_coverage.yml` into `scripts/build_workload_probe_findings.py`.
- The helper preserves the existing workload scan order and finding semantics for Deployments, StatefulSets, and DaemonSets.
- The helper preserves the existing namespace and operator-managed workload exclusions so platform/operator components are not reported as application workload hygiene findings.
- The role remains the owner of when workload probe analysis runs and only normalizes the helper output back into `workload_probe_findings`.

Validation:

- `python3 -m py_compile scripts/build_workload_probe_findings.py scripts/build_node_capacity_facts.py scripts/build_platform_component_facts.py scripts/build_node_baseline_facts.py scripts/write_json_artifact_map.py scripts/build_report_timing_artifact.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the saved pre-change payload with the new payload for every `workload_probe_findings` occurrence. Result: all matched exactly.
- Confirmed `report/payload.json`, output JSON, and workspace report JSON are byte-identical for the collected fixture.

Latest collected fixture timing after Slice 6:

- This run was materially slower than the prior clean baseline, so it should be treated as validation timing rather than a clean performance comparison.
- `evidence_loading`: 37.39 seconds
- `collected_preparation`: 2.70 seconds
- `common_analysis`: 45.57 seconds
- `openshift_analysis`: 137.11 seconds
- `collected_health_synthesis`: 6.80 seconds
- `posture_artifact_build`: 97.53 seconds
- `capability_artifact_build`: 115.28 seconds
- `shared_artifact_persistence`: 11.64 seconds
- `analysis_and_artifact_build`: 436.49 seconds
- `report_rendering`: 70.63 seconds
- `workflow`: 581.58 seconds

Observed next hotspot:

- The fixture still spends significant time in report-domain payload assembly and artifact fan-out after analysis completes.
- The run emitted a duplicate YAML key warning for `node_metadata_governance_findings` in `roles/report_common/tasks/build_openshift_domain_payload.yml`; this should be fixed separately because duplicate keys can hide report payload mistakes.
- The report assembly path also printed a very large merged shared artifact payload during the fixture run, which adds noise and can increase controller-side overhead on larger clusters.

## Follow-up Cleanup

Change made:

- Removed the duplicate `node_metadata_governance_findings` key from `roles/report_common/tasks/build_openshift_domain_payload.yml`.
- Added `scripts/load_openshift_shared_artifacts.py` so OpenShift shared artifacts are loaded directly with canonical keys:
  - `shared-collection` -> `collection`
  - `shared-analysis-graph` -> `analysis_graph`
  - other artifacts -> artifact key or file stem
- Replaced the looped shared-artifact merge in `roles/report_common/tasks/load_openshift_shared_artifacts.yml` with a single dictionary merge. This avoids printing the full shared artifact as an Ansible loop item and reduces controller-side loop overhead.

Validation:

- `python3 -m py_compile scripts/load_openshift_shared_artifacts.py scripts/load_json_artifact_dir.py scripts/build_workload_probe_findings.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Confirmed the duplicate YAML key warning no longer appears during `Build shared OpenShift domain payload`.
- Confirmed the large shared-artifact loop item dump no longer appears during `Merge OpenShift shared artifacts`.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.

Latest collected fixture timing after follow-up cleanup:

- This run was materially slower than the prior clean baseline, so it should be treated as validation timing rather than a clean performance comparison.
- `analysis_and_artifact_build`: 506.32 seconds
- `report_rendering`: 84.01 seconds
- `workflow`: 685.90 seconds

## Phase 2 Slice 7

Change made:

- Added `scripts/build_workload_health_domain_payload.py` to build the OpenShift `workload_health` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `workload_health` mappings in both collected and live domain payload branches with the precomputed `workload_health_domain_payload`.
- The helper does not create or reinterpret findings. It only preserves the existing precedence rules:
  - posture artifact values first
  - posture render inputs second
  - existing analysis facts as fallback
- Kept `roles/report_common/tasks/build_openshift_domain_payload.yml` as the owner of when the domain payload is assembled.

Validation:

- `python3 -m py_compile scripts/build_workload_health_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.workload_health` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 7:

- This run was materially slower than the prior clean baseline, so it should be treated as validation timing rather than a clean performance comparison.
- `common_analysis`: 49.73 seconds
- `openshift_analysis`: 127.81 seconds
- `posture_artifact_build`: 118.29 seconds
- `capability_artifact_build`: 114.11 seconds
- `analysis_and_artifact_build`: 453.95 seconds
- `report_rendering`: 87.12 seconds
- `workflow`: 679.68 seconds

Observed next hotspot:

- Domain payload assembly still has many large Jinja-backed sections. The next safe migration target is another contained domain with clear artifact/render-input precedence, such as `network_and_application_access` or `storage_and_resilience`.
- The common workload governance loops still print many per-item skip lines and remain a good future target, but that path creates findings and needs stricter false-positive and false-negative checks than domain payload assembly.

## Phase 2 Slice 8

Change made:

- Added `scripts/build_network_access_domain_payload.py` to build the OpenShift `network_and_application_access` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `network_and_application_access` mappings in both collected and live domain payload branches with the precomputed `network_access_domain_payload`.
- The helper preserves the existing precedence rules and does not create or reinterpret network findings:
  - posture artifact values first
  - posture render inputs second
  - existing analysis facts as fallback
- Kept `roles/report_common/tasks/build_openshift_domain_payload.yml` as the owner of when the domain payload is assembled.

Validation:

- `python3 -m py_compile scripts/build_network_access_domain_payload.py scripts/build_workload_health_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: rendered payload artifacts were produced successfully.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.network_and_application_access` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 8:

- `common_analysis`: 20.21 seconds
- `openshift_analysis`: 52.64 seconds
- `posture_artifact_build`: 69.18 seconds
- `capability_artifact_build`: 109.28 seconds
- `analysis_and_artifact_build`: 280.62 seconds
- `report_rendering`: 66.10 seconds
- `workflow`: 406.49 seconds

Observed next hotspot:

- Domain payload assembly still has contained Jinja-heavy sections that can be migrated safely when their source precedence is clear. The next candidate is `storage_and_resilience`.
- The common workload governance loops remain a future target, but they should be handled after the contained payload-only migrations because they participate in finding creation and need stricter accuracy checks.

## Phase 2 Slice 9

Change made:

- Added `scripts/build_storage_resilience_domain_payload.py` to build the OpenShift `storage_and_resilience` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `storage_and_resilience` mappings in both collected and live domain payload branches with the precomputed `storage_resilience_domain_payload`.
- The helper preserves the existing collected/live fallback difference:
  - collected runs use the full storage, backup, and machine remediation finding lists
  - live runs use the existing `top_*` limited finding lists
- The helper does not create or reinterpret findings.

Validation:

- `python3 -m py_compile scripts/build_storage_resilience_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.storage_and_resilience` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 9:

- `common_analysis`: 22.71 seconds
- `openshift_analysis`: 62.20 seconds
- `posture_artifact_build`: 61.19 seconds
- `capability_artifact_build`: 69.16 seconds
- `analysis_and_artifact_build`: 239.67 seconds
- `report_rendering`: 53.59 seconds
- `workflow`: 353.06 seconds

Observed next hotspot:

- The remaining domain payload assembly sections still include large Jinja maps, especially security/governance, platform health, and node health/capacity. Security/governance is larger and higher risk because it contains many subsections, so the next low-risk pass should target a smaller contained domain first.
- Common workload governance loops remain a strong future candidate, but should be optimized only with direct finding-level comparisons because they influence report findings rather than only moving payload mapping.

## Phase 2 Slice 10

Change made:

- Added `scripts/build_observability_domain_payload.py` to build the OpenShift `observability` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `observability` mappings in both collected and live domain payload branches with the precomputed `observability_domain_payload`.
- The helper preserves the existing collected/live fallback differences:
  - collected runs use full observability findings, connected-cluster posture/findings, and collected advisor defaults
  - live runs use the existing top observability/advisor findings and live advisor summary defaults
- The helper does not create or reinterpret findings.

Validation:

- `python3 -m py_compile scripts/build_observability_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.observability` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 10:

- `common_analysis`: 20.17 seconds
- `openshift_analysis`: 86.31 seconds
- `posture_artifact_build`: 121.05 seconds
- `capability_artifact_build`: 106.13 seconds
- `analysis_and_artifact_build`: 369.51 seconds
- `report_rendering`: 73.42 seconds
- `workflow`: 501.04 seconds

Observed next hotspot:

- Continue with small contained domain payloads before optimizing finding-generation loops. `node_health_and_capacity` is a reasonable next target because it is still duplicated in collected/live payload assembly and has clear fallback differences.
- Defer `security_and_governance` until later because it is larger and has more subsection-level risk.

## Phase 2 Slice 11

Change made:

- Added `scripts/build_node_health_domain_payload.py` to build the OpenShift `node_health_and_capacity` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `node_health_and_capacity` mappings in both collected and live domain payload branches with the precomputed `node_health_domain_payload`.
- The helper preserves the existing collected/live fallback differences:
  - collected runs use `node_diagnostics_findings` and `assessment_mcp_summary`
  - live runs use live inspect/sosreport top findings and `cluster_current_state.machineconfigpools`
- The helper does not create or reinterpret findings.

Validation:

- `python3 -m py_compile scripts/build_node_health_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.node_health_and_capacity` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 11:

- `common_analysis`: 20.06 seconds
- `openshift_analysis`: 55.03 seconds
- `posture_artifact_build`: 47.51 seconds
- `capability_artifact_build`: 51.43 seconds
- `analysis_and_artifact_build`: 192.79 seconds
- `report_rendering`: 35.06 seconds
- `workflow`: 275.59 seconds

Observed next hotspot:

- Continue with contained domain payloads if minimizing report assembly risk remains the priority. `platform_health` is a reasonable next target but has more fields and support-tool fallbacks than node health.
- After the remaining low-risk payload moves, shift to finding-generation loops with direct finding-level before/after comparisons.

## Phase 2 Slice 12

Change made:

- Added `scripts/build_platform_health_domain_payload.py` to build the OpenShift `platform_health` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `platform_health` mappings in both collected and live domain payload branches with the precomputed `platform_health_domain_payload`.
- The helper preserves the existing collected/live fallback differences:
  - collected runs use assessment health/operator defaults, full OMC/APIService/image registry facts, and collected-only control-plane readyz fields
  - live runs use live top findings where the existing payload did so and do not add collected-only control-plane readyz keys
- The helper does not create or reinterpret findings.

Validation:

- `python3 -m py_compile scripts/build_platform_health_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.platform_health` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 12:

- `common_analysis`: 20.00 seconds
- `openshift_analysis`: 52.17 seconds
- `posture_artifact_build`: 47.59 seconds
- `capability_artifact_build`: 52.00 seconds
- `analysis_and_artifact_build`: 190.10 seconds
- `report_rendering`: 37.22 seconds
- `workflow`: 275.57 seconds

Observed next hotspot:

- The remaining large inline payload section is `security_and_governance`. It can be moved, but it is wider and should be split into subsection helpers or validated carefully with direct domain comparison.
- If the goal shifts from report assembly cleanup to runtime reduction, the next higher-impact area is finding-generation loops with direct finding-level before/after comparisons.

## Phase 2 Slice 13

Change made:

- Added `scripts/build_security_governance_domain_payload.py` to build the OpenShift `security_and_governance` domain payload from existing artifacts, render inputs, and fallback facts.
- Replaced the inline `security_and_governance` mappings in both collected and live domain payload branches with the precomputed `security_governance_domain_payload`.
- The helper preserves the existing collected/live fallback differences:
  - collected runs include `node_metadata_governance_findings` in namespace hygiene
  - collected runs use full compliance and access-review findings where the previous payload did so
  - live runs use the existing top compliance and access-review findings
- The helper does not create or reinterpret findings.

Validation:

- `python3 -m py_compile scripts/build_security_governance_domain_payload.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared `domains.security_and_governance` directly between the pre-change and post-change payloads. Result: exact match.

Latest collected fixture timing after Slice 13:

- `common_analysis`: 20.65 seconds
- `openshift_analysis`: 119.19 seconds
- `posture_artifact_build`: 102.25 seconds
- `capability_artifact_build`: 113.27 seconds
- `analysis_and_artifact_build`: 394.13 seconds
- `report_rendering`: 87.81 seconds
- `workflow`: 543.18 seconds

Observed next hotspot:

- The main report-domain payload cleanup pass is complete for the largest duplicated posture domains.
- Next performance work should shift from payload mapping to finding-generation and analysis loops. Those changes need stricter guardrails: compare the specific generated finding lists before and after, not just the final domain payload.

## Phase 3 Slice 1

Change made:

- Added `scripts/build_route_ingress_findings.py` to build OpenShift route admission findings, ingress findings, route host-owner maps, ingress host-owner maps, and route/ingress host-conflict findings in one helper pass.
- Replaced the multi-loop Ansible implementation in `roles/analyze_openshift/tasks/workload.yml` with one helper call and a fact-expansion step.
- The helper preserves the existing finding shapes:
  - route issues: `route-not-admitted`, `route-missing-service`
  - ingress issues: `ingress-no-rules-or-default-backend`, `ingress-missing-service`, `ingress-without-class`
  - host conflicts: `duplicate-route-host`, `duplicate-ingress-host`, `duplicate-route-ingress-host`
- The helper only calculates existing route and ingress facts; it does not reinterpret report severity or section rendering.

Validation:

- `python3 -m py_compile scripts/build_route_ingress_findings.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Synthetic helper check with non-empty route, ingress, duplicate route-host, and cross route/ingress host-conflict findings.
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared the direct generated route/ingress finding lists in `domains.network_and_application_access`:
  - `route_issues`: exact match
  - `ingress_issues`: exact match
  - `route_host_conflicts`: exact match
  - `ingress_host_conflicts`: exact match
  - `route_ingress_host_conflicts`: exact match
- Compared `domains.network_and_application_access` directly. Result: exact match.

Latest collected fixture timing after Phase 3 Slice 1:

- `common_analysis`: 78.19 seconds
- `openshift_analysis`: 351.75 seconds
- `posture_artifact_build`: 428.36 seconds
- `capability_artifact_build`: 460.27 seconds
- `analysis_and_artifact_build`: 1460.86 seconds
- `report_rendering`: 408.25 seconds
- `workflow`: 2113.77 seconds

Timing note:

- This fixture run was significantly slower than the previous baseline across unrelated stages, so the timing is not a clean performance comparison for this slice.
- The validation value of this run is contract correctness: full fixture success, rendered report validation, direct finding-list equality, direct network-domain equality, and final payload equality.

Observed next hotspot:

- Continue with analysis loops that still print per-item Ansible output and build aggregate maps through repeated `set_fact`, especially:
  - `roles/analyze_common/tasks/security/deprecation_endpoints_and_ip_capacity.yml`
  - `roles/analyze_common/tasks/security/storage_and_tls.yml`
  - `roles/analyze_openshift/tasks/summary/aggregate_and_counts.yml`
- Use the same guardrail: direct finding-list/count-map comparison plus final payload comparison.

## Phase 3 Slice 2

Change made:

- Added `scripts/build_deprecation_endpoint_findings.py` to build deprecated CRD findings, service endpoint address counts, and Services-without-ready-endpoints findings in one helper pass.
- Replaced the repeated `set_fact` loops in `roles/analyze_common/tasks/security/deprecation_endpoints_and_ip_capacity.yml` with one helper call and a fact-expansion step.
- Kept deprecated API resource parsing and IP-capacity analysis unchanged.
- This role is shared by OpenShift and generic Kubernetes paths, so both playbook syntax checks are required for this slice.

Accuracy note:

- The before/after comparison found one intentional behavior correction in the CI fixture: `app-team-a/web` is a Service with a selector and a matching Endpoints object whose `subsets` list is empty.
- The previous Ansible loop missed that as a service endpoint gap. The helper reports it as `services_without_endpoints`, which is the more accurate result and avoids a false negative.
- The resulting report drift is limited to that corrected service-endpoint finding and the downstream network-access status, reason, and recommendation text derived from it.

Validation:

- `python3 -m py_compile scripts/build_deprecation_endpoint_findings.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- Synthetic helper check with one deprecated CRD, one Service with ready endpoints, and one selected Service with no endpoint addresses.
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: payloads differ only because of the corrected `services_without_endpoints` finding and its downstream status/recommendation fields.
- Compared route and ingress finding lists directly. Result: exact match; this slice did not change route or ingress behavior.

Latest collected fixture timing after Phase 3 Slice 2:

- `common_analysis`: 97.75 seconds
- `openshift_analysis`: 380.66 seconds
- `posture_artifact_build`: 212.98 seconds
- `capability_artifact_build`: 206.41 seconds
- `analysis_and_artifact_build`: 974.26 seconds
- `report_rendering`: 146.45 seconds
- `workflow`: 1593.06 seconds

Timing note:

- This run remains noisy and should not be treated as a clean benchmark. The important validation result for this slice is correctness: full fixture success, rendered report validation, and an explainable payload delta that removes a false negative.

Observed next hotspot:

- Continue with remaining high-output analysis loops, especially:
  - `roles/analyze_common/tasks/security/storage_and_tls.yml`
  - `roles/analyze_openshift/tasks/summary/aggregate_and_counts.yml`
  - `roles/analyze_common/tasks/security/hygiene_and_pod_security.yml`
  - `roles/analyze_common/tasks/workload/governance.yml`
- Keep the guardrail strict: compare the direct generated findings or count maps first, then compare the final payload and explain any intentional accuracy corrections.

## Phase 3 Slice 3

Change made:

- Added `scripts/build_storage_tls_facts.py` to build StorageClass summaries, PV/PVC phase counts, PV/PVC issue lists, TLS secret expiry targets, and certificate-expiry findings.
- Replaced repeated `set_fact` loops in `roles/analyze_common/tasks/security/storage_and_tls.yml` with helper calls and fact-expansion steps.
- Kept the existing storage posture helper, TLS OpenSSL batch helper, and report rendering logic unchanged.
- This role is shared by OpenShift and generic Kubernetes paths, so both playbook syntax checks were run.

Validation:

- `python3 -m py_compile scripts/build_storage_tls_facts.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/k8s_cluster_health_report.yml`
- Synthetic helper check with:
  - one default StorageClass
  - one Bound PV
  - one Failed PV with a claim reference
  - one Pending PVC
  - one TLS Secret target
  - one certificate-expiry result
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the pre-change and post-change report payloads after normalizing expected volatile run metadata. Result: normalized payloads matched.
- Compared the storage-sensitive rendered domains directly:
  - `domains.storage_resilience`: exact match
  - `domains.backup_and_disaster_recovery`: exact match
  - `domains.platform_architecture_and_lifecycle`: exact match
  - `domains.observability`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 3:

- `common_analysis`: 23.00 seconds
- `openshift_analysis`: 53.20 seconds
- `posture_artifact_build`: 47.68 seconds
- `capability_artifact_build`: 52.81 seconds
- `analysis_and_artifact_build`: 195.51 seconds
- `report_rendering`: 45.53 seconds
- `workflow`: 291.18 seconds

Timing note:

- This fixture run was much faster than the previous noisy run, but it still should not be treated as a clean isolated benchmark. The correctness guardrail is stronger than the timing signal for this slice.

Observed next hotspot:

- `roles/analyze_openshift/tasks/summary/aggregate_and_counts.yml` is now the best next slice. It mostly computes top-N lists and issue-type count maps from already-built facts, so it should be possible to move that aggregation into one helper with exact payload comparison.
- `roles/analyze_common/tasks/security/hygiene_and_pod_security.yml` remains a larger follow-up because it combines namespace hygiene, CPU request maps, security findings, and workload-practice findings.

## Phase 3 Slice 4

Change made:

- Added `scripts/build_openshift_aggregate_facts.py` to build OpenShift top-N aggregate lists and issue-type count maps from already-computed facts.
- Replaced the large aggregate `set_fact` block and three repeated issue-count loops in `roles/analyze_openshift/tasks/summary/aggregate_and_counts.yml` with one helper call and a fact-expansion step.
- The helper does not create new findings. It only sorts, slices, filters, deduplicates, and counts existing facts.
- This slice is OpenShift-specific.

Validation:

- `python3 -m py_compile scripts/build_openshift_aggregate_facts.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Synthetic helper check with restart sorting, default StorageClass selection, event count sorting, issue-type counts, filtered workload-practice scoring, privileged access sorting, and stale-user deduplication.
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared aggregate-sensitive rendered domains directly:
  - `domains.platform_health`: exact match
  - `domains.node_health_and_capacity`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.observability`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.workload_health`: exact match
  - `domains.storage_resilience`: exact match
  - `domains.upgrade_and_lifecycle_risk`: exact match
  - `health_summary`: exact match

Residual validation note:

- Full normalized payload comparison did not match because `domains.capacity_planning_snapshot.cluster_current_state.ip_capacity` differed between the saved baseline and this run.
- The changed fields were service and pod CIDR range derivation plus the derived capacity sanity findings.
- This drift is outside the aggregate helper's input/output contract. The aggregate helper does not read or write `service_ip_capacity_summary`, `pod_ip_capacity_summary`, `node_ip_capacity_summary`, `cluster_profile`, or network configuration facts.
- Treat this as a separate follow-up before claiming full payload equivalence for this slice.

Latest collected fixture timing after Phase 3 Slice 4:

- `common_analysis`: 122.99 seconds
- `openshift_analysis`: 288.84 seconds
- `posture_artifact_build`: 174.74 seconds
- `capability_artifact_build`: 177.22 seconds
- `analysis_and_artifact_build`: 835.89 seconds
- `report_rendering`: 118.16 seconds
- `workflow`: 1153.40 seconds

Timing note:

- This run was slow across unrelated stages, so it is not a clean benchmark.

Observed next hotspot:

- Before starting the next performance slice, investigate why `capacity_planning_snapshot` can lose service and pod CIDR range data even when the report-level cluster profile still contains `service_networks` and `cluster_networks`.
- After that is resolved, the next performance target remains `roles/analyze_common/tasks/security/hygiene_and_pod_security.yml`.

## Phase 3 Slice 4 Follow-up

Change made:

- Hardened `roles/posture_capacity_planning_snapshot/tasks/analysis.yml` so the capacity planning posture can rebuild service, pod, and node IP capacity summaries locally when upstream summary facts arrive incomplete.
- The fallback uses the existing `scripts/build_ip_capacity_summary.py` helper and the already-loaded cluster profile, network config, machinesets, services, pods, and nodes.
- This is an accuracy hardening change, not a performance optimization.

Validation:

- `python3 -m py_compile scripts/build_ip_capacity_summary.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/posture_capacity_planning_snapshot/tasks/analysis.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Confirmed `domains.capacity_planning_snapshot` now matches the baseline exactly.
- Confirmed capacity IP ranges were preserved:
  - service range: `172.30.0.0/16`
  - pod range: `10.128.0.0/14`
  - sanity findings: none

Latest collected fixture timing after Phase 3 Slice 4 follow-up:

- `evidence_loading`: 94.14 seconds
- `common_analysis`: 80.12 seconds
- `openshift_analysis`: 220.23 seconds
- `posture_artifact_build`: 166.74 seconds
- `capability_artifact_build`: 217.10 seconds
- `analysis_and_artifact_build`: 756.32 seconds
- `report_rendering`: 216.67 seconds
- `workflow`: 1151.82 seconds

Observed next hotspot:

- Continue with `roles/analyze_common/tasks/security/hygiene_and_pod_security.yml`.
- The next slice should keep the same guardrail: exact normalized payload comparison against the saved baseline, with special attention to security findings, workload-practice findings, namespace hygiene, and Pod Security content.

## Phase 3 Slice 5

Change made:

- Added `scripts/build_security_hygiene_facts.py` to compute namespace policy/quota/limitrange counts, namespace hygiene lists, and basic pod security/workload practice findings outside Ansible loops.
- Replaced the loop-heavy portions of `roles/analyze_common/tasks/security/hygiene_and_pod_security.yml` with one helper call plus fact expansion.
- Left the existing specialized helpers in place for CPU request maps, pod hardening findings, and storage/sensitive-string findings.
- The helper preserves the previous finding shapes and ordering. It does not introduce new issue types or broaden namespace scope.

Validation:

- `python3 -m py_compile scripts/build_security_hygiene_facts.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_security_hygiene_facts.py roles/analyze_common/tasks/security/hygiene_and_pod_security.yml`
- Synthetic helper check for:
  - network policy count and ingress/egress policy classification
  - resource quota and limit range counts
  - namespace hygiene lists
  - platform namespace exclusion
  - privileged container, hostNetwork, hostPath, run-as-root findings
  - missing resource request and limit findings
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared security-sensitive rendered domains directly:
  - `domains.security_and_governance`: exact match
  - `domains.workload_health`: exact match
  - `domains.network_and_application_access`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 5:

- `evidence_loading`: 91.42 seconds
- `common_analysis`: 74.60 seconds
- `openshift_analysis`: 175.67 seconds
- `posture_artifact_build`: 265.61 seconds
- `capability_artifact_build`: 275.29 seconds
- `analysis_and_artifact_build`: 863.70 seconds
- `report_rendering`: 121.19 seconds
- `workflow`: 1145.03 seconds

Timing note:

- `common_analysis` improved modestly compared with the prior fixture run (`80.12s` to `74.60s`), but this remains a noisy end-to-end benchmark. Correctness remains the primary guardrail.

Observed next hotspot:

- Continue reducing high-cardinality Ansible loops in common analysis. The next practical target is the remaining loop-heavy security/storage/TLS or unused-resource analysis paths, with the same exact payload comparison guardrail.

## Phase 3 Slice 6

Change made:

- Added `scripts/build_crd_usage_facts.py` to build namespaced CRD count targets and likely-unused CRD findings outside Ansible loops.
- Updated `roles/analyze_common/tasks/security/references_rbac_and_crd_usage.yml` to use the helper before and after the existing `batch_crd_instance_counts.py` collection step.
- Kept the live CRD instance count batching behavior unchanged. This slice only replaces Ansible-side target filtering and result shaping.

Validation:

- `python3 -m py_compile scripts/build_crd_usage_facts.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_crd_usage_facts.py roles/analyze_common/tasks/security/references_rbac_and_crd_usage.yml`
- Synthetic helper check for:
  - namespaced CRD target selection
  - cluster-scoped CRD exclusion
  - missing CRD field handling
  - zero-count non-platform CRD findings
  - platform CRD group exclusion
  - nonzero and failed count-result exclusion
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared CRD/security-adjacent rendered domains directly:
  - `domains.security_and_governance`: exact match
  - `domains.workload_health`: exact match
  - `domains.storage_resilience`: exact match
  - `domains.platform_architecture_and_lifecycle`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 6:

- `evidence_loading`: 100.14 seconds
- `common_analysis`: 89.10 seconds
- `openshift_analysis`: 185.81 seconds
- `posture_artifact_build`: 151.66 seconds
- `capability_artifact_build`: 165.45 seconds
- `analysis_and_artifact_build`: 652.16 seconds
- `report_rendering`: 121.12 seconds
- `workflow`: 944.79 seconds

Timing note:

- This slice reduces controller-side loop overhead, but the fixture timing is noisy. The full workflow improved in this run mostly because artifact-build stages were faster; do not attribute the full workflow delta to the CRD helper.

Observed next hotspot:

- Continue with common workload analysis. `roles/analyze_common/tasks/workload.yml` still has Ansible loops for namespace classification, workload replica summaries, and subscription missing-starting-CSV findings.

## Phase 3 Slice 7

Change made:

- Added `scripts/build_operator_managed_namespaces.py` to detect operator-managed namespaces outside high-cardinality Ansible loops.
- Updated `roles/analyze_common/tasks/workload.yml` to call the helper once and normalize `operator_managed_namespace_names` from the helper output.
- Preserved the existing detection order and scope:
  - namespace metadata markers
  - deployment, statefulset, daemonset, and deploymentconfig workload markers
  - subscription namespaces

Validation:

- `python3 -m py_compile scripts/build_operator_managed_namespaces.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_operator_managed_namespaces.py roles/analyze_common/tasks/workload.yml`
- Synthetic helper check for:
  - operator namespace name and suffix detection
  - OLM/operator label and annotation markers
  - managed-by operator values
  - controller-manager and operator workload names
  - ClusterServiceVersion owner references
  - subscription namespace inclusion
  - duplicate namespace de-duplication while preserving first-seen order
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared rendered domains directly:
  - `domains.workload_health`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 7:

- `evidence_loading`: 89.16 seconds
- `common_analysis`: 104.31 seconds
- `openshift_analysis`: 177.60 seconds
- `posture_artifact_build`: 189.48 seconds
- `capability_artifact_build`: 106.04 seconds
- `analysis_and_artifact_build`: 632.99 seconds
- `report_rendering`: 85.10 seconds
- `workflow`: 865.08 seconds

Timing note:

- The fixture remains noisy, so this slice should be treated as controller-side loop reduction with correctness preserved, not as a standalone end-to-end timing claim.

Observed next hotspot:

- Continue in workload health with `roles/analyze_common/tasks/workload/governance.yml`, especially orphan pod review and workload label/resource requirement loops. This should follow the same pattern: helper-owned shaping, exact fixture payload comparison, and no report-contract drift.

## Phase 3 Slice 8

Change made:

- Added `scripts/build_workload_governance_facts.py` to build workload governance findings outside high-cardinality Ansible loops.
- Updated `roles/analyze_common/tasks/workload/governance.yml` to call the helper once and apply the returned facts:
  - `orphan_pods`
  - `workload_label_governance_findings`
  - `workload_resource_findings`
- Left node label governance on the existing helper path.
- Kept the helper task fail-closed so a helper failure does not silently suppress workload-governance findings.

Validation:

- `python3 -m py_compile scripts/build_workload_governance_facts.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_workload_governance_facts.py roles/analyze_common/tasks/workload/governance.yml`
- Synthetic helper check for:
  - orphan pod inclusion and exclusion
  - ownerReference exclusion
  - platform namespace exclusion
  - operator namespace exclusion
  - CI runner noise exclusion
  - operator/controller workload exclusion
  - workload label governance recommendations
  - workload resource request and limit findings
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared rendered domains directly:
  - `domains.workload_health`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 8:

- `evidence_loading`: 82.03 seconds
- `common_analysis`: 64.34 seconds
- `openshift_analysis`: 130.16 seconds
- `posture_artifact_build`: 102.59 seconds
- `capability_artifact_build`: 285.87 seconds
- `analysis_and_artifact_build`: 687.77 seconds
- `report_rendering`: 108.92 seconds
- `workflow`: 950.28 seconds

Timing note:

- `common_analysis` improved materially in this fixture run compared with Slice 7 (`104.31s` to `64.34s`). The fixture remains noisy, but this is the expected direction for removing three high-cardinality Jinja loops.

Observed next hotspot:

- Continue reducing loop-heavy OpenShift analysis paths. The next likely target is the OpenShift-specific workload analysis in `roles/analyze_openshift/tasks/workload.yml`, especially remaining per-item loops that build workload or release-engineering summaries.

## Phase 3 Slice 9

Change made:

- Added `scripts/build_deploymentconfig_resource_findings.py` to build OpenShift `DeploymentConfig` resource request and limit findings outside an Ansible loop.
- Updated `roles/analyze_openshift/tasks/workload.yml` to call the helper and append its returned findings to `workload_resource_findings`.
- Preserved the existing OpenShift-specific behavior:
  - user namespace filtering only
  - no operator-managed workload filtering
  - same `DeploymentConfig` finding shape
  - same request-before-limit ordering per workload
- Kept the helper task fail-closed so a helper failure cannot silently suppress `DeploymentConfig` findings.

Validation:

- `python3 -m py_compile scripts/build_deploymentconfig_resource_findings.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_deploymentconfig_resource_findings.py roles/analyze_openshift/tasks/workload.yml`
- Synthetic helper check for:
  - user namespace inclusion
  - platform namespace exclusion
  - empty container list exclusion
  - complete resource request and limit exclusion
  - missing request and missing limit finding order
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared rendered domains directly:
  - `domains.workload_health`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 9:

- `evidence_loading`: 63.63 seconds
- `common_analysis`: 84.73 seconds
- `openshift_analysis`: 172.76 seconds
- `posture_artifact_build`: 144.63 seconds
- `capability_artifact_build`: 209.55 seconds
- `analysis_and_artifact_build`: 681.34 seconds
- `report_rendering`: 117.99 seconds
- `workflow`: 915.69 seconds

Timing note:

- This was a small cleanup slice. It removes one OpenShift-specific loop and preserves correctness; the end-to-end timing remains dominated by larger analysis, artifact, and rendering stages.

Observed next hotspot:

- Continue with `roles/analyze_openshift/tasks/workload.yml` helper calls that still fail open. Converting critical helper calls to fail closed is not a speed gain, but it protects report accuracy while continuing the performance refactor.

## Phase 3 Slice 10

Change made:

- Hardened report-critical helper calls in `roles/analyze_openshift/tasks/workload.yml` to fail closed instead of silently suppressing findings:
  - `build_workload_health_findings.py`
  - `build_workload_label_governance_findings.py`
  - `build_route_ingress_findings.py`
- Simplified normalization for those helpers to parse helper JSON directly after the command succeeds.
- Left optional/availability-style helper fallback behavior outside this file unchanged.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/analyze_openshift/tasks/workload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared rendered domains directly:
  - `domains.workload_health`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 10:

- `evidence_loading`: 56.95 seconds
- `common_analysis`: 96.60 seconds
- `openshift_analysis`: 235.79 seconds
- `posture_artifact_build`: 138.64 seconds
- `capability_artifact_build`: 155.82 seconds
- `analysis_and_artifact_build`: 685.27 seconds
- `report_rendering`: 133.13 seconds
- `workflow`: 925.66 seconds

Timing note:

- This was an accuracy hardening slice, not a performance slice. The timing variance is expected and should not be interpreted as a speed regression caused by the fail-closed changes.

Observed next hotspot:

- Move back to performance work in OpenShift analysis. The next practical target is loop-heavy observability setup/offline analysis, where several helper-backed summaries still perform expensive collected-state parsing and should be reviewed for consolidation without changing missing-signal semantics.

## Phase 3 Slice 11

Change made:

- Added `scripts/build_observability_metric_summaries.py` to build observability metric summaries outside repeated Ansible loops.
- Updated `roles/analyze_openshift/tasks/observability/findings.yml` to call the helper and apply the returned facts.
- Preserved the existing metric semantics:
  - alert counters default missing severity/name to `unknown`
  - alert namespace defaults to `cluster`
  - CPU, memory, and disk summaries remain gated on observed runtime signal status
  - pod-density summaries remain threshold-based and are not gated by signal status
  - node metric values remain rounded to one decimal place
- Parsed the helper result once before applying facts to avoid repeated `from_json` work in Ansible.

Validation:

- `python3 -m py_compile scripts/build_observability_metric_summaries.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_observability_metric_summaries.py roles/analyze_openshift/tasks/observability/findings.yml`
- Synthetic helper check for:
  - alert severity/name/namespace counters
  - observed CPU and memory low/high thresholds
  - not-collected disk suppression
  - high and critical pod-density thresholds
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared rendered domains directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match

Latest collected fixture timing after Phase 3 Slice 11:

- `evidence_loading`: 80.17 seconds
- `common_analysis`: 87.73 seconds
- `openshift_analysis`: 213.21 seconds
- `posture_artifact_build`: 149.92 seconds
- `capability_artifact_build`: 154.05 seconds
- `analysis_and_artifact_build`: 665.78 seconds
- `report_rendering`: 121.40 seconds
- `workflow`: 933.67 seconds

Timing note:

- The helper refactor is correct and removes several per-item Ansible loops from observability metric summarization, but this slice is not expected to dominate fixture runtime. Current timing remains dominated by OpenShift analysis, posture/capability artifact assembly, and report rendering.
- The task-progress counter reached `1748` known tasks because dynamic includes are added during execution. The percentage did finish correctly at `100%`, but the mid-run percentage still under-represents actual completion while new tasks are being discovered.

Observed next hotspot:

- Consolidate loop-heavy observability setup/offline and forwarding summaries next. Specific candidates seen during the fixture are `Build warning event summaries`, `Normalize warning event timestamps`, `Detect vendor-managed telemetry evidence`, `Build log forwarding findings`, `Build metrics forwarding findings`, and `Build external alert delivery findings`.

## Phase 3 Slices 12-14

Batching note:

- These slices were intentionally batched before the runtime fixture to improve tuning velocity. Static and synthetic checks were run first; one collected-state fixture was run after the batch.

Slice 12 change:

- Added `scripts/build_warning_event_summaries.py`.
- Replaced the warning-event reason-count loop in `roles/analyze_openshift/tasks/observability/setup_and_offline.yml`.
- Removed the later warning-event timestamp normalization and sort loops from `roles/analyze_openshift/tasks/observability/prometheus_collection.yml`.
- The helper now builds `warning_event_reason_counts`, `warning_event_items`, and `recent_warning_events` in one pass while preserving timestamp precedence:
  - `lastTimestamp`
  - `eventTime`
  - `metadata.creationTimestamp`

Slice 13 change:

- Split Prometheus helper normalization in `roles/analyze_openshift/tasks/observability/prometheus_collection.yml` so the helper JSON is parsed once, then projected into `prom_available`, `prom_result_map`, `prom_query_error_map`, `prom_query_status_map`, and `prom_collection_transport`.

Slice 14 change:

- Added `scripts/build_observability_forwarding_bundle.py`.
- Updated the existing forwarding helper scripts to expose reusable `build(data)` functions while preserving their command-line output behavior:
  - `scripts/build_vendor_managed_telemetry.py`
  - `scripts/build_log_forwarding_findings.py`
  - `scripts/build_metrics_forwarding_findings.py`
  - `scripts/build_external_alert_delivery_findings.py`
- Replaced four separate forwarding helper command invocations in `roles/analyze_openshift/tasks/observability/forwarding.yml` with one bundled helper call plus one apply step.
- Preserved the previous fallback behavior for the forwarding bundle: helper failure still falls back to empty/default observability forwarding facts rather than failing the report.

Validation:

- `python3 -m py_compile scripts/build_warning_event_summaries.py scripts/build_observability_forwarding_bundle.py scripts/build_vendor_managed_telemetry.py scripts/build_log_forwarding_findings.py scripts/build_metrics_forwarding_findings.py scripts/build_external_alert_delivery_findings.py scripts/run_json_helper_from_stdin.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_warning_event_summaries.py scripts/build_observability_forwarding_bundle.py scripts/build_vendor_managed_telemetry.py scripts/build_log_forwarding_findings.py scripts/build_metrics_forwarding_findings.py scripts/build_external_alert_delivery_findings.py roles/analyze_openshift/tasks/observability/setup_and_offline.yml roles/analyze_openshift/tasks/observability/prometheus_collection.yml roles/analyze_openshift/tasks/observability/forwarding.yml`
- Synthetic helper check for:
  - warning-event reason counters
  - warning-event timestamp sort precedence
  - recent warning-event limit
  - vendor telemetry detection
  - log forwarding pipeline and external pipeline counts
  - metrics remote-write external counts
  - external alert receiver and routing detection
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared rendered domains and key observability facts directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match
  - `recent_warning_events`: exact match
  - `warning_event_reason_counts`: exact match

Latest collected fixture timing after Phase 3 Slices 12-14:

- `evidence_loading`: 86.59 seconds
- `common_analysis`: 72.18 seconds
- `openshift_analysis`: 124.60 seconds
- `posture_artifact_build`: 159.44 seconds
- `capability_artifact_build`: 109.33 seconds
- `analysis_and_artifact_build`: 515.00 seconds
- `report_rendering`: 92.80 seconds
- `workflow`: 757.19 seconds

Timing note:

- This batch removed several Ansible loop tasks and three extra Python helper process launches from the observability path. Fixture timing improved from the previous `workflow=933.67s` to `workflow=757.19s`; treat the exact delta as directional because local fixture timing is noisy.
- Dynamic task count dropped from `1748` to `1740` in this fixture, reflecting removed observability tasks.

Observed next hotspot:

- Continue batching small adjacent slices before the next fixture. The next practical targets are remaining OpenShift analysis and artifact-builder hotspots visible in timing: `openshift_analysis`, `posture_artifact_build`, `capability_artifact_build`, and `report_rendering`.

## Phase 3 Slices 15-17

Batching note:

- These slices were intentionally batched before the runtime fixture to improve tuning velocity while keeping the change inside artifact persistence and report-contract plumbing.

Slice 15 change:

- Collapsed capability section lookup into the capability artifact payload build path in `roles/report_common/tasks/persist_openshift_capability_artifact.yml`.
- Added use of the precomputed `day2_capability_sections_by_key` map while preserving the existing ordered-list fallback and explicit override behavior.
- This removes the separate per-capability `Resolve requested OpenShift capability section` task.

Slice 16 change:

- Buffered posture artifact payloads and flushed them through `scripts/write_json_artifact_map.py`.
- Combined posture flush bookkeeping and buffer clearing into one task in `roles/report_common/tasks/flush_openshift_posture_artifacts.yml`.
- Kept a skipped-flush fallback clear so empty buffers do not leak between runs.

Slice 17 change:

- Buffered capability artifact payloads and flushed them through `scripts/write_json_artifact_map.py`.
- Combined capability flush bookkeeping and buffer clearing into one task in `roles/report_common/tasks/flush_openshift_capability_artifacts.yml`.
- Preserved the individual JSON artifact file contract under `.run-state/openshift/<mode>-artifacts/capabilities/`.

Validation:

- `python3 -m py_compile scripts/write_json_artifact_map.py scripts/write_stdin_to_file.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- playbooks/openshift_cluster_health_report.yml roles/report_common/tasks/persist_openshift_posture_artifact.yml roles/report_common/tasks/persist_openshift_capability_artifact.yml roles/report_common/tasks/flush_openshift_posture_artifacts.yml roles/report_common/tasks/flush_openshift_capability_artifacts.yml scripts/write_json_artifact_map.py group_vars/all.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 15-17:

- `evidence_loading`: 95.85 seconds
- `common_analysis`: 73.02 seconds
- `openshift_analysis`: 162.69 seconds
- `posture_artifact_build`: 99.58 seconds
- `capability_artifact_build`: 105.18 seconds
- `analysis_and_artifact_build`: 488.01 seconds
- `report_rendering`: 91.69 seconds
- `workflow`: 733.07 seconds

Timing note:

- Posture artifact build improved from `159.44s` to `99.58s`.
- Capability artifact build moved from `109.33s` to `105.18s`; the remaining cost is now mostly per-capability role/include overhead rather than file writes.
- Overall workflow timing improved from `757.19s` to `733.07s`; treat exact deltas as directional because local fixture timing is noisy.
- Dynamic task count dropped from `1740` to `1715`.

Observed next hotspot:

- The next practical batch should target remaining per-artifact role overhead and report rendering. The fixture still shows repeated skipped immediate-write/record tasks under buffered artifact mode, plus expensive payload/render steps after artifact build.

## Phase 3 Slices 18-19

Batching note:

- These slices were batched before the runtime fixture to keep tuning velocity up. The batch focused on artifact/report plumbing only; it did not change report findings, section content, or profile-gated rendering.

Slice 18 change:

- Split posture and capability artifact persistence into mode-specific task files:
  - `roles/report_common/tasks/persist_openshift_posture_artifact_buffered.yml`
  - `roles/report_common/tasks/persist_openshift_posture_artifact_immediate.yml`
  - `roles/report_common/tasks/persist_openshift_capability_artifact_buffered.yml`
  - `roles/report_common/tasks/persist_openshift_capability_artifact_immediate.yml`
- The public task entry points remain:
  - `roles/report_common/tasks/persist_openshift_posture_artifact.yml`
  - `roles/report_common/tasks/persist_openshift_capability_artifact.yml`
- Buffered mode now dispatches directly to the buffered path and no longer walks the immediate-write and immediate-record tasks for every artifact.
- The individual posture and capability JSON artifact contract is preserved.

Slice 19 change:

- Added `scripts/write_stdin_to_files.py`.
- Replaced duplicate final JSON report writes/copies with one helper invocation that writes the same serialized payload to:
  - workspace `report/payload.json`
  - final output JSON path
  - workspace report JSON path
- Applied this to both:
  - `roles/report_common/tasks/render_report_artifacts.yml`
  - `roles/report_openshift/tasks/render_collected_state_report.yml`

Validation:

- `python3 -m py_compile scripts/write_stdin_to_files.py scripts/write_json_artifact_map.py scripts/write_stdin_to_file.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/report_common/tasks/persist_openshift_posture_artifact.yml roles/report_common/tasks/persist_openshift_posture_artifact_buffered.yml roles/report_common/tasks/persist_openshift_posture_artifact_immediate.yml roles/report_common/tasks/persist_openshift_capability_artifact.yml roles/report_common/tasks/persist_openshift_capability_artifact_buffered.yml roles/report_common/tasks/persist_openshift_capability_artifact_immediate.yml roles/report_common/tasks/render_report_artifacts.yml roles/report_openshift/tasks/render_collected_state_report.yml scripts/write_stdin_to_files.py`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 18-19:

- `evidence_loading`: 64.22 seconds
- `common_analysis`: 76.61 seconds
- `openshift_analysis`: 270.20 seconds
- `posture_artifact_build`: 282.17 seconds
- `capability_artifact_build`: 150.34 seconds
- `analysis_and_artifact_build`: 869.74 seconds
- `report_rendering`: 104.02 seconds
- `workflow`: 1086.63 seconds

Timing note:

- Dynamic task count dropped from `1715` to `1676`.
- This run was substantially slower overall despite the lower task count. The slowdown was concentrated in `openshift_analysis`, `posture_artifact_build`, and `capability_artifact_build`, and the live log showed long waits in Day 2 capability enrichment, platform architecture/lifecycle synthesis, and capacity planning snapshot temp-file/helper work.
- Treat this batch as contract-correct task-count cleanup, not a proven wall-clock improvement.

Observed next hotspot:

- Stop spending effort on artifact file-write micro-optimizations for now. The next useful batch should target analysis helpers that still create/write/read/remove large temporary JSON inputs:
  - Day 2 capability section enrichment
  - platform architecture and lifecycle topology resilience
  - capacity planning current-state rebuild
  - summary aggregate and health summary synthesis

## Phase 3 Slices 20-22

Batching note:

- These slices were batched before the runtime fixture to keep performance tuning velocity up while preserving a single report-contract validation point.
- The batch targeted analysis helper invocation overhead only. It did not change findings logic, report section routing, or profile-gated rendering.

Slice 20 change:

- Reworked platform architecture and lifecycle topology resilience synthesis to use the existing stdin helper wrapper instead of Ansible-managed temp input creation, copy, command execution, and cleanup.
- The underlying helper remains `scripts/build_openshift_topology_resilience.py`, so the report payload contract remains owned by the same synthesis code.

Slice 21 change:

- Reworked capacity planning current-state synthesis to use the existing stdin helper wrapper instead of Ansible-managed temp input creation, copy, command execution, and cleanup.
- The underlying helper remains `scripts/build_openshift_cluster_current_state.py`, preserving current report semantics.

Slice 22 change:

- Reduced repeated JSON parsing in capacity IP summary normalization by parsing the rebuild helper output once and reusing the parsed value for the derived capacity facts.

Validation:

- `python3 -m py_compile scripts/run_json_helper_from_stdin.py scripts/build_openshift_topology_resilience.py scripts/build_openshift_cluster_current_state.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/posture_platform_architecture_and_lifecycle/tasks/analysis.yml roles/posture_capacity_planning_snapshot/tasks/analysis.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 20-22:

- `evidence_loading`: 26.66 seconds
- `common_analysis`: 23.24 seconds
- `openshift_analysis`: 51.11 seconds
- `posture_artifact_build`: 55.16 seconds
- `capability_artifact_build`: 116.30 seconds
- `analysis_and_artifact_build`: 278.17 seconds
- `report_rendering`: 88.51 seconds
- `workflow`: 430.64 seconds

Timing note:

- Dynamic task count dropped from `1676` to `1663`.
- Workflow time improved from `1086.63s` in the prior fixture to `430.64s` in this fixture. Treat the exact delta as directional because fixture timing is noisy, but the reduction is consistent with removing large temp-file/copy/remove paths from high-cost analysis sections.
- The report payload equality check is the main correctness gate for this batch and passed exactly after volatile metadata normalization.

Observed next hotspot:

- The next meaningful performance slice should target Day 2 capability section enrichment. It still uses large Jinja/Ansible transformations and is a likely controller-side hotspot on large clusters.
- This should be handled as a dedicated helper extraction with a synthetic input/output comparison before a full fixture, because Day 2 capability sections are customer-visible and sensitive to false positives and false negatives.

## Phase 3 Slices 23-26

Batching note:

- These slices were batched before the runtime fixture to keep tuning velocity up.
- The batch targeted the completed-assessment fast path for production Day 2 capability sections. It does not change fallback enrichment semantics when the Day 2 analyzer fails or returns no mapped capability sections.

Slice 23 change:

- Cached the production Day 2 capability assessment completion state once after normalizing the analyzer output.
- Reused this cached state in capability-section resolution and summary aggregation instead of repeating the same assessment-state and section-count expression.

Slice 24 change:

- Split fallback capability-section initialization from fallback capability-section construction.
- When completed analyzer capability sections are present, the fallback list is initialized to an empty list and the fallback construction Jinja is skipped.

Slice 25 change:

- Skipped the fallback enrichment include when completed analyzer capability sections are present.
- This avoids loading and evaluating the large fallback enrichment task path on the normal completed-assessment route.

Slice 26 change:

- Kept a defensive `when` guard inside `roles/analyze_openshift/tasks/day2/enrich_sections.yml` so direct inclusion of the fallback enrichment task still does not evaluate the large Jinja body when completed assessment output exists.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/analyze_openshift/tasks/day2/normalize.yml roles/analyze_openshift/tasks/day2/capability_sections.yml roles/analyze_openshift/tasks/day2/resolve_sections.yml roles/analyze_openshift/tasks/day2/aggregate.yml roles/analyze_openshift/tasks/day2/enrich_sections.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match
- Run log confirmed the completed-assessment fast path:
  - fallback section construction skipped
  - fallback enrichment include skipped

Latest collected fixture timing after Phase 3 Slices 23-26:

- `evidence_loading`: 94.59 seconds
- `common_analysis`: 65.82 seconds
- `openshift_analysis`: 113.32 seconds
- `posture_artifact_build`: 94.59 seconds
- `capability_artifact_build`: 98.37 seconds
- `analysis_and_artifact_build`: 419.97 seconds
- `report_rendering`: 86.66 seconds
- `workflow`: 656.55 seconds

Timing note:

- Dynamic task count changed from `1663` to `1667` because this batch adds explicit fast-path guard tasks while skipping expensive fallback work.
- This run was slower than the immediately prior `430.64s` fixture but faster than the earlier `1086.63s` fixture. Treat the timing as noisy and do not claim a proven wall-clock improvement from this batch alone.
- The contract value of this batch is that the normal completed Day 2 path now avoids the largest fallback-only Jinja block while preserving exact rendered payload output.

Observed next hotspot:

- The next useful batch should reduce repeated Ansible/Jinja transformations in the shared OpenShift domain payload builder. The log shows many domain payload build and normalize tasks taking measurable time, and those tasks run after all posture and capability artifacts are available.
- A safer approach is to extract one or two domain payload builders at a time into helper scripts, compare payload equality, then expand to the next domains after validation.

## Phase 3 Slices 27-29

Batching note:

- These slices were batched before the runtime fixture to keep tuning velocity up.
- The batch targeted task overhead in shared OpenShift domain payload assembly. It did not change domain helper scripts, report section content, or profile-gated rendering.

Slice 27 change:

- Consolidated repeated posture artifact fact resolution in `roles/report_common/tasks/build_openshift_domain_payload.yml` into one task.
- The same posture artifact variables and render-input variables are still published with the same names.

Slice 28 change:

- Consolidated repeated domain helper output normalization into one `Normalize OpenShift domain helper payloads` task.
- The same domain payload facts are still produced from the same helper command stdout values.

Slice 29 change:

- Consolidated capability artifact section lookup and Day 2 capability section overlay into one task.
- The intermediate lookup is now local to the Jinja expression; the rendered `day2_capability_sections_artifact_resolved` output remains the same.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/report_common/tasks/build_openshift_domain_payload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 27-29:

- `evidence_loading`: 26.87 seconds
- `common_analysis`: 39.27 seconds
- `openshift_analysis`: 152.60 seconds
- `posture_artifact_build`: 84.81 seconds
- `capability_artifact_build`: 108.30 seconds
- `analysis_and_artifact_build`: 434.84 seconds
- `report_rendering`: 89.03 seconds
- `workflow`: 598.18 seconds

Timing note:

- Dynamic task count dropped from `1667` to `1648`.
- Workflow time improved from the prior fixture's `656.55s` to `598.18s`, but exact timing should still be treated as noisy.
- The strongest signal from this batch is task-count reduction plus exact payload equality across every affected rendered domain.

Observed next hotspot:

- The next practical batch should target repeated report-render-stage artifact loading and restore work. The fixture log still shows measurable time in shared/posture/capability artifact loading, merge, and canonical fact restore before domain payload assembly.
- The safest approach is to inspect the artifact loaders and consolidate adjacent initialization/find/load/merge tasks where output facts can remain identical.

## Phase 3 Slices 30-32

Batching note:

- These slices were batched before the runtime fixture to improve tuning velocity.
- The batch targeted report-render-stage artifact loader overhead. It did not change artifact file names, artifact JSON shape, domain payload construction, report section content, or profile-gated rendering.

Slice 30 change:

- Simplified `roles/report_common/tasks/load_openshift_posture_artifacts.yml`.
- Removed the separate directory `find` and empty-map initialization tasks.
- The posture loader now always calls the bulk JSON artifact directory helper, which safely returns an empty object for a missing or empty directory, then recursively merges into the existing `openshift_posture_artifacts` fact.

Slice 31 change:

- Simplified `roles/report_common/tasks/load_openshift_capability_artifacts.yml`.
- Removed the separate directory `find` and empty-map initialization tasks.
- The capability loader now follows the same direct bulk-loader pattern and preserves the existing recursive merge behavior for `openshift_capability_artifacts`.

Slice 32 change:

- Simplified `roles/report_common/tasks/load_openshift_shared_artifacts.yml`.
- Removed the separate directory `find` and empty-map initialization tasks.
- Combined shared artifact merge and canonical fact restoration into one task while preserving the same restored facts for collection, analysis graph, profile, evidence summary, assessment collection summary, optional command skips, and live support data.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/report_common/tasks/load_openshift_shared_artifacts.yml roles/report_common/tasks/load_openshift_posture_artifacts.yml roles/report_common/tasks/load_openshift_capability_artifacts.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 30-32:

- `evidence_loading`: 26.38 seconds
- `collected_preparation`: 1.43 seconds
- `common_analysis`: 24.47 seconds
- `openshift_analysis`: 118.42 seconds
- `collected_health_synthesis`: 10.01 seconds
- `posture_artifact_build`: 102.88 seconds
- `capability_artifact_build`: 99.49 seconds
- `shared_artifact_persistence`: 11.99 seconds
- `analysis_and_artifact_build`: 388.26 seconds
- `report_rendering`: 70.65 seconds
- `workflow`: 521.62 seconds

Timing note:

- Dynamic task count dropped from `1648` to `1641`.
- Workflow time improved from the prior fixture's `598.18s` to `521.62s`, but exact timing should still be treated as noisy.
- The strongest signal from this batch is task-count reduction plus exact payload equality across every affected rendered domain.

Observed next hotspot:

- The next practical batch should inspect report rendering and Markdown/JSON finalization for repeated controller-side transformations that can be safely collapsed without changing the final Markdown, JSON, or persisted payload.
- A second candidate is further consolidation in artifact build orchestration where repeated include/skip scaffolding still contributes many dynamic tasks, but that area is more contract-sensitive and should be changed in smaller slices.

## Phase 3 Slices 33-35

Batching note:

- These slices were batched before the runtime fixture to improve tuning velocity.
- The batch targeted final report rendering and finalization task overhead. It did not change the report template, report payload schema, report filenames, profile-gated rendering, or artifact manifest contract.

Slice 33 change:

- Simplified `roles/report_common/tasks/render_report_artifacts.yml` for the shared live/common render path.
- Replaced the separate Markdown template render, unknown-label normalization, and workspace Markdown copy tasks with one `write_stdin_to_files.py` call.
- The rendered template content is still normalized with the same unknown-label pattern before being written to both the report output path and run workspace path.

Slice 34 change:

- Simplified `roles/report_openshift/tasks/render_collected_state_report.yml` for collected-state OpenShift rendering.
- Replaced the separate collected Markdown template render, unknown-label normalization, and workspace Markdown copy tasks with one `write_stdin_to_files.py` call.
- The collected report still writes the same output Markdown file and the same workspace Markdown artifact.

Slice 35 change:

- Consolidated collected-state JSON payload resolution and metadata compatibility fact setup into one task.
- Resume-payload reuse still uses the restored `supportability_report_payload`; fresh collected rendering still combines `openshift_report_payload_common` with collected-mode extras.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/report_common/tasks/render_report_artifacts.yml roles/report_openshift/tasks/render_collected_state_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 33-35:

- `evidence_loading`: 27.67 seconds
- `collected_preparation`: 1.84 seconds
- `common_analysis`: 43.76 seconds
- `openshift_analysis`: 143.57 seconds
- `collected_health_synthesis`: 7.57 seconds
- `posture_artifact_build`: 105.97 seconds
- `capability_artifact_build`: 121.95 seconds
- `shared_artifact_persistence`: 10.52 seconds
- `analysis_and_artifact_build`: 455.73 seconds
- `report_rendering`: 70.52 seconds
- `workflow`: 587.10 seconds

Timing note:

- Dynamic task count dropped from `1641` to `1638`.
- Workflow time increased from the prior fixture's `521.62s` to `587.10s`, so this batch should be treated as task-count cleanup rather than a proven wall-clock improvement.
- The strongest signal from this batch is exact payload equality, byte-identical report/workspace artifacts, and reduced finalization task count.

Observed next hotspot:

- The largest remaining task-count hotspot is artifact build orchestration: repeated include, resume decision, builder, and persist scaffolding around each posture and capability.
- The safer next pass is to reduce skip/include overhead around disabled or out-of-scope posture/capability artifact builders without changing the owning role boundaries or report artifact schema.

## Phase 3 Slices 36-40

Batching note:

- These slices were batched before the runtime fixture to improve tuning velocity.
- The batch targeted artifact orchestration overhead inside the shared posture/capability artifact wrapper and buffered flush helpers.
- It did not change posture or capability owner roles, artifact JSON shape, artifact file names, manifest semantics, report payload construction, or profile-gated rendering.

Slice 36 change:

- Removed the repeated posture artifact builder-selection assertion from `roles/posture_artifact_from_builder/tasks/main.yml`.
- Current posture owner roles already pass `posture_artifact_builder_tasks_from: builder.yml`, so the assertion was adding one controller-side task per enabled posture artifact without changing report behavior.

Slice 37 change:

- Removed the repeated capability artifact builder-selection assertion from `roles/capability_artifact_from_builder/tasks/main.yml`.
- Current capability owner roles already pass `capability_artifact_builder_tasks_from: builder.yml`, so the assertion was adding one controller-side task per enabled capability artifact without changing report behavior.

Slice 38 change:

- Bypassed the one-line posture persistence wrapper from `posture_artifact_from_builder`.
- The wrapper still exists for compatibility, but the builder now includes the selected `persist_openshift_posture_artifact_<mode>.yml` implementation directly.
- Buffered and immediate persistence behavior remains owned by the existing shared persistence task files.

Slice 39 change:

- Bypassed the one-line capability persistence wrapper from `capability_artifact_from_builder`.
- The builder now includes the selected `persist_openshift_capability_artifact_<mode>.yml` implementation directly.
- Buffered and immediate persistence behavior remains owned by the existing shared persistence task files.

Slice 40 change:

- Removed the extra skipped clear-buffer task from both buffered flush helpers:
  - `roles/report_common/tasks/flush_openshift_posture_artifacts.yml`
  - `roles/report_common/tasks/flush_openshift_capability_artifacts.yml`
- The normal record-flush task now clears the buffer after processing the flush result.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/posture_artifact_from_builder/tasks/main.yml roles/capability_artifact_from_builder/tasks/main.yml roles/report_common/tasks/flush_openshift_posture_artifacts.yml roles/report_common/tasks/flush_openshift_capability_artifacts.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 36-40:

- `evidence_loading`: 26.51 seconds
- `collected_preparation`: 1.45 seconds
- `common_analysis`: 23.63 seconds
- `openshift_analysis`: 49.91 seconds
- `collected_health_synthesis`: 3.66 seconds
- `posture_artifact_build`: 69.16 seconds
- `capability_artifact_build`: 101.77 seconds
- `shared_artifact_persistence`: 12.41 seconds
- `analysis_and_artifact_build`: 276.84 seconds
- `report_rendering`: 69.97 seconds
- `workflow`: 409.88 seconds

Timing note:

- Dynamic task count dropped from `1638` to `1562`.
- Workflow time improved from the prior fixture's `587.10s` to `409.88s`, but exact timing should still be treated as noisy.
- The strongest signal from this batch is the large task-count reduction plus exact payload equality and unchanged artifact counts.

Observed next hotspot:

- Batch B should focus on remaining resume/checkpoint/report-stage scaffolding and small persistence/timing overhead.
- The artifact-builder wrapper still has a per-artifact resume-decision task. Removing or consolidating that would require more careful resume-specific validation, so it should not be changed casually in the final cleanup batch unless a focused resume fixture is added.

## Phase 3 Slices 41-45

Batching note:

- These slices were batched before the runtime fixture to improve tuning velocity.
- The batch targeted timing, checkpoint, and collected-report rendering scaffolding that was outside posture/capability business logic.
- It did not change posture or capability owner roles, artifact JSON schema, report payload construction, profile-gated rendering, or final report section content.

Slice 41 change:

- Removed the per-event `python3 -c` clock subprocess from `roles/report_common/tasks/record_timing_event.yml`.
- Timing events now use Ansible's `now(utc=true)` directly in one `set_fact`.
- This keeps the same event fields while removing one controller-side command task per timing event.

Slice 42 change:

- Simplified `roles/report_common/tasks/persist_openshift_timing_artifact.yml`.
- Removed the intermediate timing-artifact normalization fact.
- Wrote the timing artifact from parsed helper output as canonical JSON through `ansible.builtin.copy`; this preserves valid JSON under Ansible native type handling and avoids the previous helper write subprocess.

Slice 43 change:

- Consolidated duplicate checkpoint manifest writes in `roles/report_common/tasks/save_run_checkpoint.yml`.
- The checkpoint manifest and workspace manifest are now written by one helper invocation using `scripts/write_stdin_to_files.py`.
- This preserves byte-identical checkpoint/workspace manifest content while reducing repeated file-write scaffolding.

Slice 44 change:

- Consolidated collected-state report naming and timestamp facts in `roles/report_openshift/tasks/render_collected_state_report.yml`.
- The collected renderer now resolves report timestamp, reusable report names, output paths, and completion timestamps in one task.

Slice 45 change:

- Re-ran the collected CI fixture and report-contract checks after fixing the timing artifact JSON write path.
- Updated this progress tracker with the final Phase 3 Batch B validation results.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/report_common/tasks/record_timing_event.yml roles/report_common/tasks/persist_openshift_timing_artifact.yml roles/report_common/tasks/save_run_checkpoint.yml roles/report_openshift/tasks/render_collected_state_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 3 Slices 41-45:

- `evidence_loading`: 86.26 seconds
- `collected_preparation`: 2.27 seconds
- `common_analysis`: 77.08 seconds
- `openshift_analysis`: 169.99 seconds
- `collected_health_synthesis`: 7.98 seconds
- `posture_artifact_build`: 123.20 seconds
- `capability_artifact_build`: 141.87 seconds
- `shared_artifact_persistence`: 16.35 seconds
- `analysis_and_artifact_build`: 549.52 seconds
- `report_rendering`: 133.16 seconds
- `workflow`: 832.96 seconds

Timing note:

- Dynamic task count dropped from `1562` to `1533`.
- The final fixture's wall-clock runtime increased from the prior `409.88s` to `832.96s`, so wall-clock time for this batch should be treated as noisy and not as a performance regression signal.
- The reliable signal is the task-count reduction, exact payload equality, valid timing artifact JSON, byte-identical report/workspace outputs, byte-identical checkpoint/workspace manifests, and unchanged artifact counts.

Phase 3 status:

- Phase 3 is complete.
- The main remaining hotspot is deeper artifact-builder resume-decision and explicit skip-heavy role dispatch. Those changes should move into Phase 4 because they need resume-specific validation and a larger dispatch refactor to avoid breaking collected-state and resume contracts.

## Phase 4 Slices 46-50

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted skip-heavy OpenShift artifact role dispatch while preserving the dedicated posture and capability owner roles.
- The dynamic dispatch keeps the existing role order and still calls the same role-local `main.yml`, `analysis.yml`, and `builder.yml` ownership paths.
- The batch also fixed a fallback identity-provider casing inconsistency found by payload parity checking.

Slice 46 change:

- Updated `roles/posture_artifact_from_builder/tasks/main.yml` so posture artifact resume decisions are resolved only during `report_run_mode=resume_last_failure`.
- Fresh runs now avoid computing resume-decision data that cannot affect execution.

Slice 47 change:

- Updated `roles/capability_artifact_from_builder/tasks/main.yml` with the same resume-only decision behavior.
- Fresh capability artifact builds still use the same builder and persistence contract.

Slice 48 change:

- Replaced the explicit collected posture artifact include list in `playbooks/openshift_cluster_health_report.yml` with a filtered dynamic role list.
- Filtering is driven by `cluster_health_profile_execution.postures.<key>.enabled`, preserving profile-gated execution and existing posture order.

Slice 49 change:

- Replaced the explicit collected capability artifact include list with a filtered dynamic role list.
- Filtering is driven by `cluster_health_profile.capabilities.<key>.enabled`, preserving enabled capability artifact generation and existing capability order.

Slice 50 change:

- Replaced the resumed collected posture and capability artifact include lists with the same filtered dynamic dispatch pattern.
- The skipped resumed-collected path remains guarded by the existing resume stage conditions.

Correctness fix:

- Normalized fallback authentication provider type rendering for `basicAuth`, `openID`, and `requestHeader` in `roles/analyze_openshift/tasks/core/authentication.yml`.
- This keeps the Ansible fallback path aligned with the Python authentication helper and prevents case-only payload drift such as `OpenID` versus `openID`.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- playbooks/openshift_cluster_health_report.yml roles/posture_artifact_from_builder/tasks/main.yml roles/capability_artifact_from_builder/tasks/main.yml roles/analyze_openshift/tasks/core/authentication.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved pre-helper baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 4 Slices 46-50:

- `evidence_loading`: 286.36 seconds
- `collected_preparation`: 5.66 seconds
- `common_analysis`: 179.20 seconds
- `openshift_analysis`: 222.17 seconds
- `collected_health_synthesis`: 11.09 seconds
- `posture_artifact_build`: 174.70 seconds
- `capability_artifact_build`: 170.07 seconds
- `shared_artifact_persistence`: 22.76 seconds
- `analysis_and_artifact_build`: 800.65 seconds
- `report_rendering`: 228.62 seconds
- `workflow`: 1490.10 seconds

Timing note:

- Static task count at play start dropped from `465` to `317`.
- Final dynamic task count dropped from `1533` to `1385`.
- The final fixture's wall-clock runtime was `1490.10s`; this environment remains noisy, so the reliable signal is the task-count reduction plus exact payload equality, valid timing JSON, byte-identical report/workspace outputs, byte-identical checkpoint/workspace manifests, and unchanged artifact counts.

Observed next hotspot:

- Live and resumed-live artifact dispatch still contain explicit skip-heavy role lists.
- A future Phase 4 batch can apply the same filtered dynamic dispatch pattern to those paths, but it should include live or resume-specific validation because the current CI fixture primarily exercises collected-state behavior.

## Phase 4 Slices 51-55

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted live and resumed-live OpenShift artifact dispatch, applying the same filtered dynamic role-dispatch pattern already used for collected and resumed-collected paths.
- The change preserves the dedicated posture and capability owner roles; it only changes how enabled roles are selected and invoked.
- Existing role order is preserved by ordered play-level posture and capability role maps.

Slice 51 change:

- Added ordered play-level posture and capability artifact role maps in `playbooks/openshift_cluster_health_report.yml`.
- The maps are used by the new live and resumed-live dynamic dispatch paths and keep the existing OpenShift report artifact build order.

Slice 52 change:

- Replaced the explicit live posture artifact include list with a filtered dynamic role list.
- Filtering is driven by `cluster_health_profile_execution.postures.<key>.enabled`, preserving profile-gated execution and existing posture ownership.

Slice 53 change:

- Replaced the explicit live capability artifact include list with a filtered dynamic role list.
- Filtering is driven by `cluster_health_profile.capabilities.<key>.enabled`, preserving enabled capability artifact generation and existing capability order.

Slice 54 change:

- Replaced the explicit resumed-live posture artifact include list with the same filtered dynamic role dispatch pattern.
- The path remains guarded by the existing `report_run_mode=resume_last_failure` and live-mode conditions.

Slice 55 change:

- Replaced the explicit resumed-live capability artifact include list with the same filtered dynamic role dispatch pattern.
- The path still uses the existing resumed-live artifact and checkpoint contract.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report artifacts: `3`
  - shared artifacts: `2`
- Compared the regenerated report payload with the saved baseline after normalizing expected volatile metadata. Result: normalized payloads matched exactly.
- Compared key rendered payload areas directly:
  - `domains.observability`: exact match
  - `domains.workload_health`: exact match
  - `domains.platform_health`: exact match
  - `domains.production_day2_readiness`: exact match
  - `domains.security_and_governance`: exact match
  - `domains.network_and_application_access`: exact match
  - `domains.storage_and_resilience`: exact match
  - `health_summary`: exact match
  - `day2_capability_sections`: exact match

Latest collected fixture timing after Phase 4 Slices 51-55:

- `evidence_loading`: 26.13 seconds
- `collected_preparation`: 0.61 seconds
- `common_analysis`: 22.68 seconds
- `openshift_analysis`: 135.32 seconds
- `collected_health_synthesis`: 7.21 seconds
- `posture_artifact_build`: 120.06 seconds
- `capability_artifact_build`: 102.84 seconds
- `shared_artifact_persistence`: 17.42 seconds
- `analysis_and_artifact_build`: 413.23 seconds
- `report_rendering`: 116.42 seconds
- `workflow`: 592.77 seconds

Timing note:

- Static task count at play start dropped from `317` to `169`.
- Final dynamic task count dropped from `1385` to `1237`.
- Skipped tasks dropped from `334` to `186`.
- The latest fixture's wall-clock runtime was `592.77s`; this environment remains noisy, so the reliable signal is the task-count reduction plus exact payload equality, valid timing JSON, byte-identical report/workspace outputs, byte-identical checkpoint/workspace manifests, and unchanged artifact counts.

Observed next hotspot:

- The largest remaining fixture costs are actual analysis, artifact-build, and rendering work rather than skip-heavy static dispatch.
- Current fixture timing hotspots are `openshift_analysis` at `135.32s`, `posture_artifact_build` at `120.06s`, `capability_artifact_build` at `102.84s`, and `report_rendering` at `116.42s`.
- A small cleanup can remove duplicate collected/resumed-collected local role maps by reusing the play-level maps, but that is more maintainability-focused than runtime-focused.
- The next meaningful performance pass should target data-heavy helper consolidation, expensive analysis slices, or report payload/template rendering cost while preserving exact payload parity.

## Phase 4 Slices 56-60

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch finished the artifact-role dispatch cleanup by centralizing enabled OpenShift artifact role list resolution once after selector-scope dependency resolution.
- The change preserves the existing modular owner roles and report order; posture and capability roles still own their own artifact content.

Slice 56 change:

- Added one centralized `Resolve enabled OpenShift artifact role lists` task in `playbooks/openshift_cluster_health_report.yml`.
- The posture list is still filtered from `cluster_health_profile_execution.postures.<key>.enabled`.
- The capability list is still filtered from `cluster_health_profile.capabilities.<key>.enabled`.

Slice 57 change:

- Removed the duplicate live-run enabled posture and capability role-list build tasks.
- Live artifact dispatch now reuses the centralized enabled role lists.

Slice 58 change:

- Removed the duplicate resumed-live enabled posture and capability role-list build tasks.
- Resumed-live artifact dispatch now reuses the centralized enabled role lists.

Slice 59 change:

- Removed duplicate collected-run local artifact role maps and list-building tasks.
- Collected artifact dispatch now reuses the play-level maps and centralized enabled role lists.

Slice 60 change:

- Removed duplicate resumed-collected local artifact role maps and list-building tasks.
- Resumed-collected artifact dispatch now reuses the play-level maps and centralized enabled role lists.

Correctness hardening found during validation:

- Fixed supportability evidence summary fallback so empty live-support placeholders no longer mask collected evidence.
- This corrected a false `insufficient-evidence` reference-compliance result when collected `cluster-compare` evidence exists.
- Hardened observability metric summary handling so a successful helper invocation with empty stdout uses explicit safe defaults instead of failing the report run.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- playbooks/openshift_cluster_health_report.yml roles/analyze_openshift/tasks/supportability_evidence/summaries.yml roles/analyze_openshift/tasks/observability/findings.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 4 Slices 56-60:

- `evidence_loading`: 90.32 seconds
- `collected_preparation`: 2.33 seconds
- `common_analysis`: 76.04 seconds
- `openshift_analysis`: 339.30 seconds
- `collected_health_synthesis`: 11.01 seconds
- `posture_artifact_build`: 77.06 seconds
- `capability_artifact_build`: 51.69 seconds
- `shared_artifact_persistence`: 9.09 seconds
- `analysis_and_artifact_build`: 575.07 seconds
- `report_rendering`: 74.99 seconds
- `workflow`: 772.23 seconds

Timing note:

- Static task count at play start dropped from `169` to `162`.
- Final dynamic task count dropped from `1237` to `1230`.
- Skipped tasks dropped from `186` to `180`.
- The latest fixture's wall-clock runtime was `772.23s`; this environment remains noisy, so the reliable signal is the task-count reduction plus successful rendered-report validation, byte-identical report/workspace outputs, byte-identical checkpoint/workspace manifests, and preserved artifact counts.

Observed next hotspot:

- Skip-heavy artifact dispatch cleanup is now largely complete.
- The next meaningful pass should target expensive helper/process churn and data-heavy analysis work while preserving report accuracy.
- Current fixture timing hotspots are `openshift_analysis` at `339.30s`, `evidence_loading` at `90.32s`, `common_analysis` at `76.04s`, `posture_artifact_build` at `77.06s`, and `report_rendering` at `74.99s`.

## Phase 4 Slices 61-65

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted repeated helper invocations that serialize large pod/workload inputs.
- Existing helper logic remains the source of truth; the new runner only executes multiple existing helpers from one Ansible command task.

Slice 61 change:

- Added `scripts/run_json_helpers_from_stdin.py`.
- The helper accepts a batch payload, writes repo-local temporary JSON input files, executes existing JSON-file helpers in-process, and returns a structured result map.
- The script avoids `from __future__ import annotations` and modern-only type syntax for compatibility with older Python runtimes seen on customer bastions.

Slice 62 change:

- Batched common security hygiene helper execution in `roles/analyze_common/tasks/security/hygiene_and_pod_security.yml`.
- Consolidated namespace hygiene, pod CPU request mapping, pod security hardening, and storage/sensitive-string findings into one Ansible command task.

Slice 63 change:

- Preserved the existing common security fact expansion contract.
- The same facts are still published: namespace policy/quota/limitrange counts, missing namespace controls, `pod_cpu_request_map`, `node_cpu_request_millicores`, `security_findings`, and `workload_practice_findings`.

Slice 64 change:

- Batched OpenShift workload analysis helper execution in `roles/analyze_openshift/tasks/workload.yml`.
- Consolidated workload health, workload label governance, node label governance, DeploymentConfig resource findings, and route/ingress findings into one Ansible command task.

Slice 65 change:

- Preserved OpenShift workload fact expansion semantics.
- The same facts are still published: platform pod issues, workload health issues, high-replica workloads, probe findings, workload label governance, node label governance, DeploymentConfig resource findings, and route/ingress ownership/conflict data.

Validation:

- `python3 -m py_compile scripts/run_json_helpers_from_stdin.py`
- Minimal batch-runner smoke test with two helper entries
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/run_json_helpers_from_stdin.py roles/analyze_common/tasks/security/hygiene_and_pod_security.yml roles/analyze_openshift/tasks/workload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 4 Slices 61-65:

- `evidence_loading`: 63.39 seconds
- `collected_preparation`: 1.54 seconds
- `common_analysis`: 42.20 seconds
- `openshift_analysis`: 108.78 seconds
- `collected_health_synthesis`: 5.81 seconds
- `posture_artifact_build`: 98.59 seconds
- `capability_artifact_build`: 77.86 seconds
- `shared_artifact_persistence`: 13.92 seconds
- `analysis_and_artifact_build`: 356.06 seconds
- `report_rendering`: 70.56 seconds
- `workflow`: 521.47 seconds

Timing note:

- Static task count at play start stayed at `162`.
- Final dynamic task count dropped from `1230` to `1224`.
- Successful task count dropped from `581` to `578`.
- Skipped tasks stayed at `180`.
- The latest fixture's wall-clock runtime was `521.47s`; this environment remains noisy, so the reliable signal is the task-count reduction plus successful rendered-report validation, byte-identical report/workspace outputs, byte-identical checkpoint/workspace manifests, and preserved artifact counts.

Observed next hotspot:

- Helper batching is now proven for two high-fanout analysis slices.
- The next similar target is common security storage/TLS and reference/RBAC/CRD analysis, but those include dependent external checks (`openssl` and live CRD instance counts), so batching must preserve those dependency boundaries.
- Remaining larger timing hotspots also include posture artifact analysis/build and report payload rendering.

## Phase 4 Slices 66-70

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted independent common security helpers while preserving dependency-sensitive external checks.
- Existing helper scripts remain the source of truth; `scripts/run_json_helpers_from_stdin.py` only reduces Ansible command/task churn around them.

Slice 66 change:

- Batched deprecation, endpoint, and IP capacity helper execution in `roles/analyze_common/tasks/security/deprecation_endpoints_and_ip_capacity.yml`.
- Consolidated `build_deprecation_endpoint_findings.py` and `build_ip_capacity_summary.py` behind one batch-runner command.

Slice 67 change:

- Preserved effective IP capacity cluster profile resolution before the helper bundle.
- Normalized service, pod, and node IP-capacity summaries from the bundled helper result without changing downstream fact names.

Slice 68 change:

- Batched reference usage, privileged RBAC, and namespaced CRD target discovery in `roles/analyze_common/tasks/security/references_rbac_and_crd_usage.yml`.
- Consolidated `build_reference_usage_findings.py` and the CRD target-discovery mode of `build_crd_usage_facts.py` behind one batch-runner command.

Slice 69 change:

- Preserved the CRD instance-count dependency boundary.
- The CRD instance-count command still runs separately because likely-unused CRD findings depend on those external count results.

Slice 70 change:

- Preserved optional/common security failure behavior with `fail_on_error: false` and safe default result normalization.
- The rendered report still receives the same named facts, reducing false-positive/false-negative risk from task restructuring.

Validation:

- `python3 -m py_compile scripts/run_json_helpers_from_stdin.py scripts/build_deprecation_endpoint_findings.py scripts/build_ip_capacity_summary.py scripts/build_reference_usage_findings.py scripts/build_crd_usage_facts.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- roles/analyze_common/tasks/security/deprecation_endpoints_and_ip_capacity.yml roles/analyze_common/tasks/security/references_rbac_and_crd_usage.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 4 Slices 66-70:

- `evidence_loading`: 25.93 seconds
- `collected_preparation`: 0.70 seconds
- `common_analysis`: 18.70 seconds
- `openshift_analysis`: 98.12 seconds
- `collected_health_synthesis`: 5.65 seconds
- `posture_artifact_build`: 106.15 seconds
- `capability_artifact_build`: 189.82 seconds
- `shared_artifact_persistence`: 27.59 seconds
- `analysis_and_artifact_build`: 457.89 seconds
- `report_rendering`: 100.77 seconds
- `workflow`: 650.06 seconds

Timing note:

- Static task count at play start stayed at `162`.
- Final dynamic task count dropped from `1224` to `1220`.
- Successful task count dropped from `578` to `576`.
- Skipped tasks stayed at `180`.
- The latest fixture's wall-clock runtime was `650.06s`; this environment remains noisy, so the reliable signal is the task-count reduction plus successful rendered-report validation, byte-identical report/workspace outputs, byte-identical checkpoint/workspace manifests, and preserved artifact counts.

Observed next hotspot:

- The remaining common security storage/TLS file is only partly batchable because the TLS expiry probe uses an external `openssl` boundary.
- Larger remaining hotspots are now posture/capability artifact build and final report payload/render assembly.
- The next high-value pass should reduce artifact-builder and render-stage Ansible fact churn while preserving the existing artifact-first resume contract.

## Phase 5 Slices 71-75

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted artifact persistence plumbing, not posture or capability business logic.
- The report contract remains artifact-first: posture/capability artifacts still render through the same workspace, manifest, resume, and final-report paths.

Slice 71 change:

- Added `roles/report_common/tasks/prepare_openshift_artifact_persistence_context.yml`.
- This task precomputes posture dependency keys, capability dependency keys, derived shared inputs, and Day 2 capability sections by key once per artifact-build phase.

Slice 72 change:

- Wired the persistence-context preparation task into live and collected fresh artifact-build flows before posture/capability artifacts are built.
- This removes repeated dependency/shared-input expansion from every artifact payload build.

Slice 73 change:

- Wired the same persistence-context preparation into resumed live and resumed collected analysis flows before artifact rebuilds.
- This keeps resume behavior aligned with fresh-run artifact behavior.

Slice 74 change:

- Simplified buffered posture and capability artifact persistence tasks to consume precomputed maps.
- Removed the per-capability fallback scan across `day2_capability_sections`; capability artifacts now use the prepared `day2_capability_sections_by_key` lookup.

Slice 75 change:

- Kept immediate and buffered artifact persistence modes aligned by applying the same lookup simplification to both paths.
- Explicit artifact-specific overrides are still honored when provided, preserving extension compatibility.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- playbooks/openshift_cluster_health_report.yml roles/report_common/tasks/prepare_openshift_artifact_persistence_context.yml roles/report_common/tasks/persist_openshift_capability_artifact_buffered.yml roles/report_common/tasks/persist_openshift_capability_artifact_immediate.yml roles/report_common/tasks/persist_openshift_posture_artifact_buffered.yml roles/report_common/tasks/persist_openshift_posture_artifact_immediate.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 5 Slices 71-75:

- `evidence_loading`: 79.37 seconds
- `collected_preparation`: 2.85 seconds
- `common_analysis`: 68.19 seconds
- `openshift_analysis`: 186.16 seconds
- `collected_health_synthesis`: 7.13 seconds
- `posture_artifact_build`: 119.33 seconds
- `capability_artifact_build`: 87.21 seconds
- `shared_artifact_persistence`: 12.09 seconds
- `analysis_and_artifact_build`: 491.09 seconds
- `report_rendering`: 103.51 seconds
- `workflow`: 711.06 seconds

Timing note:

- Static task count increased from `162` to `164` because artifact persistence context is now prepared explicitly.
- Final dynamic task count increased from `1220` to `1223`.
- Successful task count dropped from `576` to `575`.
- Skipped tasks increased from `180` to `183` because resumed-flow preparation is visible but skipped in the fixture's fresh collected run.
- The latest fixture's wall-clock runtime was `711.06s`; this environment remains noisy, so the reliable signal is preserved report correctness plus reduced repeated per-artifact Jinja work in the artifact persistence path.

Observed next hotspot:

- Artifact persistence context is now centralized and prepared once, but per-artifact payload construction still uses Ansible `set_fact` once per posture/capability.
- Capability artifact build timing improved in this fixture relative to the prior run, while posture build and render remain noisy and still expensive.
- The next high-value pass should target final report payload/render assembly and possibly move mechanical domain payload composition into fewer helper calls while preserving rendered-section accuracy.

## Phase 5 Slices 76-82

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted render-domain helper process and task churn, not posture or capability business logic.
- Existing domain helper scripts remain the source of truth for domain payload semantics.
- Final collected/live domain payload structure and output fact names were preserved.

Slice 76 change:

- Bundled the security governance render-domain helper into a single render-domain helper batch.
- Preserved the existing `security_governance_domain_payload` output fact.

Slice 77 change:

- Bundled the platform health and observability render-domain helpers into the same batch.
- Preserved the existing `platform_health_domain_payload` and `observability_domain_payload` output facts.

Slice 78 change:

- Bundled the node health and network access render-domain helpers into the same batch.
- Preserved the existing `node_health_domain_payload` and `network_access_domain_payload` output facts.

Slice 79 change:

- Bundled the workload health and storage/resilience render-domain helpers into the same batch.
- Preserved the existing `workload_health_domain_payload` and `storage_resilience_domain_payload` output facts.

Slice 80 change:

- Collapsed posture-artifact render fact resolution into one task to reduce repeated Ansible `set_fact` overhead before domain payload assembly.
- Kept all downstream fact names unchanged.

Slice 81 change:

- Collapsed capability artifact Day 2 section resolution into one task while preserving the rendered capability section list.
- Kept collected/live final domain payload assembly shape unchanged.

Slice 82 change:

- Kept helper failure behavior fail-closed with `fail_on_error: true`.
- A helper failure still fails the report build instead of silently producing partial or stale domain payload data.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `python3 -m py_compile scripts/run_json_helpers_from_stdin.py scripts/build_security_governance_domain_payload.py scripts/build_platform_health_domain_payload.py scripts/build_observability_domain_payload.py scripts/build_node_health_domain_payload.py scripts/build_network_access_domain_payload.py scripts/build_workload_health_domain_payload.py scripts/build_storage_resilience_domain_payload.py`
- `git diff --check -- roles/report_common/tasks/build_openshift_domain_payload.yml scripts/run_json_helpers_from_stdin.py scripts/build_security_governance_domain_payload.py scripts/build_platform_health_domain_payload.py scripts/build_observability_domain_payload.py scripts/build_node_health_domain_payload.py scripts/build_network_access_domain_payload.py scripts/build_workload_health_domain_payload.py scripts/build_storage_resilience_domain_payload.py`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 5 Slices 76-82:

- `evidence_loading`: 78.03 seconds
- `collected_preparation`: 2.32 seconds
- `common_analysis`: 51.77 seconds
- `openshift_analysis`: 143.20 seconds
- `collected_health_synthesis`: 5.72 seconds
- `posture_artifact_build`: 90.83 seconds
- `capability_artifact_build`: 84.63 seconds
- `shared_artifact_persistence`: 12.88 seconds
- `analysis_and_artifact_build`: 398.86 seconds
- `report_rendering`: 71.83 seconds
- `workflow`: 584.85 seconds

Timing note:

- Static task count stayed at `164`.
- Final dynamic task count dropped from `1223` to `1217`.
- Successful task count dropped from `575` to `570`.
- Skipped tasks dropped from `183` to `182`.
- The latest fixture's wall-clock runtime was `584.85s`; this environment remains noisy, so the reliable signal is preserved report correctness plus a six-task reduction in the render-domain path.

Observed next hotspot:

- Final report payload assembly still contains large mechanical `set_fact` operations and Markdown rendering remains a significant controller-side cost.
- The next high-value pass should target collected-state report payload assembly in `roles/report_common/tasks/build_openshift_report_payload.yml`, but this touches the final JSON contract and must be validated with the fixture before moving on.

## Phase 5 Slices 83-90

Batching note:

- These slices were batched before the final runtime fixture to increase tuning velocity.
- The batch targeted final OpenShift report payload assembly, not report-template content or posture/capability business logic.
- The existing Ansible role remains the owner of when report payloads are built; the helper only performs deterministic JSON-shaped payload construction.
- The helper covers collected-state, fresh live, and resumed live payload modes to avoid creating divergent report families.

Slice 83 change:

- Added `scripts/build_openshift_report_payload.py`.
- The helper builds the shared OpenShift report payload from explicitly supplied facts and preserves the existing top-level payload shape.

Slice 84 change:

- Moved collected-state shared report payload assembly out of a large Ansible `set_fact` block and into the helper.
- Preserved collected metadata, audit, supportability, evidence, domain, findings, metrics, and supplemental artifact keys.

Slice 85 change:

- Moved resumed live shared report payload assembly into the same helper.
- Preserved the resumed live metadata and checkpoint behavior while keeping reusable payload handling outside the helper.

Slice 86 change:

- Moved fresh live shared report payload assembly into the same helper.
- Preserved live supportability, evidence, findings, metrics, and supplemental artifact keys.

Slice 87 change:

- Added one normalization task that restores the helper output into `openshift_report_payload_common`.
- Used mode-specific command registers so skipped mutually exclusive branches cannot overwrite the executed branch result.

Slice 88 change:

- Preserved collected evidence coverage recursive merge semantics in the helper.
- Existing nested coverage fields are retained when the helper adds or overrides collected-state coverage status details.

Slice 89 change:

- Kept downstream report rendering unchanged.
- `report_openshift` still combines `openshift_report_payload_common` with mode extras and writes the same final JSON and Markdown artifacts.

Slice 90 change:

- Kept the helper fail-closed.
- If payload construction fails, the report build fails rather than rendering a partial payload.

Validation:

- `python3 -m py_compile scripts/build_openshift_report_payload.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_openshift_report_payload.py roles/report_common/tasks/build_openshift_report_payload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 5 Slices 83-90:

- `evidence_loading`: 88.51 seconds
- `collected_preparation`: 2.13 seconds
- `common_analysis`: 58.39 seconds
- `openshift_analysis`: 182.14 seconds
- `collected_health_synthesis`: 6.26 seconds
- `posture_artifact_build`: 97.60 seconds
- `capability_artifact_build`: 98.85 seconds
- `shared_artifact_persistence`: 44.01 seconds
- `analysis_and_artifact_build`: 503.18 seconds
- `report_rendering`: 89.50 seconds
- `workflow`: 727.43 seconds

Timing note:

- Static task count stayed at `164`.
- Final dynamic task count increased from `1217` to `1218`.
- Successful task count increased from `570` to `571`.
- Skipped tasks stayed at `182`.
- This batch trades one extra normalization task for removing a large report-payload construction `set_fact` from Ansible's templating engine.
- The latest fixture's wall-clock runtime was `727.43s`; this environment remains noisy, so the reliable signal is preserved report correctness and relocation of mechanical payload assembly into a reusable Python helper.

Observed next hotspot:

- The final report rendering path still spends meaningful time loading and merging shared, posture, and capability artifacts before rendering Markdown.
- The next high-value pass should target the render-only artifact load/merge sequence and collected-state report extras, while preserving artifact-granular resume behavior and final report JSON equivalence.

## Phase 5 Slices 91-98

Batching note:

- These slices were batched before the final runtime fixture to increase tuning velocity.
- The batch targeted render-time artifact preparation, offline support-table construction, and collected-state report extras.
- The final report contract is preserved; the helper prepares the same fact names that the previous Ansible task chain produced.
- The change remains collected-state specific in the render path and does not create a separate OpenShift report family.

Slice 91 change:

- Added `scripts/prepare_openshift_render_artifacts.py`.
- The helper loads shared, posture, and capability artifact directories in one Python pass.

Slice 92 change:

- Preserved shared artifact key normalization semantics.
- `shared-collection` still restores to `collection`, and `shared-analysis-graph` still restores to `analysis_graph`.

Slice 93 change:

- Preserved canonical collected-state facts restored from shared artifacts.
- The helper restores `collected_resource_graph`, `analysis_graph`, `cluster_profile`, evidence summary, assessment collection summary, assessment collection failures, optional command skips, and live support data.

Slice 94 change:

- Moved collected-state OpenShift support table synthesis into the helper.
- Operator, MachineConfigPool, and Route summaries are still derived from the collected resource graph.

Slice 95 change:

- Added `roles/report_common/tasks/prepare_openshift_render_artifacts.yml`.
- The role task invokes the helper and normalizes its output into the existing Ansible fact names consumed by downstream rendering.

Slice 96 change:

- Replaced separate render-time includes for support-table building and artifact loading in `roles/report_openshift/tasks/render_collected_state_report.yml`.
- The render path now uses a single render-preparation include before payload construction.

Slice 97 change:

- Folded collected-state top-level report extras into `scripts/build_openshift_report_payload.py`.
- `cluster_compare`, `inspect`, `sosreport`, `advisor_export`, `insights_archive`, and `managed_gates` remain present in the final payload shape.

Slice 98 change:

- Removed the separate collected-state report-extras include from the render path.
- Existing supplemental artifact payload handling remains unchanged.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py scripts/build_openshift_report_payload.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/prepare_openshift_render_artifacts.py scripts/build_openshift_report_payload.py roles/report_common/tasks/prepare_openshift_render_artifacts.yml roles/report_openshift/tasks/render_collected_state_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 5 Slices 91-98:

- `evidence_loading`: 76.18 seconds
- `collected_preparation`: 2.19 seconds
- `common_analysis`: 54.08 seconds
- `openshift_analysis`: 171.01 seconds
- `collected_health_synthesis`: 6.91 seconds
- `posture_artifact_build`: 94.16 seconds
- `capability_artifact_build`: 69.57 seconds
- `shared_artifact_persistence`: 11.67 seconds
- `analysis_and_artifact_build`: 416.96 seconds
- `report_rendering`: 84.53 seconds
- `workflow`: 612.08 seconds

Timing note:

- Static task count stayed at `164`.
- Final dynamic task count dropped from `1218` to `1206`.
- Successful task count dropped from `571` to `563`.
- Skipped tasks stayed at `182`.
- The latest fixture's wall-clock runtime was `612.08s`; this environment remains noisy, so the reliable signal is preserved report correctness plus a twelve-task reduction in the render-preparation path.

Observed next hotspot:

- Render preparation still normalizes large artifact maps back into Ansible facts, which can be expensive on large clusters.
- Markdown rendering remains a significant controller-side cost.
- The next high-value pass should reduce large render-time fact normalization or move additional deterministic domain payload assembly into helpers, while preserving final JSON and Markdown report equivalence.

## Phase 6 Slices 99-102

Batching note:

- These slices were batched before the runtime fixture to increase tuning velocity.
- The batch targeted collected-state domain payload assembly, not posture or capability business logic.
- The live report path remains unchanged in this batch.
- The final OpenShift report contract is preserved; the helper emits the same domain payload shape consumed by the report payload builder and templates.

Slice 99 change:

- Added `scripts/build_collected_openshift_domain_payload.py`.
- The helper builds the collected-state `openshift_report_domain_payload` from already resolved posture artifacts, render inputs, helper-built domain payloads, and compatibility facts.

Slice 100 change:

- Replaced the large collected-state `openshift_report_domain_payload` Ansible `set_fact` block in `roles/report_common/tasks/build_openshift_domain_payload.yml`.
- The collected path now calls the helper and normalizes only the final domain payload result.

Slice 101 change:

- Moved collected-state Day 2 capability-section artifact resolution into the collected domain payload helper.
- The existing Ansible capability-section resolution task is now skipped for collected runs and remains available for live runs.

Slice 102 change:

- Preserved collected-state fallback order for supportability, lifecycle, capacity, declarative operations, release engineering, and Day 2 production readiness domains.
- Existing artifact values still win over render inputs, and render inputs still win over analysis facts where that was the previous collected-state behavior.

Validation:

- `python3 -m py_compile scripts/build_collected_openshift_domain_payload.py scripts/prepare_openshift_render_artifacts.py scripts/build_openshift_report_payload.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/build_collected_openshift_domain_payload.py roles/report_common/tasks/build_openshift_domain_payload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 6 Slices 99-102:

- `evidence_loading`: 77.12 seconds
- `collected_preparation`: 1.88 seconds
- `common_analysis`: 48.41 seconds
- `openshift_analysis`: 122.65 seconds
- `collected_health_synthesis`: 4.97 seconds
- `posture_artifact_build`: 79.68 seconds
- `capability_artifact_build`: 67.08 seconds
- `shared_artifact_persistence`: 10.87 seconds
- `analysis_and_artifact_build`: 341.88 seconds
- `report_rendering`: 137.68 seconds
- `workflow`: 589.00 seconds

Timing note:

- Static task count stayed at `164`.
- Final dynamic task count increased from `1206` to `1207` because the new collected helper adds a command task while the skipped Day 2 artifact-resolution task remains counted dynamically.
- Successful task count stayed at `563`.
- Skipped tasks increased from `182` to `183`.
- The latest fixture's wall-clock runtime was `589.00s` from the timing artifact; the terminal progress elapsed was noisier, so the reliable signal remains preserved report correctness and removal of one large collected-state domain payload `set_fact` block from Ansible templating.

Observed next hotspot:

- Render preparation still spends heavily in `Normalize OpenShift render artifacts and support tables`, which normalizes large artifact maps back into Ansible facts.
- `Resolve OpenShift posture artifact facts` and `Normalize OpenShift domain helper payloads` are also visible render-stage costs on this fixture.
- The next high-value pass should reduce render-stage compatibility fact normalization by loading only the posture/capability slices needed for final rendering, or by extending helper input/output so downstream report payload construction can consume file-backed artifacts without rebuilding large intermediate Ansible facts.

## Phase 6 Slices 103-110

Batching note:

- These slices were completed together before the runtime fixture to avoid slow one-slice-at-a-time fixture cycles.
- The batch targets collected-state render preparation and domain payload compatibility facts.
- The live report path remains unchanged; live runs still resolve artifact-backed facts through the existing task path.
- The final report contract is preserved; the collected path still renders from the same persisted shared, posture, capability, and report artifacts.

Slice 103 change:

- Updated `scripts/prepare_openshift_render_artifacts.py` to emit selected shared artifact compatibility facts directly.
- The helper now provides `openshift_shared_collection_artifact`, `openshift_shared_analysis_graph_artifact`, and `openshift_artifact_backed_cluster_profile`.

Slice 104 change:

- Updated the render-prep helper to emit posture artifact and render-input facts directly for each enabled OpenShift posture family.
- Collected rendering no longer needs a full `openshift_posture_artifacts` map normalized back into Ansible facts before domain payload assembly.

Slice 105 change:

- Updated the render-prep helper to emit `openshift_capability_artifact_sections`.
- The collected Day 2 capability-section resolver can now use section-level data instead of the full capability artifact map.

Slice 106 change:

- Updated the render-prep helper to emit `analysis_graph_ingress_count`.
- Collected network-domain payload assembly no longer reads the full `analysis_graph.ingresses` structure from Ansible facts.

Slice 107 change:

- Removed collected render normalization of full `openshift_shared_artifacts`, `openshift_posture_artifacts`, `openshift_capability_artifacts`, `collected_resource_graph`, and `analysis_graph`.
- The collected render-prep task now normalizes only the targeted compatibility facts and report support tables required downstream.

Slice 108 change:

- Skipped shared and posture artifact fact resolver tasks for collected render mode.
- Collected mode uses the facts prepared by the render-prep helper, while live mode keeps the previous resolver behavior.

Slice 109 change:

- Updated `scripts/build_collected_openshift_domain_payload.py` to prefer `openshift_capability_artifact_sections`.
- The helper still keeps a fallback to full capability artifacts for compatibility with older or direct helper invocations.

Slice 110 change:

- Stopped sending large artifact and graph maps through the collected render-prep helper stdin during normal collected report rendering.
- The helper reads persisted artifacts from the run workspace and only receives small fallback/default values from Ansible.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py scripts/build_collected_openshift_domain_payload.py scripts/build_openshift_report_payload.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/prepare_openshift_render_artifacts.py scripts/build_collected_openshift_domain_payload.py roles/report_common/tasks/prepare_openshift_render_artifacts.yml roles/report_common/tasks/build_openshift_domain_payload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 6 Slices 103-110:

- `evidence_loading`: 199.12 seconds
- `collected_preparation`: 7.99 seconds
- `common_analysis`: 115.30 seconds
- `openshift_analysis`: 192.94 seconds
- `collected_health_synthesis`: 8.86 seconds
- `posture_artifact_build`: 123.47 seconds
- `capability_artifact_build`: 96.12 seconds
- `shared_artifact_persistence`: 15.17 seconds
- `analysis_and_artifact_build`: 572.31 seconds
- `report_rendering`: 178.80 seconds
- `workflow`: 996.82 seconds

Timing note:

- The fixture passed, but this local run was materially slower than the prior run across unrelated stages such as evidence loading and common analysis, so the wall-clock number should not be treated as a clean before/after performance comparison.
- The render-prep task now avoids full artifact-map normalization, but it still normalizes full posture artifact objects as individual compatibility facts; that remains visible in `Normalize OpenShift render artifacts and support tables`.
- Phase 6 is functionally complete. The next optimization phase should target eliminating large posture artifact object normalization entirely by having report/domain helpers consume file-backed posture fields or narrowed render slices directly.

## Phase 7 Slices 111-118

Batching note:

- These slices were completed together before one runtime fixture to keep performance tuning velocity up.
- The batch targets collected render-time posture artifact normalization only.
- The live report path remains compatibility-safe because existing live posture artifact facts are still used when no collected render slice map is present.
- The final report contract is preserved; the collected path still renders from persisted posture artifacts, but only narrowed render slices are normalized into Ansible facts for report assembly.

Slice 111 change:

- Inventoried collected render consumers of `*_posture_artifact` and `*_posture_render_inputs`.
- Confirmed the remaining heavy path was `roles/report_common/tasks/prepare_openshift_render_artifacts.yml` normalizing every full posture artifact object for collected rendering.

Slice 112 change:

- Added a posture render-slice schema to `scripts/prepare_openshift_render_artifacts.py`.
- Each collected posture slice contains an `artifact` object without the nested `render_inputs` field and a narrowed `render_inputs` object.

Slice 113 change:

- Added per-posture render-input allowlists for fields consumed by the collected report/domain helpers.
- This avoids carrying unrelated render-input data into Ansible facts during collected report rendering.

Slice 114 change:

- Replaced individual collected render-prep facts such as `platform_health_posture_artifact` and `platform_health_posture_render_inputs` with one `openshift_posture_render_slices` map.
- The render-prep task no longer normalizes full posture artifact objects as individual collected-mode facts.

Slice 115 change:

- Updated the OpenShift domain helper bundle task to resolve posture artifact inputs from `openshift_posture_render_slices` when present.
- Existing individual posture facts remain fallback inputs for live mode and compatibility paths.

Slice 116 change:

- Updated the collected OpenShift domain payload task to consume the same narrowed render slices for supportability, lifecycle, capacity, declarative operations, release engineering, and Day 2 readiness.
- Fallbacks to existing variables remain in place for direct or legacy invocation paths.

Slice 117 change:

- Preserved collected-mode capability section behavior through `openshift_capability_artifact_sections`.
- No capability artifact rendering contract was changed in this phase.

Slice 118 change:

- Preserved report correctness by keeping the existing domain helper interfaces and changing only the data source feeding them.
- This limits the blast radius to collected render plumbing while avoiding report-shape changes.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py scripts/build_collected_openshift_domain_payload.py scripts/build_openshift_report_payload.py scripts/build_platform_health_domain_payload.py scripts/build_node_health_domain_payload.py scripts/build_network_access_domain_payload.py scripts/build_storage_resilience_domain_payload.py scripts/build_workload_health_domain_payload.py scripts/build_security_governance_domain_payload.py scripts/build_observability_domain_payload.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `git diff --check -- scripts/prepare_openshift_render_artifacts.py roles/report_common/tasks/prepare_openshift_render_artifacts.yml roles/report_common/tasks/build_openshift_domain_payload.yml`
- `bash tests/run_ci_report_fixture.sh`
- Fixture result: `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- Output and workspace Markdown reports were byte-identical.
- Output and workspace JSON reports were byte-identical.
- Checkpoint manifest and workspace manifest were byte-identical.
- `reports/.run-state/openshift/collected-artifacts/shared/timing.json` parsed as valid JSON.
- Supportability reference-compliance verdict rendered as `supported`.
- Workspace manifest artifact counts after fixture:
  - completed artifacts: `42`
  - failed artifacts: `0`
  - posture artifacts: `12`
  - capability artifacts: `25`
  - report files: `5`
  - shared JSON artifacts: `3`

Latest collected fixture timing after Phase 7 Slices 111-118:

- `evidence_loading`: 113.10 seconds
- `collected_preparation`: 3.48 seconds
- `common_analysis`: 69.36 seconds
- `openshift_analysis`: 185.68 seconds
- `collected_health_synthesis`: 7.48 seconds
- `posture_artifact_build`: 118.62 seconds
- `capability_artifact_build`: 127.11 seconds
- `shared_artifact_persistence`: 44.62 seconds
- `analysis_and_artifact_build`: 572.35 seconds
- `report_rendering`: 222.99 seconds
- `workflow`: 989.35 seconds

Timing note:

- The run passed all correctness checks, but timing remains noisy and should not be treated as a clean isolated benchmark.
- The render-prep task no longer normalizes full posture artifacts as individual facts, but it still spends time converting the single `openshift_posture_render_slices` map. Further gains likely require moving more render/domain assembly fully into Python helpers or reducing final Jinja Markdown rendering cost.
- The next optimization phase should target the remaining report rendering cost: domain helper bundle runtime, shared payload normalization, and Markdown template rendering.

## Phase 8 Slice 119

Batching note:

- This slice resumes the performance-improvement plan after the findings-first report refactor.
- The slice is validator-only. It adds accuracy guardrails before the next render-performance pass touches more payload and template plumbing.
- No report data, report template, profile gating, collection behavior, or analysis semantics are changed by this slice.

Slice 119 change:

- Extended `scripts/validate_openshift_report_output.py` with focused JSON assertions for high-risk summaries.
- Added count consistency checks for workload health:
  - `unhealthy_user_pod_count` must match the `unhealthy_user_pods` list length.
  - `high_restart_pod_count` must match the `restart_hotspots` list length.
  - `workload_health_issue_count` must match the `workload_health_issues` list length.
- Added a workload false-negative guard: unhealthy user pods or rollout issues must not render behind a non-critical workload status.
- Added count and false-negative checks for node health:
  - `high_pod_density_node_count` must match the `high_pod_density_nodes` list length.
  - not-ready, pressured, or critical-density nodes must not render as a healthy node posture.
- Added capacity false-negative checks:
  - zero allocatable data or partial object-count evidence must not render as a healthy capacity snapshot.
- Added Day 2 false-negative check:
  - top blockers must not render behind a healthy Day 2 readiness status.

Validation:

- `python3 -m py_compile scripts/validate_openshift_report_output.py`
- `python3 scripts/validate_openshift_report_output.py reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`

Validation result:

- Existing collected fixture Markdown validation passed.
- Existing collected fixture JSON validation passed with the new high-risk summary checks active.
- Follow-up cross-check after the findings-first report refactor:
  - `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
  - `python3 -m py_compile scripts/validate_openshift_report_template.py scripts/validate_openshift_report_output.py scripts/prepare_openshift_render_artifacts.py scripts/build_collected_openshift_domain_payload.py scripts/build_openshift_report_payload.py`
  - `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
  - `python3 scripts/validate_openshift_report_output.py reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
  - `bash tests/run_ci_report_fixture.sh`
- Follow-up result: full collected CI fixture passed with `failed=0`; rendered Markdown validation passed; rendered JSON validation passed.
- The run exercised the optimized collected render path, including buffered posture/capability artifact persistence, render-slice preparation, shared domain payload assembly, final report payload assembly, and timing artifact persistence.

Latest collected fixture timing after findings-first cross-check:

- `evidence_loading`: 25.47 seconds
- `collected_preparation`: 0.76 seconds
- `common_analysis`: 17.47 seconds
- `openshift_analysis`: 47.17 seconds
- `collected_health_synthesis`: 2.07 seconds
- `posture_artifact_build`: 33.11 seconds
- `capability_artifact_build`: 26.40 seconds
- `shared_artifact_persistence`: 4.28 seconds
- `analysis_and_artifact_build`: 133.62 seconds
- `report_rendering`: 36.02 seconds
- `workflow`: 206.98 seconds

Timing note:

- This follow-up run confirms the recent findings/report-shape changes did not break the performance-optimized collected fixture path.
- Treat the timing as a validation data point, not a clean benchmark, because prior local fixture timing has been noisy.

Next work:

- Continue with report-rendering performance work now that Phase 8 has a stronger high-risk accuracy guardrail.
- The next practical target remains report rendering cost: domain helper bundle runtime, shared payload normalization, and Markdown template rendering.

## Phase 8 Slices 120-123

Batching note:

- These slices are intentionally batched before the next runtime fixture to increase tuning velocity.
- The batch targets report writer and final render-stage filter overhead only.
- No report findings, posture/capability business logic, profile gating, domain payload helper logic, or template section contract is changed.

Slice 120 change:

- Removed the redundant collected report payload recursive combine in `roles/report_openshift/tasks/render_collected_state_report.yml`.
- `scripts/build_openshift_report_payload.py` already includes the collected supplemental artifact keys that were being re-applied through `openshift_report_payload_mode_extras`, so the render task can use `openshift_report_payload_common` directly.

Slice 121 change:

- Extended `scripts/write_stdin_to_files.py` with `--json-pretty`.
- Collected report JSON writing now sends compact JSON from Ansible and lets Python parse and pretty-print it before writing the output and workspace copies.
- This moves pretty JSON formatting out of Ansible/Jinja while preserving JSON semantics.

Slice 122 change:

- Extended `scripts/write_stdin_to_files.py` with `--normalize-unknown-labels`.
- Collected Markdown writing now renders the template once and lets Python normalize legacy unknown labels before writing report files.
- This moves the full-report regex scan out of Ansible/Jinja.

Slice 123 change:

- Applied the same writer improvements to the shared live render path in `roles/report_common/tasks/render_report_artifacts.yml`.
- Live Markdown writing now uses Python-side unknown-label normalization.
- Live JSON writing now uses Python-side pretty JSON formatting.

Validation:

- `python3 -m py_compile scripts/write_stdin_to_files.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `printf '{"b":2,"a":{"c":3}}' | python3 scripts/write_stdin_to_files.py .runtime/tmp/write-json-test.json --json-pretty`
- `printf 'UNKNOWN Unknown UNKONWN ok' | python3 scripts/write_stdin_to_files.py .runtime/tmp/write-text-test.txt --normalize-unknown-labels`
- `git diff --check -- scripts/write_stdin_to_files.py roles/report_openshift/tasks/render_collected_state_report.yml roles/report_common/tasks/render_report_artifacts.yml`

Validation result:

- Static validation passed.
- Helper smoke tests passed.
- Runtime fixture intentionally deferred until additional adjacent render-stage slices are batched.

Next work:

- Continue inspecting final render-stage tasks for more low-risk Ansible/Jinja filter work that can be moved into existing helpers.
- Before running the next runtime fixture, include an exact rendered Markdown/JSON comparison against the previous fixture output if the previous artifacts are still available.

## Phase 8 Slices 124-127

Batching note:

- These slices continue the report-rendering pass and intentionally defer the runtime fixture.
- The batch targets template startup work and render helper precomputation only.
- No posture or capability scoring logic, profile gating, collection scope, or finding semantics are intentionally changed.

Slice 124 change:

- Extended `scripts/prepare_openshift_render_artifacts.py` to build `openshift_template_graph_render`.
- The helper now precomputes compact Node and MachineConfigPool render lists from the resource graph.
- The helper also precomputes object counts for APIService, Route, Ingress, SecurityContextConstraint, and Secret resources.

Slice 125 change:

- Wired `openshift_template_graph_render` through `roles/report_common/tasks/prepare_openshift_render_artifacts.yml`.
- This keeps the optimization inside the existing render-preparation contract instead of adding another report-family path.

Slice 126 change:

- Updated `templates/openshift_cluster_health_report.md.j2` to consume the precomputed compact Node/MCP lists when available.
- The template keeps the previous graph-scan fallback for compatibility if the helper output is absent.

Slice 127 change:

- Removed unused top-level graph item initializers from the OpenShift Markdown template.
- Replaced route, ingress, APIService, SCC, and secret count fallbacks with precomputed counts where available.
- This avoids creating large unused Jinja lists for build, pipeline, image, compliance, and registry-adjacent resource families during final Markdown rendering.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `python3 -c 'import json, subprocess; data={"shared_dir":"reports/.run-state/openshift/collected-artifacts/shared","postures_dir":"reports/.run-state/openshift/collected-artifacts/postures","capabilities_dir":"reports/.run-state/openshift/collected-artifacts/capabilities"}; p=subprocess.run(["python3","scripts/prepare_openshift_render_artifacts.py"], input=json.dumps(data), text=True, capture_output=True, check=True); payload=json.loads(p.stdout); render=payload.get("openshift_template_graph_render",{}); print(json.dumps({"nodes": len(render.get("nodes", [])), "mcps": len(render.get("machineconfigpools", [])), "routes_count": render.get("routes_count"), "ingresses_count": render.get("ingresses_count"), "apiservices_count": render.get("apiservices_count"), "scc_count": render.get("securitycontextconstraints_count"), "secrets_count": render.get("secrets_count")}, sort_keys=True))'`
- `git diff --check -- scripts/prepare_openshift_render_artifacts.py roles/report_common/tasks/prepare_openshift_render_artifacts.yml templates/openshift_cluster_health_report.md.j2`

Validation result:

- Static validation passed.
- Helper smoke test completed and returned the expected graph-render summary shape.
- Runtime fixture intentionally deferred until the next batch or until an equivalence check can be run against preserved pre-change artifacts.

Next work:

- Continue reducing final Markdown rendering cost by precomputing any remaining high-cost summary lists that are still built directly in Jinja.
- Add a pre-fixture report comparison step if previous report artifacts are preserved, then run the collected fixture to measure `report_rendering` after Slices 120-127.

## Phase 8 Slices 128-131

Batching note:

- These slices continue batching render-stage changes before the next runtime fixture.
- The batch targets Node and MachineConfigPool inventory table rendering only.
- The report facts, posture findings, capability findings, scoring rules, and profile gating are unchanged.

Slice 128 change:

- Extended `scripts/prepare_openshift_render_artifacts.py` with Node display-row fields:
  - node name
  - role list
  - Ready condition value
  - Ready badge status
  - pressure condition list
  - kubelet version
  - OS image
- The helper preserves the original compact `metadata` and `status` fields for compatibility.

Slice 129 change:

- Extended `scripts/prepare_openshift_render_artifacts.py` with MachineConfigPool display-row fields:
  - MCP name
  - Updated, Updating, and Degraded condition values
  - badge status for each condition
  - machine, ready-machine, and updated-machine counts
- The helper preserves the original compact `metadata` and `status` fields for compatibility.

Slice 130 change:

- Updated the Node inventory table in `templates/openshift_cluster_health_report.md.j2` to consume pre-shaped Node display fields when present.
- The previous Jinja `selectattr`, `map`, role extraction, and pressure extraction remain available only as fallback logic.

Slice 131 change:

- Updated the MachineConfigPool inventory table in `templates/openshift_cluster_health_report.md.j2` to consume pre-shaped MCP display fields when present.
- The previous Jinja condition extraction remains available only as fallback logic.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Helper smoke test with synthetic Node and MCP graph input confirmed the expected display fields:
  - `node.roles=worker`
  - `node.ready_badge_status=OK`
  - `node.pressures=MemoryPressure`
  - `mcp.updated_badge_status=OK`
  - `mcp.updating_badge_status=OK`
  - `mcp.degraded_badge_status=OK`

Validation result:

- Static validation passed.
- Helper smoke test passed.
- Runtime fixture intentionally deferred so the render-stage changes can continue to be batched before measurement.

Next work:

- Inspect remaining high-cost template summary fragments for low-risk precomputation.
- If no equally safe render slices remain, run the collected fixture and compare `report_rendering` timing after Slices 120-131.

## Phase 8 Slices 132-135

Batching note:

- These slices continue the final render-stage batching before the next runtime fixture.
- The changes are limited to template fast paths and dead template setup removal.
- No report findings, scoring rules, collection behavior, or rendered section gating are intentionally changed.

Slice 132 change:

- Split the Node inventory table into a fast path and compatibility fallback.
- When helper-shaped Node rows are present, the template renders the precomputed row fields directly.
- The older `selectattr`, `dict2items`, role extraction, and pressure extraction logic remains only for non-helper-shaped fallback data.

Slice 133 change:

- Split the MachineConfigPool inventory table into a fast path and compatibility fallback.
- When helper-shaped MCP rows are present, the template renders precomputed condition badge statuses and machine counts directly.
- The older condition extraction logic remains only for non-helper-shaped fallback data.

Slice 134 change:

- Removed unused `enabled_posture_items` and `enabled_capability_items` top-level template setup.
- Profile gating still uses `posture_profile` and `capability_profile` directly, so rendered section behavior is unchanged.

Slice 135 change:

- Removed unused `optional_access_denied_count` top-level template setup.
- Collection skip details continue to render from the existing collection summary variables where used.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `rg -n "enabled_posture_items|enabled_capability_items|optional_access_denied_count" templates/openshift_cluster_health_report.md.j2`
- Helper smoke test confirmed pre-shaped Node and MCP rows still include the expected badge fields.
- `git diff --check -- templates/openshift_cluster_health_report.md.j2 scripts/prepare_openshift_render_artifacts.py docs/performance-improvement-progress.md`

Validation result:

- Static validation passed.
- Removed variables are no longer referenced in the template.
- Helper smoke test passed.
- Runtime fixture intentionally deferred for the current batching cycle.

Next work:

- The next meaningful step is likely a collected runtime fixture with rendered report validation and timing comparison for Slices 120-135.
- If one more pre-fixture batch is desired, target only mechanical sorted-table precomputation for small count maps; avoid moving Findings Summary wording until after a runtime checkpoint.

## Phase 8 Slice 136

Batching note:

- This slice is a report-content quality correction discovered during the Phase 8 runtime fixture review.
- The change is intentionally limited to rendered Findings table wording and does not change collection, scoring, section gating, posture/capability inclusion, or evidence mapping.

Slice 136 change:

- Expanded terse OK-row technical evidence in the Security and Governance and Platform Architecture and Lifecycle Findings tables so rows such as privileged access and conditional update risk explain what the reported zero count means.
- Strengthened generic capability Finding and check remediation fallbacks so non-clean capability rows point the reader to the expected outcome, missing control, missing evidence, and rerun confirmation step instead of falling back to raw evidence strings.
- Confirmed the prior raw evidence issue remains limited to Technical Evidence where it belongs; Action Plan no longer emits strings such as raw readiness key/value output.

Validation:

- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.

Validation result:

- Template validation passed.
- OpenShift playbook syntax check passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.

Latest fixture timing:

- `evidence_loading`: `26.43s`
- `common_analysis`: `17.62s`
- `openshift_analysis`: `46.76s`
- `posture_artifact_build`: `40.93s`
- `capability_artifact_build`: `45.34s`
- `shared_artifact_persistence`: `8.61s`
- `analysis_and_artifact_build`: `165.49s`
- `report_rendering`: `73.71s`
- `workflow`: `286.24s`

Next work:

- Continue Phase 8 only with changes that preserve Findings table accuracy and section-contract consistency.
- The highest remaining render-stage cost in this fixture is still report payload/domain assembly and Markdown rendering, so the next safe target is mechanical precomputation of additional display-only tables rather than changing finding semantics.

## Phase 8 Slice 137

Batching note:

- This slice continues render-stage optimization with display-only table rows.
- The change deliberately avoids Findings generation, severity logic, health score logic, collection behavior, section gating, or evidence mapping.
- Template fallbacks remain in place so live, collected, and resume paths can still render from the original dictionaries if precomputed rows are absent.

Slice 137 change:

- Added `openshift_template_table_render` to `scripts/prepare_openshift_render_artifacts.py`.
- Precomputed sorted row lists for:
  - control-plane query errors
  - firing alert severity counts
  - PV phase counts
  - PVC phase counts
  - pod security issue type counts with human-readable labels
  - compliance result counts
  - workload probe issue type counts
  - BuildConfig strategy counts
  - PipelineRun status counts
- Wired `openshift_template_table_render` through `roles/report_common/tasks/prepare_openshift_render_artifacts.yml`.
- Updated `templates/openshift_cluster_health_report.md.j2` to use the precomputed row lists with fallback to the previous Jinja `dict2items` and sorting behavior.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Helper smoke test against explicit count-map input confirmed all new row sets populate.
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.
- `git diff --check -- scripts/prepare_openshift_render_artifacts.py roles/report_common/tasks/prepare_openshift_render_artifacts.yml templates/openshift_cluster_health_report.md.j2`

Validation result:

- Static validation passed.
- Helper smoke test passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- Rendered summary tables were spot-checked for pod security, probe coverage, PV phases, and PVC phases.

Latest fixture timing:

- `evidence_loading`: `25.54s`
- `common_analysis`: `17.3s`
- `openshift_analysis`: `150.69s`
- `collected_health_synthesis`: `12.73s`
- `posture_artifact_build`: `151.59s`
- `capability_artifact_build`: `45.34s`
- `shared_artifact_persistence`: `6.41s`
- `analysis_and_artifact_build`: `391.11s`
- `report_rendering`: `57.92s`
- `workflow`: `490.62s`

Timing note:

- `report_rendering` improved from the prior Slice 136 checkpoint of `73.71s` to `57.92s`.
- Total workflow time was slower in this fixture because upstream `openshift_analysis` and `posture_artifact_build` varied materially; those stages are outside the Slice 137 render-table change.

Next work:

- Continue Phase 8 with additional low-risk display-table precomputation only if the template still contains costly sort/filter loops on non-Findings content.
- The next larger improvement target is not more Findings wording; it is reducing repeated domain/payload assembly and large Markdown render inputs while preserving report accuracy.

## Phase 8 Slices 138-142 Combined Batch

Batching note:

- The remaining Phase 8 slices were completed in one batch per request.
- The changes are limited to display-only render precomputation and template consumption fallbacks.
- Findings generation, severity logic, health score logic, collection behavior, section gating, posture/capability inclusion, and evidence mapping were not changed.

Slices completed:

- Slice 138: precomputed node-density, storageclass, aged user pod, pod usage, available update, conditional update, and update history display rows.
- Slice 139: precomputed capacity current-state display strings and sanity booleans for node platform summary rendering.
- Slice 140: consolidated render-only table inputs and display limits through the render artifact helper.
- Slice 141: ran one collected CI fixture to validate the combined batch end to end.
- Slice 142: scanned the rendered report for Findings table consistency and checked the changed diff for whitespace issues.

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- Helper smoke test against explicit render artifact input confirmed the new display-row sets populate.
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.
- Spot-check for rendered node density, storage, pod usage, update history, and node platform summary sections.
- `git diff --check -- scripts/prepare_openshift_render_artifacts.py roles/report_common/tasks/prepare_openshift_render_artifacts.yml templates/openshift_cluster_health_report.md.j2 docs/performance-improvement-progress.md`

Validation result:

- Static validation passed.
- Helper smoke test passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- Diff whitespace check passed.

Latest fixture timing:

- `evidence_loading`: `57.06s`
- `common_analysis`: `41.44s`
- `openshift_analysis`: `103.75s`
- `posture_artifact_build`: `70.17s`
- `capability_artifact_build`: `60.87s`
- `shared_artifact_persistence`: `33.54s`
- `analysis_and_artifact_build`: `325.7s`
- `report_rendering`: `208.78s`
- `workflow`: `658.66s`

Timing note:

- Correctness passed, but `report_rendering` was slower in this fixture than the Slice 137 checkpoint.
- The slow portion is now dominated by shared domain/payload assembly and final Markdown rendering around the collected report path, not the display-row helper itself.
- The next optimization phase should reduce repeated domain/payload assembly and large render payload size while preserving the current report contract and Findings accuracy.

## Phase 9 Slice 143

Scope:

- Targeted the collected-state report render path after Phase 8 showed `report_rendering` dominated by shared domain/payload assembly and Markdown rendering.
- Kept Findings table wording, severity logic, score logic, profile gating, collection behavior, and evidence mapping unchanged.

Change:

- Added `scripts/build_collected_openshift_domain_payload_fast.py`.
- The helper imports the existing domain helper modules and the existing collected-domain reducer instead of duplicating Findings or evidence logic.
- Collected mode now skips the intermediate OpenShift domain helper bundle and reads persisted posture artifacts from `report_run_workspace_postures_dir`.
- The collected domain command now sends only the posture artifact directory plus the few release-engineering lists/counts that are not currently represented by a dedicated posture artifact.

Correctness checks:

- `python3 -m py_compile scripts/build_collected_openshift_domain_payload_fast.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- A helper equivalence check confirmed the file-path fast helper produced the same `domains` payload as the prior rendered fixture payload.
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.
- `git diff --check -- scripts/build_collected_openshift_domain_payload_fast.py roles/report_common/tasks/build_openshift_domain_payload.yml docs/performance-improvement-progress.md`

Validation result:

- Static validation passed.
- Domain payload equivalence check passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- Diff whitespace check passed.

Latest fixture timing:

- `evidence_loading`: `221.7s`
- `common_analysis`: `81.46s`
- `openshift_analysis`: `103.76s`
- `posture_artifact_build`: `60.22s`
- `capability_artifact_build`: `46.44s`
- `shared_artifact_persistence`: `7.36s`
- `analysis_and_artifact_build`: `315.3s`
- `report_rendering`: `47.25s`
- `workflow`: `628.14s`

Timing note:

- `report_rendering` improved from the prior Phase 8 checkpoint of `208.78s` to `47.25s`.
- Total workflow time was still high in this fixture because `evidence_loading` was unusually slow at `221.7s`; that is outside the render-path change.
- The next performance target should be evidence loading and early collected-resource parsing, not Findings content or final Markdown rendering.

## Phase 10 Slice 144

Scope:

- Targeted collected optional-evidence loading, which was the largest remaining measured stage after Phase 9.
- Preserved the existing parser scripts as the source of truth for evidence interpretation.
- Kept Findings wording, severity logic, health score logic, profile gating, report rendering, collection behavior, and evidence mapping rules unchanged.

Change:

- Added `scripts/parse_optional_evidence_bundle.py`.
- Replaced the repeated optional-evidence parse/register/merge task sequence in `roles/load_evidence_common/tasks/optional_evidence.yml` with one helper command and one merge task.
- The bundle helper delegates to the existing optional evidence parsers:
  - `parse_cluster_compare.py`
  - `parse_inspect.py`
  - `parse_managed_gates.py`
  - `parse_sosreport.py`
  - `parse_advisor_export.py`
  - `parse_insights_archive.py`
- The helper preserves the previous fail-fast behavior when an enabled optional parser returns a non-zero exit code.

Correctness checks:

- `python3 -m py_compile scripts/parse_optional_evidence_bundle.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Evidence summary spot-check confirmed expected optional labels and hybrid mode.
- Findings table content scan across all rendered Findings tables.
- `git diff --check -- roles/load_evidence_common/tasks/optional_evidence.yml scripts/parse_optional_evidence_bundle.py scripts/build_collected_openshift_domain_payload_fast.py roles/report_common/tasks/build_openshift_domain_payload.yml docs/performance-improvement-progress.md`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Evidence summary retained expected labels: `must-gather`, `cluster-compare`, `inspect`, `managed-gates`, `advisor-export`, `insights-archive`, and `sosreport`.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- Diff whitespace check passed.

Latest fixture timing:

- `evidence_loading`: `21.75s`
- `common_analysis`: `17.59s`
- `openshift_analysis`: `47.14s`
- `posture_artifact_build`: `33.41s`
- `capability_artifact_build`: `26.85s`
- `shared_artifact_persistence`: `5.18s`
- `analysis_and_artifact_build`: `135.64s`
- `report_rendering`: `25.31s`
- `workflow`: `194.65s`

Timing note:

- `evidence_loading` improved from the previous Phase 9 checkpoint of `221.7s` to `21.75s` on the latest fixture run.
- The fixture used the existing collected-resource extractor cache, so the next uncached run should still be reviewed before treating this as the full cold-run gain.
- The next performance target is broad Ansible orchestration overhead in the analysis and artifact build path, especially repeated small `set_fact` and loop-heavy posture/capability builder tasks.

## Phase 10 Slice 145

Scope:

- Ran a cold collected fixture after clearing the repo-local collected-resource extractor cache.
- This validates that the Slice 144 evidence-loading improvement is not only a cached-run artifact.

Validation:

- Cleared `.runtime/tmp/ohc-collected-resource-cache-*.json`.
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Evidence summary spot-check confirmed expected optional labels and hybrid mode.
- Findings table content scan across all rendered Findings tables.

Validation result:

- Cold collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Evidence summary retained expected labels: `must-gather`, `cluster-compare`, `inspect`, `managed-gates`, `advisor-export`, `insights-archive`, and `sosreport`.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.

Cold fixture timing:

- `evidence_loading`: `23.71s`
- `common_analysis`: `17.41s`
- `openshift_analysis`: `46.77s`
- `posture_artifact_build`: `33.0s`
- `capability_artifact_build`: `25.86s`
- `shared_artifact_persistence`: `4.12s`
- `analysis_and_artifact_build`: `132.41s`
- `report_rendering`: `24.68s`
- `workflow`: `192.78s`

Timing note:

- The cold run confirms the collected-resource extractor cache is not hiding a major remaining evidence-loading cost in the fixture path.
- `analysis_and_artifact_build` is now the main remaining target and should be optimized by reducing Ansible task orchestration around repeated analysis/build normalization while preserving the current helper-backed evidence and Findings semantics.

## Phase 10 Slice 146

Scope:

- Reduced repeated capability-section list scans in enabled capability and security posture builders.
- Replaced repeated `selectattr('key', 'equalto', ...) | list | first` lookups with the existing precomputed `day2_capability_sections_by_key` map.
- Kept the existing role-local builder ownership model; no shared business logic was re-centralized.

Files updated:

- `roles/capability_declarative_gitops_operations/tasks/builder.yml`
- `roles/capability_cluster_log_forwarding/tasks/builder.yml`
- `roles/capability_user_workload_metrics_monitoring/tasks/builder.yml`
- `roles/capability_persistent_monitoring_storage/tasks/builder.yml`
- `roles/capability_cluster_network_observability/tasks/builder.yml`
- `roles/capability_custom_ca_trust_bundle/tasks/builder.yml`
- `roles/capability_ovn_ipsec_encryption/tasks/builder.yml`
- `roles/capability_image_registry_policy_governance/tasks/builder.yml`
- `roles/capability_workload_vulnerability_scanning/tasks/builder.yml`
- `roles/posture_security_and_governance/tasks/builder.yml`

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check` for the changed builders and this progress file.

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- JSON comparison confirmed `domains`, `findings`, and `health_summary` were unchanged. Only run metadata differed: generated timestamps and checkpoint workspace paths.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `70.87s`
- `common_analysis`: `71.66s`
- `openshift_analysis`: `108.46s`
- `posture_artifact_build`: `51.76s`
- `capability_artifact_build`: `41.14s`
- `shared_artifact_persistence`: `7.43s`
- `analysis_and_artifact_build`: `292.05s`
- `report_rendering`: `43.91s`
- `workflow`: `428.96s`

Timing note:

- This fixture run was substantially slower across stages that were not touched by this slice, so the timing is not a clean performance signal.
- The correctness signal is clean: report findings and health summary stayed identical while the builder path now uses map lookups instead of repeated list filtering.
- The next useful target remains Ansible orchestration overhead in analysis and artifact build, with priority on repeated task-level normalization that can be safely moved into helper-backed, schema-preserving transforms.

## Phase 10 Slice 147

Scope:

- Completed the remaining safe Day 2 capability section lookup replacements across capability builders.
- Replaced the remaining `day2_capability_sections | selectattr('key', 'equalto', ...) | list | first` section-current lookups with `day2_capability_sections_by_key.get(...)`.
- Kept each capability builder role-local; this slice only changes lookup mechanics, not finding synthesis or report semantics.

Validation:

- Verified no remaining `section_current` assignments use the repeated `day2_capability_sections` list-scan pattern.
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check` for changed capability builders and this progress file.

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- JSON comparison confirmed `domains`, `findings`, and `health_summary` were unchanged. Only run metadata differed: generated timestamps and checkpoint workspace paths.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `71.94s`
- `common_analysis`: `45.83s`
- `openshift_analysis`: `116.88s`
- `posture_artifact_build`: `69.53s`
- `capability_artifact_build`: `54.52s`
- `shared_artifact_persistence`: `12.81s`
- `analysis_and_artifact_build`: `311.85s`
- `report_rendering`: `162.53s`
- `workflow`: `595.81s`

Timing note:

- This run was slower in broad, unrelated stages and is not a clean measurement of the map-lookup change.
- The useful outcome is correctness plus removal of the remaining repeated list-scan lookup pattern in capability builders.
- The next target should shift away from micro lookup cleanup and into larger helper-backed analysis transforms, especially common workload/security normalization and report rendering payload assembly.

## Phase 10 Slice 148

Scope:

- Optimized collected-state report payload handling in the rendering path.
- Extended `scripts/build_openshift_report_payload.py` so the collected path can:
  - write the full pretty JSON payload directly to all report JSON destinations
  - return a smaller render-sized payload to Ansible for Markdown rendering
- Skipped the old collected JSON write task when the helper already wrote the full JSON artifacts.
- Preserved the existing report contract: the persisted JSON still includes supplemental artifacts and top-level support artifact aliases.

Files updated:

- `scripts/build_openshift_report_payload.py`
- `roles/report_common/tasks/build_openshift_report_payload.yml`
- `roles/report_openshift/tasks/render_collected_state_report.yml`

Validation:

- `python3 -m py_compile scripts/build_openshift_report_payload.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across all rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check` for changed files and this progress file.

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- The old `Write collected-state JSON report artifacts` task skipped because the helper pre-wrote the JSON artifacts.
- Content scan found `37` Findings tables and no weak Findings table cells or raw-evidence Action Plan values.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged. Only run metadata differed: generated timestamps and checkpoint workspace paths.
- Persisted JSON still contains `supplemental_artifacts` and top-level artifact aliases for `cluster_compare`, `inspect`, `sosreport`, `advisor_export`, `insights_archive`, and `managed_gates`.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `53.11s`
- `common_analysis`: `41.78s`
- `openshift_analysis`: `102.9s`
- `posture_artifact_build`: `73.32s`
- `capability_artifact_build`: `52.98s`
- `shared_artifact_persistence`: `10.66s`
- `analysis_and_artifact_build`: `292.99s`
- `report_rendering`: `52.76s`
- `workflow`: `425.47s`

Timing note:

- `report_rendering` improved materially compared with the prior noisy run (`162.53s` to `52.76s`) while preserving report content and full JSON artifacts.
- Some unrelated analysis/artifact stages remain noisy and still dominate the run. The next useful target is common analysis normalization, especially workload and security task chains that repeatedly build, normalize, and apply related facts across multiple Ansible tasks.

## Phase 11 Batch A

Scope:

- Batched common workload analysis helper execution.
- Added a bundled workload analysis helper that computes workload health, multi-replica resilience, and probe coverage findings in one helper invocation.
- Added a bundled workload governance helper that computes workload governance facts and node label governance findings in one helper invocation.
- Preserved existing filtering and finding semantics:
  - operator-managed namespace detection remains the prerequisite step
  - deploymentconfig behavior in workload health remained unchanged
  - probe coverage still skips the standalone probe helper when the bundle already populated probe findings

Files updated:

- `scripts/build_common_workload_analysis_bundle.py`
- `scripts/build_common_workload_governance_bundle.py`
- `scripts/build_workload_resilience.py`
- `scripts/build_node_label_governance_findings.py`
- `roles/analyze_common/tasks/workload.yml`
- `roles/analyze_common/tasks/workload/health_and_resilience.yml`
- `roles/analyze_common/tasks/workload/governance.yml`

Validation:

- `python3 -m py_compile scripts/build_workload_resilience.py scripts/build_common_workload_analysis_bundle.py scripts/build_workload_probe_findings.py scripts/build_workload_health_findings.py scripts/build_node_label_governance_findings.py scripts/build_common_workload_governance_bundle.py scripts/build_workload_governance_facts.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found no weak Findings table rows.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, `workload_health`, and `security_and_governance` were unchanged.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `77.18s`
- `common_analysis`: `52.89s`
- `openshift_analysis`: `173.98s`
- `posture_artifact_build`: `120.5s`
- `capability_artifact_build`: `95.56s`
- `shared_artifact_persistence`: `18.53s`
- `analysis_and_artifact_build`: `499.03s`
- `report_rendering`: `89.59s`
- `workflow`: `709.97s`

Timing note:

- This fixture was slower overall than the previous checkpoint, so it should not be used as a clean speed comparison.
- The useful outcome is task-count reduction and behavior-equivalent report content for the common workload path.
- The next batch should target another high-cardinality analysis chain or artifact/render orchestration hotspot, with direct report JSON comparison as the accuracy guardrail.

## Phase 11 Batch B

Scope:

- Batched common storage/TLS analysis helper execution.
- Added a bundled storage/TLS helper that computes:
  - storage class summaries
  - PV and PVC phase summaries and issue lists
  - TLS secret expiry targets
  - storage posture summary
- Preserved the external `openssl` certificate expiry probe as a separate task boundary so certificate parsing behavior and timeout handling stayed unchanged.

Files updated:

- `scripts/build_common_storage_tls_bundle.py`
- `scripts/build_storage_tls_facts.py`
- `scripts/build_storage_posture_summary.py`
- `roles/analyze_common/tasks/security/storage_and_tls.yml`

Validation:

- `python3 -m py_compile scripts/build_common_storage_tls_bundle.py scripts/build_storage_tls_facts.py scripts/build_storage_posture_summary.py scripts/batch_tls_secret_expiry.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Content scan found no weak Findings table rows.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, `security_and_governance`, `backup_and_disaster_recovery`, and `workload_health` were unchanged.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `64.92s`
- `common_analysis`: `38.9s`
- `openshift_analysis`: `148.31s`
- `posture_artifact_build`: `96.73s`
- `capability_artifact_build`: `76.39s`
- `shared_artifact_persistence`: `16.62s`
- `analysis_and_artifact_build`: `394.69s`
- `report_rendering`: `90.33s`
- `workflow`: `594.43s`

Timing note:

- `common_analysis` improved from the previous fixture's `52.89s` to `38.9s` while preserving report content.
- The next batch should move to the next measured hotspot in order: OpenShift analysis loops or artifact/render orchestration. A good low-risk candidate is replacing the loop-heavy node debug target synthesis with a helper because it currently performs several small Ansible loops and only affects optional node-debug target selection metadata.

## Phase 11 Batch C

Scope:

- Replaced loop-heavy OpenShift node-debug target synthesis with a helper-backed transform.
- Preserved the downstream fact contract:
  - `node_debug_target_candidates`
  - `node_debug_target_nodes`
  - `node_debug_target_reason_map`
- Preserved candidate source order and reason de-duplication semantics.
- This affects optional live node-debug/sosreport target metadata, not primary report findings.

Files updated:

- `scripts/build_node_debug_targets.py`
- `roles/analyze_openshift/tasks/node_debug_targets.yml`

Validation:

- `python3 -m py_compile scripts/build_node_debug_targets.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged.
- Weak-row scan found no weak Findings table rows.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `72.1s`
- `common_analysis`: `47.15s`
- `openshift_analysis`: `149.44s`
- `posture_artifact_build`: `113.64s`
- `capability_artifact_build`: `80.39s`
- `shared_artifact_persistence`: `13.6s`
- `analysis_and_artifact_build`: `423.22s`
- `report_rendering`: `72.61s`
- `workflow`: `601.89s`

Timing note:

- This is a targeted task-count and loop reduction, so it is not expected to materially change collected-mode report content.
- Report rendering improved compared with Batch B in this fixture, but the Batch C change itself is isolated to node-debug target synthesis; treat the timing as directional rather than a clean causal measurement.
- The next batch should target the next measured hotspot: posture/capability artifact builder loops or report rendering preparation.

## Phase 11 Batch D

Scope:

- Moved Day 2 capability-section filtering and capability posture summary counts out of the Markdown template and into the existing OpenShift render-preparation helper.
- Preserved the template fallback path when precomputed Day 2 render data is absent.
- Preserved profile-gated capability rendering semantics: only enabled capabilities are included in the rendered Day 2 capability section list and summary counts.
- This is a render-time precompute only; it does not change Day 2 analysis, capability findings, or posture scoring.

Files updated:

- `scripts/prepare_openshift_render_artifacts.py`
- `templates/openshift_cluster_health_report.md.j2`

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged.
- Weak-row scan found no weak Findings table rows.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `80.47s`
- `common_analysis`: `55.62s`
- `openshift_analysis`: `191.6s`
- `posture_artifact_build`: `114.1s`
- `capability_artifact_build`: `100.87s`
- `shared_artifact_persistence`: `17.16s`
- `analysis_and_artifact_build`: `500.02s`
- `report_rendering`: `83.58s`
- `workflow`: `708.11s`

Timing note:

- This fixture was slower than Batch C across unrelated stages, so it should not be used as a clean speed comparison.
- The useful outcome is removal of another template loop/counting block while preserving rendered report content exactly.
- The next batch should target a measured artifact-builder or render-preparation hotspot with larger expected payoff than small template-loop precomputes.

## Phase 11 Batch E

Scope:

- Reduced collected render-preparation helper output size by returning compact shared collection and analysis-graph artifacts instead of the full collected resource graph.
- Preserved the helper's internal use of the full graph for compact render tables, support tables, and domain inputs.
- Preserved the downstream shared-artifact fact names used by domain and report payload builders.
- This is a controller-side serialization/normalization reduction only; it does not change analysis, findings, scoring, or report section content.

Files updated:

- `scripts/prepare_openshift_render_artifacts.py`

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged.
- Weak-row scan found no weak Findings table rows.
- Diff whitespace check passed.

Fixture timing:

- `evidence_loading`: `86.85s`
- `common_analysis`: `52.2s`
- `openshift_analysis`: `173.1s`
- `posture_artifact_build`: `125.51s`
- `capability_artifact_build`: `107.24s`
- `shared_artifact_persistence`: `22.62s`
- `analysis_and_artifact_build`: `502.25s`
- `report_rendering`: `125.16s`
- `workflow`: `766.41s`

Timing note:

- This fixture was slower overall and does not show a measurable render-stage improvement. The report content remained identical, so the change is safe, but it is not a proven runtime win in this fixture.
- The next batch should avoid more small render-prep output shaping and instead target a clearer repeated-cost source: artifact-builder orchestration or shared artifact persistence.

## Phase 11 Batch F

Scope:

- Inlined the default buffered posture/capability artifact payload construction into the shared artifact-from-builder roles.
- Kept immediate artifact persistence mode available through the existing immediate writer include.
- Preserved the generated posture and capability artifact JSON contract:
  - artifact metadata
  - selector/request scope
  - dependency and shared-input metadata
  - analysis summary
  - findings
  - render inputs
  - collection inputs
- This targets artifact-builder orchestration overhead and does not change posture/capability business logic.

Files updated:

- `roles/posture_artifact_from_builder/tasks/main.yml`
- `roles/capability_artifact_from_builder/tasks/main.yml`

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged.
- Weak-row scan found no weak Findings table rows.
- Diff whitespace check passed.
- Task count dropped from `1153` known tasks in the prior fixture to `1116` known tasks.

Fixture timing:

- `evidence_loading`: `88.14s`
- `common_analysis`: `56.89s`
- `openshift_analysis`: `460.43s`
- `posture_artifact_build`: `372.8s`
- `capability_artifact_build`: `127.04s`
- `shared_artifact_persistence`: `17.55s`
- `analysis_and_artifact_build`: `1078.71s`
- `report_rendering`: `96.72s`
- `workflow`: `1312.23s`

Timing note:

- The fixture runtime was much slower across unrelated analysis stages and should not be used as a clean speed comparison.
- The reliable win is task-count reduction: the default collected fixture now executes 37 fewer known tasks while preserving report output exactly.
- The next batch should remove the remaining default-path skipped immediate-writer tasks from the artifact-from-builder roles; those skips are now visible overhead after inlining the buffered path.

## Phase 11 Batch G

Scope:

- Removed the remaining default-path skipped immediate-writer include from the shared posture and capability artifact-from-builder roles.
- Routed posture/capability artifact entrypoints to the lean buffered task path by default.
- Preserved immediate artifact persistence mode through explicit `immediate.yml` task files selected when `report_artifact_persistence_mode` is not `buffered`.
- Preserved the generated posture and capability artifact JSON contract and kept posture/capability business logic inside each owning role.

Files updated:

- `roles/posture_artifact_from_builder/tasks/main.yml`
- `roles/posture_artifact_from_builder/tasks/immediate.yml`
- `roles/capability_artifact_from_builder/tasks/main.yml`
- `roles/capability_artifact_from_builder/tasks/immediate.yml`
- all posture and capability role `tasks/main.yml` entrypoints that include the shared artifact-from-builder role

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml -e report_artifact_persistence_mode=immediate`
- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed for both buffered and explicit immediate artifact modes.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged.
- Weak-row scan found no weak Findings table rows.
- Diff whitespace check passed.
- Task count dropped from `1116` known tasks in Batch F to `1079` known tasks in this fixture.

Fixture timing:

- `evidence_loading`: `89.81s`
- `collected_preparation`: `5.96s`
- `common_analysis`: `71.25s`
- `openshift_analysis`: `222.34s`
- `collected_health_synthesis`: `10.08s`
- `posture_artifact_build`: `134.67s`
- `capability_artifact_build`: `97.49s`
- `shared_artifact_persistence`: `17.51s`
- `analysis_and_artifact_build`: `571.29s`
- `report_rendering`: `83.82s`
- `workflow`: `796.57s`

Timing note:

- This fixture was still slower than the fast Phase 2 baseline across unrelated analysis and rendering stages, so treat the duration as validation timing rather than clean proof of runtime improvement.
- The reliable win is another task-count reduction while preserving rendered report content exactly.
- The next batch should target the remaining high-cost controller-side work now visible in the fixture: render artifact normalization, checkpoint snapshot writes, or large analysis `set_fact` operations that still serialize broad data structures.

## Phase 11 Batches H-I-J

Scope:

- Combined the next three Phase 11 cleanup batches to increase tuning velocity.
- Replaced large render-preparation stdout parsing and follow-up `set_fact` normalization with a repo-local render facts artifact:
  - `reports/.run-state/openshift/<mode>-artifacts/report/render-artifacts.json`
  - loaded with `include_vars` as the report render facts source.
- Kept render-preparation logic in `scripts/prepare_openshift_render_artifacts.py`; the helper now writes to `output_path` when provided and falls back to stdout for compatibility.
- Reduced collected analysis checkpoint payloads after artifact persistence by removing the full `collected_resource_graph` and `live_support_data` from report-stage resume snapshots.
- Preserved full live collection checkpoint payloads because live analysis resume still needs collection state when resuming from the collection stage.
- This targets render normalization, checkpoint write size, and broad controller-side serialization without changing analysis or report findings.

Files updated:

- `scripts/prepare_openshift_render_artifacts.py`
- `roles/report_common/tasks/prepare_openshift_render_artifacts.yml`
- `playbooks/openshift_cluster_health_report.yml`

Validation:

- `python3 -m py_compile scripts/prepare_openshift_render_artifacts.py`
- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `bash tests/run_ci_report_fixture.sh`
- Rendered report validator from the fixture:
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md`
  - `reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json`
- Findings table content scan across rendered Findings tables.
- JSON content comparison against the pre-change fixture baseline.
- `git diff --check`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- JSON comparison confirmed `domains`, `findings`, `health_summary`, and `supportability` were unchanged.
- Weak-row scan found no weak Findings table rows.
- Diff whitespace check passed.
- Task count stayed at `1079` known tasks; this batch targeted serialization cost rather than task count.
- Collected analysis checkpoint snapshot is now compact: `reports/.run-state/openshift/collected-analysis.json` was `68K` in the fixture.
- Render facts artifact was written under the report workspace: `reports/.run-state/openshift/collected-artifacts/report/render-artifacts.json`.

Fixture timing:

- `evidence_loading`: `44.67s`
- `collected_preparation`: `1.1s`
- `common_analysis`: `20.07s`
- `openshift_analysis`: `54.99s`
- `collected_health_synthesis`: `1.94s`
- `posture_artifact_build`: `28.97s`
- `capability_artifact_build`: `20.54s`
- `shared_artifact_persistence`: `3.81s`
- `analysis_and_artifact_build`: `134.15s`
- `report_rendering`: `13.06s`
- `workflow`: `209.11s`

Timing note:

- This was the first clean fast fixture after the prior noisy Batch F/G runs.
- The main measurable improvement is in report rendering: Batch G render time was `83.82s`; this run was `13.06s`.
- Checkpoint snapshot writing also became visibly cheaper during the run because the collected report-stage checkpoint no longer embeds the full collected graph after the artifact workspace already has the canonical shared artifacts.

Next work:

- Phase 11 can be considered functionally complete unless live-cluster testing exposes another bottleneck.
- The next step should be a live-cluster run with the current defaults and timings enabled.
- If live runtime is still high, use the timing artifact to choose the next phase; likely candidates are live collection latency, optional support evidence collection, or remaining large analysis helpers that are only expensive with real large-cluster evidence.

## Phase 2 Live Performance Profiles

Scope:

- Resumed the plan after the Phase 11 fixture passed.
- Added a live-only `report_performance_profile` default and profile settings in `group_vars/all.yml`.
- Added OpenShift playbook validation for allowed profiles.
- Added early profile resolution before live API preflight and support collection planning.
- Kept collected-mode behavior unchanged.
- Kept `extra_vars` as the highest-precedence override path for explicit live collector choices.

Profile behavior:

- `fast`: required API evidence only, optional support collectors disabled, PDF disabled.
- `standard`: default live path; API evidence plus lower-cost `inspect` and Insights archive, with `must-gather`, `cluster-compare`, `sosreport`, provider gates, Advisor export, and PDF disabled unless explicitly requested.
- `full`: deep support path; preserves the prior broad live collector defaults and PDF generation when prerequisites are available.

Accuracy guardrails:

- Optional support evidence is still represented through collector capability status rather than silently converted to healthy findings.
- Disabling node diagnostics through the profile still respects the existing `collect_live_sosreport=false` contract.
- Selector-scoped reduction remains in place after profile resolution and can further reduce optional support evidence for narrow runs.

Files updated:

- `group_vars/all.yml`
- `playbooks/openshift_cluster_health_report.yml`
- `README.md`

Validation status:

- Passed.

Validation:

- `ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml`
- `python3 scripts/validate_openshift_report_template.py templates/openshift_cluster_health_report.md.j2`
- `git diff --check -- group_vars/all.yml playbooks/openshift_cluster_health_report.yml README.md docs/performance-improvement-progress.md`
- `bash tests/run_ci_report_fixture.sh`

Validation result:

- Static validation passed.
- Collected CI fixture passed with `failed=0`.
- Rendered Markdown and JSON validation passed.
- Collected fixture confirmed the live-only profile resolver is skipped in collected mode.

Fixture timing:

- Fixture wall-clock was `03:15` for this local run.
- Timing should not be treated as a profile performance signal because this change affects live collection defaults and the fixture uses collected mode.

Next work:

- Run a live cluster report with the default `report_performance_profile=standard` and compare `live_support_collection` plus per-collector timings against the prior full-style run.
- If the customer needs the prior broad support collection behavior, run with `-e report_performance_profile=full`.
