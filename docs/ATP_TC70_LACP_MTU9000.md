# TC-70: Validate LACP bonding and MTU 9000

## Purpose

TC-70 passes only when the cluster has at least one runtime `bond0` and every discovered `bond0` satisfies all of these checks:

- Bonding mode is `IEEE 802.3ad` (LACP).
- `MII Status` is `up`.
- The bond's runtime MTU is `9000`.

The ATP checks the live host state on each node. A node without `bond0` is reported as outside the check; if no node has `bond0`, TC-70 fails because the required configuration was not found.

## Why the previous command failed

The previous JSONPath format string included an invalid escape sequence (`\\:`) and an escaped space. The JSONPath parser rejected the format string before it could query anything. In addition, a NodeNetworkConfigurationEnactment (NNCE) reports policy enactment status; it is not a reliable runtime inventory of interface MTUs. The corrected ATP inspects the node's `/proc/net/bonding/bond0` and `ip link` output through `oc debug`.

## Prerequisites

1. Authenticate to the target cluster with `oc login`.
2. Use an account permitted to debug the target nodes (normally a cluster administrator).
3. Ensure the cluster has the Kubernetes NMState Operator if NNCPs are used to manage the bonds.
4. Coordinate the configuration with the network team. The switch ports connected to each bond member must be configured in the same LACP port-channel/EtherChannel. Jumbo frames must be supported end-to-end by the NICs, switches, and any hypervisor or network path.
5. Use the actual node selector and physical interface names for the cluster. Do not apply the sample manifest unchanged to production.

## Review configured policy and enactment

List the desired policies and their status:

```bash
oc get nncp
```

Inspect a policy that is intended to create `bond0`:

```bash
oc get nncp <policy-name> -o yaml
```

List per-node enactments and inspect a failing enactment:

```bash
oc get nnce
oc get nnce <node-name>.<policy-name> -o yaml
```

Confirm the policy selects the intended nodes, requests `bond0` as a bond, sets `link-aggregation.mode: 802.3ad`, and sets `mtu: 9000`. Wait for the NNCP to become `Available` and review any NNCE traceback before checking runtime state.

## Example NNCP fragment

Adapt the policy name, node selector, addresses, and physical interface names to the cluster design. The example illustrates the LACP and MTU fields only; preserve the cluster's existing IP, route, DNS, and primary network configuration.

```yaml
apiVersion: nmstate.io/v1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: worker-bond0-lacp
spec:
  nodeSelector:
    node-role.kubernetes.io/worker: ""
  desiredState:
    interfaces:
      - name: bond0
        type: bond
        state: up
        mtu: 9000
        link-aggregation:
          mode: 802.3ad
          options:
            miimon: "100"
            lacp_rate: fast
          port:
            - <physical-interface-1>
            - <physical-interface-2>
      - name: <physical-interface-1>
        type: ethernet
        state: up
        mtu: 9000
      - name: <physical-interface-2>
        type: ethernet
        state: up
        mtu: 9000
```

Applying an NNCP can change node networking and interrupt connectivity if the policy is incorrect. Validate it against the cluster's network design and maintenance/change process before applying.

## Run the same runtime checks manually

For each node expected to have `bond0`:

```bash
oc debug node/<node-name> -- chroot /host bash -c \
  'cat /proc/net/bonding/bond0; ip -d link show bond0'
```

Expected evidence includes `Bonding Mode: IEEE 802.3ad`, `MII Status: up`, and `mtu 9000`.

## If TC-70 fails

- **No bond0 found:** Confirm whether the cluster design requires a bond named `bond0`. If the interface is named differently, update the ATP check to the approved interface name rather than treating a different design as a pass.
- **NNCP not Available or NNCE has an error:** Review the policy selector, interface names, existing network state, and the NNCE traceback. Correct the policy through the approved networking workflow.
- **LACP mode is wrong or MII is down:** Verify both switch ports are members of the same LACP group, both links are connected, and LACP is enabled on both ends.
- **MTU is not 9000:** Set the intended MTU on the bond and its member interfaces, then verify that the full network path supports jumbo frames.
- **Debug inspection fails:** Check node readiness, API connectivity, debug permissions, and the `oc debug` output.

Rerun the ATP after correction. A Pass means runtime checks succeeded on every discovered `bond0`; a policy's desired state alone is not sufficient evidence.

## References

- [Red Hat OpenShift Container Platform 4.20: Kubernetes NMState](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/kubernetes_nmstate/k8s-nmstate-updating-node-network-config) — NNCP/NNCE behavior, bond configuration, and policy verification.
- [Red Hat OpenShift Container Platform 4.20: Hardware networks](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/hardware_networks/index) — LACP configuration and MTU configuration examples.
- [Red Hat OpenShift Container Platform 4.20: Advanced networking](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/advanced_networking/index) — jumbo frame and hardware MTU prerequisites.
- [Red Hat OpenShift Container Platform 4.20: Troubleshooting](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/observability/support/troubleshooting) — accessing host files and diagnostics through node debug.
