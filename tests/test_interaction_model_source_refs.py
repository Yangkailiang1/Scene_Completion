"""Focused tests for normal-model source-reference guidance and diagnostics."""
from __future__ import annotations

import copy

import pytest

from scene_completion import interaction_batches as batches
from scene_completion.sources import index_sources


def _source(tmp_path):
    path = tmp_path / "rr.md"
    path.write_text("# Requirements\n## UC-1\n用户提交商品编号。\n", encoding="utf-8")
    index = index_sources([str(path)])
    index["documents"][0]["requirement_layer"] = "RR"
    doc = index["documents"][0]
    chapter = next(row for row in doc["chapters"] if "UC-1" in row["title"])
    section = {key: chapter[key] for key in ("document", "chapter_id", "line_start", "line_end", "heading_path")}
    ref = {"document": doc["document"], "line_start": 3, "line_end": 3}
    return index, section, ref


def _packet(section):
    return {"input": {"sections": [section]}}


def _result(section, ref):
    return {"covered_section_ids": [section["chapter_id"]],
        "components": [], "exchanges": [], "normal_scenarios": [],
        "implementation_references": [], "model_gaps": [], "pending_details": [],
        "use_case_hierarchy": []}


def _walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs":
                yield child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


@pytest.mark.parametrize("field", ["implementation_references", "model_gaps", "pending_details", "use_case_hierarchy"])
def test_empty_top_level_source_refs_report_field_and_item_identity(field, tmp_path):
    index, section, ref = _source(tmp_path)
    result = _result(section, ref)
    item = {"description": "未知恢复行为"} if field != "use_case_hierarchy" else {
        "unit_id": "UNIT-1", "source_id": "UC-1", "name": "用例", "layer": "RR", "parent_ids": []}
    item["source_refs"] = []
    result[field] = [item]
    with pytest.raises(ValueError, match=rf"{field}\[0.*source_refs: source_refs must contain verifiable citations"):
        batches.model_validator(index)(_packet(section), result)


@pytest.mark.parametrize("nested_field", ["contracts", "data_relations"])
def test_empty_nested_source_refs_report_exchange_path_and_nested_index(nested_field, tmp_path, monkeypatch):
    index, section, ref = _source(tmp_path)
    monkeypatch.setattr(batches, "validate_exchange_fields", lambda _exchange: None)
    result = _result(section, ref)
    component = {"component_id": "UI", "name": "UI", "kind": "frontend_ui", "layer": "RR",
        "boundary_role": "ui", "service_types": [], "source_refs": [ref]}
    exchange = {"local_id": "EX-1", "hierarchy_unit_id": "UNIT-1", "requirement_layer": "RR",
        "path_type": "main_success", "from_component_id": "UI", "to_component_id": "UI",
        "operation": "提交", "operation_kinds": ["create"], "source_refs": [ref]}
    if nested_field == "contracts":
        exchange["contracts"] = [{"rule": "账户状态必须有效", "source_refs": []}]
    else:
        exchange["data_relations"] = [{"object": "商品编号", "relation": "reference",
            "evidence_quote": "用户提交商品编号。", "source_refs": []}]
    result["components"] = [component]
    result["exchanges"] = [exchange]
    with pytest.raises(ValueError, match=rf"exchanges\[local_id='EX-1'\]\.{nested_field}\[0\]\.source_refs: source_refs must contain verifiable citations"):
        batches.model_validator(index)(_packet(section), result)


def test_model_packet_prompt_and_contract_require_citations_without_inventing_sources(tmp_path, monkeypatch):
    index, _, _ = _source(tmp_path)
    captured = {}

    def fake_prepare(_directory, stage, payloads, instructions, contract):
        captured.update(stage=stage, payloads=payloads, instructions=instructions, contract=contract)
        return {"stage": stage}

    monkeypatch.setattr(batches, "prepare_packets", fake_prepare)
    batches.model_packets({"use_cases": [{"use_case_id": "UC-1", "use_case_name": "用例", "architecture": {}}]},
        index, tmp_path / "packets")
    prompt = "\n".join(captured["instructions"])
    assert "MUST have nonempty source_refs" in prompt
    assert "Unknown details still need cited evidence" in prompt
    assert "Nested contracts" in prompt and "data_relations" in prompt
    assert "replace every value with the actual filename and integer line numbers" in prompt
    refs = list(_walk(captured["contract"]))
    assert refs and all(ref for ref in refs)
    example = refs[0][0]
    assert example["document"] == "<exact assigned filename>"
    assert example["line_start"] == "<actual integer line>"
