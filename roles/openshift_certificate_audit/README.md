# OpenShift certificate audit role

This role runs the read-only OpenShift certificate inventory and expiration audit. The collector and node scan helper are packaged under the role's `files/` directory so the role remains self-contained.

## Run

```bash
ansible-playbook -i localhost, playbooks/openshift_certificate_audit.yml
```

Configuration defaults are in `defaults/main.yml`. Use inventory variables, `-e`, or environment variables to override them. The audit never exports private keys, raw Secret objects, or certificate bodies.

The complete scope, privacy model, and report fields are documented in [the certificate toolkit guide](../../toolkits/openshift-healthcheck/Certificates/README.md).
