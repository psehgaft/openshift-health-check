# Acceptance Test Plan (ATP) Playbook - User Guide

## Overview
This Ansible playbook automates the acceptance verification procedures defined in the **ATP - Red Hat OpenShift Container Platform 4.20** specification. It covers **all 73 test cases** (including the two sub-cases for TC-67) spanning core OpenShift components, infrastructure governance, application scheduling, storage resilience, networking, and Telco 5G performance tuning (HugePages, LACP Bonding, MTU 9000, and SR-IOV VFs).

## Directory Structure
```text
openshift-health-check/
├── playbooks/
│   └── atp.yml                      # Main orchestrator playbook
├── tools/
│   └── atps/
│       ├── main.yml                 # Section task loader
│       ├── vars/
│       │   └── main.yml             # Global variables & test case toggle switches
│       ├── templates/
│       │   └── atp_report.md.j2     # Jinja2 template for the Markdown acceptance report
│       ├── 01_services_check.yml    # Test Cases 01 to 22
│       ├── 02_administration.yml    # Test Cases 23 to 31
│       ├── 03_manage_application.yml# Test Cases 32 to 38
│       ├── 04_logging_stack.yml     # Test Cases 39 to 40
│       ├── 05_storage_management.yml# Test Cases 41 to 45
│       ├── 06_network_management.yml# Test Cases 46 to 48
│       ├── 07_user_security.yml     # Test Cases 49 to 60
│       ├── 08_backup_restore.yml    # Test Cases 61 to 62
│       └── 09_general_telco_support.yml # Test Cases 63 to 73
└── docs/
    └── ATP_PLAYBOOK_GUIDE.md        # Technical user guide
```

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

### 2. Using Feature Toggles in `tools/atps/vars/main.yml` or CLI Extra Vars
```bash
# Disable specific test cases dynamically:
ansible-playbook -i inventory.ini playbooks/atp.yml \
  -e "run_tc26_sanity_reboot=false run_tc27_reboot_worker=false run_tc62_etcd_restore=false"
```

## Output Report
The playbook automatically produces a consolidated report in Markdown format saved under:
`reports/ATP-Report-OCP418-<timestamp>.md`

The report includes an executive summary with pass/fail counts and a detailed matrix of all 73 test cases with captured evidence.