#!/usr/bin/env python3
import json
import re
import sys


def main() -> int:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)

    system_name_re = re.compile(r"^(system:|kube:|openshift:)")
    user_names = {
        str((((item.get("metadata") or {}).get("name")) or "")).strip()
        for item in (data.get("users") or [])
        if str((((item.get("metadata") or {}).get("name")) or "")).strip()
    }
    group_map = {
        str((((item.get("metadata") or {}).get("name")) or "")).strip(): item
        for item in (data.get("groups") or [])
        if str((((item.get("metadata") or {}).get("name")) or "")).strip()
    }

    stale_users = []
    stale_groups = []
    bindings = (data.get("rolebindings") or []) + (data.get("clusterrolebindings") or [])

    for binding in bindings:
        subjects = binding.get("subjects") or []
        binding_kind = str(binding.get("kind") or "Binding").strip() or "Binding"
        binding_namespace = str((((binding.get("metadata") or {}).get("namespace")) or "")).strip()
        binding_name = str((((binding.get("metadata") or {}).get("name")) or "unknown")).strip() or "unknown"
        binding_scope = "cluster-wide" if not binding_namespace else f"namespace {binding_namespace}"
        grant_source = (
            f"{binding_kind}/{binding_name}"
            if not binding_namespace
            else f"{binding_kind}/{binding_namespace}/{binding_name}"
        )

        for subject in subjects:
            kind = str(subject.get("kind") or "").strip()
            name = str(subject.get("name") or "").strip()
            if not name or system_name_re.search(name):
                continue
            if kind == "User":
                if name not in user_names:
                    stale_users.append(
                        {
                            **subject,
                            "binding_scope": binding_scope,
                            "grant_source": grant_source,
                            "reason": "subject appears in RBAC bindings but no matching OpenShift User object was collected",
                        }
                    )
            elif kind == "Group":
                matching_group = group_map.get(name)
                if matching_group is None:
                    stale_groups.append(
                        {
                            **subject,
                            "binding_scope": binding_scope,
                            "grant_source": grant_source,
                            "reason": "subject appears in RBAC bindings but no matching OpenShift Group object was collected",
                        }
                    )
                else:
                    matching_group_users = matching_group.get("users") or []
                    if len(matching_group_users) == 0:
                        stale_groups.append(
                            {
                                **subject,
                                "binding_scope": binding_scope,
                                "grant_source": grant_source,
                                "reason": "matching OpenShift Group object was collected but it currently lists no members",
                            }
                        )

    print(
        json.dumps(
            {
                "stale_access_review_serviceaccounts": data.get("likely_unused_serviceaccounts") or [],
                "stale_access_review_users": stale_users,
                "stale_access_review_groups": stale_groups,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
