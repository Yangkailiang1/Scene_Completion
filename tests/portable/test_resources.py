"""Portable checks use only the files shipped beside the embedded interpreter."""

import json
import os
import subprocess
import sys

from jsonschema import Draft202012Validator

from tests.support.paths import FIXTURES_ROOT, ROOT


def test_portable_resources_and_public_fixtures_are_present():
    for relative in (
        "web/index.html",
        "web/third-party-licenses.txt",
        ".cac/skills/scene-case-analysis/SKILL.md",
        "src/scene_completion/workflow/task_semantics.json",
        "src/scene_completion/models/tokenizer_data/manifest.json",
        "deployment/windows/launcher.py",
    ):
        assert (ROOT / relative).is_file(), relative
    approved = json.loads((FIXTURES_ROOT / "memory_repository/acceptance.json").read_text())
    assert approved["expected_data_rules"]
    for name in ("submitted-bundle", "prepared-snapshot", "refined-existing-snapshot"):
        assert isinstance(
            json.loads((FIXTURES_ROOT / "compat/standalone" / (name + ".json")).read_text()),
            dict,
        )


def test_portable_skill_schema_from_an_unrelated_directory(tmp_path):
    entry = ROOT / ".cac/skills/scene-case-analysis/scripts/case_analysis.py"
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(entry), "schema"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        encoding="utf8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    fixture = json.loads((FIXTURES_ROOT / "compat/standalone/submitted-bundle.json").read_text())
    Draft202012Validator(json.loads(result.stdout)).validate(fixture)
