#!/usr/bin/env python3
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: build_authentication_findings.py <input-json-path>"}))
        return 2

    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    idps = (((data.get("oauth_config") or {}).get("spec") or {}).get("identityProviders") or [])
    secrets = data.get("secrets") or []

    local_types = {"htpasswd", "basicauth"}
    external_types = {"github", "gitlab", "google", "ldap", "keystone", "openid", "requestheader"}
    generic_keys = {"name", "mappingMethod", "type", "challenge", "login"}
    provider_types = []
    provider_names = []
    external_provider_count = 0
    local_provider_count = 0
    invalid_provider_count = 0

    for item in idps:
        if not isinstance(item, dict):
            continue
        provider_names.append(str(item.get("name") or "unnamed"))
        typed_keys = [key for key in item.keys() if key not in generic_keys and item.get(key) is not None]
        provider_type = typed_keys[0] if typed_keys else str(item.get("type") or "unknown")
        provider_type_normalized = provider_type.strip().lower()
        if provider_type_normalized == "basicauth":
            provider_type = "basicAuth"
        elif provider_type_normalized == "openid":
            provider_type = "openID"
        elif provider_type_normalized == "requestheader":
            provider_type = "requestHeader"
        else:
            provider_type = provider_type.strip()
        provider_types.append(provider_type)
        if provider_type_normalized in local_types:
            local_provider_count += 1
        elif provider_type_normalized in external_types:
            external_provider_count += 1
        else:
            invalid_provider_count += 1

    kubeadmin_secret_present = any(
        ((item.get("metadata") or {}).get("name") == "kubeadmin")
        and ((item.get("metadata") or {}).get("namespace") == "kube-system")
        for item in secrets
        if isinstance(item, dict)
    )

    findings = []
    if len(idps) == 0:
        detail = "oauth/cluster has no configured identityProviders"
        if kubeadmin_secret_present:
            detail += "; kubeadmin secret is still present"
        findings.append({"issue": "missing-identity-provider", "detail": detail})
        status = "warning"
        reason_summary = "no configured identity providers"
    elif external_provider_count == 0 and local_provider_count > 0:
        detail = "only local identity providers are configured: " + ", ".join(sorted(set(provider_types)))
        if kubeadmin_secret_present:
            detail += "; kubeadmin secret is still present"
        if invalid_provider_count > 0:
            detail += f"; unclassified identity provider entries={invalid_provider_count}"
        findings.append({"issue": "local-only-identity-provider", "detail": detail})
        status = "warning"
        reason_summary = "only local identity providers are configured"
    elif external_provider_count == 0:
        detail = (
            "oauth/cluster does not show a valid external identity provider configuration; "
            + "provider types observed: "
            + (", ".join(sorted(set(provider_types))) or "unknown")
        )
        if kubeadmin_secret_present:
            detail += "; kubeadmin secret is still present"
        findings.append({"issue": "invalid-identity-provider-configuration", "detail": detail})
        status = "warning"
        reason_summary = "no valid external identity providers are configured"
    elif kubeadmin_secret_present:
        findings.append(
            {
                "issue": "kubeadmin-secret-still-present",
                "detail": "kubeadmin secret is still present while identity providers are configured",
            }
        )
        status = "review"
        reason_summary = "external identity providers are configured, but kubeadmin fallback is still present"
    elif invalid_provider_count > 0:
        findings.append(
            {
                "issue": "unclassified-identity-provider-configuration",
                "detail": "one or more identity provider entries could not be classified as a supported local or external provider type",
            }
        )
        status = "review"
        reason_summary = "external identity providers are configured, but some provider entries are unclassified"
    elif external_provider_count == 1 and len(idps) == 1:
        status = "healthy"
        reason_summary = "single external identity provider configured"
    else:
        status = "healthy"
        reason_summary = "external identity providers are configured"

    print(
        json.dumps(
            {
                "auth_findings": findings,
                "auth_posture_summary": {
                    "status": status,
                    "identity_provider_count": len(idps),
                    "provider_names": provider_names,
                    "provider_types": provider_types,
                    "external_identity_provider_count": external_provider_count,
                    "local_identity_provider_count": local_provider_count,
                    "invalid_identity_provider_count": invalid_provider_count,
                    "kubeadmin_secret_present": kubeadmin_secret_present,
                    "reason_summary": reason_summary,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
