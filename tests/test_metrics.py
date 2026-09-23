import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_scene_completion import sample_model
from tools.scene_completion.concerns import plan_concern_matrix
from tools.scene_completion.metrics import attach_metrics_to_run_manifest, load_stage_metrics

_CLI_PATH = Path(__file__).resolve().parents[1] / "tools" / "scene_completion.py"
_CLI_SPEC = importlib.util.spec_from_file_location("scene_completion_cli", _CLI_PATH)
_CLI_MODULE = importlib.util.module_from_spec(_CLI_SPEC)
assert _CLI_SPEC and _CLI_SPEC.loader
_CLI_SPEC.loader.exec_module(_CLI_MODULE)
main = _CLI_MODULE.main


class MetricsTests(unittest.TestCase):
    def test_cli_metrics_are_optional_and_store_counts_not_input_content(self):
        model = sample_model()
        model["use_cases"][0]["use_case_name"] = "private test phrase"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path = root / "model.json"
            model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            metrics_dir = root / "metrics"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["validate-model", "--input", str(model_path), "--metrics-dir", str(metrics_dir)]), 0)
            metric = json.loads((metrics_dir / "validate-model.json").read_text(encoding="utf-8"))
            self.assertEqual(metric["status"], "success")
            self.assertGreaterEqual(metric["elapsed_seconds"], 0)
            self.assertEqual(metric["input"]["records"]["use_cases"], 1)
            self.assertFalse(metric["content_recorded"])
            self.assertNotIn("private test phrase", (metrics_dir / "validate-model.json").read_text(encoding="utf-8"))

    def test_run_manifest_aggregates_per_stage_metrics_and_marks_agent_uninstrumented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metrics_dir = root / "metrics"
            metrics_dir.mkdir()
            (metrics_dir / "plan-concerns.json").write_text(json.dumps({"stage": "plan-concerns", "elapsed_seconds": 0.25}), encoding="utf-8")
            output_dir = root / "assembled"
            output_dir.mkdir()
            manifest_path = output_dir / "run_manifest.json"
            manifest_path.write_text(json.dumps({"project": "test"}), encoding="utf-8")
            attach_metrics_to_run_manifest(output_dir, metrics_dir)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["performance"]["tool_stages"]["plan-concerns"]["elapsed_seconds"], 0.25)
            self.assertEqual(manifest["performance"]["agent_semantic_analysis"], "not_instrumented")
            self.assertEqual(load_stage_metrics(None)["tool_stages"], {})

    def test_cli_assemble_attaches_this_run_metrics_to_manifest(self):
        model = sample_model()
        model["version"] = "6"
        matrix = plan_concern_matrix(model)
        for item in matrix["items"]:
            item.update({"status": "not_applicable", "basis": "基准测试排除该候选。", "evidence_types": ["ssd"]})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_path, matrix_path, findings_path = root / "model.json", root / "matrix.json", root / "findings.json"
            model_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
            matrix_path.write_text(json.dumps(matrix, ensure_ascii=False), encoding="utf-8")
            findings_path.write_text('{"findings": []}', encoding="utf-8")
            metrics_dir = root / "metrics"
            output_dir = root / "assembled"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main([
                    "assemble", "--model", str(model_path), "--concern-matrix", str(matrix_path),
                    "--semantic-findings", str(findings_path), "--output-dir", str(output_dir),
                    "--metrics-dir", str(metrics_dir),
                ])
            self.assertEqual(code, 0)
            manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertIn("assemble", manifest["performance"]["tool_stages"])
            self.assertEqual(manifest["performance"]["tool_stages"]["assemble"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
