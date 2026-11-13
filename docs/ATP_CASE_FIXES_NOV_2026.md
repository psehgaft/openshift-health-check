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
The failure `wait_attempts: unbound variable` came from shell variables referenced under `set -u` without being initialized in the shell task. The task now renders the Ansible defaults into shell variables and uses the configured attempt count and interval. The later failure, `subscriptions.apps.open-cluster-management.io ... not found`, came from the ambiguous short resource name `subscription`, which resolved to the ACM API in this cluster. TC-28 now uses the fully qualified `subscriptions.operators.coreos.com`, `clusterserviceversions.operators.coreos.com`, and `installplans.operators.coreos.com` resources for its checks. If the matching Subscription already exists and its CSV is Succeeded with the controller Deployment available, the case passes on rerun. If OLM has not populated `installedCSV` yet, the task looks for an existing Succeeded SNRO CSV in the target namespace and reuses it. OLM's `unchanged` response is expected.

## TC-30: project deletion
A successful `oc delete` response means deletion was accepted; the namespace can remain in Terminating while controllers remove resources and finalizers. TC-30 now polls the API until the project returns NotFound. At timeout, evidence includes its phase, deletion timestamp, finalizers, and conditions. Resolve the owning resource/controller issue; do not remove finalizers blindly.

## TC-55 and TC-57: intentional self-signed exceptions
The API setting `atp_api_cert_self_signed` already controls TC-55. The new `atp_ingress_cert_self_signed` controls TC-57. Set either to `true` in `group_vars/atp/main.yml` only for an approved self-signed endpoint. The case reports Skipped and says chain, SAN, and expiry were not validated. This is not a Pass.

## TC-67a: StorageClass inventory
The case reports each StorageClass name and provisioner, an inferred backend type/purpose, default status, binding mode, reclaim policy, volume-expansion setting, and the class description. The notes/observations repeat the discovered inventory, including when multipath is Skipped because SAN is absent. In the supplied cluster evidence, `ocs-storagecluster-ceph-rbd` is Ceph RBD (block/filesystem), `ocs-storagecluster-cephfs` is shared CephFS, `ocs-storagecluster-ceph-rgw` and `openshift-storage.noobaa.io` provide object buckets, and `localblock` is static node-local block storage. These classifications use provisioner/name plus the StorageClass description; workload-specific intent still belongs in site annotations or the storage design. See [OpenShift Data Foundation storage classes](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_and_allocating_storage_resources/storage-classes_rhodf) and [OBC storage classes](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.13/html-single/deploying_and_managing_openshift_data_foundation_using_red_hat_openstack_platform/index#creating-object-bucket-claim-using-openshift-web-console_rhodf).
