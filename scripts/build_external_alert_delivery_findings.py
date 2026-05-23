#!/usr/bin/env python3
import json
import sys


SUPPORTED_RECEIVER_KEYS = [
    ("slackConfigs", "slack"),
    ("pagerdutyConfigs", "pagerduty"),
    ("opsgenieConfigs", "opsgenie"),
    ("victorOpsConfigs", "victorops"),
    ("webhookConfigs", "webhook"),
    ("wechatConfigs", "wechat"),
    ("emailConfigs", "email"),
]


def describe_target(receiver_type, cfg):
    if receiver_type == "slack":
        return cfg.get("channel") or "configured"
    if receiver_type == "webhook":
        return cfg.get("url") or "secret-or-config-ref"
    if receiver_type == "email":
        return cfg.get("to") or "configured"
    if receiver_type in {"pagerduty", "opsgenie", "victorops", "wechat"}:
        return "configured"
    return "configured"


def collect_route_receivers(route_obj, result):
    route_obj = route_obj or {}
    receiver = route_obj.get("receiver")
    if receiver:
        result.add(str(receiver))
    for child in route_obj.get("routes", []) or []:
        collect_route_receivers(child, result)


def bool_value(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def build(data):
    findings = []
    receivers = []
    config_sources = []
    configs_with_external_routes = 0
    configs_without_route_receivers = 0
    require_external_alert_delivery = bool_value(data.get("require_external_alert_delivery"))

    for item in data.get("items", []):
        meta = item.get("metadata", {}) or {}
        namespace = meta.get("namespace", "")
        config_name = meta.get("name", "")
        external_receiver_names = set()
        for receiver in (item.get("spec", {}) or {}).get("receivers", []) or []:
            receiver_name = receiver.get("name", "unnamed")
            for key, receiver_type in SUPPORTED_RECEIVER_KEYS:
                for cfg in receiver.get(key, []) or []:
                    external_receiver_names.add(receiver_name)
                    receivers.append({
                        "namespace": namespace,
                        "alertmanagerconfig": config_name,
                        "receiver": receiver_name,
                        "type": receiver_type,
                        "target": describe_target(receiver_type, cfg),
                    })
        if external_receiver_names:
            config_sources.append({
                "source": "AlertmanagerConfig",
                "namespace": namespace,
                "name": config_name,
            })

        route_receivers = set()
        collect_route_receivers((item.get("spec", {}) or {}).get("route") or {}, route_receivers)
        routed_external_receivers = sorted(route_receivers.intersection(external_receiver_names))
        if external_receiver_names and routed_external_receivers:
            configs_with_external_routes += 1
        elif external_receiver_names and not route_receivers:
            configs_without_route_receivers += 1
            findings.append({
                "issue": "alertmanagerconfig-route-missing",
                "detail": f"{namespace}/{config_name} defines external receivers but no route receiver was configured"
            })
        elif external_receiver_names and not routed_external_receivers:
            findings.append({
                "issue": "external-alert-receiver-not-routed",
                "detail": f"{namespace}/{config_name} defines external receivers that are not referenced by any route"
            })

    cluster_additional_count = len(data.get("cluster_alertmanager_additional_configs") or [])
    user_additional_count = len(data.get("user_workload_alertmanager_additional_configs") or [])
    if cluster_additional_count > 0:
        config_sources.append({
            "source": "cluster-monitoring-config",
            "namespace": "openshift-monitoring",
            "name": "alertmanagerMain.additionalAlertmanagerConfigs",
        })
    if user_additional_count > 0:
        config_sources.append({
            "source": "user-workload-monitoring-config",
            "namespace": "openshift-user-workload-monitoring",
            "name": "alertmanager.additionalAlertmanagerConfigs",
        })

    if require_external_alert_delivery and not receivers and not config_sources:
        findings.append({
            "issue": "external-alert-delivery-not-configured",
            "detail": "no AlertmanagerConfig receiver was found for supported external channels such as email, Slack, PagerDuty, Opsgenie, VictorOps, webhook, or WeChat"
        })
    elif not receivers and config_sources:
        findings.append({
            "issue": "external-alert-delivery-not-verifiable",
            "detail": "additional Alertmanager configuration was detected, but no explicit externally routed receivers were visible in AlertmanagerConfig resources"
        })

    return {
        "findings": findings,
        "receivers": receivers,
        "config_sources": config_sources,
        "alert_delivery_source_count": len(config_sources),
        "external_alert_receiver_count": len(receivers),
        "external_alert_delivery_configured": len(receivers) > 0,
        "alert_routing_to_external_receiver_configured": configs_with_external_routes > 0,
        "alertmanagerconfigs_with_external_routes": configs_with_external_routes,
        "alertmanagerconfigs_without_route_receivers": configs_without_route_receivers
    }


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))


if __name__ == "__main__":
    main()
