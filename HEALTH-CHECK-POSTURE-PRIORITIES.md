# OpenShift Health Check Priorities

This file explains the report in plain language and also serves as a practical health-check guide.

It is written for two audiences:

- leadership and delivery stakeholders such as CIOs, CTOs, program managers, and service owners
- engineers, architects, consultants, and SREs who need a sensible walkthrough order for the health check

The goal is simple:

- explain the main health-check areas
- explain why they matter to the business
- provide a usable review sequence for technical teams
- keep the language easy to understand

This reflects the current state of the repo and its OpenShift report model.

## What The Report Is Trying To Answer

The report is not just checking whether the cluster is "up".

It is trying to answer five business questions:

1. Can this platform be supported when something goes wrong?
2. Is the platform stable enough for production use?
3. Is the platform secure and compliant enough for the organization’s needs?
4. Can teams operate, monitor, scale, and recover it reliably?
5. Are optional platform capabilities actually deployed where the customer expects them?

## Main Health-Check Areas

These sections are also the practical walkthrough sequence most teams should use during a health check.

### Supportability

This tells you whether the report is based on enough evidence to trust the rest of the conclusions.

Business meaning:
- If support evidence is weak, every other conclusion has lower confidence.
- A cluster that cannot be diagnosed quickly is a business risk even if it looks healthy today.

Typical concerns:
- missing diagnostics
- weak node-level evidence
- missing support bundles
- limited advisory or Insights evidence

### Core Platform Health

This is the fastest way to see if the cluster has an immediate production problem.

Business meaning:
- If core platform services are unhealthy, application stability is already at risk.

Typical concerns:
- degraded platform operators
- API or etcd instability
- node readiness problems
- machine config problems
- ingress or route failures

### Lifecycle And Architecture

This tells you whether the platform is on a safe and supportable long-term path.

Business meaning:
- A cluster can appear healthy now but still be risky if it is outdated, poorly designed, or hard to upgrade.

Typical concerns:
- unsupported or aging versions
- upgrade blockers
- weak high-availability design
- poor failure-domain spread
- architecture not matching business expectations

### Security And Compliance

This explains whether the platform’s protection model is acceptable for production use.

Business meaning:
- Security gaps can delay go-live, increase audit risk, or create exposure during incidents.

Typical concerns:
- weak identity setup
- excessive privilege
- certificate and trust problems
- image governance problems
- compliance gaps such as FIPS, CIS, PCI-DSS, NIST, FedRAMP, and related standards

### Observability

This shows whether the organization can actually see problems early and respond quickly.

Business meaning:
- A platform without usable monitoring, alerting, metrics, and logs usually has slower incident response and longer outages.

Typical concerns:
- weak monitoring
- alerts not reaching the right destination
- missing metrics
- poor log collection
- no reliable export of application, infrastructure, or audit logs

### Backup And Recovery

This tells you whether recovery is real or only assumed.

Business meaning:
- If backup and restore are weak, even a short incident can become a prolonged outage.

Typical concerns:
- backup tooling exists but restore evidence is missing
- missing schedules
- missing successful backups
- weak disaster recovery posture
- limited control-plane recovery evidence

### Capacity And Node Health

This shows whether the platform has enough headroom and whether nodes are under stress.

Business meaning:
- Capacity pressure often becomes instability, poor performance, failed scaling, or blocked growth.

Typical concerns:
- hot or pressured nodes
- high pod density
- memory or CPU saturation
- quota pressure
- poor diagnostic depth for node issues

### Workload Health

This focuses on the applications and platform workloads running on the cluster.

Business meaning:
- The platform may look healthy while important workloads are still fragile or failing.

Typical concerns:
- failing pods
- rollout problems
- restart hotspots
- probe issues
- weak workload resource settings

### Operations Maturity

This tells you how disciplined and repeatable day-to-day operations look.

Business meaning:
- Weak operating practices usually lead to avoidable downtime, inconsistent changes, and slow recovery.

Typical concerns:
- weak GitOps or declarative operations
- poor change discipline
- weak onboarding controls
- inconsistent platform management practices

### Optional Platform Capabilities

This section confirms whether advanced or customer-specific capabilities are actually present.

Business meaning:
- These are usually not the first production risk, but they matter if the customer expects them.

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
- use the “business meaning” text to explain why a finding matters
- use the report itself for the detailed technical findings, evidence, and remediation items

## Related Files

- [README.md](README.md)
- [health-check-inputs.md](./health-check-inputs.md)
- [DESIGN-PRINCIPLE.md](DESIGN-PRINCIPLE.md)
