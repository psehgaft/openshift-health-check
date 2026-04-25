# Kubernetes Cluster Health Check

This repo contains an Ansible-based health report framework for a single cluster.

It supports:

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

The tool uses your current `oc` or `kubectl` session, reads cluster state, and writes:

- a Markdown report for people
- a JSON report for automation

Report file names include the cluster type and cluster name.

It is read-only. It does not make changes to the cluster.

By default, it collects data in parallel so the run finishes faster. It also reports collection failures and timeouts, because a health report is only useful when you can see whether the data set is complete.
Optional collectors that target APIs or config objects which are not installed on the cluster are tracked separately as not applicable, rather than counted as hard collection failures.

> [!IMPORTANT]
> This tool is a reporting aid, not a replacement for operator judgment. It helps surface health signals, risks, and likely issues, but no automated report can fully understand every cluster design,
  business requirement, or accepted exception. Review the findings critically and use your own operational judgment before making decisions.

## Design Notes

The check set in this repo follows the design in [DESIGN-PRINCIPLE.md](DESIGN-PRINCIPLE.md).

Use this `README.md` when you want to install, run, and read the tool.
Use the design notes when you want to understand why the checks exist and how the report is meant to be used.

## Quick Start

Launch the tool from the repo root:

```bash
./scripts/setup-ansible-venv.sh
source .venv/bin/activate
ansible-playbook playbooks/openshift_cluster_health_report.yml
```

For other supported cluster types, activate `.venv` and run the matching playbook in [`playbooks/`](/Users/luqman/workspace/guides/openshift-health-check/playbooks).

For OpenShift, use `playbooks/openshift_cluster_health_report.yml`. It is the primary live cluster entrypoint and now defaults to a live support collection profile of `all`. The scan builds a capability-based collector plan from the cluster type, installed tools, configured commands, and available access, then runs all applicable collectors during the same scan.

Example live OpenShift run:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml
```

`must-gather` and `inspect` can run directly from the standard `oc` access path. The live OpenShift scan also pulls the Insights Operator archive from `openshift-insights` as part of the same support collection flow. `cluster-compare` requires the plugin plus an explicit baseline/reference command. Provider-managed gates, Advisor export, and node-level `sosreport` also run in the same scan when their tool or command prerequisites are available. If possible, install `omc` as well. The OpenShift path can use it as a must-gather post-analyzer to enrich etcd and alert/rule analysis from collected support data.

The same OpenShift playbook also supports collected-state reprocessing. If you set any of these inputs, the playbook automatically resolves into the collected-state path:

- `must_gather_path`
- `inspect_path`
- `cluster_compare_path`
- `advisor_export_path`
- `managed_gates_path`
- `sosreport_paths`
- `case_bundle_path`

You can also force that path explicitly with `-e report_mode=collected`.

For CI, use the stable wrapper so the run always emits one normalized report artifact regardless of cluster type:

```bash
scripts/run_ci_report.sh playbooks/openshift_cluster_health_report.yml \
  -e live_support_collection_profile=all
```

This writes:
- `reports/ci-cluster-report.md`
- `reports/ci-cluster-report.json`

The CI report is organized by priority:
- summary and snapshot first
- priority findings next
- operational sections after that
- evidence and limitations last

## What This Tool Does

In simple terms, the tool tries to answer two questions:

1. Is the cluster healthy right now?
2. Is there anything risky, weak, or badly configured that should be fixed?

The report includes:

- an overall status
- an audit score
- a cluster health score from `0` to `100`
- a score legend directly above `Cluster Current State`
- a `Cluster Current State` section near the top
- a grouped `Operational Risk Summary` near the top
- grouped findings
- suggested next steps near the end
- execution details
- a JSON file for dashboards, scripts, or later processing

## What It Checks

The report covers the main areas operators usually care about.

The OpenShift path is the deepest path in the repo.
The Kubernetes path covers shared checks plus provider-aware sections where safe cluster-local signals exist.

For OpenShift, the final report is organized by priority:

- `P1` Supportability
- `P2` Core platform health
- `P3` Platform architecture and lifecycle
- `P4` Networking architecture
- `P5` Security and compliance
- `P6` Observability
- `P7` Backup and disaster recovery
- `P8` Node health and capacity planning
- `P9` Workload health and deployment hygiene
- `P10` Operations and lifecycle maturity
- `P11` Container platform adoption and release engineering
- `P12` Workload capability extensions
- `P13` Day 2 production readiness

Each section starts with a short recommendation and summary. The report moves from urgent problems to longer-term readiness.

Main areas:

- cluster profile and topology
- cluster version and update history
- cluster authentication setup and identity provider presence
- available updates and conditional update risks
- cluster operator health
- one consolidated cluster-operator table with availability, progression, degradation, desired version, and version drift or mismatch against cluster desired version
- cluster infrastructure component health such as authentication, DNS, ingress, image registry, monitoring, network, and ingress controllers
- machine config pool health
- node readiness and node pressure
- node role and kubelet version spread
- node inventory that works across UPI, ARO, and ROSA
- current cluster state such as visibility, uptime, node counts, worker pool shapes, node architectures, OS images, and average utilization
- normalized capacity units in the report:
  - CPU in `m`
  - memory in `MiB`
  - ephemeral storage in `GiB`
- pod density on nodes
- workload rollout health for deployments, statefulsets, and daemonsets
- workloads missing liveness, readiness, or startup probes
- platform pod issues in `openshift-*`, `kube-*`, and `default`
- restart hotspots and pods with high restart counts
- overprovisioned pod candidates
- quota pressure
- unhealthy routes and ingresses, missing backend services, and host conflicts
- observability setup, including monitoring health, log forwarding, and metrics remote write to external targets
- deprecated APIs and deprecated CRD versions
- expiring TLS certificates
- image registry risks
- network policy and namespace hygiene
- security and best-practice issues in pod specs
- privileged RBAC grants for service accounts, users, and groups
- stale-access review candidates for service accounts, users, and groups
- likely unused resources
- warning events
- optional Prometheus signals such as alerts, API latency, etcd latency, CPU, memory, and pod usage
- OpenShift control-plane signals such as:
  - API `/readyz`
  - API server read and write rates
  - API server inflight requests
  - API server stored object count
  - API server 5xx rate and p99 latency
  - etcd leader count and leader changes
  - etcd WAL fsync, backend commit, and peer RTT latency
- worker-pool, MachineSet, and failure-domain spread checks
- service, pod, and node IP capacity summaries
- node growth headroom from pod-network allocation
- external alert delivery detection from `AlertmanagerConfig`
- external storage provider detection and local-or-ephemeral-only risk
- external log forwarding and external metrics remote write posture
- internal image registry use in workloads
- pipeline, build, and DeploymentConfig inventory on OpenShift
- privileged access and stale-access review candidates
- node-to-node and control-plane latency rows in milliseconds where supported


The report also includes:

- cluster type in the file name and report body
- cluster profile mode in the Kubernetes path
- provider-specific sections for AKS, EKS, GKE, Rancher, and Minikube
- OpenShift deployment type labels for SNO and ROSA HCP
- cleaned-up section formatting that prefers readable tables and plain-language labels over debug-style issue dumps


## Signal Notes

The report prefers signals that are cluster-local, explainable, and actionable.

Use these rules when reading it:

- `direct`: the signal comes from a collected object or metric and is rendered directly
- `derived`: the signal is computed from collected data using a documented heuristic
- `unknown`: the cluster did not expose enough data to support a defensible value
- `not applicable`: the report looked for an optional feature or API that is not installed or not configured on this cluster

Important examples:

- Node growth headroom:
  - `derived`
  - estimated from pod-network CIDRs and `hostPrefix` when present
  - limited by node IP availability when node IP ranges are known
  - remains `unknown` when those network allocation details are not available
- Service, pod, and node IP capacity:
  - `direct` for observed used IPs
  - `derived` for total and available IPs from configured CIDRs
  - remains `unknown` when the relevant CIDRs are not exposed in cluster config
- Control-plane-to-control-plane latency:
  - `derived` from etcd peer RTT
  - shown in milliseconds
- Control-plane-to-worker and worker-to-worker latency:
  - `direct` only when the cluster exposes a matching Prometheus latency metric
  - otherwise shown as `unavailable`
- External alert delivery:
  - `direct`
  - inferred from discovered `AlertmanagerConfig` receivers for supported external channels
  - this shows configured delivery targets, not guaranteed runtime reachability
- Collection completeness:
  - `direct`
  - based on command execution results from the current run
  - optional collectors for APIs or config objects that are absent are shown as not applicable and do not reduce the success rate
- External storage provider detection:
  - `derived`
  - inferred from `StorageClass` provisioners and PV backends
  - local `hostPath`, local PVs, and ephemeral volumes are treated as local-only indicators
- Topology resilience:
  - `derived`
  - computed from node zone labels, worker-pool grouping, and OpenShift MachineSet replica distribution
  - warns on single-zone worker groups, missing zone labels, and imbalanced spread
- Security and workload-practice findings:
  - `direct` from collected pod and workload specs
  - scope excludes platform namespaces for user-workload checks

## OpenShift Review Coverage

The OpenShift path is designed to support a structured cluster review, but not every topic can be proven from cluster-state data alone.

Use this rule when reading the report:

- `direct`: the report collects and evaluates cluster-local data for this area
- `partial`: the report provides useful signals, but not a full end-to-end assessment
- `manual`: this area still needs process review, interviews, or external system evidence

### Infrastructure And Cluster Health

| Review area | Coverage | Current support |
| --- | --- | --- |
| OpenShift Container Platform | `direct` | ClusterVersion, update history, conditional update risks, operator health, MCP health, current-state and topology sections |
| Platform infrastructure dependencies | `partial` | Platform, topology, storage classes, PV/PVC health, route/ingress health, DNS/network/ingress operator health, worker-pool and node-shape signals |
| Node and operator status | `direct` | Node readiness, pressure, kubelet spread, cluster operators, infrastructure component inventory, consolidated operator table |
| API services and etcd health | `direct` | API `/readyz`, API latency, 5xx, read/write rates, inflight requests, stored object count, etcd leader count, leader changes, WAL fsync, backend commit, peer RTT |
| Capability and readiness for common disaster scenarios | `partial` | Topology, route and ingress health, storage health, observability forwarding, collection confidence, control-plane health, but not a full backup and restore audit |
| Environment patching process | `partial` | Current version, update history, conditional update risks, MCP state, operator drift; the human patching workflow itself is not inferred from cluster state |

### Application Development Practices Related To OpenShift

| Review area | Coverage | Current support |
| --- | --- | --- |
| Build and deploy practices | `partial` | Workload rollout health, probe coverage, restart hotspots, resource requests and limits, image-registry findings; this does not fully audit Dockerfiles or build pipelines |
| Pipeline usage | `partial` | OpenShift path inventories `Pipeline`, `PipelineRun`, failed `PipelineRun` status, and `BuildConfig` trigger posture; full CI/CD process maturity still needs human review |
| Liveness, readiness, requests, limits, and project quotas | `direct` | Probe findings, rollout findings, missing requests and limits, namespace quotas, LimitRange, NetworkPolicy, quota-pressure signals |
| Capacity planning | `partial` | Current allocatable capacity, pod density, top CPU and memory consumers, average utilization, quota pressure, restart hotspots; future growth still requires platform and application planning input |

### Security Posture Check

| Review area | Coverage | Current support |
| --- | --- | --- |
| Examine compliance requirements | `manual` | The report surfaces useful evidence such as privileged access, certificates, observability, and lifecycle issues, but it does not map findings to a formal compliance framework by itself |
| Identity and group management | `direct` | OAuth identity provider presence, privileged access review, stale-access review candidates for users, groups, and service accounts |
| Certificate policies | `partial` | TLS secret expiry checks and certificate aging signals; policy conformance beyond collected certs is still manual |
| Security Context Constraints (SCC) | `partial` | OpenShift path inventories SCCs and surfaces high-risk SCC grants; full SCC policy review still needs human assessment |
| Secrets management | `partial` | Secret reference heuristics, likely unused secrets, TLS secret expiry findings; full external secret lifecycle and policy review is still manual |
| Container image management | `partial` | Image registry exposure and policy findings, image pruner state, image registry management state, and internal image-registry use in workloads; registry signing, scanning, and external image governance remain manual unless surfaced elsewhere in-cluster |

The tool is strongest as a structured evidence-gathering report. It is explicit about which areas are backed by cluster-local evidence and which still need human review.

## Signal Catalog

This section maps the main report signals to their reason for inclusion and the main condition behind them.

| Signal family | Why it is collected | Main condition or reasoning |
| --- | --- | --- |
| ClusterVersion and update risk | upgrade safety and change readiness | `Available`, `Progressing`, `Failing`, available updates, conditional risks, and update history are first-class OpenShift lifecycle signals |
| Cluster operators and infrastructure components | control-plane and platform health | operators should normally report `Available=True`, `Progressing=False`, `Degraded=False` |
| API and etcd metrics | control-plane responsiveness and stability | latency, 5xx, inflight requests, leader changes, and peer RTT are high-signal failure predictors |
| Node readiness and pressure | platform continuity | `NotReady`, `MemoryPressure`, `DiskPressure`, and `PIDPressure` are treated as urgent platform signals |
| Worker-pool and failure-domain spread | resilience during zone or node failure | the report warns when worker groups are single-zone, zone labels are missing, or MachineSets are uneven |
| Service, pod, and node IP capacity | network exhaustion risk | each node needs an IP, workloads need pod IPs, and services need service IPs; remaining IP space is surfaced when CIDRs are known |
| Node growth headroom | scaling readiness | estimated from pod-network slot math plus known node IP availability; kept `unknown` if the cluster does not expose enough network allocation detail |
| Storage posture | persistence and resilience | warns when no external storage provider is detected or when local or ephemeral storage appears to be the only option |
| Workload rollout, probes, and restarts | application resilience | rollout gaps, missing probes, unhealthy pods, and restart hotspots indicate weak workload recovery behavior |
| Namespace hygiene | noisy-neighbor protection and baseline guardrails | user namespaces should normally have `NetworkPolicy`, `ResourceQuota`, and `LimitRange` |
| Resource requests and limits | scheduling and capacity hygiene | missing requests and limits weaken bin packing, quota control, and capacity planning |
| Build, pipeline, and image posture | delivery discipline | OpenShift path inventories builds, pipelines, triggers, and image-registry usage to support application-delivery review |
| Privileged access and SCC grants | least privilege review | privileged RBAC subjects and risky SCC grants are surfaced because they materially affect platform risk |
| Stale-access review candidates | access cleanup | these are conservative review candidates, not proofs of inactivity |
| External log, metrics, and alert delivery | operational readiness and incident response | the report checks whether logs, metrics, and alert receivers appear to reach destinations outside the cluster |
| Certificates and deprecated APIs | lifecycle and outage prevention | expiring certificates and deprecated APIs are early indicators of avoidable future failures |

## Repository Layout

- [playbooks/openshift_cluster_health_report.yml](playbooks/openshift_cluster_health_report.yml)
  Main OpenShift playbook for both live scans and collected-state reprocessing.
- [playbooks/k8s_cluster_health_report.yml](playbooks/k8s_cluster_health_report.yml)
  Generic Kubernetes playbook.
- [playbooks/development_k8s_cluster_health_report.yml](playbooks/development_k8s_cluster_health_report.yml)
  Development Kubernetes playbook.
- [playbooks/aks_cluster_health_report.yml](playbooks/aks_cluster_health_report.yml)
  AKS playbook.
- [playbooks/eks_cluster_health_report.yml](playbooks/eks_cluster_health_report.yml)
  EKS playbook.
- [playbooks/gke_cluster_health_report.yml](playbooks/gke_cluster_health_report.yml)
  GKE playbook.
- [playbooks/rancher_cluster_health_report.yml](playbooks/rancher_cluster_health_report.yml)
  Rancher Kubernetes playbook.
- [playbooks/minikube_cluster_health_report.yml](playbooks/minikube_cluster_health_report.yml)
  Minikube playbook.
- [DESIGN-PRINCIPLE.md](DESIGN-PRINCIPLE.md)
  Design notes and the reasoning behind the checks.
- [roles/preflight_openshift/tasks/main.yml](roles/preflight_openshift/tasks/main.yml)
  Login and access checks.
- [roles/preflight_common/tasks/main.yml](roles/preflight_common/tasks/main.yml)
  Shared preflight setup.
- [roles/preflight_kubernetes/tasks/main.yml](roles/preflight_kubernetes/tasks/main.yml)
  Kubernetes preflight checks.
- [roles/collect_common/tasks/main.yml](roles/collect_common/tasks/main.yml)
  Shared Kubernetes-native data collection.
- [roles/collect_openshift/tasks/main.yml](roles/collect_openshift/tasks/main.yml)
  OpenShift-specific data collection.
- [roles/collect_live_support_evidence/tasks/main.yml](roles/collect_live_support_evidence/tasks/main.yml)
  Optional live support collectors and must-gather post-analysis.
- [roles/collect_kubernetes/tasks/main.yml](roles/collect_kubernetes/tasks/main.yml)
  Kubernetes collection extension point.
- [roles/load_evidence_common/tasks/main.yml](roles/load_evidence_common/tasks/main.yml)
  Shared collected-state evidence discovery and parsing.
- [roles/load_evidence_openshift/tasks/main.yml](roles/load_evidence_openshift/tasks/main.yml)
  OpenShift collected-state loading and graph preparation.
- [roles/load_evidence_openshift_products/tasks/main.yml](roles/load_evidence_openshift_products/tasks/main.yml)
  Optional product evidence loading for collected-state OpenShift inputs, including Pipelines, Logging, GitOps, ODF, Virtualization, and OpenShift AI.
- [roles/analyze_common/tasks/main.yml](roles/analyze_common/tasks/main.yml)
  Shared workload analysis.
- [roles/analyze_openshift/tasks/main.yml](roles/analyze_openshift/tasks/main.yml)
  OpenShift-specific analysis entry point.
- [roles/analyze_kubernetes/tasks/main.yml](roles/analyze_kubernetes/tasks/main.yml)
  Kubernetes analysis extension point.
- [roles/report_common/tasks/main.yml](roles/report_common/tasks/main.yml)
  Shared reporting extension point.
- [roles/report_openshift/tasks/main.yml](roles/report_openshift/tasks/main.yml)
  OpenShift scoring, rendering, and output generation.
- [roles/report_openshift/tasks/render_collected_state_report.yml](roles/report_openshift/tasks/render_collected_state_report.yml)
  Collected-state OpenShift report rendering entrypoint.
- [templates/openshift_cluster_health_report.md.j2](templates/openshift_cluster_health_report.md.j2)
  OpenShift Markdown report template.
- [templates/openshift_supportability_report.md.j2](templates/openshift_supportability_report.md.j2)
  Collected-state OpenShift Markdown renderer built on the same shared payload model.
- [scripts/parse_must_gather.py](scripts/parse_must_gather.py)
  Must-gather summary parser.
- [scripts/parse_inspect.py](scripts/parse_inspect.py)
  Inspect summary parser.
- [scripts/parse_cluster_compare.py](scripts/parse_cluster_compare.py)
  Cluster-compare parser.
- [scripts/parse_sosreport.py](scripts/parse_sosreport.py)
  `sosreport` parser.
- [scripts/collect_insights_archive.py](scripts/collect_insights_archive.py)
  Live Insights Operator archive collector.
- [scripts/parse_insights_archive.py](scripts/parse_insights_archive.py)
  Insights Operator archive and `gathers.json` parser.
- [scripts/parse_etcd_ocp_diag.py](scripts/parse_etcd_ocp_diag.py)
  Local `etcd-ocp-diag` wrapper for must-gather analysis.
- [scripts/parse_omc.py](scripts/parse_omc.py)
  Optional `omc` wrapper for must-gather etcd and alert/rule diagnostics.
- [tests/run_supportability_fixture.sh](tests/run_supportability_fixture.sh)
  Main OpenShift collected-state fixture.
- [tests/run_supportability_inspect_fixture.sh](tests/run_supportability_inspect_fixture.sh)
  Inspect-only collected-state fixture.
- [tests/run_supportability_case_bundle_fixture.sh](tests/run_supportability_case_bundle_fixture.sh)
  Case-bundle fixture.
- [tests/run_k8s_fixture.sh](tests/run_k8s_fixture.sh)
  Generic Kubernetes smoke fixture.

## Profile Guide

Use these entrypoints:

- OpenShift production and unified live scan: [playbooks/openshift_cluster_health_report.yml](playbooks/openshift_cluster_health_report.yml)
- Generic Kubernetes production: [playbooks/k8s_cluster_health_report.yml](playbooks/k8s_cluster_health_report.yml)
- Generic Kubernetes development or lab: [playbooks/development_k8s_cluster_health_report.yml](playbooks/development_k8s_cluster_health_report.yml)
- Minikube or local lightweight cluster: [playbooks/minikube_cluster_health_report.yml](playbooks/minikube_cluster_health_report.yml)
- Provider-specific Kubernetes wrappers:
  - [playbooks/aks_cluster_health_report.yml](playbooks/aks_cluster_health_report.yml)
  - [playbooks/eks_cluster_health_report.yml](playbooks/eks_cluster_health_report.yml)
  - [playbooks/gke_cluster_health_report.yml](playbooks/gke_cluster_health_report.yml)
  - [playbooks/rancher_cluster_health_report.yml](playbooks/rancher_cluster_health_report.yml)

For OpenShift variants:

- standard OpenShift, ARO, ROSA, ROSA HCP, and SNO should use [playbooks/openshift_cluster_health_report.yml](playbooks/openshift_cluster_health_report.yml)
- the tool labels the deployment type in the report when the cluster signals are clear

Simple profile matrix:

| Use case | Playbook | Profile mode |
| --- | --- | --- |
| Production OpenShift | `openshift_cluster_health_report.yml` | `production` |
| Production Kubernetes | `k8s_cluster_health_report.yml` | `production` |
| Shared dev or lab Kubernetes | `development_k8s_cluster_health_report.yml` | `development` |
| Local Minikube | `minikube_cluster_health_report.yml` | `lightweight` |

Development wrapper defaults:

- HTML and PDF off by default
- lower collection timeout
- smaller top-N sections
- faster report shape for day-to-day lab use

## Prerequisites

Install these programs first:

- `python3`
- `openssl`

## Python Virtual Environment

This repo is configured to run Ansible from a local virtual environment in `.venv`.

Create and populate it with:

```bash
./scripts/setup-ansible-venv.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p .ansible/tmp
```

After activation, use the repo-local Ansible:

```bash
source .venv/bin/activate
ansible-playbook --version
```

You also need one working cluster CLI session:

- OpenShift: `oc`
- Kubernetes, AKS, EKS, GKE, Rancher, Minikube: `kubectl`

Access needs depend on the playbook:

OpenShift playbook:
- a working `oc login`
- a user with `cluster-admin`

Kubernetes playbooks:
- a working `kubectl` context
- cluster-wide read access that lets the tool query nodes, workloads, storage, events, CRDs, and namespace-scoped objects across the cluster

For Ansible:

- install Python dependencies from `requirements.txt` into `.venv`
- no extra Ansible collections are required
- no extra Ansible modules are required
- the playbook uses only `ansible.builtin` modules

Nice to have:

- OpenShift: access to `openshift-monitoring/thanos-querier`

Optional OpenShift helper tools:

- `oc cluster-compare`
  Used only when you want `cluster-compare` baseline drift analysis.
- `rosa`
  Used only for ROSA or other managed-service gate collection paths.
- `omc`
  Recommended must-gather helper when available. The OpenShift path can use it to extract additional must-gather diagnostics such as etcd status and alert/rule signals, which enriches the report analysis from collected cluster data.

The live OpenShift scan also collects the Insights Operator archive directly from the cluster through `oc` when support collectors are enabled, so no extra binary is needed for that source.

For `omc`, the playbook will use, in this order:

- `-e omc_binary_path=/path/to/omc` if you set it
- `scripts/omc` if you vendor the binary into the repo
- `omc` from `PATH`

If none of those are present, the playbook just runs without the extra `omc`-derived must-gather diagnostics.

Optional tools by output format:

- Markdown report: no extra tools
- JSON report: no extra tools
- HTML report: `pandoc`
- PDF report: `pandoc` plus one supported PDF engine

Supported PDF engines are checked automatically:

- `wkhtmltopdf`
- `weasyprint`
- `prince`
- `tectonic`
- `xelatex`
- `lualatex`
- `pdflatex`

Important runtime settings:

- `collection_parallelism`
  Number of cluster read commands to run at the same time. Default: `8`
- `collection_command_timeout_seconds`
  Timeout for each collection command. Default: `300`
- `keep_collection_artifacts`
  If `true`, keep the temporary raw collection file for debugging. Default: `false`
- `require_cluster_log_forwarder`
  If `true`, missing `ClusterLogForwarder` is reported as a finding. Default: `false`
- `require_external_metrics_remote_write`
  If `true`, missing external Prometheus `remoteWrite` targets are reported as findings. Default: `false`
- `warn_on_ingress_without_class`
  If `true`, `Ingress` objects with no explicit class are reported. Default: `false`

Before the playbook starts, the tool validates the current CLI session and broad cluster access:

- OpenShift path: `oc whoami` must work and `oc auth can-i '*' '*' --all-namespaces` must return `yes`
- Kubernetes path: `kubectl auth whoami` or `kubectl config current-context` must work, and `kubectl auth can-i '*' '*' --all-namespaces` must return `yes`

## Namespace Scope

Most objects are collected from all namespaces with `-A`.

For checks that should focus on customer workloads, the tool treats these as platform namespaces by default:

- `default`
- `openshift`
- `openshift-*`
- `kube-system`
- `kube-public`
- `kube-node-lease`
- `kube-*`
- `kubernetes-*`

That default works well for OpenShift, ARO, and ROSA.

Checks such as security review, best-practice review, probe coverage, and unused-resource detection skip those namespaces on purpose. That keeps platform components from creating noise in the application-focused sections.

If your environment has extra managed namespaces that should also be excluded, override:

- `platform_namespaces_regex`
- `user_namespaces_exclude_regex`

## Launch The Tool

Pick the playbook that matches the cluster you are checking.

### OpenShift

Use this for OpenShift, SNO, ARO, ROSA, and ROSA HCP:

```bash
. .venv/bin/activate
ansible-playbook playbooks/openshift_cluster_health_report.yml
```

Collected-state example:

```bash
. .venv/bin/activate
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e must_gather_path=/path/to/must-gather.local.123456 \
  -e inspect_path=/path/to/inspect-dir
```

### Generic Kubernetes

Use this for a standard Kubernetes cluster when you want the shared Kubernetes checks:

```bash
. .venv/bin/activate
ansible-playbook playbooks/k8s_cluster_health_report.yml
```

### Development Or Lab Kubernetes

Use this for shared lab or development clusters when you want lighter defaults:

```bash
. .venv/bin/activate
ansible-playbook playbooks/development_k8s_cluster_health_report.yml
```

### Provider Wrappers

Use these when you want the report name and provider context to match the target platform from the start:

```bash
. .venv/bin/activate
ansible-playbook playbooks/aks_cluster_health_report.yml
ansible-playbook playbooks/eks_cluster_health_report.yml
ansible-playbook playbooks/gke_cluster_health_report.yml
ansible-playbook playbooks/rancher_cluster_health_report.yml
ansible-playbook playbooks/minikube_cluster_health_report.yml
```

### Common Parameters

These parameters work across the playbooks:

- `report_output_dir`
  Where report files are written
- `report_basename`
  File name prefix before cluster type, cluster name, and timestamp
- `report_generate_html`
  Set to `true` or `false`
- `report_generate_pdf`
  Set to `true` or `false`
- `collection_parallelism`
  Number of collection commands to run at the same time
- `collection_command_timeout_seconds`
  Timeout for each collection command
- `keep_collection_artifacts`
  Keep the temporary raw collection file for debugging
- `report_mode`
  `auto`, `live`, or `collected`
- `must_gather_path`
  Path to an extracted `must-gather.local*` directory
- `inspect_path`
  Path to an extracted `oc adm inspect` directory
- `cluster_compare_path`
  Path to saved `oc cluster-compare` JSON output
- `advisor_export_path`
  Path to saved Advisor export JSON
- `managed_gates_path`
  Path to saved managed-service gate JSON
- `sosreport_paths`
  One or more extracted `sosreport` directories or archives
- `case_bundle_path`
  Folder containing a mix of collected-state inputs discovered automatically

Example:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_output_dir=./reports \
  -e report_basename=prod-cluster-health \
  -e report_generate_html=false \
  -e report_generate_pdf=false
```

### Report Size And Tuning Parameters

Use these when you want more or less detail in the report:

- `warning_event_limit`
- `top_restart_pod_limit`
- `top_alert_group_limit`
- `top_event_reason_limit`
- `top_namespace_issue_limit`
- `top_pvc_issue_limit`
- `top_workload_issue_limit`
- `top_security_issue_limit`
- `top_certificate_issue_limit`
- `top_deprecated_api_limit`

Example:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e warning_event_limit=25 \
  -e top_restart_pod_limit=20 \
  -e top_alert_group_limit=20 \
  -e top_event_reason_limit=20 \
  -e top_pvc_issue_limit=30
```

### Stricter Best-Practice Parameters

These are optional and make the report stricter:

- `require_cluster_log_forwarder=true`
- `require_external_metrics_remote_write=true`
- `warn_on_ingress_without_class=true`

Example:

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e require_cluster_log_forwarder=true \
  -e require_external_metrics_remote_write=true \
  -e warn_on_ingress_without_class=true
```

### Namespace Scope Parameters

Use these when your environment has extra managed namespaces that should be excluded from workload-focused checks:

- `platform_namespaces_regex`
- `user_namespaces_exclude_regex`

Example:

```bash
ansible-playbook playbooks/k8s_cluster_health_report.yml \
  -e 'platform_namespaces_regex=^(default|kube-system|kube-public|kube-node-lease|kube-.*|istio-system)$' \
  -e 'user_namespaces_exclude_regex=^(default|kube-system|kube-public|kube-node-lease|kube-.*|istio-system)$'
```

### Notes About Parameters

- You do not need to pass `provider_family` when you use a provider wrapper playbook.
- You do not need to pass `cluster_profile_mode` when you use the development or Minikube wrappers.
- The generic Kubernetes playbook tries to detect cluster type automatically.
- The OpenShift playbook expects an active `oc` session and cluster-admin access.
- The Kubernetes playbooks expect a working `kubectl` context with broad read access.

## Estimated Run Time

Run time depends on cluster size, API speed, network latency, and whether Prometheus-based checks are available.

As a rough guide:

- small cluster: about `5` to `15` minutes
- medium cluster: about `15` to `30` minutes
- large cluster: about `30` to `60` minutes

Runs usually take longer when:

- the cluster has many namespaces, pods, PVCs, or CRDs
- API calls are slow
- Prometheus is available and the optional metrics queries run
- many custom resources exist and the CRD usage checks need to inspect them

Runs can also take longer if you lower `collection_parallelism` or raise `collection_command_timeout_seconds`.

## Output

By default, the tool writes:

```text
reports/cluster-health-my-cluster-20260402T112233Z.md
reports/cluster-health-my-cluster-20260402T112233Z.json
```

The Markdown file is the main report for day-to-day review.

The JSON file is useful for:

- dashboards
- scripts
- automation
- storing results from many runs

If `pandoc` is installed, the playbook will also try to write:

```text
reports/cluster-health-my-cluster-20260402T112233Z.html
```

If `pandoc` and a supported PDF engine are installed, the playbook will also try to write:

```text
reports/cluster-health-my-cluster-20260402T112233Z.pdf
```

HTML and PDF output are best-effort. If the required tools are missing, the Markdown and JSON reports are still generated.

HTML and PDF rendering now use a shared report stylesheet. The PDF path prefers readability for wide tables by using:

- smaller table font sizing
- aggressive cell wrapping
- repeated table headers
- landscape layout when `wkhtmltopdf` is the active PDF engine

Near the top of the report, the `Cluster Current State` section shows what the cluster looks like before you get into the findings. This includes version, visibility, uptime, node counts, worker pool shapes, node platform details, and average resource usage when Prometheus data is available.

The `Cluster Current State` section uses normalized units:

- CPU in `m`
- memory in `MiB`
- ephemeral storage in `GiB`

Near the top of the report, the grouped `Operational Risk Summary` highlights the highest-signal checks in smaller themed tables. In the OpenShift path, those tables are grouped as:

- control plane and change
- platform and topology
- traffic and capacity
- security, access, and guardrails
- lifecycle, observability, and auditability

In the generic Kubernetes path, the same idea is applied with a reduced set of fields that are safe for the shared collector:

- cluster and nodes
- lifecycle, provider, and auditability
- security and guardrails
- workloads and storage

The `my-cluster` part comes from the cluster infrastructure name. If that is not available, the tool falls back to the current `oc` context name.

The report also includes a `Data Collection` section. Check that section early if a report looks too clean. It shows:

- how many collection commands were attempted
- the parallelism and timeout used
- which commands failed
- which commands timed out
- whether any core data sets were missing

By default, the temporary raw collection file is removed automatically. Set `keep_collection_artifacts=true` only when you need it for debugging.

The OpenShift report also keeps cluster-admin signals before workload-oriented sections. Workload-heavy sections such as rollout, probe, restart, and top pod usage details are lower in the report so platform health is visible first.

For node inventory, the report uses cloud instance-type labels when they exist. If they do not exist, which is common in some UPI environments, it falls back to a node shape built from allocatable CPU, memory, and architecture. That keeps the node summary useful across OpenShift installation types.

For example:

- on ARO and ROSA, you will usually see cloud instance types
- on many UPI clusters, you may see allocatable shapes instead

Both are expected. The node summary stays usable even when cloud labels are missing.

## How To Read The Report

### Overall Status

The report starts with one overall status:

- `HEALTHY`
- `WARNING`
- `CRITICAL`

This is the fast summary.

If the report shows collection failures, be careful with the result. A cluster can look healthier than it really is when part of the data could not be collected.

If the report shows optional collectors as skipped or not applicable, read those as feature absence, not as a broken run. Examples include clusters without Tekton, OADP or Velero CRDs, or clusters that do not define optional monitoring configmaps.

### Suggested Next Steps

The report includes a `Suggested Next Steps` section near the end so you can decide what to do first:

- `immediate` means do this first
- `next` means important, but not the first emergency action
- `planned` means cleanup or posture work
- `steady-state` means the cluster looks healthy and should stay on normal review

Those suggestions are written as operator actions with short admin guidance, not raw finding codes.

### Cluster Health Score

The report also gives a health score from `0` to `100`.

Score bands:

- `95-100`: `Excellent`
- `85-94.9`: `Good`
- `70-84.9`: `Fair`
- `50-69.9`: `Poor`
- `0-49.9`: `Critical`

In plain terms:

- `Excellent`: the cluster looks stable
- `Good`: the cluster is healthy but has some warnings
- `Fair`: the cluster works, but there are clear issues to fix
- `Poor`: the cluster has several meaningful problems
- `Critical`: the cluster has serious risk or active failure

### Audit Score

The report also includes a weighted audit score. That score feeds the `0-100` health score.

The audit rubric also includes `Data Collection Completeness`:

- `pass` means all collection commands worked
- `warning` means some non-core commands failed
- `critical` means one or more core commands failed

Core commands are the main data sources for cluster state, nodes, workloads, routes, ingresses, and storage.

### Best Order To Read

If you are reading the report by hand, this order usually works well:

1. `Cluster Current State`
2. `Audit Rubric`
3. `Operational Risk Summary`
4. `Priority Findings`
5. `Control Plane Signals` or provider-specific sections when present
6. `Cluster Operators`
7. `Upgrade Risk`
8. `Storage`
9. `Workload Health`
10. `Security And Best Practice Audit`
11. `Suggested Next Steps`

## Strong Signals And Heuristic Signals

Not every finding has the same weight.

Some findings are strong signals:

- cluster operators unavailable or degraded
- cluster version failing or unavailable
- nodes not ready
- node pressure
- route admission failures
- bad PV or PVC states
- quota pressure
- firing alerts
- expiring TLS certificates

Some findings are heuristic:

- unused service accounts, configmaps, secrets, and CRDs
- stale-access review candidates for service accounts, users, and groups
- overprovisioned pods
- image registry policy findings
- network policy best-practice findings
- feature findings

Heuristic means the tool is making its best guess from the data it could see. Review those findings before you treat them as cleanup work or policy violations.

## Known Limits

- unused resource checks can still show false positives
- overprovisioned pod checks use short Prometheus time windows
- certificate checks only look at `kubernetes.io/tls` secrets that can be read by `openssl x509`
- image registry checks are conservative and only flag clear risks
- pod density checks are for one cluster only
- if Prometheus access is not available, Prometheus sections will be missing but the rest of the report will still work
- if some collection commands fail or time out, the report is still generated but should be treated as incomplete

## How To Use This Tool

This tool is useful for:

- regular cluster health review
- pre or post cluster upgrade checks
- post-incident review
- platform cleanup work
- feeding JSON into dashboards or scripts

Do not use this as your only monitoring system. It works best alongside normal OpenShift monitoring, alerts, and runbooks.
