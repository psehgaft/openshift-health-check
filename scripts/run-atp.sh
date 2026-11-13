#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/playbooks"
if [[ -f "$repo_root/group_vars/atp/vault.yml" ]]; then
  exec ansible-playbook --ask-vault-pass -i localhost, atp.yml "$@"
fi
exec ansible-playbook -i localhost, atp.yml "$@"
