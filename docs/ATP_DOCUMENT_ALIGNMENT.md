# ATP Source Document Alignment

## Source and execution model

The Acceptance Test Playbook is aligned with the supplied **Red Hat OpenShift Container Platform 4 v1 - template.docx**. Each report record now shows both the source document's procedure and expected result, separately from the command the playbook actually executed and its captured evidence. The source procedure is reference guidance; it is not evidence that every manual step was executed.

The report retains all source test cases. TC-23 runs first to ensure `testproject` exists. TC-30 runs after all other test cases because it deletes that project.

## Procedure corrections and added evidence

- **TC-55:** Validates the API certificate chain against the active kubeconfig CA, verifies the endpoint SAN, and enforces a configurable minimum remaining validity. The prior CN substring check was incompatible with OpenSSL's spaced subject output.
- **TC-53:** Creates or verifies ServiceAccount `atp-test` in `testproject`. If the account already exists, the task reports that state and does not modify it.

- **TC-15:** Runs `crictl ps` through `oc debug -q`, matching the documented container-list check.
- **TC-17:** Captures the last hour of logs through the Kubernetes API for the API server, controller manager, and scheduler.
- **TC-18:** Records the internal registry's `.svc` DNS name and also probes a configured or discovered external registry API, including robot authentication when credentials are supplied.
- **TC-19:** Adds internal registry pod placement and last-hour log evidence, and probes the external registry API when configured or discovered. It is Fail when neither an internal registry nor an external endpoint is available, so this automated case is never silently skipped.
- **TC-20:** Runs the documented JSONPath plus `jq .` query. Storage classification uses a separate Ansible fact task to avoid the Jinja syntax failure. External registry API reachability does not prove external storage durability, so that storage check remains Skipped pending owner-side verification.
- **TC-21 and TC-22:** Add pod lists and node placement to operator/logging status evidence. TC-22 checks the legacy ClusterLogging/ClusterLogForwarder APIs and the Logging 6 observability API, then requires all logging pods to be Running and ready. TC-22 checks the legacy ClusterLogging/ClusterLogForwarder APIs and the Logging 6 observability API, then requires all logging pods to be Running and ready.
- **TC-24 and TC-25:** Add the documented post-create queries for LimitRange and ResourceQuota.
- **TC-28:** A CatalogSource check is only a prerequisite. OperatorHub installation and the Succeeded status remain a manual case and are reported as Skipped until performed.
- **TC-29:** Captures status before and after resource cleanup and verifies that no `oc get all` resources remain.
- **TC-30:** Waits for project deletion and verifies that `testproject` no longer appears in the project list.
- **TC-31:** Captures node status after cordon and after uncordon.

Manual UI steps and disruptive operations remain documented as source procedures and are not silently represented as executed automation. Credentials, hashes, node names, and cluster-specific addresses from the source document are replaced with safe placeholders in the published reference map.

## Integration metadata

The `integration/` directory is retained. Its `sources.json` manifest is read by `scripts/unified_healthcheck.py` to include source repository/commit metadata in generated manifests. It is also referenced by the integration guide and `THIRD_PARTY_NOTICES.md`; deleting it would break provenance reporting and documentation links.


## External registry validation

TC-18 and TC-19 validate the internal registry when its service exists and additionally probe an external registry. Automatic discovery reads mirror endpoints from ImageDigestMirrorSet, ImageTagMirrorSet, and legacy ImageContentSourcePolicy objects, and selects a URL only when there is exactly one unique target. Inspect these settings with `oc get imagedigestmirrorsets,imagetagmirrorsets -o yaml` and `oc get imagecontentsourcepolicies.operator.openshift.io -o yaml`.

Set `atp_external_registry_url` in `toolkits/openshift-atp/vars/main.yml` when there are multiple mirror targets or the external registry is not declared as a cluster mirror. Robot credentials cannot be safely inferred from those objects. Provide `ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME` and `ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN` through the execution environment; the probe task suppresses credential-bearing output and reports only the endpoint and HTTP status.


## TC-22: logging API version compatibility

TC-22 no longer assumes that the legacy `ClusterLogging` custom resource exists. It queries both the Logging 5 APIs (`ClusterLogging` and `ClusterLogForwarder` in `logging.openshift.io`) and the Logging 6 `ClusterLogForwarder` API in `observability.openshift.io`. The case passes only when at least one supported configuration resource is returned and the logging pods in `openshift-logging` are all Running and ready. Missing API groups remain visible in the report evidence, while their absence alone does not fail a newer logging installation.

If the case fails, inspect the API group available on the cluster, the matching resource status conditions, the Logging/Loki/Cluster Observability Operators, pod events, and container logs. Do not create a legacy CRD to satisfy the ATP.
