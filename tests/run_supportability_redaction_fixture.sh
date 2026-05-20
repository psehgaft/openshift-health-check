#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "${ROOT_DIR}/scripts/repo-runtime-env.sh"
BUNDLE_PATH="${ROOT_DIR}/tests/fixtures"
REPORT_DIR="$(mktemp -d "${REPO_TMP_ROOT}/supportability-redaction-reports.XXXXXX")"
ARTIFACT_DIR="${REPO_TMP_ROOT}/supportability-redaction-artifacts"
MANIFEST_PATH="${ARTIFACT_DIR}/redaction-manifest.json"
REDACTED_BUNDLE_PATH="${ARTIFACT_DIR}/redacted-bundle"
ANSIBLE_PLAYBOOK_BIN="${ROOT_DIR}/.venv/bin/ansible-playbook"
VENV_PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

rm -rf "${ARTIFACT_DIR}"
mkdir -p "${ARTIFACT_DIR}"
trap 'rm -rf "${REPORT_DIR}" "${ARTIFACT_DIR}"' EXIT

cleanup_repo_ansible_temp_dirs

ANSIBLE_LOCAL_TEMP="${REPO_ANSIBLE_LOCAL_TEMP}" \
ANSIBLE_REMOTE_TEMP="${REPO_ANSIBLE_REMOTE_TEMP}" \
ANSIBLE_STDOUT_CALLBACK=minimal \
"${ANSIBLE_PLAYBOOK_BIN}" "${ROOT_DIR}/playbooks/openshift_cluster_health_report.yml" \
  -e report_output_dir="${REPORT_DIR}" \
  -e report_basename=cluster-supportability \
  -e case_bundle_path="${BUNDLE_PATH}" \
  -e write_redaction_manifest=true \
  -e redaction_manifest_path="${MANIFEST_PATH}" \
  -e write_redacted_bundle=true \
  -e redacted_bundle_output_dir="${REDACTED_BUNDLE_PATH}" \
  >/dev/null

report_json="$(find "${REPORT_DIR}" -maxdepth 1 -name 'cluster-supportability-openshift-*.json' -print | sort | tail -n 1)"

"${VENV_PYTHON_BIN}" - "${report_json}" "${MANIFEST_PATH}" "${REDACTED_BUNDLE_PATH}" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
redacted_root = Path(sys.argv[3])
manifest_path_resolved = manifest_path.resolve()
redacted_root_resolved = redacted_root.resolve()

payload = json.loads(report_path.read_text(encoding="utf-8"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

assert payload["evidence"]["redaction_outputs"]["manifest_written"] is True
assert payload["evidence"]["redaction_outputs"]["redacted_bundle_written"] is True
assert payload["evidence"]["redaction_outputs"]["manifest_path"] == str(manifest_path_resolved)
assert payload["evidence"]["redaction_outputs"]["redacted_bundle"]["path"] == str(redacted_root_resolved)
assert manifest["summary"]["candidate_count"] >= 3
assert (redacted_root_resolved / "case-bundle-sensitive/id_rsa").exists()
assert "REDACTED FILE" in (redacted_root_resolved / "case-bundle-sensitive/id_rsa").read_text(encoding="utf-8")
assert (redacted_root_resolved / "must-gather.local.mock/quay-io-openshift-release-dev-ocp-v4.0-art-dev-sha256-mock/cluster-scoped-resources/resources.yaml").exists()
print(report_path)
PY

printf 'redaction fixture ok\njson=%s\nmanifest=%s\nredacted=%s\n' "${report_json}" "${MANIFEST_PATH}" "${REDACTED_BUNDLE_PATH}"
