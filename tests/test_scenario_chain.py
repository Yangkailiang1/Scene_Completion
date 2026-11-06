"""Regressions for recognized-but-lost scenes and channel-local normalization."""

from copy import deepcopy

import pytest

from scene_completion.analysis.concern_alignment import bind_scenarios, recognize
from scene_completion.analysis.concern_hierarchy import resolve_matches
from scene_completion.analysis.global_idempotency import validate_explicit_modes
from scene_completion.analysis.normal_rules import validate_rules
from scene_completion.analysis.scenario_patterns import applicability, generated
from tests.test_scenario_patterns import positive
from tests.test_workflow import R, parameter, scenario


def internal():
    x = positive()
    x["sr-ssd"]["interactions"] = x["enriched-interactions"]["interactions"]
    i = x["enriched-interactions"]["interactions"][0]
    i["sender"].update(name="Platform", position="内部服务")
    i["receiver"].update(name="Admin", position="内部服务")
    i["operation"]["kinds"] = ["update"]
    x["business-crud"] = {
        "rows": [{"interaction_id": i["id"], "operation": "update", "entity_id": "Product"}]
    }
    x["business-entities"] = {
        "entities": [{"id": "Product", "attributes": [], "business_rules": [{"source_refs": R}]}]
    }
    x["concern-match"] = {"matches": [], "pending": []}
    return x, i


def identified(x, i, key, condition, kind, **guard):
    raw = {
        "interaction_id": i["id"],
        "target": "receiver",
        "object": i["receiver"]["name"],
        "concern_key": key,
        "basis": condition,
        "concrete_rule": condition,
        "source_refs": R,
        "activation_evidence": [
            {
                "kind": kind,
                "condition": condition,
                "value": True,
                "status": "explicit",
                "source_refs": R,
                **guard,
            }
        ],
    }
    x["concern-match"] = recognize(x, {"matches": [raw]})
    return x["concern-match"]


def test_external_generated_failure_keeps_actual_call_not_party_mentioned_in_quote():
    x, i = internal()
    up = deepcopy(i)
    up.update(id="upstream", sequence=0)
    up["receiver"]["name"] = "Admin"
    i["sender"]["name"] = "Admin"
    i["receiver"].update(name="Database资源服务", position="外部服务")
    i["source_refs"] = [{**R[0], "quote": '{"sender":"Admin","receiver":"Database"}'}]
    x["enriched-interactions"]["interactions"].insert(0, up)
    x["concern-match"] = resolve_matches(x, [])
    out = generated(applicability(x))
    available = [s for s in out["scenarios"] if s["concern_key"] == "service.base.availability"]
    assert len(available) == 1
    assert available[0]["interaction_id"] == i["id"]
    assert available[0]["element_anchors"][0]["object"] == "Database资源服务"


def test_declared_service_caller_identity_without_token_mechanism_generates_scene():
    x, i = internal()
    identified(
        x, i, "service_relation.authentication", "调用方身份必须为Platform", "authentication"
    )
    g = generated(applicability(x))["scenarios"]
    rows = [s for s in g if s["concern_key"] == "service_relation.authentication"]
    assert len(rows) == 1 and "Platform" in rows[0]["cause"]
    assert not rows[0]["executable"] and rows[0]["resolution"] == "conditional"
    assert not any("签名" in s["cause"] or "过期" in s["cause"] for s in rows)


@pytest.mark.parametrize(
    "key,kind,condition",
    [
        (
            "service_relation.data_isolation",
            "authorization",
            "不得以其他service-id访问本服务的数据",
        ),
        (
            "service.business_attribute_constraint",
            "business",
            "productType为SERVICE时price必须大于等于1",
        ),
        ("service.business_attribute_constraint", "business", "productType创建后不得修改"),
    ],
)
def test_recognized_positive_conditions_expand_without_reading_inverse_answers(
    key, kind, condition
):
    x, i = internal()
    identified(x, i, key, condition, kind)
    x["E"] = {"secret": "DO_NOT_COPY"}
    x["GT"] = {"secret": "DO_NOT_COPY"}
    out = generated(applicability(x))
    rows = [s for s in out["scenarios"] if s["concern_key"] == key]
    assert len(rows) == 1 and condition in rows[0]["cause"]
    assert "DO_NOT_COPY" not in str(out)
    x["concern-match"]["matches"][0]["status"] = "pending"
    assert not any(s["concern_key"] == key for s in generated(applicability(x))["scenarios"])


def test_cross_field_conditional_rule_cannot_be_split_into_data_range():
    x, i = internal()
    i["data"]["sequence"] = [parameter("productType"), parameter("price")]
    with pytest.raises(ValueError, match="cross-field"):
        identified(x, i, "api.data.range", "productType为SERVICE时price必须大于等于1", "range")


def test_composite_field_is_contract_error_instead_of_success_with_empty_truth():
    x, i = internal()
    i["data"]["sequence"] = [parameter("productType"), parameter("price")]
    with pytest.raises(ValueError, match="composite data target"):
        recognize(
            x,
            {
                "matches": [
                    {
                        "interaction_id": i["id"],
                        "target": "data",
                        "object": "productType + price",
                        "data_location": "body",
                        "concern_key": "api.data.range",
                        "basis": "业务类型价格约束",
                        "source_refs": R,
                        "activation_evidence": [],
                    }
                ]
            },
        )


def test_cross_field_contract_cannot_bypass_validation_by_omitting_guards():
    x, i = internal()
    i["data"]["sequence"] = [parameter("productType"), parameter("price")]
    with pytest.raises(ValueError, match="cross-field conditional"):
        recognize(
            x,
            {
                "matches": [
                    {
                        "interaction_id": i["id"],
                        "target": "data",
                        "object": "price",
                        "data_location": "body",
                        "concern_key": "api.data.range",
                        "basis": "类型价格关系",
                        "concrete_rule": "productType=SERVICE时price必须>=1",
                        "source_refs": R,
                    }
                ]
            },
            inverse=True,
        )


def test_local_business_check_keeps_entity_without_adding_crud_rows():
    x, call = internal()
    local = deepcopy(call)
    local.update(id="local", step_kind="action", sequence=call["sequence"] + 1)
    local["sender"] = deepcopy(local["receiver"])
    local["data"]["sequence"] = []
    x["enriched-interactions"]["interactions"].append(local)
    before = deepcopy(x["business-crud"])
    rows = identified(
        x, local, "service.business_attribute_constraint", "类型为SERVICE时price>=1", "business"
    )
    assert rows["matches"][0]["status"] == "applicable"
    assert x["business-crud"] == before
    # A second real call without an explicit validates link is ambiguous.
    other = deepcopy(call)
    other["id"] = "another-call"
    x["enriched-interactions"]["interactions"].append(other)
    rows = identified(
        x, local, "service.business_attribute_constraint", "类型为SERVICE时price>=1", "business"
    )
    assert rows["matches"][0]["status"] == "not_applicable"
    local["validates"] = [call["id"]]
    rows = identified(
        x, local, "service.business_attribute_constraint", "类型为SERVICE时price>=1", "business"
    )
    assert rows["matches"][0]["status"] == "applicable"


def test_inverse_uses_complete_own_test_note_and_not_neighbour_note():
    x, call = internal()
    local = deepcopy(call)
    local.update(id="database-check", step_kind="action", sequence=call["sequence"] + 1)
    local["sender"] = deepcopy(local["receiver"])
    local["operation"]["name"] = "S4. Admin执行原子业务检查"
    x["enriched-interactions"]["interactions"].append(local)
    refs = [
        {
            **R[0],
            "source_id": "test",
            "line_start": 1,
            "line_end": 1,
            "quote": "SERVICE商品价格为0",
        },
        {**R[0], "source_id": "test", "line_start": 2, "line_end": 2, "quote": "失败于步骤S4。"},
    ]
    x["test-documents"] = [
        {
            "source_id": "test",
            "name": "test.json",
            "channel": "test",
            "lines": [{"number": n + 1, "text": r["quote"]} for n, r in enumerate(refs)],
        }
    ]
    test = {
        "id": "own",
        "case_id": "tc",
        "name": "价格关系",
        "scenario_type": "exception",
        "preconditions": "",
        "trigger": refs[0]["quote"],
        "expected_result": "失败",
        "source_refs": refs,
    }
    x["test-inventory"] = {"cases": [{"id": "tc", "association": ""}], "tests": [test]}
    m = {
        "interaction_id": call["id"],
        "target": "receiver",
        "object": "Admin",
        "concern_key": "service.business_attribute_constraint",
        "basis": "测试自己的业务约束",
        "source_refs": refs[:1],
        "activation_evidence": [
            {
                "kind": "business",
                "condition": "SERVICE价格>=1",
                "status": "explicit",
                "value": True,
                "source_refs": refs[:1],
            }
        ],
    }
    out = recognize(x, {"matches": [m]}, inverse=True)
    assert out["matches"][0]["interaction_id"] == local["id"]
    assert refs[1] in out["matches"][0]["source_refs"]
    test["source_refs"] = refs[:1]
    x["test-inventory"]["tests"].append({**test, "id": "neighbour", "source_refs": refs[1:]})
    out = recognize(x, {"matches": [m]}, inverse=True)
    assert out["matches"][0]["interaction_id"] == call["id"]


def test_non_field_database_scene_normalizes_scope_without_widening_data_scope():
    x, i = internal()
    i["receiver"].update(name="Catalog", position="外部数据库")
    i["sender"] = deepcopy(i["receiver"])
    i["step_kind"] = "action"
    s = scenario("uniqueness")
    s.update(
        interaction_id=i["id"],
        object="Catalog",
        field=None,
        concern_key="database.uniqueness",
        cause="同商家商品名称重复",
    )
    values = []
    for scope in ["interface", "service", "storage"]:
        out = bind_scenarios({"scenarios": [{**s, "scope": scope}]}, x)
        assert len(out["scenarios"]) == 1
        values.append(out["scenarios"][0])
    assert {s["scope"] for s in values} == {"storage"}
    assert len({tuple(s["concern_binding_ids"]) for s in values}) == 1


def test_return_rule_contract_owner_is_responder_and_cannot_bind_request_checks():
    x, i = internal()
    i.update(direction="return", id="response")
    i["data"]["sequence"] = [parameter("status", "response", dtype="string")]
    ref = {**R[0], "quote": "发布成功的response.status必须为PUBLISHED"}
    r = {
        "id": "r",
        "interaction_id": "response",
        "owner_service": "Platform",
        "concern_key": "api.data.range",
        "condition": ref["quote"],
        "violation": "发布成功响应status不是PUBLISHED",
        "fields": ["status"],
        "functional_kinds": [],
        "resolution": "explicit",
        "pending_details": [],
        "source_refs": [ref],
    }
    inp = {
        "fused-ssd": x["enriched-interactions"],
        "normal-documents": [
            {
                "source_id": ref["source_id"],
                "name": "SR",
                "channel": "normal",
                "lines": [{"number": 1, "text": ref["quote"]}],
            }
        ],
    }
    validate_rules({"rules": [r]}, inp)
    with pytest.raises(ValueError, match="response normal rules"):
        validate_rules({"rules": [{**r, "concern_key": "human.authentication"}]}, inp)


def test_global_key_conflict_is_separate_and_requires_its_own_positive_premise():
    inp = {
        "business-operations": {"operations": [{"id": "op"}]},
        "identified-concerns": {
            "matches": [{"business_operation_id": "op", "concern_key": "global.idempotency"}]
        },
        "normal-documents": [{"channel": "normal", "lines": [{"text": "同键不同内容必须拒绝"}]}],
    }
    same = {
        "business_operation_id": "op",
        "concern_key": "global.idempotency",
        "cause": "同键同内容重复执行",
        "conditions": ["重复产生额外影响"],
    }
    with pytest.raises(ValueError, match="same-key/different-content"):
        validate_explicit_modes({"scenarios": [same]}, inp)
    validate_explicit_modes({"scenarios": [{**same, "cause": "同键不同内容未被拒绝"}]}, inp)
    inp["normal-documents"] = []
    validate_explicit_modes({"scenarios": [same]}, inp)


def test_response_rule_survives_partition_and_context_compaction():
    from scene_completion.workflow.task_context import semantic_view
    from scene_completion.workflow.task_partitions import split_task

    x, request = internal()
    response = deepcopy(request)
    response.update(id="response", direction="return", parent_id=request["id"], sequence=2)
    response["sender"], response["receiver"] = response["receiver"], response["sender"]
    response["data"]["sequence"] = [parameter("status", "response", dtype="string")]
    inp = {
        "fused-ssd": {"interactions": [request, response], "rr_sr_links": [], "pending": []},
        "normal-documents": [],
    }
    units = split_task("normal-rules", inp)
    part = next(q for key, q in units if key == "response")
    compacted = semantic_view("normal-rules", part)
    assert compacted["fused-ssd"]["interactions"][0]["direction"] == "return"


def test_single_operation_sequence_alias_does_not_duplicate_bindings():
    x, i = internal()
    i["operation"]["sequence"] = [i["operation"]["name"]]
    raw = {
        "interaction_id": i["id"],
        "target": "operation",
        "object": i["operation"]["name"],
        "concern_key": "service_relation.data_isolation",
        "basis": "仅访问本服务数据",
        "concrete_rule": "不得以其他service-id访问本服务的数据",
        "source_refs": R,
        "activation_evidence": [
            {
                "kind": "authorization",
                "status": "explicit",
                "condition": "不得以其他service-id访问本服务的数据",
                "value": True,
                "source_refs": R,
            }
        ],
    }
    out = recognize(
        x, {"matches": [{**raw, "operation_index": 0}, {**raw, "operation_index": None}]}
    )
    assert len(out["matches"]) == 1 and out["matches"][0]["operation_index"] is None


def test_one_test_caller_enum_violation_keeps_all_concerns_but_one_failure():
    from scene_completion.analysis.inverse_duplicates import merge_caller_enum

    x, i = internal()
    p = parameter("caller", "header", True, "string", [("enum", ["platform"])])
    i["data"]["sequence"] = [p]
    x["normal-constraints"] = {"apis": [{"id": i["api_id"], "parameters": [p]}]}
    x["fused-ssd"] = x["enriched-interactions"]
    x["identified-concerns"] = {
        "matches": [
            {
                "interaction_id": i["id"],
                "concern_key": "service_relation.authentication",
                "status": "applicable",
                "activation_evidence": [
                    {
                        "field": "caller",
                        "constraint_kind": "enum",
                        "status": "explicit",
                        "source_refs": R,
                    }
                ],
            }
        ]
    }
    a = scenario("auth")
    a.update(interaction_id=i["id"], concern_key="service_relation.authentication")
    b = {**deepcopy(a), "id": "enum", "concern_key": "api.data.range", "field": "caller"}
    record = {"触发条件": "header.caller=other"}
    removed = merge_caller_enum([a, b], record, x)
    assert removed == ["auth"]
    assert set(b["concern_origins"]) == {"service_relation.authentication", "api.data.range"}
    assert set(b["source_unit_ids"]) == {"auth", "enum"}
    assert b["failure_rule"] == {"kind": "enum", "value": ["platform"]}
    # Two values/fields or a permitted caller do not prove one identical failure.
    for trigger in ["header.caller=one，header.caller=two", "header.caller=platform"]:
        assert merge_caller_enum([a, b], {"触发条件": trigger}, x) == []


def test_normal_rule_excerpt_is_not_replaced_with_full_multirule_citation():
    from scene_completion.domain.contracts import packet
    from scene_completion.inputs.indexed_context import EvidenceContext

    x, i = internal()
    i.update(step_kind="action", validates=["inbound"])
    doc = {
        "source_id": "positive",
        "name": "SR",
        "channel": "normal",
        "lines": [{"number": 1, "text": "productType不可修改；name不可重复。"}],
    }
    inp = {
        "fused-ssd": {**x["enriched-interactions"], "rr_sr_links": [], "pending": []},
        "normal-documents": [doc],
    }
    p = packet("normal-rules", inp)
    from scene_completion.workflow.task_context import semantic_view

    compact = semantic_view("normal-rules", inp)["fused-ssd"]["interactions"][0]
    assert compact["step_kind"] == "action" and compact["validates"] == ["inbound"]
    ctx = EvidenceContext(p)
    row = {
        "id": "r",
        "interaction_id": i["id"],
        "owner_service": i["receiver"]["name"],
        "concern_key": "service.business_attribute_constraint",
        "condition": "productType不可修改",
        "violation": "productType被修改",
        "fields": ["productType"],
        "functional_kinds": ["update"],
        "resolution": "explicit",
        "pending_details": [],
        "source_refs": [
            {
                "source_id": "positive",
                "line_start": 1,
                "line_end": 1,
                "quote": doc["lines"][0]["text"],
            }
        ],
    }
    row["source_refs"] = [
        next(eid for eid, ref in ctx.pool.items() if ref["quote"] == doc["lines"][0]["text"])
    ]
    out = ctx.expand({"rules": [row], "pending": []})
    assert out["rules"][0]["condition"] == "productType不可修改"


def test_success_response_fixed_value_is_additional_to_generic_enum():
    x, i = internal()
    i.update(direction="return")
    i["data"]["sequence"] = [
        parameter("status", "response", True, "string", [("enum", ["DRAFT", "PUBLISHED"])])
    ]
    x["api-parameters"]["apis"][0]["parameters"] = deepcopy(i["data"]["sequence"])
    x["concern-match"] = recognize(
        x,
        {
            "matches": [
                {
                    "interaction_id": i["id"],
                    "target": "data",
                    "object": "status",
                    "scope": "interface",
                    "data_location": "response",
                    "concern_key": "api.data.range",
                    "basis": "成功响应约定",
                    "concrete_rule": "status枚举及本次成功值",
                    "source_refs": R,
                    "activation_evidence": [],
                }
            ]
        },
    )
    x["normal-rules"] = {
        "rules": [
            {
                "id": "published",
                "functional_kinds": [],
                "interaction_id": i["id"],
                "owner_service": "Platform",
                "concern_key": "api.data.range",
                "condition": "发布成功时status=PUBLISHED",
                "violation": "发布成功时status不等于PUBLISHED",
                "fields": ["status"],
                "source_refs": R,
                "resolution": "explicit",
                "pending_details": [],
            }
        ],
        "pending": [],
    }
    rows = [s for s in generated(applicability(x))["scenarios"] if s.get("field") == "status"]
    assert any(s["cause"] == "enum" for s in rows)
    assert any(s["cause"] == "发布成功时status不等于PUBLISHED" for s in rows)


@pytest.mark.parametrize(
    "kind,value,condition,expected",
    [
        ("minimum", [0, 100], "price在[0,100]区间内", {"minimum", "maximum"}),
        ("length", "1-50", "price存储字符串长度在1-50之间", {"length.minimum", "length.maximum"}),
    ],
)
def test_storage_schema_fields_follow_their_own_binding_and_split_bounds(
    kind, value, condition, expected
):
    x, i = internal()
    i["sender"].update(name="DB", position="外部数据库")
    i["receiver"] = deepcopy(i["sender"])
    i.update(step_kind="action", api_id=None)
    ref = {**R[0], "quote": condition}
    x["concern-match"] = recognize(
        x,
        {
            "matches": [
                {
                    "interaction_id": i["id"],
                    "target": "data",
                    "object": "price",
                    "scope": "storage",
                    "data_location": "storage",
                    "concern_key": "database.storage_validity",
                    "basis": condition,
                    "concrete_rule": condition,
                    "source_refs": [ref],
                    "activation_evidence": [
                        {
                            "kind": "storage_field",
                            "field": "price",
                            "constraint_kind": kind,
                            "value": value,
                            "status": "explicit",
                            "condition": condition,
                            "source_refs": [ref],
                        }
                    ],
                }
            ]
        },
    )
    rows = [
        s
        for s in generated(applicability(x))["scenarios"]
        if s["concern_key"] == "database.storage_validity"
    ]
    assert {s["failure_rule"]["kind"] for s in rows} == expected
    assert len({tuple(s["concern_binding_ids"]) for s in rows}) == 1
    assert all(s["scope"] == s["data_location"] == "storage" for s in rows)


@pytest.mark.parametrize("condition", ['{"rules": "whole document"}', "规则" * 251])
def test_normal_rule_rejects_whole_json_or_oversized_clause(condition):
    inp = {"fused-ssd": {"interactions": [], "rr_sr_links": [], "pending": []}}
    with pytest.raises(ValueError, match="short verbatim business clause"):
        validate_rules({"rules": [{"id": "bad", "condition": condition}]}, inp)
