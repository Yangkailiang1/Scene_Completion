import json
from copy import deepcopy
from pathlib import Path

from scene_completion.analysis.interactions.field_anchors import anchors
from scene_completion.analysis.ssd.command_contract import attach
from scene_completion.analysis.ssd.core_input import convert, validate_core
from scene_completion.analysis.ssd.entity_semantics import classify
from scene_completion.analysis.ssd.pipeline import build_cases, generate_g
from scene_completion.domain.current_scope import COMMAND_PROFILE
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
    role_quote = f"Actor：{actor}。CatalogService 是服务。"
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
                    "crud": ["read"] if u["step_id"] == "D3" else ["create"],
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
        ("D1", ["D1", "D2"]),
        ("D3", ["D3"]),
    ]
    bundle["channels"]["G"] = generate_g(bundle)
    key = "service.crud.create.idempotency"
    g = [row for row in bundle["channels"]["G"]["scenarios"] if row["key"] == key]
    assert [row["step_id"] for row in g] == ["R1", "R1", "D1"]
    assert len({binding(row) for row in g}) == 3

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


def test_named_originals_excel_ranges_and_duplicate_files_survive_conversion(tmp_path):
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
    spec.write_text("标题\n唯一的原文引文。\n", encoding="utf8")
    docs.append({"path": "originals/document.md", "role": "SR", "aliases": ["designDocument"]})
    (root / "source-documents.json").write_text(json.dumps({"documents": docs}), encoding="utf8")
    behavior = next(root.rglob("SysOperation.json"))
    operation = json.loads(behavior.read_text(encoding="utf8"))
    main = next(iter(operation["operations"].values()))
    declared = [
        {"doc": "designDocument", "location": "L1726-L1726", "quote": "唯一的原文引文。"},
        {"doc": "missing.md", "location": "L35", "quote": "暂未提供原件"},
    ]
    main["interaction"][0]["source_refs"] = declared
    behavior.write_text(json.dumps(operation, ensure_ascii=False), encoding="utf8")
    core = tmp_path / "core"
    assert convert(root, core, profile=COMMAND_OPERATION_PROFILE)["output"]
    assert validate_core(core)["valid"]
    assert (core / "originals/原始用例.xlsx").read_bytes() == workbook.read_bytes()
    case = build_cases(core)[0]
    mixed_refs = [r for step in case["steps"] for r in step["source_refs"]]
    assert any(r["kind"] == "origin" and r["quote"] == declared[0]["quote"] for r in mixed_refs)
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
    assert found["match"] == "located" and found["start_line"] == 2
