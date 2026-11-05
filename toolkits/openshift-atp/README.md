# OpenShift ATP toolkit

This toolkit runs the Acceptance Test Procedure for OpenShift and writes Markdown and HTML execution reports.

## Run

From the repository root, activate the Ansible environment, authenticate with `oc`, then run:

```bash
source .venv/bin/activate
oc whoami
ansible-playbook -i inventory.ini playbooks/atp.yml
```

Generated reports are written to `reports/` by default. Override `atp_report_dir` to select another location.

## Report contents

The report includes each test case’s evidence. TC-23 is executed first and creates or verifies `testproject` before later cases begin. Each test case includes its execution date/time, description, topology, executed command or manual gate, expected result, full captured stdout/stderr and exit code, Pass/Fail/Skipped conclusion, and follow-up guidance when the test fails. TC-58 applies its Secret in `testproject` idempotently. TC-30 is executed after all other cases because it deletes `testproject`; it is the final cleanup action. TC-17 checks logs from the API server and control-plane components. TC-18 selects the internal registry service when available or checks the configured external registry API. TC-20 checks internal storage configuration and clearly reports that external registry persistence needs provider-side or authenticated push/pull verification. Output is rendered from the ATP result data to both `.md` and `.html`.

The ATP has dedicated templates in [templates/](templates/). It uses the same Ansible/Jinja rendering workflow as the health-check reports without changing the health-check report contract.

## Select cases

Test toggles are documented in [vars/main.yml](vars/main.yml). Disable or enable a case through extra variables, for example:

```bash
ansible-playbook -i inventory.ini playbooks/atp.yml -e run_tc26_sanity_reboot=false
```

Disruptive tests remain gated by default. Review each ATP test task and its operational impact before enabling it.
