#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "${ROOT_DIR}/scripts/repo-runtime-env.sh"
INSPECT_PATH="${ROOT_DIR}/tests/fixtures/inspect.mock"
REPORT_DIR="$(mktemp -d "${REPO_TMP_ROOT}/supportability-inspect-reports.XXXXXX")"
LOG_PATH="${REPO_TMP_ROOT}/supportability-inspect-fixture.log"
ANSIBLE_PLAYBOOK_BIN="${ROOT_DIR}/.venv/bin/ansible-playbook"
VENV_PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
trap 'rm -rf "${REPORT_DIR}"' EXIT

cleanup_repo_ansible_temp_dirs

ANSIBLE_LOCAL_TEMP="${REPO_ANSIBLE_LOCAL_TEMP}" \
ANSIBLE_REMOTE_TEMP="${REPO_ANSIBLE_REMOTE_TEMP}" \
ANSIBLE_STDOUT_CALLBACK=minimal \
"${ANSIBLE_PLAYBOOK_BIN}" "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  -e report_output_dir="${REPORT_DIR}" \
  -e report_basename=cluster-supportability \
  -e evidence_mode=inspect \
  -e inspect_path="${INSPECT_PATH}" \
  > "${LOG_PATH}" 2>&1

report_json="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.json' -print | sort | tail -n 1)"
report_md="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.md' -print | sort | tail -n 1)"

if [[ -z "${report_json}" || -z "${report_md}" ]]; then
  echo "failed to detect newly generated inspect-only supportability reports" >&2
  tail -n 40 "${LOG_PATH}" >&2 || true
  exit 1
fi

"${VENV_PYTHON_BIN}" - "${report_json}" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8"))

assert payload["metadata"]["evidence_mode"] == "inspect"
assert payload["evidence"]["summary"]["mode"] == "inspect"
assert payload["supportability"]["diagnostics_coverage"]["must_gather"] == "missing"
assert payload["supportability"]["etcd_ocp_diag_summary"]["verdict"] == "not-collected"
assert payload["supportability"]["node_diagnostics_summary"]["inspect_present"] is True
assert int(payload["health_summary"]["nodes_total"]) >= 1
assert int(payload["health_summary"]["mcps_total"]) >= 1
print(report_path)
PY

rg -q '^# OpenShift Cluster Health Report' "${report_md}"
rg -q 'Evidence mode: inspect' "${report_md}"
! rg -q 'No sosreport archive was collected for node diagnostics\.' "${report_md}"

printf 'inspect fixture report ok\njson=%s\nmd=%s\nlog=%s\n' "${report_json}" "${report_md}" "${LOG_PATH}"
