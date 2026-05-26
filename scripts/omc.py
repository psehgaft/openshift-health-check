#!/usr/bin/env python3
"""Report-focused local clone of the OMC must-gather client.

This is not a full reimplementation of github.com/gmeghnag/omc. It preserves the
OMC command shapes the report depends on and reads must-gather content directly.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None


CONFIG_NAME = ".omc.json"
RESOURCE_ALIASES = {
    "co": "clusteroperators",
    "clusteroperator": "clusteroperators",
    "clusteroperators": "clusteroperators",
    "node": "nodes",
    "nodes": "nodes",
    "no": "nodes",
    "pod": "pods",
    "pods": "pods",
    "po": "pods",
    "service": "services",
    "services": "services",
    "svc": "services",
    "namespace": "namespaces",
    "namespaces": "namespaces",
    "ns": "namespaces",
    "prometheusrule": "prometheusrules",
    "prometheusrules": "prometheusrules",
    "endpoint": "endpoints",
    "endpoints": "endpoints",
    "ep": "endpoints",
}
RESOURCE_KIND_BY_NAME = {
    "clusteroperators": "ClusterOperator",
    "nodes": "Node",
    "pods": "Pod",
    "services": "Service",
    "namespaces": "Namespace",
    "prometheusrules": "PrometheusRule",
    "endpoints": "Endpoints",
}


def config_path() -> Path:
    return Path(os.environ.get("HOME") or ".") / CONFIG_NAME


def load_context() -> Optional[Path]:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    root = data.get("must_gather_path")
    return Path(root) if root else None


def save_context(path: Path) -> int:
    if not path.exists():
        print(f"must-gather path not found: {path}", file=sys.stderr)
        return 1
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps({"must_gather_path": str(path.resolve())}), encoding="utf-8")
    return 0


def load_documents(path: Path) -> Iterable[Dict[str, Any]]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in normalize_documents(data):
                yield item
        elif suffix in {".yaml", ".yml"} and yaml is not None:
            with path.open("r", encoding="utf-8") as handle:
                for data in yaml.safe_load_all(handle):
                    for item in normalize_documents(data):
                        yield item
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    except Exception as exc:
        if yaml is not None and exc.__class__.__module__.startswith("yaml"):
            return
        raise


def normalize_documents(data: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            for item in data.get("items") or []:
                if isinstance(item, dict):
                    yield item
        if data.get("kind"):
            yield data
        if isinstance(data.get("data"), dict):
            yield data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield from normalize_documents(item)


def iter_documents(root: Path) -> Iterable[Dict[str, Any]]:
    for path in sorted(root.glob("**/*")):
        if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml"}:
            yield from load_documents(path)


def meta(obj: Dict[str, Any]) -> Dict[str, Any]:
    return obj.get("metadata") or {}


def canonical_resource(value: str) -> str:
    return RESOURCE_ALIASES.get(value.lower(), value.lower())


def resource_matches(obj: Dict[str, Any], resource: str) -> bool:
    kind = str(obj.get("kind") or "").lower()
    wanted_kind = RESOURCE_KIND_BY_NAME.get(resource, resource).lower()
    return kind == wanted_kind or kind + "s" == resource


def parse_selector(selector: str) -> List[Tuple[str, Optional[str]]]:
    items = []
    for part in selector.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            items.append((key.strip(), value.strip()))
        else:
            items.append((part, None))
    return items


def labels_match(obj: Dict[str, Any], selector: str) -> bool:
    if not selector:
        return True
    labels = meta(obj).get("labels") or {}
    for key, value in parse_selector(selector):
        if key not in labels:
            return False
        if value is not None and str(labels.get(key)) != value:
            return False
    return True


def select_resources(root: Path, resource: str, namespace: str = "", selector: str = "", name: str = "") -> List[Dict[str, Any]]:
    selected = []
    for obj in iter_documents(root):
        if not resource_matches(obj, resource):
            continue
        obj_meta = meta(obj)
        if namespace and obj_meta.get("namespace") != namespace:
            continue
        if name and obj_meta.get("name") != name:
            continue
        if not labels_match(obj, selector):
            continue
        selected.append(obj)
    return selected


def get_field(data: Any, path: str) -> Any:
    current = data
    for part in [item for item in path.strip(".").split(".") if item]:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current


def render_jsonpath(data: Any, template: str) -> str:
    expr = template.strip()
    if expr.startswith("{") and expr.endswith("}"):
        expr = expr[1:-1].strip()
    # Minimal support for the OMC documented etcd-pod lookup.
    match = re.fullmatch(r"\.items\[\?\(@\.spec\.nodeName==['\"]([^'\"]+)['\"]\)\]\.metadata\.name", expr)
    if match and isinstance(data, dict):
        node_name = match.group(1)
        names = [
            str(get_field(item, ".metadata.name"))
            for item in data.get("items", [])
            if get_field(item, ".spec.nodeName") == node_name and get_field(item, ".metadata.name")
        ]
        return " ".join(names)
    value = get_field(data, expr)
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def print_yaml(data: Any) -> None:
    if yaml is None:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(yaml.safe_dump(data, sort_keys=False).rstrip())


def output_get(resources: List[Dict[str, Any]], resource: str, output: str, name: str) -> int:
    if output == "name":
        for item in resources:
            kind = str(item.get("kind") or resource.rstrip("s")).lower()
            print(f"{kind}/{meta(item).get('name', '')}")
        return 0
    payload = resources[0] if name and len(resources) == 1 else {
        "apiVersion": "v1",
        "kind": "List",
        "items": resources,
    }
    if output.startswith("jsonpath="):
        print(render_jsonpath(payload, output.split("=", 1)[1]), end="")
    elif output == "json":
        print(json.dumps(payload, sort_keys=True))
    elif output == "yaml":
        print_yaml(payload)
    else:
        print_get_table(resources, output == "wide")
    return 0


def print_get_table(resources: List[Dict[str, Any]], wide: bool) -> None:
    if not resources:
        return
    kind = resources[0].get("kind")
    if kind == "Pod":
        headers = ["NAME", "READY", "STATUS", "RESTARTS"]
        if wide:
            headers.extend(["NODE", "IP"])
        rows = []
        for pod in resources:
            statuses = (pod.get("status") or {}).get("containerStatuses") or []
            ready = sum(1 for item in statuses if item.get("ready"))
            restarts = sum(int(item.get("restartCount") or 0) for item in statuses)
            row = [
                meta(pod).get("name", ""),
                f"{ready}/{len(statuses)}" if statuses else "0/0",
                (pod.get("status") or {}).get("phase", ""),
                str(restarts),
            ]
            if wide:
                row.extend([get_field(pod, ".spec.nodeName") or "", get_field(pod, ".status.podIP") or ""])
            rows.append(row)
        print_aligned(headers, rows)
        return
    headers = ["NAME"]
    rows = [[meta(item).get("name", "")] for item in resources]
    print_aligned(headers, rows)


def print_aligned(headers: List[str], rows: List[List[str]]) -> None:
    widths = [len(item) for item in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))
    print("  ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    for row in rows:
        print("  ".join(str(row[index]).ljust(widths[index]) for index in range(len(headers))))


def cmd_get(root: Path, args: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="omc get", add_help=False)
    parser.add_argument("resource")
    parser.add_argument("name", nargs="?")
    parser.add_argument("-n", "--namespace", default="")
    parser.add_argument("-A", "--all-namespaces", action="store_true")
    parser.add_argument("-l", "--selector", default="")
    parser.add_argument("-o", "--output", default="")
    parsed, _ = parser.parse_known_args(args)
    namespace = "" if parsed.all_namespaces else parsed.namespace
    resource = canonical_resource(parsed.resource)
    resources = select_resources(root, resource, namespace, parsed.selector, parsed.name or "")
    return output_get(resources, resource, parsed.output, parsed.name or "")


def endpoint_addresses(endpoint: Dict[str, Any], ready: bool) -> List[str]:
    key = "addresses" if ready else "notReadyAddresses"
    values = []
    for subset in endpoint.get("subsets") or []:
        for address in subset.get(key) or []:
            ip = address.get("ip") or address.get("hostname") or address.get("targetRef", {}).get("name")
            if ip:
                values.append(str(ip))
    return values


def find_etcd_pod_names(root: Path) -> List[str]:
    names = []
    for path in sorted(root.glob("**/namespaces/openshift-etcd/pods/etcd-*")):
        if path.is_dir():
            names.append(path.name)
    if names:
        return names
    pods = select_resources(root, "pods", "openshift-etcd", "app=etcd")
    return [str(meta(pod).get("name")) for pod in pods if meta(pod).get("name")]


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    amount = float(value)
    for unit in units:
        if abs(amount) < 1000 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} B"
            return f"{amount:.1f} {unit}"
        amount /= 1000
    return f"{value} B"


def normalize_endpoint_key(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^[a-z]+://", "", text, flags=re.IGNORECASE)
    text = text.split("/", 1)[0]
    text = text.rsplit(":", 1)[0] if ":" in text and text.count(":") == 1 else text
    if text.startswith("etcd-ip-"):
        text = text.removeprefix("etcd-ip-").replace("-", ".")
    elif text.startswith("etcd-"):
        text = text.removeprefix("etcd-")
    return text.lower()


def endpoint_keys(value: str) -> List[str]:
    key = normalize_endpoint_key(value)
    values = [key]
    if key and re.fullmatch(r"\d+(?:\.\d+){3}", key):
        values.extend([f"https://{key}:2379", f"etcd-{key}", f"etcd-ip-{key.replace('.', '-')}"])
    return values


def parse_size_value(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?i?b|bytes?)?", text, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    multipliers = {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1000,
        "mb": 1000 ** 2,
        "gb": 1000 ** 3,
        "tb": 1000 ** 4,
        "pb": 1000 ** 5,
        "kib": 1024,
        "mib": 1024 ** 2,
        "gib": 1024 ** 3,
        "tib": 1024 ** 4,
        "pib": 1024 ** 5,
    }
    return int(number * multipliers.get(unit, 1))


def parse_bool_value(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0"}:
        return False
    return None


def format_not_used_pct(db_size: Optional[int], db_in_use: Optional[int]) -> str:
    if not isinstance(db_size, int) or not isinstance(db_in_use, int) or db_size <= 0:
        return ""
    unused = max(db_size - db_in_use, 0)
    return f"{round((unused / db_size) * 100.0, 1)}%"


def first_present(data: Dict[str, Any], keys: Iterable[str]) -> Any:
    lowered = {str(key).lower().replace(" ", "_").replace("/", "_"): value for key, value in data.items()}
    for key in keys:
        normalized = key.lower().replace(" ", "_").replace("/", "_")
        if normalized in lowered and lowered[normalized] not in (None, ""):
            return lowered[normalized]
    return None


def endpoint_status_from_dict(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    endpoint = first_present(data, ["endpoint", "ENDPOINT", "name"])
    status = data.get("Status") or data.get("status") or data
    if not isinstance(status, dict):
        status = data
    if not endpoint:
        endpoint = first_present(status, ["endpoint", "ENDPOINT", "name"])
    if not endpoint:
        return None

    header = status.get("header") if isinstance(status.get("header"), dict) else {}
    member_id = first_present(status, ["id", "ID", "member_id", "memberId"]) or first_present(header, ["member_id", "memberId"])
    leader_id = first_present(status, ["leader", "leader_id", "leaderId"])
    is_leader = parse_bool_value(first_present(status, ["is_leader", "isLeader", "IS LEADER"]))
    if is_leader is None and member_id not in (None, "") and leader_id not in (None, ""):
        is_leader = str(member_id) == str(leader_id)

    db_size = parse_size_value(first_present(status, ["db_size", "dbSize", "DB SIZE"]))
    db_in_use = parse_size_value(first_present(status, ["db_in_use", "dbSizeInUse", "db_size_in_use", "DB IN USE"]))
    not_used = first_present(status, ["not_used", "notUsed", "NOT USED"])
    errors = first_present(status, ["errors", "error", "ERRORS"]) or ""
    if is_leader is None and db_size is None and db_in_use is None and not str(errors).strip():
        return None
    return {
        "endpoint": str(endpoint),
        "db_size": db_size,
        "db_in_use": db_in_use,
        "not_used": str(not_used or format_not_used_pct(db_size, db_in_use)),
        "is_leader": is_leader,
        "errors": str(errors),
    }


def iter_nested_dicts(data: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from iter_nested_dicts(value)
    elif isinstance(data, list):
        for value in data:
            yield from iter_nested_dicts(value)


def parse_pipe_status_table(text: str) -> List[Dict[str, Any]]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    table_lines = [line for line in lines if line.lstrip().startswith("|") and line.rstrip().endswith("|")]
    if len(table_lines) < 2:
        return []
    headers = [cell.strip().lower().replace(" ", "_").replace("/", "_") for cell in table_lines[0].strip("|").split("|")]
    rows = []
    for line in table_lines[1:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        if all(cell and set(cell) <= {"-"} for cell in cells):
            continue
        item = dict(zip(headers, cells))
        endpoint = item.get("endpoint")
        if not endpoint:
            continue
        combined = item.get("db_size_in_use", "")
        db_size = item.get("db_size", "")
        db_in_use = item.get("db_in_use", "")
        if combined and "/" in combined:
            db_size, db_in_use = [part.strip() for part in combined.split("/", 1)]
        elif combined:
            db_size = combined
        rows.append({
            "endpoint": endpoint,
            "db_size": parse_size_value(db_size),
            "db_in_use": parse_size_value(db_in_use),
            "not_used": item.get("not_used") or format_not_used_pct(parse_size_value(db_size), parse_size_value(db_in_use)),
            "is_leader": parse_bool_value(item.get("is_leader")),
            "errors": item.get("errors", ""),
        })
    return rows


def collect_etcd_status_facts(root: Path) -> Dict[str, Dict[str, Any]]:
    facts = {}  # type: Dict[str, Dict[str, Any]]
    for path in sorted(root.glob("**/*")):
        if not path.is_file():
            continue
        path_key = str(path).lower()
        if "etcd" not in path_key or not any(token in path_key for token in ("status", "endpoint")):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        discovered = []
        parsed = None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            if yaml is not None and path.suffix.lower() in {".yaml", ".yml"}:
                try:
                    parsed = yaml.safe_load(text)
                except Exception as exc:
                    if yaml is not None and exc.__class__.__module__.startswith("yaml"):
                        parsed = None
                    else:
                        raise
        if parsed is not None:
            for item in iter_nested_dicts(parsed):
                fact = endpoint_status_from_dict(item)
                if fact:
                    discovered.append(fact)
        else:
            discovered.extend(parse_pipe_status_table(text))

        for fact in discovered:
            key = normalize_endpoint_key(str(fact.get("endpoint", "")))
            if not key:
                continue
            current = facts.setdefault(key, {})
            for field in ("db_size", "db_in_use", "not_used", "is_leader", "errors"):
                if current.get(field) in (None, "") and fact.get(field) not in (None, ""):
                    current[field] = fact.get(field)
    return facts


def etcd_db_size(root: Path, endpoint_name: str) -> str:
    endpoint_names = {endpoint_name}
    if endpoint_name.startswith("etcd-"):
        suffix = endpoint_name.removeprefix("etcd-")
        endpoint_names.add(f"etcd-ip-{suffix.replace('.', '-')}")
        endpoint_names.add(f"etcd-ip-{suffix.replace('.', '-')}.ec2.internal")
    candidates = []
    for name in endpoint_names:
        for path in root.glob(f"**/namespaces/openshift-etcd/pods/{name}/**/member/snap/db"):
            if path.is_file():
                candidates.append(path)
        for path in root.glob(f"**/namespaces/openshift-etcd/pods/{name}/**/*.db"):
            if path.is_file():
                candidates.append(path)
    if not candidates:
        wanted_keys = {normalize_endpoint_key(name) for name in endpoint_names}
        for pod_dir in root.glob("**/namespaces/openshift-etcd/pods/*"):
            if not pod_dir.is_dir():
                continue
            pod_keys = {normalize_endpoint_key(pod_dir.name), normalize_endpoint_key(pod_dir.name.split(".", 1)[0])}
            if not (wanted_keys & pod_keys):
                continue
            for path in pod_dir.glob("**/member/snap/db"):
                if path.is_file():
                    candidates.append(path)
            for path in pod_dir.glob("**/*.db"):
                if path.is_file():
                    candidates.append(path)
    try:
        return format_bytes(max(path.stat().st_size for path in candidates)) if candidates else ""
    except OSError:
        return ""


def print_pipe_table(headers: List[str], rows: List[List[str]]) -> None:
    print("| " + " | ".join(headers) + " |")
    for row in rows:
        print("| " + " | ".join(row) + " |")


def cmd_etcd_status(root: Path) -> int:
    rows = []
    status_facts = collect_etcd_status_facts(root)
    endpoints = select_resources(root, "endpoints", "openshift-etcd", "", "etcd")
    if not endpoints:
        endpoints = [obj for obj in iter_documents(root) if obj.get("kind") == "Endpoints" and meta(obj).get("namespace") == "openshift-etcd"]
    for endpoint in endpoints:
        ready_addresses = endpoint_addresses(endpoint, ready=True)
        not_ready_addresses = endpoint_addresses(endpoint, ready=False)
        all_addresses = ready_addresses + not_ready_addresses
        for index, address in enumerate(all_addresses):
            endpoint_name = f"etcd-{address}"
            fact = status_facts.get(normalize_endpoint_key(address), {})
            db_size_value = fact.get("db_size")
            db_in_use_value = fact.get("db_in_use")
            db_size = format_bytes(db_size_value) if isinstance(db_size_value, int) else etcd_db_size(root, endpoint_name)
            db_in_use = format_bytes(db_in_use_value) if isinstance(db_in_use_value, int) else ""
            db_combined = f"{db_size} / {db_in_use}" if db_size and db_in_use else db_size
            not_used = str(fact.get("not_used") or format_not_used_pct(db_size_value, db_in_use_value))
            is_leader = fact.get("is_leader")
            rows.append([
                f"https://{address}:2379",
                "",
                "",
                db_combined,
                not_used,
                str(is_leader).lower() if isinstance(is_leader, bool) else ("true" if len(all_addresses) == 1 and index == 0 else ""),
                "",
                "",
                "",
                "",
                str(fact.get("errors") or ("not-ready" if address in not_ready_addresses else "")),
            ])
    if not rows:
        pods = find_etcd_pod_names(root)
        for index, pod in enumerate(pods):
            fact = {}
            for key in endpoint_keys(pod):
                fact = status_facts.get(normalize_endpoint_key(key), {})
                if fact:
                    break
            db_size_value = fact.get("db_size")
            db_in_use_value = fact.get("db_in_use")
            db_size = format_bytes(db_size_value) if isinstance(db_size_value, int) else etcd_db_size(root, pod)
            db_in_use = format_bytes(db_in_use_value) if isinstance(db_in_use_value, int) else ""
            db_combined = f"{db_size} / {db_in_use}" if db_size and db_in_use else db_size
            not_used = str(fact.get("not_used") or format_not_used_pct(db_size_value, db_in_use_value))
            is_leader = fact.get("is_leader")
            rows.append([pod, "", "", db_combined, not_used, str(is_leader).lower() if isinstance(is_leader, bool) else ("true" if len(pods) == 1 and index == 0 else ""), "", "", "", "", str(fact.get("errors") or "")])
    if not rows:
        return 1
    print_pipe_table(
        ["ENDPOINT", "ID", "VERSION", "DB SIZE/IN USE", "NOT USED", "IS LEADER", "IS LEARNER", "RAFT TERM", "RAFT INDEX", "RAFT APPLIED INDEX", "ERRORS"],
        rows,
    )
    return 0


def rule_groups(root: Path) -> List[Dict[str, Any]]:
    groups = []
    for obj in iter_documents(root):
        data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        for group in data.get("groups") or []:
            if isinstance(group, dict):
                groups.append(group)
        spec_groups = get_field(obj, ".spec.groups")
        if isinstance(spec_groups, list):
            for group in spec_groups:
                if isinstance(group, dict):
                    groups.append(group)
    return groups


def alert_state(rule: Dict[str, Any]) -> str:
    state = str(rule.get("state") or "").lower()
    if state:
        return state
    alerts = rule.get("alerts") or []
    states = {str(item.get("state") or "").lower() for item in alerts if isinstance(item, dict)}
    if "firing" in states:
        return "firing"
    if "pending" in states:
        return "pending"
    return "inactive"


def alert_rule_rows(root: Path, states: List[str], group_filter: str = "") -> List[List[str]]:
    wanted = {item.lower() for item in states if item}
    rows = []
    for group in rule_groups(root):
        group_name = str(group.get("name") or "")
        if group_filter and group_filter not in group_name:
            continue
        for rule in group.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            if rule.get("type") not in {None, "alerting"} and not rule.get("alert"):
                continue
            state = alert_state(rule)
            if wanted and state not in wanted:
                continue
            name = str(rule.get("name") or rule.get("alert") or "unknown")
            alerts = rule.get("alerts") if isinstance(rule.get("alerts"), list) else []
            active_since = "----"
            for alert in alerts:
                if isinstance(alert, dict) and alert.get("activeAt"):
                    active_since = str(alert.get("activeAt"))
                    break
            rows.append([group_name, name, state, "", str(len(alerts)), active_since])
    for obj in iter_documents(root):
        if obj.get("kind") not in {"Alert", "AlertmanagerAlert"}:
            continue
        state = str(obj.get("state") or get_field(obj, ".status.state") or get_field(obj, ".status.phase") or "").lower()
        if wanted and state not in wanted:
            continue
        rows.append([meta(obj).get("namespace", "must-gather"), meta(obj).get("name", obj.get("alertname", "unknown")), state or "unknown", "", "1", ""])
    return rows


def parse_state_filter(args: List[str]) -> Tuple[List[str], str]:
    states = []
    group = ""
    for index, arg in enumerate(args):
        if arg in {"-s", "--state", "--states"} and index + 1 < len(args):
            states = [item.strip() for item in args[index + 1].split(",") if item.strip()]
        elif arg.startswith("-s="):
            states = [item.strip() for item in arg.split("=", 1)[1].split(",") if item.strip()]
        elif arg == "--group" and index + 1 < len(args):
            group = args[index + 1]
        elif arg.startswith("--group="):
            group = arg.split("=", 1)[1]
    return states, group


def cmd_alert(root: Path, args: List[str]) -> int:
    if not args:
        print("usage: omc alert groups | omc alert rule [-s states] [-o wide] [--group name]", file=sys.stderr)
        return 1
    if args[0] == "groups":
        print_yaml({"status": "success", "data": {"groups": rule_groups(root)}})
        return 0
    if args[0] in {"rule", "rules"}:
        states, group = parse_state_filter(args[1:])
        rows = alert_rule_rows(root, states, group)
        print("GROUP                        RULE                                 STATE     AGE   ALERTS   ACTIVE SINCE")
        for row in rows:
            print(f"{row[0]:<28} {row[1]:<36} {row[2]:<8} {row[3]:<5} {row[4]:<8} {row[5]}")
        return 0
    return 1


def usage() -> None:
    print("usage: omc use <must-gather-path> | omc get <resource> [name] [-n ns] [-l selector] [-o format] | omc etcd status | omc alert rule [-s states] [-o wide]")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        usage()
        return 0
    if args[0] == "use":
        if len(args) < 2:
            print("usage: omc use <must-gather-path>", file=sys.stderr)
            return 1
        return save_context(Path(args[1]))
    root = load_context()
    if root is None or not root.exists():
        print("no must-gather selected; run `omc use <must-gather-path>` first", file=sys.stderr)
        return 1
    if args[0] == "get":
        return cmd_get(root, args[1:])
    if args[:2] == ["etcd", "status"]:
        return cmd_etcd_status(root)
    if args[0] == "alert":
        return cmd_alert(root, args[1:])
    if args[:2] in (["prom", "rules"], ["prometheus", "rules"]):
        return cmd_alert(root, ["rule"] + args[2:])
    print(f"unsupported local omc invocation: {' '.join(args)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
