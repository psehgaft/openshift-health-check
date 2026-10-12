"""Exercise imported generator setup and shell-to-canonical evidence interoperability."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("unified", ROOT / "scripts/unified_healthcheck.py")
unified = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unified)


class IntegrationTests(unittest.TestCase):
    def test_shell_list_is_consumed_by_real_canonical_extractor(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw = base / "shell/raw"
            raw.mkdir(parents=True)
            node = {"kind": "Node", "apiVersion": "v1", "metadata": {"name": "worker-0"}}
            (raw / "baseline-nodes.json").write_text(json.dumps({"kind": "List", "items": [node]}))
            (raw / "duplicate.json").write_text(json.dumps(node))
            secret = {"kind": "Secret", "apiVersion": "v1", "metadata": {"name": "test"},
                      "data": {"password": "sensitive"}, "stringData": {"password": "sensitive"}}
            (raw / "secret.json").write_text(json.dumps(secret))
            (raw / "failed.json").write_text("permission denied")
            summary = unified.normalize_shell_evidence(base / "shell", base / "normalized")
            self.assertEqual(summary["objects"], 2)
            self.assertEqual(len(summary["invalid_files"]), 1)
            for path in (base / "normalized").glob("resource-*.json"):
                self.assertNotIn("sensitive", path.read_text())
            result = subprocess.check_output([sys.executable, ROOT / "scripts/extract_offline_resources.py",
                                              "inspect", base / "normalized"], text=True)
            payload = json.loads(result)
            self.assertEqual(payload["nodes"]["items"][0]["metadata"]["name"], "worker-0")

    def test_native_architecture_setup_and_source_traceability(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = base / "report.json"
            report.write_text(json.dumps({"metadata": {"cluster_type": "openshift"},
                "findings": {"assessment_health": [{"finding": "Node pressure", "severity": "warning"}]}}))
            shell = base / "shell/csv"
            shell.mkdir(parents=True)
            for name in ("findings.csv", "backlog.csv", "errors-criticality.csv"):
                (shell / name).write_text('severity,finding\nMajor,"Probe missing"\n')
            output = base / "engagement"
            with contextlib.redirect_stdout(io.StringIO()):
                manifest = unified.build_architecture(report, output, "Test Client", shell.parent)
            self.assertEqual(manifest["finding_rows"], 4)
            self.assertTrue((output / "generator/project.yaml").is_file())
            adr = output / manifest["architecture_adr"]
            self.assertIn("HC-0001", adr.read_text())
            self.assertIn("Node pressure", adr.read_text())
            self.assertTrue((output / "generator/LICENSE").is_file())
            with self.assertRaises(FileExistsError):
                unified.build_architecture(report, output, "Test Client")

    def test_wrong_platform_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            report = base / "report.json"
            report.write_text(json.dumps({"metadata": {"cluster_type": "aks", "platform_family": "kubernetes"}}))
            with self.assertRaises(ValueError):
                unified.build_architecture(report, base / "output", "Test")
            self.assertFalse((base / "output").exists())


if __name__ == "__main__":
    unittest.main()
