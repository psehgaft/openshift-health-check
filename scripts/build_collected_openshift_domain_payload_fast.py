#!/usr/bin/env python3
"""Build collected OpenShift domain payloads in one helper process."""

import json
import sys
from pathlib import Path

import build_collected_openshift_domain_payload as collected
import build_network_access_domain_payload as network_access
import build_node_health_domain_payload as node_health
import build_observability_domain_payload as observability
import build_platform_health_domain_payload as platform_health
import build_security_governance_domain_payload as security_governance
import build_storage_resilience_domain_payload as storage_resilience
import build_workload_health_domain_payload as workload_health


POSTURE_ARTIFACT_KEYS = {
    "supportability": "evidence_and_supportability",
    "platform_health": "platform_health",
    "observability": "observability",
    "node_health": "node_health_and_capacity",
    "network_access": "application_access_and_network_isolation",
    "backup_recovery": "backup_and_disaster_recovery",
    "security_governance": "security_and_governance",
    "workload_health": "workload_health",
    "architecture_lifecycle": "platform_architecture_and_lifecycle",
    "capacity_snapshot": "capacity_planning_snapshot",
    "declarative_operations": "declarative_operations",
    "day2_readiness": "day2_production_readiness",
}


def with_mode(data):
    payload = dict(data or {})
    payload["mode"] = "collected"
    return payload


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def load_posture_artifacts(postures_dir):
    if not postures_dir:
        return {}
    root = Path(postures_dir).expanduser()
    artifacts = {}
    for alias, key in POSTURE_ARTIFACT_KEYS.items():
        artifacts[alias] = load_json(root / f"{key}.json")
    return artifacts


def hydrate_artifact_inputs(data):
    hydrated = dict(data or {})
    artifacts = load_posture_artifacts(hydrated.get("postures_dir") or "")
    for alias, artifact in artifacts.items():
        artifact_key = f"{alias}_posture_artifact"
        render_key = f"{alias}_posture_render_inputs"
        hydrated.setdefault(artifact_key, artifact)
        hydrated.setdefault(render_key, artifact.get("render_inputs") or {})
    return hydrated


def build_payload(data):
    hydrated = hydrate_artifact_inputs(data)
    common = with_mode(hydrated)
    domain_inputs = dict(hydrated)
    domain_inputs.update(
        {
            "platform_health_domain_payload": platform_health.build_payload(common),
            "observability_domain_payload": observability.build_payload(common),
            "node_health_domain_payload": node_health.build_payload(common),
            "security_governance_domain_payload": security_governance.build_payload(common),
            "network_access_domain_payload": network_access.build_payload(common),
            "workload_health_domain_payload": workload_health.build_payload(common),
            "storage_resilience_domain_payload": storage_resilience.build_payload(common),
        }
    )
    return collected.build_payload(domain_inputs)


def main() -> int:
    data = json.loads(sys.stdin.read() or "{}")
    print(json.dumps(build_payload(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
