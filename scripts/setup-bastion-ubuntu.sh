#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or through sudo." >&2
  exit 1
fi

ARCH="$(uname -m)"
case "${ARCH}" in
  x86_64)
    OCP_ARCH="x86_64"
    ;;
  aarch64|arm64)
    OCP_ARCH="arm64"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH}" >&2
    exit 1
    ;;
esac

APT_PACKAGES=(
  ca-certificates
  curl
  git
  jq
  openssl
  pandoc
  python3
  python3-pip
  python3-venv
  tar
  unzip
  wkhtmltopdf
)

log() {
  printf '[setup-bastion-ubuntu] %s\n' "$*"
}

resolve_bootstrap_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    printf '%s\n' "${SUDO_USER}"
    return
  fi

  local repo_owner
  repo_owner="$(stat -c '%U' "${REPO_ROOT}")"
  if [[ -n "${repo_owner}" && "${repo_owner}" != "root" ]]; then
    printf '%s\n' "${repo_owner}"
    return
  fi

  printf '%s\n' ""
}

bootstrap_repo_runtime() {
  local bootstrap_user="$1"

  if [[ ! -x "${REPO_ROOT}/scripts/setup-ansible-venv.sh" ]]; then
    log "Repo-local setup-ansible-venv.sh not found; skipping .venv bootstrap"
    return
  fi

  if [[ -z "${bootstrap_user}" ]]; then
    log "Could not determine a non-root repo user; skipping .venv bootstrap to avoid creating root-owned runtime files"
    return
  fi

  log "Preparing repo-local runtime ownership for ${bootstrap_user}"
  mkdir -p "${REPO_ROOT}/.runtime/ansible/tmp" "${REPO_ROOT}/.runtime/ansible/remote_tmp"
  chown -R "${bootstrap_user}:${bootstrap_user}" "${REPO_ROOT}/.ansible"
  if [[ -e "${REPO_ROOT}/.venv" ]]; then
    chown -R "${bootstrap_user}:${bootstrap_user}" "${REPO_ROOT}/.venv"
  fi

  log "Bootstrapping repo-local Python virtual environment as ${bootstrap_user}"
  runuser -u "${bootstrap_user}" -- bash "${REPO_ROOT}/scripts/setup-ansible-venv.sh"
}

log "Refreshing apt metadata"
apt-get update

log "Installing bastion host packages"
DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"

mkdir -p "${REPO_ROOT}/.runtime/tmp"
TMP_DIR="$(mktemp -d "${REPO_ROOT}/.runtime/tmp/bootstrap.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

OCP_CLIENT_URL="https://mirror.openshift.com/pub/openshift-v4/${OCP_ARCH}/clients/ocp/stable/openshift-client-linux.tar.gz"

log "Downloading OpenShift client bundle from ${OCP_CLIENT_URL}"
curl -fsSL "${OCP_CLIENT_URL}" -o "${TMP_DIR}/openshift-client-linux.tar.gz"

log "Installing oc and kubectl into /usr/local/bin"
tar -C "${TMP_DIR}" -xzf "${TMP_DIR}/openshift-client-linux.tar.gz"
install -m 0755 "${TMP_DIR}/oc" /usr/local/bin/oc
install -m 0755 "${TMP_DIR}/kubectl" /usr/local/bin/kubectl

BOOTSTRAP_USER="$(resolve_bootstrap_user)"
bootstrap_repo_runtime "${BOOTSTRAP_USER}"

cat <<EOF

Ubuntu bastion setup complete.

Installed core commands:
  oc
  kubectl
  python3
  git
  jq
  openssl
  pandoc
  wkhtmltopdf

Next steps:
  cd "${REPO_ROOT}"
  source "${REPO_ROOT}/.venv/bin/activate"
  oc login ...
  ansible-playbook playbooks/openshift_cluster_health_report.yml -e report_mode=live

EOF
