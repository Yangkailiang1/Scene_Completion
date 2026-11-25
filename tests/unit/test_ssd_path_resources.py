from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.analysis.ssd.core_input import convert
from scene_completion.analysis.ssd.pipeline import build_cases
from scene_completion.analysis.validation import validate_result
from scene_completion.application import ssd_revision_service as revisions
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.domain.ssd import path_resources as paths
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.domain.ssd.matching import binding
from scene_completion.domain.ssd.validation import validate
from scene_completion.review.offline.business_report_export import _scenario_text
from scene_completion.workflow.ssd.compare.alignment import align
from scene_completion.workflow.ssd.compare.resource_alignment import prepare
from scene_completion.workflow.ssd.resolve import entity_semantics, operations, path_roles

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"
COMMAND = "BROWSE-GET"
NESTED = "/stores/{storeId}/categories/{categoryId}/products/{productId}"


@pytest.fixture
def bundle(tmp_path):
    target = tmp_path / "core"
    assert convert(BROWSE, target, profile=COMMAND_OPERATION_PROFILE)["output"]
    bundle = build_cases(target, generate=False)[0]
    bundle["coverage_policy"] = GRAIN_POLICY
    bundle["channels"] = {name: channel() for name in ("G", "E", "GT")}
    return bundle


def _operation(bundle, crud, path):
    command = next(row for row in bundle["commands"] if row["id"] == COMMAND)
    command["path"] = path
    step = next(step for step in bundle["steps"] if step["id"] == "B1")
    step["operation"]["http_path"] = path

    def resolve(task, inputs):
        return validate_result(
            task,
            {
                "operations": [
                    {
                        "unit_id": unit["id"],
                        "step_id": unit["step_id"],
                        "crud": [crud] if unit.get("command_id") == COMMAND else ["read"],
                        "reason": "样例中的已知操作",
                    }
                    for unit in inputs["units"]
                ]
            },
            inputs,
        )

    operations.resolve(bundle, resolve)


def _resource_rows(bundle):
    return [
        row
        for row in bundle["channels"]["G"]["scenarios"]
        if row.get("command_id") == COMMAND and row.get("resource_failure")
    ]


@pytest.mark.parametrize("crud", ["read", "update", "delete"])
def test_resource_obligations_follow_nested_path(bundle, crud):
    _operation(bundle, crud, NESTED + "?filter={ignore}")
    path_roles.resolve(bundle, lambda *_: pytest.fail("R/U/D 不应调用创建角色模型"))
    entity_semantics.infer(bundle, None)
    rows = _resource_rows(bundle)
    assert {
        (row["resource_reference"]["parameter_name"], row["resource_reference"]["role"])
        for row in rows
    } == {("storeId", "ancestor"), ("categoryId", "parent"), ("productId", "target")}
    assert all(row["step_id"] == "B1" and row["key"] == paths.KEYS[crud] for row in rows)
    assert all(row["resource_failure"] == "missing_resource" for row in rows)
    assert len({binding(row) for row in rows}) == 3


def test_create_distinguishes_target_and_dependencies(bundle):
    _operation(bundle, "create", NESTED)
    roles = {"storeId": "ancestor", "categoryId": "parent", "productId": "target"}

    def resolve(task, inputs):
        (command,) = inputs["commands"]
        assert (command["command_id"], command["parameters"]) == (COMMAND, list(roles))
        rows = [
            {"command_id": COMMAND, "name": name, "role": role, "reason": "依照创建操作"}
            for name, role in roles.items()
        ]
        with pytest.raises(ValueError, match="恰好"):
            validate_result(task, {"parameters": rows[:-1]}, inputs)
        return validate_result(task, {"parameters": rows}, inputs)

    path_roles.resolve(bundle, resolve)
    entity_semantics.infer(bundle, None)
    assert {
        (row["resource_reference"]["parameter_name"], row["resource_failure"])
        for row in _resource_rows(bundle)
    } == {
        ("storeId", "missing_resource"),
        ("categoryId", "missing_resource"),
        ("productId", "already_exists"),
    }


def test_collection_and_unknown_create_role(bundle):
    _operation(bundle, "read", "/products")
    path_roles.resolve(bundle, lambda *_: pytest.fail("不应分析路径角色"))
    entity_semantics.infer(bundle, None)
    assert not _resource_rows(bundle)
    _operation(bundle, "create", "/products/{key}/action")
    path_roles.resolve(bundle, None)
    entity_semantics.infer(bundle, None)
    assert [r["resource_failure"] for r in _resource_rows(bundle)] == ["already_exists"]
    assert any("key" in row["condition"] for row in bundle["channels"]["G"]["pending"])


def _atom(identifier, value):
    return {
        "id": identifier,
        "concern_key": paths.VALIDITY,
        "operation": "validity",
        "value": value,
        "source_refs": [{"quote": value, "proof": identifier}],
    }


def test_path_atoms_merge_provenance_but_keep_status_and_non_path_field(bundle):
    _operation(bundle, "update", NESTED)
    step = next(step for step in bundle["steps"] if step["id"] == "B1")
    category = next(field for field in step["data"] if field["name"] == "categoryId")
    assert category["entity_binding"] == {"entity_id": "Category", "attribute": "category_id"}
    category.pop("location", None)
    category["atoms"].extend(
        [_atom("contract", "categoryId 指向的分类必须存在"), _atom("state", "分类未停用")]
    )
    entity = next(e for e in bundle["entities"] if e["id"] == "Category")
    attribute = next(a for a in entity["attributes"] if a["name"] == "category_id")
    attribute["atoms"].append(_atom("entity", "分类对象必须存在"))
    query = next(field for field in step["data"] if field["name"] == "keyword")
    query["atoms"].append(_atom("ordinary", "引用的筛选模板必须存在"))
    entity_semantics.infer(bundle, None)
    path_rows = {
        row["resource_failure"]: row
        for row in _resource_rows(bundle)
        if row["resource_reference"]["parameter_name"] == "categoryId"
    }
    assert set(path_rows) == {"missing_resource", "disabled_reference"}
    missing, disabled = (path_rows[key] for key in ("missing_resource", "disabled_reference"))
    assert missing["concern_ids"] == disabled["concern_ids"]
    assert {ref["proof"] for ref in missing["source_refs"] if "proof" in ref} == {
        "contract",
        "entity",
    }
    assert {ref["proof"] for ref in disabled["source_refs"] if "proof" in ref} == {"state"}
    assert {
        row["field_id"]
        for row in bundle["channels"]["G"]["scenarios"]
        if row["key"] == paths.VALIDITY
    } == {query["id"]}


def test_independent_e_and_gt_use_exact_resource_failure_and_keep_actual_step(bundle):
    _operation(bundle, "delete", NESTED)
    entity_semantics.infer(bundle, None)
    bundle["source_classifications"] = {}
    for name, condition in (("E", "categoryId 不存在"), ("GT", "categoryId 已停用")):
        raw = {
            "id": name,
            "condition": condition,
            "expected": "拒绝本次删除",
            "failure_step_id": "B2",
            "source_refs": [],
        }
        bundle["channels"][name]["pending"] = [pending(name, condition, original=raw)]
        bundle["source_classifications"][name] = [
            {
                "record_id": name,
                "kind": "exception",
                "reason": "原文描述路径引用对象失败",
                "parts": [
                    {"condition": condition, "expected": raw["expected"], "keys": [paths.VALIDITY]}
                ],
            }
        ]

    def semantic(task, inputs):
        assert inputs["channel"] == "E"
        (part,) = inputs["parts"]
        (scene,) = part["candidates"]
        assert scene["resource_reference"]["parameter_name"] == "categoryId"
        assert scene["resource_failure"] == "missing_resource"
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "matches": [
                        {
                            "candidate_id": scene["id"],
                            "status": "full",
                            "reason": "同一父对象不存在",
                        }
                    ],
                    "fallback": None,
                    "reason": "同一父对象不存在",
                }
            ]
        }

    align(bundle, semantic)
    bundle = validate(bundle)
    (e_row,) = bundle["channels"]["E"]["scenarios"]
    (gt_row,) = bundle["channels"]["GT"]["scenarios"]
    assert e_row["step_id"] == gt_row["step_id"] == "B1"
    assert e_row["failure_step_id"] == gt_row["failure_step_id"] == "B2"
    assert (e_row["resource_failure"], gt_row["resource_failure"]) == (
        "missing_resource",
        "disabled_reference",
    )
    assert not bundle["semantic_pending"]
    assert not bundle["channels"]["GT"]["pending"]
    assert not any(row["pair"] in {"GT_G", "GT_E"} for row in bundle["decisions"])
    steps = {step["id"]: step for step in bundle["steps"]}
    text, _ = _scenario_text(gt_row, {"GT": [gt_row]}, steps, {}, {}, aligned=False)
    assert "父对象 categoryId" in text and "已停用" in text


def test_republish_keeps_unique_manual_revision_and_retains_ambiguous_issue(tmp_path, bundle):
    _operation(bundle, "update", NESTED)
    entity_semantics.infer(bundle, None)
    row = next(
        row
        for row in _resource_rows(bundle)
        if row["resource_reference"]["parameter_name"] == "categoryId"
    )
    old = deepcopy(bundle)
    old.pop("path_resource_checks")
    source_field = next(
        field for step in old["steps"] for field in step["data"] if field["name"] == "categoryId"
    )
    old["channels"]["G"]["scenarios"] = [
        {
            **row,
            "id": "legacy-path-field",
            "key": paths.VALIDITY,
            "target": "data",
            "field_id": source_field["id"],
            "resource_reference": None,
            "condition": "categoryId 指向的分类不存在",
        },
        {
            **row,
            "id": "legacy-ambiguous",
            "resource_reference": None,
            "condition": "更新所依赖或操作的业务资源不存在",
        },
    ]
    project = tmp_path / "project"
    saved = revisions.publish(project, old)
    edited = deepcopy(saved["bundle"])
    for scene in edited["channels"]["G"]["scenarios"]:
        scene["analysis"] = scene["id"] + " 的人工补充"
    revisions.save_revision(
        project,
        old["case"]["id"],
        {"base_revision": saved["revision"], "bundle": edited, "reason": "验收修订迁移"},
    )
    updated = revisions.publish(project, bundle)
    rows = {scene["id"]: scene for scene in updated["bundle"]["channels"]["G"]["scenarios"]}
    assert rows[row["id"]]["analysis"] == "legacy-path-field 的人工补充"
    assert updated["bundle"]["revision_issues"][0]["previous_record"]["id"] == "legacy-ambiguous"
    assert revisions.editor(project, old["case"]["id"], 1)["bundle"] == saved["bundle"]


def test_generic_resource_failure_does_not_attach_to_multiple_path_objects(bundle):
    _operation(bundle, "delete", NESTED)
    entity_semantics.infer(bundle, None)
    part = {
        "failure_step_id": "B2",
        "condition": "资源不存在",
        "keys": [paths.KEYS["delete"]],
    }
    prepare(bundle, {}, part)
    assert "resource_check" not in part and "resource_issue" in part
    anchored = {**part, "condition": "该分类不存在"}
    anchored.pop("resource_issue")
    prepare(bundle, {"entity_id": "Category", "attribute": "category_id"}, anchored)
    assert anchored["resource_check"]["resource_reference"]["parameter_name"] == "categoryId"
