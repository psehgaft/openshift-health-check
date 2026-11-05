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

TC-18 and TC-19 validate the internal registry when present and additionally probe an external registry when its URL is configured or discovered. Discovery reads cluster mirror definitions from ImageDigestMirrorSet, ImageTagMirrorSet, and ImageContentSourcePolicy resources. It selects the endpoint only when exactly one unique mirror is found. Inspect the source configuration with `oc get imagedigestmirrorsets,imagetagmirrorsets -o yaml` and, on clusters using the legacy API, `oc get imagecontentsourcepolicies.operator.openshift.io -o yaml`.

Configure the URL in `toolkits/openshift-atp/vars/main.yml` when the cluster has multiple mirror endpoints or the external registry is not represented in those resources:

```yaml
atp_external_registry_url: "https://quay.example.com"
atp_external_registry_validate_certs: true
```

A registry robot token cannot be obtained safely or reliably from cluster mirror settings. Supply the robot username and token from the bastion environment. The token is used as the robot account's HTTP Basic password and is excluded from task output and reports:

```bash
export ATP_EXTERNAL_REGISTRY_USERNAME='robot$organization+account'
read -rsp 'External registry robot token: ' ATP_EXTERNAL_REGISTRY_TOKEN
printf '\n'
export ATP_EXTERNAL_REGISTRY_TOKEN
ansible-playbook -i inventory.ini playbooks/atp.yml
unset ATP_EXTERNAL_REGISTRY_USERNAME ATP_EXTERNAL_REGISTRY_TOKEN
```

Without robot credentials, HTTP 200 or 401 means the OCI v2 API is reachable, but authentication is not verified. When credentials are supplied, TC-18/19 require HTTP 200. Keep TLS verification enabled when possible; install the registry CA instead of disabling certificate validation.

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
Automated cases can be selectively run with the documented `run_tc*` variables. TC-26 (cluster reboot), TC-27 (worker reboot), and TC-62 (etcd restore) are manual-only and always remain `Skipped` in this playbook; it does not execute these disruptive operations or mark them as passed without evidence.

## Output Reports
The playbook writes a Markdown report and a self-contained HTML report to `reports/` by default. Set `atp_report_dir` to change the destination.

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

Both formats contain a run summary and per-test records. TC-23 is the first case and ensures `testproject` exists. TC-58 creates or updates `test-atp` in `testproject`, making reruns safe when the Secret already exists. TC-30 runs after all other ATP cases and deletes `testproject` as the final cleanup action. TC-17 reads API server and control-plane logs through the Kubernetes API. TC-18 checks the internal registry service when present, otherwise it tests the configured external registry endpoint from a worker. TC-20 requires a persistent storage backend for the internal registry. For an external registry, it checks endpoint reachability but records that storage persistence still needs an authenticated push/pull validation or provider-side health check. The HTML follows the supplied form layout and includes the procedure, expected result, captured command output, conclusion, and comments with remediation guidance for failures.
