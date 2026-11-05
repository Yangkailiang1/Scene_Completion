from copy import deepcopy

import pytest

from scene_completion.analysis.concern_alignment import recognize
from scene_completion.analysis.recognition_coverage import field_reviews, validate_coverage
from scene_completion.inputs.colleague_formats import Facts, api_product, request_parameters
from tests.test_workflow import R, exchange, memory_inputs


def test_missing_known_field_reviews_are_rejected_not_silently_pending():
    x = memory_inputs()
    with pytest.raises(ValueError, match="omitted explicit field constraints"):
        validate_coverage(
            {"matches": [], "pending": [{"object": "Product", "reason": "unknown"}]}, x
        )
    assert any(
        r["field"] == "page" and r["concern_key"] == "api.data.type" for r in field_reviews(x)
    )
    # Validation never fills G, nor forces an optional field's missing-value check.
    value = {"matches": []}
    with pytest.raises(ValueError):
        validate_coverage(value, x)
    assert value == {"matches": []}
    assert not any(
        r["field"] == "page" and r["concern_key"] == "api.data.completeness"
        for r in field_reviews(x)
    )


def test_review_checklist_respects_project_disabled_definitions():
    x = memory_inputs()
    x["registry"] = {"definitions": {"api.data.type": {"enabled": False}}}
    assert field_reviews(x) == []
    validate_coverage({"matches": []}, x)


def test_crud_entry_review_prevents_database_only_silent_omissions():
    from scene_completion.analysis.crud_review import context, validate_reviews

    entry = exchange()
    entry["sender"]["name"], entry["receiver"]["name"] = "Platform", "Admin"
    entry["step_kind"] = "interaction"
    action = deepcopy(entry)
    action.update(id="local", step_kind="action")
    action["sender"]["name"] = "Admin"
    x = {
        "fused-ssd": {"interactions": [entry, action], "source_views": ["duplicate"]},
        "business-entities": {
            "entities": [{"id": "Thing", "name": "Thing", "attributes": [], "source_refs": R}]
        },
        "normal-documents": [],
    }
    compact = context(x)
    assert [r["interaction_id"] for r in compact["required_entry_reviews"]] == ["req"]
    assert "source_views" not in compact["fused-ssd"]
    assert x["fused-ssd"]["source_views"] == ["duplicate"]
    with pytest.raises(ValueError, match="missing=.*req"):
        validate_reviews({"rows": [], "pending": []}, x)
    validate_reviews({"rows": [], "reviews": [{"interaction_id": "req", "decision": "pending"}]}, x)
    with pytest.raises(ValueError, match="review/rows disagree"):
        validate_reviews(
            {"rows": [], "reviews": [{"interaction_id": "req", "decision": "crud"}]}, x
        )


def test_import_parses_each_independent_constraint_and_separates_response_variants():
    v = {
        "apis": [
            {
                "API序号": "A",
                "source_layer": "SR",
                "方法": "POST",
                "资源路径": "/things",
                "API请求参数": "body.name（必填；类型: string；长度 1-50）；body.mode（可选；类型: string；枚举 {A|B}）；body.price（必填；类型: number；0 <= price <= 100）",
                "API成功响应参数": "response.name（必填；类型: string；长度 1-50）",
                "成功状态码": 201,
                "API失败响应": [
                    {"状态码": 400, "参数": "response.error.code（必填；类型: string）"}
                ],
            }
        ]
    }
    result = api_product(v, "file", "api_extraction.json")
    a = next(p for p in result["artifacts"] if p["task"] == "api-parameters")["payload"]["apis"][0]
    name = next(p for p in a["parameters"] if p["name"] == "name" and p["location"] == "body")
    assert {c["kind"] for c in name["constraints"]} == {"length"}
    mode = next(p for p in a["parameters"] if p["name"] == "mode")
    assert mode["constraints"][0]["value"] == ["A", "B"]
    price = next(p for p in a["parameters"] if p["name"] == "price")
    assert {c["kind"] for c in price["constraints"]} == {"minimum", "maximum"}
    assert [(r["kind"], r["status_code"]) for r in a["responses"]] == [
        ("success", "201"),
        ("error", "400"),
    ]
    assert not any(p["name"] == "error.code" for p in a["parameters"])
    assert (
        result["counts"]["request_fields"] == 3 and result["counts"]["success_response_fields"] == 1
    )


def test_request_response_prefix_cannot_cross_direction():
    ps, pending = request_parameters(
        "response.name（必填；类型: string）", Facts("f", "f.json"), "/"
    )
    assert not ps and pending


def test_physical_and_logical_database_observations_share_one_binding():
    i = exchange()
    i["sender"].update(name="Platform", position="内部服务")
    i["receiver"].update(name="DB", position="外部数据库")
    i["operation"]["kinds"] = ["create"]
    components = {
        "components": [
            {"id": "db", "name": "DB", "composition_type": "外部数据库", "source_refs": R}
        ]
    }
    inverse = {"components": components, "fused-ssd": {"interactions": [i], "rr_sr_links": []}}
    logical = deepcopy(i)
    logical["receiver"].update(name="DB资源服务", position="内部服务（SR逻辑资源服务）")
    forward = {"components": components, "enriched-interactions": {"interactions": [logical]}}

    def observation(name):
        return {
            "interaction_id": "req",
            "target": "receiver",
            "object": name,
            "concern_key": "database.uniqueness",
            "basis": "DB enforces unique name",
            "concrete_rule": "name unique",
            "source_refs": R,
        }

    g = recognize(forward, {"matches": [observation("DB资源服务")]})["matches"][0]
    e = recognize(inverse, {"matches": [observation("DB")]}, inverse=True)["matches"][0]
    assert g["binding_id"] == e["binding_id"] and e["object"] == "DB资源服务"


def test_explicit_security_condition_with_null_generic_value_is_not_unknown():
    from scene_completion.analysis.concern_hierarchy import decorate

    i = exchange()
    ref = {**R[0], "quote": "header.Authorization；Bearer凭证必须有效且未过期"}
    m = {
        "interaction_id": i["id"],
        "target": "sender",
        "object": i["sender"]["name"],
        "concern_key": "human.authentication",
        "concrete_rule": "Bearer凭证必须有效且未过期",
        "basis": "已识别认证要求",
        "source_refs": [ref],
        "activation_evidence": [
            {
                "kind": "authentication",
                "condition": "Bearer凭证必须有效且未过期",
                "value": None,
                "unit": None,
                "status": "explicit",
                "source_refs": [ref],
            }
        ],
    }
    assert decorate(m, i, {})["status"] == "applicable"
    m["activation_evidence"][0]["source_refs"] = R
    assert decorate(m, i, {})["status"] == "pending"


def test_typed_component_flag_only_changes_the_evidenced_component():
    from scene_completion.inputs.component_facts import normalize_externality

    x = {
        "components": [
            {
                "name": "DB",
                "composition_type": "内部数据库",
                "source_refs": [{**R[0], "quote": '- {"canonical_name":"DB","is_external":true}'}],
            },
            {"name": "OtherDB", "composition_type": "内部数据库", "source_refs": R},
        ]
    }
    y = normalize_externality(x)
    assert y["components"][0]["composition_type"] == "外部数据库"
    assert y["components"][1]["composition_type"] == "内部数据库"
    assert x["components"][0]["composition_type"] == "内部数据库"


def test_delegated_crud_requires_actual_business_owner_and_same_case_call():
    from scene_completion.analysis.validation import validate_result

    parent = exchange(api=None)
    parent["sender"]["name"] = "Platform"
    parent["receiver"]["name"] = "Admin"
    child = deepcopy(parent)
    child["id"] = "db-call"
    child["sender"]["name"] = "Admin"
    child["receiver"]["name"] = "Database"
    row = {
        "case_id": parent["case_id"],
        "interaction_id": parent["id"],
        "entity_id": "Product",
        "service": "Admin",
        "operation": "read",
        "api_id": None,
        "basis": "Admin承担查询并委托数据库",
        "source_refs": R,
        "execution_mode": "delegated",
        "delegate_interaction_ids": [child["id"]],
    }
    inputs = {
        "business-entities": {"entities": [{"id": "Product"}]},
        "fused-ssd": {"interactions": [parent, child]},
    }
    validate_result("business-crud", {"rows": [row], "pending": []}, inputs)
    child["sender"]["name"] = "Unrelated"
    with pytest.raises(ValueError, match="downstream call"):
        validate_result("business-crud", {"rows": [row], "pending": []}, inputs)


def test_each_recognition_partition_keeps_only_its_own_direction_and_evidence():
    from scene_completion.workflow.task_partitions import split_task

    x = memory_inputs()
    request = x["sr-ssd"]["interactions"][0]
    response = deepcopy(request)
    response.update(id="response", direction="return", parent_id=request["id"])
    x["sr-ssd"]["interactions"].append(response)
    x["enriched-interactions"] = {"interactions": deepcopy(x["sr-ssd"]["interactions"])}
    x["normal-documents"] = [
        {
            "source_id": "positive",
            "name": "n.md",
            "channel": "normal",
            "lines": [
                {"number": 1, "text": R[0]["quote"]},
                {"number": 2, "text": "unrelated secret branch"},
            ],
        }
    ]
    units = split_task("concern-match", x)
    assert len(units) == 2
    assert all(len(q["enriched-interactions"]["interactions"]) == 1 for _, q in units)
    assert all(
        not any(r["number"] == 2 for d in q["normal-documents"] for r in d["lines"])
        for _, q in units
    )


def test_self_action_does_not_create_a_new_interservice_authentication_edge():
    from scene_completion.analysis.concern_hierarchy import decorate

    i = exchange()
    i["sender"].update(name="Admin", position="内部服务")
    i["receiver"].update(name="Admin", position="内部服务")
    i["step_kind"] = "action"
    m = {
        "interaction_id": i["id"],
        "target": "operation",
        "object": i["operation"]["name"],
        "concern_key": "service_relation.authentication",
        "basis": "本地校验",
        "concrete_rule": "校验调用身份",
        "source_refs": R,
        "activation_evidence": [
            {
                "kind": "authentication",
                "value": True,
                "condition": "校验调用身份",
                "source_refs": R,
                "status": "explicit",
            }
        ],
    }
    assert decorate(m, i, {})["status"] == "not_applicable"


def test_security_modal_word_normalization_keeps_negation():
    from scene_completion.analysis.concern_hierarchy import _security_condition_supported

    assert _security_condition_supported(
        "Bearer凭证有效且未过期", [{**R[0], "quote": "Bearer凭证必须有效且未过期"}]
    )
    assert not _security_condition_supported(
        "Bearer凭证有效", [{**R[0], "quote": "不要求Bearer凭证有效"}]
    )
