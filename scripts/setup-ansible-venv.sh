#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_dir="${repo_root}/.venv"
ansible_playbook_bin="${venv_dir}/bin/ansible-playbook"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  python_bin="${PYTHON_BIN}"
elif command -v python3.12 >/dev/null 2>&1; then
  python_bin="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
else
  echo "setup-ansible-venv.sh requires python3.12 or python3 on PATH." >&2
  exit 1
fi

"${python_bin}" -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install --upgrade pip
"${venv_dir}/bin/pip" install -r "${repo_root}/requirements.txt"

mkdir -p "${repo_root}/.runtime/ansible/tmp" "${repo_root}/.runtime/ansible/remote_tmp"

cat <<EOF
Virtual environment ready.

Installed support target:
  python3.12 or python3
  ansible-core >=2.16.3,<2.17
Using interpreter:
  ${python_bin}

Activate it with:
  source "${venv_dir}/bin/activate"

Then run:
  ${ansible_playbook_bin} --version
  ${ansible_playbook_bin} playbooks/openshift_cluster_health_report.yml
EOF
