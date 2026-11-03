"""Behavior fixtures intentionally include wrong SR endpoints: no repairs by guess."""

import json

import pytest

from scene_completion.inputs.artifact_imports import decide, receive, snapshot
from scene_completion.inputs.behavior_imports import (
    compile_product,
    flow_refs,
    materials,
)
from scene_completion.inputs.input_bundles import apply, discover
from scene_completion.inputs.source_documents import validate_evidence
from scene_completion.inputs.structure_models import existing_branches
from tests.test_input_bundles import project, write_folder


def scenarios(layer="IR", name="用例1"):
    return {
        "schema_version": "1.0",
        "use_case_id": "UC-1",
        "use_case_name": name,
        "spec_level": layer,
        "resource_object": "PAYMENT_IS_NOT_AN_ENTITY_PROOF",
        "scenarios": [
            {
                "id": "MAIN",
                "kind": "main",
                "trigger": "请求",
                "preconditions": ["已有身份"],
                "steps": [
                    {"id": "S1", "text": "开发者向平台发送查询"},
                    {"id": "S2", "text": "平台返回列表"},
                ],
                "postconditions": {"success": ["返回列表"]},
            },
            {
                "id": "ERR",
                "kind": "exception",
                "trigger": "E_ONLY_INVALID_TOKEN",
                "extends": {"scenario_id": "MAIN", "after_step": "S1"},
                "steps": [{"id": "E1", "text": "E_ONLY_REJECTED"}],
                "postconditions": {"minimal": ["DENIED"]},
            },
            {
                "id": "ALT",
                "kind": "alternative",
                "trigger": "OPTIONAL_ONLY",
                "steps": [{"id": "A1", "text": "正常备选"}],
                "postconditions": {"success": ["替代成功"]},
            },
        ],
    }


def ssd():
    return {
        "schema_version": "1.0",
        "system_boundary": "平台",
        "interactions": [
            {
                "id": "RR1",
                "sender": "开发者",
                "receiver": "平台",
                "message": "提交查询",
                "source_steps": ["S1"],
                "data_refs": [],
            },
            {
                "id": "RR2",
                "sender": "平台",
                "receiver": "开发者",
                "message": "返回列表",
                "source_steps": ["S2"],
                "data_refs": [],
            },
            {
                "id": "RR_E",
                "sender": "平台",
                "receiver": "开发者",
                "message": "E_ONLY_REJECTED",
                "source_steps": ["E1"],
                "data_refs": [],
            },
        ],
        "scenario_flows": [
            {
                "scenario_id": "MAIN",
                "flow": {
                    "type": "sequence",
                    "steps": [
                        {"type": "interaction", "ref": "RR1"},
                        {
                            "type": "choice",
                            "branches": [
                                {
                                    "guard": "E_ONLY_INVALID_TOKEN",
                                    "flow": {"type": "interaction", "ref": "RR_E"},
                                },
                                {"guard": "允许", "flow": {"type": "interaction", "ref": "RR2"}},
                            ],
                        },
                    ],
                },
            }
        ],
    }


def behavior(view="main_success"):
    return {
        "schema_version": "1.2",
        "spec_level": "SR",
        "view_type": view,
        "operation_id": "query",
        "status": "derived",
        "flow": {
            "type": "sequence",
            "steps": [
                {"type": "interaction", "ref": "I1"},
                {"type": "action", "ref": "A1"},
                {"type": "interaction", "ref": "I2"},
            ],
        },
        "interactions": [
            {
                "id": "I1",
                "sender": "开发者",
                "receiver": "平台",
                "message": "提交查询",
                "source_steps": ["S1"],
                "data_refs": [],
            },
            {
                "id": "I2",
                "sender": "平台",
                "receiver": "开发者",
                "message": "返回结果",
                "source_steps": ["S2"],
                "data_refs": [],
            },
        ],
        "actions": [
            {"id": "A1", "description": "系统内部校验，但没有声明调用双方", "source_steps": ["S1"]}
        ],
        "source_scenario_ids": ["MAIN"],
        "note": "EXTERNAL_UNVERIFIED_NOT_A_RULE",
    }


def fixture(root):
    p = root / "行为建模_资源用例/outputs/支付/任意目录名称"
    p.mkdir(parents=True)
    values = {
        "ir_scenario.json": scenarios(),
        "sr_scenario.json": scenarios("SR"),
        "ssd.json": ssd(),
        "operations/query/main_success.json": behavior(),
        "operations/query/complete_behavior.json": behavior("complete"),
    }
    for name, value in values.items():
        dest = p / name
        dest.parent.mkdir(exist_ok=True, parents=True)
        dest.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")
    return p


def enable_all(p):
    for row in snapshot(p):
        if row.get("behavior_product"):
            decide(
                p, row["id"], {"action": "enable_behavior", "expected_revision": row["revision"]}
            )


def test_folder_discovers_optional_views_without_replacing_five_roles_or_using_history(tmp_path):
    write_folder(tmp_path / "input")
    fixture(tmp_path / "input")
    h = tmp_path / "input/行为建模_资源用例/history/old/ir_scenario.json"
    h.parent.mkdir(parents=True)
    h.write_text(json.dumps(scenarios(name="旧用例")))
    old = tmp_path / "input/行为建模_资源用例/inputs/SR/对象/用例/scenario.json"
    old.parent.mkdir(parents=True)
    old.write_text(json.dumps(scenarios("SR")))
    preview, files = discover(directory=str(tmp_path / "input"))
    assert preview["complete"] and preview["model_calls"] == 0 and len(files) == 10
    rows = [r for r in preview["files"] if r["role"] == "behavior"]
    assert len(rows) == 5 and {r["case_name"] for r in rows} == {"用例1"}
    assert all(
        "任意目录名称" not in str(f.get("behavior_context", {}).get("case_name"))
        for f in files.values()
    )
    assert any("history" in x["name"] for x in preview["ignored"])
    assert any("/inputs/" in x["name"] for x in preview["ignored"])
    assert all(r["coverage"] == "partial" for r in rows)


def test_behavior_adoption_is_explicit_and_positive_existing_channels_are_separate(tmp_path):
    write_folder(tmp_path / "input")
    fixture(tmp_path / "input")
    preview, files = discover(directory=str(tmp_path / "input"))
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files)
        assert materials(snapshot(p), ["用例1"]) == {"RR": [], "SR": [], "existing": []}
        apply(service, p, preview, files, adopt_partial=True)
        selected = materials(snapshot(p), ["用例1"])
        positive = str(selected["RR"] + selected["SR"])
        assert "提交查询" in positive and "系统内部校验" in positive
        for token in (
            "E_ONLY",
            "DENIED",
            "OPTIONAL_ONLY",
            "EXTERNAL_UNVERIFIED",
            "PAYMENT_IS_NOT_AN_ENTITY_PROOF",
        ):
            assert token not in positive
        assert not materials(snapshot(p), ["其他用例"])["RR"]
        branches = existing_branches(selected["existing"])["branches"]
        assert len(branches) == 2 and "E_ONLY_INVALID_TOKEN" in str(branches)
        validate_evidence({"branches": branches}, selected["existing"])
        # Wrong endpoints remain as supplied, never a made-up Platform->Service.
        assert "开发者" in positive and "AdminService" not in positive
        assert not any(r["artifacts"] for r in snapshot(p) if r.get("behavior_product"))
    finally:
        service.pool.shutdown()


def test_no_sibling_no_main_inference_and_no_cross_case_step_id_binding(tmp_path):
    raw = ssd()
    p = compile_product(raw, "one", "ssd.json")
    row = {"id": "one", "hash": "one", "behavior_enabled": True, "behavior_product": p}
    p["case_ids"] = ["CASE"]
    assert materials([row], ["CASE"])["RR"] == []
    with pytest.raises(ValueError, match="引用不存在"):
        flow_refs({"type": "interaction", "ref": "missing"}, {}, {})
    with pytest.raises(ValueError, match="暂不支持"):
        flow_refs({"type": "execute_python"}, {}, {})
    assert flow_refs(
        {"type": "optional", "body": {"type": "interaction", "ref": "A"}}, {"A": {}}, {}
    ) == [("interaction", "A")]


def test_invalid_optional_behavior_is_visible_and_does_not_break_original_import(tmp_path):
    write_folder(tmp_path / "input")
    p = fixture(tmp_path / "input")
    bad = behavior()
    bad["flow"] = {"type": "interaction", "ref": "missing"}
    bad["view_type"] = "complete"
    (p / "operations/query/complete_behavior.json").write_text(json.dumps(bad))
    preview, files = discover(directory=str(tmp_path / "input"))
    assert preview["valid"]
    assert any(r.get("error") for r in preview["files"])
    service, project_path = project(tmp_path / "data")
    try:
        apply(service, project_path, preview, files, adopt_partial=True)
        rows = snapshot(project_path)
        assert any(r.get("structure_model") for r in rows)
        invalid = next(r for r in rows if r.get("behavior_error"))
        assert invalid["status"] == "invalid_behavior" and not invalid.get("behavior_enabled")
    finally:
        service.pool.shutdown()


def test_batch_upload_resolves_siblings_and_preserves_original_trace(tmp_path):
    from scene_completion.review.review_handoff import source_view

    service, p = project(tmp_path / "data")
    try:
        files = [
            {
                "name": "ir_scenario.json",
                "relative_path": "outputs/任意/用例/ir_scenario.json",
                "content": json.dumps(scenarios(), ensure_ascii=False),
            },
            {
                "name": "main_success.json",
                "relative_path": "outputs/任意/用例/operations/query/main_success.json",
                "content": json.dumps(behavior(), ensure_ascii=False),
            },
            {
                "name": "complete_behavior.json",
                "relative_path": "outputs/任意/用例/operations/query/complete_behavior.json",
                "content": json.dumps(behavior("complete"), ensure_ascii=False),
            },
        ]
        receive(p, files)
        rows = snapshot(p)
        assert all(r["behavior_product"]["case_name"] == "用例1" for r in rows)
        enable_all(p)
        doc = materials(snapshot(p), ["用例1"])["SR"][0]
        ref = {
            "source_id": doc["source_id"],
            "line_start": doc["lines"][0]["number"],
            "line_end": doc["lines"][0]["number"],
            "quote": doc["lines"][0]["text"],
        }
        validate_evidence(ref, [doc])
        result = source_view(p, doc["source_id"])
        assert "main_success.json" in str(result) and "json_pointer" in str(result)
        assert not (p / "run/workflow_tasks.json").exists()
    finally:
        service.pool.shutdown()


def test_old_pipeline_without_behavior_is_unchanged_and_preview_shows_real_targets(tmp_path):
    from scene_completion.analysis.import_plan import build

    write_folder(tmp_path / "input")
    fixture(tmp_path / "input")
    preview, files = discover(directory=str(tmp_path / "input"))
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        plan = build(p)
        nodes = [n for n in plan["nodes"] if n["stage"] == "fused-ssd"]
        assert any(
            any(b["purpose"] == "SR主成功时序（引用）" for b in n["input_bindings"]) for n in nodes
        )
        assert all(n["import_mode"] != "reuse" for n in nodes)
        # No fake extracted entities, fabricated formal outputs or test records.
        assert not (p / "run/workflow_tasks.json").exists()
    finally:
        service.pool.shutdown()


def test_registered_tasks_receive_main_materials_but_not_exception_answers(tmp_path):
    from scene_completion.analysis.import_plan import Plan
    from scene_completion.inputs.source_documents import normal_projection
    from scene_completion.inputs.structure_models import catalogue, imported_sources
    from scene_completion.workflow.engine import _build_cases

    write_folder(tmp_path / "input")
    fixture(tmp_path / "input")
    preview, files = discover(directory=str(tmp_path / "input"))
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        imports = snapshot(p)
        docs = imported_sources(imports)
        cat = {
            layer: catalogue(normal_projection([docs[layer]]), layer)["cases"]
            for layer in ("RR", "SR")
        }
        plan = Plan(p / "preview/run", imports, {})
        plan.root.mkdir(parents=True)
        group = {
            "id": "G-1",
            "rr_ids": ["UC-1"],
            "sr_ids": ["UC-1"],
            "status": "confirmed",
            "reason": "fixture",
            "source_refs": cat["RR"][0]["source_refs"],
        }
        _build_cases(plan, [docs["RR"]], [docs["SR"]], [], cat, [group], {}, {})
        context = plan.scheduler.tasks["G-1:ssd-context"]
        assert "提交查询" in str(context.static["RR"])
        assert "系统内部校验" in str(context.static["SR"])
        assert "E_ONLY" not in str(context.static)
        branches = plan.scheduler.tasks["G-1:existing-branches"]
        assert "E_ONLY" in str(branches.static)
        assert plan.scheduler.tasks["G-1:fused-ssd"].transform is None
        assert plan.scheduler.tasks["G-1:rr-ssd"].transform is not None
    finally:
        service.pool.shutdown()


def test_legacy_provenance_labels_are_display_mapped_without_mutating_history():
    from scene_completion.inputs.artifact_imports import provenance_label

    assert provenance_label("同事产物导入") == "已有文件输入"
    assert provenance_label("同事产物合并") == "已有文件输入（补充合并）"
    assert provenance_label("恢复后生成") == "恢复后生成"


def test_order_only_main_resolves_definitions_from_complete_and_preserves_two_sources(tmp_path):
    from scene_completion.review.review_handoff import source_view

    write_folder(tmp_path / "input")
    folder = fixture(tmp_path / "input")
    main = behavior()
    main.pop("interactions")
    main.pop("actions")
    (folder / "operations/query/main_success.json").write_text(json.dumps(main))
    complete = behavior("complete")
    complete["interactions"][0].update(
        sender="平台", receiver="AdminService", message="SR_DEFINITION_ONLY_QUERY"
    )
    complete["interactions"][1].update(
        sender="AdminService", receiver="平台", message="SR_DEFINITION_ONLY_RESULT"
    )
    (folder / "operations/query/complete_behavior.json").write_text(json.dumps(complete))
    preview, files = discover(directory=str(tmp_path / "input"))
    assert not any(r.get("error") for r in preview["files"])
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        docs = materials(snapshot(p), ["用例1"])
        sr = docs["SR"]
        assert "SR_DEFINITION_ONLY_QUERY" in str(sr) and "AdminService" in str(sr)
        order = next(d for d in sr if d["name"].startswith("main_success"))
        definitions = next(d for d in sr if d["name"].startswith("complete_behavior"))
        assert "SR_DEFINITION_ONLY_QUERY" not in str(order)
        assert "SR_DEFINITION_ONLY_QUERY" in str(definitions)
        assert "complete_behavior.json" in str(source_view(p, definitions["source_id"]))
        assert "main_success.json" in str(source_view(p, order["source_id"]))
        assert "提交查询" in str(docs["RR"]) and "AdminService" not in str(docs["RR"])
    finally:
        service.pool.shutdown()


def test_partial_main_definitions_do_not_override_complete_and_missing_definition_falls_back(
    tmp_path,
):
    write_folder(tmp_path / "input")
    folder = fixture(tmp_path / "input")
    main = behavior()
    main["interactions"] = [{"id": "I1", "message": "WRONG_DUPLICATE_MAIN_DEFINITION"}]
    main["actions"] = []
    (folder / "operations/query/main_success.json").write_text(json.dumps(main))
    preview, files = discover(directory=str(tmp_path / "input"))
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        assert "WRONG_DUPLICATE_MAIN_DEFINITION" not in str(materials(snapshot(p), ["用例1"]))
        assert "系统内部校验" in str(materials(snapshot(p), ["用例1"])["SR"])
        rows = snapshot(p)
        rows = [r for r in rows if r.get("behavior_product", {}).get("kind") != "sr_complete"]
        sr = materials(rows, ["用例1"])["SR"]
        assert not any(d["name"].startswith("main_success") for d in sr)
        assert any(
            "场景可读投影" in d["name"] for d in sr
        )  # Original declared normal material survives.
    finally:
        service.pool.shutdown()


@pytest.mark.parametrize("with_order", [True, False])
def test_complete_inventory_not_limited_to_order_view_and_scenario_kinds_split_channels(
    tmp_path, with_order
):
    write_folder(tmp_path / "input")
    folder = fixture(tmp_path / "input")
    sr = scenarios("SR")
    sr["scenarios"][0]["steps"].append({"id": "S3", "text": "正常内部调用完整定义"})
    (folder / "sr_scenario.json").write_text(json.dumps(sr))
    comp = behavior("complete")
    comp["interactions"] += [
        {
            "id": "I3",
            "sender": "平台",
            "receiver": "AdminService",
            "message": "UNREFERENCED_NORMAL_SR",
            "source_steps": ["S3"],
            "data_refs": [],
        },
        {
            "id": "IE",
            "sender": "AdminService",
            "receiver": "平台",
            "message": "E_ONLY_COMPLETE_ERROR",
            "source_steps": ["E1"],
            "data_refs": [],
        },
        {
            "id": "IA",
            "sender": "AdminService",
            "receiver": "平台",
            "message": "OPTIONAL_ONLY_COMPLETE",
            "source_steps": ["A1"],
            "data_refs": [],
        },
    ]
    (folder / "operations/query/complete_behavior.json").write_text(json.dumps(comp))
    if not with_order:
        (folder / "operations/query/main_success.json").unlink()
    preview, files = discover(directory=str(tmp_path / "input"))
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        docs = materials(snapshot(p), ["用例1"])
        assert "UNREFERENCED_NORMAL_SR" in str(docs["SR"])
        assert "E_ONLY" not in str(docs["SR"]) and "OPTIONAL_ONLY" not in str(docs["SR"])
        assert "E_ONLY_INVALID_TOKEN" in str(existing_branches(docs["existing"]))
        assert all("AdminService" not in str(d) for d in docs["RR"])
    finally:
        service.pool.shutdown()


def test_unresolved_order_is_visible_and_does_not_erase_known_complete_definitions(tmp_path):
    write_folder(tmp_path / "input")
    folder = fixture(tmp_path / "input")
    order = behavior()
    order["flow"] = {"type": "interaction", "ref": "UNKNOWN_REF"}
    order.pop("interactions")
    order.pop("actions")
    (folder / "operations/query/main_success.json").write_text(json.dumps(order))
    preview, files = discover(directory=str(tmp_path / "input"))
    assert not any(r.get("error") for r in preview["files"])
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        diagnostics = []
        docs = materials(snapshot(p), ["用例1"], diagnostics=diagnostics)
        assert "UNKNOWN_REF" in str(diagnostics)
        assert "系统内部校验" in str(docs["SR"])
        assert "UNKNOWN_REF" not in str(docs["SR"])
        from scene_completion.inputs.artifact_imports import view

        row = next(
            r for r in snapshot(p) if r.get("behavior_product", {}).get("kind") == "sr_complete"
        )
        assert "UNKNOWN_REF" in str(view(p, row["id"])["behavior_resolution"])
    finally:
        service.pool.shutdown()


def test_reimport_upgrades_old_adapter_and_keeps_its_source_and_history(tmp_path):
    from scene_completion.infrastructure.storage import write_json

    write_folder(tmp_path / "input")
    fixture(tmp_path / "input")
    preview, files = discover(directory=str(tmp_path / "input"))
    service, p = project(tmp_path / "data")
    try:
        apply(service, p, preview, files, adopt_partial=True)
        from scene_completion.inputs.artifact_imports import load

        row = next(r for r in snapshot(p) if r.get("behavior_product", {}).get("kind") == "sr_main")
        original = (p / row["original"]).read_bytes()
        record = p / load(p)["items"][row["id"]]["record"]
        row["behavior_product"]["version"] = "resource-behavior-import-v1"
        write_json(record, row)
        apply(service, p, preview, files, adopt_partial=True)
        new = next(r for r in snapshot(p) if r["id"] == row["id"])
        assert new["behavior_product"]["version"] != "resource-behavior-import-v1"
        assert new["behavior_enabled"] and new["revision"] > row["revision"]
        assert any(h["action"] == "behavior_adapter_upgrade" for h in new["history"])
        assert list((p / "imports/versions" / row["id"]).glob("*.json"))
        assert (p / new["original"]).read_bytes() == original
    finally:
        service.pool.shutdown()
