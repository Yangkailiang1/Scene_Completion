import json
from copy import deepcopy
from pathlib import Path

import pytest

from scene_completion.application import ssd_revision_service
from scene_completion.domain import business_report
from scene_completion.domain.coverage import GRAIN_POLICY, review_statuses
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, case_report
from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd import matching
from scene_completion.domain.ssd.construction import channel, pending
from scene_completion.review.offline.business_report_export import export_html
from scene_completion.workflow.ssd.compare import alignment, decision_review, stage
from scene_completion.workflow.ssd.generate.fixed import generate_g
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification, entity_semantics
from scene_completion.workflow.ssd.shared import authentication_evidence

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"


@pytest.fixture
def bundle():
    [bundle] = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)
    bundle.update(coverage_policy=GRAIN_POLICY, gt_source_available=True)
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    bundle["commands"][0]["authentication"] = "required"
    bundle["channels"]["G"] = generate_g(bundle)
    for scenario in bundle["channels"]["G"]["scenarios"]:
        scenario["analysis"] = "固定夹具的生成分析已完成"
    return bundle


def _auth(bundle):
    return next(row for row in bundle["channels"]["G"]["scenarios"] if row["key"] == policy.AUTH)


def _source(bundle, condition, *, expected="返回 HTTP 401", step="B2", hint=None, channel="GT"):
    records = bundle["channels"][channel]["pending"]
    source = {
        "id": f"{channel}-source-{len(records)}",
        "condition": condition,
        "expected": expected,
        "failure_step_id": step,
        "failure_step_hint": hint,
        "source_refs": [
            {"document_id": bundle["documents"][0]["id"], "start_line": 1, "end_line": 1}
        ],
    }
    records.append(
        pending(
            source["id"], condition, source["source_refs"], original=source, needs_semantic=True
        )
    )
    return source["id"]


def _no_model(task, _):
    pytest.fail(f"规则已经能完成该项判断，仍调用了 {task}")


def _result(part, matches, **extra):
    return {
        "part_id": part["id"],
        "reason": "依据来源及候选逐项判定",
        "matches": [
            {"candidate_id": cid, "status": status, "reason": reason}
            for cid, status, reason in matches
        ],
        "fallback": None,
        **extra,
    }


def test_explicit_auth_variants_use_no_model_and_count_one_g(bundle):
    conditions = [
        "Authorization 缺失",
        "Authorization 为空",
        "Authorization 非法",
        "Token 校验失败",
        "Token 已过期",
        "请求头 Authorization 缺失／为空／非法",
    ]
    for condition in conditions:
        _source(bundle, condition)
    _source(bundle, "Authorization 为空", channel="E")
    classification.classify(bundle, _no_model)
    alignment.align(bundle, _no_model)
    gt = bundle["channels"]["GT"]
    assert not gt["pending"]
    assert {row["condition"] for row in gt["scenarios"]} == set(conditions)
    assert all(row["step_id"] == "B1" and row["failure_step_id"] == "B2" for row in gt["scenarios"])
    [covered] = business_report.classify(bundle, matching)[0]["covered"]
    assert covered["id"] == _auth(bundle)["id"]
    assert len(covered["cells"]["GT"]) == 6
    assert len(covered["cells"]["E"]) == 1


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("非法", "401"),
        ("Authorization 无效", "返回 403"),
        ("Authorization 缺失或请求体为空", "返回 401"),
        ("Authorization 非法", "返回 HTTP 401，同时记录审计并封禁"),
        ("Authorization 为空，返回 200", "返回 HTTP 401"),
    ],
)
def test_unclear_or_inconsistent_auth_conditions_are_not_script_matches(condition, expected):
    assert not authentication_evidence.explicit_variants(condition, expected)


def test_exact_match_requires_the_same_request_and_declared_field(bundle):
    steps = {s["id"]: s for s in entity_semantics._steps(bundle)}
    field = next(row for row in bundle["steps"][0]["data"] if row["name"] == "page")
    condition = "page 超出允许范围"
    expected = "拒绝请求"
    part = {
        "failure_step_id": "B1",
        "keys": ["api.data.range"],
        "condition": condition,
        "expected": expected,
    }
    candidate = {
        **part,
        "step_id": "B1",
        "key": "api.data.range",
        "target": "data",
        "command_id": "BROWSE-GET",
        "field_id": field["id"],
    }
    source = {"parameter": {"name": "page", "command_id": "BROWSE-GET"}}
    assert alignment._fast_match(bundle, part, candidate, source, steps)[0] == "full"
    for change in (
        {"parameter": {"name": "pageSize", "command_id": "BROWSE-GET"}},
        {"parameter": {"name": "page", "command_id": "CATALOG-SEARCH"}},
        {},
    ):
        assert alignment._fast_match(bundle, part, candidate, change, steps) is None


def test_only_step_hint_keeps_auth_in_semantic_comparison(bundle):
    _source(bundle, "Authorization 为空", step=None, hint={"ref": "B2"})
    classification.classify(bundle, _no_model)

    def semantic(task, packet):
        assert task == alignment.ALIGN
        [part] = packet["parts"]
        assert part["failure_step_id"] is None and part["failure_step_hint"] == {"ref": "B2"}
        [candidate] = part["candidates"]
        return {
            "parts": [
                _result(
                    part,
                    [(candidate["id"], "full", "原文和上下文指向商城入口的凭证为空")],
                    failure_step_id="B2",
                    failure_step_reason="证据证明 B2 校验 B1 的请求头",
                )
            ]
        }

    alignment.align(bundle, semantic)
    [row] = bundle["channels"]["GT"]["scenarios"]
    assert (row["step_id"], row["failure_step_id"]) == ("B1", "B2")


def test_script_match_and_semantic_candidate_share_one_source(bundle):
    original = _auth(bundle)
    different = {
        **deepcopy(original),
        "id": "authentication-with-a-specific-outcome",
        "condition": "验证身份失败时返回专用业务状态",
        "expected": "要求客户重新发起会话并返回业务错误",
    }
    bundle["channels"]["G"]["scenarios"].append(different)
    _source(bundle, "Authorization 为空")
    classification.classify(bundle, _no_model)

    def semantic(task, packet):
        assert task == alignment.ALIGN
        [part] = packet["parts"]
        assert part["has_confirmed_match"]
        assert [row["id"] for row in part["candidates"]] == [different["id"]]
        return {"parts": [_result(part, [(different["id"], "none", "处理预期不同")])]}

    alignment.align(bundle, semantic)
    assert {
        (d["right_id"], d["status"])
        for d in bundle["decisions"]
        if d["pair"] == "GT_G" and d["level"] == "scenario"
    } == {(original["id"], "full"), (different["id"], "none")}


def test_different_boundaries_and_optional_auth_are_not_covered_by_401(bundle):
    _source(bundle, "Authorization 缺失", step="B3")
    bundle["commands"][0]["authentication"] = "optional"
    bundle["channels"]["G"] = generate_g(bundle)
    source = _source(bundle, "Authorization 缺失", step="B2")
    classification.classify(bundle, _no_model)
    alignment.align(bundle, _no_model)
    assert not [
        decision
        for decision in bundle["decisions"]
        if decision["pair"] == "GT_G"
        and decision["status"] == "full"
        and decision["level"] == "scenario"
    ]
    audits = bundle["source_classifications"]["GT"]
    assert {row["kind"] for row in audits if row["record_id"] != source} == {"out_of_scope"}


def test_boundary_downgrade_replaces_reason_and_preserves_other_matches(bundle):
    steps = entity_semantics._steps(bundle)
    candidates = [
        {"id": "auth", "key": policy.AUTH, "step_id": "B1", "target": "sender"},
        {"id": "other", "key": policy.COMPLETENESS, "step_id": "B3", "target": "data"},
    ]
    part = {
        "id": "p1",
        "keys": [policy.AUTH, policy.COMPLETENESS],
        "candidates": candidates,
        "failure_step_id": None,
    }
    result = _result(
        part,
        [("auth", "full", "判 full"), ("other", "full", "同一字段的缺失条件")],
        failure_step_id="B3",
        failure_step_reason="证据定位到 B3",
    )
    [row] = alignment.validate_result(
        alignment.ALIGN, {"parts": [result]}, {"steps": steps, "parts": [part]}
    )["parts"]
    auth, other = row["matches"]
    assert auth["status"] == "none" and "同一人类 Actor 请求边界" in auth["reason"]
    assert other["status"] == "full"
    assert not decision_review.contradictory(auth)


def _wording_case(bundle):
    original = _auth(bundle)
    alternative = {
        **deepcopy(original),
        "id": "other-credential-check",
        "condition": "请求时身份校验异常",
    }
    variant = {
        **deepcopy(original),
        "id": "credential-result-with-different-wording",
        "condition": "身份校验出现异常",
    }
    bundle["channels"]["G"]["scenarios"].extend([alternative, variant])
    return original, alternative, variant


def test_ground_retry_sends_only_conflicting_pairs_and_keeps_valid_ones(bundle):
    original, alternative, variant = _wording_case(bundle)
    _source(bundle, "入口认证失败，具体凭证错误", step="B2")
    calls = []

    def semantic(task, packet):
        if task == classification.CLASSIFY:
            [source] = packet["records"]
            return {
                "records": [
                    {
                        "record_id": source["id"],
                        "kind": "exception",
                        "reason": "原文明确身份认证失败",
                        "parts": [
                            {
                                "condition": source["condition"],
                                "expected": source["expected"],
                                "keys": [policy.AUTH],
                            }
                        ],
                    }
                ]
            }
        assert task == alignment.ALIGN
        [part] = packet["parts"]
        ids = {candidate["id"] for candidate in part["candidates"]}
        calls.append(ids)
        if packet.get("decision_recheck"):
            assert original["id"] not in ids
            return {
                "parts": [
                    _result(
                        part,
                        [
                            (alternative["id"], "full", "同一认证失败及相同拒绝预期"),
                            (variant["id"], "none", "判full同义"),
                        ],
                    )
                ]
            }
        return {
            "parts": [
                _result(
                    part,
                    [
                        (original["id"], "full", "同一认证失败及相同拒绝预期"),
                        (alternative["id"], "none", "失败条件和预期均等价"),
                        (variant["id"], "none", "判 full，同一请求同一责任对象"),
                    ],
                )
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    assert calls == [
        {original["id"], alternative["id"], variant["id"]},
        {alternative["id"], variant["id"]},
    ]
    [truth] = bundle["channels"]["GT"]["scenarios"]
    [gap] = matching.semantic_candidates(bundle)
    assert (gap["left_id"], gap["right_id"]) == (truth["id"], variant["id"])
    assert gap["reason"] == decision_review.REASON
    assert review_statuses(bundle, matching)[variant["id"]]["reason"] == "matching_pending"
    assert {row["id"] for row in business_report.classify(bundle, matching)[0]["covered"]} == {
        original["id"],
        alternative["id"],
    }
    bundle["decisions"].append(
        {
            "id": "human-decision",
            "level": "scenario",
            "pair": "GT_G",
            "left_id": truth["id"],
            "right_id": variant["id"],
            "status": "none",
            "reason": "按证据独立复核",
            "origin": "manual",
        }
    )
    assert not matching.semantic_candidates(bundle)
    assert review_statuses(bundle, matching)[variant["id"]]["reason"] == "eligible"


def test_remaining_semantic_pair_retry_marks_only_affected_records(bundle, tmp_path):
    original, alternative, variant = _wording_case(bundle)
    [parent] = original["concern_ids"]
    bundle["channels"]["GT"]["concerns"].append(
        {
            **next(r for r in bundle["channels"]["G"]["concerns"] if r["id"] == parent),
            "id": "gt-auth",
        }
    )
    truth = {
        **deepcopy(original),
        "id": "test-auth",
        "concern_ids": ["gt-auth"],
        "condition": "测试确认认证响应异常",
    }
    bundle["channels"]["GT"]["scenarios"].append(truth)
    calls = []

    class Executor:
        mode = "responses"

        def semantic(self, task, inputs, record):
            assert task == "ssd-semantic-compare"
            ids = {row["right"]["id"] for row in inputs["pairs"]}
            calls.append(ids)
            rows = []
            for ident in sorted(ids):
                status, reason = {
                    original["id"]: ("none", "同一请求同一责任对象"),
                    alternative["id"]: ("none", "应判 full"),
                    variant["id"]: ("none", "判 full"),
                }[ident]
                if ident == alternative["id"] and inputs.get("decision_recheck"):
                    status, reason = "none", "原文验证了不同的返回行为"
                rows.append(
                    {"left_id": truth["id"], "right_id": ident, "status": status, "reason": reason}
                )
            return {"decisions": rows}, None

    result = stage._compare_pairs(Executor(), bundle, {})
    assert calls == [
        {original["id"], alternative["id"], variant["id"]},
        {alternative["id"], variant["id"]},
    ]
    assert {d["right_id"] for d in result["decisions"]} == {original["id"], alternative["id"]}
    [conflict] = result["semantic_pending"]
    assert conflict["right_id"] == variant["id"]
    report = case_report(result)
    assert report["completeness"]["semantic_pairs"] == 1
    groups, excluded = business_report.classify(result, matching)
    assert not groups["gt_only"]
    assert any(r["id"] == truth["id"] for r in excluded)
    assert any(r["id"] == variant["id"] and r["reason"] == "匹配未完成" for r in excluded)

    ssd_revision_service.publish(tmp_path, result)
    html = export_html(tmp_path, {"scopes": ["interaction"]})
    data = html.split('id="ssd-business-report-data">', 1)[1].split("</script>", 1)[0]
    [group] = json.loads(data)["report"]["groups"]
    assert any(row["id"] == variant["id"] for row in group["excluded"])
    assert not group["categories"]["gt_only"]


def test_only_contradictory_candidates_keep_source_pending_without_blocking_its_step(bundle):
    generated = _auth(bundle)
    unrelated = next(
        row
        for row in bundle["channels"]["G"]["scenarios"]
        if row["id"] != generated["id"] and row["step_id"] == generated["step_id"]
    )
    source = _source(bundle, "入口认证失败，具体凭证错误")
    bundle["channels"]["GT"]["pending"][0]["step_id"] = generated["step_id"]
    bundle["source_classifications"] = {
        "GT": [
            {
                "record_id": source,
                "kind": "exception",
                "reason": "要求与入口认证场景核对",
                "parts": [
                    {
                        "condition": "入口认证失败，具体凭证错误",
                        "expected": "返回 401",
                        "keys": [policy.AUTH],
                    }
                ],
            }
        ]
    }
    calls = []

    def semantic(task, inputs):
        assert task == alignment.ALIGN
        [part] = inputs["parts"]
        calls.append(inputs.get("decision_recheck"))
        return {"parts": [_result(part, [(generated["id"], "none", "判 full")])]}

    alignment.align(bundle, semantic)
    assert calls == [None, True]
    [row] = bundle["channels"]["GT"]["pending"]
    assert row["id"] == source and row["step_id"] is None
    [pair] = matching.semantic_candidates(bundle)
    assert pair["left_id"] == source and pair["right_id"] == generated["id"]
    statuses = review_statuses(bundle, matching)
    assert statuses[generated["id"]]["reason"] == "matching_pending"
    assert statuses[unrelated["id"]]["reason"] == "eligible"
