# OpenShift Health Check Posture Priorities

This file lays out the main health-check areas in the order they should usually be reviewed. It follows [health-check-inputs.md](./health-check-inputs.md) and the way this repo now builds the report.

Use it as a practical review guide when you want to walk through the cluster one posture at a time.

If you are new to the repo, start with [README.md](README.md) for setup and basic usage, then read [DESIGN-PRINCIPLE.md](DESIGN-PRINCIPLE.md) for the bigger picture. Come back to this file when you are ready to read the OpenShift report section by section.

## Suggested Review Sequence

1. Supportability
   - evidence completeness and quality
   - `must-gather`, `inspect`, `sosreport`, Insights archive coverage
   - Advisor / Insights posture
   - managed-gate posture where relevant
   - baseline / reference comparison posture
   - ability to gather node, control-plane, and platform evidence when needed
2. Core Platform Health
   - cluster operators
   - etcd health and latency
   - API health
   - node readiness and pressure
   - machine config pool health
   - ingress / route health
   - registry health
3. Platform Architecture And Lifecycle
   - supported version and how up to date it is
   - upgrade readiness and conditional risks
   - HA / topology posture
   - cluster shape and role separation
   - architecture suitability for intended business use
4. Networking Architecture
   - ingress / load balancer posture
   - DNS / FQDN integration
   - route and ingress conflicts
   - proxy / egress posture
   - network policy coverage
5. Security And Compliance
   - identity providers
   - SCC / privileged access posture
   - secrets handling
   - certificate and trust posture
   - image policy posture
   - namespace hygiene
   - Compliance Operator posture, standards posture: `FIPS`, `FedRAMP`, `HIPAA`, `PCI-DSS`, `SOC`, `SOX`, `NIST`, `CIS`
6. Observability
   - monitoring health
   - alert health and delivery
   - warning events
   - metrics availability and remote write
   - logging posture, `application`, `infrastructure`, `audit` log collection and export posture
   - Insights / telemetry posture
7. Backup And Disaster Recovery
   - OADP / Velero footprint
   - backup storage locations
   - schedules
   - successful backup evidence
   - restore evidence
   - machine remediation posture
   - DR readiness indicators
8. Node Health And Capacity Planning
   - CPU, memory, storage, pod density
   - quota and limit posture
   - requests / limits hygiene
   - scale posture
   - current utilization vs expected growth
   - node diagnostics quality
9. Workload Health And Deployment Hygiene
   - rollout health
   - unhealthy pods
   - High restart pods
   - readiness / liveness probes
   - service and endpoint health
   - workload resource posture
10. Operations And Lifecycle Maturity
    - declarative operations
    - GitOps usage
    - patching and upgrade discipline
    - operational repeatability
    - onboarding and operating model maturity
11. Container Platform Adoption And Release Engineering
    - CI / CD and pipeline posture
    - BuildConfig trigger posture
    - release workflow maturity
    - developer / application onboarding patterns
    - platform capability adoption
12. Workload Capability Extensions
    - `Virtualization`
    - `AI`
    - model serving / notebook / runtime footprint
    - extension health when installed
13. Day 2 Production Readiness
    - lifecycle and upgrade readiness
    - observability maturity
    - backup and recovery maturity
    - security and compliance posture
    - operations maturity
    - workload capability readiness
    - production operating model maturity

## Priority Order

### P1. Supportability

Recommendations: Start here. Before trusting the rest of the report, make sure the evidence is good enough. Look for missing or weak `must-gather`, `inspect`, `sosreport`, Insights archive, Advisor, or reference-comparison evidence. If node diagnostics are only partial, keep this posture in review instead of treating it as fully supported.

Why first:
- If the cluster cannot be supported or troubleshot effectively, every other conclusion is lower-confidence.

Primary review scope:
- evidence completeness and quality
- `must-gather`, `inspect`, `sosreport`, Insights archive coverage
- Advisor / Insights posture
- managed-gate posture where relevant
- baseline / reference comparison posture
- ability to gather node, control-plane, and platform evidence when needed

### P2. Core Platform Health

Recommendations: Use this section to find urgent runtime problems first. Focus on degraded or unavailable control-plane components, not-ready nodes, API trouble, ingress trouble, and etcd instability. Be careful with simple `Progressing` states unless they also hurt availability or clearly degrade the cluster.

Why second:
- Immediate operator, control-plane, node, or routing failures are the most urgent runtime risk.

Primary review scope:
- cluster operators
- etcd health and latency
- API health
- node readiness and pressure
- machine config pool health
- ingress / route health
- registry health

### P3. Platform Architecture And Lifecycle

Recommendations: Use this section to answer two questions: is the cluster on a supported path, and is the architecture solid enough for production use? Pay close attention to support status, upgrade blockers, conditional update risks, failure-domain spread, and weak topology signals. Treat low-confidence classification as an evidence gap, not as an architecture problem by itself.

Why third:
- Unsupported versions, weak topology, or poor lifecycle posture create systemic risk even when the cluster looks healthy today.

Primary review scope:
- supported version and how up to date it is
- upgrade readiness and conditional risks
- HA / topology posture
- cluster shape and role separation
- architecture suitability for intended business use

### P4. Networking Architecture

Recommendations: Use this section to review the actual access design, not just object errors. Focus on route and ingress conflicts, exposed namespaces, proxy settings, egress posture, and whether traffic paths look safe and intentional. Keep baseline `NetworkPolicy` gaps as supporting context unless they affect exposed workloads.

Why fourth:
- Network and access design problems often present as broad service instability, partial outages, or future scale blockers.

Primary review scope:
- ingress / load balancer posture
- DNS / FQDN integration
- route and ingress conflicts
- proxy / egress posture
- network policy coverage

### P5. Security And Compliance

Recommendations: Use this section to review the real security and compliance picture. Focus on identity setup, privileged access, certificate health, active compliance standards, and failed compliance checks. Treat namespace guardrails as baseline governance context, not as the strongest security signal.

Why fifth:
- Security and compliance gaps can be production blockers and may also indicate broader operational immaturity.

Primary review scope:
- identity providers
- SCC / privileged access posture
- secrets handling
- certificate and trust posture
- image policy posture
- namespace hygiene
- Compliance Operator posture
- standards posture:
  - `FIPS`
  - `FedRAMP`
  - `HIPAA`
  - `PCI-DSS`
  - `SOC`
  - `SOX`
  - `NIST`
  - `CIS`

For compliance standards, review:
- configured or not
- actively enabled or not
- scan health
- failed checks
- for `FIPS`, runtime state only when explicit node evidence exists

### P6. Observability

Recommendations: Use this section to check whether monitoring, alerting, metrics, and logs are ready to support operations. Confirm what is configured, what can be verified, and what is only partly visible from cluster data. Treat missing external delivery as a gap only when that delivery is actually expected.

Why sixth:
- Weak monitoring, logging, and alerting increase mean time to detect and resolve incidents.

Primary review scope:
- monitoring health
- alert health and delivery
- warning events
- metrics availability and remote write
- logging posture
- confirmation that `application`, `infrastructure`, and `audit` logs are collected
- confirmation those logs are exported where expected
- Insights / telemetry posture

### P7. Backup And Disaster Recovery

Recommendations: Use this section to decide whether recovery looks real, not just whether backup objects exist. Clean successful backup and restore evidence matters more than simple object counts. If restore testing is missing, treat that as weaker confidence in recovery, not the same as having no backup capability at all.

Why seventh:
- Clusters without credible recovery posture can tolerate only shallow incidents.

Primary review scope:
- OADP / Velero footprint
- backup storage locations
- schedules
- successful backup evidence
- restore evidence
- machine remediation posture
- DR readiness indicators

### P8. Node Health And Capacity Planning

Recommendations: Use this section to check node condition, capacity pressure, density, and growth risk. Focus on not-ready nodes, pressure signals, hot nodes, quota pressure, and density. Keep storage posture and diagnostics confidence visible, but do not let them outweigh real runtime health unless they clearly affect workloads.

Why eighth:
- Capacity, density, and node-level drift tend to show up as instability, poor performance, or blocked growth.

Primary review scope:
- CPU, memory, storage, pod density
- quota and limit posture
- requests / limits hygiene
- scale posture
- current utilization vs expected growth
- node diagnostics quality

### P9. Workload Health And Deployment Hygiene

Recommendations: Use this section to separate real workload trouble from softer hygiene debt. Start with unhealthy pods, failed rollouts, restart hotspots, and probe problems. Keep things like overprovisioning or endpoint cleanup as lower-priority context unless they are clearly affecting service health.

Why ninth:
- Platform health can look acceptable while workloads are still fragile, unhealthy, or badly configured.

Primary review scope:
- rollout health
- unhealthy pods
- restart hotspots
- readiness / liveness probes
- service and endpoint health
- workload resource posture

### P10. Operations And Lifecycle Maturity

Recommendations: Use this section to check how the cluster is run day to day. Focus on identity setup, backup execution, machine remediation where needed, and whether the operating model looks repeatable. GitOps can help, but it is not a hard requirement for every cluster.

Why tenth:
- This affects repeatability, maintainability, and how safely the platform evolves over time.

Primary review scope:
- declarative operations
- GitOps usage
- patching and upgrade discipline
- operational repeatability
- onboarding and operating model maturity

### P11. Container Platform Adoption And Release Engineering

Recommendations: Use this section to review how teams build and deliver on the platform. Separate real delivery problems, like failed `PipelineRun`s or `BuildConfig`s that need review, from simple tool inventory.

Why eleventh:
- Adoption and release engineering maturity affects platform value and delivery quality, but is usually less urgent than platform risk.

Primary review scope:
- CI / CD and pipeline posture
- BuildConfig trigger posture
- release workflow maturity
- developer / application onboarding patterns
- platform capability adoption

### P12. Workload Capability Extensions

Recommendations: This section is mainly about workload extensions such as `Virtualization` and `AI`. Other platform features can show up as context, but they should not drive the posture. If these extensions are not installed, treat that as context, not as a problem. If they are installed, their health matters more than simple presence counts.

Why twelfth:
- Optional platform capabilities matter, but only after the base platform is supportable, healthy, and governable.

Primary review scope:
- `Virtualization`
  - primarily under workload health
  - also reflects Day 2 maturity
- `AI`
  - platform capability adoption and workload posture
  - model serving / notebook / runtime footprint

### P13. Day 2 Production Readiness

Recommendations: This is the final roll-up section. Use it to answer one question: is this cluster ready for real Day 2 production work? It should pull together lifecycle, upgrades, observability, recovery, security, operations maturity, workload extensions, and evidence confidence. Keep it short and put the biggest blockers first.

Why last:
- This should be synthesis, not repetition. It rolls up what the earlier sections say about production maturity.

Primary review scope:
- GitOps
- external secrets
- autoscaling
- compliance adoption
- backup adoption
- monitoring and logging maturity
- Insights posture
- production operating model maturity

## Review Rule

When reviewing each posture:
- prefer explicit collected evidence over inference
- mark uncertain items as `unknown` instead of guessing
- separate:
  - `configured`
  - `active`
  - `healthy`
  - `supported`
- do not treat product presence alone as proof of good posture
