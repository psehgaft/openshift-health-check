#!/usr/bin/env python3
"""Run the real unified suite using stored API evidence in place of live shell collection."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("unified", ROOT / "scripts/unified_healthcheck.py")
unified = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unified)
real_run = unified.run


def fixture_collection(command, **kwargs):
    if str(command[0]) != "bash" or "ocp-healthcheck.sh" not in str(command[1]):
        return real_run(command, **kwargs)
    # Replace only live shell execution; normalization, Ansible, and generator setup are real.
    output = Path(command[command.index("--output") + 1]) / "healthcheck-fixture"
    (output / "raw").mkdir(parents=True)
    docs = []
    for path in sorted((ROOT / "tests/fixtures/must-gather.local.mock").rglob("resources.yaml")):
        for item in yaml.safe_load_all(path.read_text()):
            if item:
                docs.extend(item.get("items", [item]))
    (output / "raw/baseline.json").write_text(json.dumps({"apiVersion": "v1", "kind": "List", "items": docs}))
    (output / "csv").mkdir()
    for name in ("findings.csv", "backlog.csv", "errors-criticality.csv"):
        (output / "csv" / name).write_text("severity,finding\nMajor,Fixture review required\n")


with tempfile.TemporaryDirectory(prefix="unified-health-fixture-") as tmp:
    output = Path(tmp) / "suite"
    with patch.object(unified, "run", side_effect=fixture_collection), patch.object(sys, "argv", [
        "unified_healthcheck.py", "suite", "--output", str(output), "--client", "Fixture Client",
        "--cluster-name", "fixture-ocp"]):
        unified.main()
    manifest = json.loads((output / "architecture/manifest.json").read_text())
    assert manifest["finding_rows"] >= 3
    assert (output / "architecture/generator/project.yaml").is_file()
    assert list((output / "canonical").glob("*.md"))
    print("Unified suite fixture passed: shell evidence → canonical collected report → native architecture workspace")
