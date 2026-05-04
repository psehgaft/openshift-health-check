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

mkdir -p "${LOG_DIR}"

if [[ "${OHC_RUN_TEE_ACTIVE:-0}" != "1" ]]; then
  export OHC_RUN_TEE_ACTIVE=1
  "${BASH_SOURCE[0]}" "${PLAYBOOK}" "$@" 2>&1 | tee "${LOG_FILE}"
  exit "${PIPESTATUS[0]}"
fi

printf '[%s] Writing run output to %s\n' "$(date '+%H:%M:%S')" "${LOG_FILE}"

export OHC_FORCE_TASK_PROGRESS=1
ansible-playbook "${PLAYBOOK}" "$@"
