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
    url = f"https://{route_host}/api/v1/query"
    body = urllib.parse.urlencode({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
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

    non_empty_queries = [item for item in queries if str(item.get("query") or "").strip()]

    if non_empty_queries:
        try:
            probe = query_via_route(route_host, bearer_token, str(non_empty_queries[0].get("query") or ""), timeout_seconds)
            route_working = True
            transport = "route"
            results[str(non_empty_queries[0].get("name") or "probe")] = probe
        except Exception as exc:
            route_error = str(exc)

        if not route_working:
            try:
                probe = query_via_proxy(str(non_empty_queries[0].get("query") or ""), timeout_seconds)
                proxy_working = True
                transport = "oc-proxy"
                results[str(non_empty_queries[0].get("name") or "probe")] = probe
            except Exception as exc:
                proxy_error = str(exc)

    for item in queries:
        name = str(item.get("name") or "").strip()
        query = str(item.get("query") or "").strip()
        if not name:
            continue
        if not query:
            results[name] = []
            continue
        if name in results:
            continue
        try:
            if transport == "route":
                results[name] = query_via_route(route_host, bearer_token, query, timeout_seconds) or []
            elif transport == "oc-proxy":
                results[name] = query_via_proxy(query, timeout_seconds) or []
            else:
                results[name] = []
        except Exception:
            results[name] = []

    print(json.dumps({
        "prom_available": transport in {"route", "oc-proxy"},
        "transport": transport,
        "route_working": route_working,
        "proxy_working": proxy_working,
        "route_error": route_error,
        "proxy_error": proxy_error,
        "results": results,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
