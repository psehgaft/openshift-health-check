# ATP fixes: TC-22 Logging and TC-20 Registry Storage

## TC-22 — Logging Stack Status

### Diagnosis

The supplied evidence shows OpenShift **4.20.27**, so the ATP selects the
`observability.openshift.io` ClusterLogForwarder API. The two ClusterLogForwarder
resources shown in the report have `Ready=True` and `observability.openshift.io/Valid=True`.
The pod table also shows the listed logging pods as `Running` and `1/1 Ready`.

The previous readiness command failed with exit code `5` from its `jq` pipeline.
That result was a command/parser/runtime failure, not evidence that the logging
components were unhealthy. The report also preferred an empty stdout string over
stderr, which hid the actual diagnostic.

### Change

The readiness check now parses the `oc get pods -o json` response with Python 3,
which is already a runtime dependency of Ansible. It requires at least one pod,
requires every pod to be `Running`, and requires every pod to have container
status entries with all containers ready. If a pod fails, the evidence names the
pod, phase, and unready containers. Failure stderr is preserved in the ATP report.

For this cluster, rerunning TC-22 should produce Pass if the reported API and pod
conditions have not changed. No logging configuration change is indicated by the
evidence provided.

### Manual verification

Run these read-only checks from the authenticated bastion:

```bash
oc get clusterversion version -o jsonpath='{.status.desired.version}{"\n"}'
oc get clusterlogforwarders.observability.openshift.io -n openshift-logging -o yaml
oc get pods -n openshift-logging -o wide
```

For OCP 4.19 and later, this ATP checks the observability API. Confirm that the
ClusterLogForwarder is configured and its status reports Ready/Valid conditions
as True. Confirm every pod in `openshift-logging` is Running and every container
is Ready.

## TC-20 — Check Configured Registry Storage

If the `openshift-image-registry/image-registry` Service does not exist, TC-20
now returns **Skipped** with an explicit note that internal registry storage is
not applicable. OpenShift's Image Registry Operator cannot inspect the storage
backend of an external Quay or other registry. Validate external persistence with
the registry provider's health checks or an authenticated push/pull test.

If the internal registry Service exists, TC-20 still checks the Image Registry
Operator storage configuration and fails when the backend is missing or uses
ephemeral `emptyDir` storage.

## References

- [Red Hat OpenShift Container Platform 4.20 — Logging](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/logging/)
- [Red Hat OpenShift Logging — Configuring log forwarding](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.3/html/configuring_logging/configuring-log-forwarding)
