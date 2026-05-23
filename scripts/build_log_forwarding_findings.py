#!/usr/bin/env python3
import json
import sys


def is_external_url(url):
    if not url:
        return False
    s = str(url).lower()
    return not (".svc" in s or ".cluster.local" in s or s.startswith("http://localhost") or s.startswith("https://localhost"))


def output_is_external(output):
    otype = str(output.get("type", "")).lower()
    url = output.get("url") or output.get("endpoint") or output.get("host") or ""
    if is_external_url(url):
        return True
    if otype in {"cloudwatch", "azuremonitor", "googlecloudlogging"}:
        return True
    return False


def normalize_inputs(pipeline):
    refs = pipeline.get("inputRefs")
    if isinstance(refs, list):
        return [str(item).lower() for item in refs if item not in (None, "")]
    if refs not in (None, ""):
        return [str(refs).lower()]
    input_ref = pipeline.get("inputRef")
    if input_ref not in (None, ""):
        return [str(input_ref).lower()]
    return []


def build(data):
    findings = []
    outputs = []
    external_outputs = []
    pipeline_counts = {"application": 0, "infrastructure": 0, "audit": 0}
    external_pipeline_counts = {"application": 0, "infrastructure": 0, "audit": 0}

    for clf in data["items"]:
        ns = clf.get("metadata", {}).get("namespace", "")
        name = clf.get("metadata", {}).get("name", "")
        spec = clf.get("spec", {}) or {}
        pipelines = spec.get("pipelines", []) or []
        output_refs = set()
        for pipeline in pipelines:
            for ref in pipeline.get("outputRefs", []) or []:
                output_refs.add(ref)
        current_outputs = spec.get("outputs", []) or []
        output_by_name = {str(item.get("name", "")): item for item in current_outputs if item.get("name")}
        if not current_outputs:
            findings.append({
                "issue": "clusterlogforwarder-without-outputs",
                "detail": f"{ns}/{name} has no outputs"
            })
        for output in current_outputs:
            output_name = output.get("name", "")
            record = {
                "namespace": ns,
                "clusterlogforwarder": name,
                "name": output_name,
                "type": output.get("type", "unknown"),
                "target": output.get("url") or output.get("endpoint") or output.get("host") or ""
            }
            outputs.append(record)
            if output_is_external(output):
                external_outputs.append(record)
        for pipeline in pipelines:
            input_refs = normalize_inputs(pipeline)
            pipeline_output_refs = [str(ref) for ref in (pipeline.get("outputRefs", []) or []) if ref not in (None, "")]
            pipeline_external = any(output_is_external(output_by_name.get(ref, {})) for ref in pipeline_output_refs)
            for log_type in ("application", "infrastructure", "audit"):
                if log_type in input_refs:
                    pipeline_counts[log_type] += 1
                    if pipeline_external:
                        external_pipeline_counts[log_type] += 1
        if current_outputs and not any(output_is_external(o) for o in current_outputs):
            findings.append({
                "issue": "logs-not-forwarded-to-external-destination",
                "detail": f"{ns}/{name} outputs appear cluster-local only"
            })
        if pipelines and not output_refs:
            findings.append({
                "issue": "clusterlogforwarder-pipelines-without-outputrefs",
                "detail": f"{ns}/{name} has pipelines with no outputRefs"
            })

    if not data["items"] and bool(data.get("require_cluster_log_forwarder")) and not data.get("vendor_managed_present"):
        findings.append({
            "issue": "missing-clusterlogforwarder",
            "detail": "no ClusterLogForwarder resource found"
        })

    for log_type in ("application", "infrastructure", "audit"):
        if bool(data.get("require_cluster_log_forwarder")) and not data.get("vendor_managed_present"):
            if pipeline_counts[log_type] == 0:
                findings.append({
                    "issue": f"{log_type}-logs-not-collected",
                    "detail": f"no ClusterLogForwarder pipeline was found for {log_type} logs"
                })
            elif external_pipeline_counts[log_type] == 0:
                findings.append({
                    "issue": f"{log_type}-logs-not-exported-external",
                    "detail": f"{log_type} logs appear to be collected but not forwarded to an external destination"
                })

    return {
        "findings": findings,
        "outputs": outputs,
        "external_outputs": external_outputs,
        "pipeline_counts": pipeline_counts,
        "external_pipeline_counts": external_pipeline_counts
    }


def main():
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    print(json.dumps(build(data)))


if __name__ == "__main__":
    main()
