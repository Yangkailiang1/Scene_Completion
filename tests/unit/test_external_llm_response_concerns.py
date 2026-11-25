from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.application import ssd_revision_service
from scene_completion.domain.current_scope import (
    AVAILABILITY,
    COMMAND_OPERATION_PROFILE,
    case_report,
)
from scene_completion.domain.shared_services.aggregation import build
from scene_completion.domain.ssd import llm_responses
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.domain.ssd.validation import validate
from scene_completion.domain.ssd_contracts import SCHEMAS
from scene_completion.review.offline import adoption
from scene_completion.workflow.ssd.compare.alignment import align
from scene_completion.workflow.ssd.generate import fixed, scenarios
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification, operations, participants

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"
KEY = llm_responses.KEY


def _fixture():
    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    base = bundle["steps"][0]
    internal = base["receiver"]
    external = {
        "id": "model-a",
        "name": "PlanModel",
        "type": "service",
        "external": True,
        "technology": "llm",
    }

    def add(step_id, label, *, direction="request", service=None, parent=None, crud=None):
        service = service or external
        sender, receiver = (internal, service) if direction == "request" else (service, internal)
        step = {
            **deepcopy(base),
            "id": step_id,
            "kind": "interaction",
            "direction": direction,
            "order": max(s["order"] for s in bundle["steps"]) + 1,
            "description": label,
            "operation": {"name": label, "kinds": crud or [], "kinds_source": "declared"},
            "api_id": None,
            "data": [],
            "entity_ids": [],
            "aliases": [],
            "parent_id": parent,
            "sender": sender,
            "receiver": receiver,
        }
        bundle["steps"].append(step)
        return step

    bundle["channels"] = {name: channel() for name in ("G", "E", "GT")}
    return bundle, external, add


def _rows(records):
    return [row for row in records if row["key"] == KEY]


def _evidence(bundle, side, identity, condition, failure_step):
    source = {
        "id": identity,
        "condition": condition,
        "expected": "",
        "source_refs": [],
        "failure_step_id": failure_step,
    }
    bundle["channels"][side]["pending"].append(
        pending(identity, condition, original=source, needs_semantic=True)
    )


def test_generation_and_evidence_use_one_model_anchor_and_preserve_failure_occurrences(tmp_path):
    bundle, service, add = _fixture()
    add("M0", "PlanModel 返回预览", direction="return")
    add("M1", "向 PlanModel 发送请求 JSON", crud=["read"])
    add("M2", "PlanModel 返回 JSON，响应必填字段是 result", direction="return", parent="M1")
    add("M3", "调用 PlanModel 创建结果", crud=["create"])
    add("M4", "PlanModel 返回 JSON", direction="return", parent="M3")
    other = {**service, "id": "model-b", "name": "OtherModel"}
    add("O1", "OtherModel 返回 JSON", direction="return", service=other)
    ordinary = {**service, "id": "ordinary", "name": "Ordinary", "technology": None}
    add("P1", "Ordinary 返回 JSON", direction="return", service=ordinary)
    add("I1", "调用内部模型", service={**service, "id": "internal", "external": False})
    operations.resolve(bundle, None)
    bundle["channels"]["G"] = generated = fixed.generate_g(bundle)
    assert {(r["step_id"], r["target"]) for r in _rows(generated["concerns"])} == {
        ("M1", "receiver"),
        ("O1", "sender"),
    }
    assert {r["variant_id"] for r in _rows(generated["scenarios"]) if r["step_id"] == "M1"} == {
        llm_responses.JSON,
        llm_responses.REQUIRED,
    }
    [first] = [r for r in _rows(generated["concerns"]) if r["step_id"] == "M1"]
    assert first["related_call_step_ids"] == ["M0", "M1", "M2", "M3", "M4"]
    assert {
        (unit["step_id"], tuple(unit["crud"]), tuple(unit["occurrences"]))
        for unit in bundle["operation_units"]
        if unit["receiver_id"] == service["id"]
    } == {("M1", ("read",), ("M1",)), ("M3", ("create",), ("M3",))}

    _evidence(bundle, "E", "E1", "返回的 JSON 无法解析", "M4")
    _evidence(bundle, "GT", "T1", "响应缺少必填字段 result", "M2")
    _evidence(bundle, "GT", "T2", "返回的 JSON 无法解析", "O1")
    _evidence(bundle, "GT", "T3", "返回的数据格式错误", "P1")

    def semantic(task, inputs):
        assert task == "ssd-ground-align"
        reply = []
        for part in inputs["parts"]:
            [candidate] = part["candidates"]
            expected_step = "O1" if part["failure_step_id"] == "O1" else "M1"
            assert candidate["step_id"] == expected_step
            reply.append(
                {
                    "part_id": part["id"],
                    "reason": "同一模型的同类失败",
                    "matches": [
                        {"candidate_id": candidate["id"], "status": "full", "reason": "同一失败"}
                    ],
                    "fallback": None,
                }
            )
        return {"parts": reply}

    classification.classify(bundle, semantic)
    align(bundle, semantic)
    validate(bundle)
    assert bundle["channels"]["GT"]["pending"] == []
    assert [
        (r["step_id"], r["failure_step_id"]) for r in _rows(bundle["channels"]["E"]["scenarios"])
    ] == [
        ("M1", "M4"),
    ]
    assert {
        (r["step_id"], r["failure_step_id"]) for r in _rows(bundle["channels"]["GT"]["scenarios"])
    } == {
        ("M1", "M2"),
        ("O1", "O1"),
    }
    assert bundle["source_classifications"]["GT"][2]["kind"] == "out_of_scope"
    report = case_report(bundle)
    assert first["id"] in {
        r["id"] for row in report["comparison"]["concerns"] for r in row["cells"]["G"]
    }
    assert report["scenario_diagnostic"]["generation_validity"]["numerator"] == 2
    merged = build([{"bundle": bundle, "revision": 1}])
    assert {r["key"] for r in merged["channels"]["G"]["scenarios"]} == {AVAILABILITY}
    ssd_revision_service.publish(tmp_path, bundle)
    exported = adoption.parse(adoption.export_html(tmp_path))
    [interaction] = [item for item in exported["items"] if item["scope"] == "interaction"]
    assert {
        row["cells"]["G"][0]["variant_id"]
        for row in interaction["categories"]["covered"]
        if row["cells"]["G"][0]["key"] == KEY
    } == {llm_responses.JSON, llm_responses.REQUIRED}


@pytest.mark.parametrize("with_g", [True, False])
def test_unproven_response_contract_stays_generic_and_specific_evidence_is_independent(with_g):
    bundle, _, add = _fixture()
    add("M1", "请求携带 JSON，模型返回自然语言")
    add("M2", "模型返回解释，说明 JSON 的用途", direction="return", parent="M1")
    add("M3", "模型返回预测结果", direction="return", parent="M1")
    bundle["operation_units"] = []
    bundle["channels"]["G"] = fixed.generate_g(bundle) if with_g else channel()
    assert [r["variant_id"] for r in _rows(bundle["channels"]["G"]["scenarios"])] == (
        [llm_responses.GENERIC] if with_g else []
    )
    _evidence(bundle, "GT", "T1", "响应缺少必填字段 score", "M3")

    def semantic(task, inputs):
        pytest.fail(f"不应要求模型比较不同义务或重新决定已确认的挂载边界: {task}")

    classification.classify(bundle, semantic)
    align(bundle, semantic)
    assert bundle["channels"]["GT"]["pending"] == []
    [scenario] = _rows(bundle["channels"]["GT"]["scenarios"])
    assert (scenario["step_id"], scenario["failure_step_id"], scenario["variant_id"]) == (
        "M1",
        "M3",
        llm_responses.REQUIRED,
    )
    assert not bundle.get("decisions")


def test_model_technology_uses_own_quotes_and_preserves_explicit_type():
    bundle, external, add = _fixture()
    party = {
        **external,
        "technology": None,
        "role": "external",
        "source_refs": [
            {
                "document": "srSpec",
                "start_line": 11,
                "end_line": 11,
                "quote": "PlanModel 是本平台调用的外部大语言模型服务。",
            }
        ],
    }
    add("M1", "调用 PlanModel", service=party)
    add("M2", "调用已标注的模型", service={**party, "id": "known", "technology": "llm"})

    def semantic(task, inputs):
        assert task == participants.TASK
        contract = SCHEMAS[task]["properties"]["participants"]["items"]["properties"]["technology"]
        assert "llm" in contract["enum"]
        answers = []
        for value in inputs["participants"]:
            if value["id"] == "model-a":
                [reference] = value["source_refs"]
                assert "外部大语言模型服务" in reference["quote"]
                answers.append(
                    {
                        "participant_id": value["id"],
                        "kind": "external_service",
                        "technology": "llm",
                        "source_ref_ids": [reference["id"]],
                        "reason": "原文明示身份",
                    }
                )
            else:
                answers.append(
                    {
                        "participant_id": value["id"],
                        "kind": None,
                        "technology": None,
                        "source_ref_ids": [],
                        "reason": "保留现有身份",
                    }
                )
        return participants.validate_result({"participants": answers}, inputs)

    participants.classify(bundle, semantic)
    assert {r["receiver"]["technology"] for r in bundle["steps"] if r["id"] in {"M1", "M2"}} == {
        "llm"
    }


def test_llm_generation_rejects_uncontracted_supplements():
    inputs = {
        "templates": [],
        "concerns": [{"key": KEY, "id": "L1"}],
        "all_failure_conditions": [],
    }
    with pytest.raises(ValueError, match="按响应契约选定的固定模板"):
        scenarios.validate_result(
            {
                "analyses": [],
                "supplements": [
                    {
                        "concern_id": "L1",
                        "condition": "未声明的字段缺失",
                        "expected": "重试",
                        "analysis": "分析",
                    }
                ],
            },
            inputs,
        )
