# Repository layout assessment: Ansible conventions

## Purpose of `catalogs/openshift/`

`catalogs/openshift/live-api-fallback-catalog.yml` is input data for the OpenShift live API fallback workflow. It maps report posture/capability evidence requirements to Kubernetes/OpenShift resources, identifies cluster-scoped resource keys, and defines sufficiency rules. The fallback planner and evidence-loading role consume this data; it is not an Ansible task file or a role.

Keep this catalog in `catalogs/openshift/`. Moving it into a role would couple shared report planning to one implementation role and require coordinated changes to the playbook path, helper script, docs, and tests. Treat the file as a versioned project data contract.

## Existing Ansible-standard areas

The repository already uses common Ansible conventions in several places:

- `playbooks/` for top-level playbooks.
- Root `roles/<role>/{tasks,defaults,vars,handlers,templates,files,meta}/` for shared roles.
- `group_vars/` for inventory-group variables.
- `callback_plugins/` and `filter_plugins/` for Ansible plugins.
- `ansible.cfg` and inventory files for project execution configuration.

Project-specific directories such as `catalogs/`, `inputs/`, `scripts/`, `docs/`, `tests/`, and `toolkits/` are reasonable at the repository root. They do not need to be forced into role directories.

## Areas that can be standardized incrementally

### ATP toolkit

The ATP toolkit currently has case task files, variables, and report templates grouped under `toolkits/openshift-atp/`. A conventional role layout would be:

```text
toolkits/openshift-atp/
├── playbooks/
│   └── atp.yml
└── roles/openshift_atp/
    ├── defaults/main.yml
    ├── tasks/main.yml
    ├── tasks/cases/
    ├── templates/
    └── vars/main.yml
```

Keep the public playbook as a wrapper and preserve current entry points while includes and paths are migrated. Do not delete existing task or documentation files during the transition.

### Legacy health-check toolkit

If `toolkits/openshift-healthcheck/Ansible/` remains in use, standardize its capitalization and separate playbooks from role content:

```text
toolkits/openshift-healthcheck/ansible/
├── playbooks/
└── roles/openshift_healthcheck_legacy/
    ├── defaults/
    ├── handlers/
    ├── meta/
    ├── tasks/
    ├── templates/
    └── vars/
```

Before moving duplicate or copied files, map all playbook includes, scripts, docs, CI workflows, and user commands. Keep compatibility wrappers until references are updated.

### Shared report templates

The repository-level `templates/` directory is valid when multiple playbooks or roles share those templates. Move a template into a role only when it has a single clear owner and all consumers have been updated. Avoid breaking report generation paths.

## Safe migration sequence

1. Inventory references with `rg` across playbooks, roles, scripts, docs, and CI.
2. Define the target path and keep a compatibility wrapper or include at the original path.
3. Move one toolkit area at a time, updating all includes and report paths together.
4. Validate YAML, Ansible syntax, template rendering, and documented commands.
5. Keep old files until consumers are migrated and the change is reviewed; this assessment does not remove files.

## References

- [Ansible roles](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_reuse_roles.html)
- [Ansible sample setup and project structure](https://docs.ansible.com/ansible/latest/tour_guide/ansible_intro.html)
- [Ansible collections structure](https://docs.ansible.com/ansible/latest/dev_guide/developing_collections_structure.html)
- [OpenShift live API fallback catalog guide](openshift-live-api-fallback-catalog.md)
- [Cluster health extension guide](cluster-health-extension-guide.md)
