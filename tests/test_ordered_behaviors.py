"""Offline contract tests for the ordered behavior JSON adapter."""

import pytest

from scene_completion.inputs.ordered_behaviors import compile_product


def participant():
    return {
        "U": {"name": "商家全名", "alias": "商家", "kind": "external"},
        "SYS": {"name": "商城系统全名", "alias": "系统", "kind": "system"},
    }


def interaction(ident, sender="U", receiver="SYS", message="提交"):
    return {
        "id": ident,
        "sender": sender,
        "receiver": receiver,
        "message": message,
        "data_ref": None,
        "source_refs": [{"document": "spec", "start_line": 2, "end_line": 2, "quote": message}],
    }


def action(ident="a1", executor="SYS", content="校验请求"):
    return {
        "id": ident,
        "executor": executor,
        "content": content,
        "data_ref": None,
        "source_refs": [],
    }


def scenario(kind="main", order=None, **extra):
    value = {
        "ID": "商品_main_success" if kind == "main" else "商品_异常",
        "scenario_kind": kind,
        "participant": participant(),
        "interaction": [interaction("i1"), interaction("i2", "SYS", "U", "结果")],
        "action": [action()],
        "Order": order
        or [
            {"kind": "interaction", "ref": "i1"},
            {"kind": "action", "ref": "a1"},
            {"kind": "interaction", "ref": "i2"},
        ],
        **extra,
    }
    return value


def compile_s(value, context=None, name="behaviour/IR/main_success.json"):
    return compile_product(
        value, "case-1", name, context or {"case_name": "商品", "layer": "RR", "case_ids": []}, "1"
    )


def sysop(order, interactions=None, actions=None, **extra):
    return {
        "ID": "商品_main_success",
        "source_key": "商品::main_success",
        "participant": participant(),
        "interaction": interactions or [interaction("i1"), interaction("i2", "SYS", "U", "结果")],
        "action": actions or [action()],
        "system_event": [],
        "system_response": [],
        "Order": order,
        **extra,
    }


def compile_ops(operations, context=None):
    value = {"resource": "Product", "use_case": "商品", "operations": operations}
    return compile_product(
        value,
        "case-1",
        "SysOperation.json",
        context or {"case_name": "商品", "layer": "SR", "case_ids": []},
        "1",
    )


def test_aliases_resolve_to_full_participant_names_and_action_is_self_interaction():
    op = sysop(
        [{"kind": "interaction", "ref": "i1"}, {"kind": "action", "ref": "a1"}],
        interactions=[interaction("i1")],
        actions=[action()],
    )
    p = compile_ops({"商品_main_success": op})
    rows = p["fused_template"]["interactions"]
    assert rows[0]["sender"]["name"] == "商家全名"
    assert rows[0]["receiver"]["name"] == "商城系统全名"
    assert rows[1]["sender"]["name"] == rows[1]["receiver"]["name"] == "商城系统全名"
    assert rows[1]["step_kind"] == "action"


def test_exception_scenario_is_retained_without_becoming_positive_normal_input():
    p = compile_s(scenario("exception", guard="invalid"))
    assert p["scenario_document"] is not None
    assert "invalid" in p["scenario_document"]["lines"][0]["text"]
    assert p["normal_document"]["lines"] == []


def test_missing_order_reference_is_rejected():
    with pytest.raises(ValueError, match="Order引用缺少定义"):
        compile_ops({"商品_main_success": sysop([{"kind": "interaction", "ref": "absent"}])})


def test_multiple_main_segments_require_ssd_order_and_follow_it():
    def op(ident):
        return sysop([{"kind": "interaction", "ref": ident}], interactions=[interaction(ident)])

    outer = {
        "resource": "Product",
        "use_case": "商品",
        "scenarios": {"main": {"scenario_kind": "main", "system_operations": ["a", "b"]}},
    }
    ctx = {"case_name": "商品", "layer": "SR", "case_ids": [], "outer_ssd": outer}
    p = compile_ops({"b": op("b"), "a": op("a")}, ctx)
    assert [x["operation"]["name"] for x in p["fused_template"]["interactions"]] == ["提交", "提交"]


def test_json_location_points_to_original_order_entry():
    op = sysop([{"kind": "interaction", "ref": "i1"}], interactions=[interaction("i1")])
    p = compile_ops({"商品_main_success": op})
    assert any(x["json_pointer"].endswith("/interaction/0") for x in p["json_locations"])
    assert all(set(x) == {"line", "json_pointer"} for x in p["json_locations"])


def test_self_interaction_is_warned_and_not_repaired_as_action():
    op = sysop(
        [{"kind": "interaction", "ref": "self"}],
        interactions=[interaction("self", "SYS", "SYS", "自调用")],
    )
    p = compile_ops({"商品_main_success": op})
    assert any("双方相同" in x["reason"] for x in p["pending"])
    assert p["fused_template"]["interactions"] == []
