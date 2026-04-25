#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_DIR="${ROOT_DIR}/tests/fixtures/k8s-smoke"
FAKE_KUBECTL="${FIXTURE_DIR}/mock-kubectl"
REPORT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rancher-fixture-reports.XXXXXX")"
LOG_PATH="${TMPDIR:-/tmp}/rancher-fixture.log"
trap 'rm -rf "${REPORT_DIR}"' EXIT

ANSIBLE_LOCAL_TEMP="${TMPDIR:-/tmp}/ansible-local" \
ANSIBLE_REMOTE_TEMP="${TMPDIR:-/tmp}/ansible-remote" \
ANSIBLE_STDOUT_CALLBACK=minimal \
ansible-playbook "${ROOT_DIR}/playbooks/rancher_cluster_health_report.yml" \
  -e kube_cli="${FAKE_KUBECTL}" \
  -e report_output_dir="${REPORT_DIR}" \
  -e report_generate_html=false \
  -e report_generate_pdf=false \
  > "${LOG_PATH}" 2>&1

report_json="$(find "${REPORT_DIR}" -maxdepth 1 -name 'k8s-cluster-health-*.json' -print | sort | tail -n 1)"
report_md="$(find "${REPORT_DIR}" -maxdepth 1 -name 'k8s-cluster-health-*.md' -print | sort | tail -n 1)"

if [[ -z "${report_json}" || -z "${report_md}" ]]; then
  echo "failed to detect newly generated Rancher fixture reports" >&2
  tail -n 40 "${LOG_PATH}" >&2 || true
  exit 1
fi

python3 - "${report_json}" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
payload = json.loads(report_path.read_text(encoding="utf-8"))

assert payload["metadata"]["platform_family"] == "kubernetes"
assert payload["metadata"]["provider_family"] == "rancher"
assert payload["metadata"]["cluster_profile_mode"] == "production"
assert payload["health_summary"]["status"] in {"HEALTHY", "WARNING", "CRITICAL"}
assert int(payload["health_summary"]["nodes_total"]) == 1
assert payload["cluster_profile"]["infrastructure_name"] == "fixture-k8s-context"
assert payload["cluster_current_state"]["node_counts"]["total"] == 1
assert int(payload["metrics"]["report_collection"]["failed_commands"]) == 0
assert payload["metrics"]["provider_current_state"]["provider"] == "rancher"
print(report_path)
PY

rg -q '^# Kubernetes Cluster Health Report' "${report_md}"
rg -q '^## Report Context' "${report_md}"
rg -q '^## At A Glance' "${report_md}"
rg -q '^## Health Scoring' "${report_md}"

printf 'rancher fixture report ok\njson=%s\nmd=%s\nlog=%s\n' "${report_json}" "${report_md}" "${LOG_PATH}"
