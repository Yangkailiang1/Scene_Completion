from copy import deepcopy
from pathlib import Path

from scene_completion.application import ssd_revision_service as revisions
from scene_completion.domain import business_report
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, case_report
from scene_completion.domain.ssd import concern_policy, input_concerns, matching
from scene_completion.domain.ssd.construction import add_concern, add_scenario, channel, pending
from scene_completion.domain.ssd.validation import validate
from scene_completion.workflow.ssd.compare import alignment
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification, entity_semantics

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"
KEY = concern_policy.COMPLETENESS


def _bundle():
    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE, generate=False)[0]
    bundle.update(coverage_policy=GRAIN_POLICY, gt_source_available=True)
    bundle["channels"] = {side: channel() for side in ("G", "GT", "E")}
    return bundle


def _facts(bundle, names):
    step = bundle["steps"][0]
    field = next(f for f in step["data"] if f["name"] == "keyword")
    step["data"] = [
        {**field, "id": name, "name": name, "wire_name": name, "atoms": [], "unresolved": []}
        for name in names
    ]
    return step, step["data"]


def _scene(bundle, side, step, field, *, key=KEY, refs=()):
    output = bundle["channels"][side]
    parent = add_concern(output, bundle, side, step, key, "data", field=field, refs=refs)
    return add_scenario(output, parent, f"{field['name']}缺失", "拒绝", refs)


def test_group_nine_types_without_collapsing_fields_interfaces_or_steps():
    bundle = _bundle()
    step, (left, right) = _facts(bundle, ["pathName", "queryName"])
    left["wire_name"] = left["name"] = right["wire_name"] = right["name"] = "name"
    right["command_id"] = "OTHER-GET"
    source_refs = [
        {"document_id": bundle["documents"][0]["id"], "start_line": i, "end_line": i}
        for i in (1, 2)
    ]
    ids = {}
    for key in sorted(input_concerns.KEYS):
        ids[key] = {
            _scene(bundle, "G", step, field, key=key, refs=[ref])["id"]
            for field, ref in zip((left, right), source_refs, strict=True)
        }
    other_step = bundle["steps"][1]
    field = {**left, "id": "other-interaction:name", "call_step_id": other_step["id"]}
    other_step["data"].append(field)
    _scene(bundle, "G", other_step, field)
    result = validate(bundle)
    assert validate(result) == result
    grouped = result["channels"]["G"]
    assert len(grouped["concerns"]) == 10
    assert all(row["input_group"] for row in grouped["concerns"])
    assert len(grouped["scenarios"]) == 19
    for key, scenario_ids in ids.items():
        [parent] = [
            row for row in grouped["concerns"] if row["key"] == key and row["step_id"] == step["id"]
        ]
        assert parent["field_id"] is None and parent["source_refs"] == source_refs
        scenes = [row for row in grouped["scenarios"] if row["id"] in scenario_ids]
        assert {row["field_id"] for row in scenes} == {"pathName", "queryName"}
        assert all(row["concern_ids"] == [parent["id"]] for row in scenes)
        assert all(len(row["source_refs"]) == 1 for row in scenes)


def test_different_fields_match_concern_and_remain_g_only_and_gt_only():
    bundle = _bundle()
    step, (name, price) = _facts(bundle, ["name", "price"])
    generated = _scene(bundle, "G", step, name)
    bundle = validate(bundle)
    cid = "GT-price"
    source = {
        "id": cid,
        "extension_id": cid,
        "condition": "price缺失",
        "expected": "拒绝",
        "failure_step_id": step["id"],
        "parameter": {"command_id": price["command_id"], "name": price["name"]},
        "source_refs": [],
    }
    bundle["channels"]["GT"]["pending"] = [
        pending(cid, source["condition"], original=source, needs_semantic=True)
    ]

    def semantic(task, packet):
        if task == classification.CLASSIFY:
            return {
                "records": [
                    {
                        "record_id": cid,
                        "kind": "exception",
                        "reason": "显式字段缺失",
                        "parts": [
                            {"condition": source["condition"], "expected": "拒绝", "keys": [KEY]}
                        ],
                    }
                ]
            }
        assert task == alignment.ALIGN and packet["phase"] == "independent_mount"
        [part] = packet["parts"]
        assert not part["candidates"]
        fallback = next(
            option for option in part["mount_options"] if option["field_id"] == price["id"]
        )
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "fallback": fallback,
                    "matches": [],
                    "reason": "测试明确指向本接口的 price 输入字段",
                }
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    bundle = validate(bundle)
    assert not bundle["channels"]["GT"]["pending"]
    [ground_truth] = bundle["channels"]["GT"]["scenarios"]
    assert ground_truth["field_id"] == price["id"]
    report = case_report(bundle)
    [focus] = report["comparison"]["concerns"]
    assert focus["cells"]["G"] and focus["cells"]["GT"]
    assert report["metrics_by_level"]["concern"]["generation_validity"]["numerator"] == 1
    assert report["metrics_by_level"]["scenario"]["generation_validity"]["numerator"] == 0
    assert report["metrics_by_level"]["scenario"]["missing_exception_miss_rate"]["numerator"] == 1
    grouped, _ = business_report.classify(bundle, matching)
    assert [row["id"] for row in grouped["g_only"]] == [generated["id"]]
    assert [row["id"] for row in grouped["gt_only"]] == [ground_truth["id"]]


def test_no_precise_binding_still_keeps_confirmed_type_on_same_interaction():
    bundle = _bundle()
    step, (name,) = _facts(bundle, ["name"])
    _scene(bundle, "G", step, name)
    bundle = validate(bundle)
    cid = "GT-unknown-field"
    source = {
        "id": cid,
        "condition": "某个必填参数缺失",
        "expected": "拒绝",
        "failure_step_id": step["id"],
        "source_refs": [],
    }
    bundle["channels"]["GT"]["pending"] = [
        pending(cid, source["condition"], original=source, needs_semantic=True)
    ]

    def semantic(task, packet):
        if task == classification.CLASSIFY:
            return {
                "records": [
                    {
                        "record_id": cid,
                        "kind": "exception",
                        "reason": "检查必填性",
                        "parts": [
                            {"condition": source["condition"], "expected": "拒绝", "keys": [KEY]}
                        ],
                    }
                ]
            }
        assert task == alignment.ALIGN
        [part] = packet["parts"]
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "fallback": None,
                    "reason": "现场未说明具体字段",
                    "matches": [
                        {"candidate_id": r["id"], "status": "none", "reason": "现场未说明具体字段"}
                        for r in part["candidates"]
                    ],
                }
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    report = case_report(validate(bundle))
    [focus] = report["comparison"]["concerns"]
    assert focus["cells"]["G"] and focus["cells"]["GT"]
    [generated] = [r for r in report["comparison"]["scenarios"] if r.get("generated_id")]
    assert not generated["cells"]["GT"]


def test_required_signals_from_tag_and_model_share_scene_and_both_original_quotes():
    bundle = _bundle()
    _, (name,) = _facts(bundle, ["name"])
    tag = {"document_id": bundle["documents"][0]["id"], "start_line": 2, "end_line": 2}
    quote = {"document_id": tag["document_id"], "start_line": 5, "end_line": 5}
    name["atoms"] = [
        {"concern_key": KEY, "operation": "required", "value": True, "source_refs": [tag]}
    ]
    name["unresolved"] = [
        {
            "text": "按规格提供 name",
            "quote": "该字段必须提供",
            "source_refs": [quote],
        }
    ]

    def semantic(task, packet):
        assert task == "ssd-entity-inference"
        inferred = [
            {
                "rule_id": row["id"],
                "state": "constraint",
                "reason": "同一必填规则",
                "bindings": [{"key": KEY, "failure": "未提供 name", "applies_to": []}],
            }
            for row in packet["constraints"]
            if row["attribute"] == "name"
        ]
        return {"operations": [], "constraints": inferred}

    entity_semantics.infer(bundle, semantic)
    [scene] = [
        row
        for row in bundle["channels"]["G"]["scenarios"]
        if row["key"] == KEY and row.get("field_id") == name["id"]
    ]
    assert scene["source_refs"] == [tag, quote]
    assert len(bundle["channels"]["G"]["concerns"]) >= 1


def test_upgrade_keeps_scene_identity_and_flags_old_focus_decision(tmp_path):
    bundle = _bundle()
    step, (name,) = _facts(bundle, ["name"])
    g = _scene(bundle, "G", step, name)
    gt = _scene(bundle, "GT", step, name)
    legacy = deepcopy(bundle)
    del legacy["input_concern_policy"]
    cid = legacy["case"]["id"]
    head = revisions.publish(tmp_path, legacy)
    edited = deepcopy(head["bundle"])
    edited["decisions"] = [
        {
            "id": "old-focus",
            "level": "concern",
            "pair": "GT_G",
            "left_id": gt["concern_ids"][0],
            "right_id": g["concern_ids"][0],
            "status": "none",
            "origin": "manual",
            "reason": "旧字段级判定",
        },
        {
            "id": "old-scene",
            "level": "scenario",
            "pair": "GT_G",
            "left_id": gt["id"],
            "right_id": g["id"],
            "status": "none",
            "origin": "manual",
            "reason": "具体场景判定",
        },
    ]
    old = revisions.save_revision(
        tmp_path, cid, {"base_revision": head["revision"], "bundle": edited, "reason": "校验迁移"}
    )
    result = revisions.publish(tmp_path, bundle)
    assert {d["id"] for d in result["bundle"]["decisions"]} == {"old-scene"}
    [review] = result["bundle"]["revision_issues"]
    assert review["previous_decision"]["id"] == "old-focus"
    frozen = revisions.editor(tmp_path, cid, old["revision"])
    assert {d["id"] for d in frozen["bundle"]["decisions"]} == {"old-focus", "old-scene"}
