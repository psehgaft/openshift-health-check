# Acceptance Test Plan (ATP) Playbook - User Guide

## Overview
This Ansible playbook automates the acceptance verification procedures defined in the **ATP - Red Hat OpenShift Container Platform 4.20** specification. It covers **73 numbered test cases**; TC-67 is recorded as two independently reported sub-cases, producing 74 report records. TC-23 runs first and creates or verifies `testproject` so later cases can use it. TC-30 runs last because it deletes `testproject`. The cases span core OpenShift components, infrastructure governance, application scheduling, storage resilience, networking, and Telco 5G performance tuning (HugePages, LACP Bonding, MTU 9000, and SR-IOV VFs).

## Directory Structure
```text
openshift-health-check/
├── playbooks/atp.yml
├── toolkits/
│   ├── openshift-atp/                 # ATP tasks, variables, and report templates
│   ├── openshift-healthcheck/         # Specialist health-check tools
│   └── arch-design-doc-generator/     # Architecture documentation generator
└── docs/ATP_PLAYBOOK_GUIDE.md
```

The ATP implementation is in [toolkits/openshift-atp](../toolkits/openshift-atp/). Each automated test stores the invoked command, full stdout/stderr, exit code, expected result, and conclusion. Reports also include the original procedure and expected result from the supplied ATP source document as a separate reference, so readers can distinguish documented steps from commands actually executed. The playbook renders an ATP-specific Markdown and HTML report template alongside the existing health-check reporting system.

## Reports

Both files are generated in `reports/` unless `atp_report_dir` is overridden:

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

The HTML uses a two-column procedure record matching the supplied form: date, time, description, topology, procedure, expected result and observed evidence, Pass/Fail/Skipped conclusion, and additional comments with remediation guidance for failures.

## External registry checks (TC-18 and TC-19)

TC-18 probes both available endpoint types and passes when at least one registry API is usable. If only the external registry is configured and reachable, the case passes and the report notes that the cluster is using the external registry only. If both endpoints are configured but one fails, the case still passes when the other is usable and adds a comment describing the failed endpoint. TC-19 separately checks internal registry pod placement and logs, so it has additional internal-registry conditions. Discovery reads cluster mirror definitions from ImageDigestMirrorSet, ImageTagMirrorSet, and ImageContentSourcePolicy resources. It selects the endpoint only when exactly one unique mirror is found. Inspect the source configuration with `oc get imagedigestmirrorsets,imagetagmirrorsets -o yaml` and, on clusters using the legacy API, `oc get imagecontentsourcepolicies.operator.openshift.io -o yaml`.

Configure the URL in `toolkits/openshift-atp/vars/main.yml` when the cluster has multiple mirror endpoints or the external registry is not represented in those resources:

```yaml
atp_external_registry_url: "https://quay.example.com"
atp_external_registry_validate_certs: true
# Absolute PEM CA bundle path on the Ansible controller for private/self-signed CA
atp_external_registry_ca_path: "/etc/pki/ca-trust/source/anchors/quay-issuing-ca.pem"
```

A registry robot token cannot be obtained safely or reliably from cluster mirror settings. Supply the robot username and token from the bastion environment. The token is used as the robot account's HTTP Basic password and is excluded from task output and reports:

```bash
export ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME='robot$organization+account'
read -rsp 'External registry robot token: ' ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN
printf '\n'
export ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN
ansible-playbook -i inventory.ini playbooks/atp.yml
unset ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN
```

Without robot credentials, HTTP 200 or 401 means the OCI v2 API is reachable, but authentication is not verified. When credentials are supplied, the external API probe requires HTTP 200. Keep TLS verification enabled. For a private registry CA, set `atp_external_registry_ca_path` to the issuing CA PEM bundle on the Ansible controller. The CA must validate the certificate chain presented by the configured registry hostname. Disabling certificate validation should be limited to a temporary diagnostic; do not use it as the permanent acceptance configuration.

## Mandatory Tags
Every task in the ATP playbook is tagged with:
- `general`: Tests covering standard OpenShift Container Platform features.
- `telco`: Tests covering Telco architecture, hardware acceleration, and profile validations.
- Specific Section Tags: `services_check`, `administration`, `workloads`, `logging`, `storage`, `networking`, `security`, `backup_restore`, `telco_support`.
- Specific Case Tags: `tc01`, `tc02`, ..., `tc73`.

## Skipping and Customizing Tests
You can skip tasks in two different ways:

### 1. Using Ansible Tags (`--skip-tags` or `--tags`)
```bash
# Run all tests EXCEPT disruptive reboot and restore tests:
ansible-playbook -i inventory.ini playbooks/atp.yml --skip-tags "tc26,tc27,tc62"

# Run only Telco and Networking validations:
ansible-playbook -i inventory.ini playbooks/atp.yml --tags "telco,networking,sriov"
```

### 2. Using Feature Toggles in `toolkits/openshift-atp/vars/main.yml` or CLI Extra Vars
Automated cases can be selectively run with the documented `run_tc*` variables. TC-26 and TC-27 are opt-in, disabled by default, and require exact reboot confirmations. TC-62 is opt-in and remains `Skipped` by default; it executes only when the operator supplies the exact restore confirmation and all preflight gates pass.

## Output Reports
The playbook writes a Markdown report and a self-contained HTML report to `reports/` by default. Set `atp_report_dir` to change the destination.

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

Both formats contain a run summary and per-test records. TC-23 is the first case and ensures `testproject` exists. TC-58 creates or updates `test-atp` in `testproject`, making reruns safe when the Secret already exists. TC-30 runs after all other ATP cases and deletes `testproject` as the final cleanup action. TC-17 reads API server and control-plane logs through the Kubernetes API. TC-18 checks the internal registry service when present, otherwise it tests the configured external registry endpoint from a worker. TC-20 requires a persistent storage backend for the internal registry. For an external registry, it checks endpoint reachability but records that storage persistence still needs an authenticated push/pull validation or provider-side health check. The HTML follows the supplied form layout and includes the procedure, expected result, captured command output, conclusion, and comments with remediation guidance for failures.


## TC-22: logging API version compatibility

TC-22 reads the actual release from `oc get clusterversion version` and selects the API checks by OpenShift version. On OCP 4.19 and later, it queries only `ClusterLogForwarder` in `observability.openshift.io`; it does not query legacy `ClusterLogging` or `logging.openshift.io` APIs. On earlier releases, it checks the legacy APIs and retains the modern `ClusterLogForwarder` as a compatibility fallback. All versions also require logging pods in `openshift-logging` to be Running and ready. If release detection fails, TC-22 fails with the version query evidence instead of guessing which API to use.

The API removal is associated with Red Hat OpenShift Logging 6, whose API group is `observability.openshift.io`; the Logging operator has a release/support cadence distinct from the OpenShift Container Platform release. The ATP applies the requested 4.19 version threshold to select the API policy.

If the case fails, inspect the API group available on the cluster, the matching resource status conditions, the Logging/Loki/Cluster Observability Operators, pod events, and container logs. Do not create a legacy CRD to satisfy the ATP.


- **TC-53:** Creates or verifies ServiceAccount `atp-test` in `testproject`; an existing account is reported and left unchanged.


## TC-64: must-gather and node sosreport

TC-64 runs `oc adm must-gather`, packages and integrity-checks the result, verifies host-root access on a worker, and generates/copies an integrity-checked `sosreport`. The report output for must-gather is intentionally concise: it states whether generation succeeded and the archive path; the full collection log is saved as `must-gather.log` in the same diagnostics directory. The sosreport output similarly states status/path/checksum, with detailed command output saved in `sosreport.log`. For the sosreport, the task uses `podman container runlabel run` with the `registry.redhat.io/rhel9/support-tools` image; `toolbox run ...` is not the correct invocation and treats `run` as a command inside the container. TC-64 Pass requires all stages: a non-empty valid must-gather archive, successful host-root check, a successful sosreport command, and a non-empty valid sosreport copied to the ATP report directory. Set `tc64_node_target` to select a worker; otherwise the first worker is used. For disconnected clusters, mirror `registry.redhat.io/rhel9/support-tools:latest` and set `tc64_support_tools_image` in `toolkits/openshift-atp/vars/main.yml` to the mirror image. These archives can contain sensitive cluster and host data, so protect the diagnostics directory and review it before sharing.

## TC-67a: PVC, iSCSI, and multipath

TC-67a inventories Bound PVCs, PV volume types, and StorageClasses. It auto-detects SAN classes from common names (such as `iscsi`, `fibre`, `fc`, or `san`), CSI provisioner metadata, and protocol parameters, then correlates the classes with PVs and PVCs. If no SAN-backed PV or SAN StorageClass is found, the multipath-specific result is **Skipped / not applicable**; an inactive daemon by itself does not fail a cluster that does not use SAN. For detected SAN storage, it checks that a PVC is Bound and inspects `/etc/iscsi`, iSCSI sessions, `multipathd`, and `multipath -ll` on workers. A Pass requires accessible host diagnostics, active multipathd, and active/ready paths (plus an active iSCSI session for iSCSI-backed storage). Custom StorageClass names whose CSI metadata does not identify SAN must be listed explicitly in `tc67a_san_storage_class_names` in `toolkits/openshift-atp/vars/main.yml`; for example, `tc67a_san_storage_class_names: ["custom-san-sc"]`.


## TC-55: API certificate validation

TC-55 reads the API server URL from the active kubeconfig, then validates that endpoint’s TLS chain, hostname SAN, and remaining validity (`atp_api_cert_min_validity_days`, default: 7 days). It uses `oc config view --raw --flatten --minify` so both embedded `certificate-authority-data` and a kubeconfig `certificate-authority` file path can be used. If the flattened view has no CA, verify the active `KUBECONFIG` and context, or set `atp_api_cert_ca_path` to a PEM CA bundle on the Ansible controller. The task fails rather than skipping TLS trust validation. Keep TLS verification enabled; do not use an insecure bypass. This replaces a brittle subject-string search that failed on normal OpenSSL output formatting. Set the threshold or optional CA path in `toolkits/openshift-atp/vars/main.yml` or as Ansible extra vars.


## TC-28: install and verify the Self Node Remediation Operator

The previous test subscribed to package `sample-operator`, which is not present in the healthy `redhat-operators` catalog. That is why OLM reported `ConstraintsNotSatisfiable` and never populated `.status.installedCSV`.

TC-28 installs package `self-node-remediation` from the `redhat-operators` CatalogSource, channel `stable`, in the dedicated `openshift-workload-availability` namespace. The playbook applies the Namespace, OperatorGroup, and Subscription declaratively, waits up to ten minutes for the installed ClusterServiceVersion (CSV) to reach `Succeeded`, and requires the controller Deployment to have all desired replicas available. It discovers SNRO DaemonSets by name instead of assuming a hard-coded resource name; any discovered matching DaemonSet must be Ready on all targeted nodes. If no matching DaemonSet is returned, that is recorded as an optional-resource note and does not invalidate an otherwise successful CSV and controller rollout. The default `SelfNodeRemediationConfig` and `SelfNodeRemediationTemplate` are recorded when present.

The case is a deployment and readiness check only. It does not create a remediation request or simulate a node failure, because those actions can reboot nodes. Catalog health or a created Subscription alone does not count as Pass. Pass requires CSV phase `Succeeded` and a fully available controller Deployment. On failure, the task reports Subscription resolution conditions, CSV/InstallPlan diagnostics, and workload status.

Run these read-only commands to inspect the same resources manually:

```bash
oc get subscription self-node-remediation -n openshift-workload-availability
oc get csv -n openshift-workload-availability
oc get deployment,selfnoderemediationconfig,selfnoderemediationtemplate,daemonset,pods -n openshift-workload-availability
```

The original ATP source referenced 3scale. TC-28's implemented target is now Self Node Remediation Operator, as requested; the test report states that automated scope explicitly.

Reference: [Red Hat Workload Availability for OpenShift — Installing Self Node Remediation Operator](https://docs.redhat.com/en/documentation/workload_availability_for_red_hat_openshift/26.2/html/remediation_fencing_and_maintenance/self-node-remediation-operator-remediate-nodes).

## TC-51: self-provisioner security check

TC-51 inspects all ClusterRoleBindings that reference the `self-provisioner` role and verifies that none includes the `system:authenticated:oauth` group. It allows a binding to remain for a different group, such as `self-provisioners`. The check is read-only: it does not modify RBAC. If the authenticated OAuth group is present, the report lists the affected binding and recommends removing that group with the documented `oc adm policy remove-cluster-role-from-group` command. If the group is absent but the default `self-provisioners` binding has `rbac.authorization.kubernetes.io/autoupdate=true`, the ATP remains Pass for the current state and adds a comment with the recommended `oc annotate ... autoupdate=false` command; Red Hat documents that default reconciliation can restore subjects.

## TC-26 and TC-27: guarded node reboots

Both reboot cases are disabled by default. The automation captures `oc get nodes -o wide` before and after, checks that all nodes are Ready and ClusterOperators/MachineConfigPools are healthy, cordons and drains without bypassing PodDisruptionBudgets, and reboots only one node at a time. It confirms the node boot ID changed and waits for that node to return Ready before continuing. TC-26 processes worker nodes before control-plane nodes and requires at least three control-plane nodes. TC-27 requires an explicit worker node and at least two worker nodes.

To run TC-26, set `run_tc26_sanity_reboot: true` and provide the exact `tc26_reboot_confirmation: "REBOOT-CLUSTER-<cluster_name>"`. To run TC-27, set `run_tc27_reboot_worker: true`, set `tc27_worker_node` to the target, and provide `tc27_reboot_confirmation: "REBOOT-WORKER-<worker-node>"`. Alternatively pass these as Ansible extra vars. If the toggle is false, target/confirmation is missing, or the confirmation does not match, the test is recorded as **Skipped** and executes no reboot. A safety preflight or reboot failure after a correctly confirmed run is recorded as **Fail**. The automation never disables PDB checks.

Reference: [OpenShift 4.20 graceful node reboot procedure](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/nodes/working-with-nodes#nodes-nodes-rebooting_gracefully-rebooting-nodes).

## Cluster identity and DNS examples

The ATP uses a generic `cluster_name: "cluster"` default. Certificate procedures use
`<cluster_name>` and `<domain>` placeholders rather than environment-specific hostnames.
When running the procedure, replace `<domain>` with the cluster's configured DNS base
domain and use the same cluster name configured for its API and ingress endpoints.

Keep shared case definitions environment-neutral. Store site-specific hostnames and DNS
domains in the execution inventory or runtime variables rather than in the reusable ATP
catalog.
