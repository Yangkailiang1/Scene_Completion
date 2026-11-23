from pathlib import Path

from scene_completion.application import ssd_revision_service
from scene_completion.domain import business_report
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.domain.ssd import matching, metrics, validation
from scene_completion.domain.ssd.construction import add_concern, add_scenario, channel, pending
from scene_completion.domain.ssd.validation_scope import summary_kind
from scene_completion.domain.ssd_contracts import packet
from scene_completion.review.offline import adoption
from scene_completion.workflow.ssd.compare import alignment
from scene_completion.workflow.ssd.input_conversion.case_builder import build_cases
from scene_completion.workflow.ssd.resolve import classification
from tests.support.ssd_results import coverage_bundle

BROWSE = Path(__file__).resolve().parents[2] / "datasets/mini-mall/examples/browse-product"


def test_validation_summaries_align_to_g_and_keep_other_tests_independent(tmp_path):
    bundle = build_cases(BROWSE, profile=COMMAND_OPERATION_PROFILE)[0]
    bundle.update(coverage_policy=GRAIN_POLICY, gt_source_available=True)
    bundle["channels"] = {name: channel() for name in ("E", "G", "GT")}
    steps = {step["id"]: step for step in bundle["steps"]}
    request = steps[bundle["command_bindings"]["BROWSE-GET"]["primary_step_id"]]
    unrelated = steps[bundle["command_bindings"]["CATALOG-SEARCH"]["primary_step_id"]]
    fields = {f["wire_name"]: f for f in request["data"] if f.get("wire_name")}

    def generated(step, key, condition, field=None):
        out = bundle["channels"]["G"]
        concern = add_concern(
            out, bundle, "G", step, key, "data" if field else "receiver", field=field
        )
        return add_scenario(out, concern, condition, "拒绝", [])

    low = generated(request, "api.data.range", "pageSize < 1", fields["pageSize"])
    high = generated(request, "api.data.range", "pageSize > 100", fields["pageSize"])
    fmt = generated(request, "api.data.format", "page 格式非法", fields["page"])
    other_field = next(
        f
        for f in unrelated["data"]
        if f.get("command_id") == "CATALOG-SEARCH" and "location" not in f
    )
    other = generated(unrelated, "api.data.format", "另一个接口字段格式非法", other_field)
    generated(request, "human.authentication", "凭证缺失")

    def source(identifier, condition, line, *, api="BROWSE-GET", fail="B2"):
        ref = {"document_id": "evidence", "start_line": line, "end_line": line, "quote": condition}
        return pending(
            identifier,
            condition,
            [ref],
            needs_semantic=True,
            original={
                "id": identifier,
                "condition": condition,
                "expected": "拒绝",
                "failure_step_id": fail,
                "api_id": api,
                "source_refs": [ref],
            },
        )

    bundle["channels"]["E"]["pending"] = [
        source("E-summary", "参数校验不通过，产生异常", 2),
        source("E-upper", "参数校验不通过，产生异常；pageSize > 100", 3),
    ]
    bundle["channels"]["GT"]["pending"] = [
        source("GT-fmt", "参数格式非法", 4),
        source("GT-json", "非法JSON校验格式不通过", 5),
        source("GT-high", "pageSize > 100", 6),
        source("GT-high-again", "pageSize > 100", 7),
    ]

    def semantic(task, inputs):
        if task == classification.CLASSIFY:
            assert all(summary_kind(row["condition"]) is None for row in inputs["records"])
            return {
                "records": [
                    {
                        "record_id": row["id"],
                        "kind": "exception",
                        "reason": "超出上界",
                        "parts": [
                            {
                                "condition": row["condition"].split("；")[-1],
                                "expected": "拒绝",
                                "keys": ["api.data.range"],
                            }
                        ],
                    }
                    for row in inputs["records"]
                ]
            }
        assert task == alignment.ALIGN
        assert inputs["coverage_policy"] == GRAIN_POLICY
        assert all(part["condition"] == "pageSize > 100" for part in inputs["parts"])
        assert all(
            {candidate["id"] for candidate in part["candidates"]} == {high["id"]}
            for part in inputs["parts"]
        )
        return {
            "parts": [
                {
                    "part_id": part["id"],
                    "fallback": None,
                    "reason": "同一分页上界",
                    "matches": [
                        {"candidate_id": high["id"], "status": "full", "reason": "超出同一上界"}
                    ],
                }
                for part in inputs["parts"]
            ]
        }

    classification.classify(bundle, semantic)
    alignment.align(bundle, semantic)
    bundle = validation.validate(bundle)
    assert not bundle["channels"]["GT"]["pending"]
    assert all(d["status"] in {"full", "none"} for d in bundle["decisions"])

    report = metrics.analyze(bundle)
    rows = {
        row["generated_id"]: row["cells"]
        for row in report["comparison"]["scenarios"]
        if row.get("generated_id")
    }
    assert {ref["start_line"] for ref in rows[high["id"]]["E"][1]["source_refs"]} == {2, 3}
    assert [r["condition"] for r in rows[high["id"]]["E"]] == [
        "pageSize > 100",
        "参数校验不通过，产生异常",
    ]
    assert len(rows[low["id"]]["E"]) == 1 and not rows[low["id"]]["GT"]
    assert [r["condition"] for r in rows[fmt["id"]]["GT"]] == ["参数格式非法"]
    assert not rows[other["id"]]["E"] and not rows[other["id"]]["GT"]
    truth = rows[high["id"]]["GT"]
    assert len(truth) == 1 and {r["start_line"] for r in truth[0]["source_refs"]} == {6, 7}
    assert all(r["failure_step_id"] == "B2" for r in rows[high["id"]]["E"] + truth)
    diagnostic = report["scenario_diagnostic"]
    assert diagnostic["generation_validity"]["numerator"] == 2
    assert diagnostic["missing_exception_miss_rate"]["numerator"] == 1
    assert diagnostic["missing_exception_miss_rate"]["denominator"] == 1
    groups, excluded = business_report.classify(bundle, matching)
    assert not excluded
    assert {row["id"] for row in groups["covered"]} == {high["id"], fmt["id"]}
    assert [r["condition"] for r in groups["gt_only"][0]["cells"]["GT"]] == [
        "非法JSON校验格式不通过"
    ]

    snapshot = ssd_revision_service.publish(tmp_path, bundle)
    saved = ssd_revision_service.save_revision(
        tmp_path,
        bundle["case"]["id"],
        {"base_revision": snapshot["revision"], "bundle": bundle, "reason": "核验新版口径"},
    )
    assert saved["bundle"]["coverage_policy"] == GRAIN_POLICY
    html = adoption.export_html(tmp_path, {"scopes": ["interaction"]})
    export = adoption.parse(html)
    item = export["items"][0]
    assert "reference_rows" in item
    upper = next(
        row for row in item["reference_rows"]["scenarios"] if row["cells"]["G"] == [high["id"]]
    )
    assert upper["cells"]["E"] == [r["id"] for r in rows[high["id"]]["E"]]
    assert export["report"]["counts"]["covered"]["total"] == 2
    assert export["report"]["counts"]["gt_only"]["total"] == 1


def test_binary_packets_keep_legacy_contract_readable():
    for policy, expected in [(GRAIN_POLICY, ["full", "none"]), (None, ["full", "partial", "none"])]:
        inputs = {"coverage_policy": policy}
        ground = packet("ssd-ground-align", inputs, [])
        props = ground["output_schema"]["properties"]["parts"]["items"]["properties"]
        assert props["matches"]["items"]["properties"]["status"]["enum"] == expected
        compare = packet("ssd-semantic-compare", inputs, [])
        props = compare["output_schema"]["properties"]["decisions"]["items"]["properties"]
        assert props["status"]["enum"] == expected


def test_unfinished_obligations_do_not_count_as_misses_or_invalid_generation():
    bundle = coverage_bundle()
    bundle.update(coverage_policy=GRAIN_POLICY, gt_source_available=True)
    gt = bundle["channels"]["GT"]["scenarios"]
    decisions = bundle["decisions"]
    gt.append({**gt[0], "id": "GT-extra", "condition": "签名信任链无效"})
    decisions.extend(
        {
            "id": "none-" + generated["id"],
            "pair": "GT_G",
            "level": "scenario",
            "left_id": "GT-extra",
            "right_id": generated["id"],
            "status": "none",
        }
        for generated in bundle["channels"]["G"]["scenarios"]
    )

    for identified, pending_ids in [(False, []), (True, ["G-third"])]:
        bundle["gt_identification_run_complete"] = identified
        bundle["scenario_generation"] = {"pending_ids": pending_ids}
        report = metrics.analyze(bundle)["scenario_diagnostic"]
        assert report["generation_validity"]["numerator"] == 2
        assert report["generation_validity"]["denominator"] == 2
        assert report["missing_exception_miss_rate"]["numerator"] == 0
        assert report["missing_truth_ids"] == []
        groups, _ = business_report.classify(bundle, matching)
        assert not groups["g_only"] and not groups["gt_only"]

    bundle["scenario_generation"]["pending_ids"] = []
    report = metrics.analyze(bundle)["scenario_diagnostic"]
    assert report["generation_validity"]["denominator"] == 3
    assert report["missing_truth_ids"] == ["GT-extra"]
    groups, _ = business_report.classify(bundle, matching)
    assert [row["id"] for row in groups["g_only"]] == ["G-third"]
    assert [row["id"] for row in groups["gt_only"]] == ["GT-extra"]

    bundle["gt_identification_run_complete"] = False
    bundle["decisions"] = [row for row in decisions if row["status"] == "none"]
    report = metrics.analyze(bundle)["scenario_diagnostic"]
    assert report["generation_validity"]["status"] == "未评估"
    assert report["generation_validity"]["denominator"] == 0
    assert report["missing_exception_miss_rate"]["status"] == "未评估"
