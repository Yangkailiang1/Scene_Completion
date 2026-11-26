import json
from copy import deepcopy
from pathlib import Path
from shutil import copytree

import pytest

from scene_completion.analysis.concerns.constraint_atoms import normalize_rules
from scene_completion.domain import business_report
from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, case_report
from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd import matching
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.domain.ssd.validation import validate
from scene_completion.workflow.ssd.compare import alignment
from scene_completion.workflow.ssd.generate.fixed import generate_g
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.input_conversion.core_input import convert, validate_core
from scene_completion.workflow.ssd.input_conversion.function_tree import _merge_input_fields
from scene_completion.workflow.ssd.resolve import classification, operations

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"
COMMAND = "BROWSE-GET"


@pytest.fixture
def bundle():
    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    bundle.update(coverage_policy=GRAIN_POLICY, gt_source_available=True)
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    return bundle


def _prepare(bundle, fields, *, route="/products", crud="create"):
    request = bundle["steps"][0]
    command = next(row for row in bundle["commands"] if row["id"] == COMMAND)
    template = next(row for row in command["fields"] if row["name"] == "keyword")
    definitions = []
    for name, location, options in fields:
        definitions.append(
            {
                **deepcopy(template),
                "name": name,
                "wire_name": name,
                "atoms": [],
                **({"declared_name_location": location} if location else {}),
                **options,
            }
        )
    command.update(
        name="处理商品", method="POST", path=route, fields=_merge_input_fields(definitions)
    )
    request["operation"].update(
        name="处理商品", http_method="POST", http_path=route, kinds=[], kinds_source="pending"
    )

    def semantic(task, inputs):
        assert task == operations.TASK
        return {
            "operations": [
                {
                    "unit_id": unit["id"],
                    "step_id": unit["step_id"],
                    "crud": [crud] if unit.get("command_id") == COMMAND else ["read"],
                    "reason": "fixture confirms the actual operation",
                }
                for unit in inputs["units"]
            ]
        }

    operations.resolve(bundle, semantic)
    bundle["channels"]["G"] = generate_g(bundle)


def _generated(bundle):
    return bundle["channels"]["G"]["scenarios"]


def _names(bundle):
    return [scene for scene in _generated(bundle) if scene.get("name_character_input")]


@pytest.mark.parametrize(
    ("crud", "name", "location", "expected"),
    [
        ("create", "name", "body", 1),
        ("read", "name", "body", 0),
        ("update", "name", "body", 0),
        ("create", "productName", "body", 0),
        ("create", "name", "response", 0),
    ],
)
def test_name_requires_confirmed_create_and_real_input(bundle, crud, name, location, expected):
    _prepare(bundle, [(name, location, {})], crud=crud)
    assert len(_names(bundle)) == expected
    if expected:
        [scene] = _names(bundle)
        assert scene["step_id"] == "B1" and scene["key"] == policy.PATH_CHARACTERS
        assert scene["name_character_input"]["command_id"] == COMMAND
        [group] = [
            row for row in bundle["channels"]["G"]["concerns"] if row["id"] in scene["concern_ids"]
        ]
        assert group["label"] == "特殊字符"
        assert all(word in scene["condition"] for word in ("SQL 注入", "HTML 脚本", "路径穿越"))


def test_same_path_input_reuses_identity_but_distinct_body_input_stays_separate(bundle):
    refs = bundle["steps"][0]["source_refs"]
    regex = normalize_rules([{"rule": "仅允许字母和数字"}], "name", refs, character_rules=True)[
        "items"
    ]
    fields = [("name", "path", {"atoms": regex}), ("name", "body", {"atoms": regex})]
    _prepare(bundle, fields, route="/products/{name}/{categoryId}")
    names = _names(bundle)
    assert len(names) == 2
    assert {row["name_character_input"]["location"] for row in names} == {"path", "body"}
    assert len({parent for row in names for parent in row["concern_ids"]}) == 1
    path = next(row for row in names if row.get("path_input"))
    assert path["generation_rules"] == ["path_parameter", "create_name"]
    assert len([row for row in _generated(bundle) if row.get("input_character_rule")]) == 2
    legacy = deepcopy(bundle)
    legacy.pop("name_character_policy")
    legacy["registry"] = default_registry()
    legacy_g = generate_g(legacy)
    assert not any(row.get("name_character_input") for row in legacy_g["scenarios"])
    assert path["id"] in {row["id"] for row in legacy_g["scenarios"]}
    assert [
        row["label"] for row in legacy_g["concerns"] if row["key"] == policy.PATH_CHARACTERS
    ] == ["路径参数特殊字符"]


def _entity_name(bundle):
    product = next(row for row in bundle["entities"] if row["id"] == "Product")
    product["attributes"].append({**product["attributes"][0], "name": "name", "atoms": []})


def test_explicit_alias_composes_entity_and_command_without_extra_scenario(bundle):
    _entity_name(bundle)
    _prepare(
        bundle,
        [("label", "body", {"entity_binding": {"entity_id": "Product", "attribute": "name"}})],
    )
    [scene] = _names(bundle)
    assert scene["name_character_input"]["names"] == ["label", "name"]
    assert scene["name_character_input"]["entity_id"] == "Product"
    assert scene.get("field_id")


def test_entity_from_response_only_does_not_create_an_input_scenario(bundle):
    _entity_name(bundle)
    response = next(row for row in bundle["steps"] if row["id"] == "B6")
    response["entity_ids"] = ["Product"]
    _prepare(bundle, [("keyword", "query", {})])
    assert not _names(bundle)


def test_entity_only_reuses_operation_task_without_creating_crud_owner(bundle):
    _entity_name(bundle)
    step = next(row for row in bundle["steps"] if row["id"] == "B4")
    step["operation"]["name"] = "存储新商品"

    def semantic(task, inputs):
        assert task == operations.TASK
        return {
            "operations": [
                {
                    "unit_id": row["id"],
                    "step_id": row["step_id"],
                    "crud": ["create"] if row["kind"] == "entity_name_input" else ["read"],
                    "reason": "已核对主成功流中的实际操作",
                }
                for row in inputs["units"]
            ]
        }

    operations.resolve(bundle, semantic)
    bundle["channels"]["G"] = generate_g(bundle)
    [scene] = _names(bundle)
    assert scene["step_id"] == "B4"
    assert scene["entity_id"] == "Product"
    assert scene["name_character_input"]["command_id"] is None
    assert not any(unit["step_id"] == "B4" for unit in bundle["operation_units"])


@pytest.mark.parametrize("location", ["body", "path"])
def test_egt_match_name_and_regex_separately_and_keep_actual_failure_step(bundle, location):
    refs = bundle["steps"][0]["source_refs"]
    regex = normalize_rules([{"rule": "符合正则 ^[a-z]+$"}], "name", refs, character_rules=True)[
        "items"
    ]
    route = "/products/{name}" if location == "path" else "/products"
    prefix = "路径参数 {name}" if location == "path" else "请求体 name"
    _prepare(bundle, [("name", location, {"atoms": regex})], route=route)
    [risk] = _names(bundle)
    [rule] = [row for row in _generated(bundle) if row.get("input_character_rule")]
    examples = [
        ("E", f"{prefix} 不符合明示正则", {rule["id"]}),
        ("GT", f"{prefix} 含 SQL 注入特征且不应执行", {risk["id"]}),
        ("GT", f"{prefix} 含 HTML 脚本且不符合明示正则", {risk["id"], rule["id"]}),
    ]
    expected_ids = {condition: ids for _, condition, ids in examples}
    for idx, (name, condition, _) in enumerate(examples):
        source = {
            "id": f"evidence-{idx}",
            "condition": condition,
            "expected": "拒绝请求",
            "api_id": COMMAND,
            "failure_step_id": "B2",
            "source_refs": refs,
        }
        bundle["channels"][name]["pending"].append(
            pending(source["id"], condition, refs, original=source, needs_semantic=True)
        )

    def semantic(task, inputs):
        if task == classification.CLASSIFY:
            return {
                "records": [
                    {
                        "record_id": row["id"],
                        "kind": "exception",
                        "reason": "原文描述明确失败条件",
                        "parts": [
                            {
                                "condition": row["condition"],
                                "expected": row["expected"],
                                "keys": [
                                    key
                                    for cue, key in (
                                        ("正则", policy.FIELD),
                                        ("含", policy.PATH_CHARACTERS),
                                    )
                                    if cue in row["condition"]
                                ],
                            }
                        ],
                    }
                    for row in inputs["records"]
                ]
            }
        assert task == alignment.ALIGN
        for part in inputs["parts"]:
            assert {row["id"] for row in part["candidates"]} == expected_ids[part["condition"]]
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "reason": "逐项验证证据",
                    "matches": [
                        {"candidate_id": row["id"], "status": "full", "reason": "输入和条件相同"}
                        for row in part["candidates"]
                    ],
                    "fallback": None,
                }
                for part in inputs["parts"]
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    validate(bundle)
    for name in ("E", "GT"):
        assert not bundle["channels"][name]["pending"]
        assert all(
            row["step_id"] == "B1" and row["failure_step_id"] == "B2"
            for row in bundle["channels"][name]["scenarios"]
        )
    comparison = case_report(bundle)["comparison"]
    assert {
        row["generated_id"]
        for row in comparison["scenarios"]
        if row.get("generated_id") in {risk["id"], rule["id"]} and row["cells"]["GT"]
    } == {risk["id"], rule["id"]}
    groups, _ = business_report.classify(bundle, matching)
    assert {risk["id"], rule["id"]} <= {row["id"] for row in groups["covered"]}


def test_name_locations_survive_structured_import_and_core_roundtrip(tmp_path):
    supplier = tmp_path / "supplier"
    copytree(BROWSE, supplier)
    function_tree = supplier / "功能树.json"
    tree = json.loads(function_tree.read_text(encoding="utf-8"))
    function = tree["functions"][0]
    route = "/api/v1/products/{name}"
    for layer in ("rrLayer", "srLayer"):
        command = next(row for row in function[layer]["commands"] if row["apiId"] == COMMAND)
        command.update(method="POST", path=route, name="创建商品")
    template = function["srLayer"]["commands"][0]["attributes"][0]
    function["srLayer"]["commands"][0]["attributes"] = [
        {
            **template,
            "name": "name",
            "type": "string",
            "source": {**template["source"], "section": section},
            "constraints": [],
        }
        for section in ("路径参数", "请求体")
    ]
    function_tree.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    behavior_file = next(supplier.rglob("SysOperation.json"))
    behavior = json.loads(behavior_file.read_text(encoding="utf-8"))
    [request] = behavior["operations"]["browse_main_success"]["system_event"]
    request["content"] = f"调用 POST {route} 创建商品（{COMMAND}）"
    behavior_file.write_text(json.dumps(behavior, ensure_ascii=False), encoding="utf-8")

    core = tmp_path / "core"
    result = convert(supplier, core, profile=COMMAND_OPERATION_PROFILE)
    assert result["output"], result["issues"]
    assert validate_core(core)["valid"]
    [bundle] = build_cases(core)
    operations.resolve(bundle, None)
    bundle["channels"]["G"] = generate_g(bundle)
    names = _names(bundle)
    assert {row["name_character_input"]["location"] for row in names} == {"path", "body"}
    assert len(names) == 2
    assert {row["step_id"] for row in names} == {"B1"}
