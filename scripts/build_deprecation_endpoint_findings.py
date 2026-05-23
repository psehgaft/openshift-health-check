#!/usr/bin/env python3
import json
import re
import sys


def parse_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def metadata_of(obj: dict) -> dict:
    return (obj or {}).get("metadata") or {}


def spec_of(obj: dict) -> dict:
    return (obj or {}).get("spec") or {}


def namespace_of(obj: dict) -> str:
    return str(metadata_of(obj).get("namespace") or "")


def name_of(obj: dict) -> str:
    return str(metadata_of(obj).get("name") or "")


def build_deprecated_crd_findings(crds: list[dict]) -> list[dict]:
    findings = []
    for crd in crds or []:
        spec = spec_of(crd)
        deprecated_versions = [
            str(version.get("name") or "")
            for version in spec.get("versions") or []
            if version.get("deprecated") is True
        ]
        deprecated_versions = [version for version in deprecated_versions if version]
        if deprecated_versions:
            findings.append(
                {
                    "name": name_of(crd),
                    "group": str(spec.get("group") or ""),
                    "versions": ", ".join(deprecated_versions),
                }
            )
    return findings


def endpoint_address_count(endpoint: dict) -> int:
    total = 0
    for subset in (endpoint or {}).get("subsets") or []:
        total += len((subset or {}).get("addresses") or [])
    return total


def build_service_endpoint_address_counts(endpoints: list[dict]) -> dict[str, int]:
    counts = {}
    for endpoint in endpoints or []:
        key = f"{namespace_of(endpoint)}/{name_of(endpoint)}"
        counts[key] = endpoint_address_count(endpoint)
    return counts


def build_services_without_endpoints(
    services: list[dict],
    endpoint_counts: dict[str, int],
    user_namespaces_exclude_regex: str,
) -> list[dict]:
    exclude_match = re.compile(user_namespaces_exclude_regex or r"^$").match
    findings = []
    for service in services or []:
        spec = spec_of(service)
        service_ns = namespace_of(service)
        service_name = name_of(service)
        service_type = str(spec.get("type") or "ClusterIP")
        endpoint_count = int(endpoint_counts.get(f"{service_ns}/{service_name}", 0) or 0)

        if (
            not exclude_match(service_ns)
            and service_name != "kubernetes"
            and service_type != "ExternalName"
            and len(spec.get("selector") or {}) > 0
            and endpoint_count == 0
        ):
            findings.append(
                {
                    "namespace": service_ns,
                    "name": service_name,
                    "type": service_type,
                    "endpoint_count": endpoint_count,
                }
            )
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_deprecation_endpoint_findings.py <input-json-path>"}))
        return 2

    data = parse_json(sys.argv[1])
    endpoint_counts = build_service_endpoint_address_counts(data.get("endpoints") or [])
    print(
        json.dumps(
            {
                "deprecated_crd_findings": build_deprecated_crd_findings(data.get("crds") or []),
                "service_endpoint_address_counts": endpoint_counts,
                "services_without_endpoints": build_services_without_endpoints(
                    data.get("services") or [],
                    endpoint_counts,
                    str(data.get("user_namespaces_exclude_regex") or r"^$"),
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
