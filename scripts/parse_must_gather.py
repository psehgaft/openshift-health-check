#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def relpaths(paths, base):
    return [str(path.relative_to(base)) for path in sorted(paths)[:25]]


def main() -> int:
    if len(sys.argv) != 2:
      print(json.dumps({"error": "usage: parse_must_gather.py <must-gather-path>"}))
      return 1

    root = Path(sys.argv[1]).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": "must-gather path not found", "path": str(root)}))
        return 2

    cluster_resource_dirs = list(root.glob("**/cluster-scoped-resources"))
    namespace_dirs = list(root.glob("**/namespaces"))
    resource_files = [path for path in root.glob("**/*.yaml")]
    resource_files.extend(path for path in root.glob("**/*.json"))
    event_files = [path for path in resource_files if "event" in path.name.lower()]
    log_files = [path for path in root.glob("**/*.log")]
    pod_log_dirs = list(root.glob("**/pods"))

    payload = {
        "summary": {
            "parser_version": "1",
            "root": str(root),
            "root_entry_count": len(list(root.iterdir())),
            "has_cluster_scoped_resources": len(cluster_resource_dirs) > 0,
            "has_namespaces_tree": len(namespace_dirs) > 0,
            "cluster_resource_file_count": sum(1 for path in resource_files if "cluster-scoped-resources" in path.parts),
            "namespaced_resource_file_count": sum(1 for path in resource_files if "namespaces" in path.parts),
            "event_file_count": len(event_files),
            "log_file_count": len(log_files),
            "pod_log_dir_count": len(pod_log_dirs),
        },
        "samples": {
            "cluster_resource_dirs": relpaths(cluster_resource_dirs, root),
            "namespace_dirs": relpaths(namespace_dirs, root),
            "event_files": relpaths(event_files, root),
            "log_files": relpaths(log_files, root),
        },
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
