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

> [!IMPORTANT]
> This tool is a reporting aid, not a replacement for operator judgment. It helps surface health signals, risks, and likely issues, but no automated report can fully understand every cluster design,
  business requirement, or accepted exception. Review the findings critically and use your own operational judgment before making decisions.

## Design Guide

The check set in this repo follows the design in [DESIGN-GUIDE.md](DESIGN-GUIDE.md).

Use this `README.md` when you want to install, run, and read the tool.
Use the design guide when you want to understand why the checks exist and how the report is meant to be used.

## Quick Start

Launch the tool from the repo root:

```bash
./scripts/setup-ansible-venv.sh
source .venv/bin/activate
ansible-playbook playbooks/openshift_cluster_health_report.yml
```

For other supported cluster types, activate `.venv` and run the matching playbook in [`playbooks/`](/Users/luqman/workspace/guides/openshift-health-check/playbooks).

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

The report also includes:

- cluster type in the file name and report body
- cluster profile mode in the Kubernetes path
- provider-specific sections for AKS, EKS, GKE, Rancher, and Minikube
- OpenShift deployment type labels for SNO and ROSA HCP
- cleaned-up section formatting that prefers readable tables and plain-language labels over debug-style issue dumps

## Repository Layout

- [playbooks/openshift_cluster_health_report.yml](playbooks/openshift_cluster_health_report.yml)
  Main OpenShift playbook.
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
- [DESIGN-GUIDE.md](DESIGN-GUIDE.md)
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
- [roles/collect_kubernetes/tasks/main.yml](roles/collect_kubernetes/tasks/main.yml)
  Kubernetes collection extension point.
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
- [templates/openshift_cluster_health_report.md.j2](templates/openshift_cluster_health_report.md.j2)
  OpenShift Markdown report template.

## Profile Guide

Use these entrypoints:

- OpenShift production: [playbooks/openshift_cluster_health_report.yml](playbooks/openshift_cluster_health_report.yml)
- Generic Kubernetes production: [playbooks/k8s_cluster_health_report.yml](playbooks/k8s_cluster_health_report.yml)
- Generic Kubernetes development or lab: [playbooks/development_k8s_cluster_health_report.yml](playbooks/development_k8s_cluster_health_report.yml)
- Minikube or local lightweight cluster: [playbooks/minikube_cluster_health_report.yml](playbooks/minikube_cluster_health_report.yml)
- Provider-specific Kubernetes wrappers:
  - [playbooks/aks_cluster_health_report.yml](playbooks/aks_cluster_health_report.yml)
  - [playbooks/eks_cluster_health_report.yml](playbooks/eks_cluster_health_report.yml)
  - [playbooks/gke_cluster_health_report.yml](playbooks/gke_cluster_health_report.yml)
  - [playbooks/rancher_cluster_health_report.yml](playbooks/rancher_cluster_health_report.yml)

For OpenShift variants:

- standard OpenShift, ARO, ROSA, ROSA HCP, and SNO all use [playbooks/openshift_cluster_health_report.yml](playbooks/openshift_cluster_health_report.yml)
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

- small cluster: about `1` to `5` minutes
- medium cluster: about `5` to `10` minutes
- large cluster: about `10` to `30` minutes

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
- traffic, capacity, and workloads
- security, access, and guardrails
- lifecycle, observability, and auditability

In the generic Kubernetes path, the same idea is applied with a reduced set of fields that are safe for the shared collector:

- cluster and nodes
- workloads and storage
- security and guardrails
- lifecycle, provider, and auditability

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

Both are expected. The goal is to keep the node summary useful even when cloud labels are missing.

## How To Read The Report

### Overall Status

The report starts with one overall status:

- `HEALTHY`
- `WARNING`
- `CRITICAL`

This is the fast summary.

If the report shows collection failures, be careful with the result. A cluster can look healthier than it really is when part of the data could not be collected.

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
