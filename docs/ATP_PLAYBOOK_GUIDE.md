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

TC-18 and TC-19 validate the internal registry when present and additionally probe an external registry when its URL is configured or discovered. A configured external endpoint is always evaluated; a failed connection is a Fail result with a transport/TLS diagnostic. If neither an internal nor external registry exists, these ATP cases report Fail rather than Skipped. Discovery reads cluster mirror definitions from ImageDigestMirrorSet, ImageTagMirrorSet, and ImageContentSourcePolicy resources. It selects the endpoint only when exactly one unique mirror is found. Inspect the source configuration with `oc get imagedigestmirrorsets,imagetagmirrorsets -o yaml` and, on clusters using the legacy API, `oc get imagecontentsourcepolicies.operator.openshift.io -o yaml`.

Configure the URL in `toolkits/openshift-atp/vars/main.yml` when the cluster has multiple mirror endpoints or the external registry is not represented in those resources:

```yaml
atp_external_registry_url: "https://quay.example.com"
atp_external_registry_validate_certs: true
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

Without robot credentials, HTTP 200 or 401 means the OCI v2 API is reachable, but authentication is not verified. When credentials are supplied, TC-18/19 require HTTP 200. Keep TLS verification enabled. For a private registry CA, set `atp_external_registry_ca_path` to a PEM bundle path accessible to the Ansible controller. Disabling certificate validation should be limited to a temporary diagnostic.

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
Automated cases can be selectively run with the documented `run_tc*` variables. TC-26 and TC-27 remain manual-only. TC-62 is opt-in and remains `Skipped` by default; it executes only when the operator supplies the exact restore confirmation and all preflight gates pass.

## Output Reports
The playbook writes a Markdown report and a self-contained HTML report to `reports/` by default. Set `atp_report_dir` to change the destination.

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

Both formats contain a run summary and per-test records. TC-23 is the first case and ensures `testproject` exists. TC-58 creates or updates `test-atp` in `testproject`, making reruns safe when the Secret already exists. TC-30 runs after all other ATP cases and deletes `testproject` as the final cleanup action. TC-17 reads API server and control-plane logs through the Kubernetes API. TC-18 checks the internal registry service when present, otherwise it tests the configured external registry endpoint from a worker. TC-20 requires a persistent storage backend for the internal registry. For an external registry, it checks endpoint reachability but records that storage persistence still needs an authenticated push/pull validation or provider-side health check. The HTML follows the supplied form layout and includes the procedure, expected result, captured command output, conclusion, and comments with remediation guidance for failures.


## TC-22: logging API version compatibility

TC-22 no longer assumes that the legacy `ClusterLogging` custom resource exists. It queries both the Logging 5 APIs (`ClusterLogging` and `ClusterLogForwarder` in `logging.openshift.io`) and the Logging 6 `ClusterLogForwarder` API in `observability.openshift.io`. The case passes only when at least one supported configuration resource is returned and the logging pods in `openshift-logging` are all Running and ready. Missing API groups remain visible in the report evidence, while their absence alone does not fail a newer logging installation.

If the case fails, inspect the API group available on the cluster, the matching resource status conditions, the Logging/Loki/Cluster Observability Operators, pod events, and container logs. Do not create a legacy CRD to satisfy the ATP.


- **TC-53:** Creates or verifies ServiceAccount `atp-test` in `testproject`; an existing account is reported and left unchanged.


## TC-64: must-gather and node sosreport

TC-64 runs `oc adm must-gather` without the unsupported `--dry-run` option, packages its output, checks root access to a selected worker through `oc debug`, and runs a non-interactive `sos report` through `toolbox`. Both archives and their SHA-256 checksums are saved under the ATP report directory. Set `tc64_node_target` to choose a specific worker; otherwise the first worker is selected. These archives can contain sensitive cluster and host data, so protect the report directory and review it before sharing.

## TC-67a: PVC, iSCSI, and multipath

TC-67a first inventories Bound PVCs, PV volume types, and StorageClasses. If no SAN-backed volume or configured SAN class is found, the multipath-specific result is **Skipped / not applicable**; an inactive daemon by itself does not fail a cluster that does not use SAN. For SAN storage, it checks that a PVC is Bound, inspects `/etc/iscsi`, iSCSI sessions, `multipathd`, and `multipath -ll` on worker nodes, and requires active paths. Add vendor-specific SAN StorageClass names to `tc67a_san_storage_class_names` in `toolkits/openshift-atp/vars/main.yml` when PV type or CSI driver does not identify them.
