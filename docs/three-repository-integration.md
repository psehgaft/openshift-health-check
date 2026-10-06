# Unified OpenShift health and architecture workflow

## Repository analysis and implementation

The canonical repository is [psehgaft/openshift-health-check](https://github.com/psehgaft/openshift-health-check).
All imported source is stored in this repository; a checkout does not require submodules or additional source clones.
Pinned source commits and exclusions are recorded in [sources.json](../integration/sources.json).

| Source | Strengths | Integration location | Responsibility |
| --- | --- | --- | --- |
| openshift-health-check | Ansible roles, profile-gated health scoring, live/collected evidence, checkpoint/resume, Markdown/JSON/HTML/PDF | Existing root layout | Canonical cluster health report |
| [openshift-healthcheck](https://github.com/psehgaft/openshift-healthcheck) | Bash collection for OCP 4.18+, CSV findings/backlog, CER material, ACM, certificate and DNS audits, Headlamp plugin | `toolkits/openshift-healthcheck/` | Additional diagnostics and operational evidence |
| [arch-design-doc-generator](https://github.com/stratus-ss/arch-design-doc-generator) | ADR-driven HLD/LLD, diagrams, PDF publishing, work items | `tools/arch-design-doc-generator/` | Architecture authoring and publishing |

The orchestration interface is `scripts/unified_healthcheck.py`. It delegates to the existing engines and preserves the canonical OpenShift report shape, selectors, and resume behavior. It does not merge incompatible scores or silently deduplicate findings across engines. Every exported observation retains its source path.

The architecture bridge invokes the imported generator's real setup implementation, copies its native templates into an engagement workspace, and appends observations to the working ADR. It produces an evidence packet and a remediation review CSV without calling AI. HLD/LLD and diagrams are generated later through the native generator after an architect completes the ADR.

## 1. Install on a bastion

```bash
git clone https://github.com/psehgaft/openshift-health-check.git
cd openshift-health-check
./scripts/setup-ansible-venv.sh
source .venv/bin/activate
python3 scripts/unified_healthcheck.py --help
```

Use the existing RHEL-compatible bootstrap if system packages are missing:

```bash
sudo bash scripts/setup-bastion-centos.sh
```

Shell diagnostics require `bash`, `oc`, `timeout`, and standard GNU utilities; install `jq` and Python for structured analysis/rendering. Architecture setup requires Python 3.10+ and PyYAML, both covered by the documented virtual environment on a suitable host. Native publishing requires `make` and Podman/Docker. AI generation additionally needs the selected AI CLI/SDK and its credentials.

## 2. Run the full integrated assessment

```bash
oc login https://api.<cluster>.<domain>:6443
oc whoami
python3 scripts/unified_healthcheck.py suite \
  --client 'Example Client' \
  --cluster-name prod-5gc \
  --output engagements/prod-5gc-assessment
```

Choose a new output directory for every run. Existing directories are refused to prevent overwriting a previous engagement. The workflow executes:

1. Shell collection into `shell/` with must-gather disabled by default.
2. Normalization of raw JSON lists into individual Kubernetes objects in `normalized-evidence/`. Duplicate objects are keyed by API version, kind, namespace, and name; first observed copies are retained. Secret `data` and `stringData` are removed.
3. The canonical OpenShift playbook in collected mode with `inspect_path` pointing to normalized evidence. Live API backfill and node diagnostics are disabled in this path.
4. Export of the canonical report and shell CSV observations into `architecture/`, followed by native generator setup.

To explicitly enable must-gather during shell collection:

```bash
python3 scripts/unified_healthcheck.py suite \
  --client 'Example Client' --cluster-name prod-5gc \
  --output engagements/prod-5gc-with-support --must-gather
```

`oc adm must-gather` creates temporary collection resources. Other imported standalone diagnostics may use `oc debug`, create resources, or provide remediation manifests; consult their own runbooks before execution. The suite does not apply those remediation manifests.

Review `normalized-evidence/normalization-summary.json` for invalid or non-resource JSON. Empty or failed API responses are not interpreted as proof that a resource is absent. The canonical evidence coverage and report confidence remain the authority for report completeness. The shell toolkit also records commands and error output; some imported collectors mask command failures, so a successful script exit does not prove complete collection.

## 3. Use either health engine independently

Canonical live report, with node diagnostics disabled:

```bash
python3 scripts/unified_healthcheck.py report -- \
  -e report_mode=live -e collect_live_sosreport=false
```

Existing collected evidence:

```bash
python3 scripts/unified_healthcheck.py report -- \
  -e report_mode=collected \
  -e collected_evidence_root=/path/to/support-bundle \
  -e collect_live_missing_api_evidence=false
```

Shell-only collection with customized variables:

```bash
cp toolkits/openshift-healthcheck/Shell/ocp-healthcheck.env.example \
  toolkits/openshift-healthcheck/Shell/ocp-healthcheck.env
# Edit the local env file; it is sourced Bash, so use only trusted configuration.
python3 scripts/unified_healthcheck.py shell -- \
  --env-file toolkits/openshift-healthcheck/Shell/ocp-healthcheck.env \
  --cluster-name prod-5gc --client-label 'Example Client' \
  --output engagements/shell-only --no-must-gather
```

To feed a pre-existing shell run into the canonical engine:

```bash
python3 scripts/unified_healthcheck.py normalize-shell \
  --shell-run /path/to/healthcheck-prod-5gc-TIMESTAMP \
  --output engagements/normalized-prod-5gc
python3 scripts/unified_healthcheck.py report -- \
  -e report_mode=collected \
  -e inspect_path="$PWD/engagements/normalized-prod-5gc" \
  -e collect_live_missing_api_evidence=false
```

## 4. Create architecture artifacts from an existing report

```bash
python3 scripts/unified_healthcheck.py architecture \
  --report-json /path/to/canonical-health-report.json \
  --shell-run /path/to/healthcheck-prod-5gc-TIMESTAMP \
  --client 'Example Client' \
  --output engagements/architecture-review
```

`--shell-run` is optional. When supplied, all three CSV registers (`findings.csv`, `backlog.csv`, `errors-criticality.csv`) must be present. Output includes:

| Artifact | Purpose |
| --- | --- |
| `health-report.json` | Copy of the canonical report |
| `evidence.json` | Source hashes, metadata, audit, coverage, and observations |
| `remediation-review.csv` | Stable observation IDs, source paths, pending owner and acceptance criteria |
| `manifest.json` | Source snapshots and engagement linkage |
| `generator/ADR/` | Native working ADR plus health observations |
| `generator/project.yaml` | Native engagement configuration |
| `generator/output/` | Native HLD/LLD and diagram working templates |

The imported templates cover OpenShift Virtualization, ACM, platform build, fleet operations, and migration. For a Telco/5GC-only assessment, adapt those templates and the project configuration before generating design outputs. Health evidence cannot determine desired-state architecture, contractual SLAs, RTO/RPO, approved changes, or migration readiness by itself.

## 5. Review the ADR and build HLD/LLD, diagrams, and work items

1. Inspect `evidence.json`, canonical report coverage, and shell collection errors.
2. Fill the working ADR under `generator/ADR/`: business requirements, target design, accepted decisions, owners, dependencies, capacity targets, and validation criteria.
3. Edit `generator/project.yaml` for branding, phases, paths, and missing operator facts under `slots:`.
4. Configure the selected AI tool. AI commands can transmit ADR content; the evidence export itself never invokes AI.
5. Run the native build from the **engagement generator directory**, not the pinned source module:

```bash
cd engagements/architecture-review/generator
make status
make build-hld-from-adr AI_TOOL=codex
make publish
make build-lld
make workitems
```

Select `AI_TOOL=claude` or `AI_TOOL=cursor` if appropriate. Do not run `make clean` against an engagement without reviewing its native behavior. PDFs, diagram exports, and AI generation require the imported generator prerequisites; they are separate from deterministic evidence export.

## 6. Retained specialist modules

| Module | Documentation |
| --- | --- |
| ACM | [Toolkit README](../toolkits/openshift-healthcheck/ACM/acm-health-check-toolkit/README.md) and [runbook](../toolkits/openshift-healthcheck/ACM/ACM_Health_Check_Runbook.md) |
| Certificates | [Audit installation and execution](../toolkits/openshift-healthcheck/Certificates/README.md) |
| DNS | [DNS playbook](../toolkits/openshift-healthcheck/DNS/dns-validation.yml) and matching inventory |
| Original Ansible role | [Role README](../toolkits/openshift-healthcheck/Ansible/README.md) |
| Headlamp | [Plugin build, installation, and RBAC](../toolkits/openshift-healthcheck/Shell/headlamp-openshift-rbac-html-report/README.md) |
| Versioned shell diagnostics and CER | [Shell README](../toolkits/openshift-healthcheck/Shell/README.md) and [report guide](../toolkits/openshift-healthcheck/Shell/reports/README-reports.md) |
| Native architecture tooling | [Generator README](../tools/arch-design-doc-generator/README.md) |

These are available in the consolidated repository but are not all executed automatically by `suite`. ACM remediation, certificate audits, DNS validation, and Headlamp installation remain explicit specialist workflows.

## 7. Validation and maintenance

```bash
python3 -m unittest discover -s tests -p 'test_unified_integration.py'
scripts/validate_repo.sh
.venv/bin/python tests/run_unified_integration_fixture.py
# Optional upstream architecture tests:
.venv/bin/pip install pytest
(cd tools/arch-design-doc-generator && ../../.venv/bin/python -m pytest tests)
```

When refreshing a source snapshot, preserve its license, update `integration/sources.json`, retain local fixes, and rerun integration tests. Tracked compiled Python bytecode and prebuilt Headlamp assets were deliberately excluded. Build the retained plugin source with `npm ci`, `npm run build`, and `npm run package` in its directory before following the installation instructions.

## License and provenance

The original root code retains its [Apache-2.0 license](../LICENSE). The imported architecture module retains its [GPLv3 license](../tools/arch-design-doc-generator/LICENSE) and upstream notices; it is invoked as a separate program. Do not represent all consolidated contents as Apache-2.0 or remove third-party licensing. Any distribution combining or modifying GPL-covered code must account for the applicable GPL terms.

The shell source snapshot has no root LICENSE file. It belongs to the same GitHub owner as the destination, but this import does not invent a license grant for that source. Preserve ownership and clarify licensing before redistributing it under a different license. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for the pinned import boundaries and local modifications.

Legacy Ansible login settings now read `OPENSHIFT_API_URL`, `OPENSHIFT_USER`, `OPENSHIFT_PASSWORD`, and `OPENSHIFT_TOKEN` from the environment. The imported plaintext credentials were removed; SMTP/contact settings use example values. The canonical Ansible engine and unified shell collector continue to use the active `oc` session.

Optional bastion connectivity targets are supplied as `PRECHECK_DNS_HOST`, `PRECHECK_CONTROL_PLANE_HOST`, and `PRECHECK_WORKER_HOST`. Their checks are skipped when the variables are unset. ACM documentation uses example cluster names.

## Verification of this integration

The canonical repository validator, three integration unit tests, the complete suite fixture, and all 35 imported generator tests passed locally. The suite fixture replaces only live shell collection with stored API evidence; normalization, the canonical Ansible playbook, and native generator setup all execute normally.

Validation also exposed a canonical audit-log capability that reported `OK` when its audit profile was missing. Its owning role now requires a configured audit profile before returning a healthy status, and the rendered report validator passes.

No live OpenShift cluster execution, AI HLD/LLD generation, or PDF publishing was performed. Headlamp dependency installation and the source build passed in GitHub Actions with Node 22 after repairing the dependency lockfile and replacing internal registry URLs with public npm URLs. Use Node 22 for the imported plugin toolchain. The prepared virtual environment is placed on `PATH` by the CLI and runtime wrappers so Ansible's `python3` helpers can load their installed dependencies. The CI runner explicitly installs `ripgrep` for the existing fixture validator.

## References

- [Canonical source repository](https://github.com/psehgaft/openshift-health-check)
- [Shell and specialist toolkit source](https://github.com/psehgaft/openshift-healthcheck)
- [Architecture generator source](https://github.com/stratus-ss/arch-design-doc-generator)
- [OpenShift documentation](https://docs.redhat.com/en/documentation/openshift_container_platform)
- [Ansible playbooks](https://docs.ansible.com/ansible/latest/playbook_guide/index.html)
- [GNU GPLv3 text](https://www.gnu.org/licenses/gpl-3.0.html)
