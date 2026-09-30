"""Privacy-conscious, optional per-command performance metrics."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


_COUNT_KEYS = ("use_cases", "interactions", "items", "findings", "scenarios", "messages")


def _json_summary(path: Path) -> dict[str, int]:
    """Return structural counts only; never copy payload content into metrics."""
    if path.suffix.lower() != ".json" or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    summary: dict[str, int] = {}
    if isinstance(value, dict):
        for key in _COUNT_KEYS:
            rows = value.get(key)
            if isinstance(rows, list):
                summary[key] = len(rows)
        composition = value.get("system_composition")
        if isinstance(composition, dict) and isinstance(composition.get("nodes"), list):
            summary["nodes"] = len(composition["nodes"])
    elif isinstance(value, list):
        summary["records"] = len(value)
    return summary


def _path_metrics(paths: Iterable[str]) -> dict[str, Any]:
    file_count = 0
    byte_count = 0
    record_counts: dict[str, int] = {}
    for raw in paths:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            try:
                children = list(path.iterdir())
            except OSError:
                continue
            file_count += sum(child.is_file() for child in children)
            byte_count += sum(child.stat().st_size for child in children if child.is_file())
            candidates = [child for child in children if child.is_file() and child.suffix.lower() == ".json"]
        else:
            candidates = [path]
            if path.is_file():
                file_count += 1
                try:
                    byte_count += path.stat().st_size
                except OSError:
                    pass
        for candidate in candidates:
            for key, count in _json_summary(candidate).items():
                record_counts[key] = record_counts.get(key, 0) + count
    return {"files": file_count, "bytes": byte_count, "records": record_counts}


def _argument_values(argv: list[str], option: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(argv):
        if token == option and index + 1 < len(argv):
            values.append(argv[index + 1])
        elif token.startswith(option + "="):
            values.append(token.split("=", 1)[1])
    return values


def metrics_dir_from_argv(argv: list[str]) -> Path | None:
    values = _argument_values(argv, "--metrics-dir")
    return Path(values[-1]).expanduser() if values else None


def write_stage_metric(
    metrics_dir: str | Path,
    stage: str,
    elapsed_seconds: float,
    status: str,
    argv: list[str],
) -> Path:
    """Atomically write one stage file containing timing and aggregate counts."""
    target_dir = Path(metrics_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    outputs: list[str] = []
    input_options = ("--input", "--model", "--fused-ssd", "--ssd-manifest", "--concern-matrix", "--semantic-findings", "--rr", "--sr", "--api-map", "--diagram-manifest", "--config")
    for option in input_options:
        inputs.extend(_argument_values(argv, option))
    for option in ("--output", "--output-dir", "--output-png"):
        outputs.extend(_argument_values(argv, option))
    safe_stage = re.sub(r"[^A-Za-z0-9_.-]+", "_", stage) or "stage"
    target = target_dir / f"{safe_stage}.json"
    record = {
        "stage": stage,
        "status": status,
        "elapsed_seconds": round(max(0.0, float(elapsed_seconds)), 6),
        "input": _path_metrics(inputs),
        "output": _path_metrics(outputs),
        "content_recorded": False,
    }
    fd, temporary_name = tempfile.mkstemp(prefix=f".{safe_stage}.", suffix=".tmp", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        Path(temporary_name).replace(target)
    finally:
        try:
            Path(temporary_name).unlink()
        except FileNotFoundError:
            pass
    return target


def load_stage_metrics(metrics_dir: str | Path | None) -> dict[str, Any]:
    if metrics_dir is None:
        return {"tool_stages": {}, "agent_semantic_analysis": "not_instrumented"}
    root = Path(metrics_dir).expanduser()
    stages: dict[str, Any] = {}
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(record, dict) and record.get("stage"):
                stages[str(record["stage"])] = record
    return {"tool_stages": stages, "agent_semantic_analysis": "not_instrumented"}


def attach_metrics_to_run_manifest(output_dir: str | Path, metrics_dir: str | Path | None) -> None:
    if metrics_dir is None:
        return
    path = Path(output_dir).expanduser() / "run_manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    manifest["performance"] = load_stage_metrics(metrics_dir)
    fd, temporary_name = tempfile.mkstemp(prefix=".run_manifest.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        Path(temporary_name).replace(path)
    finally:
        try:
            Path(temporary_name).unlink()
        except FileNotFoundError:
            pass
