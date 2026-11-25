"""Resolve repository fixtures explicitly and keep test runtime output isolated."""

import sys

import pytest

from tests.support.paths import ROOT

sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def isolated_runtime_directory(tmp_path, monkeypatch):
    """Default model/CLI output must never mutate the user's repository runs/."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def historical_service_security_registry():
    """Exercise legacy analysis against a taxonomy frozen before the scope change."""
    from scene_completion.domain.concern_registry import default_registry, registry_scope
    from scene_completion.domain.ssd.actor_security import SERVICE_KEYS
    from scene_completion.infrastructure.identity import fingerprint

    value = default_registry()
    for key in SERVICE_KEYS:
        value["definitions"][key]["enabled"] = True
    value["profiles"]["relation"] = sorted(SERVICE_KEYS)
    value["hash"] = fingerprint({k: v for k, v in value.items() if k != "hash"})
    with registry_scope(value):
        yield
