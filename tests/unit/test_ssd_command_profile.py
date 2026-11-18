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
