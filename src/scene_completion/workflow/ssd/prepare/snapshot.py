"""Publish immutable core snapshots after all files have been written."""

import shutil
import time
from pathlib import Path
from tempfile import mkdtemp

from scene_completion.infrastructure.storage import fingerprint, io_path, read_json, write_json
from scene_completion.workflow.ssd.input_conversion.core_files import write_core

REQUIRED = (
    "existing-exceptions.json",
    "test-exceptions.json",
    "extension-mapping.json",
    "source-map.json",
)
WINDOWS_TRANSIENT = {5, 32, 33}


def _complete(directory, case_id):
    if not (directory / "architecture.json").is_file():
        return False
    mains = list(directory.glob("cases/*/main-success.json"))
    if len(mains) != 1 or not all((mains[0].parent / name).is_file() for name in REQUIRED):
        return False
    try:
        return read_json(mains[0]).get("case", {}).get("id") == case_id
    except (FileNotFoundError, ValueError, AttributeError):
        return False


def _registered(root, index, identity, case_id):
    try:
        record = read_json(index)
        if record.get("identity") != identity:
            return None
        name = record["directory"]
        if (
            not isinstance(name, str)
            or "/" in name
            or "\\" in name
            or not name.startswith(identity[:24] + "-")
        ):
            return None
        directory = (root / ".snapshots" / name).resolve()
        if directory.parent != (root / ".snapshots").resolve() or not _complete(directory, case_id):
            return None
        for relative, size in record["files"].items():
            file = (directory / relative).resolve()
            if (
                not file.is_relative_to(directory)
                or not file.is_file()
                or file.stat().st_size != size
            ):
                return None
        return directory
    except (FileNotFoundError, ValueError, KeyError, AttributeError, TypeError):
        return None


def verify_core_snapshot(run, bundle):
    """Guard prepared cache hits against missing or incomplete on-disk cores."""
    path = bundle.get("core_snapshot")
    if not isinstance(path, str) or not path:
        raise ValueError("缓存的核心快照缺失或不完整")
    relative = Path(path)
    root = (io_path(run) / "structured-cores").resolve()
    directory = (io_path(run) / relative).resolve()
    if (
        relative.anchor
        or directory == root
        or not directory.is_relative_to(root)
        or not _complete(directory, bundle["case"]["id"])
    ):
        raise ValueError("缓存的核心快照缺失或不完整")


def pin_core(run, inputs, bundle):
    """Return the run-relative directory of a complete, registered snapshot."""
    run = io_path(run).resolve()
    root = run / "structured-cores"
    identity = fingerprint(bundle)
    case_id = bundle["case"]["id"]
    index = root / (identity + ".json")
    directory = None
    phase, path, retries = "read_core_index", index, 0
    try:
        if cached := _registered(root, index, identity, case_id):
            return cached.relative_to(run).as_posix()
        legacy = root / identity[:24]
        phase, path = "read_legacy_core", legacy
        if not legacy.is_symlink() and _complete(legacy, case_id):
            return legacy.relative_to(run).as_posix()

        parent = root / ".snapshots"
        phase, path = "write_core_snapshot", parent
        parent.mkdir(parents=True, exist_ok=True)
        directory = io_path(mkdtemp(prefix=identity[:24] + "-", dir=parent))
        path = directory
        write_core(inputs, directory, [bundle])
        if not _complete(directory, case_id):
            raise OSError("核心快照缺少必需分件")
        files = {
            f.relative_to(directory).as_posix(): f.stat().st_size
            for f in sorted(directory.rglob("*"))
            if f.is_file()
        }
        phase, path = "register_core_snapshot", index
        for delay in (0.1, 0.3, None):
            try:
                write_json(
                    index, {"identity": identity, "directory": directory.name, "files": files}
                )
                break
            except OSError as error:
                if delay is None or getattr(error, "winerror", None) not in WINDOWS_TRANSIENT:
                    raise
                retries += 1
                time.sleep(delay)
        return directory.relative_to(run).as_posix()
    except OSError as error:
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)
        error.response_diagnostic = {
            "failure_category": "artifact_io_error",
            "operation": phase,
            "relative_path": path.relative_to(run).as_posix(),
            "errno": error.errno,
            "winerror": getattr(error, "winerror", None),
            "retries": retries,
        }
        raise
