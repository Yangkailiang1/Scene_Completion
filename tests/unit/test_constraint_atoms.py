"""Declared constraints must become concerns without being lost or invented."""

from scene_completion.analysis.concerns.constraint_atoms import (
    normalize_rules,
    validate_atoms,
)
from scene_completion.analysis.interactions.field_anchors import (
    anchors,
    check_steps,
    entry_step,
)


def rules(*texts):
    return [{"rule": t, "error": None} for t in texts]


def keys(value):
    return [(i["concern_key"], i["operation"], i["value"]) for i in value["items"]]


def test_compound_rule_splits_into_independent_concerns():
    value = normalize_rules(rules("非空、长度≤N"), "product_name", [])
    assert keys(value) == [
        ("api.data.completeness", "required", True),
        ("api.data.length", "max_length", None),
    ]


def test_missing_standard_keeps_concern_and_never_invents_a_number():
    value = normalize_rules(rules("长度≤N"), "product_name", [])
    item = value["items"][0]
    # The concern exists; only its bound is unknown.
    assert item["concern_key"] == "api.data.length"
    assert item["value"] is None
    assert item["value_pending"]


def test_closed_interval_yields_both_bounds_on_one_concern():
    value = normalize_rules(rules("1 ≤ pageSize ≤ 100"), "pageSize", [])
    assert keys(value) == [
        ("api.data.range", "minimum", 1),
        ("api.data.range", "maximum", 100),
    ]


def test_interval_matches_a_differently_cased_field_name():
    value = normalize_rules(rules("1 ≤ pageSize ≤ 100"), "page_size", [])
    assert [i["value"] for i in value["items"]] == [1, 100]


def test_cross_field_bound_is_symbolic_not_a_fabricated_number():
    value = normalize_rules(rules("0 ≤ 且 ≥ sale_price"), "original_price", [])
    item = value["items"][0]
    assert item["concern_key"] == "api.data.range"
    assert item["value"] is None
    assert "sale_price" in item["value_pending"]


def test_unique_identifier_becomes_uniqueness_not_a_discarded_rule():
    value = normalize_rules(rules("唯一编号"), "product_id", [])
    assert keys(value) == [("database.uniqueness", "unique", True)]
    assert not value["unresolved"]


def test_enum_field_is_a_range_while_status_is_a_precondition():
    plain = normalize_rules(rules("{DEFAULT | PRICE_ASC}"), "sortBy", [], data_type="enum")
    assert plain["items"][0]["concern_key"] == "api.data.range"
    status = normalize_rules(rules("{ON_SALE}"), "status", [], data_type="enum")
    assert status["items"][0]["concern_key"] == "service.business_attribute_constraint"


def test_state_transition_is_not_read_as_an_enum_member():
    value = normalize_rules(rules("{WAIT_PAY → PAID}"), "status", [])
    item = value["items"][0]
    assert item["operation"] == "state_precondition"
    assert item["value"] == {"from": "WAIT_PAY", "to": "PAID"}


def test_prose_necessity_becomes_completeness():
    value = normalize_rules(rules("必要字段，缺失时缺省展示或过滤"), "product_name", [])
    assert keys(value) == [("api.data.completeness", "required", True)]


def test_display_fallback_alone_is_not_a_constraint():
    value = normalize_rules(rules("缺失时缺省展示或过滤异常商品"), "cover_image_url", [])
    assert not value["items"]
    assert value["payload"]


def test_field_list_is_a_payload_shape_not_a_constraint():
    value = normalize_rules(rules("cartItemId/productId/skuId/quantity/amount"), "items", [])
    assert not value["items"]
    assert value["payload"]


def test_unclassifiable_rule_stays_visible_forever():
    value = normalize_rules(rules("时间顺序合法"), "node_time", [])
    assert value["unresolved"][0]["text"] == "时间顺序合法"


def test_validity_needs_a_reference_not_an_adjective():
    assertive = normalize_rules(
        rules("创建后为1；有效更新或发布成功增加1；重复幂等请求不增加"), "version", []
    )
    assert not [i for i in assertive["items"] if i["concern_key"] == "api.data.validity"]
    referenced = normalize_rules(rules("分类存在且未停用"), "categoryId", [])
    assert referenced["items"][0]["concern_key"] == "api.data.validity"


def test_validation_rejects_a_fabricated_value_next_to_a_pending_one():
    value = {
        "field": "x",
        "items": [
            {
                "concern_key": "api.data.length",
                "operation": "max_length",
                "value": 100,
                "value_pending": "原文未给出",
                "source_refs": [{"quote": "q"}],
            }
        ],
    }
    try:
        validate_atoms(value, {"attributes": ["x"]})
    except ValueError as error:
        assert "不得编造" in str(error)
    else:  # pragma: no cover - the guard must fire
        raise AssertionError("a pending value must not also carry a number")


def test_validation_rejects_an_unregistered_concern():
    value = {
        "field": "x",
        "items": [
            {"concern_key": "api.data.unknown", "operation": "x", "value": 1, "source_refs": []}
        ],
    }
    try:
        validate_atoms(value, {"attributes": ["x"]})
    except ValueError as error:
        assert "未知或已停用" in str(error)
    else:  # pragma: no cover
        raise AssertionError("unregistered concerns must be rejected")


def _step(step_id, order, kind, direction="request", entities=(), text=""):
    return {
        "id": step_id,
        "order": order,
        "kind": kind,
        "direction": direction,
        "sender": {"id": "S", "name": "SYS", "position": "内部服务"},
        "receiver": {"id": "S", "name": "SYS", "position": "内部服务"},
        "operation": {"name": text},
        "data": [],
        "entity_ids": list(entities),
    }


def test_first_step_naming_the_entity_hosts_its_constraints():
    steps = [
        _step("s1", 1, "interaction", entities=["Order"]),
        _step("a1", 2, "action", entities=["Order"], text="校验订单状态"),
        _step("r1", 3, "interaction", "return"),
    ]
    bundle = {
        "case": {"id": "C"},
        "steps": steps,
        "entities": [
            {
                "id": "Order",
                "attributes": [
                    {"name": "status", "atoms": [{"concern_key": "api.data.range"}]},
                ],
            }
        ],
    }
    value = anchors(bundle)
    # The first step naming Order hosts it; the later check step must not add a
    # second copy of the same attribute concern.
    assert [u["step_id"] for u in value["units"]] == ["s1"]
    assert value["units"][0]["role"] == "首个声明该实体的交互"


def test_entity_without_a_check_step_falls_back_to_the_first_request():
    steps = [
        _step("s1", 1, "interaction"),
        _step("a1", 2, "action", entities=["Order"], text="保存订单"),
        _step("r1", 3, "interaction", "return"),
    ]
    bundle = {
        "case": {"id": "C"},
        "steps": steps,
        "entities": [
            {
                "id": "Category",
                "attributes": [
                    {"name": "status", "atoms": [{"concern_key": "api.data.range"}]},
                ],
            }
        ],
    }
    value = anchors(bundle)
    assert [(u["step_id"], u["role"]) for u in value["units"]] == [("s1", "用例首个业务请求")]


def test_several_check_steps_do_not_duplicate_the_entity():
    steps = [
        _step("s1", 1, "interaction", entities=["Order"]),
        _step("a1", 2, "action", entities=["Order"], text="校验订单状态"),
        _step("a2", 3, "action", entities=["Order"], text="校验订单金额"),
    ]
    bundle = {
        "case": {"id": "C"},
        "steps": steps,
        "entities": [
            {
                "id": "Order",
                "attributes": [{"name": "status", "atoms": [{"concern_key": "api.data.range"}]}],
            }
        ],
    }
    value = anchors(bundle)
    assert [u["step_id"] for u in value["units"]] == ["s1"]
    assert not value["pending"]


def test_helpers_ignore_return_messages_as_hosts():
    steps = [
        _step("s1", 1, "interaction"),
        _step("a1", 2, "action", text="校验Order归属"),
        _step("r1", 3, "interaction", "return"),
    ]
    assert entry_step(steps)["id"] == "s1"
    # A check step hosts an entity only when its prose or declared data names it.
    assert [s["id"] for s in check_steps(steps, "Order")] == ["a1"]
    assert not check_steps(steps, "Payment")


def test_every_constrained_attribute_of_an_entity_is_mounted():
    """A step naming an entity hosts all of its constrained attributes."""
    steps = [_step("s1", 1, "interaction")]
    bundle = {
        "case": {"id": "C"},
        "steps": steps,
        "entities": [
            {
                "id": "Product",
                "attributes": [
                    {"name": "product_id", "atoms": [{"concern_key": "database.uniqueness"}]},
                    {"name": "product_name", "atoms": [{"concern_key": "api.data.completeness"}]},
                    {"name": "sale_price", "atoms": [{"concern_key": "api.data.completeness"}]},
                    {"name": "updated_at", "atoms": []},
                ],
            }
        ],
    }
    value = anchors(bundle)
    # Two attributes under the same concern stay two units, and the attribute
    # with no declared constraint contributes nothing.
    assert len(value["units"]) == 3
    assert {u["attribute"] for u in value["units"]} == {"product_id", "product_name", "sale_price"}
    assert all(u["step_id"] == "s1" for u in value["units"])


def test_a_query_step_carrying_one_field_is_not_a_check_step():
    """Declaring the entity in data_ref does not by itself make a step a check."""
    query = _step("a1", 2, "action", entities=["Product"], text="根据条件查询状态为 ON_SALE 的商品")
    query["data"] = [{"id": "f1", "name": "status", "location": "business"}]
    steps = [_step("s1", 1, "interaction"), query]
    assert not check_steps(steps, "Product")


def test_several_entities_on_one_step_contribute_separately():
    steps = [_step("s1", 1, "interaction")]
    bundle = {
        "case": {"id": "C"},
        "steps": steps,
        "entities": [
            {
                "id": "CartItem",
                "attributes": [{"name": "quantity", "atoms": [{"concern_key": "api.data.range"}]}],
            },
            {
                "id": "SKU",
                "attributes": [{"name": "stock", "atoms": [{"concern_key": "api.data.range"}]}],
            },
        ],
    }
    value = anchors(bundle)
    assert {(u["entity"], u["attribute"]) for u in value["units"]} == {
        ("CartItem", "quantity"),
        ("SKU", "stock"),
    }


def test_enum_prefix_is_the_same_set():
    value = normalize_rules(rules("枚举 {STANDARD|SERVICE}"), "productType", [])
    assert keys(value) == [("api.data.range", "enum", ["STANDARD", "SERVICE"])]


def test_length_range_yields_both_bounds():
    value = normalize_rules(rules("长度 1-50"), "name", [])
    assert sorted((i["operation"], i["value"]) for i in value["items"]) == [
        ("max_length", 50),
        ("min_length", 1),
    ]


def test_conditional_cross_attribute_rule_stays_one_relation():
    value = normalize_rules(rules("productType为SERVICE时price必须大于等于1"), "price", [])
    item = value["items"][0]
    assert item["concern_key"] == "service.business_attribute_constraint"
    assert item["operation"] == "conditional_range"
    assert item["value"]["then"] == {"field": "price", "operator": ">=", "value": 1.0}


def test_prose_uniqueness_is_detected():
    value = normalize_rules(rules("同一merchantId下name不可重名；不同商家可重名"), "name", [])
    assert ("database.uniqueness", "unique", True) in keys(value)


def test_entity_falls_back_to_the_first_step_reaching_it():
    """SysOperation's first step naming the entity hosts it when no check exists."""
    query = _step("s3", 3, "interaction", entities=["Product"])
    steps = [_step("s1", 1, "interaction"), query, _step("r1", 4, "interaction", "return")]
    bundle = {
        "case": {"id": "C"},
        "steps": steps,
        "entities": [
            {
                "id": "Product",
                "attributes": [{"name": "price", "atoms": [{"concern_key": "api.data.range"}]}],
            }
        ],
    }
    value = anchors(bundle)
    assert [(u["step_id"], u["role"]) for u in value["units"]] == [("s3", "首个声明该实体的交互")]
