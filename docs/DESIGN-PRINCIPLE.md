# Kubernetes Cluster Health Check Design Notes

This guide explains how the cluster health report in this repo is designed and why it works the way it does.

If you are new here, read the docs in this order:

1. Start with [README.md](../README.md) for setup and basic usage.
2. Read this file to understand the design.

The original design started from OpenShift operations, but the repo has grown into something broader:

- a rich OpenShift path
- a shared Kubernetes path
- provider-aware reporting for AKS, EKS, GKE, Rancher, and Minikube
- profile-aware scoring for production, development, and lightweight use

The execution model is also broader than the original live-only design:

- one primary OpenShift playbook, `playbooks/openshift_cluster_health_report.yml`
- a live cluster scan path that gathers directly from the cluster
- a collected-state reprocessing path for `must-gather`, `inspect`, `cluster-compare`, Advisor export, managed gates, `sosreport`, and case bundles
- one shared OpenShift analysis/report model used by both paths

That matters because the design is not only about what gets checked. It is also about making live scans and collected-state analysis land in the same report structure and the same decision model.

## Current OpenShift Model

The OpenShift path now follows a few simple principles:

1. Prefer live cluster collection when access is available.
2. Treat collected-state inputs as a first-class supported path, not a separate product.
3. Normalize both paths into the same analysis graph.
4. Keep one OpenShift report model, even when the source is `must-gather` or another collected-state input.
5. Use optional support analyzers only when they add signal and are actually available.

Examples of those optional analyzers:

- `etcd-ocp-diag` for must-gather etcd log analysis
- `omc` for must-gather etcd and alert/rule enrichment when installed
- `cluster-compare` for reference drift
- `sosreport` for node-level diagnostics

The goal is to let these tools enrich the report, not split the repo into separate report families.

## Current Report Model

The OpenShift report now follows one order, from immediate risk to broader readiness:

1. Platform Health
2. Node Health And Capacity
3. Backup And Disaster Recovery
4. Application Access And Network Isolation
5. Observability
6. Security And Governance
7. Workload Health
8. Platform Architecture And Lifecycle
9. Capacity Planning Snapshot
10. Declarative Operations
11. Container Platform Adoption And Release Engineering
12. Day 2 Production Readiness

`Evidence And Supportability` still exists, but it now renders under `Appendix` instead of the main section order.

This keeps the report readable:

- early sections answer whether the cluster is safe to operate right now
- middle sections explain resilience, security, and workload quality
- later sections cover operating model, delivery practice, and production-readiness roll-up

Each posture section should start with a short recommendation and summary before the detailed tables.

More importantly, every major posture section should answer the same five questions:

1. What is the gap?
2. Why does it matter?
3. What should be done?
4. Who likely owns the action?
5. How can the team tell it is fixed?

That is the section contract for this repo. The report should behave like a practical remediation guide, not just a status dump.

In the current template, that contract shows up as a recurring section structure:

- a short leadership-oriented summary
- evidence-backed findings
- an action plan
- a suggested owner
- a clear completion signal such as `Done When`

If a section does not help the reader answer those five questions, it is incomplete even if the evidence is technically correct.

If you want the short version of that review flow, start with the first three report sections and move down only after supportability and platform health look trustworthy.

## Supported Cluster Types

Right now the repo is designed to support these cluster types:

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

OpenShift is still the deepest path in the repo. The Kubernetes path is broader now, but it stays conservative unless the cluster exposes strong local signals for a provider or platform feature.

## Best-Practice Sources

The check design and report behavior come from a mix of vendor docs, upstream guidance, and real operations practice.

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
- Prometheus/Thanos metrics from OpenShift monitoring are treated as an official data source for checks where time-series evidence improves accuracy, after cluster-state evidence sources have established object and configuration context

This repo does not try to copy one vendor document line by line. It turns the common themes from those sources into a practical review model that can run from inside the cluster with cluster-local data.

Rancher-managed Kubernetes and Minikube are supported cluster types in the repo, but the current best-practice model for those paths is still driven mostly by the shared Kubernetes guidance above, not by a deep Rancher-specific or Minikube-specific source set.

The best-practice checks in the repo are a blend of those sources, not a direct copy of any single document.

## The Basic Idea

Cluster health should not be reduced to a tiny shell script that runs a few `oc` commands and prints `green` or `red`.

That kind of check is easy to write, but it usually misses the things that really matter:

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

## Review Scope Mapping

The OpenShift path is meant to support a real platform review, not just a pass or fail health check. That said, the design still separates three kinds of review coverage:

- `direct`: the report can support the review area with cluster-local data and clear findings
- `partial`: the report can provide strong supporting signals, but not a complete judgment
- `manual`: the review area depends on process, external systems, or evidence outside the cluster

That distinction matters because several important customer review topics are not purely technical cluster-state questions.

### Infrastructure And Cluster Health

- OpenShift Container Platform: `direct`
  Signals include ClusterVersion, operator state, MCP state, topology, lifecycle, and current-state context.
- Platform infrastructure dependencies: `partial`
  The report can speak to platform, node shape, failure-domain spread, IP headroom, storage classes, storage posture, PV/PVC health, route and ingress health, and core platform operators. It cannot directly validate the underlying hypervisor, SAN, firewall, or upstream network design beyond the signals visible in-cluster.
- Node and operator status: `direct`
  This is a first-class area in the design.
- API services and etcd health: `direct`
  This is a first-class area in the design.
- Capability and readiness for common disaster scenarios: `partial`
  The report helps with resilience signals such as topology, control-plane health, storage health, route and ingress continuity, and observability forwarding. It does not prove backup and restore readiness by itself.
- Environment patching process: `partial`
  The report can show current version, update history, conditional risks, and MCP state. It cannot prove the governance or process quality of patch execution on its own.

### Application Development Practices Related To OpenShift

- Build and deploy practices: `partial`
  The report checks rollout health, probe coverage, resource requests and limits, restart hotspots, build inventory, pipeline signals, and image-registry posture. It does not inspect every container build workflow or image construction practice.
- Pipeline usage: `partial`
  The OpenShift path inventories `Pipeline`, `PipelineRun`, failed `PipelineRun` state, and `BuildConfig` trigger posture, but does not prove CI/CD process quality on its own.
- Cluster-hosted CI/CD runners and agents: `partial`
  The report inventories runner-like pods for GitLab Runner, Jenkins agents, GitHub Actions runners, Azure DevOps agents, and generic CI/CD runners when they are visible in cluster evidence. It reports pod health, scheduling pressure, restarts, resource-request coverage, and privileged runner pods, but queue depth, busy runner percentage, job duration, and failure-rate trends require runner-native metrics, Prometheus/Thanos, or the CI/CD product API.
- Liveness, readiness, requests, limits, and project quotas: `direct`
  These are already first-class checks in the report.
- Capacity planning: `partial`
  The report shows current capacity and current stress signals. Projected growth still requires application and infrastructure planning outside the cluster report.

### Security Posture Check

- Examine compliance requirements: `manual`
  The report can provide evidence, but not a formal control mapping by itself.
- Identity and group management: `direct`
  The report checks identity provider presence, privileged grants, and stale-access review candidates.
- Certificate policies: `partial`
  The report can show certificate expiry and related risks, but policy compliance is broader than expiry dates.
- Security Context Constraints (SCC): `partial`
  The OpenShift path inventories SCCs and high-risk SCC grants, but a full SCC policy review still requires human assessment.
- Secrets management: `partial`
  The report includes secret reference heuristics, likely unused secrets, and TLS secret expiry. Full lifecycle, rotation, vault integration, and policy compliance are broader than those checks.
- Container image management: `partial`
  The report evaluates image-registry posture, internal image-registry use in workloads, and some registry policy risks, but not the full external image governance chain.

The design goal is not to overclaim. The report should help an assessor move faster, show strong technical evidence, and clearly point out where human review is still needed.

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

Those thresholds are reflected directly in the OpenShift report:

- etcd WAL fsync p99 warns above `10 ms`
- etcd peer RTT p99 warns above `50 ms`
- API server p99 latency warns above `1 s` and is displayed in `ms`

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

The current report extends that same model into cluster-network and scaling posture:

- IP exhaustion risk is treated as a health and growth concern
- failure-domain spread is treated as a resilience concern
- external alert delivery is treated as an operational readiness concern
- external storage presence is treated as a persistence and disaster-readiness concern

## The Health Model Behind This Tool

The easiest way to think about this is as a layered model.

Before the tool shows problems, it shows the current state of the cluster near the top of the report. Operators usually need quick context first:

- what version is this cluster on
- how big is it
- what kind of nodes does it have
- is it public or private
- how old is it
- what does average utilization look like

Without that context, the findings are harder to interpret.

That same rule now applies across the supported cluster types. The report identifies what kind of cluster it is before it starts evaluating it. That is why the repo carries cluster type in the file name and the report body, and why the Kubernetes path also shows provider and profile context.

After the current-state section, the report uses a grouped operational summary instead of one flat findings list. This surfaces the highest-signal checks early without forcing operators to sort through a long mixed table.

For OpenShift, the high-signal summary is grouped into:

- control plane and change
- platform and topology
- traffic and capacity
- security, access, and guardrails
- lifecycle, observability, and auditability

For the shared Kubernetes path, the same idea applies with a smaller field set that is safe to compute across non-OpenShift clusters.

The summary now also includes cluster-growth and topology signals when available:

- service, pod, and node IP capacity
- estimated node growth headroom from pod-network allocation
- worker-pool and MachineSet zone spread
- external storage posture
- external alert delivery posture

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

Platform state also now includes topology and scaling posture because those are early indicators of resilience problems:

- worker nodes should be spread across failure domains where the platform supports them
- worker-pool groups should not collapse into a single zone unintentionally
- MachineSet replicas should not be heavily skewed across zones
- the cluster should still have network and IP headroom to add more nodes when scale-out is needed

## Signal Catalog

This section explains why the main signals exist and what conditions the report uses behind them.

### Version, Operators, And Control Plane

- `ClusterVersion`, update history, and conditional update risk:
  - reason: patching and upgrade readiness
  - condition: OpenShift-native lifecycle objects are trusted first
- cluster operators and platform component status:
  - reason: OpenShift operator state is one of the strongest built-in health signals
  - condition: healthy state is normally `Available=True`, `Progressing=False`, `Degraded=False`
- API `/readyz`, API latency, 5xx, request rates, inflight requests, and stored object count:
  - reason: control-plane responsiveness and overload detection
  - condition: Prometheus-backed fields render when monitoring access is available
- etcd leader count, leader changes, WAL fsync, backend commit, and peer RTT:
  - reason: control-plane stability and storage-path health
  - condition: OpenShift monitoring exposes these metrics through Prometheus

### Topology, Network, And Growth

- worker-pool and failure-domain spread:
  - reason: resilience during zone or rack failure
  - condition: derived from worker node zone labels and worker-pool grouping
- MachineSet spread and replica balance:
  - reason: OpenShift worker capacity should stay distributed across zones
  - condition: derived from MachineSet zone labels and replica counts
- service, pod, and node IP capacity:
  - reason: service creation, workload scheduling, and node growth all depend on available IP space
  - condition: total and available IPs are derived from known CIDRs; observed used IPs are direct counts
- node growth headroom:
  - reason: operators need to know how many more nodes can be added before network allocation becomes the limit
  - condition: estimated from pod-network CIDRs and `hostPrefix` when available, then constrained by known node IP availability
  - if those details are not exposed, the report keeps the value as `unknown`

### Storage And Persistence

- storage classes, PVs, PVCs, and quota pressure:
  - reason: persistence and namespace-level storage pressure are critical platform signals
  - condition: direct inventory plus simple unhealthy phase checks
- external storage provider detection:
  - reason: clusters should not rely only on local or ephemeral storage for persistent workloads
  - condition: inferred from `StorageClass` provisioners and PV backend types
- local-or-ephemeral-only risk:
  - reason: local `hostPath`, local PVs, and ephemeral volumes alone are weak persistence signals
  - condition: warns when those patterns are present but no external persistent storage provider is detected

### Observability, Alerting, And Delivery

- monitoring operator health and Thanos route availability:
  - reason: without monitoring access, many later signals become weaker or unavailable
  - condition: based on operator conditions and route discovery
- external log forwarding:
  - reason: incident data should survive cluster-local failures
  - condition: `ClusterLogForwarder` outputs are classified as external vs cluster-local
- external metrics remote write:
  - reason: external retention and off-cluster analysis improve resilience and auditability
  - condition: based on cluster-monitoring and user-workload-monitoring config
- external alert delivery:
  - reason: alerts should reach the teams who need them outside the cluster
  - condition: based on discovered `AlertmanagerConfig` receivers for supported external channels such as email, Slack, PagerDuty, Opsgenie, webhook, VictorOps, and WeChat
  - this proves configured delivery targets, not runtime reachability

### Workloads, Guardrails, And Security

- rollout health, unhealthy user pods, restart hotspots, and probe coverage:
  - reason: these are practical application resilience signals
  - condition: evaluated only for user workload namespaces, excluding platform namespaces
- large replica workloads:
  - reason: very large replica counts can be intentional, but they are worth review because they can amplify scheduling, network, and failure-domain issues
  - condition: default review threshold is greater than `10` desired replicas
- pods without parent owners:
  - reason: ownerless pods often indicate drift, debugging leftovers, or weak deployment discipline
  - condition: pods without `ownerReferences`, excluding completed pods
- workload label governance:
  - reason: recommended Kubernetes and OpenShift labels help ownership, operations, and reporting
  - condition: checks for recommended application labels and, on OpenShift `DeploymentConfig`, runtime labels
- namespace hygiene:
  - reason: `NetworkPolicy`, `ResourceQuota`, and `LimitRange` reduce noisy-neighbor risk
  - condition: checks user namespaces only, excluding platform namespaces
- privileged access, SCC grants, and stale-access review:
  - reason: least privilege and access cleanup are important platform review topics
  - condition: privileged grants are direct RBAC and SCC findings; stale-access items are conservative review candidates, not proofs of inactivity

## Unknown And Unavailable Values

The report uses `unknown` or `unavailable` in several places by design.

- `unknown` means the cluster did not expose enough object data to compute a defensible derived value
- `unavailable` usually means the signal depends on an active metric query that was not available in the current run
- `not applicable` means the report checked for an optional API or config object that is simply not present on this cluster

Examples:

- IP totals and available counts stay `unknown` when the relevant CIDRs are not exposed
- node growth headroom stays `unknown` when pod-network allocation details are missing
- control-plane-to-worker and worker-to-worker latency stay `unavailable` unless the cluster exposes a suitable Prometheus metric
- report confidence drops when collection failures or fallback synthesis paths reduce certainty
- optional collectors for absent APIs or config objects are surfaced separately and do not count as hard collection failures

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
- optional collectors that are not relevant to the current cluster are shown separately as not applicable
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

Capability sections follow the same rule. If capability assessment does not complete with collected evidence, the report should preserve the section shape for ownership and expected evidence, but it must declare those entries `not-assessed` rather than claiming the capability was evaluated.

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

For HTML and PDF output, the repo now uses a shared stylesheet so wide tables are easier to read. The print path prefers smaller table fonts, aggressive cell wrapping, tighter cell padding, repeated headers, and landscape output for both `wkhtmltopdf` and LaTeX-based fallback PDF engines.

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
