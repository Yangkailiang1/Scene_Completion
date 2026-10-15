"""Tests for packet-bound comparison citation references."""
from __future__ import annotations

import copy

import pytest

from scene_completion.comparison_evidence_refs import resolve_comparison_evidence


def _scene(sid, role):
    return {
        "scenario_id": sid,
        "exception_object": f"{role}商品",
        "operation": f"{role}创建商品",
        "failure_mechanism": f"{role}库存服务不可用",
        "trigger_condition": f"{role}库存服务请求超时",
        "necessary_conditions": [f"{role}商品必须已提交", f"{role}库存必须可用"],
    }


def _packet(*, aliases=False, checker_conditions=None):
    checker = _scene("C-1", "原")
    generated = _scene("G-1", "新")
    if checker_conditions is not None:
        checker["necessary_conditions"] = checker_conditions
    inputs = {"left": [checker], "right": [generated]} if aliases else {
        "checker": [checker], "generated": [generated]}
    return {"stage": "gap-ambiguity-EG", "input": inputs}


def _ref(side, field, index=None):
    spec = {"side": side, "field": field}
    if index is not None:
        spec["index"] = index
    return {"quote_ref": spec}


def _raw(status="full"):
    return {"pairs": [{
        "checker_scenario_id": "C-1", "generated_scenario_id": "G-1",
        "status": status, "same_object": True, "same_operation": True,
        "same_mechanism": True, "compatible_conditions": True,
        "generated_evidence": _ref("generated", "trigger_condition"),
        "checker_evidence": _ref("checker", "failure_mechanism"),
        "identification_evidence": {
            "exception_object": {"generated": _ref("generated", "exception_object"),
                "checker": _ref("checker", "exception_object")}},
        "causal_facet_evidence": {"generated": _ref("generated", "failure_mechanism"),
            "checker": _ref("checker", "trigger_condition"), "reason": "same cause"},
        "condition_evidence": [{
            "checker_condition": _ref("checker", "necessary_conditions", 0),
            "relation": "supported",
            "generated_quote": _ref("generated", "necessary_conditions", 1),
            "reason": "condition is supported"}],
        "missing_condition_evidence": [{"detail": "原商品必须已提交",
            "checker_field": "necessary_conditions",
            "checker_quote": _ref("checker", "necessary_conditions", 0),
            "generated_gap_reason": "not supplied"}],
        "reason": "semantic decision",
    }]}


def test_resolves_each_supported_quote_to_exact_packet_text_without_mutation():
    packet, raw = _packet(), _raw()
    packet_before, raw_before = copy.deepcopy(packet), copy.deepcopy(raw)

    resolved = resolve_comparison_evidence(packet, raw)
    pair = resolved["pairs"][0]
    assert pair["generated_evidence"] == "新库存服务请求超时"
    assert pair["checker_evidence"] == "原库存服务不可用"
    assert pair["identification_evidence"]["exception_object"] == {
        "generated": "新商品", "checker": "原商品"}
    assert pair["causal_facet_evidence"]["generated"] == "新库存服务不可用"
    assert pair["causal_facet_evidence"]["checker"] == "原库存服务请求超时"
    assert pair["condition_evidence"][0]["checker_condition"] == "原商品必须已提交"
    assert pair["condition_evidence"][0]["generated_quote"] == "新库存必须可用"
    assert pair["missing_condition_evidence"][0]["checker_quote"] == "原商品必须已提交"
    assert pair["same_object"] is True and pair["status"] == "full"
    assert packet == packet_before
    assert raw == raw_before


def test_empty_necessary_conditions_is_valid_but_cannot_be_indexed():
    packet = _packet(checker_conditions=[])
    raw = _raw()
    raw["pairs"][0]["condition_evidence"] = []
    raw["pairs"][0]["missing_condition_evidence"] = []
    resolved = resolve_comparison_evidence(packet, raw)
    assert resolved["pairs"][0]["condition_evidence"] == []
    raw["pairs"][0]["condition_evidence"] = [{
        "checker_condition": _ref("checker", "necessary_conditions", 0)}]
    with pytest.raises(ValueError, match="out of range"):
        resolve_comparison_evidence(packet, raw)


def test_supports_left_right_packet_aliases():
    pair = _raw()["pairs"][0]
    pair["condition_evidence"] = []
    pair["missing_condition_evidence"] = []
    resolved = resolve_comparison_evidence(_packet(aliases=True), {"pairs": [pair]})
    assert resolved["pairs"][0]["generated_evidence"] == "新库存服务请求超时"


@pytest.mark.parametrize("ref", [
    _ref("generated", "trigger_condition"),
    _ref("other", "operation"),
    {"quote_ref": {"side": "checker", "field": "trigger_condition", "index": 0}},
    {"quote_ref": {"side": "checker", "field": "trigger_condition", "extra": "x"}},
])
def test_rejects_invalid_scope_side_or_reference_shape(ref):
    raw = _raw()
    raw["pairs"][0]["checker_evidence"] = ref
    with pytest.raises(ValueError):
        resolve_comparison_evidence(_packet(), raw)


def test_causal_facet_references_are_limited_to_mechanism_or_trigger():
    raw = _raw()
    raw["pairs"][0]["causal_facet_evidence"]["generated"] = _ref(
        "generated", "exception_object")
    with pytest.raises(ValueError, match="outside this evidence scope"):
        resolve_comparison_evidence(_packet(), raw)


def test_condition_and_missing_evidence_require_their_specific_checker_scope():
    raw = _raw()
    raw["pairs"][0]["condition_evidence"][0]["checker_condition"] = _ref(
        "checker", "trigger_condition")
    with pytest.raises(ValueError, match="evidence scope"):
        resolve_comparison_evidence(_packet(), raw)

    raw = _raw()
    raw["pairs"][0]["missing_condition_evidence"][0]["checker_field"] = "trigger_condition"
    with pytest.raises(ValueError, match="checker_field"):
        resolve_comparison_evidence(_packet(), raw)


def test_rejects_unknown_ids_bad_indices_and_references_on_unmatched():
    raw = _raw()
    raw["pairs"][0]["checker_scenario_id"] = "not-in-packet"
    with pytest.raises(ValueError, match="unknown scenario"):
        resolve_comparison_evidence(_packet(), raw)

    raw = _raw()
    raw["pairs"][0]["condition_evidence"][0]["generated_quote"] = _ref(
        "generated", "necessary_conditions", True)
    with pytest.raises(ValueError, match="nonnegative integer"):
        resolve_comparison_evidence(_packet(), raw)

    raw = _raw("unmatched")
    with pytest.raises(ValueError, match="unmatched pair"):
        resolve_comparison_evidence(_packet(), raw)
