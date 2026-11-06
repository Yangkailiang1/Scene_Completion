"""Global C/U/D identity, independent channels and no interaction policy."""

from copy import deepcopy

import pytest

from scene_completion.analysis.concern_alignment import recognize
from scene_completion.analysis.global_analysis import compare_concerns, compare_scenarios
from scene_completion.analysis.global_idempotency import KEY, documents_for, operations, recognized
from scene_completion.analysis.validation import validate_result
from scene_completion.domain.contracts import registry
from tests.test_workflow import R, memory_inputs


def fixture():
    entities = [
        {"id": "entity", "name": "商品", "attributes": [], "business_rules": [], "source_refs": R}
    ]
    groups = [{"id": "G-1", "rr_ids": ["UC-1"], "sr_ids": ["SR-1"]}]
    cases = [{"id": "UC-1", "name": "创建商品"}, {"id": "SR-1", "name": "创建商品"}]
    crud = [
        {
            "case_id": "G-1",
            "entity_id": "entity",
            "operation": "create",
            "interaction_id": sid,
            "source_refs": R,
        }
        for sid in ("public", "internal", "database")
    ]
    return entities, groups, cases, crud


def test_global_CUD_one_effect_across_all_delegated_calls_and_no_R():
    entities, groups, cases, crud = fixture()
    for op in ("read", "update", "delete"):
        crud.append({**crud[0], "operation": op})
    rows = operations(crud, entities, groups, cases)
    assert {r["operation"] for r in rows} == {"create", "update", "delete"}
    assert len(rows) == 3
    create = next(r for r in rows if r["operation"] == "create")
    assert create["interaction_refs"] == ["database", "internal", "public"]
    assert operations(list(reversed(crud)), entities, groups, cases)[-1]["id"] in {
        r["id"] for r in rows
    }
    g = recognized(create)
    assert len(g["matches"]) == 1 and g["matches"][0]["business_operation_id"] == create["id"]
    assert g["matches"][0]["dependency_id"] is None and "interaction_id" not in g["matches"][0]
    assert "用户确认" in g["matches"][0]["basis"]


def test_default_does_not_fill_E_GT_and_business_operations_cannot_cross_match():
    entities, groups, cases, crud = fixture()
    op = operations(crud, entities, groups, cases)[0]
    g = recognized(op)
    empty = {"matches": [], "pending": []}
    assert compare_concerns(g, empty, empty)["M_count"] == 1
    other = deepcopy(g)
    other["matches"][0]["business_operation_id"] = "another-case-effect"
    assert (
        compare_concerns(g, empty, other)["metrics"]["generation_effectiveness"]["numerator"] == 0
    )
    s = {**g["matches"][0], "cause": "重复创建额外对象", "conditions": ["相同业务请求重复执行"]}
    assert len(compare_scenarios({"scenarios": [s, s]}, {"scenarios": []})["M"]) == 1


def test_global_validation_requires_real_operation_and_independent_source():
    entities, groups, cases, crud = fixture()
    op = operations(crud, entities, groups, cases)[0]
    inputs = {
        "business-operations": {"operations": [op]},
        "business-dependencies": {"dependencies": []},
        "business-entities": {"entities": entities},
        "registry": registry(),
    }
    validate_result("global-concerns", recognized(op), inputs)
    for field, value in [
        ("dependency_id", "fake-dep"),
        ("object", "wrong-entity"),
        ("business_operation_id", "fake-op"),
    ]:
        bad = recognized(op)
        bad["matches"][0][field] = value
        with pytest.raises(ValueError, match="business operation anchor"):
            validate_result("global-concerns", bad, inputs)
    with pytest.raises(ValueError, match="独立异常测试来源"):
        validate_result("global-test-concerns", recognized(op), {**inputs, "test-documents": []})


def test_dependency_scene_can_explicitly_leave_business_operation_anchor_null():
    from scene_completion.domain.contracts import validate

    row = {
        "id": "scene",
        "dependency_id": "actual-dependency",
        "business_operation_id": None,
        "concern_key": "global.call_order",
        "object": "entity",
        "cause": "前置操作未完成便执行后续操作",
        "conditions": ["有明确前置顺序"],
        "source_status": "explicit",
        "resolution": "explicit",
        "executable": True,
        "source_refs": R,
    }
    validate("global-scenarios", {"scenarios": [row], "pending": []})
    # Null is an alternative-anchor placeholder, never a replacement for a
    # real C/U/D operation identity when the identified concern is idempotency.
    entities, groups, cases, crud = fixture()
    op = operations(crud, entities, groups, cases)[0]
    bad = recognized(op)
    bad["matches"][0]["business_operation_id"] = None
    with pytest.raises(ValueError):
        validate_result(
            "global-concerns",
            bad,
            {
                "business-operations": {"operations": [op]},
                "business-dependencies": {"dependencies": []},
                "registry": registry(),
            },
        )


def test_interaction_recognition_never_auto_adds_idempotency_even_for_CUD_or_R():
    for operation in ("create", "read", "update", "delete"):
        x = memory_inputs()
        i = x["sr-ssd"]["interactions"][0]
        i["operation"]["kinds"] = [operation]
        assert not recognize(x, {"matches": []})["matches"]
    for key, d in registry()["definitions"].items():
        if d.get("guard") == "idempotency":
            assert d["enabled"] is False
    assert registry()["definitions"][KEY]["layer"] == "global"


def test_scope_keeps_exact_case_test_source_and_no_automatic_GT_from_policy():
    entities, groups, cases, crud = fixture()
    op = operations(crud, entities, groups, cases)[0]
    # No branch belonging to this use case: global E remains empty, not fabricated.
    docs = [
        {
            "source_id": "positive",
            "channel": "existing",
            "name": "RR.md",
            "lines": [{"number": 1, "text": "其他用例异常"}],
        }
    ]
    assert documents_for(docs, op, "existing", []) == []


def test_json_test_slice_keeps_entire_extension_not_only_opening_brace(tmp_path):
    import json

    from scene_completion.inputs.source_documents import read_documents

    source = tmp_path / "recovered_usecases.json"
    source.write_text(
        json.dumps(
            [
                {
                    "id": "UC-1",
                    "name": "创建商品",
                    "extensions": [
                        {
                            "id": "TEST-UC-001-IDEMPOTENCY",
                            "condition": "同一幂等键请求内容不同导致幂等冲突",
                            "expected_result": "返回 HTTP 409 且不重复创建",
                            "note": "实际业务创建操作",
                        }
                    ],
                },
                {
                    "id": "UC-2",
                    "name": "其他用例",
                    "extensions": [
                        {
                            "id": "UNRELATED",
                            "condition": "其他失败",
                            "expected_result": "返回400",
                        }
                    ],
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    entities, groups, cases, crud = fixture()
    op = operations(crud, entities, groups, cases)[0]
    selected = documents_for(read_documents([source], "test"), op, "test")
    text = "\n".join(line["text"] for doc in selected for line in doc["lines"])
    assert "同一幂等键请求内容不同导致幂等冲突" in text and "返回 HTTP 409 且不重复创建" in text
    assert "UNRELATED" not in text


def test_rule_upgrade_preserves_frozen_registry_and_is_idempotent(tmp_path):
    from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
    from scene_completion.review.project_review import project_registry

    project = tmp_path / "project"
    old = registry()
    old["definitions"].pop(KEY)
    old["definitions"]["service.resource_mutation.idempotency"]["enabled"] = True
    old["profiles"]["global"] = [k for k in old["profiles"]["global"] if k != KEY]
    old["hash"] = fingerprint({k: v for k, v in old.items() if k != "hash"})
    write_json(project / "run/registry_override.json", old)
    upgraded = project_registry(project)
    assert upgraded["definitions"][KEY]["layer"] == "global"
    assert upgraded["definitions"]["service.resource_mutation.idempotency"]["enabled"] is False
    assert read_json(project / "concern_versions" / (old["hash"] + ".json"))["registry"] == old
    before = sorted(p.name for p in (project / "concern_versions").glob("*.json"))
    assert project_registry(project)["hash"] == upgraded["hash"]
    assert sorted(p.name for p in (project / "concern_versions").glob("*.json")) == before
