# Ansible project and Galaxy-compatible role layout

The repository uses Ansible's standard project layout. Runnable entry points live in `playbooks/`, reusable role content lives in `roles/`, example inventories live in `inventories/`, and collection dependencies live in `requirements/`. The root `ansible.cfg` sets `roles_path = ./roles`.

## Repository layout

```text
openshift-health-check/
├── ansible.cfg
├── inventories/
├── playbooks/
│   ├── atp.yml
│   ├── openshift_certificate_audit.yml
│   ├── openshift_dns_validation.yml
│   └── legacy/
├── roles/
│   ├── openshift_atp/
│   ├── openshift_certificate_audit/
│   └── openshift_healthcheck_legacy/
├── requirements/
├── scripts/                           # Repository validation and shared runtime helpers
├── toolkits/
│   ├── openshift-healthcheck/         # Standalone, non-Ansible utilities and guides
│   └── arch-design-doc-generator/     # Non-Ansible generator
└── docs/
```

## Reusable roles

| Role | Entry point | Purpose |
| --- | --- | --- |
| `openshift_atp` | `playbooks/atp.yml` | ATP case execution and Markdown/HTML evidence reports |
| `openshift_certificate_audit` | `playbooks/openshift_certificate_audit.yml` | OpenShift certificate inventory and expiration audit |
| `openshift_healthcheck_legacy` | `playbooks/legacy/openshift_healthcheck_legacy.yml` | Compatibility wrapper for the original collector |
| Health-report roles | `playbooks/*_cluster_health_report.yml` | Canonical multi-platform health reporting |

The ATP uses the standard reusable role directories:

```text
roles/openshift_atp/
├── defaults/main.yml
├── files/
├── meta/main.yml
├── tasks/
├── templates/
└── vars/
```

The role's `meta/main.yml` declares its Galaxy metadata. Its runnable entry point stays in `playbooks/atp.yml`; that playbook invokes the role through the configured `roles_path`. The ATP case files, report templates, defaults, source-procedure catalog, and guarded helper script remain within the role so its runtime assets stay together. The site-specific `roles/openshift_atp/vars/main.yaml` file is optional and is not tracked.

The source ATP procedure catalog in `roles/openshift_atp/vars/atp_document_cases.yml` is preserved in its original Spanish for traceability. Repository documentation, automation descriptions, and generated report labels are in English; the Spanish source catalog is not rendered into reports.

These are project-local Galaxy-compatible roles. This repository does not currently publish an Ansible collection. If the roles are to be distributed independently through Galaxy, package them in a dedicated role repository or add collection metadata and use the Ansible collection layout.

## Placement rules

- Put Ansible playbooks in `playbooks/` and reusable role code in `roles/<role_name>/`.
- Keep a role's defaults, tasks, templates, files, vars, and metadata inside that role.
- Keep inventories under `inventories/` and collection dependencies under `requirements/`.
- Keep standalone Shell, Python, Kubernetes-manifest, Headlamp, and architecture-generator assets under `toolkits/`.
- Keep repository validators and shared project runtime helpers under `scripts/`. If a script is required only by one role at runtime, place it under that role's `files/` directory.
- Do not keep duplicate Ansible roles or task trees under `toolkits/`. Toolkit documentation may link to the canonical role and playbook.

The specialist toolkit remains in [`toolkits/openshift-healthcheck`](../toolkits/openshift-healthcheck/). Its Ansible certificate audit and DNS entry points were moved to `roles/` and `playbooks/`; the toolkit keeps their documentation and standalone specialist components. The architecture generator remains under [`toolkits/arch-design-doc-generator`](../toolkits/arch-design-doc-generator/).

## Dependencies and execution

The Python/Ansible environment is described in the root `requirements.txt` and setup scripts. Ansible collection dependencies are declared under `requirements/`.

Run from the repository root so that `ansible.cfg`, relative paths, and the default inventory are discovered:

```bash
source .venv/bin/activate
ansible-playbook -i inventory.ini playbooks/atp.yml
ansible-playbook -i localhost, playbooks/openshift_certificate_audit.yml
ansible-playbook -i inventories/openshift_dns_validation/hosts.ini.example \
  playbooks/openshift_dns_validation.yml --syntax-check
```

The legacy collector needs the `community.okd` collection:

```bash
ansible-galaxy collection install -r requirements/openshift_healthcheck_legacy.yml
ansible-playbook -i localhost, playbooks/legacy/openshift_healthcheck_legacy.yml --syntax-check
```

Run the repository validator after changes to playbooks, roles, or documentation that affect execution paths:

```bash
scripts/validate_repo.sh
```

## References

- [Ansible roles in playbooks](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html)
- [Ansible Galaxy user guide](https://docs.ansible.com/ansible/latest/galaxy/user_guide.html)
