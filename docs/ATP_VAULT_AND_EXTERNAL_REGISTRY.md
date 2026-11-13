# ATP Vault and External Registry Setup

This guide configures a remote Quay/OCI registry for ATP test cases TC-18 and TC-19 and stores its robot credentials in an ATP-only Ansible Vault file.

## Variables to configure

Set the registry endpoint and optional CA path in `group_vars/atp/main.yml`:

| Variable | Example | Purpose |
| --- | --- | --- |
| `atp_external_registry_url` | `https://quay.example.com` | Registry origin. The ATP adds `/v2/`; do not include that suffix. |
| `atp_external_registry_validate_certs` | `true` | Keep TLS certificate validation enabled. |
| `atp_external_registry_ca_path` | `/etc/pki/ca-trust/source/anchors/quay-ca.pem` | Optional PEM CA bundle on the Ansible execution host for a private CA. |
| `atp_external_registry_auto_discover` | `true` | Allows ATP to discover mirrors from OpenShift configuration when the URL is blank. |

If the Quay server uses a publicly trusted certificate, leave `atp_external_registry_ca_path` empty. For a private CA, install or copy the issuer bundle onto the machine running Ansible and set the absolute path. Do not turn off TLS verification to work around a trust error.

Use a Quay robot account for automation instead of a human administrator account. Grant it only the access needed for the registry check. Quay robot credentials are password-type tokens intended for automated container-client use. See the [Red Hat Quay robot account documentation](https://docs.redhat.com/en/documentation/red_hat_quay/3.18/html/about_quay_io/allow-robot-access-user-repo).

The only ATP credential pair currently needed for the remote registry probe is:

- `atp_external_registry_robot_username`: Quay robot username, commonly `organization+robot-name`.
- `atp_external_registry_robot_token`: the token/password generated for that robot.

No other ATP test currently consumes a user password. TC-18/TC-19 can also discover credential-bearing registry entries from the cluster pull-secret; those credentials are not printed or copied into this vault.

## Initialize the ATP Vault

From the repository root, run:

```bash
python3 scripts/init-atp-vault.py
```

The helper securely prompts for a Vault password and optionally for Quay robot credentials. Input is not echoed, and secrets are written only into a temporary mode-0600 file before Ansible Vault encrypts it. The resulting `group_vars/atp/vault.yml` is ignored by Git and has mode 0600. Keep the Vault password in a password manager; it is not saved by the helper.

If you prefer to initialize or edit the file manually:

```bash
mkdir -p group_vars/atp
ansible-vault create group_vars/atp/vault.yml
```

Use these variable names inside the encrypted file:

```yaml
atp_external_registry_robot_username: "organization+robot-name"
atp_external_registry_robot_token: "value-from-quay-robot-account"
```

For changes later, use `ansible-vault edit group_vars/atp/vault.yml`. Never replace the values with administrator credentials unless that is explicitly approved for the environment; a scoped robot identity is preferred.

## Run ATP with Vault enabled

The ATP role checks for the optional encrypted file and loads it before executing any cases. It suppresses output from the credential-loading task. The provided runner automatically requests the Vault password only when the encrypted file exists:

```bash
scripts/run-atp.sh
```

Or run the playbook directly:

```bash
cd playbooks
ansible-playbook --ask-vault-pass -i localhost, atp.yml
```

Without a Vault file, normal ATP execution remains available:

```bash
cd playbooks
ansible-playbook -i localhost, atp.yml
```

For automation platforms, configure an Ansible Vault credential or protected Vault password source and invoke the same playbook. Do not commit a plaintext Vault password file.

## Validation behavior and evidence handling

When robot credentials are configured, the remote OCI API probe expects HTTP 200 after authentication. A successful unauthenticated probe may accept HTTP 200 or 401 to show API reachability, but it does not prove credentials. Credential-bearing tasks use `no_log`; ATP reports include only safe status and endpoint evidence, never the token.

If Quay uses a private CA, the execution host must be able to read `atp_external_registry_ca_path` and trust the certificate chain for the configured hostname. Confirm DNS and TCP/443 reachability from the Ansible execution host. The registry pull-secret fallback may also require Podman installed on that host.

Ansible Vault protects secrets at rest. Ansible must decrypt them while running the playbook, so continue to protect execution logs, the controller, and any backup of the Vault password. See the [Ansible Vault guide](https://docs.ansible.com/projects/ansible/latest/vault_guide/vault.html) and [using encrypted variables and files](https://docs.ansible.com/projects/ansible/latest/vault_guide/vault_using_encrypted_content.html).
