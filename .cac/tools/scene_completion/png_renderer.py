"""Optional, dependency-light SVG to PNG conversion.

The core renderers remain pure Python and always emit SVG.  PNG is produced
through an already-installed local converter when available; no package is
downloaded or required at runtime.
"""

from __future__ import annotations

import shutil
import os
import subprocess
from pathlib import Path
from typing import Any


def find_svg_converter() -> str | None:
    return next(iter(_available_converters()), None)


def _available_converters() -> list[str]:
    names = ("rsvg-convert", "sips", "magick", "inkscape") if os.name == "nt" else ("rsvg-convert", "sips", "magick", "convert", "inkscape")
    return [path for name in names if (path := shutil.which(name))]


def convert_svg_to_png(svg_path: str | Path, png_path: str | Path, *, require: bool = False) -> dict[str, Any]:
    """Convert one generated SVG to PNG without adding a Python dependency."""
    source = Path(svg_path).expanduser().resolve()
    target = Path(png_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    converters = _available_converters()
    if not converters:
        result = {"status": "unavailable", "converter": "", "svg": str(source), "png": "", "error": "未找到 rsvg-convert、sips、ImageMagick 或 Inkscape。"}
        if require:
            raise RuntimeError(result["error"])
        return result

    failures = []
    for converter in converters:
        name = Path(converter).stem.lower()
        if name == "rsvg-convert":
            command = [converter, "-f", "png", "-o", str(target), str(source)]
        elif name == "sips":
            command = [converter, "-s", "format", "png", str(source), "--out", str(target)]
        elif name == "inkscape":
            command = [converter, str(source), "--export-filename", str(target)]
        elif name == "magick":
            command = [converter, str(source), str(target)]
        else:
            command = [converter, str(source), str(target)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(f"{converter}: {exc}")
            continue
        valid_png = target.is_file() and target.stat().st_size > 32 and target.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        if completed.returncode == 0 and valid_png:
            return {"status": "rendered", "converter": converter, "svg": str(source), "png": str(target), "error": "", "attempts": failures}
        failures.append(f"{converter}: {(completed.stderr or completed.stdout or 'PNG输出无效').strip()[:500]}")
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
    error = "；".join(failures) or "所有本地 PNG 转换器均失败。"
    result = {"status": "failed", "converter": "", "svg": str(source), "png": "", "error": error, "attempts": failures}
    if require:
        raise RuntimeError(error)
    return result


__all__ = ["find_svg_converter", "convert_svg_to_png"]
