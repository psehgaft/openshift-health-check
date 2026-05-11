#!/usr/bin/env python3
"""Scaffold cluster health profile entries for maintainers.

This helper prints YAML snippets to stdout so maintainers can paste them into
the unified cluster health profile without hand-building every field.
"""

import argparse
import sys
from textwrap import dedent
from typing import List, Optional


VALID_OWNERS = [
    "supportability",
    "platform",
    "node",
    "backup",
    "operations",
    "observability",
    "security",
    "storage",
    "network",
    "release",
    "workload",
    "lifecycle",
    "capacity",
    "extensions",
    "day2",
]

VALID_CRITICALITY = ["critical", "high", "medium", "low", "info"]
VALID_EXPECTED_STATE = ["present", "absent", "configured", "healthy", "not_applicable"]
VALID_EVIDENCE = [
    "must-gather",
    "inspect",
    "oc-get",
    "oc-debug-node",
    "kubectl-get",
    "insights",
    "prometheus",
    "metrics",
    "provider-api",
]


def fail(message: str) -> None:
    print(f"scaffold failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def yaml_list(items: List[str], indent: int) -> str:
    prefix = " " * indent
    return "\n".join(f'{prefix}- "{item}"' for item in items)


def parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_capability(args: argparse.Namespace) -> str:
    docs = parse_csv(args.docs) or ["https://docs.example.com/path/to/capability"]
    verification = parse_csv(args.verification) or [
        "Describe the first observable sign that the capability is present and healthy.",
        "Describe how the team can confirm the intended workflow is operating correctly.",
    ]
    evidence = parse_csv(args.evidence_required) or ["must-gather", "oc-get"]

    invalid_evidence = sorted(set(evidence) - set(VALID_EVIDENCE))
    if invalid_evidence:
        fail(f"unsupported evidence values: {', '.join(invalid_evidence)}")

    return "\n".join(
        [
            f"    {args.key}:",
            f"      enabled: {str(args.enabled).lower()}",
            f"      required: {str(args.required).lower()}",
            f"      criticality: {args.criticality}",
            f"      expected_state: {args.expected_state}",
            f"      owner: {args.owner}",
            f"      evidence_required: [{', '.join(evidence)}]",
            f'      notes: "{args.notes}"',
            "      docs:",
            yaml_list(docs, 8),
            "      verification:",
            yaml_list(verification, 8),
        ]
    )


def build_posture(args: argparse.Namespace) -> str:
    docs = parse_csv(args.docs) or ["https://docs.example.com/path/to/posture"]
    verification = parse_csv(args.verification) or [
        "Describe the first observable sign that the posture expectation is met.",
        "Describe how the team can confirm the posture remains healthy in future runs.",
    ]
    includes = parse_csv(args.includes)
    satisfied_by_all = parse_csv(args.satisfied_by_all)

    includes_value = f"[{', '.join(includes)}]" if includes else "[]"
    satisfied_value = f"[{', '.join(satisfied_by_all)}]" if satisfied_by_all else "[]"

    return "\n".join(
        [
            f"    {args.key}:",
            f"      enabled: {str(args.enabled).lower()}",
            f"      required: {str(args.required).lower()}",
            f"      owner: {args.owner}",
            f'      notes: "{args.notes}"',
            "      docs:",
            yaml_list(docs, 8),
            "      verification:",
            yaml_list(verification, 8),
            f"      includes: {includes_value}",
            f"      satisfied_by_all: {satisfied_value}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print YAML snippets for new cluster health capabilities or postures."
    )
    subparsers = parser.add_subparsers(dest="kind", required=True)

    cap = subparsers.add_parser("capability", help="Scaffold a capability entry")
    cap.add_argument("key", help="Capability key, for example external_secrets_operator")
    cap.add_argument("--enabled", action=argparse.BooleanOptionalAction, default=False)
    cap.add_argument("--required", action=argparse.BooleanOptionalAction, default=False)
    cap.add_argument("--criticality", choices=VALID_CRITICALITY, default="info")
    cap.add_argument("--expected-state", choices=VALID_EXPECTED_STATE, default="present")
    cap.add_argument("--owner", choices=VALID_OWNERS, default="platform")
    cap.add_argument(
        "--evidence-required",
        default="must-gather,oc-get",
        help=f"Comma-separated evidence sources. Valid: {', '.join(VALID_EVIDENCE)}",
    )
    cap.add_argument(
        "--notes",
        default="Describe what the capability is, why it matters, and what risk exists if it is missing or unhealthy.",
        help="One-sentence operator-facing summary used in the five-question report format.",
    )
    cap.add_argument(
        "--docs",
        help="Comma-separated documentation URLs. If omitted, a placeholder URL is emitted.",
    )
    cap.add_argument(
        "--verification",
        help="Comma-separated verification lines. If omitted, two placeholders are emitted.",
    )

    posture = subparsers.add_parser("posture", help="Scaffold a posture entry")
    posture.add_argument("key", help="Posture key, for example observability")
    posture.add_argument("--enabled", action=argparse.BooleanOptionalAction, default=True)
    posture.add_argument("--required", action=argparse.BooleanOptionalAction, default=True)
    posture.add_argument("--owner", choices=VALID_OWNERS, default="platform")
    posture.add_argument(
        "--notes",
        default="Describe what this posture covers, why it matters, and what risk exists if it is weak or unsupported.",
        help="One-sentence posture summary used in the five-question report format.",
    )
    posture.add_argument(
        "--docs",
        help="Comma-separated documentation URLs. If omitted, a placeholder URL is emitted.",
    )
    posture.add_argument(
        "--verification",
        help="Comma-separated verification lines. If omitted, two placeholders are emitted.",
    )
    posture.add_argument(
        "--includes",
        help="Comma-separated capability keys that normally satisfy this posture.",
    )
    posture.add_argument(
        "--satisfied-by-all",
        help="Comma-separated alternate capability keys that fully satisfy this posture.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.kind == "capability":
        print(build_capability(args))
    elif args.kind == "posture":
        print(build_posture(args))
    else:
        fail(f"unsupported scaffold kind: {args.kind}")

    print("", file=sys.stderr)
    print(
        "Next step: paste the snippet into inputs/openshift-cluster-health-profile.yml, "
        "replace placeholder text, then run scripts/validate_repo.sh",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
