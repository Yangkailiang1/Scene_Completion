"""Persist task state and artifacts in the existing run directory format."""

from contextlib import contextmanager
from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json


@contextmanager
def run_lock(root):
    import os

    path = Path(root) / ".workflow.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as f:
        if not path.stat().st_size:
            f.write(b"0")
            f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as e:
                raise ValueError("run already active") from e
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                raise ValueError("run already active") from e
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


class TaskStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "workflow_tasks.json"
        self.state = read_json(self.path) if self.path.exists() else {"tasks": {}, "events": []}
        self.pause_file = self.root / "pause_requested.json"

    def save(self):
        write_json(self.path, self.state)

    def load_output(self, record):
        value = read_json(self.root / record["output_file"])
        if fingerprint(value) != record["output_hash"]:
            raise ValueError("cache content altered")
        return value

    def save_output(self, key, identity, value):
        file = "task_outputs/" + fingerprint([key, identity, value]) + ".json"
        write_json(self.root / file, value)
        return file
