"""Versioned persistence for project-scoped results."""

from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from scene_completion.domain.project_scopes.validation import SCOPES
from scene_completion.infrastructure.result_cache import read_snapshot
from scene_completion.infrastructure.storage import write_json
from scene_completion.workflow_core.storage import run_lock

LOCK = RLock()


def root(project, scope=None):
    path = Path(project) / "project_results"
    if scope is not None:
        if scope not in SCOPES:
            raise ValueError("未知项目结果范围")
        path /= scope
    return path


@contextmanager
def locked(project):
    with LOCK, run_lock(root(project)):
        yield


def state(project, scope):
    path = root(project, scope) / "state.json"
    if not path.exists():
        raise ValueError("该范围尚无项目结果")
    return read_snapshot(path)


def exists(project, scope):
    return (root(project, scope) / "state.json").is_file()


def revision(project, scope, number):
    if not str(number).isdigit():
        raise ValueError("无效的项目修订版本")
    path = root(project, scope) / "revisions" / (str(number) + ".json")
    if not path.exists():
        raise ValueError("该项目修订版本不存在")
    return read_snapshot(path)


def store(project, scope, number, snapshot, current):
    write_json(root(project, scope) / "revisions" / (str(number) + ".json"), snapshot)
    write_json(root(project, scope) / "state.json", current)
