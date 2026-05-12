#!/usr/bin/env python3
import re


CIDR_PATTERN = re.compile(r"([0-9a-fA-F:.]+/\d+)")


def dedupe_preserve_order(values):
    seen = set()
    result = []
    for value in values:
        marker = str(value)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def normalize_cidrs(raw):
    cidrs = []
    for item in raw or []:
        if isinstance(item, str):
            value = item
        elif isinstance(item, dict):
            value = item.get("cidr") or item.get("CIDR")
        else:
            value = None
        if value:
            cidrs.append(str(value))
    return cidrs


def _line_indent(line):
    return len(line) - len(line.lstrip(" "))


def _collect_network_strings(raw):
    texts = []
    if isinstance(raw, dict):
        for key, value in raw.items():
            key_text = str(key).lower()
            if isinstance(value, str):
                if key_text in {"install-config", "install-config.yaml", "install_config", "installconfig"}:
                    texts.append(value)
                elif any(marker in value for marker in ("clusterNetwork", "serviceNetwork", "machineNetwork", "machineCIDR")):
                    texts.append(value)
            else:
                texts.extend(_collect_network_strings(value))
    elif isinstance(raw, list):
        for item in raw:
            texts.extend(_collect_network_strings(item))
    return texts


def _extract_block(lines, start_index):
    header_indent = _line_indent(lines[start_index])
    block_lines = []
    index = start_index + 1
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        line_indent = _line_indent(line)
        if stripped and line_indent < header_indent:
            break
        if stripped and line_indent == header_indent and not stripped.startswith("- "):
            break
        block_lines.append(line)
        index += 1
    return block_lines, index


def _parse_cluster_network_block(block_lines):
    entries = []
    current = None
    for line in block_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            cidr_match = re.search(r"cidr:\s*([0-9a-fA-F:.]+/\d+)", stripped)
            if cidr_match:
                current["cidr"] = cidr_match.group(1)
            host_prefix_match = re.search(r"hostPrefix:\s*(\d+)", stripped)
            if host_prefix_match:
                current["hostPrefix"] = int(host_prefix_match.group(1))
            continue
        if current is None:
            continue
        cidr_match = re.search(r"cidr:\s*([0-9a-fA-F:.]+/\d+)", stripped)
        if cidr_match:
            current["cidr"] = cidr_match.group(1)
        host_prefix_match = re.search(r"hostPrefix:\s*(\d+)", stripped)
        if host_prefix_match:
            current["hostPrefix"] = int(host_prefix_match.group(1))
    if current:
        entries.append(current)
    return [item for item in entries if item.get("cidr")]


def _parse_cidr_list_block(block_lines):
    cidrs = []
    for line in block_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cidr_match = CIDR_PATTERN.search(stripped)
        if cidr_match:
            cidrs.append(cidr_match.group(1))
    return cidrs


def extract_install_config_networks(sources):
    cluster_networks = []
    service_networks = []
    machine_networks = []

    for raw in sources:
        for text in _collect_network_strings(raw):
            lines = text.splitlines()
            index = 0
            while index < len(lines):
                stripped = lines[index].strip()
                if stripped.startswith("clusterNetwork:"):
                    block_lines, index = _extract_block(lines, index)
                    cluster_networks.extend(_parse_cluster_network_block(block_lines))
                    continue
                if stripped.startswith("serviceNetwork:"):
                    block_lines, index = _extract_block(lines, index)
                    service_networks.extend(_parse_cidr_list_block(block_lines))
                    continue
                if stripped.startswith("machineNetwork:"):
                    block_lines, index = _extract_block(lines, index)
                    machine_networks.extend(_parse_cidr_list_block(block_lines))
                    continue
                if stripped.startswith("machineCIDR:"):
                    cidr_match = CIDR_PATTERN.search(stripped)
                    if cidr_match:
                        machine_networks.append(cidr_match.group(1))
                index += 1

    deduped_cluster_networks = []
    seen_cluster_entries = set()
    for item in cluster_networks:
        key = (str(item.get("cidr")), str(item.get("hostPrefix", "")))
        if key in seen_cluster_entries:
            continue
        seen_cluster_entries.add(key)
        deduped_cluster_networks.append(item)

    return {
        "cluster_networks": deduped_cluster_networks,
        "service_networks": dedupe_preserve_order(service_networks),
        "machine_networks": dedupe_preserve_order(machine_networks),
    }
