#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 || "${1}" == -* ]]; then
  PLAYBOOK="${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml"
else
  PLAYBOOK="$1"
  shift
fi

FINAL_MD="${ROOT_DIR}/reports/ci-cluster-report.md"
FINAL_JSON="${ROOT_DIR}/reports/ci-cluster-report.json"
TEMP_REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ci-cluster-report.XXXXXX")"
trap 'rm -rf "${TEMP_REPORT_DIR}"' EXIT

ANSIBLE_LOCAL_TEMP="${TMPDIR:-/tmp}/ansible-local" \
ANSIBLE_REMOTE_TEMP="${TMPDIR:-/tmp}/ansible-remote" \
ansible-playbook "${PLAYBOOK}" \
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
