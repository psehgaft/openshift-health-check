# Third-party source notices

See `integration/sources.json` for exact source commits.

## OpenShift specialist toolkit

- Source: https://github.com/psehgaft/openshift-healthcheck
- Location: `toolkits/openshift-healthcheck/`
- Original attribution and documentation retained.
- No root LICENSE was present in the imported snapshot; no new license is assigned by this import.
- Exclusions: tracked Python bytecode/cache artifacts, the prebuilt Headlamp archive, and its generated `dist/main.js`. The complete plugin source and build/package scripts are retained.
- Local modifications: correct ClusterOperator table health comparison; remove full Secret export fallback and strip `stringData` in metadata exports; replace embedded legacy login credentials and endpoint with environment lookups; replace SMTP/contact values with examples; hide legacy login task output with `no_log`; replace private pre-check environment metadata with examples and operator-supplied targets; repair missing platform packages and replace internal registry URLs in the Headlamp dependency lockfile; refresh ACM checksums after anonymizing example names.

## Architecture document generator

- Source: https://github.com/stratus-ss/arch-design-doc-generator
- Location: `tools/arch-design-doc-generator/`
- License: GNU GPLv3; full license retained at `tools/arch-design-doc-generator/LICENSE`.
- Original notices, scripts, templates, test suite, container build, and documentation retained.
- The integration invokes the generator as a separate process and keeps its files in a distinct source module. Root Apache-2.0 licensing must not be applied to this module.
- No source modifications in this initial snapshot.
