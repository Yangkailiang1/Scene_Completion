"""Resolve repository fixtures explicitly and keep test runtime output isolated."""

import sys

import pytest

from tests.support.paths import ROOT

sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def isolated_runtime_directory(tmp_path, monkeypatch):
    """Default model/CLI output must never mutate the user's repository runs/."""
    monkeypatch.chdir(tmp_path)
