# OpenShift health-check specialist toolkit

This directory keeps the non-Ansible specialist utilities and their user guides. Reusable Ansible content has been moved to the repository-level `roles/` and `playbooks/` directories.

| Component | Location | Purpose |
| --- | --- | --- |
| Shell diagnostics, CER collection, and report renderer | [Shell/](Shell/README.md) | Standalone Bash and Python diagnostics |
| ACM toolkit | [ACM/](ACM/ACM_Health_Check_Runbook.md) | ACM health checks, manifests, and operational runbooks |
| Headlamp RBAC report plugin | [Shell/headlamp-openshift-rbac-html-report/](Shell/headlamp-openshift-rbac-html-report/README.md) | Headlamp plugin source and build instructions |
| Certificate audit guide | [Certificates/](Certificates/README.md) | Scope and report interpretation for the certificate-audit role |

The corresponding Ansible entry points are:

- ATP role: `roles/openshift_atp`, run with `playbooks/atp.yml`.
- Certificate audit role: `roles/openshift_certificate_audit`, run with `playbooks/openshift_certificate_audit.yml`.
- DNS validation playbook: `playbooks/openshift_dns_validation.yml`.
- Legacy health-check role: `roles/openshift_healthcheck_legacy`, retained for compatibility.
