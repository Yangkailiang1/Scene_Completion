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
