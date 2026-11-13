# ATP Manual Execution Flags

This guide documents how to report manually completed procedures for TC-26, TC-27, and TC-62 without rerunning their disruptive actions.

## Configure the flags

Edit `group_vars/atp/main.yml` before the ATP run. Defaults are false:

```yaml
# Set true only after the corresponding approved manual runbook is complete.
tc26_manual_execution: false
tc27_manual_execution: false
tc62_manual_execution: false

# Required for TC-27 to validate the worker that was rebooted.
tc27_worker_node: ""
```

Set only the case you completed to true. For TC-27, also set the worker name:

```yaml
tc27_manual_execution: true
tc27_worker_node: "worker-0.cluster.example.com"
```

## Evidence and Pass criteria

| Case | Read-only evidence collected | Pass criteria |
| --- | --- | --- |
| TC-26 | `oc get nodes -o json`; `oc get co -o json` | Every node is Ready; all ClusterOperators are Available, not Degraded, and not Progressing. |
| TC-27 | `oc get nodes -o json`; `oc get co -o json` | Same cluster checks, plus the configured target exists, is a worker, and is Ready. |
| TC-62 | `oc get nodes -o json`; `oc get co -o json`; `oc get pods -n openshift-etcd -o json` | Same cluster checks, plus etcd pods (excluding quorum-guard pods) are Running and all containers are ready. |

The manual flag suppresses the automated reboot/restore path for that case. The ATP performs only the listed read-only API checks. A **Pass** means the current health checks passed after the operator declared that the manual runbook was completed. These checks do not independently prove that the reboot or restore occurred, nor do they verify the backup and recovery procedure. Preserve the approved change record and runbook evidence separately.

Run selected cases after logging into the target cluster:

```bash
ansible-playbook -i inventory.ini playbooks/atp.yml --tags "tc26,tc27,tc62"
```

Reset the flags to false after generating the report so a later run does not carry forward a prior manual-execution attestation.

## Official runbooks

Complete the approved procedure before setting a manual flag. See the OpenShift Container Platform 4.20 [graceful node reboot guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/working-with-nodes) for TC-26/TC-27 and the [control plane backup and restore guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/backup_and_restore/control-plane-backup-and-restore) for TC-62. An etcd restore is a last-resort recovery procedure; the manual flag must not be used as a substitute for the approved runbook or its evidence.
