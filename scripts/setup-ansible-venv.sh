#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_dir="${repo_root}/.venv"

python3 -m venv "${venv_dir}"
"${venv_dir}/bin/python" -m pip install --upgrade pip
"${venv_dir}/bin/pip" install -r "${repo_root}/requirements.txt"

mkdir -p "${repo_root}/.ansible/tmp"

cat <<EOF
Virtual environment ready.

Activate it with:
  source "${venv_dir}/bin/activate"

Then run:
  ansible-playbook playbooks/openshift_cluster_health_report.yml
EOF
