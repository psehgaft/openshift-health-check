# Ansible project and role layout

The repository uses a root-level Ansible project layout: top-level playbooks are in `playbooks/`, reusable roles are in `roles/`, inventories are in `inventories/`, and collection dependencies are declared under `requirements/`. The root `ansible.cfg` points `roles_path` at `./roles`.

## Reusable roles

| Role | Entry point | Purpose |
| --- | --- | --- |
| `openshift_atp` | `playbooks/atp.yml` | Acceptance Test Procedure with evidence reports |
| `openshift_certificate_audit` | `playbooks/openshift_certificate_audit.yml` | Read-only OpenShift certificate inventory and expiration audit |
| `openshift_healthcheck_legacy` | `playbooks/legacy/openshift_healthcheck_legacy.yml` | Compatibility wrapper for the original collector |
| Existing report roles | `playbooks/*_cluster_health_report.yml` | Canonical multi-platform cluster health reports |

Each role follows the Ansible role directories for `defaults/`, `tasks/`, `handlers/`, `templates/`, `files/`, `vars/`, `meta/`, and `tests/` as needed. Roles keep their supporting scripts and templates within their own package so role-relative lookups continue to work when the playbook is launched from the repository root.

## Specialist non-Ansible tools

`toolkits/` is reserved for supporting utilities and their documentation, including Shell, Python, Kubernetes manifests, Headlamp sources, and the architecture generator. Standalone Ansible playbooks and role task files are kept in `playbooks/` and `roles/`; supporting scripts required to make a role self-contained remain under that role's standard `files/` directory.

## Dependencies

- The canonical repository environment is described in `requirements.txt` and the setup scripts.
- Legacy role collection dependencies are in `requirements/openshift_healthcheck_legacy.yml`.
- The certificate audit uses only `ansible.builtin` modules; its empty Galaxy requirements file is kept for explicit dependency documentation.

## Entry points and checks

Run playbooks from the repository root so `ansible.cfg` and the expected inventory paths are discovered:

```bash
ansible-playbook -i inventory.ini playbooks/atp.yml
ansible-playbook -i localhost, playbooks/openshift_certificate_audit.yml
ansible-playbook -i inventories/openshift_dns_validation/hosts.ini.example \\
  playbooks/openshift_dns_validation.yml --syntax-check
```

The legacy collector needs the `community.okd` collection:

```bash
ansible-galaxy collection install -r requirements/openshift_healthcheck_legacy.yml
ansible-playbook -i localhost, playbooks/legacy/openshift_healthcheck_legacy.yml --syntax-check
```

The standard role structure follows the [Ansible role documentation](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html) and [Galaxy user guide](https://docs.ansible.com/ansible/latest/galaxy/user_guide.html).

## Report language

Repository documentation, role descriptions, and generated report labels are in English. The legacy ATP source procedure catalog at `roles/openshift_atp/vars/atp_document_cases.yml` is preserved in its original Spanish for traceability; these source entries are not included in generated reports. ATP report content comes from the English automation task descriptions and captured evidence.
