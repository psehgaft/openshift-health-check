# DNS validation utility

The Ansible DNS validation playbook is maintained at `playbooks/openshift_dns_validation.yml`, with an example inventory at `inventories/openshift_dns_validation/hosts.ini.example`. This directory remains for specialist DNS documentation and supporting non-Ansible material.

Run from the repository root after replacing the example inventory addresses:

```bash
ansible-playbook -i inventories/openshift_dns_validation/hosts.ini.example \\
  playbooks/openshift_dns_validation.yml --syntax-check
ansible-playbook -i inventories/openshift_dns_validation/hosts.ini.example \\
  playbooks/openshift_dns_validation.yml
```

The playbook collects DNS evidence from each inventory host. It does not change resolver configuration.
