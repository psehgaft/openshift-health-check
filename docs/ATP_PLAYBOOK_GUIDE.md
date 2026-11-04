# Acceptance Test Plan (ATP) Playbook - User Guide

## Overview
This Ansible playbook automates the acceptance verification procedures defined in the **ATP - Red Hat OpenShift Container Platform 4.20** specification. It covers **all 73 test cases** (including the two sub-cases for TC-67) spanning core OpenShift components, infrastructure governance, application scheduling, storage resilience, networking, and Telco 5G performance tuning (HugePages, LACP Bonding, MTU 9000, and SR-IOV VFs).

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

The ATP implementation is in [toolkits/openshift-atp](../toolkits/openshift-atp/). Each automated test stores the invoked command, full stdout/stderr, exit code, expected result, and conclusion. The playbook renders an ATP-specific Markdown and HTML report template alongside the existing health-check reporting system.

## Reports

Both files are generated in `reports/` unless `atp_report_dir` is overridden:

- `ATP-Report-OCP<version>-<timestamp>.md`
- `ATP-Report-OCP<version>-<timestamp>.html`

The HTML uses a two-column procedure record matching the supplied form: date, time, description, topology, procedure, expected result and observed evidence, Pass/Fail/Skipped conclusion, and additional comments with remediation guidance for failures.

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
```bash
# Disable specific test cases dynamically:
ansible-playbook -i inventory.ini playbooks/atp.yml \
  -e "run_tc26_sanity_reboot=false run_tc27_reboot_worker=false run_tc62_etcd_restore=false"
```

## Output Report
The playbook automatically produces a consolidated report in Markdown format saved under:
`reports/ATP-Report-OCP418-<timestamp>.md`

The report includes an executive summary with pass/fail counts and a detailed matrix of all 73 test cases with captured evidence.