"""Small broker-only JSON workspace. No tool can name an arbitrary host path."""

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

MAX_BYTES = 2 * 1024 * 1024
MAX_TOTAL = 8 * MAX_BYTES
MAX_FILES = 32


class Workspace:
    def __init__(self, root, materials):
        self.root = Path(root)
        self.root.mkdir(mode=0o700)
        (self.root / "input").mkdir(mode=0o700)
        (self.root / "work").mkdir(mode=0o700)
        self.frozen = {}
        self.events = []
        for name, text in materials.items():
            if "/" in name or "\\" in name or name.startswith("."):
                raise ValueError("invalid frozen filename")
            data = text.encode("utf8")
            (self.root / "input" / name).write_bytes(data)
            self.frozen["input/" + name] = hashlib.sha256(data).hexdigest()
        self._rootfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self._rootfd)

    def _path(self, path, write=False):
        if not isinstance(path, str) or "\\" in path or ":" in path or "\0" in path:
            raise ValueError("only relative input/name or work/name.json paths are allowed")
        parts = PurePosixPath(path).parts
        if (
            len(parts) != 2
            or path != "/".join(parts)
            or any(p in (".", "..") or p.startswith(".") for p in parts)
        ):
            raise ValueError("path traversal, absolute paths and nested paths are denied")
        directory, name = parts
        if directory not in ("input", "work") or write and directory != "work":
            raise ValueError("frozen input is read-only")
        if directory == "input" and path not in self.frozen:
            raise ValueError("unknown frozen material")
        if directory == "work" and not name.endswith(".json"):
            raise ValueError("candidate and intermediate files must be JSON")
        return directory, name

    def _read(self, path):
        directory, name = self._path(path)
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._rootfd)
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dfd)
            try:
                info = os.fstat(fd)
                limit = MAX_BYTES if directory == "work" else 8 * MAX_BYTES
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                    raise ValueError("only bounded ordinary unlinked files can be read")
                with os.fdopen(fd, "rb", closefd=False) as f:
                    data = f.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("file exceeds read limit")
                if directory == "input" and hashlib.sha256(data).hexdigest() != self.frozen[path]:
                    raise ValueError("frozen material identity changed")
                return data.decode("utf8")
            finally:
                os.close(fd)
        finally:
            os.close(dfd)

    def read(self, path: str, offset: int = 0, limit: int = 60000) -> dict:
        """Read frozen task material or this execution's JSON, with bounded text paging."""
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 120000
        ):
            raise ValueError("invalid page")
        text = self._read(path)
        self.events.append({"tool": "workspace_read", "path": path, "offset": offset})
        return {
            "path": path,
            "text": text[offset : offset + limit],
            "total_characters": len(text),
            "next_offset": offset + limit if offset + limit < len(text) else None,
        }

    def write(self, path: str, content: str) -> dict:
        """Create or replace work/name.json. Frozen material is immutable."""
        _, name = self._path(path, write=True)
        json.loads(content)
        data = content.encode("utf8")
        files = list((self.root / "work").iterdir())
        if len(data) > MAX_BYTES or len(files) >= MAX_FILES and not (self.root / path).exists():
            raise ValueError("workspace file limit exceeded")
        if sum(p.lstat().st_size for p in files) + len(data) > MAX_TOTAL:
            raise ValueError("workspace storage limit exceeded")
        dfd = os.open("work", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._rootfd)
        temporary = ".broker-write"
        try:
            try:
                info = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("symlink, hardlink or special file is denied")
            except FileNotFoundError:
                pass
            fd = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd
            )
            try:
                with os.fdopen(fd, "wb", closefd=False) as f:
                    f.write(data)
                    f.flush()
                    os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temporary, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        finally:
            try:
                os.unlink(temporary, dir_fd=dfd)
            except FileNotFoundError:
                pass
            os.close(dfd)
        digest = hashlib.sha256(data).hexdigest()
        self.events.append(
            {"tool": "workspace_write", "path": path, "sha256": digest, "bytes": len(data)}
        )
        return {"path": path, "sha256": digest, "bytes": len(data), "delivered": False}

    def edit(self, path: str, old_text: str, new_text: str) -> dict:
        """Replace exactly one occurrence in a work JSON; resulting JSON must remain valid."""
        self._path(path, write=True)
        text = self._read(path)
        if not old_text or text.count(old_text) != 1:
            raise ValueError("edit must match exactly once")
        result = self.write(path, text.replace(old_text, new_text, 1))
        self.events.append({"tool": "workspace_edit", "path": path, "sha256": result["sha256"]})
        return result

    def tools(self):
        from langchain_core.tools import StructuredTool

        return [
            StructuredTool.from_function(func=fn, name=name)
            for fn, name in (
                (self.read, "workspace_read"),
                (self.write, "workspace_write"),
                (self.edit, "workspace_edit"),
            )
        ]
