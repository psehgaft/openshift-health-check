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

The report includes each test case’s evidence. TC-23 is executed first and creates or verifies `testproject` before later cases begin. Each test case includes its execution date/time, description, topology, executed command or manual gate, expected result, full captured stdout/stderr and exit code, Pass/Fail/Skipped conclusion, and follow-up guidance when the test fails. The report also preserves the source document's original procedure and expected result as reference fields, separate from the commands the playbook actually ran. TC-58 applies its Secret in `testproject` idempotently. TC-30 is executed after all other cases because it deletes `testproject`; it is the final cleanup action. TC-17 checks logs from the API server and control-plane components. TC-18 and TC-19 check the internal registry when present and also probe a configured or discovered external registry API. TC-20 checks internal storage configuration and clearly reports that external registry persistence needs provider-side or authenticated push/pull verification. Output is rendered from the ATP result data to both `.md` and `.html`.

The ATP has dedicated templates in [templates/](templates/). It uses the same Ansible/Jinja rendering workflow as the health-check reports without changing the health-check report contract.

## External registry settings (TC-18 and TC-19)

The playbook checks the internal registry when its service exists and also checks an external registry when configured or discovered. It can discover one unique mirror endpoint from the cluster's ImageDigestMirrorSet, ImageTagMirrorSet, or legacy ImageContentSourcePolicy objects. Set `atp_external_registry_url` in [vars/main.yml](vars/main.yml) when there are multiple mirrors or the registry is not declared as a cluster mirror. Use a full base URL such as `https://quay.example.com`.

The cluster configuration does not contain a safe, reliable robot token to reuse. Supply the robot username and token at runtime through environment variables; the token is sent as the robot account's HTTP Basic password and is never included in the ATP report:

```bash
export ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME='robot$organization+account'
read -rsp 'External registry robot token: ' ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN
printf '\n'
export ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN
ansible-playbook -i inventory.ini playbooks/atp.yml
unset ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN
```

Set `atp_external_registry_validate_certs: false` only when the registry uses a certificate chain the bastion does not trust. Prefer installing the registry CA. Without credentials, HTTP 200 or 401 confirms API reachability; when robot credentials are configured, only HTTP 200 passes authentication. TC-19 validates internal registry pods, placement, and logs, plus the external API when configured.

## Select cases

Test toggles are documented in [vars/main.yml](vars/main.yml). Disable or enable a case through extra variables, for example:

```bash
ansible-playbook -i inventory.ini playbooks/atp.yml -e run_tc26_sanity_reboot=false
```

Disruptive tests remain gated by default. Review each ATP test task and its operational impact before enabling it.
