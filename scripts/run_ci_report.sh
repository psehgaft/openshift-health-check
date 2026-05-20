#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "${ROOT_DIR}/scripts/repo-runtime-env.sh"
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

cleanup_repo_ansible_temp_dirs

printf '[%s] Writing CI run output to %s\n' "$(date '+%H:%M:%S')" "${LOG_FILE}"

FINAL_MD="${ROOT_DIR}/reports/ci-cluster-report.md"
FINAL_JSON="${ROOT_DIR}/reports/ci-cluster-report.json"
FINAL_WORKSPACE_MD="${ROOT_DIR}/reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md"
FINAL_WORKSPACE_JSON="${ROOT_DIR}/reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json"
TEMP_REPORT_DIR="$(mktemp -d "${REPO_TMP_ROOT}/ci-cluster-report.XXXXXX")"
EFFECTIVE_REPORT_DIR="${TEMP_REPORT_DIR}"
trap 'rm -rf "${TEMP_REPORT_DIR}"' EXIT

args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[i]}" == "-e" && $((i + 1)) -lt ${#args[@]} ]]; then
    if [[ "${args[i+1]}" == report_output_dir=* ]]; then
      EFFECTIVE_REPORT_DIR="${args[i+1]#report_output_dir=}"
    fi
  fi
done

ANSIBLE_LOCAL_TEMP="${REPO_ANSIBLE_LOCAL_TEMP}" \
ANSIBLE_REMOTE_TEMP="${REPO_ANSIBLE_REMOTE_TEMP}" \
OHC_FORCE_TASK_PROGRESS=1 \
"${ANSIBLE_PLAYBOOK_BIN}" "${PLAYBOOK}" \
  -e report_output_dir="${TEMP_REPORT_DIR}" \
  "$@"

latest_json="$(find "${EFFECTIVE_REPORT_DIR}" -maxdepth 1 -name '*.json' -print | sort | tail -n 1)"
latest_md="$(find "${EFFECTIVE_REPORT_DIR}" -maxdepth 1 -name '*.md' -print | sort | tail -n 1)"

if [[ -z "${latest_json}" || -z "${latest_md}" ]]; then
  echo "unable to locate generated report artifacts in ${EFFECTIVE_REPORT_DIR}" >&2
  exit 1
fi

mkdir -p "${ROOT_DIR}/reports"
cp "${latest_json}" "${FINAL_JSON}"
cp "${latest_md}" "${FINAL_MD}"

if [[ -d "${EFFECTIVE_REPORT_DIR}/.run-state" ]]; then
  rm -rf "${ROOT_DIR}/reports/.run-state"
  cp -R "${EFFECTIVE_REPORT_DIR}/.run-state" "${ROOT_DIR}/reports/.run-state"
fi

mkdir -p "$(dirname "${FINAL_WORKSPACE_MD}")"
cp "${latest_md}" "${FINAL_WORKSPACE_MD}"
cp "${latest_json}" "${FINAL_WORKSPACE_JSON}"

printf 'ci report ok\nsource_md=%s\nsource_json=%s\nmd=%s\njson=%s\nworkspace_md=%s\nworkspace_json=%s\n' \
  "${latest_md}" "${latest_json}" "${FINAL_MD}" "${FINAL_JSON}" "${FINAL_WORKSPACE_MD}" "${FINAL_WORKSPACE_JSON}"
