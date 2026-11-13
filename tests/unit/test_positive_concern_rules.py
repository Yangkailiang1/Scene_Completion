"""Approved deterministic G rules must not depend on a model remembering them."""

from copy import deepcopy

import pytest

from scene_completion.analysis.concerns.concern_hierarchy import resolve_matches
from scene_completion.analysis.matching.concern_alignment import definite, recognize
from scene_completion.analysis.scenarios.exception_scopes import validate_scope
from scene_completion.domain.contracts import validate
from tests.support.workflow import R, memory_inputs, parameter


def inputs():
    value = memory_inputs()
    value["enriched-interactions"]["interactions"] = value["sr-ssd"]["interactions"]
    return value


def test_human_mandatory_checks_even_with_no_model_observations_but_not_in_E_GT():
    x = inputs()
    g = resolve_matches(x, [])
    assert {m["concern_key"] for m in definite(g).values()} == {
        "human.authentication",
        "human.authorization",
    }
    assert all(
        m["identification"] == "framework_policy" and "用户确认" in m["basis"] for m in g["matches"]
    )
    assert recognize(x, {"matches": []}, inverse=True)["matches"] == []
    again = resolve_matches(x, g["matches"] * 2)
    assert len(definite(again)) == 2
    validate("concern-match", again)


def test_external_service_availability_not_local_action_return_or_internal():
    x = inputs()
    i = x["sr-ssd"]["interactions"][0]
    i["sender"].update(name="Admin", position="内部服务")
    i["receiver"].update(name="Catalog", position="外部服务")
    assert {m["concern_key"] for m in definite(resolve_matches(x, [])).values()} == {
        "service.base.availability"
    }
    for change in ("internal", "self", "return"):
        y = deepcopy(x)
        row = y["sr-ssd"]["interactions"][0]
        if change == "internal":
            row["receiver"]["position"] = "内部服务"
        elif change == "self":
            row["sender"] = deepcopy(row["receiver"])
            row["step_kind"] = "action"
        else:
            row["direction"] = "return"
        assert not definite(resolve_matches(y, []))


def test_publish_existing_target_uses_explicit_local_CRUD_check_not_url_spelling():
    x = inputs()
    i = x["sr-ssd"]["interactions"][0]
    i["sender"] = deepcopy(i["receiver"])
    i.update(step_kind="action", api_id=None)
    i["operation"].update(
        name="原子核对商品归属、存在性、状态和版本后发布", kinds=["publish", "update"]
    )
    x["business-crud"] = {
        "rows": [{"interaction_id": "req", "operation": "update", "entity_id": "Product"}]
    }
    out = resolve_matches(x, [])
    matches = list(definite(out).values())
    assert len(matches) == 1
    assert matches[0]["concern_key"] == "service.crud.update.resource_existence"
    assert matches[0]["interaction_id"] == "req"
    i["operation"]["name"] = "POST /ms/v1/products/{productId}/publish"
    assert not definite(resolve_matches(x, []))  # A URL alone is not a business rule.


def test_entity_cross_field_requirement_respects_actual_case_and_operation():
    x = inputs()
    i = x["sr-ssd"]["interactions"][0]
    i["sender"].update(name="Platform", position="内部服务")
    i["receiver"].update(name="Admin", position="内部服务")
    i["operation"]["kinds"] = ["create"]
    x["business-crud"] = {
        "rows": [{"interaction_id": "req", "operation": "create", "entity_id": "Product"}]
    }
    x["api-parameters"]["apis"][0]["parameters"] = [
        parameter("price", "body"),
        parameter("productType", "body"),
    ]
    x["business-entities"] = {
        "entities": [
            {
                "id": "Product",
                "business_rules": [],
                "attributes": [
                    {
                        "name": "price",
                        "data_type": "number",
                        "case_ids": ["UC-1"],
                        "operation": "create",
                        "source_refs": R,
                        "constraints": [
                            {
                                "kind": "other",
                                "status": "explicit",
                                "value": "productType为SERVICE时price必须大于等于1",
                                "source_refs": R,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    x["use-case-align"] = {"groups": [{"id": i["case_id"], "rr_ids": ["UC-1"], "sr_ids": []}]}
    from scene_completion.inputs.structured.colleague_formats import scoped_entities

    original = deepcopy(x["business-entities"])
    x["business-entities"] = scoped_entities(original, ["UC-1"])
    assert "service.business_attribute_constraint" in {
        m["concern_key"] for m in definite(resolve_matches(x, [])).values()
    }
    original["entities"][0]["attributes"][0]["case_ids"] = ["other-case"]
    x["business-entities"] = scoped_entities(original, ["UC-1"])
    assert not definite(resolve_matches(x, []))


def test_local_existence_check_uses_unique_delegated_business_effect_not_missing_action_CRUD():
    x = inputs()
    call = x["sr-ssd"]["interactions"][0]
    call["sender"].update(name="Admin", position="内部服务")
    call["receiver"].update(name="Database", position="外部服务")
    local = deepcopy(call)
    local.update(id="check", api_id=None, step_kind="action")
    local["sender"] = deepcopy(local["receiver"])
    local["operation"]["name"] = "数据库原子核对商品存在性后发布"
    x["sr-ssd"]["interactions"].append(local)
    x["business-crud"] = {
        "rows": [{"interaction_id": "req", "operation": "update", "entity_id": "Product"}]
    }
    matches = list(definite(resolve_matches(x, [])).values())
    existence = [m for m in matches if m["concern_key"].endswith("resource_existence")]
    assert len(existence) == 1 and existence[0]["interaction_id"] == "check"
    assert existence[0]["concern_key"] == "service.crud.update.resource_existence"
    x["business-crud"]["rows"].append(
        {"interaction_id": "req", "operation": "delete", "entity_id": "Product"}
    )
    assert not [
        m
        for m in definite(resolve_matches(x, [])).values()
        if m["concern_key"].endswith("resource_existence")
    ]


def test_global_idempotency_cannot_be_accepted_or_counted_on_an_interaction():
    x = inputs()
    row = {
        "interaction_id": "req",
        "target": "receiver",
        "object": "Platform",
        "concern_key": "service.crud.update.idempotency",
        "basis": "同键不同内容",
        "source_refs": R,
    }
    for inverse in (False, True):
        result = recognize(x, {"matches": [row]}, inverse=inverse)
        assert not result["matches"]
        assert "全局" in result["excluded"][0]["reason"]
        validate("test-concerns" if inverse else "concern-match", result)
    packet = {
        "source-records": [{"id": "T"}],
        "entity-index": {"entities": [{"id": "Product"}]},
        "case-catalogue": [{"id": "UC"}],
    }
    unit = {
        "source_id": "T",
        "trigger": "同键不同内容",
        "scope": "interaction",
        "global_kind": None,
        "entity_ids": ["Product"],
        "related_cases": ["UC"],
        "reason": "原测试",
    }
    with pytest.raises(ValueError, match="global C/U/D"):
        validate_scope({"units": [unit]}, packet)
    unit.update(scope="global", global_kind="idempotency")
    validate_scope({"units": [unit]}, packet)
    unit.update(scope="interaction", global_kind=None, trigger="商品名称重复")
    validate_scope({"units": [unit]}, packet)


def test_explicit_isolation_is_not_replaced_by_a_plain_enum_or_response_requirement():
    x = inputs()
    i = x["sr-ssd"]["interactions"][0]
    i["sender"].update(name="Platform", position="内部服务")
    i["receiver"].update(name="Admin", position="内部服务")
    p = parameter("x-service-id", "header", True, "string", [("enum", ["platform"])])
    x["api-parameters"]["apis"][0]["parameters"] = [p]
    assert not definite(resolve_matches(x, []))
    p["constraints"].append(
        {
            "kind": "other",
            "status": "explicit",
            "value": "不得以其他service-id访问本服务的数据",
            "source_refs": R,
        }
    )
    assert {m["concern_key"] for m in definite(resolve_matches(x, [])).values()} == {
        "service_relation.data_isolation"
    }
    p["location"] = "response"
    assert not definite(resolve_matches(x, []))


def test_policy_resolves_same_binding_pending_without_hiding_other_pending_fields():
    x = inputs()
    old = {
        "interaction_id": "req",
        "target": "sender",
        "object": "开发者",
        "concern_key": "human.authentication",
        "basis": "没有明示机制",
        "concrete_rule": None,
        "source_refs": R,
    }
    result = resolve_matches(x, [old])
    assert len([m for m in result["matches"] if m["concern_key"] == "human.authentication"]) == 1
    assert not result["pending"]


def test_inverse_resource_check_uses_own_explicit_step_and_positive_CRUD_family():
    x = inputs()
    request = x["sr-ssd"]["interactions"][0]
    request["sender"].update(name="Platform", position="内部服务")
    request["receiver"].update(name="Admin", position="内部服务")
    local = deepcopy(request)
    local.update(id="S4", step_kind="action", api_id=None)
    local["sender"].update(name="Database", position="外部服务")
    local["receiver"] = deepcopy(local["sender"])
    local["operation"].update(name="S4. 数据库核对商品存在性后更新", kinds=["update"])
    x["sr-ssd"]["interactions"].append(local)
    own = [{**R[0], "source_id": "test", "quote": "指定productId不存在，失败于步骤S4。"}]
    x["test-documents"] = [
        {
            "source_id": "test",
            "name": "test.json",
            "channel": "test",
            "lines": [{"number": 1, "text": own[0]["quote"]}],
        }
    ]
    raw = {
        "interaction_id": "req",
        "target": "receiver",
        "object": "Admin",
        "concern_key": "service.query_retrieval.resource_existence",
        "basis": "独立测试",
        "source_refs": own,
        "concrete_rule": None,
    }
    result = recognize(x, {"matches": [raw]}, inverse=True)
    item = next(iter(definite(result).values()))
    assert (item["interaction_id"], item["object"], item["concern_key"]) == (
        "S4",
        "Database",
        "service.crud.update.resource_existence",
    )
    assert item["classification_origin"] == "service.query_retrieval.resource_existence"


def test_inverse_isolation_needs_own_failure_and_explicit_access_boundary_not_enum():
    x = inputs()
    i = x["sr-ssd"]["interactions"][0]
    i["sender"].update(name="Platform", position="内部服务")
    own = [{**R[0], "source_id": "test", "quote": "x-service-id=other，访问本服务数据被拒绝"}]
    x["test-documents"] = [
        {
            "source_id": "test",
            "name": "test.json",
            "channel": "test",
            "lines": [{"number": 1, "text": own[0]["quote"]}],
        }
    ]
    raw = {
        "interaction_id": "req",
        "target": "operation",
        "object": i["operation"]["name"],
        "concern_key": "service_relation.authorization",
        "basis": "本条独立异常",
        "source_refs": own,
        "concrete_rule": None,
    }
    first = recognize(x, {"matches": [raw]}, inverse=True)
    assert first["matches"][0]["concern_key"] == "service_relation.authorization"
    raw["source_refs"] += [{**R[0], "quote": "不得以其他service-id访问本服务的数据"}]
    second = recognize(x, {"matches": [raw]}, inverse=True)
    assert second["matches"][0]["concern_key"] == "service_relation.data_isolation"


def test_isolation_local_check_keeps_unique_inbound_call_identity():
    from scene_completion.analysis.scenarios.failure_units import local_caller_request
    from tests.support.workflow import exchange

    request = exchange(sid="S1")
    request["sender"].update(name="Platform", position="内部服务")
    local = deepcopy(request)
    local.update(id="S2", step_kind="action", validates=["S1"])
    local["sender"] = deepcopy(local["receiver"])
    match = {"concern_key": "service_relation.data_isolation", "interaction_id": "S2"}
    assert local_caller_request(match, [request, local])["id"] == "S1"
    duplicate = deepcopy(request)
    duplicate["id"] = "another-request"
    local["validates"] = []
    assert local_caller_request(match, [request, duplicate, local]) is None
