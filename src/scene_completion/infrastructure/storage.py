"""Content identities and atomic JSON IO, including portable Windows long paths."""

from __future__ import annotations

import errno
import json
import ntpath
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from scene_completion.infrastructure.identity import fingerprint as fingerprint


def windows_extended_path(path):
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    absolute = ntpath.abspath(text)
    return "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute


def io_path(path):
    return Path(windows_extended_path(path)) if os.name == "nt" else Path(path)


def logical_path(path):
    """Use the normal spelling for persisted paths, identifiers and messages."""
    text = str(path)
    if os.name == "nt":
        if text.upper().startswith("\\\\?\\UNC\\"):
            return Path("\\\\" + text[8:])
        if text.startswith("\\\\?\\"):
            return Path(text[4:])
    return Path(path)


class CreateIOError(ValueError):
    def __init__(self, stage, root, error):
        filename = logical_path(error.filename2 or error.filename or root)
        relative = filename.relative_to(root) if filename.is_relative_to(root) else None
        winerror = getattr(error, "winerror", None)
        length = len(str(filename).encode("utf-16-le", errors="surrogatepass")) // 2
        if winerror == 206 or error.errno == errno.ENAMETOOLONG:
            reason = "路径或单个目录名超过文件系统限制"
        elif isinstance(error, FileNotFoundError):
            reason = "找不到文件或目录"
        elif isinstance(error, PermissionError):
            reason = "文件访问受限或被占用"
        else:
            reason = "文件系统操作失败"
        self.create_failure = {
            "stage": stage,
            "relative_path": relative.as_posix() if relative is not None else filename.name,
            "path_characters": length,
            "errno": error.errno,
            "winerror": winerror,
        }
        super().__init__(
            f"{stage}失败：{reason}（{self.create_failure['relative_path']}，路径长度 {length}）"
        )


@contextmanager
def create_io(stage, root):
    try:
        yield
    except OSError as error:
        raise CreateIOError(stage, logical_path(root), error) from error


def write_json(path: str | Path, value) -> None:
    target = io_path(path)
    temporary = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Avoid appending a second long identity to an already long filename.
        fd, name = tempfile.mkstemp(prefix=".sc-", suffix=".tmp", dir=target.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, target)
    except OSError as error:
        error.response_diagnostic = {
            "failure_category": "artifact_io_error",
            "operation": "atomic_json_write",
            "path": str(path),
            "errno": error.errno,
            "path_characters": len(str(path)),
            "windows_long_path_support": os.name == "nt",
        }
        raise
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Preserve the original write/replace diagnostic.


def read_json(path: str | Path):
    return json.loads(io_path(path).read_text(encoding="utf-8"))
