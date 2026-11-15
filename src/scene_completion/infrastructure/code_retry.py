"""Explicit code-fault retry identity, separate from semantic guidance and repairs."""

import time
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json


def path(root, key):
    return Path(root) / "code_retries" / (fingerprint(key) + ".json")


def revision(root, key):
    file = path(root, key)
    return read_json(file)["revision"] if file.exists() else 0


def request(root, key, failure):
    value = {
        "node": key,
        "revision": revision(root, key) + 1,
        "at": time.time(),
        "source": "terminal_or_workbench_code_retry",
        "previous_failure": failure,
    }
    file = path(root, key)
    write_json(file.parent / "history" / (fingerprint(value) + ".json"), value)
    write_json(file, value)
    return value
