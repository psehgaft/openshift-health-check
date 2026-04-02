# OpenShift Cluster Health Check Guide

Research date: April 2, 2026

This guide explains the design behind the cluster health report in this repo.

It pulls together guidance from:

- Red Hat
- IBM Cloud
- Kubernetes and CNCF
- GitHub OpenShift runbooks
- AKS
- EKS
- GKE

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
- etcd fsync p99
- etcd backend commit latency
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

- grouped summaries
- top-N sections
- priority findings
- suggested next steps
- a separate JSON artifact for automation

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

These findings are useful, but they are not the same as hard failure signals.

That is why the report tries to:

- keep them out of the highest-severity platform checks
- label them clearly
- group them separately
- suggest them as cleanup or planned work instead of immediate incident work

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

## Limits Of Any Health Report

No point-in-time report can replace:

- live monitoring
- alerting
- runbooks
- human judgement

This tool is best used as:

- a regular health review
- a pre-upgrade check
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
- human-readable Markdown plus machine-readable JSON
