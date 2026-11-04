"""A web parent importing the package must not hide child startup failures."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    ("infrastructure/project_worker.py", "infrastructure/worker_runtime.py"),
    ("manager/manager_worker.py", "manager/manager_runtime.py"),
)


@pytest.mark.parametrize("entry,runtime", ENTRYPOINTS)
def test_worker_bootstraps_its_own_package_without_site_or_pythonpath(tmp_path, entry, runtime):
    # A minimal relocated package excludes every editable install and dependency
    # from the proof. The entry script is the real shipped source, not a rewrite.
    bundle = tmp_path / "中文 Windows 离线包"
    package = bundle / "app/src/scene_completion"
    child = package / entry
    child.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "src/scene_completion" / entry, child)
    (package / "__init__.py").write_text("", encoding="utf8")
    stub = package / runtime
    stub.parent.mkdir(parents=True, exist_ok=True)
    (stub.parent / "__init__.py").write_text("", encoding="utf8")
    stub.write_text(
        "import json\nfrom pathlib import Path\n"
        "def main():\n"
        " print(json.dumps({'loaded_runtime': str(Path(__file__).resolve())}))\n",
        encoding="utf8",
    )
    elsewhere = tmp_path / "unrelated working directory"
    elsewhere.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(child)],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        encoding="utf8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["loaded_runtime"] == str(stub.resolve())


@pytest.mark.parametrize("entry,runtime", ENTRYPOINTS)
def test_real_worker_runtime_help_in_an_isolated_subprocess(tmp_path, entry, runtime):
    child = ROOT / "src/scene_completion" / entry
    result = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-B", str(child), "--help"],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--root" in result.stdout and "--project" in result.stdout
