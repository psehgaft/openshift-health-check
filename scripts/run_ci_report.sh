#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 || "${1}" == -* ]]; then
  PLAYBOOK="${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml"
else
  PLAYBOOK="$1"
  shift
fi

PLAYBOOK_BASENAME="$(basename "${PLAYBOOK}")"
CLUSTER_TYPE_LABEL="${PLAYBOOK_BASENAME%_cluster_health_report.yml}"
if [[ "${CLUSTER_TYPE_LABEL}" == "${PLAYBOOK_BASENAME}" ]]; then
  CLUSTER_TYPE_LABEL="${PLAYBOOK_BASENAME%.yml}"
fi
SANITIZED_CLUSTER_TYPE_LABEL="$(printf '%s' "${CLUSTER_TYPE_LABEL}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9._-' '-')"
LOG_DIR="${ROOT_DIR}/.logs"
TIMESTAMP="$(date '+%Y%m%dT%H%M%S')"
LOG_FILE="${LOG_DIR}/${SANITIZED_CLUSTER_TYPE_LABEL}-run-${TIMESTAMP}.log"
ANSIBLE_PLAYBOOK_BIN="${ROOT_DIR}/.venv/bin/ansible-playbook"

mkdir -p "${LOG_DIR}"

if [[ ! -x "${ANSIBLE_PLAYBOOK_BIN}" ]]; then
  echo "run_ci_report.sh requires ${ANSIBLE_PLAYBOOK_BIN}. Run scripts/setup-ansible-venv.sh first." >&2
  exit 1
fi

if [[ "${OHC_CI_TEE_ACTIVE:-0}" != "1" ]]; then
  export OHC_CI_TEE_ACTIVE=1
  "${BASH_SOURCE[0]}" "${PLAYBOOK}" "$@" 2>&1 | tee "${LOG_FILE}"
  exit "${PIPESTATUS[0]}"
fi

printf '[%s] Writing CI run output to %s\n' "$(date '+%H:%M:%S')" "${LOG_FILE}"

FINAL_MD="${ROOT_DIR}/reports/ci-cluster-report.md"
FINAL_JSON="${ROOT_DIR}/reports/ci-cluster-report.json"
TEMP_REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ci-cluster-report.XXXXXX")"
trap 'rm -rf "${TEMP_REPORT_DIR}"' EXIT

ANSIBLE_LOCAL_TEMP="${TMPDIR:-/tmp}/ansible-local" \
ANSIBLE_REMOTE_TEMP="${TMPDIR:-/tmp}/ansible-remote" \
OHC_FORCE_TASK_PROGRESS=1 \
"${ANSIBLE_PLAYBOOK_BIN}" "${PLAYBOOK}" \
  -e report_output_dir="${TEMP_REPORT_DIR}" \
  "$@"

latest_json="$(find "${TEMP_REPORT_DIR}" -maxdepth 1 -name '*.json' -print | sort | tail -n 1)"
latest_md="$(find "${TEMP_REPORT_DIR}" -maxdepth 1 -name '*.md' -print | sort | tail -n 1)"

if [[ -z "${latest_json}" || -z "${latest_md}" ]]; then
  echo "unable to locate generated report artifacts in ${TEMP_REPORT_DIR}" >&2
  exit 1
fi

mkdir -p "${ROOT_DIR}/reports"
cp "${latest_json}" "${FINAL_JSON}"
cp "${latest_md}" "${FINAL_MD}"

printf 'ci report ok\nsource_md=%s\nsource_json=%s\nmd=%s\njson=%s\n' "${latest_md}" "${latest_json}" "${FINAL_MD}" "${FINAL_JSON}"
