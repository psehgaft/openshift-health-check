# TC-71: Node roles and maximum pod capacity

## Pass criteria

The corrected TC-71 queries the node inventory as JSON and validates each node:

- At least one `node-role.kubernetes.io/<role>` label is present.
- `status.capacity.pods` is exactly `250`.
- `status.allocatable.pods` is exactly `250`.

You can optionally configure `tc71_expected_node_roles` to require role names to exist somewhere in the cluster. For example, use `master`, `worker`, `worker-std`, and `worker-ht` only if all four role labels are part of this cluster's approved design. The check does not invent node roles or change labels.

## Why the reported run failed

The JSONPath included an invalid escaped colon and space in the format expression. The API returned a parser error, so it did not retrieve node capacity or labels. The prior check also looked for the substring `250`, which could report Pass when only one node had 250 pods or when 250 appeared in unrelated output.

## Recommendation for bare-metal and telco nodes

The sample is valid OpenShift syntax, but it is not a universal bare-metal or telco tuning recommendation. OpenShift 4.20 documents 250 as the default maximum, and explicitly warns that pod density must be based on the workload's CPU, memory, storage, and IP requirements. A configured value of 250 is a scheduling ceiling; it does not mean a node can safely sustain 250 CNF pods. [OpenShift 4.20 node configuration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/working-with-nodes) and [scalability and performance guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/scalability_and_performance/planning-your-environment-according-to-object-maximums)

Use this decision sequence:

1. **Inspect before changing.** If all target nodes already report `capacity.pods=250` and `allocatable.pods=250`, do not create a KubeletConfig solely for this ATP check.
2. **Scope by pool and node profile.** Determine whether control-plane, worker, `worker-std`, and `worker-ht` nodes are each expected to have a 250-pod ceiling. The sample selector targets only the default worker MCP. For custom pools, select the intended MCP labels and confirm how the pool inherits worker configuration. Do not apply one setting to every pool without reviewing scope. [OpenShift 4.20 MachineConfigPool guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/machine_configuration/index)
3. **Choose `podsPerCore` deliberately.** `podsPerCore: 0` disables that limit and is redundant when it is already the default. It makes `maxPods` the only pod-count cap, regardless of node CPU. If using a non-zero value, calculate it against the smallest CPU count in the pool so the effective limit does not fall below 250. OpenShift uses the lower of the per-core limit and `maxPods`. [OpenShift 4.20 node configuration guidance](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/working-with-nodes)
4. **Prove the density with the actual CNF profile.** Include workload requests/limits, system and infrastructure pods, CPU pinning/NUMA requirements, memory, huge pages, storage I/O, network throughput, and pod IP availability. Establish a tested per-node target with the workload owner and platform sizing process; use a lower `maxPods` if the tested target is lower. The ATP's exact-250 criterion is a compliance requirement and may need to be revised if the approved design specifies another value.
5. **Plan the rollout.** KubeletConfig changes are applied through the Machine Config Operator and can cause nodes to reboot. Apply in an approved maintenance window and wait for the targeted pools to finish updating before rerunning TC-71.

## 1. Inspect current labels and pod capacity

```bash
oc get nodes -o custom-columns=NAME:.metadata.name,ROLES:.metadata.labels,CAPACITY_PODS:.status.capacity.pods,ALLOCATABLE_PODS:.status.allocatable.pods
```

For a focused view of role labels, use:

```bash
oc get nodes -o json | jq -r '
  .items[] |
  [
    .metadata.name,
    ([((.metadata.labels // {}) | keys[]) |
      select(startswith("node-role.kubernetes.io/")) |
      sub("^node-role.kubernetes.io/"; "")] | unique | join(",")),
    (.status.capacity.pods // "missing"),
    (.status.allocatable.pods // "missing")
  ] | @tsv'
```

Expected capacity and allocatable values are `250` on every node. Compare the role labels to the approved topology document. The original command's error is fixed in the playbook; no escaping in JSONPath is needed for this query.

## 2. Configure the kubelet pod limit

OpenShift configures the maximum pod count through a `KubeletConfig` custom resource targeted at the appropriate MachineConfigPool. Example for the default worker pool:

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: KubeletConfig
metadata:
  name: worker-max-pods-250
spec:
  machineConfigPoolSelector:
    matchLabels:
      pools.operator.machineconfiguration.openshift.io/worker: ""
  kubeletConfig:
    maxPods: 250
    podsPerCore: 0
```

Save and apply only after confirming the target pool label and intended node scope:

```bash
oc get machineconfigpool --show-labels
oc apply -f worker-max-pods-250.yaml
oc get kubeletconfig worker-max-pods-250 -o yaml
```

The kubelet uses the lower limit when both `maxPods` and `podsPerCore` apply. `podsPerCore: 0` disables the per-core limit so it will not reduce the configured 250; confirm that 250 pods is appropriate for the node's CPU, memory, networking, and workload profile. Targeting the worker pool can also affect custom pools that inherit worker configuration, so verify the selector and rollout impact before applying.

## 3. Wait for the MachineConfigPool rollout

```bash
oc get machineconfigpool
```

Before declaring success, confirm the affected pool reports `UPDATED=True`, `UPDATING=False`, and `DEGRADED=False`. Kubelet configuration changes can trigger node reboots. Plan the change in an approved window and allow the pool to finish updating.

## 4. Verify effective values and role labels

```bash
oc describe node <node-name>
oc get nodes -o json | jq -r '
  .items[] |
  [.metadata.name, .status.capacity.pods, .status.allocatable.pods] | @tsv'
```

Check that `Capacity` and `Allocatable` both show `pods: 250` for every node. Confirm that each node has the role labels intended by the cluster topology.

To require cluster-wide role names in TC-71, configure the ATP inventory/group variables:

```yaml
tc71_expected_node_roles:
  - master
  - worker
  - worker-std
  - worker-ht
```

Only include roles that are supposed to exist in this cluster. Role labels use keys such as `node-role.kubernetes.io/worker-std`. If the role names are absent, update node labels and MachineConfigPool design through the cluster's approved platform configuration; do not add labels just to silence the test.

## References

- [OpenShift Container Platform 4.20: Working with nodes — Managing the maximum number of pods per node](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/working-with-nodes)
- [OpenShift Container Platform 4.20: Machine configuration — MachineConfigPools and node roles](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/machine_configuration/index)
