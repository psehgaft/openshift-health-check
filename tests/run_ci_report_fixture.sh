#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_MD="${ROOT_DIR}/reports/ci-cluster-report.md"
CI_JSON="${ROOT_DIR}/reports/ci-cluster-report.json"
VENV_PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

"${VENV_PYTHON_BIN}" "${ROOT_DIR}/scripts/validate_openshift_report_template.py" \
  "${ROOT_DIR}/templates/openshift_cluster_health_report.md.j2"

"${VENV_PYTHON_BIN}" "${ROOT_DIR}/scripts/validate_cluster_health_profile.py" \
  "${ROOT_DIR}/inputs/openshift-cluster-health-profile.yml"

for capability_profile in \
  "${ROOT_DIR}/inputs/kubernetes-cluster-health-profile.yml" \
  "${ROOT_DIR}/inputs/development-k8s-cluster-health-profile.yml" \
  "${ROOT_DIR}/inputs/aks-cluster-health-profile.yml" \
  "${ROOT_DIR}/inputs/eks-cluster-health-profile.yml" \
  "${ROOT_DIR}/inputs/gke-cluster-health-profile.yml" \
  "${ROOT_DIR}/inputs/rancher-cluster-health-profile.yml" \
  "${ROOT_DIR}/inputs/minikube-cluster-health-profile.yml"; do
  "${VENV_PYTHON_BIN}" "${ROOT_DIR}/scripts/validate_openshift_capability_profile.py" \
    "${capability_profile}" \
    kubernetes_report_capability_profile
done

"${ROOT_DIR}/scripts/run_ci_report.sh" \
  "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  -e report_basename=cluster-supportability \
  -e case_bundle_path="${ROOT_DIR}/tests/fixtures"

"${VENV_PYTHON_BIN}" - "${CI_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
assert payload["metadata"]["platform_family"] == "openshift"
assert payload["supportability"]["summary"]["verdict"] == "unsupported-risk"
assert payload["supportability"]["summary"]["reference_compliance_verdict"] == "supported"
assert payload["supportability"]["reference_compliance_summary"]["verdict"] == "supported"
assert payload["supportability"]["node_diagnostics_summary"]["verdict"] == "supported"
assert payload["supportability"]["advisor_summary"]["verdict"] == "review-required"
assert payload["supportability"]["managed_gate_summary"]["verdict"] == "unsupported-risk"
assert payload["evidence"]["hygiene_summary"]["verdict"] == "review-required"
assert payload["evidence"]["hygiene_summary"]["candidate_count"] >= 2
assert len(payload["findings"]["assessment_health"]) > 0
print(path)
PY

"${VENV_PYTHON_BIN}" "${ROOT_DIR}/scripts/validate_openshift_report_output.py" \
  "${CI_MD}" \
  "${CI_JSON}"

rg -q '^# ' "${CI_MD}"
rg -q '^## Cluster Health Overview' "${CI_MD}"
rg -q '^## Node Health And Capacity' "${CI_MD}"
rg -q '^## Platform Architecture And Lifecycle' "${CI_MD}"
rg -q '^## Evidence And Supportability' "${CI_MD}"
rg -q '^## Day 2 Production Readiness' "${CI_MD}"
rg -q '^### Individual Capability Sections' "${CI_MD}"

printf 'ci fixture report ok\nmd=%s\njson=%s\n' "${CI_MD}" "${CI_JSON}"
