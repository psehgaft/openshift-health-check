#!/usr/bin/env python3
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


PROXY_QUERY_PREFIX = "/api/v1/namespaces/openshift-monitoring/services/https:thanos-querier:9091/proxy/api/v1/query?query="


def query_via_route(route_host, bearer_token, query, timeout_seconds):
    if not route_host or not bearer_token or not query:
        return None
    encoded_query = urllib.parse.urlencode({"query": query})
    url = f"https://{route_host}/api/v1/query?{encoded_query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
        },
        method="GET",
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout_seconds, context=context) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return ((payload.get("data", {}) or {}).get("result", [])) or []


def query_via_proxy(query, timeout_seconds):
    if not query:
        return None
    encoded_query = urllib.parse.quote(query, safe="")
    proc = subprocess.run(
        ["oc", "get", f"--raw={PROXY_QUERY_PREFIX}{encoded_query}"],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"oc get --raw failed with rc={proc.returncode}")
    payload = json.loads(proc.stdout)
    return ((payload.get("data", {}) or {}).get("result", [])) or []


def execute_query(name, query, preferred_transport, route_host, bearer_token, timeout_seconds):
    route_exc = None
    proxy_exc = None

    if preferred_transport == "route":
        try:
            return query_via_route(route_host, bearer_token, query, timeout_seconds) or [], "route", "", ""
        except Exception as exc:
            route_exc = exc
        try:
            return query_via_proxy(query, timeout_seconds) or [], "oc-proxy", str(route_exc or ""), ""
        except Exception as exc:
            proxy_exc = exc
    elif preferred_transport == "oc-proxy":
        try:
            return query_via_proxy(query, timeout_seconds) or [], "oc-proxy", "", ""
        except Exception as exc:
            proxy_exc = exc
        try:
            return query_via_route(route_host, bearer_token, query, timeout_seconds) or [], "route", "", str(proxy_exc or "")
        except Exception as exc:
            route_exc = exc
    else:
        try:
            return query_via_route(route_host, bearer_token, query, timeout_seconds) or [], "route", "", ""
        except Exception as exc:
            route_exc = exc
        try:
            return query_via_proxy(query, timeout_seconds) or [], "oc-proxy", str(route_exc or ""), ""
        except Exception as exc:
            proxy_exc = exc

    route_error = str(route_exc or "")
    proxy_error = str(proxy_exc or "")
    raise RuntimeError(
        f"{name} query failed via route and proxy"
        + (f"; route={route_error}" if route_error else "")
        + (f"; proxy={proxy_error}" if proxy_error else "")
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: query_prometheus_signals.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    route_host = str(data.get("route_host") or "").strip()
    bearer_token = str(data.get("bearer_token") or "").strip()
    timeout_seconds = int(data.get("timeout_seconds") or 30)
    queries = data.get("queries", []) or []

    results = {}
    transport = "unavailable"
    route_error = ""
    proxy_error = ""

    route_working = False
    proxy_working = False
    query_errors = {}
    query_statuses = {}

    non_empty_queries = [item for item in queries if str(item.get("query") or "").strip()]

    if non_empty_queries:
        try:
            probe, used_transport, _, _ = execute_query(
                str(non_empty_queries[0].get("name") or "probe"),
                str(non_empty_queries[0].get("query") or ""),
                "route",
                route_host,
                bearer_token,
                timeout_seconds,
            )
            route_working = used_transport == "route"
            proxy_working = used_transport == "oc-proxy"
            transport = used_transport
            results[str(non_empty_queries[0].get("name") or "probe")] = probe
            query_statuses[str(non_empty_queries[0].get("name") or "probe")] = "collected" if probe else "no-data"
        except Exception as exc:
            route_error = str(exc)
            proxy_error = str(exc)

    for item in queries:
        name = str(item.get("name") or "").strip()
        query = str(item.get("query") or "").strip()
        if not name:
            continue
        if not query:
            results[name] = []
            query_statuses[name] = "not-configured"
            continue
        if name in results:
            continue
        try:
            result, used_transport, route_query_error, proxy_query_error = execute_query(
                name,
                query,
                transport,
                route_host,
                bearer_token,
                timeout_seconds,
            )
            results[name] = result
            query_statuses[name] = "collected" if result else "no-data"
            if used_transport == "route":
                route_working = True
            elif used_transport == "oc-proxy":
                proxy_working = True
            if route_query_error:
                route_error = route_query_error
            if proxy_query_error:
                proxy_error = proxy_query_error
        except Exception as exc:
            results[name] = []
            query_errors[name] = str(exc)
            query_statuses[name] = "query-failed"

    print(json.dumps({
        "prom_available": transport in {"route", "oc-proxy"},
        "transport": transport,
        "route_working": route_working,
        "proxy_working": proxy_working,
        "route_error": route_error,
        "proxy_error": proxy_error,
        "results": results,
        "query_errors": query_errors,
        "query_statuses": query_statuses,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
