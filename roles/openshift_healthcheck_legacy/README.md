# Legacy OpenShift health-check role

This role preserves the original environment-driven OpenShift collector while placing it in a standard Ansible role layout. The current repository health-report engine remains the recommended implementation; this role is retained for compatibility with existing workflows.

## Run

From the repository root:

```bash
ansible-galaxy collection install -r requirements/openshift_healthcheck_legacy.yml
ansible-playbook -i localhost, playbooks/legacy/openshift_healthcheck_legacy.yml
```

Set `OPENSHIFT_API_URL` and either `OPENSHIFT_USER`/`OPENSHIFT_PASSWORD` or `OPENSHIFT_TOKEN` in the environment before running. Do not place credentials in tracked files.

## Role layout

Tasks, defaults, variables, handlers, templates, metadata, and the role test playbook are kept in their standard role directories. The repository entry point is `playbooks/legacy/openshift_healthcheck_legacy.yml`.

This is a legacy collector. It is not part of the unified `suite` workflow. See the [integration guide](../../docs/three-repository-integration.md) for the canonical health-check workflow.
