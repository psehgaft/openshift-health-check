#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_PATH="${ROOT_DIR}/tests/fixtures/must-gather.local.mock"
CLUSTER_COMPARE_PATH="${ROOT_DIR}/tests/fixtures/cluster-compare/mock-cluster-compare.json"
INSPECT_PATH="${ROOT_DIR}/tests/fixtures/inspect.mock"
SOSREPORT_PATH="${ROOT_DIR}/tests/fixtures/sosreport-worker-0"
ADVISOR_PATH="${ROOT_DIR}/tests/fixtures/advisor/mock-advisor.json"
MANAGED_GATES_PATH="${ROOT_DIR}/tests/fixtures/managed-gates/mock-rosa-gates.json"
OMC_PATH="${ROOT_DIR}/tests/fixtures/bin/omc"
REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/supportability-fixture-reports.XXXXXX")"
LOG_PATH="${TMPDIR:-/tmp}/supportability-fixture.log"
ANSIBLE_PLAYBOOK_BIN="${ROOT_DIR}/.venv/bin/ansible-playbook"
VENV_PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
trap 'rm -rf "${REPORT_DIR}"' EXIT

ANSIBLE_LOCAL_TEMP="${TMPDIR:-/tmp}/ansible-local" \
ANSIBLE_REMOTE_TEMP="${TMPDIR:-/tmp}/ansible-remote" \
ANSIBLE_STDOUT_CALLBACK=minimal \
"${ANSIBLE_PLAYBOOK_BIN}" "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  -e report_output_dir="${REPORT_DIR}" \
  -e report_basename=cluster-supportability \
  -e must_gather_path="${FIXTURE_PATH}" \
  -e cluster_compare_path="${CLUSTER_COMPARE_PATH}" \
  -e managed_gates_path="${MANAGED_GATES_PATH}" \
  -e inspect_path="${INSPECT_PATH}" \
  -e advisor_export_path="${ADVISOR_PATH}" \
  -e omc_binary_path="${OMC_PATH}" \
  -e "{\"sosreport_paths\":[\"${SOSREPORT_PATH}\"]}" \
  > "${LOG_PATH}" 2>&1

report_json="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.json' -print | sort | tail -n 1)"
report_md="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.md' -print | sort | tail -n 1)"

if [[ -z "${report_json}" || -z "${report_md}" ]]; then
  echo "failed to detect newly generated supportability reports" >&2
  tail -n 40 "${LOG_PATH}" >&2 || true
  exit 1
fi

"${VENV_PYTHON_BIN}" - "${report_json}" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8"))

assert payload["metadata"]["platform_family"] == "openshift"
assert payload["supportability"]["summary"]["verdict"] == "unsupported-risk"
assert payload["supportability"]["summary"]["reference_compliance_verdict"] == "supported"
assert int(payload["health_summary"]["failed_pipelineruns"]) == 1
assert int(payload["health_summary"]["apiservice_issues"]) == 1
assert int(payload["health_summary"]["routes_not_admitted"]) == 1
assert payload["metrics"]["day2_posture_summary"]["gitops_present"] is True
assert payload["metrics"]["backup_schedule_summary"], "expected backup schedule evidence in fixture report"
assert payload["supportability"]["reference_compliance_summary"]["evidence_present"] is True
assert payload["supportability"]["reference_compliance_summary"]["verdict"] == "supported"
assert payload["supportability"]["etcd_ocp_diag_summary"]["present"] is True
assert payload["supportability"]["etcd_ocp_diag_summary"]["verdict"] == "review-required"
assert int(payload["supportability"]["etcd_ocp_diag_summary"]["pod_count"]) == 1
assert int(payload["supportability"]["etcd_ocp_diag_summary"]["apply_took_too_long_count"]) == 1
assert int(payload["supportability"]["etcd_ocp_diag_summary"]["slow_fsync_count"]) == 1
assert payload["supportability"]["omc_summary"]["present"] is True
assert payload["supportability"]["omc_summary"]["verdict"] == "review-required"
assert int(payload["supportability"]["omc_summary"]["endpoint_count"]) == 2
assert int(payload["supportability"]["omc_summary"]["endpoint_error_count"]) == 1
assert int(payload["supportability"]["omc_summary"]["firing_alert_count"]) == 1
assert int(payload["supportability"]["omc_summary"]["pending_alert_count"]) == 1
assert payload["supportability"]["node_diagnostics_summary"]["inspect_present"] is True
assert payload["supportability"]["node_diagnostics_summary"]["sosreport_present"] is True
assert payload["supportability"]["node_diagnostics_summary"]["verdict"] == "supported"
assert payload["supportability"]["advisor_summary"]["present"] is True
assert payload["supportability"]["advisor_summary"]["verdict"] == "review-required"
assert payload["supportability"]["managed_gate_summary"]["present"] is True
assert payload["supportability"]["managed_gate_summary"]["verdict"] == "unsupported-risk"
assert int(payload["supportability"]["managed_gate_summary"]["blocked_count"]) == 1
assert payload["supportability"]["product_evidence"]["pipelines"]["present"] is True
assert payload["supportability"]["product_evidence"]["logging"]["present"] is True
assert payload["supportability"]["product_evidence"]["gitops"]["present"] is True
assert payload["supportability"]["product_evidence"]["odf"]["present"] is True
assert payload["supportability"]["product_evidence"]["virtualization"]["present"] is True
assert payload["supportability"]["product_evidence"]["ai"]["present"] is True
assert int(payload["supportability"]["product_evidence"]["ai"]["datasciencecluster_count"]) == 1
assert int(payload["supportability"]["product_evidence"]["ai"]["notebook_count"]) == 1
assert int(payload["supportability"]["product_evidence"]["ai"]["inferenceservice_count"]) == 1
assert payload["domains"]["upgrade_and_lifecycle_risk"]["upgrade_readiness_summary"]["status"] in ["BLOCKED", "WARNING", "READY", "UNKNOWN"]
assert payload["domains"]["upgrade_and_lifecycle_risk"]["upgrade_readiness_summary"]["recommendation"]
assert isinstance(payload["domains"]["upgrade_and_lifecycle_risk"]["upgrade_readiness_summary"]["blocker_findings"], list)
assert payload["domains"]["observability"]["summary"]["status"] in ["CRITICAL", "WARNING", "HEALTHY", "UNKNOWN"]
assert payload["domains"]["observability"]["summary"]["recommendation"]
assert "alert_delivery_verification_status" in payload["domains"]["observability"]["summary"]
assert "logs_delivery_verification_status" in payload["domains"]["observability"]["summary"]
assert payload["domains"]["security_and_governance"]["summary"]["status"] in ["CRITICAL", "WARNING", "HEALTHY", "UNKNOWN"]
assert payload["domains"]["security_and_governance"]["summary"]["recommendation"]
assert payload["domains"]["production_day2_readiness"]["day2_production_readiness_summary"]["status"] in ["CRITICAL", "WARNING", "HEALTHY", "UNKNOWN"]
assert payload["domains"]["production_day2_readiness"]["day2_production_readiness_summary"]["recommendation"]
assert isinstance(payload["domains"]["production_day2_readiness"]["day2_production_readiness_summary"]["top_blockers"], list)
assert "declarative_operations_summary" in payload["domains"]["production_day2_readiness"]
assert payload["domains"]["production_day2_readiness"]["operations_recommendations"]
assert payload["domains"]["security_and_governance"]["compliance"]["operator_summary"]["present"] is True
assert int(payload["domains"]["security_and_governance"]["compliance"]["operator_summary"]["scan_count"]) == 2
standards = {item["standard"]: item for item in payload["domains"]["security_and_governance"]["compliance"]["standards_summary"]}
assert standards["CIS"]["configured"] is True
assert standards["CIS"]["active_enabled"] is True
assert standards["PCI-DSS"]["configured"] is True
assert standards["PCI-DSS"]["active_enabled"] is True
assert standards["HIPAA"]["configured"] is False
assert standards["HIPAA"]["content_present"] is True
assert standards["HIPAA"]["active_enabled"] is False
assert standards["FedRAMP"]["configured"] is False
assert standards["FedRAMP"]["content_present"] is True
assert standards["FedRAMP"]["active_enabled"] is False
assert standards["SOC"]["configured"] is False
assert standards["SOC"]["active_enabled"] is False
assert standards["SOX"]["configured"] is False
assert standards["SOX"]["content_present"] is True
assert standards["SOX"]["active_enabled"] is False
assert standards["FIPS"]["configured"] is True
assert standards["FIPS"]["active_enabled"] is False
assert standards["FIPS"]["runtime_status"] == "enabled"
print(report_path)
PY

rg -q '^# OpenShift Cluster Health Report' "${report_md}"
rg -q 'Overall verdict: `unsupported-risk`' "${report_md}"
rg -q '### Failed PipelineRuns' "${report_md}"
rg -q '^## Day 2 Production Readiness' "${report_md}"
rg -q '## Node Health And Capacity' "${report_md}"
rg -q '^## Platform Architecture And Lifecycle' "${report_md}"
rg -q '## Observability' "${report_md}"
rg -q '## Security And Governance' "${report_md}"
rg -q '### Individual Capability Sections' "${report_md}"
rg -q '| Capability assessment state |' "${report_md}"
rg -q '| Top blockers |' "${report_md}"
rg -q '### Product Evidence' "${report_md}"
rg -q '| AI | `True` |' "${report_md}"
rg -q '### Compliance' "${report_md}"
rg -q '| `FIPS` | `True` |' "${report_md}"
rg -q '| `FedRAMP` | `True` | `False` |' "${report_md}"
rg -q '| `PCI-DSS` | `True` |' "${report_md}"
rg -q 'content-available' "${report_md}"
rg -q 'enabled' "${report_md}"
rg -q '### etcd Must-Gather Diagnostics' "${report_md}"
rg -q '### OMC Must-Gather Diagnostics' "${report_md}"

printf 'fixture report ok\njson=%s\nmd=%s\nlog=%s\n' "${report_json}" "${report_md}" "${LOG_PATH}"
