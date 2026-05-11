# OpenShift RBAC Guide For This Health Check

This document describes the minimum practical RBAC model to run the OpenShift health check without binding the runner to `cluster-admin`.

## Scope

This repo has three distinct live-access needs:

- broad cluster inventory collection through `oc get ... -o json`
- monitoring access for Thanos and Prometheus-backed checks
- support collection access for `oc adm must-gather`, `oc adm inspect`, Insights archive copy, and optional node diagnostics

There is no single built-in non-`cluster-admin` role that covers all of that.

## Required Role Model

The base live scan uses:

- built-in `cluster-reader`
- built-in `cluster-monitoring-view`
- custom `openshift-health-check-support-collector`
- namespace-scoped `openshift-health-check-insights-reader` in `openshift-insights`

Optional live node diagnostics with `collect_live_sosreport=true` also use:

- custom `openshift-health-check-node-debug`
- custom `openshift-health-check-privileged-scc`

The support-collector role must cover two extra write paths used by `oc adm must-gather`:

- creating `serviceaccounts` in the temporary or chosen must-gather namespace
- creating `clusterrolebindings.rbac.authorization.k8s.io`

## Important Caveat

This is a pragmatic least-privilege bundle for this repo. It is not a guarantee that these permissions are always equivalent to every environment where `oc adm must-gather`, `oc adm inspect`, or `oc debug node/<node>` might be used.

If you want the most predictable support-data experience, use `cluster-admin`. If you want least privilege, use this bundle and validate it in your target cluster before relying on it operationally.

## Switch Your `oc` Session To The Service Account

After applying the manifests, a human operator can mint a token for the service account and log in with it.

Create a token:

```bash
OCP_SA_TOKEN=$(oc -n openshift-health-check create token health-check-runner --duration=8h)
```

Log in with that token:

```bash
oc login --token="$OCP_SA_TOKEN" --server="https://api.<cluster-name>.<base-domain>:6443"
```

If you want to keep your current admin session intact, create a separate kubeconfig for the health-check service account:

```bash
TOKEN="$(oc -n openshift-health-check create token health-check-runner --duration=8h)"
oc login --token="$TOKEN" --server="https://api.<cluster-name>.<base-domain>:6443" --kubeconfig ./health-check-sa.kubeconfig
export KUBECONFIG=./health-check-sa.kubeconfig
oc whoami
```

If you are already logged in as an admin and just need the API server URL for the current cluster:

```bash
oc whoami --show-server
```

Then run the playbook with that service-account-backed session.

## Optional Manifest: Allow A User To Mint A Token Only For `health-check-runner`

If an operator needs to run `oc create token health-check-runner` but does not have elevated namespace admin rights, grant only the `serviceaccounts/token` create permission for that single service account.

Replace `<your-username>` with the real OpenShift user name:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: health-check-runner-token-creator
  namespace: openshift-health-check
rules:
  - apiGroups: [""]
    resources: ["serviceaccounts/token"]
    resourceNames: ["health-check-runner"]
    verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: health-check-runner-token-creator
  namespace: openshift-health-check
subjects:
  - kind: User
    name: <your-username>
    apiGroup: rbac.authorization.k8s.io
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: health-check-runner-token-creator
```

Verify the permission:

```bash
oc auth can-i create serviceaccounts/token -n openshift-health-check --resource-name=health-check-runner
```

Then mint the token:

```bash
oc -n openshift-health-check create token health-check-runner --duration=8h
```

## Example Manifest: Base Live Scan

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: openshift-health-check
---
# `cluster-reader` is a built-in OpenShift ClusterRole. This manifest binds the
# service account to that existing role; it does not recreate the built-in role.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: health-check-runner
  namespace: openshift-health-check
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: openshift-health-check-support-collector
rules:
  - nonResourceURLs:
      - /readyz
      - /readyz/*
      - /version
    verbs: ["get"]
  - apiGroups:
      - ""
      - apps
      - apiregistration.k8s.io
      - apiserver.config.openshift.io
      - argoproj.io
      - automationcontroller.ansible.com
      - automationhub.ansible.com
      - aap.ansible.com
      - autoscaling
      - autoscaling.openshift.io
      - addon.open-cluster-management.io
      - build.openshift.io
      - cdi.kubevirt.io
      - compliance.openshift.io
      - config.openshift.io
      - costmanagement-metrics-cfg.openshift.io
      - datadoghq.com
      - datasciencecluster.opendatahub.io
      - dynatrace.com
      - eda.ansible.com
      - external-secrets.io
      - image.openshift.io
      - imageregistry.operator.openshift.io
      - k8s.ovn.org
      - keda.sh
      - kubevirt.io
      - loki.grafana.com
      - machine.openshift.io
      - maistra.io
      - monitoring.coreos.com
      - networking.k8s.io
      - nmstate.io
      - oadp.openshift.io
      - olm.operatorframework.io
      - operator.knative.dev
      - operator.open-cluster-management.io
      - operator.openshift.io
      - operators.coreos.com
      - policy
      - project.config.openshift.io
      - ramendr.openshift.io
      - rbac.authorization.k8s.io
      - replication.storage.openshift.io
      - secrets-store.csi.x-k8s.io
      - security.openshift.io
      - serving.knative.dev
      - snapshot.storage.k8s.io
      - ssp.kubevirt.io
      - storage.k8s.io
      - template.openshift.io
      - tekton.dev
      - tuned.openshift.io
      - updateservice.operator.openshift.io
      - user.openshift.io
      - velero.io
    resources: ["*"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources:
      - namespaces
      - pods
      - pods/log
      - pods/exec
      - serviceaccounts
      - services
      - endpoints
      - configmaps
      - events
      - secrets
    verbs: ["create", "delete", "get", "list", "watch"]
  - apiGroups: ["rbac.authorization.k8s.io"]
    resources:
      - clusterrolebindings
    verbs: ["create", "delete", "get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-health-check-cluster-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-reader
subjects:
  - kind: ServiceAccount
    name: health-check-runner
    namespace: openshift-health-check
---
# `cluster-monitoring-view` is a built-in OpenShift ClusterRole. This manifest
# binds the service account to that existing role; it does not recreate it.
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-health-check-cluster-monitoring-view
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-monitoring-view
subjects:
  - kind: ServiceAccount
    name: health-check-runner
    namespace: openshift-health-check
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-health-check-support-collector
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: openshift-health-check-support-collector
subjects:
  - kind: ServiceAccount
    name: health-check-runner
    namespace: openshift-health-check
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: openshift-health-check-insights-reader
  namespace: openshift-insights
rules:
  - apiGroups: [""]
    resources:
      - pods
      - pods/log
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources:
      - pods/exec
    verbs: ["create", "get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: openshift-health-check-insights-reader
  namespace: openshift-insights
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: openshift-health-check-insights-reader
subjects:
  - kind: ServiceAccount
    name: health-check-runner
    namespace: openshift-health-check
```

## Example Manifest: Optional Node Debug

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: openshift-health-check-node-debug
rules:
  - apiGroups: [""]
    resources:
      - nodes
      - namespaces
      - pods
      - pods/log
      - pods/exec
    verbs: ["create", "delete", "get", "list", "watch"]
  - apiGroups: [""]
    resources:
      - nodes/proxy
    verbs: ["get", "create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-health-check-node-debug
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: openshift-health-check-node-debug
subjects:
  - kind: ServiceAccount
    name: health-check-runner
    namespace: openshift-health-check
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: openshift-health-check-privileged-scc
rules:
  - apiGroups: ["security.openshift.io"]
    resourceNames: ["privileged"]
    resources: ["securitycontextconstraints"]
    verbs: ["use"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: openshift-health-check-privileged-scc
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: openshift-health-check-privileged-scc
subjects:
  - kind: ServiceAccount
    name: health-check-runner
    namespace: openshift-health-check
```

## Which Features Need Which Access

- `cluster-reader`
  Covers the broad inventory sweep used by the main collector roles.
- `cluster-monitoring-view`
  Covers Thanos and Prometheus-backed checks.
- `openshift-health-check-support-collector`
  Covers the extra OpenShift-specific reads and support collectors used by this repo, including the `serviceaccounts` and `clusterrolebindings` writes required by `oc adm must-gather`.
- `openshift-health-check-insights-reader`
  Covers copying the Insights archive from the `openshift-insights` pod.
- `openshift-health-check-node-debug` and `openshift-health-check-privileged-scc`
  Cover optional `oc debug node/<node>`-based sosreport collection.

## Recommended Operational Modes

- Lowest privilege live mode:
  Apply only the base manifest. Live node diagnostics stay off unless you explicitly run with `-e collect_live_sosreport=true`.
- Full live mode without `cluster-admin`:
  Apply both manifests.
- Lowest friction mode:
  Collect `must-gather`, `inspect`, and optional node data with an admin account, then run this repo in collected mode with a lower-privilege account.
