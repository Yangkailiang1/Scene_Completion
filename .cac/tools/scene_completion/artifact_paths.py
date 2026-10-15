"""Portable relative artifact references without changing evidence contents."""
from pathlib import Path, PurePosixPath, PureWindowsPath


def relative_artifact_path(root, value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('artifact reference must be a nonempty relative path')
    normalized = value.replace('\\', '/')
    parts = PurePosixPath(normalized)
    if parts.is_absolute() or PureWindowsPath(value).drive or '..' in parts.parts:
        raise ValueError('artifact reference must stay below its recorded root')
    base = Path(root).resolve()
    target = (base / Path(*parts.parts)).resolve()
    if not target.is_relative_to(base):
        raise ValueError('artifact reference escapes its recorded root')
    return target
