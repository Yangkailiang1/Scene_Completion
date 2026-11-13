"""Run the portable suite against the exact allow-listed application copy."""

import hashlib
import os
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location

from tests.support.paths import ROOT


def test_application_package_has_independent_tests_and_unchanged_public_fixtures(tmp_path):
    spec = spec_from_file_location("portable_builder", ROOT / "tools/build_windows_bundle.py")
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    application = tmp_path / "中文 Windows 离线包/app"
    builder.copy_application(application)
    assert not (application / "datasets").exists()
    assert not (application / "deployment/experiments").exists()
    assert not (application / "tests/integration").exists()
    assert not (application / "tests/support/workflow.py").exists()
    assert not (application / "pytest.ini").exists()
    for name in builder.PORTABLE_FIXTURES:
        assert (
            hashlib.sha256((application / name).read_bytes()).digest()
            == hashlib.sha256((ROOT / name).read_bytes()).digest()
        )
    elsewhere = tmp_path / "unrelated working directory"
    elsewhere.mkdir()
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(application / "tests/portable"), "-q"],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        encoding="utf8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "skipped" not in result.stdout
