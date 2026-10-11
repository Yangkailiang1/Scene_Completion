"""Portable decomposition and message binding, not shopping-specific numbering."""
import copy

import pytest

from scene_completion.interaction_hierarchy import validate_hierarchy, bind_exchanges
from scene_completion.interaction_protocol import build_ssd, route_mounts
from scene_completion.interaction_batches import source_sections, model_validator, checker_validator, pair_validator
from scene_completion.interaction_reports import write_diagrams
from scene_completion.sources import index_sources
from scene_completion.interaction_metrics import compare
from scene_completion.interaction_cli import architecture_proposals, merge_model
from tests.test_interaction_protocol import model, reference, scene, pair


def units(refs):
    output = [{"unit_id": "r", "source_id": "R-7", "name": "RR", "layer": "RR", "parent_ids": [], "source_refs": refs}]
    for s in range(2):
        sid = f"s{s}"
        output.append({"unit_id": sid, "source_id": f"SR-{s+40}", "name": "SR", "layer": "SR", "parent_ids": ["r"], "source_refs": refs})
        for a in range(2):
            aid = f"{sid}-a{a}"
            output.append({"unit_id": aid, "source_id": aid, "name": "AR", "layer": "AR", "parent_ids": [sid], "source_refs": refs})
            for i in range(2):
                iid = f"{aid}-i{i}"
                output.append({"unit_id": iid, "source_id": iid, "name": "interface", "layer": "IMPLEMENTATION", "parent_ids": [aid], "source_refs": refs})
    return output


def test_multiple_units_at_every_level_preserve_traceability(tmp_path):
    rr = tmp_path / "rr.md"
    rr.write_text("# RR\n## UC-1\n查看商品\n", encoding="utf-8")
    index = index_sources([str(rr)])
    value = model(index)
    uc = value["use_cases"][0]
    uc["use_case_hierarchy"] = units(reference(index))
    for e in uc["exchanges"]:
        e["hierarchy_unit_id"] = "r" if e["requirement_layer"] == "RR" else "s1" if e["local_id"] == "sr3" else "s0"
    ssd = build_ssd(value)
    assert len(ssd["use_case_hierarchies"][0]["units"]) == 15
    assert {e["layer_use_case_id"] for e in ssd["exchanges"] if e["requirement_layer"] == "SR"} == {"SR-40", "SR-41"}
    mounts = route_mounts(ssd)
    assert all(m["requirement_layer"] in {"RR", "SR"} for m in mounts)
    write_diagrams(tmp_path / "graphs", ssd, mounts)
    text = (tmp_path / "graphs/use_case_decomposition.mmd").read_text(encoding="utf-8")
    assert text.count("IMPLEMENTATION:") == 8 and text.count("AR:") == 4


@pytest.mark.parametrize("change", ["jump", "unknown", "cycle", "duplicate_source"])
def test_invalid_decomposition_never_enters_generation(change):
    value = units([{"document": "rr.md", "line_start": 1, "line_end": 1}])
    if change == "jump":
        value[2]["parent_ids"] = ["r"]
    elif change == "unknown":
        value[1]["parent_ids"] = ["unknown"]
    elif change == "cycle":
        value[0]["parent_ids"] = [value[-1]["unit_id"]]
    else:
        value.append({**value[1], "unit_id": "copy"})
    with pytest.raises(ValueError):
        validate_hierarchy(value)


def test_message_parent_cannot_disagree_with_decomposition():
    value = units([{"document": "rr.md", "line_start": 1, "line_end": 1}])
    value.append({**value[0], "unit_id": "other-r", "source_id": "R-8"})
    exchanges = [{"local_id": "rr", "requirement_layer": "RR", "hierarchy_unit_id": "other-r"},
        {"local_id": "sr", "requirement_layer": "SR", "hierarchy_unit_id": "s0", "parent_rr_local_id": "rr"}]
    with pytest.raises(ValueError, match="decomposition"):
        bind_exchanges(value, exchanges)
    value[1]["parent_ids"].append("other-r")
    assert bind_exchanges(value, exchanges)[1]["layer_use_case_id"] == "SR-40"


def test_different_source_numbering_and_multiple_sr_sections(tmp_path):
    rr, sr = tmp_path / "rr.md", tmp_path / "sr.md"
    rr.write_text("# RR\n## R-7\n正常操作\n", encoding="utf-8")
    sr.write_text("# SR\n## SR-40\nAPI-1\n## SR-41\nAPI-10\n", encoding="utf-8")
    index = index_sources([str(rr), str(sr)])
    for document, layer in zip(index["documents"], ("RR", "SR")):
        document["requirement_layer"] = layer
    uc = {"use_case_id": "business", "source_use_case_ids": {"RR": ["R-7"], "SR": ["SR-40", "SR-41"]},
        "architecture": {"sr": [{"abstract_api_id": "API-1"}]}}
    sections = source_sections(index, uc, True)
    assert {s["title"] for s in sections} == {"R-7", "SR-40", "SR-41"}
    # Removing the second independent unit does not accidentally match API-10.
    uc["source_use_case_ids"]["SR"] = ["SR-40"]
    assert "SR-41" not in {s["title"] for s in source_sections(index, uc, True)}


def test_full_match_cannot_claim_missing_condition_details():
    decision = pair("C", "G")
    decision["missing_condition_details"] = ["指定版本尚未识别"]
    with pytest.raises(ValueError, match="full identification"):
        pair_validator({"input": {"generated": [scene("G")], "checker": [scene("C")]}}, {"pairs": [decision]})


def test_two_sr_use_cases_do_not_cover_each_other(tmp_path):
    g, c = scene("G", "SR"), scene("C", "SR")
    g["layer_use_case_id"], c["layer_use_case_id"] = "SR-40", "SR-41"
    assert compare([g], [c], [])["layers"]["SR"]["overall"]["miss_rate"] == 1
    with pytest.raises(ValueError, match="unrelated"):
        pair_validator({"input": {"generated": [g], "checker": [c]}}, {"pairs": [pair("C", "G")]})
    # Tests can state a business UC rather than a numbered SR unit; that scope
    # is only allowed in the explicit adoption stage, never formal coverage.
    packet = {"stage": "interaction-adoption", "input": {"comparison_scope": "business_use_case", "generated": [g], "checker": [c], "concern_units": {"G": ["api.data.format"], "C": ["api.data.format"]}}}
    assert pair_validator(packet, {"pairs": [pair("C", "G")]})
    packet["stage"] = "interaction-matching"
    with pytest.raises(ValueError, match="reserved"):
        pair_validator(packet, {"pairs": [pair("C", "G")]})


@pytest.mark.parametrize("field", ["failure_conditions", "exception_scenarios", "generation_constraints", "constraints", "unrecognized_candidate_list"])
def test_nested_bypass_cannot_flow_into_ssd(tmp_path, field):
    path = tmp_path / "rr.md"
    path.write_text("# RR\n## UC-1\n查看商品\n", encoding="utf-8")
    value = model(index_sources([str(path)]))
    value["use_cases"][0]["exchanges"][1][field] = [{"trigger": "直接复制异常"}]
    with pytest.raises(ValueError, match="forbidden|unknown"):
        build_ssd(value)


def test_multiple_sr_hints_pass_architecture_gate_shape():
    base = {"use_cases": [{"architecture": {"sr": [{"service_name": "A"}, {"service_name": "B"}]}}]}
    model_value = {"nodes": [{"node_id": "A", "name": "A", "kind": "internal_service", "layer": "SR", "source_refs": []},
        {"node_id": "B", "name": "B", "kind": "internal_service", "layer": "SR", "source_refs": []}], "use_cases": []}
    assert architecture_proposals(model_value, base) == []


def test_necessary_condition_evidence_is_required_and_not_response():
    g, c = scene("G"), scene("C")
    c["necessary_conditions"] = ["指定版本"]
    packet = {"input": {"generated": [g], "checker": [c]}}
    decision = pair("C", "G")
    with pytest.raises(ValueError, match="every checker necessary"):
        pair_validator(packet, {"pairs": [decision]})
    decision["condition_evidence"] = [{"checker_condition": "指定版本", "relation": "supported", "generated_quote": "HTTP 400", "reason": "错误码"}]
    with pytest.raises(ValueError, match="quote generated identification"):
        pair_validator(packet, {"pairs": [decision]})
    decision.update(status="partial", missing_condition_details=["指定版本"])
    decision["missing_condition_evidence"] = [{"detail": "指定版本", "checker_field": "necessary_conditions", "checker_quote": "指定版本", "generated_gap_reason": "生成条件未识别版本"}]
    decision["condition_evidence"][0].update(relation="missing", generated_quote="", reason="生成条件尚未识别该版本约束")
    assert pair_validator(packet, {"pairs": [decision]})


def test_partial_cannot_invent_missing_response_or_repeat_present_condition():
    g, c = scene("G"), scene("C")
    packet = {"input": {"generated": [g], "checker": [c]}}
    decision = pair("C", "G", "partial")
    decision["missing_condition_details"] = ["缺少恢复步骤"]
    with pytest.raises(ValueError, match="original checker condition evidence"):
        pair_validator(packet, {"pairs": [decision]})
    decision["missing_condition_evidence"] = [{"detail": "缺少恢复步骤", "checker_field": "trigger_condition", "checker_quote": c["trigger_condition"], "generated_gap_reason": "假定缺口"}]
    with pytest.raises(ValueError, match="absent from generated"):
        pair_validator(packet, {"pairs": [decision]})


def test_confirmed_mapping_is_read_but_old_mapping_is_not(tmp_path):
    path = tmp_path / "sr.md"
    path.write_text("# SR\n## 已确认层级\n### UC-1\n实际接口\n## V5 历史映射\n### UC-1\n旧接口\n", encoding="utf-8")
    index = index_sources([str(path)])
    index["documents"][0]["requirement_layer"] = "SR"
    sections = source_sections(index, {"use_case_id": "UC-1"})
    assert len(sections) == 1 and "实际接口" in sections[0]["numbered_text"]
    assert "旧接口" not in sections[0]["numbered_text"]


def test_checker_cannot_borrow_identifier_from_other_supplied_unit(tmp_path):
    from scene_completion.interaction_protocol import PROTOCOL
    path = tmp_path / "sr.md"
    path.write_text("# SR\n## SR-40\n查询异常\n## SR-41\n删除异常\n", encoding="utf-8")
    index = index_sources([str(path)])
    index["documents"][0]["requirement_layer"] = "SR"
    sections = index["documents"][0]["chapters"][1:]
    packet = {"input": {"protocol": PROTOCOL, "sections": sections, "requirement_layer": "SR", "use_case_id": "UC-1"}}
    value = {**scene("C", "SR"), "layer_use_case_id": "SR-41", "source_refs": [{"document": "sr.md", "line_start": 3, "line_end": 3}]}
    value.update(extraction_basis="explicit_named", failure_source_refs=value["source_refs"], contract_source_refs=[])
    output = {"covered_section_ids": [s["chapter_id"] for s in sections], "scenarios": [value]}
    with pytest.raises(ValueError, match="original identifier"):
        checker_validator(index)(packet, output)
    value["layer_use_case_id"] = "SR-40"
    assert checker_validator(index)(packet, output)


def test_production_model_accepts_same_name_sr_ar_roles_and_multiple_sr_units(tmp_path):
    rr, sr = tmp_path / "rr.md", tmp_path / "sr.md"
    rr.write_text("# RR\n## R-7\n顾客查看商品\n", encoding="utf-8")
    sr.write_text("# SR\n## S-40\nShared 服务查询数据库 DB\nAR Shared 实现\n## S-41\nShared 服务过滤商品\n", encoding="utf-8")
    index = index_sources([str(rr), str(sr)])
    for document, layer in zip(index["documents"], ("RR", "SR")):
        document["requirement_layer"] = layer
    base_uc = {"use_case_id": "business", "use_case_name": "浏览", "source_use_case_ids": {"RR": ["R-7"], "SR": ["S-40", "S-41"]}}
    sections = source_sections(index, base_uc)
    def refs(document, start, end=None):
        return [{"document": document, "line_start": start, "line_end": end or start}]
    rrefs, srefs, s2refs = refs("rr.md", 2, 3), refs("sr.md", 2, 4), refs("sr.md", 5, 6)
    output = {"covered_section_ids": [s["chapter_id"] for s in sections], "components": [
        {"component_id": "human", "name": "顾客", "kind": "human_actor", "layer": "RR", "source_refs": rrefs},
        {"component_id": "ui", "name": "逻辑 UI", "kind": "frontend_ui", "layer": "RR", "boundary_role": "ui", "source_refs": rrefs},
        {"component_id": "sr", "name": "Shared", "kind": "internal_service", "layer": "SR", "source_refs": srefs},
        {"component_id": "ar", "name": "Shared", "kind": "internal_service", "layer": "AR", "source_refs": srefs}],
        "use_case_hierarchy": [
            {"unit_id": "r", "source_id": "R-7", "name": "查看", "layer": "RR", "parent_ids": [], "source_refs": rrefs},
            {"unit_id": "s", "source_id": "S-40", "name": "查询", "layer": "SR", "parent_ids": ["r"], "source_refs": srefs},
            {"unit_id": "s2", "source_id": "S-41", "name": "过滤", "layer": "SR", "parent_ids": ["r"], "source_refs": s2refs}],
        "exchanges": [
            {"local_id": "r1", "requirement_layer": "RR", "hierarchy_unit_id": "r", "from_component_id": "human", "to_component_id": "ui", "operation": "查看商品", "path_type": "main_success", "source_refs": rrefs},
            {"local_id": "s1", "requirement_layer": "SR", "hierarchy_unit_id": "s", "parent_rr_local_id": "r1", "from_component_id": "ui", "to_component_id": "sr", "operation": "查询", "path_type": "main_success", "source_refs": srefs},
            {"local_id": "s2", "requirement_layer": "SR", "hierarchy_unit_id": "s2", "parent_rr_local_id": "r1", "from_component_id": "ui", "to_component_id": "sr", "operation": "过滤", "path_type": "alternative", "source_refs": s2refs}],
        "normal_scenarios": [{"requirement_layer": "RR", "hierarchy_unit_id": "r", "scenario_type": "main_success", "name": "查看", "source_refs": rrefs}],
        "implementation_references": [], "pending_details": [{"description": "实现接口待补充", "source_refs": srefs}], "model_gaps": []}
    packet = {"input": {**base_uc, "sections": sections}}
    for exchange, kinds in zip(output["exchanges"], (["read"], ["read"], ["read"])):
        exchange["operation_kinds"] = kinds
    validated = model_validator(index)(packet, output)
    for field in ("request_contracts", "response_contracts"):
        invalid = copy.deepcopy(output)
        invalid["exchanges"][1][field] = [{"rule": "合法字段", "source_refs": refs("sr.md", 1)}]
        with pytest.raises(ValueError, match="assigned"):
            model_validator(index)(packet, invalid)
    value = merge_model(validated, {"use_cases": [base_uc]}, index)
    assert len([n for n in value["nodes"] if n["name"] == "Shared"]) == 2
    ssd = build_ssd(value)
    assert {e["layer_use_case_id"] for e in ssd["exchanges"] if e["requirement_layer"] == "SR"} == {"S-40", "S-41"}
    assert not value["model_gaps"] and value["use_cases"][0]["pending_details"]
    # Preserve an existing facade when its physical ID was local to extraction.
    output["components"][2].update(service_role="resource_service", physical_resource_id="db")
    output["components"].append({"component_id": "db", "name": "DB", "kind": "internal_database", "layer": "AR", "source_refs": srefs})
    value = merge_model(model_validator(index)(packet, output), {"use_cases": [base_uc]}, index)
    ssd = build_ssd(value)
    assert len(ssd["resource_service_mappings"]) == 1
    facade = next(n for n in ssd["nodes"] if n["node_id"] == ssd["resource_service_mappings"][0]["resource_service_id"])
    assert facade["name"] == "Shared"
