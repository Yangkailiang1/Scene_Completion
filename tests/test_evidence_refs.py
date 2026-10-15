"""Tests for exact, packet-local evidence quote references."""
from __future__ import annotations

import copy

import pytest

from scene_completion.evidence_refs import expand_result, prepare_packet


def _ref(evidence_id):
    return {"evidence_quote_ref": {"evidence_id": evidence_id}}


def _diagnosis_packet():
    return {"stage": "gap-diagnosis", "input": {
        "allowed_inputs": [{"source": "原文：用户账户必须有效。\n另一个条件。"}],
        "failed_outputs_from_same_channel": ["拒绝输出：不能作为原文依据。"],
    }}


def _graph_packet():
    return {"stage": "gap-graph-check", "input": {
        "use_case_id": "UC-1", "exchanges": [{"exchange_id": "EX-1"}], "nodes": [],
        "sections": [{"document": "需求.md", "chapter_id": "CH-1", "line_start": 4,
            "line_end": 5, "numbered_text": "4: 用户提交申请。\n5: 系统核对账户状态。"}],
    }}


def _reverse_packet():
    return {"stage": "gap-reverse-check-G", "input": {
        "units": [{"unit_id": "U-1", "source_scenario_id": "G-1"},
            {"unit_id": "U-2", "source_scenario_id": "G-2"}],
        "original_scenarios": [
            {"scenario_id": "G-1", "trigger_condition": "账户状态无效时拒绝申请。",
                "failure_mechanism": "服务不可用。", "name": "one"},
            {"scenario_id": "G-2", "trigger_condition": "账户已冻结时停止提交。",
                "failure_mechanism": "服务不可用。", "name": "two"},
        ],
    }}


def _audit_packet():
    return {"stage": "interaction-checker-audit", "input": {
        "use_case_id": "UC-1", "scenarios": [{"scenario_id": "C-1"}],
        "sections": [{"document": "审计原文.md", "chapter_id": "CH-A", "line_start": 9,
            "line_end": 9, "numbered_text": "9: 用户提交后系统核对账户。"}],
    }}


def test_diagnosis_catalog_uses_exact_unicode_original_lines_and_omits_failed_output():
    original = _diagnosis_packet()
    packet = prepare_packet(original)
    rows = packet["input"]["evidence_catalog"]
    assert [row["quote"] for row in rows] == ["原文：用户账户必须有效。", "另一个条件。"]
    assert rows[0]["id"].startswith("EV-")
    assert "拒绝输出" not in " ".join(row["quote"] for row in rows)
    assert "evidence_catalog" not in original["input"]


def test_expands_exact_quote_and_preserves_reference_without_mutating_inputs():
    packet = prepare_packet(_graph_packet())
    entry = packet["input"]["evidence_catalog"][1]
    raw = {"checks": [{"id": "EX-1", "kind": "ssd", "valid": True,
        "source_refs": [{"document": "需求.md", "line_start": 4, "line_end": 5}],
        "evidence_quote_ref": {"evidence_id": entry["id"]}, "reason": "check"}]}
    packet_before, raw_before = copy.deepcopy(packet), copy.deepcopy(raw)

    expanded = expand_result(packet, raw)

    result = expanded["checks"][0]
    assert result["evidence_quote"] == "系统核对账户状态。"
    assert result["evidence_quote_ref"] == {"evidence_id": entry["id"]}
    assert result["valid"] is True
    assert packet == packet_before
    assert raw == raw_before


def test_reverse_review_evidence_is_bound_to_its_own_source_scenario():
    packet = prepare_packet(_reverse_packet())
    ids = {row["scope"]["scenario_id"]: row["id"] for row in packet["input"]["evidence_catalog"]
        if row["scope"]["field"] == "trigger_condition"}
    valid = {"reviews": [{"unit_id": "U-1", "passed": False,
        "evidence_quote_ref": {"evidence_id": ids["G-1"]}}]}
    assert expand_result(packet, valid)["reviews"][0]["evidence_quote"] == "账户状态无效时拒绝申请。"

    borrowed = {"reviews": [{"unit_id": "U-1", "evidence_quote_ref": {"evidence_id": ids["G-2"]}}]}
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, borrowed)


def test_unknown_or_inconsistent_quote_refs_are_rejected():
    packet = prepare_packet(_graph_packet())
    entry = packet["input"]["evidence_catalog"][0]
    row = {"id": "EX-1", "kind": "ssd", "source_refs": [{"document": "需求.md", "line_start": 4, "line_end": 4}],
        "evidence_quote_ref": {"evidence_id": entry["id"]}}
    with pytest.raises(ValueError, match="unknown packet-local evidence ID"):
        expand_result(packet, {"checks": [{**row, "evidence_quote_ref": {"evidence_id": "EV-unknown"}}]})
    with pytest.raises(ValueError, match="does not match"):
        expand_result(packet, {"checks": [{**row, "evidence_quote": "invented", "evidence_quote_ref": row["evidence_quote_ref"]}]})


def test_graph_scope_requires_the_same_packet_citation_ref():
    packet = prepare_packet(_graph_packet())
    entry = packet["input"]["evidence_catalog"][0]
    raw = {"checks": [{"id": "EX-1", "source_refs": [{"document": "别处.md", "line_start": 4, "line_end": 4}],
        "evidence_quote_ref": {"evidence_id": entry["id"]}}]}
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, raw)


def test_source_audit_reference_requires_an_assigned_line_and_own_checker_id():
    packet = prepare_packet(_audit_packet())
    evidence_id = packet["input"]["evidence_catalog"][0]["id"]
    good = {"reviews": [{"scenario_id": "C-1", "source_refs": [
        {"document": "审计原文.md", "line_start": 9, "line_end": 9}],
        "evidence_quote_ref": {"evidence_id": evidence_id}}]}
    assert expand_result(packet, good)["reviews"][0]["evidence_quote"] == "用户提交后系统核对账户。"

    wrong_id = {"reviews": [{"scenario_id": "C-OTHER", "source_refs": good["reviews"][0]["source_refs"],
        "evidence_quote_ref": {"evidence_id": evidence_id}}]}
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, wrong_id)

    wrong_line = {"reviews": [{"scenario_id": "C-1", "source_refs": [
        {"document": "审计原文.md", "line_start": 2, "line_end": 2}],
        "evidence_quote_ref": {"evidence_id": evidence_id}}]}
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, wrong_line)


def test_feature_trait_inherits_only_its_containing_exchange_and_keeps_trait_refs():
    packet = {"stage": "gap-features", "input": {
        "use_case_id": "UC-1", "exchanges": [
            {"exchange_id": "EX-1", "operation_kinds": ["read"], "source_refs": [
                {"document": "需求.md", "line_start": 4, "line_end": 4}]},
            {"exchange_id": "EX-2", "operation_kinds": ["write"], "source_refs": [
                {"document": "需求.md", "line_start": 5, "line_end": 5}]}],
        "sections": [{"document": "需求.md", "chapter_id": "CH-1", "line_start": 4,
            "line_end": 5, "numbered_text": "4: 用户读取商品信息。\n5: 用户更新商品信息。"}],
    }}
    packet = prepare_packet(packet)
    evidence_id = next(row["id"] for row in packet["input"]["evidence_catalog"]
        if row["quote"] == "用户读取商品信息。")
    raw = {"items": [{"exchange_id": "EX-1", "traits": [{"name": "role", "value": "query",
        "evidence_quote_ref": {"evidence_id": evidence_id}, "source_refs": [
            {"document": "需求.md", "line_start": 4, "line_end": 4}]}]}]}
    assert expand_result(packet, raw)["items"][0]["traits"][0]["evidence_quote"] == "用户读取商品信息。"

    outside = copy.deepcopy(raw)
    outside["items"][0]["exchange_id"] = "EX-2"
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, outside)

    nested_claim = copy.deepcopy(raw)
    nested_claim["items"][0]["traits"][0]["exchange_id"] = "EX-2"
    assert expand_result(packet, nested_claim)["items"][0]["traits"][0]["evidence_quote"] == "用户读取商品信息。"
    nested_claim["items"][0]["traits"][0]["evidence_quote_ref"] = {"evidence_id": next(
        row["id"] for row in packet["input"]["evidence_catalog"] if row["quote"] == "用户更新商品信息。")}
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, nested_claim)


def test_graph_reference_accepts_unique_local_id_and_rejects_ambiguous_alias():
    packet = _graph_packet()
    packet["input"]["exchanges"] = [{"exchange_id": "EX-1", "local_id": "local-1"}]
    packet = prepare_packet(packet)
    evidence_id = packet["input"]["evidence_catalog"][0]["id"]
    raw = {"checks": [{"id": "local-1", "kind": "ssd", "valid": True, "reason": "ok",
        "source_refs": [{"document": "需求.md", "line_start": 4, "line_end": 4}],
        "evidence_quote_ref": {"evidence_id": evidence_id}}]}
    assert expand_result(packet, raw)["checks"][0]["evidence_quote"] == "用户提交申请。"

    packet["input"]["exchanges"].append({"exchange_id": "EX-2", "local_id": "local-1"})
    packet = prepare_packet(packet)
    with pytest.raises(ValueError, match="outside this result item's source scope"):
        expand_result(packet, raw)


def test_audit_quote_reference_targets_are_explicit_and_independent():
    packet = {"stage": "interaction-checker-audit", "input": {
        "use_case_id": "UC-1", "scenarios": [{"scenario_id": "C-1"}],
        "sections": [{"document": "审计原文.md", "chapter_id": "CH-A", "line_start": 9,
            "line_end": 10, "numbered_text": "9: 扩展路径\n10: 异常场景：账户被冻结时拒绝操作。"}],
    }}
    packet = prepare_packet(packet)
    evidence_id = next(row["id"] for row in packet["input"]["evidence_catalog"]
        if "账户被冻结" in row["quote"])
    raw = {"omitted_conditions": [{"condition": "账户被冻结", "layer_use_case_id": "UC-1",
        "source_refs": [{"document": "审计原文.md", "line_start": 10, "line_end": 10}],
        "evidence_quote_ref": {"evidence_id": evidence_id},
        "failure_source_refs": [{"document": "审计原文.md", "line_start": 10, "line_end": 10}],
        "failure_evidence_quote_ref": {"evidence_id": evidence_id}}]}
    expanded = expand_result(packet, raw)["omitted_conditions"][0]
    assert expanded["evidence_quote"] == expanded["failure_evidence_quote"] == "异常场景：账户被冻结时拒绝操作。"
    assert expanded["evidence_quote_ref"] == expanded["failure_evidence_quote_ref"]

    wrong_target = copy.deepcopy(raw)
    wrong_target["omitted_conditions"][0]["evidence_quote_ref"] = {"evidence_id": evidence_id}
    wrong_target["omitted_conditions"][0]["evidence_quote"] = "different"
    with pytest.raises(ValueError, match="does not match"):
        expand_result(packet, wrong_target)


def test_catalog_tampering_and_incomplete_reference_objects_fail_closed():
    packet = prepare_packet(_graph_packet())
    altered = copy.deepcopy(packet)
    altered["input"]["evidence_catalog"][0]["quote"] = "不同文本"
    with pytest.raises(ValueError, match="does not match its source inputs"):
        expand_result(altered, {"checks": []})

    row = {"id": "EX-1", "source_refs": [{"document": "需求.md", "line_start": 4, "line_end": 4}],
        "evidence_quote_ref": {"evidence_id": packet["input"]["evidence_catalog"][0]["id"], "extra": "x"}}
    with pytest.raises(ValueError, match="only evidence_id"):
        expand_result(packet, {"checks": [row]})


def test_legacy_diagnosis_catalog_is_left_for_the_existing_dq_validator():
    packet = {"stage": "gap-diagnosis", "input": {
        "allowed_inputs": ["原文条件"],
        "evidence_catalog": [{"id": "DQ-old", "quote": "原文条件"}],
    }}
    raw = {"action": "recheck", "evidence_refs": ["DQ-old"]}
    assert expand_result(packet, raw) == raw
    assert "evidence_catalog_format" not in packet["input"]


def test_expanded_graph_feature_and_audit_packets_pass_their_existing_validators(tmp_path):
    from scene_completion.concern_gap_batches import feature_validator, graph_validator
    from scene_completion.interaction_audit import checker_audit_validator
    from scene_completion.sources import index_sources

    source = tmp_path / "requirements.md"
    source.write_text("# Requirements\n## UC-1\n用户读取商品信息。\n扩展路径\n异常场景：账户被冻结时拒绝操作。\n账户状态必须有效。\n", encoding="utf-8")
    index = index_sources([str(source)])
    index["documents"][0]["requirement_layer"] = "RR"
    document = index["documents"][0]["document"]
    chapter = next(row for row in index["documents"][0]["chapters"] if "UC-1" in row["title"])
    source_ref = {"document": document, "line_start": 3, "line_end": 3}
    section = {"document": document, "chapter_id": chapter["chapter_id"], "line_start": 3,
        "line_end": 3, "numbered_text": "3: 用户读取商品信息。"}

    graph_packet = prepare_packet({"stage": "gap-graph-check", "input": {
        "use_case_id": "UC-1", "exchanges": [{"exchange_id": "EX-1", "local_id": "read"}],
        "nodes": [], "sections": [section]}})
    graph_raw = {"checks": [{"id": "read", "kind": "ssd", "valid": True, "reason": "source",
        "source_refs": [source_ref], **_ref(graph_packet["input"]["evidence_catalog"][0]["id"])}]}
    graph_saved = copy.deepcopy(graph_raw)
    graph_expanded = expand_result(graph_packet, graph_raw)
    assert graph_validator(index)(graph_packet, graph_expanded)[0]["id"] == "EX-1"
    assert graph_raw == graph_saved

    feature_packet = prepare_packet({"stage": "gap-features", "input": {
        "use_case_id": "UC-1", "exchanges": [{"exchange_id": "EX-1", "operation_kinds": ["read"]}],
        "sections": [section]}})
    feature_raw = {"items": [{"exchange_id": "EX-1", "traits": [{"name": "operation_kinds",
        "value": ["read"], "basis": "explicit", "rationale": "input operation",
        "source_refs": [source_ref], **_ref(feature_packet["input"]["evidence_catalog"][0]["id"])}]}]}
    feature_saved = copy.deepcopy(feature_raw)
    feature_expanded = expand_result(feature_packet, feature_raw)
    assert feature_validator(index)(feature_packet, feature_expanded)
    assert feature_raw == feature_saved

    audit_section = {**section, "line_end": 6, "numbered_text":
        "3: 用户读取商品信息。\n4: 扩展路径\n5: 异常场景：账户被冻结时拒绝操作。\n6: 账户状态必须有效。"}
    audit_packet = prepare_packet({"stage": "interaction-checker-audit", "input": {
        "use_case_id": "UC-1", "checker_batch_id": "CB-1", "checker_result_hash": "hash",
        "scenarios": [{"scenario_id": "C-1"}], "sections": [audit_section]}})
    audit_catalog = audit_packet["input"]["evidence_catalog"]
    audit_raw = {"covered_section_ids": [chapter["chapter_id"]], "reviews": [{
        "scenario_id": "C-1", "source_supported": True, "atomic": True,
        "operation_binding_supported": True, "citation_accurate": True,
        **_ref(next(row["id"] for row in audit_catalog if row["quote"] == "用户读取商品信息。")),
        "source_refs": [source_ref], "issues": []}], "omitted_conditions": []}
    audit_raw["omitted_conditions"] = [{"condition": "账户状态无效", "layer_use_case_id": "UC-1",
        "extraction_basis": "explicit_named", "source_refs": [{"document": document, "line_start": 6, "line_end": 6}],
        "evidence_quote_ref": {"evidence_id": next(row["id"] for row in audit_catalog if row["quote"] == "账户状态必须有效。")},
        "failure_source_refs": [{"document": document, "line_start": 5, "line_end": 5}],
        "failure_evidence_quote_ref": {"evidence_id": next(row["id"] for row in audit_catalog if row["quote"] == "异常场景：账户被冻结时拒绝操作。")},
        "contract_source_refs": []}]
    audit_saved = copy.deepcopy(audit_raw)
    audit_expanded = expand_result(audit_packet, audit_raw)
    assert checker_audit_validator(index)(audit_packet, audit_expanded)[0]["passed"] is False
    assert audit_raw == audit_saved
