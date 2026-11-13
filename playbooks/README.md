# Ansible Playbooks: Prerequisites, Variables, Execution, and Results

This page documents every runnable playbook under \`playbooks/\`. Commands are intended to be run from the repository root so Ansible loads the repository configuration and relative paths correctly.

## Common prerequisites

- Linux or macOS with Python 3.11 or later recommended.
- Ansible Core matching the supported range in [\`requirements.txt\`](../requirements.txt); install the repository's pinned environment with \`./scripts/setup-ansible-venv.sh\`.
- \`oc\` for OpenShift playbooks and \`kubectl\` for Kubernetes report playbooks.
- A valid cluster context on the machine running Ansible. Verify it with \`oc whoami\` or \`kubectl cluster-info\`.
- Cluster permissions sufficient for the selected checks. Health reports and ATP include cluster-scoped reads; ATP cases that create resources or perform maintenance need the corresponding write permissions.
- Network access from the Ansible execution host to the Kubernetes API. Some collectors additionally need node SSH, registry, or support-image access; those are described in their sections.
- Ansible collection dependencies where noted below.

Prepare the local environment:

\`\`\`bash
git clone https://github.com/psehgaft/openshift-health-check.git
cd openshift-health-check
./scripts/setup-ansible-venv.sh
source .venv/bin/activate
\`\`\`

Use \`ansible-playbook --syntax-check <playbook>\` for a syntax-only check. It does not connect to a cluster or validate permissions.

## Playbook catalog

| Playbook | Purpose | Required cluster context | Main results |
| --- | --- | --- | --- |
| [\`openshift_cluster_health_report.yml\`](openshift_cluster_health_report.yml) | Detailed OpenShift health and posture report, live or from collected evidence | \`oc\` | Markdown and JSON; optional HTML/PDF; evidence workspace |
| [\`k8s_cluster_health_report.yml\`](k8s_cluster_health_report.yml) | Generic Kubernetes health report | \`kubectl\` | Markdown and JSON; optional HTML/PDF; evidence workspace |
| [\`aks_cluster_health_report.yml\`](aks_cluster_health_report.yml) | AKS profile using the Kubernetes report engine | \`kubectl\` configured for AKS | Same Kubernetes report outputs |
| [\`eks_cluster_health_report.yml\`](eks_cluster_health_report.yml) | EKS profile using the Kubernetes report engine | \`kubectl\` configured for EKS | Same Kubernetes report outputs |
| [\`gke_cluster_health_report.yml\`](gke_cluster_health_report.yml) | GKE profile using the Kubernetes report engine | \`kubectl\` configured for GKE | Same Kubernetes report outputs |
| [\`rancher_cluster_health_report.yml\`](rancher_cluster_health_report.yml) | Rancher-managed Kubernetes profile | \`kubectl\` configured for the target cluster | Same Kubernetes report outputs |
| [\`minikube_cluster_health_report.yml\`](minikube_cluster_health_report.yml) | Lightweight Minikube profile | \`kubectl\` configured for Minikube | Same Kubernetes report outputs |
| [\`development_k8s_cluster_health_report.yml\`](development_k8s_cluster_health_report.yml) | Shorter, development-focused Kubernetes report | \`kubectl\` | Markdown and JSON; HTML/PDF disabled by default |
| [\`atp.yml\`](atp.yml) | OpenShift Acceptance Test Procedure with captured evidence | \`oc\` | ATP Markdown and HTML reports |
| [\`openshift_certificate_audit.yml\`](openshift_certificate_audit.yml) | Certificate inventory, chain, and expiration audit | \`oc\`, and optionally node access | Certificate audit artifacts under the audit output directory |
| [\`openshift_dns_validation.yml\`](openshift_dns_validation.yml) | DNS and host resolver checks against inventory hosts | SSH to inventory targets | Per-host Ansible task output |
| [\`legacy/openshift_healthcheck_legacy.yml\`](legacy/openshift_healthcheck_legacy.yml) | Compatibility entry point for the legacy OpenShift collector | \`oc\` | Legacy collector output |

## Cluster health report playbooks

### OpenShift report

Prerequisites:

- An authenticated \`oc\` context for the target cluster.
- Read access to the cluster resources covered by the selected profile.
- For live must-gather, inspect, Insights, or sosreport collection, the required cluster permissions, image access, local storage, and node access for the selected collectors. These collectors may create temporary resources or consume significant cluster and node resources. Review the collection settings before enabling them on production systems.
- For collected mode, a readable support bundle or must-gather directory on the Ansible host.

Run a standard report:

\`\`\`bash
oc login https://api.<cluster-name>.<domain>:6443
oc whoami
ansible-playbook -i inventory.ini playbooks/openshift_cluster_health_report.yml \
  -e report_mode=live \
  -e report_performance_profile=standard \
  -e collect_live_sosreport=false
\`\`\`

Run from a previously collected evidence bundle:

\`\`\`bash
ansible-playbook -i inventory.ini playbooks/openshift_cluster_health_report.yml \
  -e report_mode=collected \
  -e collected_evidence_root=/path/to/case-bundle
\`\`\`

Common variables:

| Variable | Definition |
| --- | --- |
| \`report_mode\` | Evidence source: \`auto\`, \`live\`, or \`collected\`. |
| \`report_performance_profile\` | Collection depth: \`fast\`, \`standard\`, or \`full\`. |
| \`report_output_dir\` | Directory for final reports and the run evidence workspace. Default is \`reports/\` relative to the repository. |
| \`report_basename\` | Base filename used for generated reports. |
| \`report_generate_html\`, \`report_generate_pdf\` | Enable or disable those optional report formats. |
| \`report_run_mode\` | Start a new run (\`fresh\`) or resume the last failed run (\`resume_last_failure\`). |
| \`collected_evidence_root\` | Directory containing an offline must-gather, inspect archive, or support-case bundle. |
| \`selected_postures\` | Comma-separated posture keys to include; empty means use the configured profile. |
| \`selected_capabilities\` | Comma-separated capability keys to include; empty means use the configured profile. |
| \`collect_live_sosreport\` | Whether to run node-level sosreport collection. Keep false unless approved. |
| \`collect_live_must_gather\`, \`collect_live_inspect\`, \`collect_live_insights_archive\` | Enable individual live support collectors. |
| \`collection_parallelism\`, \`analysis_parallelism\` | Maximum parallel work for evidence collection and analysis. |
| \`collection_command_timeout_seconds\` | Timeout for an individual collector command. |
| \`cluster_health_profile_source_path\` | Input profile defining the OpenShift checks and thresholds. |
| \`cluster_health_profile_override_source_path\` | Optional site-specific profile overlay. |

Other supported variables include collector safety gates, RBAC checks, artifact retention, API fallback catalogs, report issue limits, thresholds, and redaction controls. Their defaults and descriptions are maintained in the \`vars\` block of [\`openshift_cluster_health_report.yml\`](openshift_cluster_health_report.yml) and the report roles. Change those values through \`-e\` or inventory/group variables; do not edit generated evidence.

Results are written to the configured \`report_output_dir\`. The default playbook enables HTML and PDF generation. Markdown and JSON are the stable machine- and human-readable report formats. The run workspace contains intermediate collection, posture, and report payload artifacts. See [Quick Start](../docs/QUICKSTART.md) for profile selection, resume behavior, and CI filenames.

### Kubernetes report and provider-specific wrappers

The generic Kubernetes report uses \`kubectl\` and the Kubernetes health profile. It can also be invoked through the AKS, EKS, GKE, Rancher, and Minikube wrapper playbooks. The wrappers import the generic playbook and set the provider profile; use the wrapper matching the active cluster context.

Examples:

\`\`\`bash
ansible-playbook -i inventory.ini playbooks/k8s_cluster_health_report.yml
ansible-playbook -i inventory.ini playbooks/aks_cluster_health_report.yml
ansible-playbook -i inventory.ini playbooks/eks_cluster_health_report.yml
ansible-playbook -i inventory.ini playbooks/gke_cluster_health_report.yml
ansible-playbook -i inventory.ini playbooks/rancher_cluster_health_report.yml
ansible-playbook -i inventory.ini playbooks/minikube_cluster_health_report.yml
ansible-playbook -i inventory.ini playbooks/development_k8s_cluster_health_report.yml
\`\`\`

Prerequisites:

- \`kubectl\` installed and authenticated against the intended cluster.
- Read permissions for the resources in the selected Kubernetes profile.
- For a provider wrapper, use a kubeconfig context that points to that provider's cluster. The playbook does not create cloud credentials or change the current context.

Common variables:

| Variable | Definition |
| --- | --- |
| \`kube_cli\` | CLI executable used to query the cluster. The generic playbook defaults to \`kubectl\`. |
| \`provider_family\` | Selects the provider profile. Wrapper playbooks set this to \`aks\`, \`eks\`, \`gke\`, \`rancher\`, or \`minikube\`. |
| \`cluster_profile_mode\` | Chooses the production, development, or lightweight profile. |
| \`report_mode\`, \`report_output_dir\`, \`report_basename\` | Evidence mode and report naming/output location. |
| \`report_generate_html\`, \`report_generate_pdf\` | Optional output formats. |
| \`report_run_mode\` | \`fresh\` or \`resume_last_failure\`. |
| \`kubernetes_cluster_health_profile_source_path\` | Profile file used for provider and environment-specific checks. |
| \`collection_parallelism\`, \`analysis_parallelism\`, \`collection_command_timeout_seconds\` | Runtime controls for evidence collection and analysis. |
| \`selected_postures\`, \`selected_capabilities\` | Optional comma-separated scope filters where supported by the selected profile. |

The development playbook selects the development profile and reduces collection limits; it disables HTML/PDF by default. Reports are written under \`reports/\` unless overridden.

### ATP

Prerequisites:

- An authenticated \`oc\` session (\`oc whoami\` must succeed).
- Permissions required by enabled ATP cases. Cases that create resources need namespace-level writes; node maintenance, registry checks, and cluster configuration cases require broader privileges.
- For encrypted ATP credentials, create \`group_vars/atp/vault.yml\` using Ansible Vault and supply its password with \`--ask-vault-pass\` or \`--vault-password-file\`.
- Optional external registry checks need reachable DNS/network access. If using a private CA, configure the issuing PEM bundle; credentials should be supplied via Vault or environment variables and must never be committed in plaintext.

Run all enabled ATP cases:

\`\`\`bash
ansible-playbook -i inventory.ini playbooks/atp.yml
\`\`\`

Run selected cases by tags, for example TC-18 and TC-19:

\`\`\`bash
ansible-playbook -i inventory.ini playbooks/atp.yml --tags "tc18,tc19"
\`\`\`

Supply a Vault password interactively:

\`\`\`bash
ansible-playbook --ask-vault-pass -i inventory.ini playbooks/atp.yml
\`\`\`

Important ATP variables:

| Variable | Definition |
| --- | --- |
| \`expected_ocp_version\` | Expected OpenShift version used by the version case and report metadata. |
| \`atp_report_dir\`, \`atp_report_basename\` | Report output directory and filename prefix. Markdown and HTML are generated. |
| \`run_tcNN_*\` | Boolean per-case enable/disable switches. Disabled cases are recorded as Skipped. The complete toggle list is in [ATP defaults](../roles/openshift_atp/defaults/main.yml). |
| \`atp_external_registry_url\` | Optional external OCI registry origin; the check appends the API path. |
| \`atp_external_registry_auto_discover\` | Discover an external endpoint from cluster image mirror configuration when no explicit URL is set. |
| \`atp_external_registry_validate_certs\`, \`atp_external_registry_ca_path\` | TLS validation switch and optional PEM CA bundle path on the Ansible host. Keep validation enabled and provide the CA where needed. |
| \`atp_external_registry_robot_username\`, \`atp_external_registry_robot_token\` | Robot-account credentials. Prefer encrypted Vault variables or \`ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME\` / \`ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN\` environment variables. |
| \`atp_api_cert_self_signed\`, \`atp_ingress_cert_self_signed\` | Mark intentionally self-signed API/Ingress certificates; the corresponding certificate case is skipped with a note. |
| \`tc26_manual_execution\`, \`tc27_manual_execution\`, \`tc62_manual_execution\` | Attest that the corresponding operation was completed manually; the ATP performs read-only post-operation health checks. |
| \`tc27_worker_node\` | Worker node to verify for TC-27 manual evidence or the gated reboot. |
| \`tc26_reboot_confirmation\`, \`tc27_reboot_confirmation\` | Exact confirmation strings required before enabling automated reboots. Leave empty for normal runs. |
| \`tc62_*\` | Guarded etcd restore inputs. Restore is disabled by default and requires the documented topology, snapshot, host, release, SSH, and confirmation gates. See the [ATP guide](../docs/ATP_PLAYBOOK_GUIDE.md) and [manual evidence flags](../docs/ATP_MANUAL_EXECUTION_FLAGS.md). |

Do not enable disruptive cases solely to obtain a Pass. Review each case's runbook and confirmations. Manual flags attest to a human-run operation but do not independently prove that the operation occurred.

Results: the playbook prints a summary and creates timestamped \`ATP-Report-*.md\` and \`ATP-Report-*.html\` files in \`atp_report_dir\` (default \`reports/\`). The report includes per-case status, command evidence, conclusion, and additional comments.

### OpenShift certificate audit

Prerequisites:

- Authenticated \`oc\` context with permissions to read the relevant cluster certificates, routes, secrets metadata, and node information.
- Python interpreter used by Ansible and the \`openssl\` CLI.
- If \`scan_nodes: true\`, \`oc debug node\` permission and capacity to create temporary debug pods. Disable this option if node scanning is not approved.
- If route endpoint scanning is enabled, the execution host must resolve and connect to route hosts.

Run:

\`\`\`bash
ansible-playbook -i localhost, playbooks/openshift_certificate_audit.yml
\`\`\`

Configuration variables (defaults in [the certificate role](../roles/openshift_certificate_audit/defaults/main.yml)):

| Variable | Definition |
| --- | --- |
| \`audit_output_root\` | Directory where the audit report and evidence are written. Can also be set with \`AUDIT_OUTPUT_ROOT\`. |
| \`audit_kubeconfig\` | Optional kubeconfig path; defaults to the \`KUBECONFIG\` environment variable or the current context. |
| \`audit_context\` | Optional kubeconfig context name. |
| \`warning_days\`, \`critical_days\` | Expiration thresholds for warning and critical findings. |
| \`scan_nodes\`, \`node_scan_timeout\` | Collect node certificate evidence through temporary debug pods and the per-node timeout. |
| \`scan_route_endpoints\` | Probe active TLS chains for admitted Route hosts. |
| \`max_route_endpoints\`, \`endpoint_timeout\` | Bound the number of route probes and timeout per endpoint. |
| \`cluster_query_timeout\`, \`require_complete_permissions\` | API query timeout and whether incomplete permissions should fail the audit. |
| \`oc_binary\`, \`openssl_binary\`, \`python_binary\` | Executable paths used by the audit. |

Results are stored under \`audit_output_root\`, defaulting to \`reports/certificate-audit/\`. The audit avoids exporting private keys, raw Secret objects, or certificate bodies. See the [certificate audit guide](../toolkits/openshift-healthcheck/Certificates/README.md) for artifact names and privacy details.

### OpenShift DNS validation

This playbook targets remote hosts from Ansible inventory (not the Kubernetes API). It requires SSH connectivity, privilege escalation, and \`hostname\`, \`getent\`, \`dig\`, \`nslookup\`, and \`ping\` where their corresponding checks are expected. The host must have DNS tools installed and allow ICMP if ping checks are expected.

Example:

\`\`\`bash
ansible-playbook \
  -i inventories/openshift_dns_validation/hosts.ini.example \
  playbooks/openshift_dns_validation.yml \
  -e expected_domain=example.com
\`\`\`

| Variable | Definition |
| --- | --- |
| \`expected_domain\` | DNS suffix expected for the target hosts. The playbook defaults to \`example.com\`; pass the real DNS domain with \`-e\` or inventory variables. |
| \`inventory_hostname\` | Ansible inventory name resolved through the target host's configured resolver. |
| \`ansible_default_ipv4.address\` | Address discovered by Ansible facts and used for reverse lookup. |

Results are printed per host in Ansible task output. The playbook does not generate a Markdown/HTML report or change DNS configuration.

### Legacy OpenShift health check

This is a compatibility entry point for the original health-check role. Prefer [\`openshift_cluster_health_report.yml\`](openshift_cluster_health_report.yml) for new reports.

Prerequisites:

- Authenticated \`oc\` context and access to resources queried by the legacy role.
- Install the declared collection dependency:

\`\`\`bash
ansible-galaxy collection install -r requirements/openshift_healthcheck_legacy.yml
ansible-playbook -i inventory.ini playbooks/legacy/openshift_healthcheck_legacy.yml
\`\`\`

Results follow the legacy role's report configuration. Review [the legacy role defaults](../roles/openshift_healthcheck_legacy/defaults/main.yml) and role documentation before execution.

## References

- [Ansible playbooks](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html)
- [Ansible variables and precedence](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html)
- [Ansible Galaxy roles](https://docs.ansible.com/ansible/latest/galaxy/user_guide.html)
- [OpenShift CLI documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cli_tools/openshift-cli-oc)
- [Kubernetes kubectl reference](https://kubernetes.io/docs/reference/kubectl/)
