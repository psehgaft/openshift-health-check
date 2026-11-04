# Toolkits

This directory contains three toolkits with separate responsibilities.

| Toolkit | Purpose | Start here |
| --- | --- | --- |
| [openshift-healthcheck](openshift-healthcheck/) | Shell, Ansible, ACM, certificate, DNS, and Headlamp health-check utilities | [Integration guide](../docs/three-repository-integration.md) |
| [openshift-atp](openshift-atp/) | OpenShift acceptance tests with Markdown and HTML evidence reports | [ATP guide](../docs/ATP_PLAYBOOK_GUIDE.md) |
| [arch-design-doc-generator](arch-design-doc-generator/) | Architecture decisions, HLD/LLD, diagrams, and work items | [Generator README](arch-design-doc-generator/README.md) |

The canonical health-check engine and its multi-platform reporting workflow remain at the repository root. These folders group the specialist and imported tools; existing documents are retained.
