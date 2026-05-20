#!/usr/bin/env bash

if [[ -z "${ROOT_DIR:-}" ]]; then
  ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

REPO_RUNTIME_ROOT="${ROOT_DIR}/.runtime"
REPO_TMP_ROOT="${REPO_RUNTIME_ROOT}/tmp"
REPO_ANSIBLE_ROOT="${REPO_RUNTIME_ROOT}/ansible"
REPO_ANSIBLE_LOCAL_TEMP="${REPO_ANSIBLE_ROOT}/tmp"
REPO_ANSIBLE_REMOTE_TEMP="${REPO_ANSIBLE_ROOT}/remote_tmp"

mkdir -p \
  "${REPO_RUNTIME_ROOT}" \
  "${REPO_ANSIBLE_ROOT}" \
  "${REPO_TMP_ROOT}" \
  "${REPO_ANSIBLE_LOCAL_TEMP}" \
  "${REPO_ANSIBLE_REMOTE_TEMP}" \
  "${ROOT_DIR}/.logs"

export ANSIBLE_CONFIG="${ROOT_DIR}/ansible.cfg"
export TMPDIR="${REPO_TMP_ROOT}"
export TMP="${REPO_TMP_ROOT}"
export TEMP="${REPO_TMP_ROOT}"
export ANSIBLE_LOCAL_TEMP="${REPO_ANSIBLE_LOCAL_TEMP}"
export ANSIBLE_REMOTE_TEMP="${REPO_ANSIBLE_REMOTE_TEMP}"

cleanup_repo_ansible_temp_dirs() {
  local temp_dir

  for temp_dir in "${REPO_ANSIBLE_LOCAL_TEMP}" "${REPO_ANSIBLE_REMOTE_TEMP}"; do
    mkdir -p "${temp_dir}"
    find "${temp_dir}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  done
}
