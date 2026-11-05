# TC-72: HugePages for CNF worker nodes

## What TC-72 requires to pass

The ATP now queries worker nodes as JSON and checks the Kubernetes Node resource fields. Every node in the selected CNF pool must report a positive HugePages quantity in both `status.capacity` and `status.allocatable` for at least one size:

- `hugepages-1Gi`, or
- `hugepages-2Mi`.

The default selector is `node-role.kubernetes.io/worker=`. If HugePages are intentionally configured only on a dedicated CNF pool, set `tc72_node_selector` to that pool's label selector. For example:

```yaml
tc72_node_selector: "node-role.kubernetes.io/worker-hp="
```

The test checks that the resource is configured and schedulable on all selected nodes. It does not guarantee that a particular amount is currently unallocated; also check existing pod requests against the CNF's HugePages requirement.

## Why the reported task failed

The old JSONPath included an invalid escape (`\\:`) and an escaped space in the output string. The JSONPath parser failed before retrieving worker information. The old Pass rule also accepted the presence of the text `1Gi=` or `2Mi=`, even when no positive HugePages quantity was present.

## Recommended configuration

OpenShift 4.20 recommends pre-allocating HugePages at boot using the Node Tuning Operator and a `PerformanceProfile`. Configure the page size and count from the CNF vendor/application requirements and the node's NUMA design. Do not allocate the same HugePages pool to every worker unless the architecture requires that.

Example profile fragment for a dedicated worker HugePages pool (replace selectors and count with approved values):

```yaml
apiVersion: performance.openshift.io/v2
kind: PerformanceProfile
metadata:
  name: worker-hp
spec:
  cpu:
    # Preserve the cluster's validated reserved/isolated CPU configuration.
    isolated: "<validated-isolated-cpu-list>"
    reserved: "<validated-reserved-cpu-list>"
  nodeSelector:
    node-role.kubernetes.io/worker-hp: ""
  hugepages:
    defaultHugepagesSize: 2M
    pages:
      - size: 2M
        count: 1024
        node: 0
```

This example reserves 1024 pages of 2 MiB (2 GiB) on NUMA node 0. Replace it with the amount, size, and NUMA placement required by your workload. Do not apply the placeholder CPU values as written; retain or generate CPU settings from the validated PerformanceProfile for the cluster.

If a PerformanceProfile already exists for the CNF nodes, update that profile rather than creating a competing profile for the same nodes.

## Step-by-step verification

1. Review the intended profile and target nodes:

   ```bash
   oc get performanceprofile
   oc get nodes --show-labels
   ```

2. Confirm HugePages appear in capacity and allocatable resources:

   ```bash
   oc get nodes -l 'node-role.kubernetes.io/worker-hp=' -o json |
     jq -r '.items[] | [
       .metadata.name,
       (.status.capacity["hugepages-1Gi"] // "0"),
       (.status.allocatable["hugepages-1Gi"] // "0"),
       (.status.capacity["hugepages-2Mi"] // "0"),
       (.status.allocatable["hugepages-2Mi"] // "0")
     ] | @tsv'
   ```

   Or inspect a node directly:

   ```bash
   oc describe node <node-name> | grep -i huge
   ```

3. Wait for the affected MachineConfigPool rollout to finish before rerunning the ATP:

   ```bash
   oc get machineconfigpool
   ```

   Verify the relevant pool is updated and not degraded. HugePages configured through a PerformanceProfile are reserved at boot, and applying a profile can trigger node reboots.

4. For actual CNF scheduling, ensure the pod requests and limits the same HugePages resource and that it has enough unallocated capacity:

   ```yaml
   resources:
     requests:
       hugepages-2Mi: 2Gi
       memory: 4Gi
     limits:
       hugepages-2Mi: 2Gi
       memory: 4Gi
   ```

   The resource name must match the page size configured on the target nodes. HugePages are not overcommitted; a pod cannot schedule if its request exceeds the free schedulable pool on its selected node.

## Telco and bare-metal considerations

Choose HugePages size, count, NUMA placement, and node selector from the CNF/RAN workload specification and validated hardware profile. For RAN DU profiles, follow the applicable certified reference design; Red Hat's OCP 4.20 telco reference specifies 1 GiB pages for x86_64 and workload-dependent page counts. These values are not universal settings for every telco cluster.

HugePages reduce page table/TLB overhead for applications designed to use them; they do not replace CPU pinning, NUMA alignment, real-time kernel configuration, CPU reservation, or end-to-end capacity validation. The number of pages must leave enough memory for the operating system and cluster services.

## References

- [OpenShift Container Platform 4.20: Optimizing memory management for workloads by using huge pages](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/scalability_and_performance/index)
- [OpenShift Container Platform 4.20: Configuring huge pages](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/postinstallation_configuration/post-install-node-tasks)
- [OpenShift Container Platform 4.20: Telco RAN DU reference design](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/scalability_and_performance/telco-hub-ref-design-specs)
