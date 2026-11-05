# ATP Source Document Alignment

## Source and execution model

The Acceptance Test Playbook is aligned with the supplied **Red Hat OpenShift Container Platform 4 v1 - template.docx**. Each report record now shows both the source document's procedure and expected result, separately from the command the playbook actually executed and its captured evidence. The source procedure is reference guidance; it is not evidence that every manual step was executed.

The report retains all source test cases. TC-23 runs first to ensure `testproject` exists. TC-30 runs after all other test cases because it deletes that project.

## Procedure corrections and added evidence

- **TC-55:** Validates the API certificate chain against the active kubeconfig CA, verifies the endpoint SAN, and enforces a configurable minimum remaining validity. The prior CN substring check was incompatible with OpenSSL's spaced subject output.
- **TC-51:** Evaluates every ClusterRoleBinding that references `self-provisioner` and fails only if a subject is the `system:authenticated:oauth` group. A binding to another group (such as `self-provisioners`) is not treated as a failure. This prevents the previous false negative caused by requiring the binding to have zero subjects.
- **TC-53:** Creates or verifies ServiceAccount `atp-test` in `testproject`. If the account already exists, the task reports that state and does not modify it.

- **TC-15:** Runs `crictl ps` through `oc debug -q`, matching the documented container-list check.
- **TC-17:** Captures the last hour of logs through the Kubernetes API for the API server, controller manager, and scheduler.
- **TC-18:** Probes both the internal service and a configured/discovered external OCI API. It passes when either endpoint is usable; if only the external endpoint is reachable, the report explicitly notes that the internal registry is not configured/available and that the external registry is the sole usable endpoint. If both are configured but one fails, the available endpoint can satisfy the ATP while the comments preserve the failed endpoint's diagnostic. Robot credentials, when supplied, must authenticate successfully for the external API check.
- **TC-19:** Adds internal registry pod placement and last-hour log evidence, and probes the external registry API when configured or discovered. It is Fail when neither an internal registry nor an external endpoint is available, so this automated case is never silently skipped.
- **TC-20:** Runs the documented JSONPath plus `jq .` query. Storage classification uses a separate Ansible fact task to avoid the Jinja syntax failure. External registry API reachability does not prove external storage durability, so that storage check remains Skipped pending owner-side verification.
- **TC-21:** Adds pod lists and node placement to the operator status evidence.
- **TC-22:** Detects the OpenShift release from ClusterVersion. OCP 4.19+ checks only ClusterLogForwarder in the observability API group; earlier releases check legacy logging APIs with a modern ClusterLogForwarder fallback. Every version also requires logging pods to be Running and ready. Failed version detection fails the case with evidence rather than falling back to a guessed API.
- **TC-24 and TC-25:** Add the documented post-create queries for LimitRange and ResourceQuota.
- **TC-28:** The automated procedure applies the supplied `sample-operator` Subscription (`stable`, `redhat-operators`, namespace `openshift-operators`) and waits up to ten minutes for its installed ClusterServiceVersion (CSV) to reach `Succeeded`. It passes only on that phase; catalog availability alone is insufficient. The source ATP’s original 3scale OperatorHub procedure remains visible as a reference, while the report identifies the automated sample-operator scope.
- **TC-29:** Captures status before and after resource cleanup and verifies that no `oc get all` resources remain.
- **TC-30:** Waits for project deletion and verifies that `testproject` no longer appears in the project list.
- **TC-31:** Captures node status after cordon and after uncordon.

Manual UI steps and disruptive operations remain documented as source procedures and are not silently represented as executed automation. Credentials, hashes, node names, and cluster-specific addresses from the source document are replaced with safe placeholders in the published reference map.

## Integration metadata

The `integration/` directory is retained. Its `sources.json` manifest is read by `scripts/unified_healthcheck.py` to include source repository/commit metadata in generated manifests. It is also referenced by the integration guide and `THIRD_PARTY_NOTICES.md`; deleting it would break provenance reporting and documentation links.


## External registry validation

TC-18 and TC-19 validate the internal registry when its service exists and additionally probe an external registry. Automatic discovery reads mirror endpoints from ImageDigestMirrorSet, ImageTagMirrorSet, and legacy ImageContentSourcePolicy objects, and selects a URL only when there is exactly one unique target. Inspect these settings with `oc get imagedigestmirrorsets,imagetagmirrorsets -o yaml` and `oc get imagecontentsourcepolicies.operator.openshift.io -o yaml`.

Set `atp_external_registry_url` in `toolkits/openshift-atp/vars/main.yml` when there are multiple mirror targets or the external registry is not declared as a cluster mirror. Keep `atp_external_registry_validate_certs: true`; for a private/self-signed chain, set `atp_external_registry_ca_path` to an issuing CA PEM file readable by the Ansible controller. Robot credentials cannot be safely inferred from mirror objects. Provide `ATP_EXTERNAL_REGISTRY_ROBOT_USERNAME` and `ATP_EXTERNAL_REGISTRY_ROBOT_TOKEN` through the execution environment; the probe task suppresses credential-bearing output and reports only the endpoint and HTTP status.


## TC-22: logging API version compatibility

TC-22 detects the OpenShift release from ClusterVersion before selecting logging APIs. For OCP 4.19 and later, it queries only `ClusterLogForwarder` in `observability.openshift.io`; it does not query or require the legacy `ClusterLogging` or `ClusterLogForwarder.logging.openshift.io` resources. For releases earlier than 4.19, it checks the legacy APIs and accepts the modern `ClusterLogForwarder` as a compatibility fallback. Every version also requires logging pods to be Running and ready. If release detection fails, the case fails with the version-query evidence instead of guessing the API generation.

The legacy API removal is associated with Red Hat OpenShift Logging 6, which uses the `observability.openshift.io` API group. Logging Operator and OCP releases have distinct release/support cadences; this ATP intentionally applies the requested OCP 4.19 threshold. If the case fails, inspect the detected version, ClusterLogForwarder status conditions, Logging Operator and related operators, pod events, and container logs. Do not create a legacy CRD to satisfy the ATP.
