# Toolkits

This directory contains supporting utilities that complement the repository's Ansible roles and canonical health-report engine. Standalone Ansible playbooks and reusable roles live under the repository-level `playbooks/` and `roles/` directories.

| Toolkit | Purpose | Start here |
| --- | --- | --- |
| [openshift-healthcheck](openshift-healthcheck/) | Shell diagnostics, ACM manifests and scripts, certificate-audit documentation, DNS toolkit documentation, and the Headlamp report plugin | [Integration guide](../docs/three-repository-integration.md) |
| [arch-design-doc-generator](arch-design-doc-generator/) | Architecture decisions, HLD/LLD, diagrams, and work items | [Generator README](arch-design-doc-generator/README.md) |

The OpenShift ATP is now the reusable `roles/openshift_atp` role, invoked through `playbooks/atp.yml`. The former Ansible subdirectory in the specialist toolkit has been migrated to role and playbook locations. See [Ansible role layout](../docs/ANSIBLE_GALAXY_LAYOUT.md).
