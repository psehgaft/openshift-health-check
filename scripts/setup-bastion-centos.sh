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

if command -v dnf >/dev/null 2>&1; then
  PKG_MGR="dnf"
else
  PKG_MGR="yum"
fi

CORE_PACKAGES=(
  ca-certificates
  curl
  git
  jq
  openssl
  python3
  python3-pip
  tar
  unzip
)

OPTIONAL_PACKAGES=(
  pandoc
  wkhtmltopdf
)

log() {
  printf '[setup-bastion-centos] %s\n' "$*"
}

log "Installing EPEL when available"
${PKG_MGR} install -y epel-release || true

log "Refreshing package metadata"
${PKG_MGR} makecache

log "Installing core bastion host packages"
${PKG_MGR} install -y "${CORE_PACKAGES[@]}"

log "Installing optional document-conversion packages when available"
${PKG_MGR} install -y "${OPTIONAL_PACKAGES[@]}" || true

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

OCP_CLIENT_URL="https://mirror.openshift.com/pub/openshift-v4/${OCP_ARCH}/clients/ocp/stable/openshift-client-linux.tar.gz"

log "Downloading OpenShift client bundle from ${OCP_CLIENT_URL}"
curl -fsSL "${OCP_CLIENT_URL}" -o "${TMP_DIR}/openshift-client-linux.tar.gz"

log "Installing oc and kubectl into /usr/local/bin"
tar -C "${TMP_DIR}" -xzf "${TMP_DIR}/openshift-client-linux.tar.gz"
install -m 0755 "${TMP_DIR}/oc" /usr/local/bin/oc
install -m 0755 "${TMP_DIR}/kubectl" /usr/local/bin/kubectl

if [[ -x "${REPO_ROOT}/scripts/setup-ansible-venv.sh" ]]; then
  log "Bootstrapping repo-local Python virtual environment"
  bash "${REPO_ROOT}/scripts/setup-ansible-venv.sh"
else
  log "Repo-local setup-ansible-venv.sh not found; skipping .venv bootstrap"
fi

cat <<EOF

CentOS/RHEL bastion setup complete.

Installed core commands:
  oc
  kubectl
  python3
  git
  jq
  openssl

Optional document-conversion tools were attempted:
  pandoc
  wkhtmltopdf

Next steps:
  source "${REPO_ROOT}/.venv/bin/activate"
  oc login ...
  ansible-playbook playbooks/openshift_cluster_health_report.yml -e report_mode=live

EOF
