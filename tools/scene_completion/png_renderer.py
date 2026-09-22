"""Optional, dependency-light SVG to PNG conversion.

The core renderers remain pure Python and always emit SVG.  PNG is produced
through an already-installed local converter when available; no package is
downloaded or required at runtime.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_svg_converter() -> str | None:
    for name in ("rsvg-convert", "magick", "convert", "sips", "inkscape"):
        path = shutil.which(name)
        if path:
            return path
    return None


def convert_svg_to_png(svg_path: str | Path, png_path: str | Path, *, require: bool = False) -> dict[str, Any]:
    """Convert one generated SVG to PNG without adding a Python dependency."""
    source = Path(svg_path).expanduser().resolve()
    target = Path(png_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    converter = find_svg_converter()
    if not converter:
        result = {"status": "unavailable", "converter": "", "svg": str(source), "png": "", "error": "未找到 rsvg-convert、sips、ImageMagick 或 Inkscape。"}
        if require:
            raise RuntimeError(result["error"])
        return result

    name = Path(converter).name
    if name == "rsvg-convert":
        command = [converter, "-f", "png", "-o", str(target), str(source)]
    elif name == "sips":
        command = [converter, "-s", "format", "png", str(source), "--out", str(target)]
    elif name == "inkscape":
        command = [converter, str(source), "--export-filename", str(target)]
    else:
        command = [converter, str(source), str(target)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode or not target.exists():
        error = (completed.stderr or completed.stdout or "PNG 转换失败").strip()[:2000]
        result = {"status": "failed", "converter": converter, "svg": str(source), "png": "", "error": error}
        if require:
            raise RuntimeError(error)
        return result
    return {"status": "rendered", "converter": converter, "svg": str(source), "png": str(target), "error": ""}


__all__ = ["find_svg_converter", "convert_svg_to_png"]
