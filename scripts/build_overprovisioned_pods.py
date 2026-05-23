#!/usr/bin/env python3
import json
import re
import sys

from workload_noise_filters import is_operator_managed_object


def parse_cpu(value):
    if not value:
        return 0.0
    s = str(value)
    if s.endswith("m"):
        return float(s[:-1])
    try:
        return float(s) * 1000.0
    except Exception:
        return 0.0


def parse_mem(value):
    if not value:
        return 0.0
    s = str(value)
    table = {
        "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
        "Pi": 1024**5, "Ei": 1024**6, "K": 1000, "M": 1000**2,
        "G": 1000**3, "T": 1000**4, "P": 1000**5, "E": 1000**6,
    }
    for suf, mult in table.items():
        if s.endswith(suf):
            try:
                return float(s[:-len(suf)]) * mult
            except Exception:
                return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if data.get("cpu_usage_status") != "observed" or data.get("memory_usage_status") != "observed":
        print("[]")
        return

    cpu_usage = {}
    for item in data["cpu_usage"]:
        key = f'{item.get("metric", {}).get("namespace","")}/{item.get("metric", {}).get("pod","")}'
        try:
            cpu_usage[key] = float(item["value"][1]) * 1000.0
        except Exception:
            cpu_usage[key] = 0.0

    mem_usage = {}
    for item in data["memory_usage"]:
        key = f'{item.get("metric", {}).get("namespace","")}/{item.get("metric", {}).get("pod","")}'
        try:
            mem_usage[key] = float(item["value"][1])
        except Exception:
            mem_usage[key] = 0.0

    findings = []
    exclude_re = re.compile(data["exclude_regex"])
    operator_managed_namespace_names = data.get("operator_managed_namespace_names") or []
    for pod in data["pods"]:
        ns = pod.get("metadata", {}).get("namespace", "")
        if exclude_re.match(ns):
            continue
        if is_operator_managed_object(pod, operator_managed_namespace_names):
            continue
        if pod.get("status", {}).get("phase") != "Running":
            continue
        key = f'{ns}/{pod.get("metadata", {}).get("name","")}'
        containers = pod.get("spec", {}).get("containers", []) or []
        cpu_req = sum(parse_cpu((c.get("resources", {}).get("requests", {}) or {}).get("cpu")) for c in containers)
        mem_req = sum(parse_mem((c.get("resources", {}).get("requests", {}) or {}).get("memory")) for c in containers)
        cpu_use = cpu_usage.get(key, 0.0)
        mem_use = mem_usage.get(key, 0.0)
        cpu_ratio = (cpu_use / cpu_req) if cpu_req > 0 else None
        mem_ratio = (mem_use / mem_req) if mem_req > 0 else None

        reasons = []
        if cpu_req >= 200 and cpu_ratio is not None and cpu_ratio < 0.20:
            reasons.append(("cpu", round(cpu_ratio, 3)))
        if mem_req >= 512 * 1024 * 1024 and mem_ratio is not None and mem_ratio < 0.30:
            reasons.append(("memory", round(mem_ratio, 3)))
        if reasons:
            findings.append({
                "namespace": ns,
                "pod": pod.get("metadata", {}).get("name", ""),
                "cpu_request_millicores": round(cpu_req, 1),
                "cpu_usage_millicores": round(cpu_use, 1),
                "memory_request_mib": round(mem_req / 1048576, 1),
                "memory_usage_mib": round(mem_use / 1048576, 1),
                "reasons": reasons,
                "reason_names": [reason[0] for reason in reasons],
            })

    findings.sort(key=lambda x: (
        min([r[1] for r in x["reasons"]]) if x["reasons"] else 1.0,
        -(x["cpu_request_millicores"] + x["memory_request_mib"])
    ))
    print(json.dumps(findings[:50]))


if __name__ == "__main__":
    main()
