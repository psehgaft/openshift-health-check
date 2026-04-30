# OpenShift Health Check Priorities

This file explains the report in plain language and also serves as a practical health-check guide.


The goal is to:

- explain the main health-check areas
- explain why they matter to the business
- provide a usable review sequence for technical teams


## What The Report Is Trying To Answer

The report is not just checking whether the cluster is "up".

It is trying to answer five business questions:

1. Can this platform be supported when something goes wrong?
2. Is the platform stable enough for production use?
3. Is the platform secure and compliant enough for the organization’s needs?
4. Can teams operate, monitor, scale, and recover it reliably?
5. Are optional platform capabilities actually deployed where the customer expects them?

## Main Health-Check Areas

These sections are also the practical walkthrough sequence teams should use during a health check.

### Supportability

Why it matters:
- Weak diagnostic evidence reduces confidence in every other conclusion and slows vendor, platform, and application support when incidents happen.

What to look for:
- verify must-gather, inspect, node diagnostics, and other expected evidence were collected
- verify node, control-plane, and workload conclusions are backed by evidence, not fallback assumptions
- flag missing node coverage, missing control-plane evidence, weak advisory evidence, or incomplete support bundles
- confirm the report is not relying too heavily on inferred values where direct cluster evidence should exist
- fix evidence gaps before relying on clean findings elsewhere in the report

How to read a weak result:
- fix evidence collection first, then re-evaluate the rest of the report

### Core Platform Health

Why it matters:
- This is the fastest way to confirm whether the platform is currently safe for production traffic and normal business operations.

What to look for:
- check cluster operators for unavailable, degraded, or long-progressing states
- check API and etcd health, latency, errors, and restart behavior
- check node readiness, node pressure, and machine-config drift
- check ingress and route health
- check whether issues are localized or broad enough to affect multiple applications or the full cluster
- use this section first to decide whether the cluster is fit for production traffic

### Lifecycle And Architecture

Why it matters:
- A cluster can look healthy today and still carry high change risk, upgrade risk, or design risk that will surface later under growth, maintenance, or failure.

What to look for:
- verify OpenShift version, support phase, and upgrade path
- review upgrade blockers, warnings, deprecated APIs, and conditional update risks
- verify cluster classification: service model, install model, control-plane model, and platform type
- review worker-pool spread across failure domains and zones
- verify machine-network boundaries if the report says they were not fully derived
- confirm the architecture matches the customer’s intended operating model, not just what the platform currently happens to be running

How to read a weak result:
- treat weak results here as upcoming outage or upgrade risk, not just design debt

### Security And Compliance

Why it matters:
- Security and compliance gaps create exposure, audit friction, delayed approvals, and higher business risk during both incidents and change windows.

What to look for:
- verify identity-provider posture, privileged access, kubeadmin fallback, and tenant separation
- verify certificates, trust bundles, proxies, and custom CAs where applicable
- verify image governance, mirroring, disconnected sources, and external registry controls
- verify encryption controls such as etcd encryption, IPsec, and FIPS where required
- verify compliance evidence against the standards the customer actually requested
- separate platform control gaps from missing customer-owned policy or process decisions

How to read a weak result:
- separate platform hardening gaps from customer-policy decisions that need accept, remediate, or exempt treatment

### Observability

Why it matters:
- Weak observability increases detection time, extends outages, and makes the platform harder to operate confidently at scale.

What to look for:
- verify core platform monitoring is healthy and storing usable data
- verify alerts reach the real external destinations operations teams use
- verify application, infrastructure, and audit logs are collected and forwarded where required
- verify user workload monitoring, remote write, dashboards, and integrations where expected
- verify metrics, alerts, and logs are usable for operations, not just technically present
- flag partial setups where a component exists but usable delivery is not proven

### Backup And Recovery

Why it matters:
- Backup and disaster-recovery posture matter only if recovery is credible, testable, and aligned with business recovery expectations.

What to look for:
- verify backup tooling is configured with valid storage, active schedules, and successful recent runs
- verify restore evidence, not just backup presence
- verify control-plane recovery evidence where it applies
- verify DR configuration, protected-cluster inventory, and failover readiness where expected
- verify the difference between configured recovery, exercised recovery, and assumed recovery
- separate advisory recovery posture from proven recovery posture

### Capacity And Node Health

Why it matters:
- Capacity and node pressure usually show up as degraded performance, failed scaling, and noisy incidents before they become a visible outage.

What to look for:
- review node readiness, pressure, pod density, and allocatable-versus-requested posture
- review cluster-wide CPU and memory plus top nodes and namespaces by utilization
- review service, pod, and node IP capacity
- review whether the cluster can absorb failures, maintenance, and growth
- review whether current utilization leaves enough margin for peak load, upgrades, and node loss
- use this section to identify saturation early

How to read a weak result:
- a cluster can be green and still be out of headroom

### Workload Health

Why it matters:
- Platform stability does not guarantee application resilience, service quality, or rollout safety.

What to look for:
- review rollout status for major workload controllers
- review restart hotspots, failing pods, pending pods, and probe failures
- review readiness, liveness, and resource settings
- separate platform-wide failures from workload-specific failures
- identify whether the issue is configuration quality, runtime instability, or dependency failure
- identify workloads that are fragile even when the cluster is stable

### Operations Maturity

Why it matters:
- Weak operating discipline increases change failure risk, slows recovery, and creates repeated issues that consume engineering and support capacity.

What to look for:
- verify whether cluster and application changes are driven through GitOps or other controlled workflows
- verify whether tenant onboarding follows a governed path
- verify whether non-admin users can self-provision namespaces when they should not
- verify whether autoscaling, remediation, maintenance guardrails, and ownership patterns are intentional
- verify whether the cluster can be operated consistently by the team, not just by one experienced individual
- use this section to judge whether the platform is operationally repeatable

How to read a weak result:
- this often explains repeated incidents even when core health looks acceptable

### Optional Platform Capabilities

Why it matters:
- Optional capabilities matter when the cluster is expected to deliver a broader platform service model, not just baseline container hosting.

What to look for:
- verify optional products and integrations are actually deployed
- verify them from workload, CRD, controller, or configuration evidence, not namespace-only footprint
- separate presence from health
- verify the capability is configured in a usable way, not just installed
- confirm the cluster supports the intended service model: AI, virtualization, service mesh, serverless, custom autoscaling, security tooling, or external observability tooling

Examples from the current repo:
- OpenShift Virtualization
- OpenShift AI
- OpenShift AAP
- KEDA-based custom metrics autoscaling
- service mesh
- serverless
- Windows workloads
- GPU workloads
- sandboxed containers
- vendor observability or security tools such as Dynatrace, Datadog, Splunk, AppDynamics, Aqua, Prisma, and Qualys

## Simple Priority Model

For non-technical readers, the report can be thought of in three layers.

### Layer 1: Immediate Business Risk

These sections should get attention first:

- Supportability
- Core Platform Health
- Lifecycle And Architecture
- Security And Compliance

If any of these are weak, the cluster may not be safe to operate at scale.

### Layer 2: Operational Reliability

These sections show whether the platform can be run safely day to day:

- Observability
- Backup And Recovery
- Capacity And Node Health
- Workload Health

If these are weak, the platform may stay online but will be harder to operate and recover.

### Layer 3: Capability Maturity

These sections show how complete the platform is compared with customer expectations:

- Operations Maturity
- Optional Platform Capabilities

These matter most when the customer expects a broader platform service model, not just a working cluster.

## What Changed Compared With Older Versions

The repo has grown.

The report now covers a much wider set of optional capabilities and product integrations than older versions of this file implied.

That includes:

- more observability integrations
- more security software detection
- more OpenShift platform extensions
- stronger backup and disaster recovery checks
- more evidence-quality and supportability logic

Because of that, the older long technical list was harder to follow and no longer the best guide for non-technical readers.

## How To Use This File

If you are a business or delivery stakeholder:

- use the sections to understand where the largest business risks usually sit
- focus first on whether there is immediate production risk
- then focus on whether operations and recovery are credible
- then review whether the platform includes the capabilities the customer expects

If you are an engineer or architect:

- use the sections above as the walkthrough order for the health check
- use the “Why it matters” text to explain why a finding matters
- use the “What to look for” text as the practical review checklist for each posture
- use the report itself for the detailed technical findings, evidence, and remediation items

## Related Files

- [README.md](README.md)
- [health-check-inputs.md](./health-check-inputs.md)
- [DESIGN-PRINCIPLE.md](DESIGN-PRINCIPLE.md)
