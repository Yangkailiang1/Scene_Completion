import json
from pathlib import Path

import pytest

from scene_completion.analysis.ssd.core_input import convert, inspect, validate_core
from scene_completion.analysis.ssd.pipeline import build_cases

DATA = Path(__file__).resolve().parents[2] / "datasets/mini-mall"


def test_core_commands_round_trip_and_reject_stale_agent_patch(tmp_path):
    census = inspect(DATA, ["UC-002"])
    assert [case["id"] for case in census["cases"]] == ["UC-002"]
    source = "系统需求_spec.md"
    spec = (DATA / "输入文件" / source).read_text().splitlines()
    line = next(i for i, text in enumerate(spec, 1) if "商家" in text)
    patch = {
        "version": "core-input-overrides-v1",
        "input_hash": census["input_hash"],
        "patches": [
            {
                "file": "architecture.json",
                "id": "U",
                "set": {"kind": "external_actor"},
                "evidence": [
                    {"file": source, "start_line": line, "end_line": line, "quote": spec[line - 1]}
                ],
            }
        ],
    }
    corrections = tmp_path / "corrections.json"
    corrections.write_text(json.dumps(patch), encoding="utf-8")
    output = tmp_path / "core"
    converted = convert(DATA, output, ["UC-002"], corrections)
    assert converted["case_ids"] == ["UC-002"]
    assert validate_core(output)["valid"]
    assert (output / "accepted-overrides.json").is_file()
    bundle = build_cases(output)[0]
    assert bundle["steps"][0]["sender"]["type"] == "human"
    assert all(channel in bundle["channels"] for channel in ("E", "G", "GT"))
    availability = next(
        scene
        for scene in bundle["channels"]["E"]["scenarios"]
        if scene["key"] == "service.base.availability"
    )
    assert {
        ref.get("origin", {}).get("role")
        for ref in availability["source_refs"]
        if ref.get("kind") == "origin"
    } == {"RR", "SR"}
    patch["input_hash"] = "a different input"
    corrections.write_text(json.dumps(patch), encoding="utf-8")
    with pytest.raises(ValueError, match="输入已变化"):
        convert(DATA, tmp_path / "stale", ["UC-002"], corrections)


def test_core_validate_reports_missing_part_in_deep_directory(tmp_path, monkeypatch):
    import errno

    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
    from scene_completion.infrastructure.storage import io_path

    output = tmp_path / ("核心目录" * 25) / ("输出版本" * 30) / "core"
    assert len(str(output)) > 260
    result = convert(DATA / "examples/browse-product", output, profile=COMMAND_OPERATION_PROFILE)
    assert result["case_ids"] == ["UC-BROWSE-01"]
    assert validate_core(output)["valid"]
    part = next(io_path(output).glob("cases/*/source-map.json"))
    stat_path = Path.stat
    is_file = Path.is_file

    def denied(path, *args, **kwargs):
        if path == part:
            raise PermissionError(errno.EACCES, "权限受限")
        return stat_path(path, *args, **kwargs)

    def stat_based_is_file(path):
        if path == part:
            path.stat()
        return is_file(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", denied)
        # Python 3.12 checks file type through Path.stat.
        patch.setattr(Path, "is_file", stat_based_is_file)
        blocked = validate_core(output)
        assert not blocked["valid"]
        assert any(
            row["reason"] == "无法读取核心分件 source-map.json：权限受限"
            for row in blocked["issues"]
        )
    part.unlink()
    rejected = validate_core(output)
    assert not rejected["valid"]
    assert any(
        row["kind"] == "blocking" and row["reason"] == "缺少核心分件：source-map.json"
        for row in rejected["issues"]
    )
