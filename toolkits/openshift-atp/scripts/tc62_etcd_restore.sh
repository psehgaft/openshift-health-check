#!/usr/bin/env bash
set -uo pipefail
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required by the TC-62 recovery verification script." >&2
  exit 1
fi
cp_hosts_json="${TC62_CONTROL_PLANE_HOSTS_JSON:-[]}"
if ! printf '%s' "$cp_hosts_json" | jq -e 'type == "array" and all(.[]; type == "string")' >/dev/null; then
  echo "TC62_CONTROL_PLANE_HOSTS_JSON must be a JSON string array." >&2
  exit 1
fi
mapfile -t cp_hosts < <(printf '%s' "$cp_hosts_json" | jq -r '.[]')
recovery_host="${TC62_RECOVERY_HOST:-}"
backup_dir="${TC62_BACKUP_DIR:-}"
ssh_user="${TC62_SSH_USER:-core}"
ssh_key="${TC62_SSH_KEY_PATH:-}"
current_release="${TC62_EXPECTED_RELEASE:-}"
backup_release="${TC62_BACKUP_RELEASE:-}"
restore_timeout="${TC62_RESTORE_TIMEOUT_SECONDS:-5400}"
two_node_fencing="${TC62_TWO_NODE_FENCING:-false}"
ha_topology_confirmed="${TC62_STANDARD_HA_TOPOLOGY_CONFIRMED:-false}"


echo "== Destructive-operation preflight =="
echo "This test will disable etcd on all configured control-plane nodes and restore the selected snapshot."
echo "No cluster changes are made unless all preflight gates below pass."
if [[ "$two_node_fencing" == "true" || "$ha_topology_confirmed" != "true" ]]; then
  echo "Confirm a standard three-or-more-node HA control plane and confirm this is not a two-node-with-fencing topology; aborting before changes." >&2
  exit 1
fi
if [[ "${#cp_hosts[@]}" -lt 3 ]]; then
  echo "At least three control-plane hosts must be configured." >&2
  exit 1
fi
if [[ -z "$recovery_host" || -z "$backup_dir" || -z "$ssh_key" || -z "$current_release" || -z "$backup_release" ]]; then
  echo "Recovery host, backup path, SSH key, cluster release, and backup release are required." >&2
  exit 1
fi
if [[ "$backup_dir" != /home/core/* || "$backup_dir" == *..* || ! "$backup_dir" =~ ^/home/core/[A-Za-z0-9._/-]+$ ]]; then
  echo "Backup directory must be a safe absolute path under /home/core." >&2
  exit 1
fi
if [[ "$current_release" != "$backup_release" ]]; then
  echo "The configured backup release ($backup_release) does not match the cluster release ($current_release). Restore aborted." >&2
  exit 1
fi
if [[ ! -r "$ssh_key" ]]; then
  echo "SSH key is not readable at the Ansible controller." >&2
  exit 1
fi
found_recovery=false
declare -A seen_hosts=()
for host in "${cp_hosts[@]}"; do
  if [[ -z "$host" || -n "${seen_hosts[$host]:-}" ]]; then
    echo "Control-plane host list contains an empty or duplicate host." >&2
    exit 1
  fi
  seen_hosts[$host]=1
  [[ "$host" == "$recovery_host" ]] && found_recovery=true
done
if [[ "$found_recovery" != "true" ]]; then
  echo "Recovery host must be included in the control-plane host list." >&2
  exit 1
fi

ssh_host() {
  ssh -i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 "$ssh_user@$1" "${@:2}"
}

echo "Configured cluster release: $current_release; operator-verified backup release: $backup_release"
echo "== Verify SSH access and recovery scripts on every control-plane host =="
for host in "${cp_hosts[@]}"; do
  echo "-- $host --"
  if ! ssh_host "$host" "sudo -n test -x /usr/local/bin/disable-etcd.sh"; then
    echo "Cannot verify SSH access or disable-etcd.sh on $host." >&2
    exit 1
  fi
done
if ! ssh_host "$recovery_host" "sudo -n test -x /usr/local/bin/cluster-restore.sh"; then
  echo "cluster-restore.sh is not executable on the recovery host." >&2
  exit 1
fi

echo "== Verify matching snapshot and static pod resources on recovery host =="
backup_files="$(ssh_host "$recovery_host" "find '$backup_dir' -maxdepth 1 -type f -printf '%f\n'")"
echo "$backup_files"
snapshot_stamps="$(printf '%s\n' "$backup_files" | sed -nE 's/^snapshot_(.+)\.db$/\1/p')"
resources_stamps="$(printf '%s\n' "$backup_files" | sed -nE 's/^static_kuberesources_(.+)\.tar\.gz$/\1/p')"
matched_backup=false
while IFS= read -r stamp; do
  [[ -n "$stamp" ]] || continue
  if printf '%s\n' "$resources_stamps" | grep -Fxq "$stamp"; then
    matched_backup=true
    echo "Matching snapshot timestamp: $stamp"
    break
  fi
done <<< "$snapshot_stamps"
if [[ "$matched_backup" != "true" ]]; then
  echo "Backup must contain snapshot_<timestamp>.db and static_kuberesources_<same timestamp>.tar.gz." >&2
  exit 1
fi

echo "== Guard: refuse restore while the Kubernetes API is ready =="
if oc get --raw=/version >/dev/null 2>&1; then
  echo "The API is responding. etcd restore is a last resort and will not run against a responsive cluster." >&2
  exit 1
fi
echo "API readiness probe is unavailable; continuing with the explicitly authorized recovery."

echo "== Disable etcd on each configured control-plane node =="
for host in "${cp_hosts[@]}"; do
  echo "-- $host --"
  if ! ssh_host "$host" "sudo -n -E /usr/local/bin/disable-etcd.sh"; then
    echo "disable-etcd.sh failed on $host. Recovery has started; follow the approved recovery runbook immediately." >&2
    exit 1
  fi
done

echo "== Restore from the selected snapshot on $recovery_host =="
if ! timeout "$restore_timeout" ssh -i "$ssh_key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 "$ssh_user@$recovery_host" "sudo -n -E /usr/local/bin/cluster-restore.sh '$backup_dir'"; then
  echo "cluster-restore.sh failed or timed out. Follow the approved recovery runbook; do not retry blindly." >&2
  exit 1
fi

echo "== Wait for the API to return =="
api_ready=false
for attempt in $(seq 1 180); do
  if oc get --raw=/readyz >/dev/null 2>&1; then
    api_ready=true
    break
  fi
  sleep 10
done
if [[ "$api_ready" != "true" ]]; then
  echo "API did not return within 30 minutes. Quorum-guard change was not attempted; continue with the recovery runbook." >&2
  exit 1
fi

echo "== Temporarily disable the etcd quorum guard per the OCP recovery procedure =="
if ! oc patch etcd/cluster --type=merge -p '{"spec":{"unsupportedConfigOverrides":{"useUnsupportedUnsafeNonHANonProductionUnstableEtcd":true}}}'; then
  echo "Could not temporarily set the etcd quorum guard override." >&2
  exit 1
fi
restore_quorum_guard() {
  echo "== Restore etcd quorum guard =="
  oc patch etcd/cluster --type=merge -p '{"spec":{"unsupportedConfigOverrides":null}}'
}
trap restore_quorum_guard EXIT

echo "== Wait for cluster stability =="
if ! timeout 45m oc adm wait-for-stable-cluster; then
  echo "Cluster did not become stable within the recovery timeout." >&2
  exit 1
fi
if ! restore_quorum_guard; then
  echo "Failed to restore the etcd quorum guard." >&2
  exit 1
fi
trap - EXIT
if ! timeout 45m oc adm wait-for-stable-cluster; then
  echo "Cluster failed the stability check after quorum guard restoration." >&2
  exit 1
fi

echo "== Verify node readiness =="
nodes_json="$(oc get nodes -o json 2>&1)" || { echo "$nodes_json"; exit 1; }
printf '%s\n' "$nodes_json" | jq -e 'all(.items[]; any(.status.conditions[]; .type=="Ready" and .status=="True"))' >/dev/null 2>&1
nodes_rc=$?
oc get nodes -o wide
echo "Node readiness check exit code: $nodes_rc"

echo "== Verify ClusterOperator conditions =="
co_json="$(oc get co -o json 2>&1)" || { echo "$co_json"; exit 1; }
printf '%s\n' "$co_json" | jq -e 'all(.items[]; any(.status.conditions[]; .type=="Available" and .status=="True") and all([.status.conditions[] | select(.type=="Degraded")]; .status=="False") and all([.status.conditions[] | select(.type=="Progressing")]; .status=="False"))' >/dev/null 2>&1
co_rc=$?
oc get co
echo "ClusterOperator health check exit code: $co_rc"

echo "== Verify etcd pods and pending CSRs =="
etcd_json="$(oc get pods -n openshift-etcd -o json 2>&1)" || { echo "$etcd_json"; exit 1; }
printf '%s\n' "$etcd_json" | jq -e '[.items[] | select(.metadata.name | contains("etcd-quorum-guard") | not)] | length > 0 and all(.[]; .status.phase=="Running" and ([.status.containerStatuses[]?.ready] | all))' >/dev/null 2>&1
etcd_rc=$?
oc get pods -n openshift-etcd -o wide
echo "etcd pod readiness check exit code: $etcd_rc"
csr_json="$(oc get csr -o json 2>&1)" || { echo "$csr_json"; exit 1; }
csr_pending="$(printf '%s\n' "$csr_json" | jq -r '[.items[] | select(([.status.conditions[]?.type] | index("Approved")) == null and ([.status.conditions[]?.type] | index("Denied")) == null) | .metadata.name] | join(",")')" || { echo "Could not parse CSR inventory."; exit 1; }
echo "Pending CSRs requiring administrator review (not auto-approved): ${csr_pending:-none}"
if [[ "$nodes_rc" -ne 0 || "$co_rc" -ne 0 || "$etcd_rc" -ne 0 || -n "$csr_pending" ]]; then
  echo "Post-restore verification failed. Review node readiness, operators, etcd pods, and pending CSRs before declaring recovery complete." >&2
  exit 1
fi
echo "TC62_RESULT=PASS: API ready, all nodes Ready, ClusterOperators healthy, etcd pods ready, and no pending CSRs."
