# OpenShift Health Check and Architecture Toolkit

Ansible toolkit that builds a **cluster health report** for one cluster at a time.

| Mode | Input | Output |
| --- | --- | --- |
| **Live** | Current `oc` / `kubectl` session | Markdown + JSON under `reports/` |
| **Collected** | must-gather, inspect, or support case bundle | Same report formats |

The tool **does not change cluster workload configuration**. Optional node diagnostics (`oc debug node`, `sosreport`) may create temporary debug resources when enabled.

> [!IMPORTANT]
> Findings are signals and likely risks. Review them before operational decisions.

## 5-minute Quick Start (OpenShift live)

```bash
git clone https://github.com/psehgaft/openshift-health-check.git
cd openshift-health-check

./scripts/setup-ansible-venv.sh
source .venv/bin/activate

oc login https://api.<cluster-name>.<domain>:6443
oc whoami

# Production-safe first run: solid evidence, no node sosreport
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=live \
  -e report_performance_profile=standard \
  -e collect_live_sosreport=false
```

Reports appear under `reports/`. For more variants (fast/full, collected mode, resume, selectors), see **[docs/QUICKSTART.md](docs/QUICKSTART.md)**.

## Supported platforms

OpenShift · OpenShift SNO · ARO · ROSA · ROSA HCP · generic Kubernetes · AKS · EKS · GKE · Rancher-managed Kubernetes · Minikube

OpenShift is the deepest path (`playbooks/openshift_cluster_health_report.yml`). Other types use the matching playbook under [`playbooks/`](playbooks/).

## What the report answers

1. Is the cluster healthy right now?
2. What is risky, weak, or misconfigured?

Each major section follows the same contract:

1. What is the gap?
2. Why does it matter?
3. What should be done?
4. Who likely owns it?
5. How do we know it is fixed?

Design rationale: [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md).

## Common options

| Argument | Typical values | Purpose |
| --- | --- | --- |
| `report_mode` | `live`, `collected`, `auto` | Live cluster vs offline artifacts |
| `report_performance_profile` | `fast`, `standard`, `full` | Evidence depth / runtime |
| `collect_live_sosreport` | `true` / `false` | Node-level diagnostics (disable in production unless approved) |
| `collected_evidence_root` | path | Case bundle / must-gather / inspect root |
| `report_run_mode` | `fresh`, `resume_last_failure` | Resume after a failed run |
| `selected_postures` | comma-separated keys | Limit posture sections |
| `selected_capabilities` | comma-separated keys | Limit capability sections |
| `report_output_dir` | path | Override default `reports/` |

### Collected mode

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_mode=collected \
  -e collected_evidence_root=/path/to/case-bundle-or-must-gather
```

### Resume after failure

```bash
ansible-playbook playbooks/openshift_cluster_health_report.yml \
  -e report_run_mode=resume_last_failure
```

## Bastion bootstrap (optional)

```bash
# Ubuntu
sudo bash scripts/setup-bastion-ubuntu.sh

# CentOS / RHEL-compatible
sudo bash scripts/setup-bastion-centos.sh
```

## Unified toolkit

This repository also integrates the shell/ACM/certificate/DNS/Headlamp toolkit and a pinned architecture generator. The Ansible report remains the canonical engine.

```bash
python3 scripts/unified_healthcheck.py --help
```

Details: [docs/three-repository-integration.md](docs/three-repository-integration.md).

## Validate changes

```bash
scripts/validate_repo.sh openshift
```

CI-stable report filenames:

```bash
scripts/run_ci_report.sh playbooks/openshift_cluster_health_report.yml
# → reports/ci-cluster-report.md and reports/ci-cluster-report.json
```


## Ansible playbooks

The repository includes dedicated playbooks for OpenShift, Kubernetes, ATP, certificates, DNS, and a legacy compatibility path. Each playbook has documented prerequisites, configurable variables, execution examples, and expected outputs in the [playbook reference](playbooks/README.md).

| Playbook | Purpose | Execution |
| --- | --- | --- |
| [OpenShift health report](playbooks/openshift_cluster_health_report.yml) | Live or collected-evidence OpenShift health report | `ansible-playbook -i inventory.ini playbooks/openshift_cluster_health_report.yml` |
| [Kubernetes health report](playbooks/k8s_cluster_health_report.yml) | Generic Kubernetes health report | `ansible-playbook -i inventory.ini playbooks/k8s_cluster_health_report.yml` |
| [AKS health report](playbooks/aks_cluster_health_report.yml) | AKS-specific Kubernetes health profile | `ansible-playbook -i inventory.ini playbooks/aks_cluster_health_report.yml` |
| [EKS health report](playbooks/eks_cluster_health_report.yml) | EKS-specific Kubernetes health profile | `ansible-playbook -i inventory.ini playbooks/eks_cluster_health_report.yml` |
| [GKE health report](playbooks/gke_cluster_health_report.yml) | GKE-specific Kubernetes health profile | `ansible-playbook -i inventory.ini playbooks/gke_cluster_health_report.yml` |
| [Rancher health report](playbooks/rancher_cluster_health_report.yml) | Rancher-managed Kubernetes health profile | `ansible-playbook -i inventory.ini playbooks/rancher_cluster_health_report.yml` |
| [Minikube health report](playbooks/minikube_cluster_health_report.yml) | Lightweight Minikube profile | `ansible-playbook -i inventory.ini playbooks/minikube_cluster_health_report.yml` |
| [Development Kubernetes report](playbooks/development_k8s_cluster_health_report.yml) | Reduced collection profile for development clusters | `ansible-playbook -i inventory.ini playbooks/development_k8s_cluster_health_report.yml` |
| [ATP](playbooks/atp.yml) | OpenShift Acceptance Test Procedure with Markdown/HTML evidence | `ansible-playbook -i inventory.ini playbooks/atp.yml` |
| [Certificate audit](playbooks/openshift_certificate_audit.yml) | OpenShift certificate inventory and expiration checks | `ansible-playbook -i localhost, playbooks/openshift_certificate_audit.yml` |
| [DNS validation](playbooks/openshift_dns_validation.yml) | DNS and resolver checks over SSH to inventory hosts | `ansible-playbook -i inventories/openshift_dns_validation/hosts.ini.example playbooks/openshift_dns_validation.yml -e expected_domain=example.com` |
| [Legacy OpenShift health check](playbooks/legacy/openshift_healthcheck_legacy.yml) | Compatibility entry point for the legacy collector | `ansible-playbook -i inventory.ini playbooks/legacy/openshift_healthcheck_legacy.yml` |

Before running a report, activate the repository virtual environment and select the matching authenticated `oc` or `kubectl` context. Some ATP cases and live support collectors can modify cluster state or create temporary debug resources; review their gates and permissions before enabling them. For variable definitions, prerequisites, and report artifact details for every entry point, see [playbooks/README.md](playbooks/README.md).

## Documentation map

| Doc | Purpose |
| --- | --- |
| [playbooks/README.md](playbooks/README.md) | Per-playbook prerequisites, variables, run commands, and expected results |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Shortest path and common command variants |
| [docs/ANSIBLE_GALAXY_LAYOUT.md](docs/ANSIBLE_GALAXY_LAYOUT.md) | Reusable role structure and specialist Ansible entry points |
| [docs/ATP_PLAYBOOK_GUIDE.md](docs/ATP_PLAYBOOK_GUIDE.md) | ATP role variables, evidence, operational gates, and case troubleshooting links |
| [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md) | Why the report is structured this way |
| [docs/ocp-health-check-sa-rbac.md](docs/ocp-health-check-sa-rbac.md) | Dedicated ServiceAccount / RBAC |
| [docs/three-repository-integration.md](docs/three-repository-integration.md) | Unified toolkit workflow |
| [docs/cluster-health-extension-guide.md](docs/cluster-health-extension-guide.md) | Extending checks |
| [docs/openshift-live-api-fallback-catalog.md](docs/openshift-live-api-fallback-catalog.md) | Collected-mode live API fallback |

## License

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
