import json
from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.analysis.interactions.field_anchors import anchors
from scene_completion.analysis.ssd.command_contract import attach
from scene_completion.analysis.ssd.core_input import convert, validate_core
from scene_completion.analysis.ssd.entity_semantics import classify
from scene_completion.analysis.ssd.pipeline import build_cases, generate_g
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, COMMAND_PROFILE
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.domain.ssd.matching import binding, semantic_candidates
from scene_completion.domain.ssd_contracts import packet

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"


def test_sr_commands_round_trip_uses_one_validation_anchor_and_two_bounds(tmp_path):
    output = tmp_path / "core"
    assert convert(BROWSE, output, profile=COMMAND_PROFILE)["output"]
    assert validate_core(output)["valid"]
    main = next(output.glob("cases/*/main-success.json"))
    core = json.loads(main.read_text())
    assert core["command_bindings"]["BROWSE-GET"] == {
        "primary_step_id": "B1",
        "occurrences": ["B1"],
        "validation_step_id": "B2",
        "validation_step_ids": ["B2"],
        "response_step_ids": ["B6"],
    }
    assert core["command_bindings"]["CATALOG-SEARCH"]["primary_step_id"] == "B3"
    bundle = build_cases(output)[0]
    scenes = bundle["channels"]["G"]["scenarios"]
    assert {
        s["condition"]
        for s in scenes
        if s["key"] == "api.data.range" and "pageSize" in s["condition"]
    } == {"pageSize < 1", "pageSize > 100"}
    assert {
        s["step_id"]
        for s in scenes
        if s["key"] == "api.data.range" and "pageSize" in s["condition"]
    } == {"B1"}
    assert not any(
        s.get("variant_id") == "missing_credential" and s["step_id"] == "B1" for s in scenes
    )
    units = bundle["field_anchors"]["units"]
    assert {unit["step_id"] for unit in units if unit["entity"] == "Product"} == {"B3"}
    assert "Product" in bundle["steps"][3]["entity_ids"]
    assert len(bundle["command_aliases"]) == 1
    assert any(
        s.get("attribute") == "category_id" and s["key"] == "api.data.format" for s in scenes
    )

    core["command_bindings"]["BROWSE-GET"]["primary_step_id"] = "B2"
    main.write_text(json.dumps(core), encoding="utf-8")
    assert not validate_core(output)["valid"]


def test_external_database_role_survives_core_and_availability_does_not_need_crud(tmp_path):
    from shutil import copytree

    from scene_completion.workflow.ssd.resolve.operations import resolve

    material = tmp_path / "supplier"
    copytree(BROWSE, material)
    path = next(material.rglob("SysOperation.json"))
    behavior = json.loads(path.read_text(encoding="utf8"))
    main = behavior["operations"]["browse_main_success"]
    participant = "act-gaussdb4mysql"
    del main["participant"]["CATALOG"]
    main["participant"][participant] = {
        "name": "Gaussdb4mysql",
        "kind": "external",
        "role": "外部数据库",
    }
    for kind in ("interaction", "action", "system_response"):
        for node in main[kind]:
            for field in ("sender", "receiver", "executor"):
                if node.get(field) == "CATALOG":
                    node[field] = participant
    path.write_text(json.dumps(behavior, ensure_ascii=False), encoding="utf8")
    core = tmp_path / "core"
    assert convert(material, core, profile=COMMAND_OPERATION_PROFILE)["output"]
    assert validate_core(core)["valid"]
    elements = json.loads((core / "architecture.json").read_text(encoding="utf8"))["elements"]
    db = next(e for e in elements if e["id"] == participant)
    assert (db["kind"], db["technology"], db["classification_source"]) == (
        "external_service",
        "database",
        "participant.role",
    )
    bundle = build_cases(core)[0]
    resolve(bundle, None)
    availability = "service.base.availability"
    special = "database.special_characters"
    for key in (availability, special):
        assert [row["step_id"] for row in generate_g(bundle)["concerns"] if row["key"] == key] == [
            "B3"
        ]
    bundle["operation_units"] = []
    assert [
        row["step_id"] for row in generate_g(bundle)["concerns"] if row["key"] == availability
    ] == ["B3"]
    bundle["steps"] = [step for step in bundle["steps"] if step["id"] != "B3"]
    assert [
        row["step_id"] for row in generate_g(bundle)["concerns"] if row["key"] == availability
    ] == ["B4"]
    bundle["steps"] = [
        step
        for step in bundle["steps"]
        if participant not in {step["sender"]["id"], step["receiver"]["id"]}
    ]
    assert not any(row["key"] == availability for row in generate_g(bundle)["concerns"])


@pytest.mark.parametrize("target", ["receiver", "sender"])
@pytest.mark.parametrize("with_g", [True, False])
def test_return_only_database_and_literal_e_gt_are_mounted(target, with_g):
    from scene_completion.analysis.ssd import grounding
    from scene_completion.domain.coverage import GRAIN_POLICY
    from scene_completion.domain.shared_services.aggregation import build

    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    for command in bundle["commands"]:
        if command["id"] == "BROWSE-GET":
            command["authentication"] = "required"
    request = bundle["steps"][0]
    database = {
        "id": "act-gaussdb4mysql",
        "name": "GaussDB4mysql",
        "technology": "database",
        "type": "service",
        "external": True,
    }
    returned = {
        **deepcopy(request),
        "id": "N0005",
        "order": 2,
        "direction": "return",
        "operation": {"name": "数据库返回结果", "kinds": [], "kinds_source": "pending"},
        "entity_ids": [],
        "data": [],
        "api_id": None,
        "sender": request["receiver"],
        "receiver": request["receiver"],
        target: database,
    }
    bundle["steps"] = [request, returned, {**deepcopy(returned), "id": "N0006", "order": 3}]
    bundle["operation_units"] = []
    bundle["coverage_policy"] = GRAIN_POLICY
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    generated = generate_g(bundle)
    keys = {"service.base.availability", "database.special_characters"}
    db_concerns = [r for r in generated["concerns"] if r["key"] in keys]
    assert {(r["key"], r["target"], r["step_id"]) for r in db_concerns} == {
        (key, target, "N0005") for key in keys
    }
    assert all(r["related_call_step_ids"] == ["N0005", "N0006"] for r in db_concerns)
    assert not any(
        r["step_id"] == "N0005"
        and r["key"].startswith(("service.crud.", "service.query_retrieval."))
        for r in generated["concerns"]
    )
    if with_g:
        bundle["channels"]["G"] = generated

    for origin, ident, condition, expected in (
        ("E", "E-access", "数据库访问异常", "返回原有错误"),
        ("GT", "GT-auth", "Authorization 缺失->401", "401"),
        ("GT", "GT-db", "数据库不可用", "返回服务不可用"),
    ):
        raw = {"id": ident, "condition": condition, "expected": expected, "source_refs": []}
        bundle["channels"][origin]["pending"].append(
            pending(ident, condition, original=raw, needs_semantic=True)
        )

    def semantic(task, inputs):
        pytest.fail(f"唯一的原文失败和挂载对象可确定，不需要调用 {task}")

    grounding.classify(bundle, semantic)
    grounding.align(bundle, semantic)
    for side in ("E", "GT"):
        assert bundle["channels"][side]["pending"] == []
    [existing] = bundle["channels"]["E"]["scenarios"]
    assert (existing["key"], existing["step_id"], existing["target"]) == (
        "service.base.availability",
        "N0005",
        target,
    )
    truth = {r["key"]: r for r in bundle["channels"]["GT"]["scenarios"]}
    assert truth["service.base.availability"]["step_id"] == "N0005"
    assert truth["human.authentication"]["step_id"] == request["id"]
    matched = [d for d in bundle["decisions"] if d["level"] == "scenario" and d["status"] == "full"]
    assert len(matched) == (2 if with_g else 0)
    assert all(d["pair"] == "GT_G" for d in matched)
    if with_g:
        canonical = {r["id"]: r["variant_id"] for r in generated["scenarios"]}
        assert {canonical[d["right_id"]] for d in matched} == {
            "missing_credential",
            "service_unavailable",
        }

    merged = build([{"bundle": bundle, "revision": 1}])
    [anchor] = merged["anchors"]
    assert [call["step_id"] for call in anchor["calls"]] == ["N0005", "N0006"]
    assert len(merged["channels"]["GT"]["scenarios"]) == 1
    assert merged["channels"]["GT"]["pending"] == []


def test_four_missing_g_candidates_use_verified_independent_placements():
    from scene_completion.analysis.ssd import grounding
    from scene_completion.domain.coverage import GRAIN_POLICY
    from scene_completion.workflow.ssd.resolve.operations import resolve

    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    resolve(bundle, None)
    bundle["coverage_policy"] = GRAIN_POLICY
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    samples = {
        "实体字段格式不合法": (
            "api.data.format",
            {"entity_id": "Category", "attribute": "category_id", "failure_step_id": "B2"},
        ),
        "pageSize 超过上限": (
            "api.data.range",
            {"parameter": {"command_id": "BROWSE-GET", "name": "pageSize"}},
        ),
        "目录服务无法连接": ("service.base.availability", {}),
        "认证信息无效": ("service_relation.authentication", {}),
    }
    for condition, (_, identity) in samples.items():
        raw = {
            "id": condition,
            "extension_id": condition,
            "condition": condition,
            "expected": "返回相应错误",
            "source_refs": [],
            **identity,
        }
        bundle["channels"]["GT"]["pending"].append(
            pending(raw["id"], condition, original=raw, needs_semantic=True)
        )
    calls = []

    def model(task, inputs):
        calls.append(task)
        if task == grounding.CLASSIFY:
            return {
                "records": [
                    {
                        "record_id": r["id"],
                        "kind": "exception",
                        "reason": "有原文失败",
                        "parts": [
                            {
                                "condition": r["condition"],
                                "expected": r["expected"],
                                "keys": [samples[r["condition"]][0]],
                            }
                        ],
                    }
                    for r in inputs["records"]
                ]
            }
        assert task == grounding.ALIGN and inputs["phase"] == "independent_mount"
        assert inputs["channel"] == "GT"
        rows = []
        for part in inputs["parts"]:
            assert not part["candidates"]
            name = part["condition"]
            if name in {"pageSize 超过上限", "目录服务无法连接"}:
                step = "B1" if name == "pageSize 超过上限" else "B3"
                binding = next(c for c in part["mount_options"] if c["step_id"] == step)
                reason = "由条件中的输入字段或服务名确认"
            else:
                assert name == "认证信息无效"
                binding, reason = None, "本批G候选为空，无可判定候选"
            rows.append(
                {"part_id": part["id"], "matches": [], "fallback": binding, "reason": reason}
            )
        return {"parts": rows}

    grounding.classify(bundle, model)
    grounding.align(bundle, model)
    assert calls == [grounding.CLASSIFY, grounding.ALIGN]
    assert bundle["channels"]["G"]["scenarios"] == [] and bundle["decisions"] == []
    scenes = {s["condition"]: s for s in bundle["channels"]["GT"]["scenarios"]}
    assert {name: scene["step_id"] for name, scene in scenes.items()} == {
        "实体字段格式不合法": "B2",
        "pageSize 超过上限": "B1",
        "目录服务无法连接": "B3",
    }
    [unresolved] = bundle["channels"]["GT"]["pending"]
    assert unresolved["condition"] == "认证信息无效"
    assert "具体交互步骤或挂载对象" in unresolved["reason"]


def test_gt_field_binding_accepts_different_actual_step_and_retains_independent_failure():
    bundle = build_cases(BROWSE, profile=COMMAND_PROFILE)[0]
    assert len(bundle["channels"]["GT"]["pending"]) == 4

    def classify_batch(task, inputs):
        assert task == "ssd-command-classify"
        assert "G" not in inputs and "channels" not in inputs
        fields = {f["name"]: f["id"] for f in inputs["interface_fields"]}
        schema = packet(task, inputs, ["UC-BROWSE-01"])["output_schema"]
        keys = schema["properties"]["records"]["items"]["properties"]["bindings"]["items"]
        assert "api.data.range" in keys["properties"]["key"]["enum"]
        reported = []
        for row in inputs["records"]:
            condition = row["condition"]
            good = "空列表" in condition or "=" in condition
            field = "keyword" if "keyword" in condition else "pageSize"
            reported.append(
                {
                    "record_id": row["id"],
                    "kind": "normal" if good else "exception",
                    "reason": "fixture",
                    "bindings": []
                    if good
                    else [
                        {
                            "step_id": "B1",
                            "target": "interface",
                            "field_id": fields[field],
                            "key": "api.data.length" if field == "keyword" else "api.data.range",
                            "entity_id": None,
                            "attribute": None,
                            "condition": condition,
                            "expected": row["expected"],
                        }
                    ],
                }
            )
        return {"records": reported}

    classify(bundle, classify_batch)
    gt = {s["condition"]: s for s in bundle["channels"]["GT"]["scenarios"]}
    assert len(gt) == 3
    assert gt["pageSize > 100"]["step_id"] == "B1"
    assert gt["pageSize > 100"]["validation_step_ids"] == ["B2"]
    assert gt["pageSize > 100"]["failure_step_id"] == "B1"
    assert all(s["condition"] != "keyword 长度 > 32" for s in bundle["channels"]["G"]["scenarios"])
    assert binding(gt["pageSize > 100"]) in {
        binding(s) for s in bundle["channels"]["G"]["scenarios"]
    }
    candidates = semantic_candidates(bundle)
    g = {s["condition"]: s for s in bundle["channels"]["G"]["scenarios"]}
    assert not any(
        pair["left_id"] == gt["pageSize < 1"]["id"]
        and pair["right_id"] == g["pageSize > 100"]["id"]
        for pair in candidates
    )


def test_first_call_merges_explicit_entity_and_interface_from_different_steps():
    bundle = build_cases(BROWSE, profile=COMMAND_PROFILE)[0]
    steps = bundle["steps"]
    # Keep the validator for the repeated call. Only the first call owns expansion.
    second = deepcopy(steps[0])
    second.update(id="B7", order=7)
    steps.append(second)
    steps[1]["validates"] = ["B7"]
    # The original entity can also be recorded independently at later steps.
    steps[3]["entity_ids"].append("Category")
    attach(bundle, {c["id"]: c for c in bundle["commands"]})
    bundle["field_anchors"] = anchors(bundle)
    bundle["channels"]["G"] = generate_g(bundle)
    assert bundle["command_bindings"]["BROWSE-GET"]["occurrences"] == ["B1", "B7"]
    assert [
        s["step_id"]
        for s in bundle["channels"]["G"]["scenarios"]
        if s["condition"] == "pageSize > 100"
    ] == ["B1"]
    assert (
        len(
            [
                s
                for s in bundle["channels"]["G"]["concerns"]
                if s.get("attribute") == "category_id" and s["key"] == "api.data.format"
            ]
        )
        == 1
    )

    field = next(f for f in steps[0]["data"] if f["name"] == "categoryId")
    for name, actual in (("E", "B2"), ("GT", "B7")):
        raw = {
            "id": name,
            "condition": "分类编号格式错误",
            "expected": "拒绝",
            "failure_step_id": actual,
            "source_refs": [],
        }
        bundle["channels"][name] = channel()
        bundle["channels"][name]["pending"].append(
            pending(name, raw["condition"], original=raw, needs_semantic=True)
        )

    def classify_batch(task, inputs):
        is_entity = inputs["channel"] == "E"
        row = inputs["records"][0]
        return {
            "records": [
                {
                    "record_id": row["id"],
                    "kind": "exception",
                    "reason": "同一分类格式义务",
                    "bindings": [
                        {
                            "step_id": "B2" if is_entity else "B7",
                            "target": "entity" if is_entity else "interface",
                            "field_id": None if is_entity else field["id"],
                            "key": "api.data.format",
                            "entity_id": "Category" if is_entity else None,
                            "attribute": "category_id" if is_entity else None,
                            "condition": row["condition"],
                            "expected": row["expected"],
                        }
                    ],
                }
            ]
        }

    classify(bundle, classify_batch)
    e = bundle["channels"]["E"]["scenarios"][0]
    gt = bundle["channels"]["GT"]["scenarios"][0]
    assert e["step_id"] == gt["step_id"] == "B1"
    assert (e["failure_step_id"], gt["failure_step_id"]) == ("B2", "B7")
    assert binding(e) == binding(gt)


def test_legacy_command_revision_keeps_historical_anchor():
    bundle = build_cases(BROWSE, profile="command-interaction-v1")[0]
    assert [
        s["step_id"]
        for s in bundle["channels"]["G"]["scenarios"]
        if s["condition"] == "pageSize > 100"
    ] == ["B2"]


def test_repeated_interface_is_a_source_link_after_core_round_trip(tmp_path):
    from shutil import copytree

    from scene_completion.analysis.ssd.entity_semantics import infer
    from scene_completion.analysis.ssd.operation_units import resolve
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE

    root = tmp_path / "raw"
    copytree(BROWSE, root)
    original = next(root.rglob("SysOperation.json"))
    value = json.loads(original.read_text(encoding="utf8"))
    main = next(iter(value["operations"].values()))
    repeated = deepcopy(main["interaction"][0])
    repeated["id"] = "B7"
    main["interaction"].append(repeated)
    main["Order"].append({"kind": "interaction", "ref": "B7"})
    original.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")
    tree = root / "功能树.json"
    tree_value = json.loads(tree.read_text(encoding="utf8"))
    product = tree_value["functions"][0]["srLayer"]["entities"][0]
    status = next(a for a in product["attributes"] if a["name"] == "status")
    status["constraints"].append({"rule": "状态不允许修改"})
    tree.write_text(json.dumps(tree_value, ensure_ascii=False), encoding="utf8")
    core = tmp_path / "core"
    convert(root, core, profile=COMMAND_OPERATION_PROFILE)
    assert validate_core(core)["valid"]
    bundle = build_cases(core)[0]
    resolve(
        bundle,
        lambda _, inputs: {
            "operations": [
                {
                    "unit_id": u["id"],
                    "step_id": u["step_id"],
                    "crud": ["create", "update"]
                    if u.get("command_id") == "CATALOG-SEARCH"
                    else ["read"],
                    "reason": "夹具操作范围",
                }
                for u in inputs["units"]
            ]
        },
    )
    infer(bundle, None)
    binding = bundle["command_bindings"]["CATALOG-SEARCH"]
    by_id = {s["id"]: s for s in bundle["steps"]}
    assert binding["primary_step_id"] == "B3"
    assert binding["occurrences"] == ["B3", "B7"]
    assert binding["entity_ids"] == ["Product"]
    assert by_id["B7"]["api_id"] is None
    assert by_id["B7"]["call_command_id"] == "CATALOG-SEARCH"
    assert by_id["B7"]["data"] == []
    assert by_id["B7"]["operation"]["kinds"] == []
    immutable = [
        r
        for r in bundle["channels"]["G"]["scenarios"]
        if r.get("variant_id") == "immutable_attribute"
    ]
    assert [(r["step_id"], r["attribute"]) for r in immutable] == [("B3", "status")]
    assert bundle["registry"]["definitions"][immutable[0]["key"]]["layer"] == "base"


def test_split_commands_name_alignment_and_operation_audit(tmp_path):
    import json
    from copy import deepcopy
    from shutil import copytree

    from scene_completion.analysis.ssd.entity_semantics import classify
    from scene_completion.analysis.ssd.generation import apply_result, batches
    from scene_completion.analysis.ssd.operation_units import resolve, validate_result
    from scene_completion.analysis.ssd.pipeline import _person
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
    from scene_completion.domain.ssd.matching import binding, semantic_candidates

    root = tmp_path / "raw"
    copytree(BROWSE, root)
    tree_path = root / "功能树.json"
    tree = json.loads(tree_path.read_text(encoding="utf8"))
    case = tree["functions"][0]
    case.update(functionId="TREE-900", name=" 浏览商品 ")
    commands = case["srLayer"]["commands"]
    commands[0].update(method="POST", name="创建商品")
    ird = ("name", "method", "path", "service")
    case["rrLayer"] = {
        "commands": [
            {"apiId": c["apiId"], **{k: c.pop(k) for k in ird if k in c}} for c in commands
        ]
    }
    tree_path.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf8")

    behavior = next(root.rglob("SysOperation.json"))
    value = json.loads(behavior.read_text(encoding="utf8"))
    original = next(iter(value["operations"].values()))
    actor = "AI原生应用开发者"
    role_quote = f"actor-001|{actor}|actor|主(人)|。CatalogService 是服务。"
    original["participant"] = {
        "U": {"name": actor, "kind": "external", "source_refs": [{"quote": role_quote}]},
        "M": {"name": "商城", "kind": "internal"},
        "DB": {
            "name": "CatalogService",
            "kind": "external",
            "technology": "database",
            "source_refs": [{"quote": role_quote}],
        },
    }
    original.update(system_event=[], action=[], system_response=[])
    original["interaction"] = [
        {"id": "R1", "sender": "U", "receiver": "M", "content": "提交商品申请"},
        {"id": "D1", "sender": "M", "receiver": "DB", "content": "保存商品"},
        {"id": "D2", "sender": "M", "receiver": "DB", "content": "重试保存商品"},
        {"id": "D3", "sender": "M", "receiver": "DB", "content": "读取商品"},
    ]
    original["Order"] = [
        {"kind": "interaction", "ref": row["id"]} for row in original["interaction"]
    ]
    value["operations"] = {"main": original}
    value["use_case_id"] = "BEHAVIOR-99"
    behavior.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")

    recovered = root / "recovered_usecases.json"
    data = json.loads(recovered.read_text(encoding="utf8"))
    gt = data[0]
    gt["id"] = "TEST-900"
    gt["extensions"] = [
        {
            "id": f"EXT-{i}",
            "condition": f"请求字段校验样本 {i}",
            "expected_result": "拒绝",
            "extend_at_main": {"after": "R1"},
        }
        for i in range(10)
    ] + [
        {
            "id": "IDEMP",
            "condition": "两次提交相同创建请求",
            "expected_result": "只创建一条记录",
            "extend_at_main": {"after": "R1"},
        },
        *[
            {"id": f"REST-{i}", "condition": f"其他测试 {i}", "expected_result": "结果"}
            for i in range(5)
        ],
    ]
    recovered.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
    target = tmp_path / "core"
    assert convert(root, target, profile=COMMAND_OPERATION_PROFILE)["output"]
    architecture = json.loads((target / "architecture.json").read_text(encoding="utf8"))
    assert {party["id"]: party["kind"] for party in architecture["elements"]} == {
        "U": "external_actor",
        "M": "internal_service",
        "DB": "external_service",
    }
    bundle = build_cases(target, generate=False)[0]
    assert bundle["case"]["id"] == "BEHAVIOR-99"
    assert bundle["function_tree_case_id"] == "TREE-900"
    assert bundle["test_source_case_id"] == "TEST-900"
    assert len(bundle["test_import_records"]) == 16
    assert bundle["steps"][0]["sender"]["type"] == "human"
    assert bundle["steps"][1]["receiver"]["type"] == "service"
    assert (
        _person("U", {"U": {**original["participant"]["U"], "kind_override": "external_service"}})[
            "type"
        ]
        == "service"
    )
    assert bundle["commands"][0]["method"] == "POST"
    assert len(bundle["commands"][0]["source_refs"]) >= 2

    def model(task, inputs):
        assert task == "ssd-operation-units"
        payload = {
            "operations": [
                {
                    "unit_id": u["id"],
                    "step_id": (
                        "R1" if u.get("command_id") == commands[0]["apiId"] else u["step_id"]
                    ),
                    "crud": (
                        ["create", "read"]
                        if u["kind"] == "external"
                        else ["create", "update"]
                        if u.get("command_id") == commands[0]["apiId"]
                        else ["create"]
                    ),
                    "reason": "按业务动作核对",
                }
                for u in inputs["units"]
            ]
        }
        return validate_result(payload, inputs)

    resolve(bundle, model)
    a, b = [c["apiId"] for c in commands]
    assert (
        bundle["command_bindings"][a]["primary_step_id"]
        == bundle["command_bindings"][b]["primary_step_id"]
        == "R1"
    )
    assert bundle["command_bindings"][a]["binding_source"] == "semantic"
    assert bundle["command_bindings"][b]["binding_source"] == "step1_fallback"
    assert [s["api_id"] for s in bundle["steps"]] == [a, None, None, None]
    units = bundle["operation_units"]
    assert [(u["step_id"], u["occurrences"]) for u in units if u["kind"] == "external"] == [
        ("D1", ["D1", "D2", "D3"]),
    ]
    bundle["channels"]["G"] = generate_g(bundle)
    key = "service.crud.create.idempotency"
    g = [row for row in bundle["channels"]["G"]["scenarios"] if row["key"] == key]
    assert [row["step_id"] for row in g] == ["R1", "R1", "D1"]
    assert len({binding(row) for row in g}) == 3
    assert any(row.get("applicable_operations") == ["create", "update"] for row in g)
    resources = [
        row
        for row in bundle["channels"]["G"]["concerns"]
        if row["step_id"] == "D1" and row.get("applicable_operations") == ["create", "read"]
    ]
    assert len(resources) == 1
    assert set(resources[0]["concern_keys"]) == {
        "service.query_retrieval.resource_existence",
        "service.crud.create.resource_existence",
    }
    for concern in ("service.base.availability", "database.special_characters"):
        assert [
            s["step_id"] for s in bundle["channels"]["G"]["concerns"] if s["key"] == concern
        ] == ["D1"]
    assert not any(step["operation"]["kinds"] for step in bundle["steps"][2:])

    selected = next(u for u in units if u.get("command_id") == a)

    def classifier(_, inputs):
        result = []
        for row in inputs["records"]:
            condition = row["condition"]
            kind = "exception"
            bindings = []
            if condition.startswith("请求字段"):
                field = next(f for f in inputs["interface_fields"] if f["command_id"] == a)
                bindings = [
                    {
                        "step_id": "R1",
                        "target": "interface",
                        "field_id": field["id"],
                        "key": "api.data.range",
                        "entity_id": None,
                        "attribute": None,
                        "condition": condition,
                        "expected": "拒绝",
                    }
                ]
            elif condition.startswith("两次"):
                bindings = [
                    {
                        "step_id": "R1",
                        "target": "receiver",
                        "field_id": None,
                        "key": key,
                        "entity_id": None,
                        "attribute": None,
                        "operation_unit_id": selected["id"],
                        "condition": condition,
                        "expected": "只创建一条记录",
                    }
                ]
            else:
                kind = (
                    "normal"
                    if condition.endswith(("0", "1"))
                    else "out_of_scope"
                    if condition.endswith("2")
                    else "pending"
                )
            result.append(
                {
                    "record_id": row["id"],
                    "kind": kind,
                    "reason": "核对测试条件",
                    "bindings": bindings,
                }
            )
        return {"records": result}

    classify(bundle, classifier)
    rows = bundle["source_classifications"]["GT"]
    assert len(rows) == 16
    assert {kind: sum(r["kind"] == kind for r in rows) for kind in {r["kind"] for r in rows}} == {
        "exception": 11,
        "normal": 2,
        "out_of_scope": 1,
        "pending": 2,
    }
    gt = next(row for row in bundle["channels"]["GT"]["scenarios"] if row["key"] == key)
    governing = next(row for row in g if row["operation_unit_id"] == selected["id"])
    assert binding(gt) == binding(governing)
    assert any(
        c["left_id"] == gt["id"] and c["right_id"] == governing["id"]
        for c in semantic_candidates(bundle)
    )

    packet = next(
        row for row in batches(bundle) if governing["id"] in {r["id"] for r in row["templates"]}
    )
    payload = {
        "analyses": [{"scenario_id": row["id"], "analysis": "分析"} for row in packet["templates"]],
        "supplements": [
            {
                "concern_id": governing["concern_ids"][0],
                "condition": "重传后生成第二条商品",
                "expected": "禁止新增",
                "analysis": "同一重复请求",
            }
        ],
    }
    apply_result(bundle, packet, deepcopy(payload))
    assert sum(r["key"] == key for r in bundle["channels"]["G"]["scenarios"]) == 3


@pytest.mark.parametrize(
    "reference",
    [
        {"doc": "designDocument", "location": "L1726-L1726", "quote": "唯一的原文引文。"},
        {"path": "/supplier/originals/document.md", "line": "L2", "quote": "唯一的原文引文。"},
        r"C:\supplier\originals\document.md:L2 - 唯一的原文引文。",
    ],
)
def test_named_originals_excel_ranges_and_duplicate_files_survive_conversion(tmp_path, reference):
    from shutil import copytree
    from zipfile import ZipFile

    from scene_completion.analysis.ssd.pipeline import origin_documents
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
    from scene_completion.inputs.provenance.ssd_sources import Sources

    root = tmp_path / "input"
    copytree(BROWSE, root)
    originals = root / "originals"
    originals.mkdir()
    workbook = originals / "原始用例.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="测试用例" r:id="r1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            '<row r="120"><c r="O120" t="inlineStr"><is><t>只创建一次</t></is></c>'
            '<c r="P120" t="inlineStr"><is><t>相邻文本</t></is></c></row></sheetData></worksheet>',
        )
    docs = [{"path": "originals/原始用例.xlsx", "role": "test", "aliases": ["testing"]}]
    for place in (root, originals):
        (place / "duplicate.md").write_text("同名文档\n", encoding="utf8")
        docs.append({"path": (place / "duplicate.md").relative_to(root).as_posix(), "role": "RR"})
    spec = originals / "document.md"
    spec.write_text(
        "标题\n唯一的原文引文。\n" + "说明\n" * 18 + "异常原文跨行\n并指明参数错误。\n",
        encoding="utf8",
    )
    docs.append({"path": "originals/document.md", "role": "SR", "aliases": ["designDocument"]})
    (root / "source-documents.json").write_text(json.dumps({"documents": docs}), encoding="utf8")
    behavior = next(root.rglob("SysOperation.json"))
    operation = json.loads(behavior.read_text(encoding="utf8"))
    main = next(iter(operation["operations"].values()))
    declared = [
        reference,
        {"doc": "missing.md", "location": "L35", "quote": "暂未提供原件"},
    ]
    main["interaction"][0]["source_refs"] = declared
    main["participant"]["MALL"]["source_refs"] = [
        {
            "document": "designDocument",
            "start_line": 6000,
            "end_line": 6000,
            "quote": "唯一的原文引文。",
        }
    ]
    operation["operations"]["SC_EX_PAGE_SIZE_HIGH"]["source_refs"] = [
        {
            "document": r"D:\supplier\document.md",
            "start_line": 1,
            "end_line": 1,
            "quote": "异常原文跨行并指明参数错误。",
        }
    ]
    behavior.write_text(json.dumps(operation, ensure_ascii=False), encoding="utf8")
    core = tmp_path / "core"
    assert convert(root, core, profile=COMMAND_OPERATION_PROFILE)["output"]
    assert validate_core(core)["valid"]
    assert (core / "originals/原始用例.xlsx").read_bytes() == workbook.read_bytes()
    from scene_completion.inputs.documents.input_bundles import discover

    _, material = discover(directory=str(core))
    assert any(f["relative_path"] == "originals/原始用例.xlsx" for f in material.values())
    case = build_cases(core)[0]
    e_sources = [
        ref
        for row in case["channels"]["E"]["pending"]
        for ref in row["source_refs"]
        if ref.get("kind") == "origin"
    ]
    assert any(
        ref["origin"]["document"] == "originals/document.md"
        and ref["start_line"] == 21
        and ref["end_line"] == 22
        and ref["quote"] == "异常原文跨行\n并指明参数错误。"
        for ref in e_sources
    )
    mall = case["steps"][0]["receiver"]
    assert mall["source_refs"][0]["start_line"] == 6000
    assert mall["original_refs"][0]["start_line"] == 2
    mixed_refs = [r for step in case["steps"] for r in step["source_refs"]]
    assert any(r["kind"] == "origin" and r["quote"] == "唯一的原文引文。" for r in mixed_refs)
    assert any(
        r.get("declared_source") == declared[1] and "missing.md" in r["origin"]["reason"]
        for r in mixed_refs
    )
    sources = Sources(core, origin_documents(core))
    result = sources.trace(
        {"doc": "testing", "location": "测试用例!A120:O120", "quote": "只创建一次"}
    )
    assert result["match"] == "exact" and result["start_line"] == 120
    assert result["cell_range"] == "A120:O120"
    assert (
        sources.trace({"doc": "testing", "location": "测试用例!A120:O120", "quote": "相邻文本"})[
            "match"
        ]
        == "pending"
    )
    assert (
        "无效"
        in sources.trace(
            {"doc": "testing", "location": "测试用例!A120:0120", "quote": "只创建一次"}
        )["reason"]
    )
    assert (
        sources.trace({"doc": "duplicate.md", "location": "L1-L1", "quote": "同名文档"})["match"]
        == "pending"
    )
    found = sources.trace(declared[0])
    assert found["match"] in {"exact", "located"} and found["start_line"] == 2
    assert found["document"] == "originals/document.md"


def test_function_tree_uses_each_constraint_and_tag_citation(tmp_path):
    from shutil import copytree

    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE

    raw = tmp_path / "source"
    copytree(BROWSE, raw)
    original = raw / "product.md"
    lines = [
        '"productId": "P10001"',
        "商品实体属性的声明位置",
        "下限引用的实体约束",
        "上限引用的实体约束",
        "接口下限的独立约束",
        "接口上限的独立约束",
        "标签规定商品号必填",
        '"productId": "P10001"',
    ]
    original.write_text("\n".join(lines), encoding="utf8")
    (raw / "source-documents.json").write_text(
        json.dumps({"documents": [{"path": "product.md", "role": "SR", "aliases": ["srSpec"]}]}),
        encoding="utf8",
    )

    def cite(line, quote=None):
        return {"doc": "srSpec", "line": f"L{line}", "quote": quote or lines[line - 1]}

    tree = raw / "功能树.json"
    payload = json.loads(tree.read_text(encoding="utf8"))
    sr = payload["functions"][0]["srLayer"]
    product_id = sr["entities"][0]["attributes"][0]
    product_id.update(
        source=cite(2),
        tags=[{"name": "必填", "source": cite(7)}],
        constraints=[{"rule": "唯一编号", "error": None, "source": cite(2, lines[0])}],
    )
    category = sr["entities"][1]["attributes"][0]
    wire = next(a for a in sr["commands"][0]["attributes"] if a["name"] == "categoryId")
    for field, first in ((category, 3), (wire, 5)):
        field.update(
            source={**field["source"], **cite(2)},
            constraints=[
                {"rule": rule, "source": cite(n)}
                for rule, n in ((">= 1", first), ("<= 100", first + 1))
            ],
        )
    tree.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf8")
    core = tmp_path / "core"
    convert(raw, core, profile=COMMAND_OPERATION_PROFILE)
    bundle = build_cases(core)[0]
    document = next(d["id"] for d in bundle["documents"] if d["name"] == "product.md")

    def cited_lines(refs):
        return sorted({r["start_line"] for r in refs if r["document_id"] == document})

    product_id = bundle["entities"][0]["attributes"][0]
    unique_rule = product_id["unresolved"][0]
    assert unique_rule["text"] == "唯一编号"
    assert cited_lines(unique_rule["source_refs"]) == [1]
    assert unique_rule["source_refs"][0]["origin"]["match"] == "located"
    assert unique_rule["source_refs"][1]["json_pointer"].endswith("/constraints/0")
    assert cited_lines(
        next(a for a in product_id["atoms"] if a["operation"] == "required")["source_refs"]
    ) == [7]
    rows = {
        row["condition"].split("：", 1)[-1]: cited_lines(row["source_refs"])
        for row in bundle["channels"]["G"]["scenarios"]
        if row.get("attribute") == "category_id" and row["key"] == "api.data.range"
    }
    assert rows == {"category_id < 1": [3, 5], "category_id > 100": [4, 6]}


def test_independent_evidence_aligns_many_to_final_g_and_falls_back(tmp_path):
    from scene_completion.analysis.ssd import grounding
    from scene_completion.analysis.validation import validate_result
    from scene_completion.application import ssd_revision_service
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
    from scene_completion.domain.ssd import metrics, validation
    from scene_completion.domain.ssd.construction import add_concern, add_scenario
    from scene_completion.review.offline import adoption

    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    bundle["gt_source_available"] = True
    step = bundle["steps"][0]
    fields = {f["name"]: f for f in step["data"]}
    out = bundle["channels"]["G"]
    auth = add_concern(out, bundle, "G", step, "human.authentication", "sender")
    add_scenario(out, auth, "凭证格式无效", "拒绝", [])
    required = []
    for name in ("page", "pageSize"):
        concern = add_concern(
            out, bundle, "G", step, "api.data.completeness", "data", field=fields[name]
        )
        required.append(add_scenario(out, concern, name + " 缺失", "拒绝", [])["id"])

    def raw(ident, condition, expected="拒绝", step_id="B2"):
        return pending(
            ident,
            condition,
            needs_semantic=True,
            original={
                "id": ident,
                "extension_id": ident,
                "condition": condition,
                "expected": expected,
                "failure_step_id": step_id,
                "source_refs": [],
            },
        )

    bundle["channels"]["E"] = channel()
    bundle["channels"]["GT"] = channel()
    bundle["channels"]["E"]["pending"] = [
        raw("E-config", "配置不完整", step_id=None),
        raw("E-bounds", "pageSize < 1；pageSize > 100"),
    ]
    bundle["channels"]["GT"]["pending"] = [
        raw("GT-auth", "无效凭证"),
        raw("GT-high", "pageSize > 100"),
        raw("GT-keyword", "keyword 比协议允许长度更长"),
        raw("GT-normal", "合法的上边界被接受", "成功"),
    ]
    definitions = {
        "配置不完整": "api.data.completeness",
        "无效凭证": "human.authentication",
        "pageSize < 1": "api.data.range",
        "pageSize > 100": "api.data.range",
        "keyword 比协议允许长度更长": "api.data.length",
    }

    def identify(task, inputs):
        assert task == grounding.CLASSIFY
        assert "G" not in inputs and "parts" not in inputs
        assert len(inputs["steps"]) == len(bundle["steps"])
        prefix = inputs["channel"] + "-"
        assert all(row["id"].startswith(prefix) for row in inputs["records"])
        return validate_result(
            task,
            {
                "records": [
                    {
                        "record_id": row["id"],
                        "reason": "依据本方原文分类",
                        "kind": "normal" if row["id"] == "GT-normal" else "exception",
                        "parts": [
                            {
                                "condition": condition,
                                "expected": row["expected"],
                                "keys": [definitions[condition]],
                            }
                            for condition in row["condition"].split("；")
                            if condition in definitions
                        ],
                    }
                    for row in inputs["records"]
                ]
            },
            inputs,
        )

    grounding.classify(bundle, identify)
    expiry = add_scenario(out, auth, "凭证过期", "拒绝", [])["id"]
    assert bundle["channels"]["GT"]["scenarios"] == []

    def compare(task, inputs):
        assert task == grounding.ALIGN
        results = []
        for part in inputs["parts"]:
            condition = part["condition"]
            if condition == "配置不完整":
                assert set(required) <= {g["id"] for g in part["candidates"]}
            if condition == "无效凭证":
                assert expiry in {g["id"] for g in part["candidates"]}
            if condition == "pageSize > 100":
                assert not any(g["condition"] == "pageSize < 1" for g in part["candidates"])
            matches = [
                {
                    "candidate_id": g["id"],
                    "status": "partial"
                    if condition in {"配置不完整", "无效凭证"}
                    else "full"
                    if condition == g["condition"]
                    else "none",
                    "reason": "按来源和失败条件核对",
                }
                for g in part["candidates"]
            ]
            fallback = None
            if "keyword" in condition:
                fallback = {
                    "step_id": "B1",
                    "target": "interface",
                    "key": "api.data.length",
                    "entity_id": None,
                    "attribute": None,
                    "field_id": fields["keyword"]["id"],
                    "operation_unit_id": None,
                }
            results.append(
                {
                    "part_id": part["id"],
                    "matches": matches,
                    "fallback": fallback,
                    "reason": "依据来源",
                }
            )
        return validate_result(task, {"parts": results}, inputs)

    grounding.align(bundle, compare)
    bundle = validation.validate(bundle)
    gt = {r["condition"]: r for r in bundle["channels"]["GT"]["scenarios"]}
    assert len(gt) == 3
    assert gt["无效凭证"]["step_id"] == "B1"
    assert gt["无效凭证"]["failure_step_id"] == "B2"
    assert len(bundle["channels"]["E"]["scenarios"]) == 3
    assert {
        r["condition"]
        for r in bundle["channels"]["E"]["scenarios"]
        if "E-bounds" in r["source_record_ids"]
    } == {"pageSize < 1", "pageSize > 100"}
    assert not bundle["channels"]["GT"]["pending"]
    assert not bundle["channels"]["E"]["pending"]
    config = next(r for r in bundle["channels"]["E"]["scenarios"] if r["condition"] == "配置不完整")
    assert set(required) <= {
        d["left_id"]
        for d in bundle["decisions"]
        if d["level"] == "scenario" and d["right_id"] == config["id"] and d["status"] == "partial"
    }
    assert metrics.analyze(bundle)["scenario_diagnostic"]["counts"]["GT"] == 3
    ssd_revision_service.publish(tmp_path, bundle)
    categories = adoption.export_payload(tmp_path)["items"][0]["categories"]
    assert expiry in {row["cells"]["G"][0]["id"] for row in categories["covered"]}
    assert gt["keyword 比协议允许长度更长"]["id"] in {
        row["cells"]["GT"][0]["id"] for row in categories["gt_only"]
    }


def test_grounding_admits_exact_fragments_and_isolates_duplicate_and_foreign_parts():
    from scene_completion.analysis.ssd import grounding
    from scene_completion.analysis.validation import validate_result

    bundle = build_cases(BROWSE, profile=COMMAND_PROFILE)[0]
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    cases = [
        (
            "mixed",
            "keyword 为空时拒绝；合法 keyword 通过",
            "返回 400；合法返回 200；保留未创建状态",
        ),
        ("split", "字段为空或字段无效", "拒绝"),
        ("conflict", "字段为空且配置有效；配置不存在", "拒绝"),
        ("pass", "合法边界通过", "返回 200"),
    ]
    for record_id, condition, expected in cases:
        original = {
            "id": record_id,
            "condition": condition,
            "expected": expected,
            "source_refs": [],
        }
        bundle["channels"]["GT"]["pending"].append(
            pending(record_id, condition, original=original, needs_semantic=True)
        )
    key = "api.data.completeness"

    def part(condition, expected="拒绝"):
        return {"condition": condition, "expected": expected, "keys": [key]}

    mixed = {
        **part("", ""),
        "condition_fragments": [{"field": "condition", "index": None, "quote": "keyword 为空"}],
        "expected_fragments": [
            {"field": "expected", "index": None, "quote": quote}
            for quote in ("返回 400", "保留未创建状态")
        ],
    }

    def execute(task, inputs):
        assert task == grounding.CLASSIFY and inputs["channel"] == "GT"
        records = [
            {
                "record_id": rid,
                "kind": "exception" if parts else "normal",
                "reason": "原文判定",
                "parts": parts,
            }
            for rid, parts in (
                ("mixed", [mixed, mixed, part("不是本条原文")]),
                ("split", [part("字段为空或字段无效"), part("字段为空"), part("字段无效")]),
                ("conflict", [part("字段为空且配置有效"), part("字段为空"), part("配置不存在")]),
                ("pass", []),
                ("foreign", []),
            )
        ]
        with pytest.raises(ValueError, match="本批每个来源"):
            validate_result(task, {"records": records[1:]}, inputs)
        return validate_result(task, {"records": records}, inputs)

    grounding.classify(bundle, execute)
    by_id = {row["record_id"]: row for row in bundle["source_classifications"]["GT"]}
    assert set(by_id) == {rid for rid, _, _ in cases}
    (excerpt,) = by_id["mixed"]["parts"]
    assert (excerpt["condition"], excerpt["expected"]) == (
        "keyword 为空",
        "返回 400；保留未创建状态",
    )
    assert by_id["mixed"]["pending_parts"][0]["condition"] == "不是本条原文"
    assert [p["condition"] for p in by_id["split"]["parts"]] == ["字段为空", "字段无效"]
    assert [p["condition"] for p in by_id["conflict"]["parts"]] == ["配置不存在"]
    assert len(by_id["conflict"]["pending_parts"]) == 2
    assert by_id["pass"]["kind"] == "normal" and not by_id["pass"]["parts"]


def test_ground_align_uses_one_request_for_auth_fallback_and_validates_reason_paths():
    from scene_completion.analysis.ssd.entity_semantics import _steps
    from scene_completion.analysis.validation import validate_result

    steps = _steps(build_cases(BROWSE, profile=COMMAND_PROFILE)[0])
    human = "human.authentication"
    service = "service_relation.authentication"
    inputs = {
        "steps": steps,
        "parts": [{"id": "p1", "keys": [service], "candidates": [], "failure_step_id": "B2"}],
    }
    row = {
        "part_id": "p1",
        "matches": [],
        "reason": "入口请求校验失败",
        "fallback": {
            "step_id": "B1",
            "key": service,
            "target": "receiver",
            "entity_id": None,
            "attribute": None,
            "field_id": None,
            "operation_unit_id": None,
        },
    }
    task = "ssd-ground-align"
    result = validate_result(task, {"parts": [row], "reason": "多余的总体说明"}, inputs)
    assert set(result) == {"parts"}
    fallback = result["parts"][0]["fallback"]
    assert (fallback["step_id"], fallback["key"], fallback["target"]) == ("B1", human, "sender")
    wrong = {**row, "fallback": {**row["fallback"], "step_id": "B3"}}
    rejected = validate_result(task, {"parts": [wrong]}, inputs)["parts"][0]
    assert rejected["fallback"] is None and "待定位" in rejected["reason"]
    with pytest.raises(ValueError, match="p1 缺少对齐依据"):
        validate_result(
            task,
            {
                "parts": [{k: v for k, v in row.items() if k != "reason"}],
                "reason": "不能代替片段依据",
            },
            inputs,
        )
    with pytest.raises(ValueError, match="Additional properties"):
        validate_result(task, {"parts": [row], "unrelated": "不允许"}, inputs)


def test_authentication_alignment_preserves_branch_and_distinguishes_actual_failure(tmp_path):
    import shutil

    from scene_completion.analysis.ssd import grounding
    from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
    from scene_completion.domain.ssd.construction import add_concern, add_scenario
    from scene_completion.inputs.documents.input_bundles import apply, discover
    from scene_completion.inputs.imports.artifact_imports import snapshot
    from tests.support.input_bundles import project

    material = tmp_path / "supplier"
    shutil.copytree(BROWSE, material)
    path = next(material.rglob("SysOperation.json"))
    behavior = json.loads(path.read_text(encoding="utf-8"))
    branches = behavior["operations"]
    base = deepcopy(branches["SC_EX_PAGE_SIZE_HIGH"])
    base.pop("source_refs")
    base["system_response"][0]["message"] = "拒绝认证失败的请求"
    for name, hint, message in (
        ("E4", "旧异常分支中的 ID", "顾客调用商城时认证失败"),
        ("E5", {"ref": "B3"}, "入口请求认证失败"),
        ("E6", None, "认证失败"),
        ("E7", {"step_id": "B3"}, "已声明校验步的认证失败"),
    ):
        branches[name] = {**base, "ID": name, "guard": message, "failure_step_hint": hint}
    branches["E5"].update(extend_at_main={"ref": "B3"}, resume_at_main={"ref": "B4"})
    branches["E7"]["failure_step_id"] = "B2"
    path.write_text(json.dumps(behavior, ensure_ascii=False, indent=2), encoding="utf-8")
    output = tmp_path / "core"
    assert convert(material, output, profile=COMMAND_OPERATION_PROFILE)["output"]
    assert validate_core(output)["valid"]
    preview, files = discover(directory=str(output))
    assert preview["valid"] and preview["authoring_case_count"] == 1
    frozen_path = next(
        f["relative_path"] for f in files.values() if "source-evidence" in f["relative_path"]
    )
    assert frozen_path.endswith("-behavior.json")
    service, workbench = project(tmp_path / "workbench")
    assert apply(service, workbench, preview, files)["saved"]
    assert not any(row.get("behavior_product") for row in snapshot(workbench))
    manifest = json.loads((workbench / "imports/ssd-input.json").read_text(encoding="utf-8"))
    bundle = build_cases(workbench / manifest["path"])[0]
    bundle["channels"]["GT"] = channel()
    pending_rows = bundle["channels"]["E"]["pending"]
    bundle["channels"]["E"]["pending"] = [r for r in pending_rows if "认证" in r["condition"]]

    human_step = next(s for s in bundle["steps"] if s["id"] == "B1")
    service_step = next(s for s in bundle["steps"] if s["id"] == "B3")
    bundle["channels"]["G"] = generated = channel()
    human = add_concern(generated, bundle, "G", human_step, "human.authentication", "sender")
    service = add_concern(
        generated, bundle, "G", service_step, "service_relation.authentication", "receiver"
    )
    human_id = add_scenario(generated, human, "调用方认证失败", "拒绝认证失败的请求", [])["id"]
    service_id = add_scenario(generated, service, "调用方认证失败", "拒绝认证失败的请求", [])["id"]

    def classify_auth(task, inputs):
        assert task == grounding.CLASSIFY
        assert {s["id"] for s in inputs["steps"]} >= {"B1", "B2", "B3"}
        assert next(s for s in inputs["steps"] if s["id"] == "B2")["validates"] == ["B1"]
        decision = []
        for row in inputs["records"]:
            if row["condition"].startswith("顾客"):
                assert row["failure_step_hint"] == "旧异常分支中的 ID"
                assert row["failure_step_id"] is None
                assert row["branch"]["system_response"][0]["sender"] == "MALL"
                assert row["branch"]["source_pointers"][0]["json_pointer"] == "/operations/E4"
            if row["condition"].startswith("入口"):
                assert row["failure_step_hint"] == {"ref": "B3"}
                assert row["failure_step_id"] is None
                assert row["branch"]["extend_at_main"] == {"ref": "B3"}
                assert row["branch"]["resume_at_main"] == {"ref": "B4"}
            if row["condition"].startswith("已声明"):
                assert row["failure_step_id"] == "B2"
            decision.append(
                {
                    "record_id": row["id"],
                    "kind": "exception",
                    "reason": "判为认证失败，调用方待核对",
                    "parts": [
                        {
                            "condition": row["condition"],
                            "expected": row["expected"],
                            "keys": ["service_relation.authentication"],
                        }
                    ],
                }
            )
        return {"records": decision}

    grounding.classify(bundle, classify_auth)

    def align_auth(task, inputs):
        assert task == grounding.ALIGN
        if inputs.get("phase") == "independent_mount":
            [part] = inputs["parts"]
            assert part["condition"] == "认证失败"
            assert {c["step_id"] for c in part["mount_options"]} == {"B1", "B3"}
            return {
                "parts": [
                    {
                        "part_id": part["id"],
                        "matches": [],
                        "fallback": None,
                        "reason": "无法核实哪一方发起认证",
                    }
                ]
            }
        results = []
        for part in inputs["parts"]:
            condition = part["condition"]
            actual = "B2" if condition.startswith(("入口", "已声明")) else None
            ids = {g["id"] for g in part["candidates"]}
            assert ids == ({human_id} if condition.startswith("已声明") else {human_id, service_id})
            confirmed = condition != "认证失败"
            matches = [
                {
                    "candidate_id": gid,
                    "status": "full" if confirmed and gid == human_id else "none",
                    "reason": "按认证调用主体核对",
                }
                for gid in sorted(ids)
            ]
            row = {
                "part_id": part["id"],
                "matches": matches,
                "fallback": None,
                "reason": "顾客向商城发起请求" if confirmed else "无法核实哪一方发起认证",
                "failure_step_id": actual,
                "failure_step_reason": "校验步 B2 明确关联 B1" if actual else "原文未声明失败步骤",
            }
            if condition.startswith("顾客"):
                with pytest.raises(ValueError, match="主成功流"):
                    grounding.validate_result(
                        task,
                        {"parts": [{**row, "failure_step_id": "E4"}]},
                        {**inputs, "parts": [part]},
                    )
                ambiguous = grounding.validate_result(
                    task,
                    {"parts": [{**row, "matches": [{**m, "status": "full"} for m in matches]}]},
                    {**inputs, "parts": [part]},
                )["parts"][0]
                assert {m["status"] for m in ambiguous["matches"]} == {"none"}
                assert "同一调用边界" in ambiguous["reason"] and ambiguous["fallback"] is None
            if condition.startswith("已声明"):
                with pytest.raises(ValueError, match="主成功流"):
                    grounding.validate_result(
                        task,
                        {"parts": [{**row, "failure_step_id": "B3"}]},
                        {**inputs, "parts": [part]},
                    )
            results.append(row)
        return {"parts": results}

    grounding.align(bundle, align_auth)
    rows = {r["condition"]: r for r in bundle["channels"]["E"]["scenarios"]}
    e4 = rows["顾客调用商城时认证失败"]
    assert e4["step_id"] == "B1"
    assert e4["key"] == "human.authentication"
    assert e4["failure_step_pending"] and not e4.get("failure_step_id")
    assert e4["failure_step_reason"] == "原文未声明失败步骤"
    assert rows["入口请求认证失败"]["failure_step_id"] == "B2"
    assert rows["入口请求认证失败"]["step_id"] == "B1"
    assert rows["已声明校验步的认证失败"]["failure_step_id"] == "B2"
    assert any(
        d["level"] == "scenario" and d["left_id"] == human_id and d["right_id"] == e4["id"]
        for d in bundle["decisions"]
    )
    assert [r["condition"] for r in bundle["channels"]["E"]["pending"]] == ["认证失败"]
    refs = {
        r["document_id"] for r in e4["source_refs"] if r.get("json_pointer") == "/operations/E4"
    }
    assert any(
        d["id"] in refs
        and d["name"].endswith("-behavior.json")
        and '"guard": "顾客调用商城时认证失败"' in d["content"]
        for d in bundle["documents"]
    )


@pytest.mark.parametrize("profile", [COMMAND_PROFILE, COMMAND_OPERATION_PROFILE])
def test_empty_exception_details_keep_other_five_gt_records(profile):
    from scene_completion.analysis.ssd import grounding
    from scene_completion.analysis.validation import validate_result
    from scene_completion.domain.ssd.construction import add_concern, add_scenario

    bundle = build_cases(BROWSE, profile=profile)[0]
    step = next(s for s in bundle["steps"] if s["id"] == "B1")
    field = next(f for f in step["data"] if f["name"] == "pageSize")
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    bundle["gt_source_available"] = True
    generated = bundle["channels"]["G"]
    key = "api.data.range"
    concern = add_concern(generated, bundle, "G", step, key, "data", field=field)

    expected = "拒绝"
    for i in range(1, 7):
        condition = "请求缺少 service-id" if i == 5 else f"pageSize 取 {100 + i} 超上界"
        record_id = f"GT{i}"
        refs = [{"document_id": "test", "start_line": i, "end_line": i, "kind": "test"}]
        bundle["channels"]["GT"]["pending"].append(
            pending(
                record_id,
                condition,
                refs,
                original={
                    "id": record_id,
                    "extension_id": record_id,
                    "condition": condition,
                    "expected": expected,
                    "source_refs": refs,
                },
                needs_semantic=True,
            )
        )
        if i != 5:
            add_scenario(generated, concern, condition, expected, [])

    def execute(task, inputs):
        if task == grounding.ALIGN:
            value = {
                "parts": [
                    {
                        "part_id": part["id"],
                        "reason": "测试条件与生成场景相同",
                        "matches": [
                            {
                                "candidate_id": candidate["id"],
                                "status": "full"
                                if candidate["condition"] == part["condition"]
                                else "none",
                                "reason": "比较分页数值",
                            }
                            for candidate in part["candidates"]
                        ],
                        "fallback": None,
                    }
                    for part in inputs["parts"]
                ]
            }
        else:
            assert len(inputs["records"]) == 6
            assert inputs["channel"] == "GT"
            modern = task == grounding.CLASSIFY
            detail_key = "parts" if modern else "bindings"
            records = []
            for row in inputs["records"]:
                detail = {"condition": row["condition"], "expected": expected}
                detail.update(
                    {"keys": [key]}
                    if modern
                    else {
                        "step_id": step["id"],
                        "target": "interface",
                        "key": key,
                        "field_id": field["id"],
                        "entity_id": None,
                        "attribute": None,
                    }
                )
                records.append(
                    {
                        "record_id": row["id"],
                        "kind": "exception",
                        "reason": "判为失败场景",
                        detail_key: [] if row["id"] == "GT5" else [detail],
                    }
                )
            value = {"records": records}
            with pytest.raises(ValueError, match="每个来源恰好"):
                validate_result(task, {"records": records[:4] + records[5:]}, inputs)
        # The transport validates the raw reply before the stage interprets it.
        validate_result(task, value, inputs)
        return value

    if profile == COMMAND_OPERATION_PROFILE:
        grounding.classify(bundle, execute)
        grounding.align(bundle, execute)
        assert (
            sum(d["level"] == "scenario" and d["status"] == "full" for d in bundle["decisions"])
            == 5
        )
    else:
        classify(bundle, execute)

    output = bundle["channels"]["GT"]
    assert {r["extension_id"] for r in output["scenarios"]} == {"GT1", "GT2", "GT3", "GT4", "GT6"}
    (unlocated,) = output["pending"]
    assert unlocated["id"] == "GT5"
    assert unlocated["condition"] == "请求缺少 service-id"
    assert unlocated["source_refs"][0]["start_line"] == 5
    assert "模型判为异常" in unlocated["reason"] and "待定位" in unlocated["reason"]
    assert not unlocated["needs_semantic"]
    assert bundle["gt_identification_run_complete"]


def test_source_manifest_is_authoritative_and_legacy_copies_are_content_checked(tmp_path):
    from scene_completion.analysis.ssd.pipeline import origin_documents
    from scene_completion.inputs.provenance.ssd_sources import Sources

    name = "系统需求_spec.md"
    original = tmp_path / name
    copied = tmp_path / "structure_model_fusion" / "RR" / name
    alias_collision = tmp_path / "RR-副本.md"
    copied.parent.mkdir(parents=True)
    original.write_text("# 需求\n原始引文\n", encoding="utf8")
    copied.write_bytes(original.read_bytes())
    trace = {"doc": name, "line": "L2", "quote": "原始引文"}

    def sources():
        return Sources(tmp_path, origin_documents(tmp_path))

    assert sources().trace(trace)["document"] == name
    copied.write_text("# 需求\n不同版本\n", encoding="utf8")
    assert sources().trace(trace)["match"] == "pending"
    alias_collision.write_text("# 其他文件\n未登记的引文\n", encoding="utf8")
    (tmp_path / "source-documents.json").write_text(
        json.dumps(
            {"documents": [{"path": name, "role": "RR", "aliases": [alias_collision.name]}]}
        ),
        encoding="utf8",
    )
    registered = sources()
    assert registered.trace(trace)["document"] == name
    assert registered.trace({**trace, "doc": alias_collision.name})["document"] == name
    assert (
        registered.trace({**trace, "doc": copied.relative_to(tmp_path).as_posix()})["match"]
        == "pending"
    )
    assert {d["name"] for d in registered.documents.values()} == {name}


@pytest.mark.parametrize("profile", [COMMAND_PROFILE, COMMAND_OPERATION_PROFILE])
def test_participant_aliases_mount_five_and_keep_one_record_pending(profile):
    from scene_completion.analysis.ssd import grounding
    from scene_completion.analysis.validation import validate_result

    bundle = build_cases(BROWSE, profile=profile)[0]
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    facts = {
        "GT1": ("B1", "human.authentication", "human"),
        "GT2": ("B3", "service_relation.authentication", "service"),
        "GT3": ("B1", "human.authorization", "sender"),
        "GT4": ("B3", "service_relation.authorization", "receiver"),
        "GT5": ("B2", "service.base.availability", "service"),
        "GT6": ("B1", "human.authentication", "sender"),
    }
    for rid in facts:
        condition = f"条件 {rid}"
        original = {"id": rid, "condition": condition, "source_refs": [], "extension_id": rid}
        bundle["channels"]["GT"]["pending"].append(
            pending(rid, condition, original=original, needs_semantic=True)
        )

    def binding(rid):
        step_id, key, target = facts[rid]
        return {
            "step_id": step_id,
            "key": key,
            "target": target,
            "entity_id": None,
            "attribute": None,
            "field_id": None,
            "operation_unit_id": None,
        }

    def execute(task, inputs):
        if task == grounding.ALIGN:
            value = {
                "parts": [
                    {
                        "part_id": item["id"],
                        "matches": [],
                        "fallback": binding(item["condition"].split()[-1]),
                        "reason": "依据对应步骤",
                    }
                    for item in inputs["parts"]
                ]
            }
        else:
            records = []
            for record in inputs["records"]:
                rid = record["id"]
                condition = {"condition": record["condition"], "expected": ""}
                detail = (
                    {"parts": [{**condition, "keys": [facts[rid][1]]}]}
                    if task == grounding.CLASSIFY
                    else {"bindings": [{**binding(rid), **condition}]}
                )
                records.append(
                    {"record_id": rid, "kind": "exception", "reason": "测试失败", **detail}
                )
            value = {"records": records}
        validate_result(task, value, inputs)
        return value

    if profile == COMMAND_OPERATION_PROFILE:
        grounding.classify(bundle, execute)
        grounding.align(bundle, execute)
    else:
        classify(bundle, execute)
    gt = bundle["channels"]["GT"]
    scenes = {r["extension_id"]: r for r in gt["scenarios"]}
    assert set(scenes) == {"GT1", "GT2", "GT3", "GT4", "GT6"}
    assert scenes["GT1"]["target"] == "sender"
    assert scenes["GT2"]["target"] == "receiver"
    (unlocated,) = gt["pending"]
    assert unlocated["id"] == "GT5" and "未唯一确定挂载方向" in unlocated["reason"]
    audit = {r["source_id"]: r for r in bundle["source_classifications"]["GT"]}
    assert audit["GT1"]["target_corrections"][0]["original_target"] == "human"
    assert audit["GT2"]["target_corrections"][0]["original_target"] == "service"
    assert audit["GT5"]["kind"] == "pending"


def test_resolve_classifies_each_participant_from_its_quotes_after_core_round_trip(tmp_path):
    from shutil import copytree

    from scene_completion.analysis.validation import validate_result
    from scene_completion.application.execution import Execution
    from scene_completion.workflow.ssd.resolve.stage import _resolve

    materials = tmp_path / "raw"
    copytree(BROWSE, materials)
    source = next(materials.rglob("SysOperation.json"))
    operation = json.loads(source.read_text(encoding="utf8"))
    people = operation["operations"]["browse_main_success"]["participant"]
    mall_quotes = [
        {"document": "sr", "quote": "MallAdminService 是商城内部软件单元，依赖商品目录服务。"},
        {"document": "structure", "quote": "MallAdminService 负责校验商城查询请求。"},
    ]
    people["MALL"].update(
        name="MallAdminService",
        role="外部服务",
        kind="internal",
        element_type="software_unit",
        source_refs=mall_quotes,
    )
    people["U"].update(
        name="AI原生应用开发者",
        kind="external_service",
        role="外部服务",
        source_refs=[{"document": "sr", "quote": "业务的交互发起人是个人开发者。"}],
    )
    people["CATALOG"].update(
        kind="internal",
        technology="database",
        source_refs=[{"document": "sr", "quote": "商城访问其边界之外的商品目录服务。"}],
    )
    source.write_text(json.dumps(operation, ensure_ascii=False), encoding="utf8")
    core = tmp_path / "core"
    assert convert(materials, core, profile=COMMAND_OPERATION_PROFILE)["output"]
    assert validate_core(core)["valid"]
    [bundle] = build_cases(core)
    assert bundle["steps"][0]["sender"]["type"] == "service"
    bundle["channels"]["GT"]["pending"].append(pending("gt-fixture-only", "GT-ONLY-SENTINEL"))

    calls = []

    def classify(packet):
        rows = {p["id"]: p for p in packet["input"]["participants"]}
        calls.append(tuple(rows))
        assert "GT-ONLY-SENTINEL" not in json.dumps(packet["input"])
        assert rows["MALL"]["kind"] == "internal"
        assert rows["MALL"]["role"] == "外部服务"
        assert rows["MALL"]["element_type"] == "software_unit"
        assert [r["quote"] for r in rows["MALL"]["source_refs"]] == [
            r["quote"] for r in mall_quotes
        ]
        decisions = {
            "participants": [
                {
                    "participant_id": pid,
                    "kind": kind,
                    "reason": "依据各自的参与者声明及引文",
                    "source_ref_ids": [rows[pid]["source_refs"][0]["id"]],
                }
                for pid, kind in (
                    ("MALL", "internal_service"),
                    ("U", "external_actor"),
                    ("CATALOG", "external_service"),
                )
            ]
        }
        forged = deepcopy(decisions)
        forged["participants"][0]["source_ref_ids"] = [rows["U"]["source_refs"][0]["id"]]
        with pytest.raises(ValueError, match="自己的原文"):
            validate_result(packet["task"], forged, packet["input"])
        duplicate = deepcopy(decisions)
        duplicate["participants"][0] = duplicate["participants"][1]
        with pytest.raises(ValueError, match="恰好"):
            validate_result(packet["task"], duplicate, packet["input"])
        return decisions

    ex = Execution(
        tmp_path / "run",
        mocks={
            "ssd-participant-classify": classify,
            "ssd-operation-units": lambda p: {
                "operations": [
                    {
                        "unit_id": row["id"],
                        "step_id": row["step_id"],
                        "crud": ["read"],
                        "reason": "查询",
                    }
                    for row in p["input"]["units"]
                ]
            },
            "ssd-entity-inference": lambda p: {
                "operations": [],
                "constraints": [
                    {"rule_id": row["id"], "state": "pending", "reason": "待核查", "bindings": []}
                    for row in p["input"]["constraints"]
                ],
            },
            "ssd-evidence-classify": lambda p: {
                "records": [
                    {"record_id": row["id"], "kind": "normal", "reason": "夹具", "parts": []}
                    for row in p["input"]["records"]
                ]
            },
        },
    )
    resolved = _resolve(ex, bundle, {"case": bundle["case"]["id"]})
    assert calls == [("U", "MALL", "CATALOG")]
    assert resolved["steps"][0]["sender"]["type"] == "human"
    assert all(
        party["classification_source"] == "ssd-participant-classify"
        for step in resolved["steps"]
        for party in (step["sender"], step["receiver"])
    )
    assert any(
        row["key"] == "service.base.availability" and row["step_id"] == "B3"
        for row in resolved["channels"]["G"]["concerns"]
    )
    assert any(
        row["key"] == "database.special_characters" and row["step_id"] == "B3"
        for row in resolved["channels"]["G"]["concerns"]
    )


def test_participant_manual_override_and_missing_evidence_keep_script_type():
    from scene_completion.workflow.ssd.input_conversion.sys_operation import _person
    from scene_completion.workflow.ssd.resolve.participants import classify

    original = {"role": "外部服务", "kind": "external_service"}
    sources = [{"quote": "已有原文，无法判断该服务是否属于当前系统。"}]
    values = {
        "manual": {**original, "kind_override": "internal_service", "source_refs": sources},
        "undecided": {**original, "source_refs": sources},
        "missing": original,
    }
    parties = {pid: _person(pid, values) for pid in values}
    bundle = {
        "case": {"id": "case", "name": "夹具"},
        "steps": [
            {"sender": parties["manual"], "receiver": parties["undecided"]},
            {"sender": parties["missing"], "receiver": parties["manual"]},
        ],
    }

    def semantic(task, inputs):
        assert task == "ssd-participant-classify"
        assert [row["id"] for row in inputs["participants"]] == ["undecided"]
        return {
            "participants": [
                {
                    "participant_id": "undecided",
                    "kind": None,
                    "source_ref_ids": [],
                    "reason": "没有系统边界依据",
                }
            ]
        }

    classify(bundle, semantic)
    assert not parties["manual"]["external"]
    assert parties["undecided"]["external"]
    assert parties["missing"]["external"]
