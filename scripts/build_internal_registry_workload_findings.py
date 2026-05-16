#!/usr/bin/env python3
import json
import re
import sys


INTERNAL_MARKERS = [
    "image-registry.openshift-image-registry.svc",
    "image-registry.openshift-image-registry.svc:5000",
]


def is_internal_image(image):
    text = str(image or "").strip().lower()
    return any(marker in text for marker in INTERNAL_MARKERS)


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    exclude_re = re.compile(data.get("exclude_regex") or r"^$")
    findings = []
    for kind, key in [
        ("Deployment", "deployments"),
        ("StatefulSet", "statefulsets"),
        ("DaemonSet", "daemonsets"),
    ]:
        for item in data.get(key, []):
            meta = item.get("metadata", {}) or {}
            ns = meta.get("namespace", "")
            if exclude_re.search(ns or ""):
                continue
            template_spec = ((((item.get("spec", {}) or {}).get("template", {}) or {}).get("spec", {})) or {})
            containers = (template_spec.get("containers", []) or []) + (template_spec.get("initContainers", []) or [])
            matched = []
            for container in containers:
                image = container.get("image", "")
                if is_internal_image(image):
                    matched.append(
                        {
                            "container": container.get("name", "unknown"),
                            "image": image,
                        }
                    )
            if matched:
                findings.append(
                    {
                        "kind": kind,
                        "namespace": ns,
                        "name": meta.get("name", "unknown"),
                        "container_names": [entry["container"] for entry in matched],
                        "images": sorted({entry["image"] for entry in matched}),
                    }
                )

    result = {
        "internal_registry_workloads": findings,
        "image_registry_findings": (
            [
                {
                    "issue": "internal-registry-images-in-user-workloads",
                    "detail": f"{len(findings)} workload templates reference the internal OpenShift image registry service",
                }
            ]
            if findings
            else []
        ),
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
