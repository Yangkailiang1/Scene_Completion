"""Filesystem persistence and locking for SSD result snapshots."""

import threading
from contextlib import contextmanager
from pathlib import Path

from scene_completion.infrastructure.result_cache import read_snapshot
from scene_completion.infrastructure.storage import fingerprint, write_json
from scene_completion.workflow_core.storage import run_lock

LOCK = threading.RLock()


def root(project, case_id=None):
    root = Path(project) / "ssd_results"
    return root / fingerprint(str(case_id))[:24] if case_id is not None else root


@contextmanager
def locked(project):
    with LOCK, run_lock(root(project)):
        yield


def state(project, cid):
    path = root(project, cid) / "state.json"
    if not path.exists():
        raise ValueError("该用例尚无 SSD 比较结果")
    return read_snapshot(path)


def exists(project, cid):
    return (root(project, cid) / "state.json").exists()


def revision_path(project, case_id, number):
    return root(project, case_id) / "revisions" / (str(number) + ".json")


def revision(project, case_id, number, *, isolate=True):
    path = revision_path(project, case_id, number)
    if not path.is_file():
        raise ValueError("该修订版本不存在")
    return read_snapshot(path, isolate=isolate)


def store(project, case_id, revision, snapshot, current_state):
    destination = root(project, case_id)
    write_json(destination / "revisions" / (str(revision) + ".json"), snapshot)
    write_json(destination / "state.json", current_state)


def states(project):
    return [read_snapshot(path) for path in sorted(root(project).glob("*/state.json"))]


def _head(path):
    state = read_snapshot(path, isolate=False)
    return {"case": dict(state["case"]), "revision": state["revision"]}


def head(project, case_id):
    path = root(project, case_id) / "state.json"
    if not path.is_file():
        raise ValueError("该用例尚无 SSD 比较结果")
    return _head(path)


def heads(project):
    return [_head(path) for path in sorted(root(project).glob("*/state.json"))]
