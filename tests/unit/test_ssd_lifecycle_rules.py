"""Regressions found by reviewing the real five-case model evaluation."""

from copy import deepcopy

import pytest

from scene_completion.analysis.ssd.pipeline import _business_conditions, build_cases, generate_g
from tests.support.paths import ROOT


@pytest.fixture(scope="module")
def cases():
    return {b["case"]["id"]: b for b in build_cases(ROOT / "datasets/mini-mall")}


def conditions(bundle, step_id):
    return [
        s
        for s in bundle["channels"]["G"]["scenarios"]
        if s["step_id"] == step_id and s["key"] == "service.business_attribute_constraint"
    ]


def test_compound_state_clause_retains_update_and_delete_preconditions(cases):
    for case_id in ("UC-003", "UC-004"):
        rules = conditions(cases[case_id], "A_S4")
        state = [r for r in rules if "status = PUBLISHED" in r["condition"]]
        assert len(state) == 1
        assert state[0]["target"] == "receiver" and state[0]["entity_id"] == "Product"
        assert state[0]["source_refs"]
        assert not any("创建后为" in r["condition"] for r in rules)


def test_publish_has_concrete_pre_and_post_states_without_edit_only_rules(cases):
    bundle = cases["UC-005"]
    local = conditions(bundle, "A_S4")
    assert any("status = PUBLISHED" in r["condition"] for r in local)
    assert not any(
        any(word in r["condition"] for word in ("不可重名", "不可修改", "SERVICE")) for r in local
    )
    for step in ("SR-005-RES", "RR-005-RES"):
        returned = conditions(bundle, step)
        state = [r for r in returned if "status = DRAFT" in r["condition"]]
        assert len(state) == 1 and state[0]["target"] == "sender"
        assert state[0]["source_refs"]
        assert not any(
            any(
                text in r["condition"]
                for text in (
                    "创建请求不传",
                    "创建后为",
                    "status = PUBLISHED",
                    "version != 1",
                    "不可修改",
                    "不可重名",
                )
            )
            for r in returned
        )


def test_initial_values_only_apply_to_create_response(cases):
    created = conditions(cases["UC-001"], "SR-001-RES")
    assert any("status = PUBLISHED" in r["condition"] for r in created)
    assert any("version != 1" in r["condition"] for r in created)
    for case_id in ("UC-002", "UC-003", "UC-004", "UC-005"):
        for step in cases[case_id]["steps"]:
            if step["direction"] == "return":
                assert not any(
                    "创建成功响应" in r["condition"] for r in conditions(cases[case_id], step["id"])
                )


def test_state_generation_uses_source_values_and_operations_not_case_ids(cases):
    original = cases["UC-005"]
    bundle = deepcopy(original)
    bundle["case"] = {"id": "ARBITRARY-42", "name": "激活条目"}
    for entity in bundle["entities"]:
        for attribute in entity["attributes"]:
            for rule in attribute["constraints"]:
                if isinstance(rule.get("value"), str):
                    rule["value"] = (
                        rule["value"].replace("DRAFT", "READY").replace("PUBLISHED", "LIVE")
                    )
                elif rule.get("kind") == "enum":
                    rule["value"] = [
                        value.replace("DRAFT", "READY").replace("PUBLISHED", "LIVE")
                        for value in rule["value"]
                    ]
    for step in bundle["steps"]:
        for field in step["data"]:
            for rule in field["constraints"]:
                if isinstance(rule.get("value"), str):
                    rule["value"] = (
                        rule["value"].replace("DRAFT", "READY").replace("PUBLISHED", "LIVE")
                    )
                elif rule.get("kind") == "enum":
                    rule["value"] = [
                        value.replace("DRAFT", "READY").replace("PUBLISHED", "LIVE")
                        for value in rule["value"]
                    ]
    bundle["channels"]["G"] = generate_g(bundle)
    assert any("status = LIVE" in r["condition"] for r in conditions(bundle, "A_S4"))
    assert any("status = READY" in r["condition"] for r in conditions(bundle, "SR-005-RES"))
    assert original["case"]["id"] == "UC-005"


def test_unknown_state_domain_keeps_general_predicate_without_inventing_states():
    assert _business_conditions("phase", "仅QUEUED可删除", {"delete"}) == [
        "phase != QUEUED（仅QUEUED可删除）"
    ]
    assert _business_conditions(
        "phase", "发布时由QUEUED改为ACTIVE", {"publish"}, response=True
    ) == ["phase != ACTIVE（发布成功响应）"]


def test_multiple_enum_values_yield_distinct_invalid_state_scenarios():
    domain = ["QUEUED", "ACTIVE", "ARCHIVED"]
    before = _business_conditions("phase", "仅QUEUED可更新或删除", {"update"}, enum_values=domain)
    assert [s.split("（")[0] for s in before] == ["phase = ACTIVE", "phase = ARCHIVED"]
    after = _business_conditions(
        "phase", "由QUEUED改为ACTIVE", {"publish"}, response=True, enum_values=domain
    )
    assert [s.split("（")[0] for s in after] == ["phase = QUEUED", "phase = ARCHIVED"]
    initial = _business_conditions(
        "phase", "创建后为QUEUED", {"create"}, response=True, enum_values=domain
    )
    assert [s.split("（")[0] for s in initial] == ["phase = ACTIVE", "phase = ARCHIVED"]
    assert _business_conditions("phase", "仅QUEUED可删除", {"delete"}, enum_values=["QUEUED"]) == []


def test_immutable_rules_identify_attribute_and_keep_scenario_sources_separate(cases):
    bundle = cases["UC-003"]
    business = conditions(bundle, "A_S4")
    immutable = [
        r for r in business if "不可修改" in r["condition"] or "提供不同值" in r["condition"]
    ]
    assert len(immutable) == 2
    for scenario in immutable:
        assert "productType" in scenario["condition"]
        assert scenario["field_id"] is None and scenario["entity_id"] == "Product"
        quotes = [ref["quote"] for ref in scenario["source_refs"]]
        assert quotes and all("productType" in quote for quote in quotes)
        assert not any("Product.name" in quote or '"name": "price"' in quote for quote in quotes)
    state = next(r for r in business if "status = PUBLISHED" in r["condition"])
    assert all("status" in ref["quote"] for ref in state["source_refs"])
    concern = next(
        r for r in bundle["channels"]["G"]["concerns"] if r["id"] in state["concern_ids"]
    )
    assert any("Product.name" in ref["quote"] for ref in concern["source_refs"])
    assert any("Product.status" in ref["quote"] for ref in concern["source_refs"])
