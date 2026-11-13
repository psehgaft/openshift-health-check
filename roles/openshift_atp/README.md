# OpenShift Acceptance Test Procedure role

This Ansible role executes the OpenShift ATP and renders Markdown and HTML evidence reports. The role follows the standard Ansible role layout and is invoked by the stable repository entry point, `playbooks/atp.yml`.

## Run

From the repository root, activate the project virtual environment and authenticate with `oc`:

```bash
source .venv/bin/activate
oc whoami
ansible-playbook -i inventory.ini playbooks/atp.yml
```

If you are already in the `playbooks/` directory, this also works:

```bash
ansible-playbook atp.yml
```

The directory includes its own `ansible.cfg`, which points Ansible to the repository's `roles/`, `callback_plugins/`, and `filter_plugins/`. This keeps the short command working without installing the role globally or setting a machine-specific `roles_path`.

Reports are written to `reports/` by default. Override `atp_report_dir` to select another directory.

## Layout

- `defaults/main.yml`: overridable case toggles, report paths, and thresholds.
- `tasks/main.yml`: authentication, setup, case execution, evidence enrichment, and report rendering.
- `tasks/main_cases.yml`: ordered case-section loader.
- `tasks/*.yml`: ATP case sections and reusable probe tasks.
- `templates/`: Markdown and HTML report templates.
- `files/tc62_etcd_restore.sh`: guarded helper for the approved etcd restore case.
- `vars/atp_document_cases.yml`: retained source-language reference catalog for traceability; its original Spanish text is not rendered in the English execution reports.

## Local overrides

Create `roles/openshift_atp/vars/main.yaml` for site-specific overrides. This file is optional and ignored by Git. For example, to record TC-55 as skipped when the API certificate is intentionally self-signed:

```yaml
atp_api_cert_self_signed: true
```

You can also override variables through inventory or `-e`. Disruptive tests such as node reboot and etcd restore remain gated by explicit confirmations. Review [the ATP guide](../../docs/ATP_PLAYBOOK_GUIDE.md) before enabling them.
