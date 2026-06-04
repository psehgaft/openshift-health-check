# OpenShift Live API Fallback Catalog

Catalog file:

- [catalogs/openshift/live-api-fallback-catalog.yml](../catalogs/openshift/live-api-fallback-catalog.yml)

This file controls collected-mode live API backfill for OpenShift runs.

It answers four questions:

- which API resources may be backfilled with live `oc get`
- which postures and capabilities depend on those resources
- which resource keys are cluster-scoped
- which keys need stricter sufficiency checks than “payload exists”

This file is not a replacement for [inputs/openshift-cluster-health-profile.yml](../inputs/openshift-cluster-health-profile.yml), and it does not describe non-API sources such as `inspect`, `sosreport`, `cluster-compare`, Advisor export, managed-gates, or Insights archive parsing.

## Coverage Rules

Keep this catalog complete for the current API-backed resource-key set.

1. Every resource key in [scripts/extract_offline_resources.py](../scripts/extract_offline_resources.py) should appear in at least one posture or capability mapping when live API fallback is meaningful.
2. Every capability in `inputs/openshift-cluster-health-profile.yml` should have an explicit entry in `capability_resources`, even when that entry is intentionally empty because the capability has no dedicated API-backed resource key yet.
3. Resource keys that require stronger checks than “payload exists” should have a `sufficiency_rules` entry.

An empty capability mapping is acceptable only when one of these is true:

- the capability depends mostly on non-API evidence
- the capability depends on product-specific CRDs that are not yet part of `RESOURCE_KEYS`
- the capability is already covered well enough by its owning posture during non-scoped runs, but there is no precise capability-local API key to target

If a capability should participate in live backfill and still has an empty mapping, fix the catalog.

## How To Maintain It

When adding or changing API-backed evidence:

1. Update [scripts/extract_offline_resources.py](../scripts/extract_offline_resources.py) first if the resource key does not exist yet.
2. Add the resource key to the fallback catalog.
3. Place it in the owning posture mapping.
4. Add it to any capability mappings that should work in capability-only scoped runs.
5. Add the key to `cluster_scoped_resource_keys` when the live command should be cluster-scoped.
6. Add a `sufficiency_rules` entry when a bare object or list is not enough to tell whether the offline evidence is usable.
7. Update docs if the fallback behavior or maintenance expectations changed.

Before adding a key, check:

- Is this evidence recoverable from `oc get` alone?
- Is the resource namespaced or cluster-scoped?
- Does selector-scoped fallback need the key for a specific capability?
- Does the key need a semantic sufficiency rule instead of the default “payload exists” rule?

## Validation

After editing the catalog, run the narrowest useful checks first:

```bash
python3 -m py_compile scripts/build_live_api_fallback_plan.py scripts/extract_offline_resources.py
ansible-playbook --syntax-check playbooks/openshift_cluster_health_report.yml
python3 scripts/discover_case_bundle.py tests/fixtures | python3 -m json.tool
```

Then run a real collected-mode path that exercises fallback planning:

```bash
scripts/run_ci_report.sh playbooks/openshift_cluster_health_report.yml \
  -e report_basename=cluster-supportability \
  -e collected_evidence_root=tests/fixtures \
  -e selected_capabilities=etcd_encryption
```

For broader contract changes, finish with:

```bash
tests/run_ci_report_fixture.sh
```
