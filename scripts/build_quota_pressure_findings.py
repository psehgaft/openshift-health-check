#!/usr/bin/env python3
import json
import sys


def parse_qty(val):
    if val is None:
        return None
    s = str(val)
    units = {
        "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
        "Pi": 1024**5, "Ei": 1024**6, "K": 1000, "M": 1000**2,
        "G": 1000**3, "T": 1000**4, "P": 1000**5, "E": 1000**6,
    }
    if s.endswith("m"):
        try:
            return float(s[:-1]) / 1000.0
        except Exception:
            return None
    for suf, mult in units.items():
        if s.endswith(suf):
            try:
                return float(s[:-len(suf)]) * mult
            except Exception:
                return None
    try:
        return float(s)
    except Exception:
        return None


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        quotas = json.load(handle)

    findings = []
    interesting = {
        "pods", "persistentvolumeclaims", "requests.cpu", "requests.memory",
        "limits.cpu", "limits.memory", "requests.storage"
    }
    for quota in quotas:
        ns = quota.get("metadata", {}).get("namespace", "")
        qn = quota.get("metadata", {}).get("name", "")
        hard = (quota.get("status", {}) or {}).get("hard", {}) or {}
        used = (quota.get("status", {}) or {}).get("used", {}) or {}
        for key, hard_val in hard.items():
            if key not in interesting:
                continue
            used_val = used.get(key)
            h = parse_qty(hard_val)
            u = parse_qty(used_val)
            if h and h > 0 and u is not None:
                pct = round((u / h) * 100, 1)
                if pct >= 80:
                    findings.append({
                        "namespace": ns,
                        "quota": qn,
                        "resource": key,
                        "used": str(used_val),
                        "hard": str(hard_val),
                        "pct": pct,
                    })
    findings.sort(key=lambda x: (-x["pct"], x["namespace"], x["resource"]))
    print(json.dumps(findings[:50]))


if __name__ == "__main__":
    main()
