# Kubernetes Cluster Health Check Design Guide

This guide explains the design behind the cluster health report in this repo.

The original design started from OpenShift operations, but the repo now has a broader shape:

- a rich OpenShift path
- a shared Kubernetes path
- provider-aware reporting for AKS, EKS, GKE, Rancher, and Minikube
- profile-aware scoring for production, development, and lightweight use

## Supported Cluster Types

Today the repo is designed to support these cluster types:

- OpenShift
- OpenShift SNO
- ARO
- ROSA
- ROSA HCP
- generic Kubernetes
- AKS
- EKS
- GKE
- Rancher-managed Kubernetes
- Minikube

The design is layered on purpose:

- shared Kubernetes checks for things that are portable
- OpenShift-specific checks for OpenShift-only APIs and behaviors
- provider-aware sections where safe cluster-local signals exist
- profile-aware scoring so development and lightweight clusters are not judged like production by default

OpenShift is still the deepest path in the repo. The Kubernetes path is broader now, but it intentionally stays conservative unless the cluster exposes strong local signals for a provider or platform feature.

## Best-Practice Sources

The check design and report behavior are based on a mix of vendor, upstream, and operations sources.

Main source groups:

- Red Hat OpenShift documentation
- IBM Cloud OpenShift documentation
- Kubernetes upstream documentation
- CNCF guidance and operational best practices
- GitHub OpenShift runbooks
- Microsoft AKS documentation
- AWS EKS documentation and AWS prescriptive guidance
- Google GKE documentation

Reference URLs:

- Red Hat OpenShift etcd practices:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html-single/etcd/
- Red Hat Lightspeed Advisor:
  https://docs.redhat.com/en/documentation/red_hat_lightspeed/1-latest/html-single/monitoring_your_openshift_cluster_health_with_red_hat_lightspeed_advisor/index
- IBM Cloud OpenShift cluster health and monitoring:
  https://cloud.ibm.com/docs/openshift?topic=openshift-health-monitor
  https://cloud.ibm.com/docs/openshift?topic=openshift-monitoring
- Kubernetes node pressure eviction:
  https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/
- CNCF monitoring and alerting guidance:
  https://www.cncf.io/blog/2020/06/30/kubernetes-best-practices-for-monitoring-and-alerts/
- OpenShift runbooks:
  https://github.com/openshift/runbooks
- AKS monitoring and proactive checks:
  https://learn.microsoft.com/en-us/azure/aks/monitor-aks
  https://learn.microsoft.com/en-us/azure/aks/best-practices-monitoring-proactive
  https://learn.microsoft.com/en-us/azure/aks/cluster-health-monitor
- EKS control plane and alerting guidance:
  https://docs.aws.amazon.com/eks/latest/best-practices/control-plane.html
  https://docs.aws.amazon.com/prescriptive-guidance/latest/amazon-eks-observability-best-practices/alerting-best-practices.html
- GKE observability and cluster notifications:
  https://cloud.google.com/kubernetes-engine/docs/concepts/observability
  https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-notifications

How those sources are used:

- Red Hat is the main source for OpenShift-specific health, lifecycle, operator, registry, ingress, monitoring, and hosted-topology guidance
- IBM Cloud is used to reinforce OpenShift operational guidance in managed environments
- Kubernetes and CNCF are the main sources for portable node, workload, storage, networking, lifecycle, and observability practices
- GitHub OpenShift runbooks are used as operational references for what should have an owner and a response path
- AKS, EKS, and GKE guidance shape the provider-aware sections in the Kubernetes path

This repo does not try to copy one vendor document line by line. It turns the common themes from those sources into a practical health-review model that can run from inside the cluster with cluster-local data.

Rancher-managed Kubernetes and Minikube are supported cluster types in the repo, but the current best-practice model for those paths is still driven mostly by the shared Kubernetes guidance above, not by a deep Rancher-specific or Minikube-specific source set.

It pulls together guidance from:

- Red Hat
- IBM Cloud
- Kubernetes and CNCF
- GitHub OpenShift runbooks
- AKS
- EKS
- GKE

The best-practice checks in the repo are therefore a synthesis of those sources, not a direct copy of any single document.

## The Basic Idea

Cluster health should not be reduced to a tiny shell script that runs a few `oc` commands and prints `green` or `red`.

That kind of check is easy to write, but it usually misses the things that matter:

- partial control-plane problems
- operator degradation
- upgrade blockers
- pressure building on nodes
- broken service paths
- weak operational posture

A better design has a few layers:

1. trust built-in OpenShift signals first
2. add a small number of active checks for important cluster paths
3. keep alerts clear and low-noise
4. tie serious alerts to runbooks
5. review health on a schedule, not only during incidents

That is the model this project follows.

## Minimum Scope

At a minimum, a useful cluster health check should cover:

- cluster version
- cluster operators
- API server health
- etcd health
- node readiness and pressure
- DNS
- ingress
- monitoring stack health
- upgrade readiness
- advisory findings

If a solution skips most of that, it may still be useful as a quick script, but it is not really a full cluster health review.

## What The Different Sources Agree On

### Red Hat

Red Hat already gives a lot of health signal out of the box:

- built-in monitoring
- built-in alerts
- operator status
- Insights and Lightspeed Advisor

One of the clearest messages in Red Hat guidance is that cluster operator state is a core health signal.

Normal operator state looks like this:

- `AVAILABLE=True`
- `PROGRESSING=False`
- `DEGRADED=False`

Red Hat also puts strong weight on etcd health. Useful signals include:

- WAL fsync latency
- backend commit latency
- leader changes
- peer round-trip time

Useful target values:

- etcd fsync p99 under `10 ms`
- etcd peer RTT p99 under `50 ms`

### IBM Cloud

IBM Cloud guidance points in the same direction:

- use built-in OpenShift monitoring for cluster health
- use central monitoring and logging for wider visibility

That does not conflict with the Red Hat view. It supports it.

### Kubernetes And CNCF

Upstream Kubernetes guidance treats node pressure as a serious signal:

- `MemoryPressure`
- `DiskPressure`
- `PIDPressure`

Those are not cosmetic warnings. They can lead to eviction, instability, and noisy failures elsewhere in the platform.

CNCF guidance also makes a practical point: collecting too much data without a clear standard creates noise, not clarity. Good health checks focus on a small set of useful signals and avoid pointless alert churn.

### GitHub OpenShift Runbooks

The OpenShift runbooks reinforce one simple rule:

- detection is not enough

If a signal matters enough to page someone, it should have a runbook and an owner.

### AKS, EKS, And GKE

Managed Kubernetes guidance lands in the same place:

- active checks matter
- node health matters
- control plane metrics matter
- upgrade notices matter
- logs and metrics should work together

The common pattern is hard to miss:

- use passive metrics
- add a few active checks
- keep alert design tight
- include lifecycle and upgrade risk

## The Health Model Behind This Tool

The easiest way to think about this is as a layered model.

Before the tool shows problems, it now shows the current state of the cluster near the top of the report. That is intentional. Operators usually need quick context first:

- what version is this cluster on
- how big is it
- what kind of nodes does it have
- is it public or private
- how old is it
- what does average utilization look like

Without that context, the findings are harder to interpret.

That same rule now applies across the supported cluster types. The report should identify what kind of cluster it is before it starts judging it. That is why the repo now carries cluster type in the file name and the report body, and why the Kubernetes path also shows provider and profile context.

After the current-state section, the report now uses a grouped operational summary instead of one flat findings list. That is also intentional. The goal is to surface the most important signals early, but still keep them grouped by meaning so operators do not have to mentally sort a long mixed table.

For OpenShift, the high-signal summary is grouped into:

- control plane and change
- platform and topology
- traffic, capacity, and workloads
- security, access, and guardrails
- lifecycle, observability, and auditability

For the shared Kubernetes path, the same idea applies with a smaller field set that is safe to compute across non-OpenShift clusters.

The score legend is placed directly above `Cluster Current State` so an operator can interpret the score before reading the rest of the report.

### Layer 1: Platform State

Start with the platform itself:

```bash
oc get clusterversion
oc get clusteroperators
oc get nodes
```

In a healthy cluster:

- cluster version is available
- no operator is stuck in degraded
- no important operator is progressing for too long without a clear reason
- all needed nodes are ready
- no node is under lasting pressure

This is the fastest way to answer, "is the platform obviously unhealthy?"

### Layer 2: Control Plane And etcd

This is the most sensitive technical layer.

Watch:

- API server errors
- API server latency
- API server readiness
- API server read rate
- API server write rate
- API server inflight requests
- API server stored object count
- etcd fsync p99
- etcd backend commit latency
- etcd leader count
- etcd leader changes
- etcd peer RTT p99

Useful starting targets:

- etcd fsync p99 under `10 ms`
- etcd peer RTT p99 under `50 ms`

Active checks that are worth adding:

- API `/readyz`
- DNS lookup from inside the cluster
- metrics path checks

### Layer 3: Node Health

Watch for:

- `Ready`
- node pressure
- kubelet failures
- container runtime failures
- repeated node restart or flap

These are usually page-level events:

- control plane node down
- repeated node flapping
- many worker nodes down in one zone
- wide pressure across nodes

These usually are not page-level on their own:

- one short worker restart
- one warning event with no visible impact

For the node inventory itself, the tool needs to work across more than one OpenShift style. ARO and ROSA often have cloud instance-type labels. UPI clusters often do not. SNO and ROSA HCP also have their own topology expectations. That is why the report prefers cloud instance types when they exist, but falls back to an allocatable node shape built from CPU, memory, and architecture when they do not. The point is to keep the node summary readable across UPI, ARO, ROSA, ROSA HCP, and SNO without pretending the metadata is always the same.

For ROSA HCP, control plane nodes are not expected to appear in the worker cluster node inventory. The report should reflect that in wording and not imply a fault from that shape alone.

For SNO, single-replica expectations are normal. The report should not score it like a multi-node production cluster for replica assumptions that do not apply.

### Layer 4: Service Path Checks

Metrics alone are not enough here.

Add active checks for:

- internal DNS
- service-to-service traffic
- ingress route path
- image registry path, if it matters in your environment
- monitoring and alert path

A practical setup is:

- one small namespace for checks
- one scheduled job for deeper checks
- one light long-running component for simple checks
- export results as Prometheus metrics

### Layer 5: Lifecycle And Advisory Health

Cluster health is not only about whether the cluster is up right now.

Also review:

- Insights or Lightspeed findings
- certificate expiry
- blocked upgrades
- version skew
- monitoring capacity
- security bulletins

If you skip this layer, many problems only show up when they are already urgent.

## Why This Tool Looks The Way It Does

### Use OpenShift Monitoring First

Start with what OpenShift already provides:

- Prometheus
- Alertmanager
- default alerts
- default dashboards
- OpenShift runbooks

Do not start by building a second monitoring stack from scratch.

### Add A Small Layer For What OpenShift Does Not Cover Well

Built-in monitoring still leaves a few gaps, especially around active checks for DNS, ingress, and monitoring reachability.

That is why the report design combines:

- platform state
- event and object analysis
- optional Prometheus queries
- a small set of opinionated audit checks

### Keep The Findings Readable

Raw object dumps create noise. Operators need signal.

That is why the report favors:

- a current-state section first
- a grouped operational summary instead of one flat mixed findings block
- grouped summaries
- top-N sections
- priority findings
- suggested next steps
- a separate JSON artifact for automation

The same thinking applies to wording. If a field is inferred from operator state, topology, labels, or observed configuration, the report should say that plainly instead of presenting it as a stronger fact than the data supports.

The report should also avoid debug-log presentation. Findings are more useful when they are rendered as tables or short structured summaries with plain-language labels instead of internal issue codes.

That is why newer report sections now prefer:

- one consolidated table over repeated summary and detail blocks for the same data set
- readable labels such as `Degraded` or `Not available` instead of internal issue keys
- cluster-admin sections earlier in the report and workload-oriented sections later
- counts in the top summary and detailed tables in the later sections

### Make Collection Quality Visible

One of the fastest ways to lose trust is to quietly ignore failed collection.

This tool treats collection quality as part of the result:

- command failures are tracked
- timeouts are shown
- core collection failures affect scoring
- the report tells you when it may be incomplete

That was a deliberate design choice.

## Alerting And Operational Style

Good alert design is small and clear.

Useful rules:

- page only on clear operational risk
- warn before critical where possible
- map page-level alerts to runbooks
- avoid findings that are too opinionated unless they are clearly marked

This is why the tool separates stronger health signals from more heuristic best-practice checks.

## Why The Tool Includes Heuristics At All

Some operational debt does not show up as a broken operator or failed node.

Examples:

- overprovisioned pods
- likely unused configmaps or secrets
- weak namespace hygiene
- missing probes
- weak observability posture
- stale-access review candidates for service accounts, users, and groups
- privileged RBAC grants that are operationally important but still need human interpretation

These findings are useful, but they are not the same as hard failure signals.

That is why the report now separates:

- stronger risk signals such as control-plane, operator, node, route, storage, and certificate problems
- access and security posture signals such as privileged RBAC or privileged pods
- heuristic cleanup signals such as likely unused resources or stale-access review candidates

That is why the report tries to:

- keep them out of the highest-severity platform checks
- label them clearly
- group them separately
- suggest them as cleanup or planned work instead of immediate incident work

The same principle now applies to stale-access and privileged-access reporting. The report presents those as review candidates or privileged grants, not as proven misuse.

## How To Interpret The Scores

The `0-100` cluster health score is a summary, not a replacement for reading the findings.

It is useful for:

- trending over time
- quick comparison across runs
- giving teams a simple summary number

It is not useful if treated as the whole truth.

The score only works well when read together with:

- collection completeness
- critical checks
- warning checks
- priority findings

## Implementation Shape Used In This Repo

This repo uses Ansible because it is easy to run in a controlled way and easy to fit into existing operations workflows.

The structure is split into roles:

- `preflight`
  Confirm the user is logged in and has the right access
- `collect`
  Gather raw cluster data
- `analyze`
  Build findings and summaries
- `report`
  Score, render, and write artifacts

That split keeps the code easier to reason about and easier to maintain than one very long playbook.

## Why Markdown And JSON

Markdown is there for operators.
JSON is there for machines.

That split is intentional:

- people need a readable report
- automation needs a stable structured artifact

Optional HTML and PDF exist for teams that want easy sharing, but the core outputs are still `md` and `json`.

For HTML and PDF output, the repo now uses a shared stylesheet so wide tables are easier to read. The print path prefers smaller table fonts, aggressive cell wrapping, repeated headers, and landscape layout when `wkhtmltopdf` is the active PDF engine.

## Limits Of Any Health Report

No point-in-time report can replace:

- live monitoring
- alerting
- runbooks
- human judgement

This tool is best used as:

- a regular health review
- a pre/post cluster upgrade check
- a post-incident review
- a hygiene and posture review

It is not meant to replace the platform monitoring stack.

## Final Design Rule

The design goal is simple:

Make the report useful enough that an operator can read it and decide what to do next without having to reverse-engineer the tool itself.

That is the reason for:

- layered checks
- grouped summaries
- collection completeness tracking
- suggested next steps
- readable tables and plain-language section labels
- human-readable Markdown plus machine-readable JSON
