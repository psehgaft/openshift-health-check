#!/usr/bin/env python3
import argparse
import json
import shlex
import subprocess
from pathlib import Path


def run(argv, timeout=None):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def run_bytes(argv, timeout=None):
    return subprocess.run(argv, capture_output=True, text=False, timeout=timeout, check=False)


def safe_name(value):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def get_nodes(kube_cli, selector):
    argv = [
        kube_cli,
        "get",
        "nodes",
        "-o",
        "jsonpath={range .items[*]}{.metadata.name}{'\\n'}{end}",
    ]
    if selector:
        argv[3:3] = ["-l", selector]
    res = run(argv)
    nodes = [line.strip() for line in (res.stdout or "").splitlines() if line.strip()]
    return nodes, res


def build_remote_script(node_name, remote_dir, sos_args):
    quoted_args = " ".join(shlex.quote(arg) for arg in sos_args)
    return f"""
set -eu
mkdir -p {shlex.quote(remote_dir)}
cd {shlex.quote(remote_dir)}
if command -v sos >/dev/null 2>&1; then
  sos report --batch --tmp-dir {shlex.quote(remote_dir)} --name {shlex.quote(node_name)} {quoted_args}
elif command -v sosreport >/dev/null 2>&1; then
  sosreport --batch --tmp-dir {shlex.quote(remote_dir)} --name {shlex.quote(node_name)} {quoted_args}
elif command -v toolbox >/dev/null 2>&1; then
  toolbox -- bash -lc {shlex.quote('sos report --batch --tmp-dir ' + shlex.quote(remote_dir) + ' --name ' + shlex.quote(node_name) + (' ' + quoted_args if quoted_args else ''))}
else
  echo "sos, sosreport, and toolbox were not found on the node" >&2
  exit 127
fi
find {shlex.quote(remote_dir)} -maxdepth 1 -type f \\( -name 'sosreport-*' -o -name '*.tar.xz' -o -name '*.tar.gz' -o -name '*.txz' \\) | sort | tail -1
""".strip()


def collect_node(kube_cli, node, output_dir, remote_dir, sos_args, timeout):
    node_dir = output_dir / safe_name(node)
    node_dir.mkdir(parents=True, exist_ok=True)
    remote_script = build_remote_script(node, remote_dir, sos_args)
    debug_cmd = [
        kube_cli,
        "debug",
        f"node/{node}",
        "--",
        "chroot",
        "/host",
        "bash",
        "-lc",
        remote_script,
    ]
    debug_res = run(debug_cmd, timeout=timeout)
    remote_archive = ""
    if debug_res.returncode == 0:
        for line in reversed((debug_res.stdout or "").splitlines()):
            line = line.strip()
            if line.startswith(remote_dir) and "sosreport" in line:
                remote_archive = line
                break

    local_archive = ""
    copy_res = None
    if remote_archive:
        target = node_dir / Path(remote_archive).name
        copy_cmd = [
            kube_cli,
            "debug",
            f"node/{node}",
            "--",
            "bash",
            "-c",
            f"cat /host/{remote_archive.lstrip('/')}",
        ]
        copy_res = run_bytes(copy_cmd, timeout=timeout)
        if copy_res.returncode == 0 and copy_res.stdout:
            target.write_bytes(copy_res.stdout)
            local_archive = str(target)

    return {
        "node": node,
        "debug": {
            "rc": debug_res.returncode,
            "stdout": (debug_res.stdout or "")[-4000:],
            "stderr": (debug_res.stderr or "")[-4000:],
        },
        "remote_archive": remote_archive,
        "copy": {
            "rc": copy_res.returncode if copy_res else None,
            "stderr": (((copy_res.stderr or b"").decode("utf-8", errors="ignore"))[-4000:] if copy_res else ""),
        },
        "local_archive": local_archive,
        "collected": bool(local_archive),
    }


def main():
    parser = argparse.ArgumentParser(description="Collect node-level sosreports through oc debug node/<node>.")
    parser.add_argument("--kube-cli", default="oc")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--node", action="append", default=[])
    parser.add_argument("--node-selector", default="")
    parser.add_argument("--node-limit", type=int, default=0)
    parser.add_argument(
        "--require-explicit-nodes",
        action="store_true",
        help="Skip cleanly instead of discovering all nodes when no --node or --node-selector is provided.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--remote-dir", default="/var/tmp/openshift-health-check-sos")
    parser.add_argument(
        "--sos-arg",
        action="append",
        default=[],
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.require_explicit_nodes and not args.node and not args.node_selector:
        payload = {
            "output_dir": str(output_dir),
            "node_lookup": {"rc": 0, "stdout": "", "stderr": ""},
            "requested_nodes": [],
            "collected_paths": [],
            "results": [],
            "summary": {
                "requested_node_count": 0,
                "collected_count": 0,
                "failed_count": 0,
                "skipped": True,
                "skip_reason": "no explicit, selector, or derived target nodes were provided",
            },
        }
        print(json.dumps(payload))
        return 0

    if args.node:
        nodes = args.node
        node_lookup = {"rc": 0, "stdout": "\n".join(nodes), "stderr": ""}
    else:
        nodes, lookup_res = get_nodes(args.kube_cli, args.node_selector)
        node_lookup = {
            "rc": lookup_res.returncode,
            "stdout": lookup_res.stdout or "",
            "stderr": lookup_res.stderr or "",
        }
        if lookup_res.returncode != 0:
            print(json.dumps({"error": "failed to list nodes", "node_lookup": node_lookup}))
            return lookup_res.returncode

    if args.node_limit and args.node_limit > 0:
        nodes = nodes[: args.node_limit]

    sos_args = args.sos_arg or [
        "-k",
        "crio.all=on",
        "-k",
        "crio.logs=on",
        "-k",
        "podman.all=on",
        "-k",
        "podman.logs=on",
    ]

    results = [
        collect_node(args.kube_cli, node, output_dir, args.remote_dir, sos_args, args.timeout_seconds)
        for node in nodes
    ]
    payload = {
        "output_dir": str(output_dir),
        "node_lookup": node_lookup,
        "requested_nodes": nodes,
        "collected_paths": [item["local_archive"] for item in results if item["local_archive"]],
        "results": results,
        "summary": {
            "requested_node_count": len(nodes),
            "collected_count": sum(1 for item in results if item["collected"]),
            "failed_count": sum(1 for item in results if not item["collected"]),
        },
    }
    print(json.dumps(payload))
    return 0 if payload["summary"]["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
