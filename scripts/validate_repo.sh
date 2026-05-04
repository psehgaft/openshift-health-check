#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/.logs"
TIMESTAMP="$(date '+%Y%m%dT%H%M%S')"
CLUSTER_TYPE_LABEL="${1:-repo}"
SANITIZED_CLUSTER_TYPE_LABEL="$(printf '%s' "${CLUSTER_TYPE_LABEL}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9._-' '-')"
LOG_FILE="${LOG_DIR}/${SANITIZED_CLUSTER_TYPE_LABEL}-run-${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

if [[ "${VALIDATE_REPO_TEE_ACTIVE:-0}" != "1" ]]; then
  export VALIDATE_REPO_TEE_ACTIVE=1
  "${BASH_SOURCE[0]}" "${CLUSTER_TYPE_LABEL}" 2>&1 | tee "${LOG_FILE}"
  exit "${PIPESTATUS[0]}"
fi

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

log "Writing validation output to ${LOG_FILE}"
export OHC_FORCE_TASK_PROGRESS=1

log "Validating YAML syntax across repository"
python3 - "${ROOT_DIR}" <<'PY'
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit(f"PyYAML is required for YAML validation: {exc}")

root = Path(sys.argv[1])
tracked_files = [
    Path(line)
    for line in __import__("subprocess").check_output(
        ["git", "-C", str(root), "ls-files"],
        text=True,
    ).splitlines()
    if line
]
yaml_files = sorted(
    root / path
    for path in tracked_files
    if path.suffix in {".yml", ".yaml"} and path.parts and path.parts[0] in {"playbooks", "roles", "inputs", "manifests"}
)

failures = []
for path in yaml_files:
    try:
        list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except Exception as exc:
        failures.append((path, exc))

if failures:
    for path, exc in failures:
        print(f"YAML parse failed: {path}: {exc}", file=sys.stderr)
    raise SystemExit(1)

print(f"YAML OK: {len(yaml_files)} files")
PY

log "Running Ansible playbook syntax checks"
while IFS= read -r playbook; do
  ansible-playbook --syntax-check "${playbook}"
done < <(find "${ROOT_DIR}/playbooks" -type f -name '*.yml' | sort)

log "Compiling Python sources"
python3 - "${ROOT_DIR}" <<'PY'
import py_compile
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
python_files = sorted(
    root / Path(line)
    for line in subprocess.check_output(["git", "-C", str(root), "ls-files"], text=True).splitlines()
    if line.endswith(".py")
)

for path in python_files:
    py_compile.compile(str(path), doraise=True)

print(f"Python OK: {len(python_files)} files")
PY

log "Checking shell script syntax"
while IFS= read -r script_path; do
  bash -n "${script_path}"
done < <(
  git -C "${ROOT_DIR}" ls-files \
    | awk '/^(scripts|tests)\/.*\.sh$/ { print "'"${ROOT_DIR}"'/" $0 }'
)

log "Validating report template"
python3 "${ROOT_DIR}/scripts/validate_openshift_report_template.py" \
  "${ROOT_DIR}/templates/openshift_cluster_health_report.md.j2"

log "Validating capability profiles"
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

log "Repository validation passed"
