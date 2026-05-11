#!/usr/bin/env python3
"""Collect control-plane backup artifact evidence through oc debug node."""

import argparse
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


PUBLIC_REGISTRY_HINTS = ("quay.io", "registry.redhat.io", "registry.access.redhat.com")


def run(argv: List[str], timeout: int):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect control-plane backup artifact evidence from OpenShift nodes.")
    parser.add_argument("--kube-cli", default="oc")
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--search-path",
        action="append",
        default=[],
        help="Candidate host directory to scan for snapshot_*.db and static_kuberesources_* archives.",
    )
    return parser.parse_args()


def parse_timestamp_from_name(path: str) -> str:
    name = Path(path).name
    for pattern in [
        r"^snapshot_(.+)\.db$",
        r"^static_kuberesources_(.+)\.tar(?:\.gz)?$",
    ]:
        match = re.match(pattern, name)
        if match:
            return match.group(1)
    return ""


def iso_from_epoch(value: Optional[Union[float, int]]) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def collect_node_files(kube_cli: str, node: str, search_paths: List[str], timeout: int) -> Dict[str, Any]:
    quoted_paths = " ".join(shlex.quote(p) for p in search_paths)
    remote_script = f"""
for dir in {quoted_paths}; do
  if [ -d "$dir" ]; then
    find "$dir" -maxdepth 3 -type f \\( -name 'snapshot_*.db' -o -name 'static_kuberesources_*.tar.gz' -o -name 'static_kuberesources_*.tar' \\) -printf 'FILE\\t%T@\\t%p\\n'
  fi
done
""".strip()
    cmd = [
        kube_cli,
        "debug",
        "--as-root",
        f"node/{node}",
        "--",
        "chroot",
        "/host",
        "/bin/sh",
        "-c",
        remote_script,
    ]
    result = run(cmd, timeout=timeout)
    node_payload = {
        "name": node,
        "rc": result.returncode,
        "stderr": (result.stderr or "").strip(),
        "stdout": (result.stdout or "").strip(),
        "search_paths": search_paths,
        "snapshot_files": [],
        "static_kuberesource_files": [],
        "matching_pairs": [],
    }
    if result.returncode != 0:
        return node_payload

    by_timestamp = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]
    for raw_line in (result.stdout or "").splitlines():
        parts = raw_line.split("\t", 2)
        if len(parts) != 3 or parts[0] != "FILE":
            continue
        mtime = float(parts[1])
        path = parts[2].strip()
        entry = {
            "path": path,
            "mtime_epoch": mtime,
            "mtime": iso_from_epoch(mtime),
            "timestamp_key": parse_timestamp_from_name(path),
        }
        if Path(path).name.startswith("snapshot_"):
            node_payload["snapshot_files"].append(entry)
            by_timestamp.setdefault(entry["timestamp_key"], {})["snapshot"] = entry
        elif Path(path).name.startswith("static_kuberesources_"):
            node_payload["static_kuberesource_files"].append(entry)
            by_timestamp.setdefault(entry["timestamp_key"], {})["static"] = entry

    for ts_key, pair in sorted(by_timestamp.items()):
        if not ts_key or "snapshot" not in pair or "static" not in pair:
            continue
        latest_epoch = max(pair["snapshot"]["mtime_epoch"], pair["static"]["mtime_epoch"])
        node_payload["matching_pairs"].append(
            {
                "timestamp_key": ts_key,
                "snapshot_path": pair["snapshot"]["path"],
                "static_kuberesources_path": pair["static"]["path"],
                "latest_mtime_epoch": latest_epoch,
                "latest_mtime": iso_from_epoch(latest_epoch),
            }
        )
    return node_payload


def newest_pair_age_hours(nodes: List[Dict[str, Any]]) -> Optional[float]:
    latest = None
    for node in nodes:
        for pair in node.get("matching_pairs", []):
            epoch = pair.get("latest_mtime_epoch")
            if epoch is None:
                continue
            latest = epoch if latest is None else max(latest, epoch)
    if latest is None:
        return None
    return round((datetime.now(timezone.utc).timestamp() - float(latest)) / 3600.0, 2)


def main() -> int:
    args = parse_args()
    search_paths = args.search_path or [
        "/home/core/assets/backup",
        "/var/lib/etcd-backup",
        "/var/backups/etcd",
        "/opt/backups/etcd",
    ]
    nodes_cmd = run(
        [
            args.kube_cli,
            "get",
            "nodes",
            "-l",
            "node-role.kubernetes.io/master",
            "-o",
            "json",
        ],
        timeout=min(args.timeout_seconds, 120),
    )
    node_items = []
    if nodes_cmd.returncode == 0:
        try:
            node_items = (json.loads(nodes_cmd.stdout or "{}").get("items") or [])
        except Exception:
            node_items = []
    if not node_items:
        fallback_cmd = run(
            [
                args.kube_cli,
                "get",
                "nodes",
                "-l",
                "node-role.kubernetes.io/control-plane",
                "-o",
                "json",
            ],
            timeout=min(args.timeout_seconds, 120),
        )
        if fallback_cmd.returncode == 0:
            try:
                node_items = (json.loads(fallback_cmd.stdout or "{}").get("items") or [])
            except Exception:
                node_items = []

    node_names = sorted(
        {
            str(((item.get("metadata") or {}).get("name") or "")).strip()
            for item in node_items
            if str(((item.get("metadata") or {}).get("name") or "")).strip()
        }
    )
    results = [collect_node_files(args.kube_cli, node, search_paths, args.timeout_seconds) for node in node_names]
    nodes_with_pairs = sum(1 for item in results if item.get("matching_pairs"))
    summary = {
        "present": bool(results),
        "node_count": len(results),
        "nodes_with_any_artifacts": sum(
            1 for item in results if item.get("snapshot_files") or item.get("static_kuberesource_files")
        ),
        "nodes_with_matching_pairs": nodes_with_pairs,
        "search_paths": search_paths,
        "newest_matching_pair_age_hours": newest_pair_age_hours(results),
        "healthy": bool(results) and nodes_with_pairs > 0,
    }
    findings = []
    if not results:
        findings.append(
            {
                "issue": "control-plane-node-inventory-missing",
                "detail": "no control plane nodes were resolved for control-plane backup artifact collection",
            }
        )
    elif nodes_with_pairs == 0:
        findings.append(
            {
                "issue": "control-plane-backup-artifacts-not-found",
                "detail": "no matching snapshot_*.db and static_kuberesources_* backup artifact pair was found on collected control plane nodes",
            }
        )
    payload = {"summary": summary, "nodes": results, "findings": findings}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
