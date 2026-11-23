"""Current scope, independent aggregation, frozen evidence and review round-trips."""

from copy import deepcopy

import pytest

from scene_completion.application import shared_service_service as shared
from scene_completion.application import ssd_revision_service as cases
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.coverage import POLICY as LEGACY_COVERAGE
from scene_completion.domain.current_scope import AVAILABILITY, POLICY, case_report
from scene_completion.domain.project_scopes import matching
from scene_completion.domain.shared_services.aggregation import build
from scene_completion.review.offline import adoption
from tests.support.shared_services import service_case
from tests.support.ssd_results import coverage_bundle


def test_independent_channels_merge_actual_service_faults_keep_members_and_manual_decisions(
    tmp_path,
):
    for cid in ("A", "B"):
        b = service_case(cid, ("service_unavailable", "timeout"))
        b["decisions"].append(
            {
                "id": "manual",
                "level": "scenario",
                "pair": "GT_G",
                "left_id": "GT-timeout",
                "right_id": "G-timeout",
                "status": "partial",
                "origin": "manual",
                "reason": "已人工核对",
            }
        )
        cases.publish(tmp_path, b)
    view = shared.publish(tmp_path)
    b = view["bundle"]
    assert b["analysis_policy"] == POLICY
    assert len(b["anchors"]) == 1 and len(b["anchors"][0]["calls"]) == 2
    for channel in ("E", "G", "GT"):
        assert len(b["channels"][channel]["concerns"]) == 1
        assert len(b["channels"][channel]["scenarios"]) == 2
        for row in b["channels"][channel]["scenarios"]:
            assert {m["case_id"] for m in row["members"]} == {"A", "B"}
            assert len({m["expected"] for m in row["members"]}) == 2
    assert not matching.semantic_candidates(b)  # Different known faults are not candidates.
    assert any(d["status"] == "partial" and len(d["member_decisions"]) == 2 for d in b["decisions"])
    assert (
        shared.index(tmp_path)["metrics"]["by_scope"]["shared_services"]["scenario"][
            "generation_validity"
        ]["denominator"]
        == 2
    )
    # Availability is displayed at the calls but never added again to case metrics.
    for cid in ("A", "B"):
        v = cases.editor(tmp_path, cid)
        assert v["scenario_diagnostic"]["counts"]["G"] == 3


def test_distinct_services_do_not_merge_and_unlocated_records_are_not_discarded():
    a, b = service_case("A"), service_case("B", service_id="OTHER")
    a["channels"]["GT"]["scenarios"][-1]["step_id"] = "missing"
    out = build([{"bundle": a, "revision": 1}, {"bundle": b, "revision": 2}])
    assert len(out["anchors"]) == 2
    assert len(out["channels"]["G"]["scenarios"]) == 2
    assert (
        out["channels"]["GT"]["pending"][0]["member_identity"]["record_id"]
        == "GT-service_unavailable"
    )


def test_scope_exclusion_and_three_categories_many_to_many_and_e_reference(tmp_path):
    b = coverage_bundle()
    # Scope-excluded test results must never inflate the miss-rate denominator.
    original = case_report(b)["metrics"]
    outside = {
        **deepcopy(b["channels"]["GT"]["scenarios"][0]),
        "id": "chain",
        "key": "service_relation.data_isolation",
    }
    b["channels"]["GT"]["scenarios"].append(outside)
    assert case_report(b)["metrics"] == original
    truth = {
        **deepcopy(b["channels"]["GT"]["scenarios"][0]),
        "id": "GT-extra",
        "condition": "新测试失败",
    }
    b["channels"]["GT"]["scenarios"].append(truth)
    for g in b["channels"]["G"]["scenarios"]:
        b["decisions"].append(
            {
                "id": "none-" + g["id"],
                "level": "scenario",
                "pair": "GT_G",
                "left_id": truth["id"],
                "right_id": g["id"],
                "status": "none",
                "origin": "manual",
                "reason": "独立失败",
            }
        )
    cases.publish(tmp_path, b)
    p = adoption.export_payload(tmp_path)
    counts = p["report"]["counts"]
    assert counts["covered"]["total"] == 2
    assert counts["g_only"]["total"] == 1
    assert counts["gt_only"]["total"] == 1
    assert outside["id"] not in str(p["items"][0]["categories"])
    assert adoption.parse(adoption.render_html(p)) == p


def test_shared_adoption_once_idempotent_and_member_conflict_preserves_provenance(tmp_path):
    for cid in ("A", "B"):
        b = service_case(cid)
        for channel in ("E", "GT"):
            for kind in ("concerns", "scenarios"):
                b["channels"][channel][kind] = [
                    r for r in b["channels"][channel][kind] if r["key"] != AVAILABILITY
                ]
        cases.publish(tmp_path, b)
    p = adoption.export_payload(tmp_path)
    item = next(i for i in p["items"] if i["scope"] == "shared_services")
    assert len(item["rows"]) == 1
    gid = item["rows"][0]["cells"]["G"][0]["id"]
    p["decisions"] = [{"item_id": item["id"], "g_id": gid, "adopted": True, "comment": "业务确认"}]
    assert adoption.feedback(tmp_path, p, apply=True)["summary"]["applied"] == 1
    assert adoption.feedback(tmp_path, p, apply=True)["summary"]["unchanged"] >= 1
    gt = [
        r
        for r in shared.editor(tmp_path)["bundle"]["channels"]["GT"]["scenarios"]
        if r.get("origin") == "business_review"
    ]
    assert len(gt) == 1 and len(gt[0]["members"]) == 2
    assert all(m["source"] == "business_review" and not m["source_refs"] for m in gt[0]["members"])
    newer = adoption.export_payload(tmp_path)
    v = cases.editor(tmp_path, "A")
    v["bundle"]["steps"][0]["operation"]["name"] = "已改变"
    cases.save_revision(tmp_path, "A", {"base_revision": v["revision"], "bundle": v["bundle"]})
    shared_item = next(
        i for i in adoption.feedback(tmp_path, newer)["cases"] if i["scope"] == "shared_services"
    )
    assert shared_item["status"] == "unchanged"  # Read-only reference isn't a change request.


def test_unapplied_shared_feedback_conflicts_when_a_member_changes(tmp_path):
    b = service_case()
    for channel in ("E", "GT"):
        b["channels"][channel] = {"concerns": [], "scenarios": [], "pending": []}
    current = cases.publish(tmp_path, b)
    p = adoption.export_payload(tmp_path)
    item = next(i for i in p["items"] if i["scope"] == "shared_services")
    p["decisions"] = [
        {
            "item_id": item["id"],
            "g_id": item["rows"][0]["cells"]["G"][0]["id"],
            "adopted": True,
            "comment": "尚未应用",
        }
    ]
    changed = deepcopy(current["bundle"])
    changed["steps"][0]["operation"]["name"] = "已变化"
    cases.save_revision(tmp_path, "A", {"base_revision": current["revision"], "bundle": changed})
    feedback = next(
        i
        for i in adoption.feedback(tmp_path, p, apply=True)["cases"]
        if i["scope"] == "shared_services"
    )
    assert feedback["status"] == "conflict" and "成员" in feedback["conflicts"][0]


def test_shared_revision_conflicts_and_survives_republish(tmp_path):
    cases.publish(tmp_path, service_case())
    original = shared.publish(tmp_path)
    proposed = deepcopy(original["bundle"])
    proposed["channels"]["G"]["scenarios"][0]["analysis"] = "人工说明"
    saved = shared.save_revision(
        tmp_path, "shared_services", {"base_revision": original["revision"], "bundle": proposed}
    )
    assert shared.publish(tmp_path)["revision"] == saved["revision"]
    cases.publish(tmp_path, service_case("B"))
    current = shared.publish(tmp_path)
    assert current["bundle"]["channels"]["G"]["scenarios"][0]["analysis"] == "人工说明"
    with pytest.raises(cases.RevisionConflict):
        shared.save_revision(
            tmp_path, "shared_services", {"base_revision": saved["revision"], "bundle": proposed}
        )


def test_relocated_member_keeps_human_record_content_in_unbound_area(tmp_path):
    c = cases.publish(tmp_path, service_case())
    original = shared.publish(tmp_path)
    proposed = deepcopy(original["bundle"])
    row = proposed["channels"]["G"]["scenarios"][0]
    row["analysis"] = "必须保留的人工说明"
    shared.save_revision(
        tmp_path, "shared_services", {"base_revision": original["revision"], "bundle": proposed}
    )
    changed = deepcopy(c["bundle"])
    changed["steps"][0]["receiver"].update(id="OTHER", name="另一个明确的外部服务")
    cases.save_revision(tmp_path, "A", {"base_revision": c["revision"], "bundle": changed})
    current = shared.publish(tmp_path)["bundle"]
    retained = next(r for r in current["channels"]["G"]["scenarios"] if r["id"] == row["id"])
    assert retained["status"] == "unbound" and retained["analysis"] == "必须保留的人工说明"
    assert retained["members"] == row["members"]
    assert current["revision_issues"]


def test_seventeen_case_fixture_counts_incomplete_cases_without_hardcoding(tmp_path):
    from scene_completion.infrastructure.storage import write_json

    for n in range(1, 17):
        b = coverage_bundle()
        b["case"].update(id=f"UC-{n:03}", name=f"用例{n}")
        cases.publish(tmp_path, b)
    write_json(
        tmp_path / "run/run_manifest.json", {"ssd_cases": [f"UC-{n:03}" for n in range(1, 18)]}
    )
    p = adoption.export_payload(tmp_path)
    assert p["report"]["case_count"] == 17
    assert not p["report"]["cases"][-1]["complete"]
    assert p["report"]["counts"]["covered"]["total"] == 32
    forged = deepcopy(p)
    forged["report"]["case_count"] = 100
    with pytest.raises(ValueError, match="报告统计"):
        adoption.feedback(tmp_path, forged)


@pytest.mark.parametrize("coverage_policy", [LEGACY_COVERAGE, GRAIN_POLICY])
def test_business_report_offline_controls_and_save_roundtrip(tmp_path, coverage_policy):
    import json
    import subprocess

    from tests.support.paths import ROOT

    bundle = coverage_bundle()
    bundle["coverage_policy"] = coverage_policy
    cases.publish(tmp_path, bundle)
    target = tmp_path / "report.html"
    target.write_text(adoption.export_html(tmp_path), encoding="utf8")
    result = subprocess.run(
        [
            "node",
            str(ROOT / "tests/support/offline_business_report.mjs"),
            str(target),
            str(ROOT / "frontend/node_modules/jsdom/lib/api.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["saved_reopened"]
