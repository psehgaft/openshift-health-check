#!/usr/bin/env python3
import json
import re
import sys


STANDARDS = [
    ("FIPS", [r"\bfips\b"]),
    ("FedRAMP", [r"\bfedramp\b"]),
    ("HIPAA", [r"\bhipaa\b"]),
    ("PCI-DSS", [r"\bpci(?:[-_ ]?dss)?\b"]),
    ("SOC", [r"\bsoc[-_ ]?[123]\b", r"\bservice organization control\b"]),
    ("SOX", [r"\bsox\b"]),
    ("NIST", [r"\bnist\b"]),
    ("CIS", [r"\bcis\b"]),
]


def gather_strings(obj):
    if isinstance(obj, dict):
        strings = []
        for key, value in obj.items():
            if key in {"metadata", "spec", "title", "description", "id"}:
                strings.extend(gather_strings(value))
        return strings
    if isinstance(obj, list):
        strings = []
        for item in obj:
            strings.extend(gather_strings(item))
        return strings
    if isinstance(obj, str):
        return [obj]
    return []


def resource_matches(item, regexes):
    haystack = " ".join(gather_strings(item)).lower()
    return any(re.search(pattern, haystack) for pattern in regexes)


def metadata_name(item):
    return str(((item.get("metadata") or {}).get("name") or ""))


def binding_profile_refs(binding):
    refs = []
    for profile in ((binding.get("profiles") or []) or []):
        if isinstance(profile, dict):
            refs.append(str(profile.get("name") or ""))
    return [item for item in refs if item]


def scan_profile_refs(scan):
    spec = scan.get("spec") or {}
    refs = []
    for key in ("profile", "profileRef", "tailoredProfile"):
        value = spec.get(key)
        if isinstance(value, str) and value:
            refs.append(value)
        elif isinstance(value, dict):
            name = str(value.get("name") or "")
            if name:
                refs.append(name)
    return refs


def scan_result(scan):
    status = scan.get("status") or {}
    return str(status.get("result") or status.get("phase") or "Unknown")


def scan_phase(scan):
    status = scan.get("status") or {}
    return str(status.get("phase") or "Unknown")


def check_result(item):
    status = item.get("status") or {}
    labels = (item.get("metadata") or {}).get("labels") or {}
    return str(
        status.get("result")
        or status.get("status")
        or labels.get("compliance.openshift.io/check-status")
        or item.get("result")
        or "Unknown"
    )


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    suites = data.get("compliancesuites") or []
    scans = data.get("compliancescans") or []
    scan_settings = data.get("scansettings") or []
    scan_setting_bindings = data.get("scansettingbindings") or []
    tailored_profiles = data.get("tailoredprofiles") or []
    profiles = data.get("profiles") or []
    profile_bundles = data.get("profilebundles") or []
    check_results = data.get("compliancecheckresults") or []
    sosreport_reports = data.get("sosreport_reports") or []
    fips_enabled_nodes = sum(
        1 for item in sosreport_reports if str(item.get("fips_enabled_status") or "") == "enabled"
    )
    fips_disabled_nodes = sum(
        1 for item in sosreport_reports if str(item.get("fips_enabled_status") or "") == "disabled"
    )
    fips_crypto_policy_nodes = sum(
        1 for item in sosreport_reports if "FIPS" in str(item.get("crypto_policy") or "").upper()
    )
    fips_runtime_evidence_count = fips_enabled_nodes + fips_disabled_nodes
    namespace_names = {(item.get("metadata") or {}).get("name", "") for item in (data.get("namespaces") or [])}

    operator_present = bool(
        suites
        or scans
        or scan_settings
        or scan_setting_bindings
        or tailored_profiles
        or profiles
        or profile_bundles
        or ("openshift-compliance" in namespace_names)
    )

    valid_profilebundle_count = 0
    invalid_profilebundle_count = 0
    profilebundle_summary = []
    for item in profile_bundles:
        status = item.get("status") or {}
        ds_status = str(status.get("dataStreamStatus") or "Unknown")
        profilebundle_summary.append(
            {
                "namespace": ((item.get("metadata") or {}).get("namespace") or ""),
                "name": ((item.get("metadata") or {}).get("name") or ""),
                "data_stream_status": ds_status,
            }
        )
        if ds_status == "VALID":
            valid_profilebundle_count += 1
        else:
            invalid_profilebundle_count += 1

    failing_scan_count = 0
    scan_summary = []
    for item in scans:
        result = scan_result(item)
        phase = scan_phase(item)
        if result not in {"COMPLIANT", "NOT-APPLICABLE", "PASS"} or phase not in {
            "DONE",
            "COMPLIANT",
            "NOT-APPLICABLE",
        }:
            failing_scan_count += 1
        scan_summary.append(
            {
                "namespace": ((item.get("metadata") or {}).get("namespace") or ""),
                "name": ((item.get("metadata") or {}).get("name") or ""),
                "phase": phase,
                "result": result,
            }
        )

    check_fail_count = 0
    for item in check_results:
        result = check_result(item)
        if result not in {"PASS", "COMPLIANT", "NOT-APPLICABLE", "INFO"}:
            check_fail_count += 1

    standards_summary = []
    standards_findings = []

    for standard_name, regexes in STANDARDS:
        matched_profiles = [item for item in profiles if resource_matches(item, regexes)]
        matched_tailored = [item for item in tailored_profiles if resource_matches(item, regexes)]
        standard_profile_names = {metadata_name(item) for item in matched_profiles + matched_tailored if metadata_name(item)}
        standard_profile_refs_lower = {item.lower() for item in standard_profile_names}
        matched_bindings = [
            item
            for item in scan_setting_bindings
            if (
                any(ref in standard_profile_names for ref in binding_profile_refs(item))
                or any(ref.lower() in standard_profile_refs_lower for ref in binding_profile_refs(item))
            )
        ]
        matched_binding_names = {metadata_name(item) for item in matched_bindings if metadata_name(item)}
        matched_suites = [item for item in suites if metadata_name(item) in matched_binding_names]
        matched_suite_names = {metadata_name(item) for item in matched_suites if metadata_name(item)}
        matched_scans = []
        for item in scans:
            labels = (item.get("metadata") or {}).get("labels") or {}
            owner_refs = item.get("metadata", {}).get("ownerReferences") or []
            owner_names = {str(ref.get("name") or "") for ref in owner_refs if isinstance(ref, dict)}
            scan_name = metadata_name(item)
            if (
                any(ref in standard_profile_names for ref in scan_profile_refs(item))
                or any(ref.lower() in standard_profile_refs_lower for ref in scan_profile_refs(item))
                or any(name in matched_suite_names for name in owner_names)
                or str(labels.get("compliance.openshift.io/suite") or "") in matched_suite_names
                or any(binding_name and binding_name in scan_name for binding_name in matched_binding_names)
            ):
                matched_scans.append(item)
        matched_scan_names = {metadata_name(item) for item in matched_scans if metadata_name(item)}
        matched_checks = []
        for item in check_results:
            labels = (item.get("metadata") or {}).get("labels") or {}
            if (
                str(labels.get("compliance.openshift.io/scan-name") or "") in matched_scan_names
                or str(labels.get("compliance.openshift.io/suite") or "") in matched_suite_names
            ):
                matched_checks.append(item)

        matched_settings = [
            item
            for item in scan_settings
            if metadata_name(item)
            in {str((binding.get("settingsRef") or {}).get("name") or "") for binding in matched_bindings}
        ]
        content_present = bool(matched_profiles or matched_tailored)
        configured = bool(matched_bindings or matched_suites or matched_scans)
        active_enabled = bool(matched_bindings or matched_suites or matched_scans)
        standard_failing_scans = [
            item
            for item in matched_scans
            if scan_result(item) not in {"COMPLIANT", "NOT-APPLICABLE", "PASS"}
            or scan_phase(item) not in {"DONE", "COMPLIANT", "NOT-APPLICABLE"}
        ]
        standard_failed_checks = [
            item
            for item in matched_checks
            if check_result(item) not in {"PASS", "COMPLIANT", "NOT-APPLICABLE", "INFO"}
        ]

        runtime_status = "not-applicable"
        if standard_name == "FIPS":
            configured = fips_runtime_evidence_count > 0
            active_enabled = False
            if fips_enabled_nodes > 0 and fips_disabled_nodes == 0:
                runtime_status = "enabled"
            elif fips_disabled_nodes > 0 and fips_enabled_nodes == 0:
                runtime_status = "not-enabled"
            elif fips_enabled_nodes > 0 and fips_disabled_nodes > 0:
                runtime_status = "mixed"
            elif fips_crypto_policy_nodes > 0:
                runtime_status = "crypto-policy-fips"
            else:
                runtime_status = "unknown"
        if standard_name == "FIPS" and runtime_status == "enabled":
            verdict = "supported"
        elif standard_name == "FIPS" and runtime_status == "crypto-policy-fips":
            verdict = "partial-evidence"
        elif standard_name == "FIPS" and runtime_status in {"not-enabled", "mixed"}:
            verdict = "review-required"
        elif standard_name == "FIPS" and content_present and not configured:
            verdict = "content-available"
        elif standard_name == "FIPS":
            verdict = "not-configured"
        elif active_enabled and (standard_failing_scans or standard_failed_checks):
            verdict = "review-required"
        elif active_enabled:
            verdict = "supported"
        elif configured:
            verdict = "configured-no-scan"
        elif content_present:
            verdict = "content-available"
        elif standard_failing_scans or standard_failed_checks:
            verdict = "review-required"
        else:
            verdict = "not-configured"

        standards_summary.append(
            {
                "standard": standard_name,
                "content_present": content_present,
                "configured": configured,
                "active_enabled": active_enabled,
                "profile_count": len(matched_profiles),
                "tailored_profile_count": len(matched_tailored),
                "scan_setting_count": len(matched_settings),
                "scan_setting_binding_count": len(matched_bindings),
                "profilebundle_count": 0,
                "suite_count": len(matched_suites),
                "scan_count": len(matched_scans),
                "failing_scan_count": len(standard_failing_scans),
                "failed_check_count": len(standard_failed_checks),
                "runtime_status": runtime_status,
                "runtime_evidence_count": fips_runtime_evidence_count if standard_name == "FIPS" else 0,
                "verdict": verdict,
                "detail": (
                    (
                        f"runtime FIPS evidence: enabled_nodes={fips_enabled_nodes}, disabled_nodes={fips_disabled_nodes}, crypto_policy_fips_nodes={fips_crypto_policy_nodes}"
                        if standard_name == "FIPS" and configured
                        else (
                            "FIPS compliance content is present, but runtime node FIPS evidence was not collected"
                            if standard_name == "FIPS" and content_present
                            else (
                                "no runtime node FIPS evidence was collected"
                                if standard_name == "FIPS"
                                else ""
                            )
                        )
                    )
                    if standard_name == "FIPS"
                    else (
                        "configured from Compliance Operator resources"
                        if configured
                        else (
                            "matching Compliance Operator content is present but not bound into current scans"
                            if content_present
                            else "no matching Compliance Operator standard configuration detected"
                        )
                    )
                ),
            }
        )

        if configured and verdict == "configured-no-scan":
            standards_findings.append(
                {
                    "severity": "warning",
                    "area": "compliance",
                    "standard": standard_name,
                    "detail": f"{standard_name} configuration was detected, but no ComplianceSuite or ComplianceScan evidence was found.",
                }
            )
        if content_present and not configured:
            standards_findings.append(
                {
                    "severity": "info",
                    "area": "compliance",
                    "standard": standard_name,
                    "detail": f"{standard_name} compliance content is available, but no current binding, suite, or scan evidence shows it is configured.",
                }
            )
        if standard_failing_scans:
            standards_findings.append(
                {
                    "severity": "warning",
                    "area": "compliance",
                    "standard": standard_name,
                    "detail": f"{standard_name} has failing or incomplete compliance scans: {len(standard_failing_scans)}.",
                }
            )
        if standard_failed_checks:
            standards_findings.append(
                {
                    "severity": "warning",
                    "area": "compliance",
                    "standard": standard_name,
                    "detail": f"{standard_name} has failed compliance checks: {len(standard_failed_checks)}.",
                }
            )
        if standard_name == "FIPS":
            if runtime_status == "unknown":
                standards_findings.append(
                    {
                        "severity": "info",
                        "area": "compliance",
                        "standard": standard_name,
                        "detail": "FIPS is an install-time cluster setting. Runtime FIPS mode remains unknown because no explicit node evidence was collected from sosreport or equivalent node diagnostics.",
                    }
                )
            elif runtime_status == "crypto-policy-fips":
                standards_findings.append(
                    {
                        "severity": "info",
                        "area": "compliance",
                        "standard": standard_name,
                        "detail": "FIPS crypto policy was detected, but /proc/sys/crypto/fips_enabled evidence was not collected to confirm runtime FIPS mode.",
                    }
                )
            elif runtime_status in {"not-enabled", "mixed"}:
                standards_findings.append(
                    {
                        "severity": "warning",
                        "area": "compliance",
                        "standard": standard_name,
                        "detail": f"FIPS is expected to be enabled at installation time, but runtime node evidence is {runtime_status}.",
                    }
                )

    if not operator_present:
        operator_verdict = "not-installed"
    elif invalid_profilebundle_count > 0 or failing_scan_count > 0 or check_fail_count > 0:
        operator_verdict = "review-required"
    elif suites or scans:
        operator_verdict = "supported"
    else:
        operator_verdict = "configured-no-scan"

    findings = []
    if operator_present and invalid_profilebundle_count > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "compliance",
                "detail": f"Compliance Operator profile bundles not reporting VALID: {invalid_profilebundle_count}.",
            }
        )
    if operator_present and failing_scan_count > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "compliance",
                "detail": f"Compliance Operator scans failing or incomplete: {failing_scan_count}.",
            }
        )
    if operator_present and check_fail_count > 0:
        findings.append(
            {
                "severity": "warning",
                "area": "compliance",
                "detail": f"Compliance check results not passing: {check_fail_count}.",
            }
        )
    findings.extend(standards_findings)

    print(
        json.dumps(
            {
                "operator_summary": {
                    "present": operator_present,
                    "namespace_present": "openshift-compliance" in namespace_names,
                    "suite_count": len(suites),
                    "scan_count": len(scans),
                    "scan_setting_count": len(scan_settings),
                    "scan_setting_binding_count": len(scan_setting_bindings),
                    "profile_count": len(profiles),
                    "tailored_profile_count": len(tailored_profiles),
                    "profilebundle_count": len(profile_bundles),
                    "valid_profilebundle_count": valid_profilebundle_count,
                    "invalid_profilebundle_count": invalid_profilebundle_count,
                    "failing_scan_count": failing_scan_count,
                    "failed_check_count": check_fail_count,
                    "standards_configured_count": len([item for item in standards_summary if item["configured"]]),
                    "fips_runtime_status": next(
                        (item["runtime_status"] for item in standards_summary if item["standard"] == "FIPS"),
                        "unknown",
                    ),
                    "fips_enabled_node_count": fips_enabled_nodes,
                    "fips_disabled_node_count": fips_disabled_nodes,
                    "verdict": operator_verdict,
                    "profilebundle_summary": profilebundle_summary,
                    "scan_summary": scan_summary[:20],
                },
                "standards_summary": standards_summary,
                "findings": findings,
            }
        )
    )


if __name__ == "__main__":
    main()
