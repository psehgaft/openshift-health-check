#!/usr/bin/env python3
import json
import re
import sys
import tarfile
from pathlib import Path


def infer_node_name(path: Path) -> str:
    stem = path.name
    match = re.search(r"sosreport-([A-Za-z0-9._-]+)", stem)
    return match.group(1) if match else "unknown"


def inspect_members(path: Path):
    members = []
    if path.is_dir():
        members = [str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()]
    elif tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as handle:
            members = [member.name for member in handle.getmembers() if member.isfile()]
    return members


def read_small_text(path: Path, relative_paths):
    if path.is_dir():
        for rel in relative_paths:
            candidate = path / rel
            if candidate.is_file():
                try:
                    return candidate.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    return None
            for nested in path.rglob(Path(rel).name):
                try:
                    if nested.is_file() and str(nested).endswith(str(rel)):
                        return nested.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    return None
        return None

    if tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as handle:
            members = {member.name: member for member in handle.getmembers() if member.isfile()}
            for rel in relative_paths:
                for member_name, member in members.items():
                    if member_name.endswith(rel):
                        extracted = handle.extractfile(member)
                        if extracted is None:
                            return None
                        try:
                            return extracted.read().decode("utf-8", errors="ignore")
                        except Exception:
                            return None
        return None

    return None


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: parse_sosreport.py <sosreport-path> [...]"}))
        return 1

    reports = []
    missing = []
    for raw in sys.argv[1:]:
      path = Path(raw).expanduser().resolve()
      if not path.exists():
          missing.append(str(path))
          continue
      members = inspect_members(path)
      member_sample = members[:100]
      fips_enabled_text = read_small_text(path, ["proc/sys/crypto/fips_enabled"])
      crypto_policy_text = read_small_text(path, ["etc/crypto-policies/config"])
      fips_status = (
          "enabled"
          if ((fips_enabled_text or "").strip() == "1")
          else ("disabled" if ((fips_enabled_text or "").strip() == "0") else "unknown")
      )
      crypto_policy = (crypto_policy_text or "").strip() or "unknown"
      reports.append({
          "path": str(path),
          "name": path.name,
          "node_name": infer_node_name(path),
          "kind": "directory" if path.is_dir() else "file",
          "size_bytes": path.stat().st_size,
          "suffixes": list(path.suffixes),
          "member_count": len(members),
          "has_journal": any("journal" in member.lower() for member in member_sample),
          "has_crio_logs": any("crio" in member.lower() for member in member_sample),
          "has_kubelet_logs": any("kubelet" in member.lower() for member in member_sample),
          "has_network_data": any(("ip_addr" in member.lower()) or ("routes" in member.lower()) or ("network" in member.lower()) for member in member_sample),
          "fips_enabled_status": fips_status,
          "crypto_policy": crypto_policy,
      })

    payload = {
        "summary": {
            "count": len(reports),
            "missing_count": len(missing),
            "node_names": sorted({item["node_name"] for item in reports}),
            "reports_with_journal": sum(1 for item in reports if item["has_journal"]),
            "reports_with_crio_logs": sum(1 for item in reports if item["has_crio_logs"]),
            "reports_with_kubelet_logs": sum(1 for item in reports if item["has_kubelet_logs"]),
            "reports_with_network_data": sum(1 for item in reports if item["has_network_data"]),
            "reports_with_fips_enabled": sum(1 for item in reports if item["fips_enabled_status"] == "enabled"),
            "reports_with_fips_disabled": sum(1 for item in reports if item["fips_enabled_status"] == "disabled"),
            "reports_with_crypto_policy_fips": sum(1 for item in reports if "FIPS" in str(item["crypto_policy"]).upper()),
        },
        "reports": reports,
        "missing": missing,
    }
    print(json.dumps(payload))
    return 0 if not missing else 3


if __name__ == "__main__":
    raise SystemExit(main())
