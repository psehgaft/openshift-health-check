# Acceptance Test Plan (ATP) Playbook - User Guide

## Overview
This Ansible playbook automates the acceptance verification procedures defined in the **ATP - Red Hat OpenShift Container Platform 4.20** specification. It covers **73 numbered test cases**; TC-67 is recorded as two independently reported sub-cases, producing 74 report records. TC-23 runs first and creates or verifies `testproject` so later cases can use it. TC-30 runs last because it deletes `testproject`. The cases span core OpenShift components, infrastructure governance, application scheduling, storage resilience, networking, and Telco 5G performance tuning (HugePages, LACP Bonding, MTU 9000, and SR-IOV VFs).

## Repository and role layout
```text
openshift-health-check/
├── ansible.cfg
├── inventories/                       # Inventory examples for project playbooks
├── playbooks/                         # Stable runnable entry points
│   ├── atp.yml
│   ├── openshift_certificate_audit.yml
│   └── openshift_dns_validation.yml
├── roles/
│   ├── openshift_atp/                 # ATP role and its Galaxy metadata
│   ├── openshift_certificate_audit/
│   └── openshift_healthcheck_legacy/
├── requirements/                      # Ansible collection requirements
├── scripts/                           # Repository validators and runtime helpers
├── toolkits/
│   ├── openshift-healthcheck/         # Standalone Shell/Python, ACM, and Headlamp tools
│   └── arch-design-doc-generator/     # Non-Ansible architecture generator
└── docs/                              # User and architecture documentation
```

Reusable Ansible tasks, defaults, templates, helper files, and Galaxy metadata for ATP live in [the `openshift_atp` role](../roles/openshift_atp/). Run it through the stable entry point, [`playbooks/atp.yml`](../playbooks/atp.yml). The former `toolkits/openshift-atp` directory is retired. `toolkits/` contains standalone specialist utilities that are not Ansible roles or playbooks. Repository-level validation scripts stay in `scripts/`, and a role-specific helper that is required at runtime stays inside that role.

### Run ATP from either repository directory

From the repository root, run:

```bash
ansible-playbook -i inventory.ini playbooks/atp.yml
```

If your shell is already in `playbooks/`, run:

```bash
ansible-playbook atp.yml
```

The [playbooks-scoped Ansible configuration](../playbooks/ansible.cfg) adds the repository's `roles/` and plugin directories to Ansible's search paths. You do not need to install `openshift_atp` into `~/.ansible/roles`. For a syntax-only check that does not contact a cluster, run `ansible-playbook --syntax-check -i localhost, atp.yml` from `playbooks/`.

Each automated ATP case records the invoked command, stdout/stderr, exit code, expected result, and conclusion. Reports also include the source procedure as separate reference data, so readers can distinguish documented steps from commands actually executed. The role renders its Markdown and HTML reports from templates in the role itself.

## Reports

Both files are generated in `reports/` unless `atp_report_dir` is overridden:

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

The HTML uses a two-column procedure record matching the supplied form: date, time, description, topology, procedure, expected result and observed evidence, Pass/Fail/Skipped conclusion, and additional comments with remediation guidance for failures.

## External registry checks (TC-18 and TC-19)

TC-18 probes both available endpoint types and passes when at least one registry API is usable. If only the external registry is configured and reachable, the case passes and the report notes that the cluster is using the external registry only. If both endpoints are configured but one fails, the case still passes when the other is usable and adds a comment describing the failed endpoint. TC-19 separately checks internal registry pod placement and logs, so it has additional internal-registry conditions. Discovery reads cluster mirror definitions from ImageDigestMirrorSet, ImageTagMirrorSet, and ImageContentSourcePolicy resources. It selects the endpoint only when exactly one unique mirror is found. Inspect the source configuration with `oc get imagedigestmirrorsets,imagetagmirrorsets -o yaml` and, on clusters using the legacy API, `oc get imagecontentsourcepolicies.operator.openshift.io -o yaml`.

Configure the URL in `roles/openshift_atp/defaults/main.yml` when the cluster has multiple mirror endpoints or the external registry is not represented in those resources:

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

Before selecting the endpoint, TC-18/TC-19 query `oc get clusteroperator image-registry -o yaml`, the Image Registry Operator `spec.managementState`, and the internal `image-registry` Service. When the internal registry is Removed or fails its health check, the ATP enumerates registry host keys in `openshift-config/pull-secret` and tries `podman login` for each credential-bearing host. The decoded pull-secret and Podman output are hidden, credentials are read from stdin, and Podman writes only to a temporary auth file that is removed after the probe. If the internal registry passes, external pull-secret host keys are reported as discovered references but are not authenticated by that case. The pull-secret must contain a valid credential for the external Quay/registry domain; Podman must be installed on the Ansible execution host. For a private CA, `atp_external_registry_ca_path` supplies the PEM file used for the login probe.

For TC-18, the report result is assembled into a dedicated `tc18_result` fact and appended to `atp_results` in a separate task. This avoids parsing the nested inline Jinja dictionary that caused `expected token ')', got ':'` during result finalization. If the syntax error reappears, confirm the playbook is using the latest `01_services_check.yml` from the ATP branch; this reporting refactor does not change the registry pass criteria. TC-19 uses the same separate result-fact and append pattern, and parses pod names in its own task before building the report record.

## Test-case troubleshooting references

Use these case-specific notes alongside the current playbook output. Their captured cluster evidence is historical and must not be treated as the current cluster state.

| Test cases | Guide |
| --- | --- |
| TC-20 and TC-22 | [Registry storage and logging fixes](ATP_TC22_TC20_FIXES.md) |
| TC-70 | [LACP bonding and MTU 9000](ATP_TC70_LACP_MTU9000.md) |
| TC-71 | [Node roles and maximum pod capacity](ATP_TC71_NODE_PROFILING.md) |
| TC-72 | [HugePages for CNF workers](ATP_TC72_HUGEPAGES.md) |

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

### 2. Using Feature Toggles in `roles/openshift_atp/defaults/main.yml` or CLI Extra Vars
Automated cases can be selectively run with the documented `run_tc*` variables. TC-26 and TC-27 are opt-in, disabled by default, and require exact reboot confirmations. TC-62 is opt-in and remains `Skipped` by default; it executes only when the operator supplies the exact restore confirmation and all preflight gates pass.

## Output Reports
The playbook writes a Markdown report and a self-contained HTML report to `reports/` by default. Set `atp_report_dir` to change the destination.

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

Both formats contain a run summary and per-test records. TC-23 is the first case and ensures `testproject` exists. TC-58 creates or updates `test-atp` in `testproject`, making reruns safe when the Secret already exists. TC-30 runs after all other ATP cases and deletes `testproject` as the final cleanup action. TC-17 reads API server and control-plane logs through the Kubernetes API. TC-18 and TC-19 check the Image Registry Operator management state and internal service; when internal registry is Removed or unhealthy, they test an explicit/mirror endpoint or perform temporary-file Podman logins against credential-bearing registry hosts in the cluster pull-secret. If internal checks pass, discovered external pull-secret entries are noted without exposing credentials. TC-20 requires a persistent storage backend for the internal registry. For an external registry, it checks endpoint reachability but records that storage persistence still needs an authenticated push/pull validation or provider-side health check. The HTML follows the supplied form layout and includes the procedure, expected result, captured command output, conclusion, and comments with remediation guidance for failures.


## TC-22: logging API version compatibility

TC-22 reads the actual release from `oc get clusterversion version` and selects the API checks by OpenShift version. On OCP 4.19 and later, it queries only `ClusterLogForwarder` in `observability.openshift.io`; it does not query legacy `ClusterLogging` or `logging.openshift.io` APIs. On earlier releases, it checks the legacy APIs and retains the modern `ClusterLogForwarder` as a compatibility fallback. All versions also require logging pods in `openshift-logging` to be Running and ready. If release detection fails, TC-22 fails with the version query evidence instead of guessing which API to use.

The API removal is associated with Red Hat OpenShift Logging 6, whose API group is `observability.openshift.io`; the Logging operator has a release/support cadence distinct from the OpenShift Container Platform release. The ATP applies the requested 4.19 version threshold to select the API policy.

If the case fails, inspect the API group available on the cluster, the matching resource status conditions, the Logging/Loki/Cluster Observability Operators, pod events, and container logs. Do not create a legacy CRD to satisfy the ATP.


- **TC-53:** Creates or verifies ServiceAccount `atp-test` in `testproject`; an existing account is reported and left unchanged.


## TC-72: HugePages target nodes and PerformanceProfile

TC-72 requires **every node matched by** `tc72_node_selector` to report positive HugePages capacity and allocatable resources for at least one size, `hugepages-1Gi` or `hugepages-2Mi`. In the 2026-11-06 evidence, 10 selected nodes already expose 1Gi HugePages; `carfzt5gclmt01`, `carfzt5gclmt02`, and `carfzt5gclmt03` report zero for both sizes. Decide from the approved CNF topology whether those three nodes are expected CNF hosts:

- If they are not CNF targets, label only the designated CNF nodes through the cluster's normal node-label/GitOps process and set `tc72_node_selector` in `roles/openshift_atp/defaults/main.yml` to that label selector. Example:
  ```yaml
  tc72_node_selector: "atp.openshift.io/cnf-hugepages=true"
  ```
  Do not narrow the selector just to hide a real HugePages gap on nodes that are intended to run CNFs.
- If those nodes must host CNFs, update the existing Node Tuning Operator `PerformanceProfile` that targets their node pool. Add the HugePages page size and count from the CNF vendor/application sizing and NUMA design. Merge this into the existing profile; do not apply it as a standalone, incomplete PerformanceProfile:
  ```yaml
  spec:
    hugepages:
      defaultHugepagesSize: 1G
      pages:
      - size: 1G
        count: <number-of-1Gi-pages-required-by-the-CNF>
        node: <NUMA-node-id>
  ```
  Choose `1G` or `2M` according to the CNF requirements. The count is a number of pages, not a memory size. If the `node` field is omitted, the operator distributes the pages across NUMA nodes. Ensure the profile's node selector and MachineConfigPool selectors target only the intended nodes/pool. HugePages are preallocated and reduce memory available for regular workloads; do not copy the existing 40Gi/160Gi figures to other nodes without hardware and workload sizing.

After applying a profile, wait until its MachineConfigPool rollout completes and the nodes return Ready. Check the pool and resource values:
```bash
oc get mcp
oc get nodes -l 'atp.openshift.io/cnf-hugepages=true' -o json | jq -r '
  .items[] |
  [.metadata.name,
   (.status.capacity["hugepages-1Gi"] // "0"),
   (.status.allocatable["hugepages-1Gi"] // "0"),
   (.status.capacity["hugepages-2Mi"] // "0"),
   (.status.allocatable["hugepages-2Mi"] // "0")] | @tsv'
```
For every node selected by the configured selector, at least one size must be greater than zero in **both** capacity and allocatable. Then rerun TC-72. OpenShift 4.20 documents preallocation with the Node Tuning Operator PerformanceProfile and recommends waiting for the relevant MachineConfigPool update to finish. See [HugePages configuration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/scalability_and_performance/using-cpu-manager) and the [PerformanceProfile API](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/node_apis/index).

## TC-64: must-gather and node sosreport

TC-64 runs `oc adm must-gather`, packages and integrity-checks the collected directory, and verifies host-root access on a worker. It attempts to generate/copy an integrity-checked `sosreport` when the node and image prerequisites allow it. Must-gather collection logs are saved as `must-gather.log`; sosreport command/copy logs are saved alongside the artifacts. The sosreport uses `podman container runlabel run` with `registry.redhat.io/rhel9/support-tools` and directs output to `/host/var/tmp`, which maps to the node's `/var/tmp`. TC-64 Pass requires a non-empty must-gather archive that passes gzip/tar integrity checks and a successful host-root check. Sosreport is best-effort: it is validated and included when generated, but its absence is reported and does not fail TC-64. If must-gather times out but produced files, the playbook packages and validates those files and records a Pass-with-warning marker; review `must-gather.log` because the archive may be incomplete. Configure `tc64_must_gather_timeout_seconds` (60-18000, default 7200) and `tc64_sosreport_timeout_seconds` (60-3000, default 2700) in `roles/openshift_atp/defaults/main.yml`; the first can be increased for large clusters. Set `tc64_node_target` to select a worker; otherwise the first worker is used. For disconnected clusters, mirror `registry.redhat.io/rhel9/support-tools:latest` and set `tc64_support_tools_image` to that mirror image. These archives can contain sensitive cluster and host data, so protect the diagnostics directory and review it before sharing.

## TC-67a: PVC, iSCSI, and multipath

TC-67a inventories Bound PVCs, PV volume types, and StorageClasses. It auto-detects SAN classes from common names (such as `iscsi`, `fibre`, `fc`, or `san`), CSI provisioner metadata, and protocol parameters, then correlates the classes with PVs and PVCs. If no SAN-backed PV or SAN StorageClass is found, the multipath-specific result is **Skipped / not applicable**; an inactive daemon by itself does not fail a cluster that does not use SAN. For detected SAN storage, it checks that a PVC is Bound and inspects `/etc/iscsi`, iSCSI sessions, `multipathd`, and `multipath -ll` on workers. A Pass requires accessible host diagnostics, active multipathd, and active/ready paths (plus an active iSCSI session for iSCSI-backed storage). Custom StorageClass names whose CSI metadata does not identify SAN must be listed explicitly in `tc67a_san_storage_class_names` in `roles/openshift_atp/defaults/main.yml`; for example, `tc67a_san_storage_class_names: ["custom-san-sc"]`.


## TC-55: API certificate validation

TC-55 normally validates the API server URL from the active kubeconfig, including its TLS chain, hostname SAN, and remaining validity (`atp_api_cert_min_validity_days`, default: 7 days). It uses the embedded kubeconfig CA when available, or `atp_api_cert_ca_path` for a PEM CA bundle on the Ansible controller. The playbook always loads `roles/openshift_atp/defaults/main.yml` and then loads `roles/openshift_atp/vars/main.yaml` as an optional site override when that file exists. To skip TC-55 for a known self-signed API certificate, set `atp_api_cert_self_signed: true` in either loaded file or pass `-e atp_api_cert_self_signed=true`. TC-55 then records **Skipped** and an Additional comments note that self-signed API certificates are in use and chain, SAN, and expiration were not validated. The default is `false`, so normal validation runs. This skip is an explicit reporting choice, not a trust validation or security approval; use it only when self-signed certificates are an accepted design exception. Keep TLS verification enabled in normal validation.


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

To run TC-26, set `run_tc26_sanity_reboot: true` and provide the exact `tc26_reboot_confirmation: "REBOOT-CLUSTER-<cluster_name>"`. To run TC-27, set `run_tc27_reboot_worker: true`, set `tc27_worker_node` to the target, and provide `tc27_reboot_confirmation: "REBOOT-WORKER-<worker-node>"`. Alternatively pass these as Ansible extra vars. If the toggle is false, target/confirmation is missing, or the confirmation does not match, the test is recorded as **Skipped** and executes no reboot. A safety preflight or reboot failure after a correctly confirmed run is recorded as **Fail**. The automation never disables PDB checks. TC-26 and TC-27 build each report entry as a YAML `tc26_result`/`tc27_result` fact, then append it to `atp_results` in a separate task. This avoids the nested inline Jinja dictionary parsing error during report finalization.

Reference: [OpenShift 4.20 graceful node reboot procedure](https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/nodes/working-with-nodes#nodes-nodes-rebooting_gracefully-rebooting-nodes).

## Cluster identity and DNS examples

The ATP uses a generic `cluster_name: "cluster"` default. Certificate procedures use
`<cluster_name>` and `<domain>` placeholders rather than environment-specific hostnames.
When running the procedure, replace `<domain>` with the cluster's configured DNS base
domain and use the same cluster name configured for its API and ingress endpoints.

Keep shared case definitions environment-neutral. Store site-specific hostnames and DNS
domains in the execution inventory or runtime variables rather than in the reusable ATP
catalog.


## Site variables and per-case execution controls

The shared [`group_vars/all.yml`](../group_vars/all.yml) file is the editable site configuration for repository playbooks. The ATP entry point explicitly loads it, so it works even when Ansible uses an implicit localhost inventory. The role defaults remain fallback values for standalone role use.

Every automated ATP case has its own `run_tc*` switch in that file. Set an individual switch to `false` to avoid running that case; the ATP still adds a report row with conclusion `Skipped` and identifies the switch to re-enable it. For example:

```yaml
run_tc28_install_operator: false
run_tc51_disable_self_provisioner: true
run_tc67a_storage_iscsi_multipath: true
```

TC-26 and TC-27 are disabled by default because they reboot nodes. TC-62 uses the separate `tc62_restore_enabled` control and requires its exact confirmation string. Keep those false except during an approved maintenance or recovery exercise.

TC-28's earlier failure was caused by the short `oc get subscription` resource name resolving to the unrelated `subscriptions.apps.open-cluster-management.io` API in this cluster. The task now queries the explicit `subscriptions.operators.coreos.com` resource. Package, namespace, channel, catalog source, wait period, and controller deployment are also configurable in `group_vars/all.yml`.

TC-51 correctly failed because the observed `self-provisioners` ClusterRoleBinding still granted `system:authenticated:oauth` the `self-provisioner` role. This is a cluster configuration finding, not an automation error. Remove that group from the binding using the approved change procedure, set the binding's autoupdate behavior so the default subject is not restored, then rerun TC-51. The ATP remains read-only for this check.

TC-67a's `NOT_APPLICABLE` result is expected when no SAN-backed PV or SAN StorageClass is configured. The reported inventory showed Ceph RBD and local block storage, with no iSCSI/FC/SAN resources, so the check was correctly Skipped. The report now states this explicitly. For a custom SAN StorageClass that cannot be auto-detected, list its name in `tc67a_san_storage_class_names`.
