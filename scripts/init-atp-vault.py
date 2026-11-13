#!/usr/bin/env python3
"""Create the ATP-only Ansible Vault file without exposing secrets in shell history."""
from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    vault_dir = root / "group_vars" / "atp"
    vault_dir.mkdir(parents=True, exist_ok=True)
    vault_path = vault_dir / "vault.yml"

    if vault_path.exists():
        print(f"{vault_path.relative_to(root)} already exists. Use ansible-vault edit to change it.")
        return 2
    if not shutil.which("ansible-vault"):
        print("ansible-vault is not installed or is not available in PATH.", file=sys.stderr)
        return 2

    password = getpass.getpass("Choose an Ansible Vault password: ")
    confirm = getpass.getpass("Confirm the Ansible Vault password: ")
    if not password or password != confirm:
        print("Vault passwords are empty or do not match.", file=sys.stderr)
        return 2

    username = input("Quay robot username (leave blank to use pull-secret discovery): ").strip()
    token = getpass.getpass("Quay robot token/password (leave blank with username): ")
    if bool(username) != bool(token):
        print("Enter both the robot username and token, or leave both blank.", file=sys.stderr)
        return 2

    values = (
        {
            "atp_external_registry_robot_username": username,
            "atp_external_registry_robot_token": token,
        }
        if username
        else {}
    )
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix=".atp-vault-", dir=vault_dir) as tmp:
        tmp_dir = Path(tmp)
        plain_file = tmp_dir / "vault.yml"
        password_file = tmp_dir / "vault-password"
        encrypted_file = tmp_dir / "vault.yml.encrypted"
        # JSON scalar quoting is valid YAML and safely handles special characters.
        plain_file.write_text(
            "".join(
                f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
                for key, value in values.items()
            ),
            encoding="utf-8",
        )
        plain_file.chmod(0o600)
        password_file.write_text(password + "\n", encoding="utf-8")
        password_file.chmod(0o600)
        result = subprocess.run(
            [
                "ansible-vault",
                "encrypt",
                "--vault-password-file",
                str(password_file),
                "--output",
                str(encrypted_file),
                str(plain_file),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not encrypted_file.is_file():
            print("Vault encryption failed. No credential file was installed.", file=sys.stderr)
            if result.stderr:
                print(result.stderr.strip(), file=sys.stderr)
            return 1
        encrypted_file.chmod(0o600)
        os.replace(encrypted_file, vault_path)
        vault_path.chmod(0o600)

    print("Created encrypted group_vars/atp/vault.yml.")
    print("The vault password and Quay token were not printed or written to tracked plaintext files.")
    print("Run ATP with scripts/run-atp.sh; Ansible will prompt for the vault password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
