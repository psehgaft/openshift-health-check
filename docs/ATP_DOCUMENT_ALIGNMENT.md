# ATP Source Document Alignment

## Source and execution model

The Acceptance Test Playbook is aligned with the supplied **Red Hat OpenShift Container Platform 4 v1 - template.docx**. Each report record now shows both the source document's procedure and expected result, separately from the command the playbook actually executed and its captured evidence. The source procedure is reference guidance; it is not evidence that every manual step was executed.

The report retains all source test cases. TC-23 runs first to ensure `testproject` exists. TC-30 runs after all other test cases because it deletes that project.

## Procedure corrections and added evidence

- **TC-15:** Runs `crictl ps` through `oc debug -q`, matching the documented container-list check.
- **TC-17:** Captures the last hour of logs through the Kubernetes API for the API server, controller manager, and scheduler.
- **TC-18:** Records the internal registry's `.svc` DNS name; checks the configured external registry when the internal service is absent.
- **TC-19:** Adds registry pod placement and last-hour log evidence. The case is Skipped when the cluster uses only an external registry.
- **TC-20:** Runs the documented JSONPath plus `jq .` query. Storage classification uses a separate Ansible fact task to avoid the Jinja syntax failure. External registry API reachability does not prove external storage durability, so that storage check remains Skipped pending owner-side verification.
- **TC-21 and TC-22:** Add pod lists and node placement to operator/logging status evidence.
- **TC-24 and TC-25:** Add the documented post-create queries for LimitRange and ResourceQuota.
- **TC-28:** A CatalogSource check is only a prerequisite. OperatorHub installation and the Succeeded status remain a manual case and are reported as Skipped until performed.
- **TC-29:** Captures status before and after resource cleanup and verifies that no `oc get all` resources remain.
- **TC-30:** Waits for project deletion and verifies that `testproject` no longer appears in the project list.
- **TC-31:** Captures node status after cordon and after uncordon.

Manual UI steps and disruptive operations remain documented as source procedures and are not silently represented as executed automation. Credentials, hashes, node names, and cluster-specific addresses from the source document are replaced with safe placeholders in the published reference map.

## Integration metadata

The `integration/` directory is retained. Its `sources.json` manifest is read by `scripts/unified_healthcheck.py` to include source repository/commit metadata in generated manifests. It is also referenced by the integration guide and `THIRD_PARTY_NOTICES.md`; deleting it would break provenance reporting and documentation links.
