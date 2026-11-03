"""Explicit task semantic versions; update only for a changed business contract."""

import json
from functools import lru_cache
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint


@lru_cache(maxsize=1)
def _versions() -> dict:
    return json.loads(Path(__file__).with_name("task_semantics.json").read_text(encoding="utf8"))


def code_version(task: str) -> str:
    return _versions()["tasks"].get(
        task,
        fingerprint({"protocol": _versions()["protocol"], "task": task, "semantic_revision": 1}),
    )


def component_version(name: str) -> str:
    return _versions()["components"][name]
