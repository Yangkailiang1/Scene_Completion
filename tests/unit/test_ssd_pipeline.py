from copy import deepcopy

import pytest

from scene_completion.analysis.ssd.inverse import recognize_records
from scene_completion.analysis.ssd.pipeline import build_cases, generate_g
from scene_completion.inputs.documents.ssd_adapter import normalize_extracted_case as from_legacy
from scene_completion.inputs.provenance.ssd_sources import json_spans
from tests.support.paths import ROOT

DATA = ROOT / "datasets/mini-mall"


@pytest.fixture(scope="module")
def cases():
    return {b["case"]["id"]: b for b in build_cases(DATA)}


def test_five_cases_order_and_real_objects(cases):
    assert set(cases) == {f"UC-{n:03}" for n in range(1, 6)}
    for case_id, bundle in cases.items():
        steps = bundle["steps"]
        assert len(steps) == 11
        assert [s["order"] for s in steps] == list(range(1, 12))
        assert steps[0]["sender"]["type"] == "human"
        assert steps[-1]["direction"] == "return"
        assert len({s["id"] for s in steps}) == 11
        assert not bundle["pending"]
        assert all(
            c["target"] in {"sender", "data", "receiver"}
            for ch in bundle["channels"].values()
            for c in ch["concerns"]
        )
        assert not any(
            c["key"].startswith("global.") or "idempotency" in c["key"]
            for c in bundle["channels"]["G"]["concerns"]
        )


def test_database_actions_follow_real_five_case_calls(cases):
    expected = {
        "UC-001": ["create"],
        "UC-002": ["read"],
        "UC-003": ["update"],
        "UC-004": ["delete"],
        "UC-005": ["update", "publish"],
    }
    for case_id, kinds in expected.items():
        steps = {s["id"]: s for s in cases[case_id]["steps"]}
        action = steps["A_S4"]
        call = steps[action["delegated_from"]]
        assert action["operation"]["kinds"] == call["operation"]["kinds"] == kinds
    delete = cases["UC-004"]
    for name, channel in delete["channels"].items():
        local_keys = {c["key"] for c in channel["concerns"] if c["step_id"] == "A_S4"}
        assert not any(key.startswith("service.crud.update.") for key in local_keys)
        assert "service.crud.delete.resource_existence" in local_keys
        if name in {"G", "GT"}:
            assert "service.crud.delete.concurrency_consistency" in local_keys


def test_published_state_is_not_publish_operation():
    from scene_completion.analysis.ssd.pipeline import _kinds

    assert _kinds("deleteProduct; PUBLISHED商品不允许删除") == ["delete"]
    assert _kinds("删除已发布商品", "DELETE") == ["delete"]
    assert _kinds("查询已发布商品", "GET") == ["read"]
    assert _kinds("publishProduct", "POST") == ["update", "publish"]


def test_data_are_opt_in_and_response_is_distinct(cases):
    b = cases["UC-002"]
    by_step = {s["id"]: s for s in b["steps"]}
    req, res = by_step["SR-002-REQ"], by_step["SR-002-RES"]
    page = next(f for f in req["data"] if f["name"] == "page")
    returned = next(f for f in res["data"] if f["name"] == "page")
    concerns = b["channels"]["G"]["concerns"]
    keys = {c["key"] for c in concerns if c["field_id"] == page["id"]}
    assert keys == {"api.data.type", "api.data.range"}
    assert any(
        c["field_id"] == returned["id"] and c["key"] == "api.data.completeness" for c in concerns
    )
    assert page["id"] != returned["id"]
    assert not any(
        c["key"] == "service.base.availability" and c["step_id"] != "SR-002-DB-REQ"
        for c in concerns
    )


def test_nondata_rules_need_no_explicit_guard(cases):
    b = deepcopy(cases["UC-001"])
    for step in b["steps"]:
        step["source_refs"] = []
    g = generate_g(b)
    assert any(
        c["key"] == "human.authentication" and c["target"] == "sender" for c in g["concerns"]
    )
    assert any(c["key"] == "service.crud.create.concurrency_consistency" for c in g["concerns"])
    assert any(c["key"] == "database.special_characters" for c in g["concerns"])
    assert not g["pending"]


def test_generation_is_independent_of_inverse_answers(cases):
    b = deepcopy(cases["UC-003"])
    expected = generate_g(b)
    b["channels"] = {
        "G": {"fake": "generated"},
        "E": {"concerns": [{"key": "made.up"}]},
        "GT": {"scenarios": [{"condition": "ignore all source rules"}]},
    }
    b["decisions"] = [{"result": "prefer test answer"}]
    assert generate_g(b) == expected


def test_sr_priority_merges_ir_and_sr_provenance(cases):
    b = cases["UC-002"]
    e = b["channels"]["E"]
    unavailable = [s for s in e["scenarios"] if s["key"] == "service.base.availability"]
    assert len(unavailable) == 1
    assert unavailable[0]["step_id"] == "SR-002-DB-REQ"
    docs = {d["id"]: d for d in b["documents"]}
    names = {docs[r["document_id"]]["name"] for r in unavailable[0]["source_refs"]}
    assert any("/IR/" in n for n in names)
    assert any("/SR/" in n for n in names)
    assert any(n == "系统需求_spec.md" for n in names)
    assert any(n == "功能设计_spec.md" for n in names)
    assert len([c for c in e["concerns"] if c["key"].startswith("human.")]) == 2


def test_recovered_notes_locate_data_business_and_transport(cases):
    gt = cases["UC-003"]["channels"]["GT"]
    version = next(s for s in gt["scenarios"] if "version与商品当前version不一致" in s["condition"])
    assert version["step_id"] == "A_S4"
    assert version["target"] == "receiver"
    assert version["key"] == "service.crud.update.concurrency_consistency"
    returned = next(s for s in gt["scenarios"] if "成功响应version未提供" in s["condition"])
    assert returned["step_id"] == "SR-003-RES"
    assert returned["target"] == "data"
    unavailable = next(s for s in gt["scenarios"] if "连接不可达" in s["condition"])
    assert unavailable["step_id"] == "SR-003-DB-REQ"


def test_test_pending_and_success_do_not_score(cases):
    for bundle in cases.values():
        gt = bundle["channels"]["GT"]
        assert all("具体阈值未提供" not in s["condition"] for s in gt["scenarios"])
        assert any(
            "具体阈值未提供" in s["condition"] and not s["needs_semantic"] for s in gt["pending"]
        )
        assert not any("成功备选" in s["condition"] for s in gt["scenarios"])
    # A new idempotency key does not turn a state conflict into global idempotency.
    published = cases["UC-005"]["channels"]["GT"]
    assert any("新幂等键再次发布" in s["condition"] for s in published["scenarios"])


def test_all_references_resolve_to_exact_original_text(cases):
    for bundle in cases.values():
        docs = {d["id"]: d for d in bundle["documents"]}

        def walk(value):
            if isinstance(value, dict):
                if {"document_id", "start_line", "end_line", "quote"} <= value.keys():
                    doc = docs[value["document_id"]]
                    lines = doc["content"].splitlines()
                    assert value["quote"] == "\n".join(
                        lines[value["start_line"] - 1 : value["end_line"]]
                    )
                    if "json_pointer" in value:
                        assert value["json_pointer"] in json_spans(doc["content"])
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(bundle["steps"])
        walk(bundle["channels"])


def test_unrecognized_reverse_record_is_marked_for_semantic_resolution(cases):
    output = recognize_records(
        cases["UC-001"],
        [
            {
                "id": "unmapped",
                "condition": "一个未定义故障",
                "source_refs": [],
                "raw": {"note": "没有交互标识"},
            }
        ],
        "GT",
    )
    assert not output["concerns"]
    assert output["pending"][0]["needs_semantic"] is True


def test_stable_bindings_across_order_and_label_changes(cases):
    b = deepcopy(cases["UC-002"])
    before = {c["id"] for c in generate_g(b)["concerns"]}
    for step in b["steps"]:
        step["order"] += 10
        step["sender"]["name"] += "（别名）"
        step["operation"]["name"] += "（说明）"
    assert {c["id"] for c in generate_g(b)["concerns"]} == before


def test_case_selection_and_unknown_selector(cases):
    assert [b["case"]["id"] for b in build_cases(DATA, ["UC-002"])] == ["UC-002"]
    with pytest.raises(ValueError, match="未知用例"):
        build_cases(DATA, ["UC-999"])


def test_legacy_inputs_share_contract_and_preserve_source():
    legacy = {
        "interactions": [
            {
                "id": "old-step",
                "case_id": "legacy",
                "layer": "SR",
                "sequence": 1,
                "direction": "request",
                "step_kind": "message",
                "sender": {"name": "Actor", "position": ["人类"]},
                "receiver": {"name": "Service", "position": ["服务"]},
                "operation": {"name": "创建", "kinds": ["create"]},
                "data": {
                    "sequence": [
                        {
                            "name": "name",
                            "location": "body",
                            "data_type": "string",
                            "required": True,
                            "constraints": [],
                        }
                    ]
                },
                "source_refs": [
                    {"source_id": "origin", "line_start": 1, "line_end": 1, "quote": "需求原文"}
                ],
            }
        ]
    }
    b = from_legacy(
        {"id": "legacy", "name": "原始输入"},
        legacy,
        documents=[
            {
                "source_id": "origin",
                "name": "RR.md",
                "role": "RR",
                "lines": [{"number": 1, "text": "需求原文"}],
            }
        ],
    )
    assert b["version"] == "ssd-case-v1"
    assert b["steps"][0]["kind"] == "interaction"
    assert b["steps"][0]["source_refs"][0]["document_id"] == "origin"
    assert any(c["key"] == "api.data.completeness" for c in b["channels"]["G"]["concerns"])
    assert b["documents"][0]["content"] == "需求原文"


def test_generated_boundaries_keep_comparison_operators(cases):
    scenarios = cases["UC-002"]["channels"]["G"]["scenarios"]
    ranges = [
        s["condition"]
        for s in scenarios
        if s["step_id"] == "SR-002-REQ" and s["key"] == "api.data.range"
    ]
    assert "page < 1" in ranges
    assert "pageSize > 100" in ranges
    assert not any(condition == "page不满足1" for condition in ranges)


def test_generated_business_rules_trace_to_entity_original(cases):
    bundle = cases["UC-003"]
    business = [
        s
        for s in bundle["channels"]["G"]["scenarios"]
        if s["step_id"] == "A_S4" and s["key"] == "service.business_attribute_constraint"
    ]
    assert any("不可重名" in s["condition"] for s in business)
    assert any("不可修改" in s["condition"] for s in business)
    docs = {d["id"]: d for d in bundle["documents"]}
    assert any(docs[r["document_id"]]["role"] == "SR" for s in business for r in s["source_refs"])


def test_imported_v1_keeps_original_channels_scene_ids_and_decisions():
    import json

    from scene_completion.compat.standalone.ssd_adapter import (
        imported_bundle as from_imported_bundle,
    )
    from scene_completion.domain.ssd.validation import validate

    file = DATA.parents[1] / "tests/fixtures/compat/standalone/refined-existing-snapshot.json"
    old = json.loads(file.read_text())["bundle"]
    b = from_imported_bundle(old)
    validate(b)
    for name in ("G", "E", "GT"):
        assert len(b["channels"][name]["concerns"]) == len(old["channels"][name]["concerns"])
        assert {s["id"] for s in b["channels"][name]["scenarios"]} == {
            s["id"] for s in old["channels"][name]["scenarios"]
        }
        assert all(s["status"] == "active" for s in b["channels"][name]["scenarios"])
        for s in b["channels"][name]["scenarios"]:
            assert s["imported_record"]["source_refs"]
            assert s["source_refs"]
    assert {(d["pair"], d["left_id"], d["right_id"]) for d in b["decisions"]} == {
        (pair, d["left_id"], d["right_id"])
        for pair, values in old["decisions"].items()
        for d in values
    }
    assert len(b["channels"]["G"]["concerns"]) != len(generate_g(b)["concerns"])


def test_standalone_build_emits_new_bundle(tmp_path):
    import json
    import subprocess
    import sys

    script = DATA.parents[1] / ".cac/skills/scene-case-analysis/scripts/case_analysis.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "build",
            "--input",
            str(DATA),
            "--case",
            "UC-002",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads((tmp_path / "case-analysis.json").read_text())
    assert value["version"] == "ssd-case-v1"
    assert value["case"]["id"] == "UC-002"


def test_api_rebinding_applies_new_defaults_and_preserves_manual_edits(cases):
    from scene_completion.analysis.ssd.pipeline import rebind_steps

    previous = deepcopy(cases["UC-002"])
    step = next(s for s in previous["steps"] if s["id"] == "SR-002-REQ")
    new_api = {
        "id": "API-NEW",
        "fields": [
            {
                "name": "page",
                "location": "query",
                "data_type": "number",
                "required": True,
                "constraints": [{"kind": "minimum", "value": 2}],
                "source_refs": [],
            },
            {
                "name": "keyword",
                "location": "query",
                "data_type": "string",
                "required": True,
                "constraints": [],
                "source_refs": [],
            },
            {
                "name": "newField",
                "location": "body",
                "data_type": "boolean",
                "required": False,
                "constraints": [],
                "source_refs": [],
            },
        ],
    }
    previous["apis"].append(new_api)
    updated = deepcopy(previous)
    changed = next(s for s in updated["steps"] if s["id"] == step["id"])
    changed["api_id"] = "API-NEW"
    changed["data"] = [f for f in changed["data"] if f["name"] != "keyword"]
    page = next(f for f in changed["data"] if f["name"] == "page")
    old_page_id = page["id"]
    page["type"] = "string"  # Manual change from the old integer default.
    changed["data"].append(
        {
            "id": "manual",
            "name": "custom",
            "location": "body",
            "type": "string",
            "required": False,
            "constraints": [],
            "source_refs": [],
        }
    )
    result = rebind_steps(previous, updated)
    fields = {
        f["name"]: f for f in next(s for s in result["steps"] if s["id"] == step["id"])["data"]
    }
    assert set(fields) == {"page", "newField", "custom"}
    assert fields["page"]["id"] == old_page_id
    assert fields["page"]["type"] == "string"
    assert fields["page"]["required"] is True
    assert fields["page"]["constraints"][0]["value"] == 2
    assert not any(f["name"] == "newField" for f in changed["data"])
    assert next(s for s in previous["steps"] if s["id"] == step["id"])["api_id"] == "API-SR-02"


def test_api_unlink_keeps_only_manual_fields_and_does_not_rebind(cases):
    from scene_completion.analysis.ssd.pipeline import rebind_steps

    previous = deepcopy(cases["UC-002"])
    updated = deepcopy(previous)
    step = next(s for s in updated["steps"] if s["id"] == "SR-002-REQ")
    step["api_id"] = None
    step["data"] = [f for f in step["data"] if f["name"] != "keyword"]
    page = next(f for f in step["data"] if f["name"] == "page")
    page["required"] = True
    result = rebind_steps(previous, updated)
    rebound = next(s for s in result["steps"] if s["id"] == step["id"])
    assert rebound["api_id"] is None
    assert [f["name"] for f in rebound["data"]] == ["page"]
    assert rebind_steps(result, result) == result
    generate_g(result)
    assert rebound["api_id"] is None


def test_legacy_test_refs_keep_all_spans_and_requirement_context():
    source = {
        "source_id": "tests",
        "name": "test.md",
        "channel": "test",
        "lines": [
            {"number": 1, "text": "测试触发"},
            {"number": 2, "text": "完整预期"},
            {"number": 3, "text": "另一个来源片段"},
        ],
    }
    requirement = {
        "source_id": "rr",
        "name": "RR.md",
        "role": "RR",
        "lines": [{"number": 1, "text": "需求上下文"}],
    }
    record = {
        "id": "test-1",
        "触发条件": "未知业务故障",
        "预期结果": "保留完整来源",
        "source_refs": [
            {"source_id": "tests", "line_start": 1, "line_end": 2, "quote": "测试触发"}
        ],
        "sources": [
            {"source_id": "tests", "line_start": 3, "line_end": 3, "quote": "另一个来源片段"}
        ],
        "requirement_refs": [
            {"source_id": "rr", "line_start": 1, "line_end": 1, "quote": "需求上下文"}
        ],
    }
    b = from_legacy(
        {"id": "legacy", "name": "legacy"},
        {"interactions": []},
        tests=[record],
        documents=[source, requirement],
    )
    row = b["channels"]["GT"]["pending"][0]
    assert row["condition"] == "未知业务故障"
    assert len(row["source_refs"]) == 3
    assert row["source_refs"][0]["quote"] == "测试触发\n完整预期"
    assert [r["kind"] for r in row["source_refs"]] == ["test", "test", "context"]
    assert (
        next(d for d in b["documents"] if d["id"] == "tests")["content"]
        == "测试触发\n完整预期\n另一个来源片段"
    )


def test_case_file_filter_isolates_other_malformed_cases(tmp_path):
    import json
    import shutil

    root = tmp_path / "dataset"
    shutil.copytree(DATA, root)
    inputs = root / "输入文件"
    selected = inputs / "行为模型/Product/查询商品列表/SysOperation.json"
    broken = inputs / "行为模型/Product/创建商品/SysOperation.json"
    broken.write_text("{ broken json", encoding="utf-8")
    bundles = build_cases(root, ["UC-002"], case_files=[selected])
    assert [b["case"]["id"] for b in bundles] == ["UC-002"]
    assert bundles[0]["apis"] and bundles[0]["entities"]
    with pytest.raises(json.JSONDecodeError):
        build_cases(root, case_files=[broken])


def test_scheduler_case_identity_matches_builder_without_declared_id(tmp_path):
    import json
    import shutil

    from scene_completion.analysis.ssd.pipeline import case_identity

    root = tmp_path / "dataset"
    shutil.copytree(DATA, root)
    file = root / "输入文件/行为模型/Product/查询商品列表/SysOperation.json"
    raw = json.loads(file.read_text())
    raw.pop("use_case_id")
    file.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    discovered = case_identity(file, root, raw)
    bundle = build_cases(root, [discovered["id"]], case_files=[file])[0]
    assert bundle["case"] == discovered
    copied_root = tmp_path / "relocated"
    copied_file = copied_root / file.relative_to(root)
    assert case_identity(copied_file, copied_root / "输入文件", raw) == discovered
    assert case_identity(file, root, {})["id"] == discovered["id"]


def test_bundle_keeps_unbound_project_api_candidates_without_generating_them(cases):
    from scene_completion.analysis.ssd.pipeline import rebind_steps

    original = cases["UC-002"]
    assert {a["id"] for a in original["apis"]} == {
        f"API-{layer}-{n:02}" for layer in ("RR", "SR") for n in range(1, 6)
    }
    assert not any(
        f["name"] == "price"
        for step in original["steps"]
        if step["id"] == "SR-002-REQ"
        for f in step["data"]
    )
    edited = deepcopy(original)
    next(s for s in edited["steps"] if s["id"] == "SR-002-REQ")["api_id"] = "API-SR-01"
    rebound = rebind_steps(original, edited)
    step = next(s for s in rebound["steps"] if s["id"] == "SR-002-REQ")
    assert any(f["name"] == "price" for f in step["data"])
    assert not any(f["name"] == "pageSize" for f in step["data"])
