#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_PATH="${ROOT_DIR}/tests/fixtures"
REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/supportability-case-bundle-reports.XXXXXX")"
LOG_PATH="${TMPDIR:-/tmp}/supportability-case-bundle.log"
ANSIBLE_PLAYBOOK_BIN="${ROOT_DIR}/.venv/bin/ansible-playbook"
VENV_PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
trap 'rm -rf "${REPORT_DIR}"' EXIT

ANSIBLE_LOCAL_TEMP="${TMPDIR:-/tmp}/ansible-local" \
ANSIBLE_REMOTE_TEMP="${TMPDIR:-/tmp}/ansible-remote" \
ANSIBLE_STDOUT_CALLBACK=minimal \
"${ANSIBLE_PLAYBOOK_BIN}" "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  -e report_output_dir="${REPORT_DIR}" \
  -e report_basename=cluster-supportability \
  -e case_bundle_path="${BUNDLE_PATH}" \
  > "${LOG_PATH}" 2>&1

report_json="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.json' -print | sort | tail -n 1)"
report_md="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.md' -print | sort | tail -n 1)"

if [[ -z "${report_json}" || -z "${report_md}" ]]; then
  echo "failed to detect newly generated case-bundle supportability reports" >&2
  tail -n 40 "${LOG_PATH}" >&2 || true
  exit 1
fi

"${VENV_PYTHON_BIN}" - "${report_json}" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8"))

assert payload["metadata"]["evidence_mode"] == "hybrid"
assert payload["evidence"]["summary"]["case_bundle_path"].endswith("/tests/fixtures")
assert payload["supportability"]["managed_gate_summary"]["verdict"] == "unsupported-risk"
assert payload["supportability"]["advisor_summary"]["verdict"] == "review-required"
assert payload["supportability"]["reference_compliance_summary"]["verdict"] == "supported"
assert payload["supportability"]["node_diagnostics_summary"]["verdict"] == "supported"
assert payload["evidence"]["hygiene_summary"]["verdict"] == "review-required"
assert payload["evidence"]["hygiene_summary"]["candidate_count"] >= 2
print(report_path)
PY

rg -q '^# OpenShift Cluster Health Report' "${report_md}"
rg -q 'Case bundle path' "${report_md}"
rg -q '^## Evidence And Supportability' "${report_md}"
rg -q '^## Day 2 Production Readiness' "${report_md}"

printf 'case bundle fixture report ok\njson=%s\nmd=%s\nlog=%s\n' "${report_json}" "${report_md}" "${LOG_PATH}"
