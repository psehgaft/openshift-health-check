# Ansible layout migration status

The former mixed Ansible toolkits have been reorganized into root-level playbooks, reusable roles, inventories, and collection requirements. The ATP is now the `openshift_atp` role; certificate auditing is packaged as `openshift_certificate_audit`; the legacy health-check collector is in `openshift_healthcheck_legacy`; and DNS validation is a standalone playbook.

Standalone Shell, Python, Kubernetes-manifest, Headlamp, and architecture-generator assets remain in `toolkits/`. Supporting scripts that a reusable role needs at runtime stay under that role's standard `files/` directory so the role remains self-contained.

See [Ansible Galaxy-compatible layout](ANSIBLE_GALAXY_LAYOUT.md) for the complete structure, entry points, dependency installation, and validation commands.
