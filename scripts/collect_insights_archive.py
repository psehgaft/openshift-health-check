#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(argv):
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Insights Operator archive data from a live OpenShift cluster.")
    parser.add_argument("--kube-cli", default="oc")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pod_cmd = [
        args.kube_cli,
        "get",
        "pods",
        "-n",
        "openshift-insights",
        "--field-selector=status.phase=Running",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ]
    pod_res = run(pod_cmd)
    pod_name = (pod_res.stdout or "").strip()
    if pod_res.returncode != 0 or not pod_name:
        print(
            json.dumps(
                {
                    "error": "failed to resolve a running insights operator pod",
                    "pod_lookup": {
                        "rc": pod_res.returncode,
                        "stderr": (pod_res.stderr or "").strip(),
                        "stdout": (pod_res.stdout or "").strip(),
                    },
                }
            )
        )
        return 1

    archive_dir = output_dir / "insights-data"
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    cp_cmd = [
        args.kube_cli,
        "cp",
        f"openshift-insights/{pod_name}:/var/lib/insights-operator",
        str(archive_dir),
    ]
    cp_res = run(cp_cmd)
    payload = {
        "pod_name": pod_name,
        "namespace": "openshift-insights",
        "output_dir": str(output_dir),
        "archive_root": str(archive_dir),
        "cp": {
            "rc": cp_res.returncode,
            "stderr": (cp_res.stderr or "").strip(),
            "stdout": (cp_res.stdout or "").strip(),
        },
    }
    print(json.dumps(payload))
    return cp_res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
