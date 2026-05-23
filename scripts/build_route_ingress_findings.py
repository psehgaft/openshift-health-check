#!/usr/bin/env python3
import json
import sys
from collections import defaultdict


def parse_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def metadata_of(obj: dict) -> dict:
    return (obj or {}).get("metadata") or {}


def namespace_of(obj: dict) -> str:
    return str(metadata_of(obj).get("namespace") or "")


def name_of(obj: dict) -> str:
    return str(metadata_of(obj).get("name") or "")


def unique_append(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def service_names_by_namespace(services: list[dict]) -> dict[str, list[str]]:
    names = defaultdict(list)
    for service in services or []:
        ns_name = namespace_of(service)
        svc_name = name_of(service)
        if ns_name and svc_name:
            unique_append(names[ns_name], svc_name)
    return dict(names)


def route_admitted_status(route: dict) -> str:
    for ingress in ((route.get("status") or {}).get("ingress") or []):
        for condition in (ingress or {}).get("conditions") or []:
            if condition.get("type") == "Admitted":
                return str(condition.get("status") or "Unknown")
    return "Unknown"


def build_route_issues(routes: list[dict], service_names: dict[str, list[str]]) -> list[dict]:
    findings = []
    for route in routes or []:
        metadata = metadata_of(route)
        spec = route.get("spec") or {}
        ns_name = str(metadata.get("namespace") or "")
        route_name = str(metadata.get("name") or "")
        route_host = str(spec.get("host") or "")
        admitted_status = route_admitted_status(route)
        target = spec.get("to") or {}
        target_kind = str(target.get("kind") or "Service")
        target_service_name = str(target.get("name") or "")
        missing_target_service = (
            target_kind == "Service"
            and target_service_name != ""
            and target_service_name not in service_names.get(ns_name, [])
        )

        if admitted_status != "True":
            findings.append(
                {
                    "kind": "Route",
                    "namespace": ns_name,
                    "name": route_name,
                    "host": route_host,
                    "issue": "route-not-admitted",
                    "detail": f"admitted={admitted_status}",
                }
            )
        if missing_target_service:
            findings.append(
                {
                    "kind": "Route",
                    "namespace": ns_name,
                    "name": route_name,
                    "host": route_host,
                    "issue": "route-missing-service",
                    "detail": target_service_name,
                }
            )
    return findings


def ingress_backend_service_names(ingress: dict) -> tuple[list[str], list[str]]:
    spec = ingress.get("spec") or {}
    rule_hosts = []
    backend_services = []

    for rule in spec.get("rules") or []:
        host = str((rule or {}).get("host") or "")
        if host:
            rule_hosts.append(host)
        for path in ((((rule or {}).get("http") or {}).get("paths")) or []):
            service_name = str(((((path or {}).get("backend") or {}).get("service") or {}).get("name")) or "")
            if service_name and service_name not in backend_services:
                backend_services.append(service_name)

    default_backend_service = str(((((spec.get("defaultBackend") or {}).get("service") or {}).get("name")) or ""))
    if default_backend_service and default_backend_service not in backend_services:
        backend_services.append(default_backend_service)

    return rule_hosts, backend_services


def build_ingress_issues(
    ingresses: list[dict],
    service_names: dict[str, list[str]],
    warn_on_ingress_without_class: bool,
) -> list[dict]:
    findings = []
    for ingress in ingresses or []:
        metadata = metadata_of(ingress)
        spec = ingress.get("spec") or {}
        annotations = metadata.get("annotations") or {}
        ns_name = str(metadata.get("namespace") or "")
        ingress_name = str(metadata.get("name") or "")
        ingress_class = str(spec.get("ingressClassName") or annotations.get("kubernetes.io/ingress.class") or "")
        rule_hosts, backend_service_names = ingress_backend_service_names(ingress)
        missing_backend_services = [
            service for service in backend_service_names if service not in service_names.get(ns_name, [])
        ]
        host = ", ".join(rule_hosts)

        if len(rule_hosts) == 0 and len(backend_service_names) == 0:
            findings.append(
                {
                    "kind": "Ingress",
                    "namespace": ns_name,
                    "name": ingress_name,
                    "host": host,
                    "issue": "ingress-no-rules-or-default-backend",
                    "detail": "no rules and no default backend",
                }
            )
        if missing_backend_services:
            findings.append(
                {
                    "kind": "Ingress",
                    "namespace": ns_name,
                    "name": ingress_name,
                    "host": host,
                    "issue": "ingress-missing-service",
                    "detail": ", ".join(missing_backend_services),
                }
            )
        if warn_on_ingress_without_class and (rule_hosts or backend_service_names) and ingress_class == "":
            findings.append(
                {
                    "kind": "Ingress",
                    "namespace": ns_name,
                    "name": ingress_name,
                    "host": host,
                    "issue": "ingress-without-class",
                    "detail": "ingressClassName and ingress.class annotation are unset",
                }
            )
    return findings


def build_route_host_owners(routes: list[dict]) -> dict[str, list[str]]:
    owners = defaultdict(list)
    for route in routes or []:
        host = str(((route.get("spec") or {}).get("host")) or "")
        if not host:
            continue
        owner = f"{namespace_of(route)}/{name_of(route)}"
        unique_append(owners[host], owner)
    return dict(owners)


def build_ingress_host_owners(ingresses: list[dict]) -> dict[str, list[str]]:
    owners = defaultdict(list)
    for ingress in ingresses or []:
        owner = f"{namespace_of(ingress)}/{name_of(ingress)}"
        for rule in ((ingress.get("spec") or {}).get("rules") or []):
            host = str((rule or {}).get("host") or "")
            if host:
                unique_append(owners[host], owner)
    return dict(owners)


def host_conflicts(owners: dict[str, list[str]], issue: str) -> list[dict]:
    return [
        {"host": host, "owners": values, "issue": issue}
        for host, values in owners.items()
        if len(values) > 1
    ]


def route_ingress_conflicts(route_owners: dict[str, list[str]], ingress_owners: dict[str, list[str]]) -> list[dict]:
    findings = []
    seen_hosts = []
    for host in list(route_owners.keys()) + list(ingress_owners.keys()):
        if host in seen_hosts:
            continue
        seen_hosts.append(host)
        route_values = route_owners.get(host, [])
        ingress_values = ingress_owners.get(host, [])
        if route_values and ingress_values:
            findings.append(
                {
                    "host": host,
                    "route_owners": route_values,
                    "ingress_owners": ingress_values,
                    "owners": route_values + ingress_values,
                    "issue": "duplicate-route-ingress-host",
                }
            )
    return findings


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_route_ingress_findings.py <input-json-path>"}))
        return 2

    data = parse_json(sys.argv[1])
    services = data.get("services") or []
    routes = data.get("routes") or []
    ingresses = data.get("ingresses") or []
    warn_on_ingress_without_class = bool(data.get("warn_on_ingress_without_class", False))

    service_names = service_names_by_namespace(services)
    route_owners = build_route_host_owners(routes)
    ingress_owners = build_ingress_host_owners(ingresses)
    print(
        json.dumps(
            {
                "service_names_by_namespace": service_names,
                "route_issues": build_route_issues(routes, service_names),
                "ingress_issues": build_ingress_issues(ingresses, service_names, warn_on_ingress_without_class),
                "route_host_owners": route_owners,
                "ingress_host_owners": ingress_owners,
                "route_host_conflicts": host_conflicts(route_owners, "duplicate-route-host"),
                "ingress_host_conflicts": host_conflicts(ingress_owners, "duplicate-ingress-host"),
                "route_ingress_host_conflicts": route_ingress_conflicts(route_owners, ingress_owners),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
