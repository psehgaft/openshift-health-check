#!/usr/bin/env python3
import json
import re
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({
            "error": "usage: build_storage_and_sensitive_findings.py <input-json-path>"
        }))
        return 2

    input_path = sys.argv[1]
    with open(input_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    sensitive_name_re = re.compile(
        r"(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|secret[_-]?key|private[_-]?key|client[_-]?secret)",
        re.IGNORECASE,
    )
    sensitive_inline_re = re.compile(
        r"(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|secret[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]\s*[^\s,;]{4,}",
        re.IGNORECASE,
    )

    extra_security = []
    extra_practices = []

    for pod in data.get("pods", []):
        meta = pod.get("metadata", {}) or {}
        spec = pod.get("spec", {}) or {}
        namespace = meta.get("namespace", "")
        name = meta.get("name", "")
        if exclude_re.search(namespace or ""):
            continue

        volumes = spec.get("volumes", []) or []
        empty_dir_names = [
            v.get("name", "unknown")
            for v in volumes
            if isinstance(v, dict) and v.get("emptyDir") is not None
        ]
        generic_ephemeral_names = [
            v.get("name", "unknown")
            for v in volumes
            if isinstance(v, dict) and v.get("ephemeral") is not None
        ]

        ephemeral_detail_parts = []
        if empty_dir_names:
            ephemeral_detail_parts.append("emptyDir=" + ", ".join(empty_dir_names))
        if generic_ephemeral_names:
            ephemeral_detail_parts.append("ephemeral=" + ", ".join(generic_ephemeral_names))
        if ephemeral_detail_parts:
            extra_practices.append({
                "namespace": namespace,
                "pod": name,
                "issue": "ephemeral-storage-volume",
                "detail": "; ".join(ephemeral_detail_parts),
            })

        containers = (spec.get("containers", []) or []) + (spec.get("initContainers", []) or [])
        literal_env_hits = []
        literal_arg_hits = []
        for container in containers:
            container_name = container.get("name", "unknown")
            for env in container.get("env", []) or []:
                env_name = str(env.get("name", ""))
                env_value = env.get("value")
                if env_value not in (None, "") and sensitive_name_re.search(env_name):
                    literal_env_hits.append(f"{container_name}:{env_name}")
            for field_name in ("command", "args"):
                for item in container.get(field_name, []) or []:
                    text = str(item or "")
                    if sensitive_inline_re.search(text):
                        literal_arg_hits.append(container_name)
                        break

        if literal_env_hits:
            extra_security.append({
                "namespace": namespace,
                "pod": name,
                "issue": "literal-sensitive-env",
                "detail": ", ".join(sorted(set(literal_env_hits))),
            })
        if literal_arg_hits:
            extra_security.append({
                "namespace": namespace,
                "pod": name,
                "issue": "literal-sensitive-arg",
                "detail": ", ".join(sorted(set(literal_arg_hits))),
            })

    print(json.dumps({
        "security_findings": extra_security,
        "workload_practice_findings": extra_practices,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
