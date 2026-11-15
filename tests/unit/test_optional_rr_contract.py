from copy import deepcopy

import pytest

from scene_completion.analysis.ssd.contract_binding import apply_result, prepare, validate_result
from scene_completion.analysis.ssd.pipeline import _kinds, build_cases, rebind_steps
from tests.support.paths import ROOT


def test_methods_and_post_semantics():
    assert _kinds("GET /things") == ["read"]
    assert _kinds("POST /things/search 查询商品") == ["read"]
    assert _kinds("POST /things") == []
    assert _kinds("删除商品", "DELETE") == ["delete"]


def test_no_rr_api_preserves_fields_links_only_selected_request_property():
    b = build_cases(ROOT / "datasets/mini-mall", ["UC-002"])[0]
    rr = next(s for s in b["steps"] if s["layer"] == "RR" and s["direction"] == "request")
    rr["api_id"] = None
    field = next(f for f in rr["data"] if f["name"] == "pageSize")
    field.update(type=None, required=None, constraints=[])
    context, maps = prepare(b)
    sid = next(k for k, v in maps["steps"].items() if v == rr["id"])
    fid = next(k for k, v in maps["fields"].items() if v == field["id"])
    api = next(
        a
        for a in context["apis"]
        if any(
            f["name"] == "pageSize" and f.get("location") == "query" for f in a.get("fields", [])
        )
    )
    old_fields = {f["id"] for f in rr["data"]}
    output = {
        "operations": [],
        "field_links": [
            {
                "step_id": sid,
                "field_id": fid,
                "api_id": api["id"],
                "location": "query",
                "name": "pageSize",
            }
        ],
        "field_definitions": [],
        "pending": [],
    }
    result = apply_result(b, context, maps, output)
    assert rr["api_id"] is None and {f["id"] for f in rr["data"]} == old_fields
    assert field["type"] == "integer" and field["constraints"]
    assert any(
        c["field_id"] == field["id"] and c["key"] == "api.data.range"
        for c in result["channels"]["G"]["concerns"]
    )
    bad = deepcopy(output)
    bad["field_links"][0]["location"] = "response"
    with pytest.raises(ValueError):
        validate_result(bad, context)


def test_edit_api_and_operation_refresh_crud_but_manual_choice_wins():
    original = build_cases(ROOT / "datasets/mini-mall", ["UC-001"])[0]
    changed = deepcopy(original)
    step = changed["steps"][0]
    step["operation"]["name"] = "GET /v1/products 查询商品"
    step["api_id"] = None
    result = rebind_steps(original, changed)
    assert result["steps"][0]["operation"]["kinds"] == ["read"]
    changed["steps"][0]["operation"]["kinds"] = ["delete"]
    result = rebind_steps(original, changed)
    assert result["steps"][0]["operation"]["kinds"] == ["delete"]
    assert result["steps"][0]["operation"]["kinds_source"] == "manual"


@pytest.mark.parametrize("value", ["1-50", 1, True, [1, 50], {"min": 1}, None])
def test_constraint_value_union_keeps_native_json_types(value):
    from scene_completion.models.transport.model_submission import containers

    containers(value, {"type": ["string", "number", "boolean", "array", "object", "null"]})


def test_manual_crud_alias_remains_an_override_after_api_rebind():
    original = build_cases(ROOT / "datasets/mini-mall", ["UC-001"])[0]
    changed = deepcopy(original)
    changed["steps"][0]["operation"]["kinds"] = ["R"]
    changed["steps"][0]["operation"]["name"] = "POST /v1/products 创建商品"
    result = rebind_steps(original, changed)
    assert result["steps"][0]["operation"]["kinds"] == ["read"]
    assert result["steps"][0]["operation"]["kinds_source"] == "manual"
