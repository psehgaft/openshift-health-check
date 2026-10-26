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

## Documentation map

| Doc | Purpose |
| --- | --- |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Shortest path and common command variants |
| [docs/DESIGN-PRINCIPLE.md](docs/DESIGN-PRINCIPLE.md) | Why the report is structured this way |
| [docs/ocp-health-check-sa-rbac.md](docs/ocp-health-check-sa-rbac.md) | Dedicated ServiceAccount / RBAC |
| [docs/three-repository-integration.md](docs/three-repository-integration.md) | Unified toolkit workflow |
| [docs/cluster-health-extension-guide.md](docs/cluster-health-extension-guide.md) | Extending checks |
| [docs/openshift-live-api-fallback-catalog.md](docs/openshift-live-api-fallback-catalog.md) | Collected-mode live API fallback |

## License

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
