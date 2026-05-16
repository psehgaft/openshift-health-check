#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_MD="${ROOT_DIR}/reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.md"
CI_JSON="${ROOT_DIR}/reports/.run-state/openshift/collected-artifacts/report/ci-cluster-report.json"
CI_WORKSPACE_ROOT="${ROOT_DIR}/reports/.run-state/openshift/collected-artifacts"
CI_POSTURES_DIR="${CI_WORKSPACE_ROOT}/postures"
CI_CAPABILITIES_DIR="${CI_WORKSPACE_ROOT}/capabilities"
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

"${VENV_PYTHON_BIN}" - \
  "${ROOT_DIR}/inputs/openshift-cluster-health-profile.yml" \
  "${CI_POSTURES_DIR}" \
  "${CI_CAPABILITIES_DIR}" <<'PY'
import json
import sys
from pathlib import Path

import yaml

profile_path = Path(sys.argv[1])
postures_dir = Path(sys.argv[2])
capabilities_dir = Path(sys.argv[3])

profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
cluster_profile = profile["cluster_health_profile"]

enabled_postures = sorted(
    key for key, cfg in cluster_profile["postures"].items() if cfg.get("enabled", False)
)
enabled_capabilities = sorted(
    key for key, cfg in cluster_profile["capabilities"].items() if cfg.get("enabled", False)
)

missing = []

if not postures_dir.is_dir():
    missing.append(f"missing postures artifact directory: {postures_dir}")
if not capabilities_dir.is_dir():
    missing.append(f"missing capabilities artifact directory: {capabilities_dir}")

for key in enabled_postures:
    path = postures_dir / f"{key}.json"
    if not path.is_file():
        missing.append(f"missing posture artifact: {path}")
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("key") != key or payload.get("kind") != "posture":
        missing.append(f"invalid posture artifact contract: {path}")

for key in enabled_capabilities:
    path = capabilities_dir / f"{key}.json"
    if not path.is_file():
        missing.append(f"missing capability artifact: {path}")
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("key") != key or payload.get("kind") != "capability":
        missing.append(f"invalid capability artifact contract: {path}")

if missing:
    raise SystemExit("\n".join(missing))

print(postures_dir)
print(capabilities_dir)
PY

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
rg -q '^### Capability Assessments' "${CI_MD}"

printf 'ci fixture report ok\nmd=%s\njson=%s\n' "${CI_MD}" "${CI_JSON}"
