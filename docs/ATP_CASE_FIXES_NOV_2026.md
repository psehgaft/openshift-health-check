# ATP Storage and Certificate Case Updates

This note explains the TC-20, TC-28, TC-30, TC-55, TC-57, and TC-67a behavior changes.

## TC-20: registry storage
If the Image Registry Operator Service exists, TC-20 validates the internal storage configuration and rejects ephemeral `emptyDir`. If it does not, the case looks for an in-cluster QuayRegistry:
- Requires the QuayRegistry `Available=True` condition.
- Lists Quay PVCs and requires a Bound PostgreSQL PVC when PostgreSQL is managed by the operator.
- Requires a Bound ObjectBucketClaim when Quay object storage is operator-managed.
- Reports unmanaged PostgreSQL/object storage as provider-owned; Kubernetes cannot prove external durability from PVC status.
- Returns Skipped only when neither the internal registry nor an in-cluster QuayRegistry exists.

Red Hat Quay uses object storage for image layer blobs and managed PostgreSQL for registry metadata; the Quay operator can provision object storage through ObjectBucketClaim. See [Quay operator components](https://docs.redhat.com/en/documentation/red_hat_quay/3.18/html/configure_red_hat_quay/operator-components-intro) and [Quay object storage overview](https://docs.redhat.com/en/documentation/red_hat_quay/3.16/html/deploying_the_red_hat_quay_operator_on_openshift_container_platform/operator-concepts).

## TC-28: Self Node Remediation Operator
The failure `wait_attempts: unbound variable` came from shell variables referenced under `set -u` without being initialized in the shell task. The task now renders the Ansible defaults into shell variables, uses the configured attempt count and interval, and initializes the PackageManifest/CSV resource names before diagnostic queries.

## TC-30: project deletion
A successful `oc delete` response means deletion was accepted; the namespace can remain in Terminating while controllers remove resources and finalizers. TC-30 now polls the API until the project returns NotFound. At timeout, evidence includes its phase, deletion timestamp, finalizers, and conditions. Resolve the owning resource/controller issue; do not remove finalizers blindly.

## TC-55 and TC-57: intentional self-signed exceptions
The API setting `atp_api_cert_self_signed` already controls TC-55. The new `atp_ingress_cert_self_signed` controls TC-57. Set either to `true` in `group_vars/atp/main.yml` only for an approved self-signed endpoint. The case reports Skipped and says chain, SAN, and expiry were not validated. This is not a Pass.

## TC-67a: StorageClass inventory
The case reports each StorageClass name and provisioner, an inferred backend type/purpose, default status, binding mode, reclaim policy, and volume-expansion setting. The inferred purpose describes backend capabilities; the workload-specific reason must come from a site annotation or storage design document.
