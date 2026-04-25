#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


SENSITIVE_RULES = [
    ("private-key", "private key material", lambda name: name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"} or name.endswith((".pem", ".key", ".p12", ".pfx"))),
    ("kubeconfig", "cluster access config", lambda name: "kubeconfig" in name),
    ("pull-secret", "registry pull secret", lambda name: "pull-secret" in name or "pull_secret" in name),
    ("token", "authentication token", lambda name: "token" in name),
    ("credential", "credential material", lambda name: "credential" in name or "password" in name or "passwd" in name or "htpasswd" in name),
    ("secret", "generic secret material", lambda name: "secret" in name),
]

ARCHIVE_SUFFIXES = (".tar", ".tgz", ".gz", ".xz", ".zip", ".bz2")
LIMIT_CANDIDATES = 25


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze evidence hygiene and redaction candidates.")
    parser.add_argument("--root", nargs=2, action="append", metavar=("LABEL", "PATH"), default=[])
    return parser.parse_args()


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def match_sensitive_rule(path: Path):
    name = path.name.lower()
    for category, reason, matcher in SENSITIVE_RULES:
        if matcher(name):
            return {"category": category, "reason": reason}
    return None


def build_guidance(summary):
    guidance = [
        "Review candidate sensitive files before sharing the evidence bundle outside the primary support or SRE workflow.",
        "Prefer sharing the report outputs and a redaction manifest before sharing raw bundle contents broadly.",
    ]
    if summary["private_key_candidates"] > 0:
        guidance.append("Remove or redact private key material before handing the bundle to general CI or collaboration tooling.")
    if summary["kubeconfig_candidates"] > 0 or summary["pull_secret_candidates"] > 0:
        guidance.append("Redact kubeconfig and pull-secret files or replace them with placeholder manifests before redistribution.")
    if summary["secret_like_candidates"] > 0 or summary["credential_candidates"] > 0 or summary["token_candidates"] > 0:
        guidance.append("Inspect secret, credential, and token-named files manually; filename-only detection may still undercount sensitive content.")
    return guidance


def scan_roots(roots):
    extension_counter = Counter()
    file_type_counter = Counter()
    root_summaries = []
    candidates = []
    total_files = 0
    total_directories = 0

    for label, root in roots:
        file_count = 0
        directory_count = 0
        candidate_count = 0
        for path in root.rglob("*"):
            if path.is_dir():
                directory_count += 1
                total_directories += 1
                continue
            if not path.is_file():
                continue
            total_files += 1
            file_count += 1
            suffix = path.suffix.lower() or "<none>"
            extension_counter[suffix] += 1
            if path.name.lower().endswith(ARCHIVE_SUFFIXES):
                file_type_counter["archive"] += 1
            sensitive = match_sensitive_rule(path)
            if sensitive:
                candidate_count += 1
                relative_path = str(path.relative_to(root))
                candidates.append(
                    {
                        "label": label,
                        "path": str(path),
                        "relative_path": relative_path,
                        "category": sensitive["category"],
                        "reason": sensitive["reason"],
                    }
                )
                file_type_counter[sensitive["category"]] += 1
        root_summaries.append(
            {
                "label": label,
                "path": str(root),
                "file_count": file_count,
                "directory_count": directory_count,
                "candidate_count": candidate_count,
            }
        )

    candidates.sort(key=lambda item: (item["category"], item["relative_path"]))
    summary = {
        "verdict": "review-required" if candidates else ("supported" if roots else "unknown"),
        "present": bool(roots),
        "scanned_root_count": len(roots),
        "scanned_file_count": total_files,
        "scanned_directory_count": total_directories,
        "candidate_count": len(candidates),
        "archive_file_count": file_type_counter["archive"],
        "private_key_candidates": file_type_counter["private-key"],
        "kubeconfig_candidates": file_type_counter["kubeconfig"],
        "pull_secret_candidates": file_type_counter["pull-secret"],
        "token_candidates": file_type_counter["token"],
        "credential_candidates": file_type_counter["credential"],
        "secret_like_candidates": file_type_counter["secret"],
        "top_extensions": [
            {"name": name, "count": count}
            for name, count in extension_counter.most_common(10)
        ],
    }

    findings = []
    if not roots:
        findings.append(
            {
                "severity": "warning",
                "area": "evidence-hygiene",
                "detail": "No evidence roots were available for hygiene scanning.",
            }
        )
    elif candidates:
        findings.append(
            {
                "severity": "warning",
                "area": "evidence-hygiene",
                "detail": f"Detected {len(candidates)} likely sensitive files that should be reviewed or redacted before redistribution.",
            }
        )
        if summary["private_key_candidates"] > 0:
            findings.append(
                {
                    "severity": "critical",
                    "area": "evidence-hygiene",
                    "detail": f"Detected {summary['private_key_candidates']} file(s) that look like private key material.",
                }
            )
        if summary["kubeconfig_candidates"] > 0 or summary["pull_secret_candidates"] > 0:
            findings.append(
                {
                    "severity": "warning",
                    "area": "evidence-hygiene",
                    "detail": f"Detected {summary['kubeconfig_candidates'] + summary['pull_secret_candidates']} kubeconfig or pull-secret candidate file(s).",
                }
            )
    else:
        findings.append(
            {
                "severity": "info",
                "area": "evidence-hygiene",
                "detail": "No filename-based sensitive evidence candidates were detected in the scanned roots.",
            }
        )

    return {
        "summary": summary,
        "roots": root_summaries,
        "findings": findings,
        "sensitive_candidates": candidates[:LIMIT_CANDIDATES],
        "redaction_guidance": build_guidance(summary),
    }


def main():
    args = parse_args()
    roots = []
    for label, raw_path in args.root:
        root = Path(raw_path).expanduser().resolve()
        if root.exists():
            roots.append((label, root))

    payload = scan_roots(roots)
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
