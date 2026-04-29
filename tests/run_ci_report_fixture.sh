#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_MD="${ROOT_DIR}/reports/ci-cluster-report.md"
CI_JSON="${ROOT_DIR}/reports/ci-cluster-report.json"

python3 "${ROOT_DIR}/scripts/validate_openshift_report_template.py" \
  "${ROOT_DIR}/templates/openshift_cluster_health_report.md.j2"

python3 "${ROOT_DIR}/scripts/validate_openshift_capability_profile.py" \
  "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  "${ROOT_DIR}/inputs/openshift-capability-profile.yml"

for capability_profile in \
  "${ROOT_DIR}/inputs/kubernetes-capability-profile.yml" \
  "${ROOT_DIR}/inputs/development-k8s-capability-profile.yml" \
  "${ROOT_DIR}/inputs/aks-capability-profile.yml" \
  "${ROOT_DIR}/inputs/eks-capability-profile.yml" \
  "${ROOT_DIR}/inputs/gke-capability-profile.yml" \
  "${ROOT_DIR}/inputs/rancher-capability-profile.yml" \
  "${ROOT_DIR}/inputs/minikube-capability-profile.yml"; do
  python3 "${ROOT_DIR}/scripts/validate_openshift_capability_profile.py" \
    "${ROOT_DIR}/playbooks/k8s_cluster_health_report.yml" \
    "${capability_profile}" \
    kubernetes_report_capability_profile
done

"${ROOT_DIR}/scripts/run_ci_report.sh" \
  "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  -e report_basename=cluster-supportability \
  -e case_bundle_path="${ROOT_DIR}/tests/fixtures"

python3 - "${CI_JSON}" <<'PY'
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

python3 "${ROOT_DIR}/scripts/validate_openshift_report_output.py" \
  "${CI_MD}" \
  "${CI_JSON}"

rg -q '^# ' "${CI_MD}"
rg -q '^## Summary' "${CI_MD}"
rg -q '^## Node Health And Capacity' "${CI_MD}"
rg -q '^## Upgrade And Lifecycle Risk' "${CI_MD}"
rg -q '^## Evidence And Supportability' "${CI_MD}"
rg -q '^## Reference Compliance' "${CI_MD}" || rg -q '^### Reference Compliance' "${CI_MD}"
rg -q '^## Evidence Hygiene' "${CI_MD}" || rg -q '^### Evidence Hygiene' "${CI_MD}"

printf 'ci fixture report ok\nmd=%s\njson=%s\n' "${CI_MD}" "${CI_JSON}"
