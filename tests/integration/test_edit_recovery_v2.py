from copy import deepcopy

import pytest

from scene_completion.application import ssd_revision_service as service
from scene_completion.domain.coverage import review_candidates
from scene_completion.domain.ssd import matching
from scene_completion.domain.ssd.metrics import analyze
from scene_completion.review.offline import adoption
from tests.support.ssd_results import coverage_bundle


def test_partial_one_truth_covers_multiple_g_and_legacy_is_frozen():
    b = coverage_bundle()
    rates = analyze(b)
    assert rates["scenario_diagnostic"]["generation_validity"]["numerator"] == 2
    assert rates["scenario_diagnostic"]["generation_validity"]["denominator"] == 3
    assert rates["scenario_diagnostic"]["missing_exception_miss_rate"]["numerator"] == 0
    legacy = deepcopy(b)
    legacy.pop("coverage_policy")
    assert analyze(legacy)["scenario_diagnostic"]["generation_validity"]["numerator"] == 0
    records, counters = review_candidates(b, matching)
    assert [r["id"] for r in records] == ["G-third"] and counters["covered"] == 2
    b["decisions"].pop()
    assert not review_candidates(b, matching)[0]


def test_adoption_is_gt_only_versioned_and_idempotent(tmp_path):
    service.publish(tmp_path, coverage_bundle())
    payload = adoption.export_payload(tmp_path, {"scopes": ["interaction"]})
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert [r["cells"]["G"][0]["id"] for r in item["rows"]] == ["G-third"]
    payload["decisions"] = [
        {"item_id": item["id"], "g_id": "G-third", "adopted": True, "comment": "采纳，需补充测试"}
    ]
    original = service.editor(tmp_path, "case")["bundle"]
    preview = adoption.feedback(tmp_path, payload)
    assert preview["cases"][0]["status"] == "ready"
    applied = adoption.feedback(tmp_path, payload, apply=True)
    assert applied["cases"][0]["status"] == "applied"
    current = service.editor(tmp_path, "case")["bundle"]
    assert current["channels"]["E"] == original["channels"]["E"]
    assert current["channels"]["G"] == original["channels"]["G"]
    added = next(
        r for r in current["channels"]["GT"]["scenarios"] if r.get("origin") == "business_review"
    )
    assert added["source_refs"] == [] and added["adopted_from_g"] == "G-third"
    assert added["review_comment"] == "采纳，需补充测试"
    assert adoption.feedback(tmp_path, payload, apply=True)["cases"][0]["status"] == "unchanged"
    assert service.editor(tmp_path, "case", 1)["bundle"] == original
    for key in ("steps", "channels", "documents"):
        bad = deepcopy(payload)
        bad["items"][0]["bundle"][key] = [{"tampered": True}]
        with pytest.raises(ValueError, match="只读上下文"):
            adoption.feedback(tmp_path, bad)
    bad = deepcopy(payload)
    bad["items"][0]["rows"].append(deepcopy(item["rows"][0]))
    with pytest.raises(ValueError):
        adoption.feedback(tmp_path, bad)


def test_no_adoption_only_comments_keeps_gt_unchanged(tmp_path):
    first = service.publish(tmp_path, coverage_bundle())
    payload = adoption.export_payload(tmp_path, {"scopes": ["interaction"]})
    item = payload["items"][0]
    payload["decisions"] = [
        {"item_id": item["id"], "g_id": "G-third", "adopted": False, "comment": "暂不采纳"}
    ]
    adoption.feedback(tmp_path, payload, apply=True)
    assert (
        service.editor(tmp_path, "case")["bundle"]["channels"]["GT"]
        == first["bundle"]["channels"]["GT"]
    )


def test_pending_sources_only_block_relevant_anchor_and_unrun_identification_blocks_export():
    b = coverage_bundle()
    b["channels"]["GT"]["pending"] = [{"id": "unknown", "step_id": "other", "status": "pending"}]
    assert [r["id"] for r in review_candidates(b, matching)[0]] == ["G-third"]
    b["channels"]["GT"]["pending"][0]["step_id"] = "step"
    assert not review_candidates(b, matching)[0]
    b["channels"]["GT"]["pending"] = []
    b["gt_identification_run_complete"] = False
    assert not review_candidates(b, matching)[0]
    b["gt_identification_run_complete"] = True
    b["scenario_generation"] = {"pending_ids": ["G-third"]}
    assert not review_candidates(b, matching)[0]


def test_adoption_http_roundtrip_rejects_readonly_tampering(tmp_path):
    import json

    from fastapi.testclient import TestClient

    from scene_completion.api.application import create_app
    from scene_completion.application.project_service import Workbench

    workbench = Workbench(tmp_path / "data")
    meta = workbench.create(
        {
            "name": "review",
            "sources": {r: [{"name": r + ".md", "content": "# Context"}] for r in ("RR", "SR")},
        }
    )
    project = workbench.run_dir(meta["id"])
    service.publish(project, coverage_bundle())
    with TestClient(create_app(workbench.root)) as client:
        base = "/api/projects/" + meta["id"] + "/ssd-review"
        response = client.post(base + "/export", json={"scopes": ["interaction"]})
        payload = adoption.parse(response.text)
        payload["decisions"] = [
            {
                "item_id": payload["items"][0]["id"],
                "g_id": "G-third",
                "adopted": True,
                "comment": "业务补充",
            }
        ]
        content = json.dumps(payload)
        assert (
            client.post(base + "/preview", json={"content": content}).json()["cases"][0]["status"]
            == "ready"
        )
        assert (
            client.post(base + "/apply", json={"content": content}).json()["cases"][0]["status"]
            == "applied"
        )
        assert (
            client.post(base + "/apply", json={"content": content}).json()["cases"][0]["status"]
            == "unchanged"
        )
        payload["items"][0]["bundle"]["steps"] = []
        assert (
            client.post(base + "/preview", json={"content": json.dumps(payload)}).status_code == 400
        )
    workbench.pool.shutdown()


def test_current_review_entry_rejects_legacy_content_edit_protocol(tmp_path):
    from fastapi.testclient import TestClient

    from scene_completion.api.application import create_app
    from scene_completion.application.project_service import Workbench
    from scene_completion.review.offline.ssd_review import export_html

    workbench = Workbench(tmp_path / "data")
    meta = workbench.create(
        {
            "name": "legacy",
            "sources": {r: [{"name": r + ".md", "content": "# RR"}] for r in ("RR", "SR")},
        }
    )
    root = workbench.run_dir(meta["id"])
    service.publish(root, coverage_bundle())
    legacy = export_html(root)
    with TestClient(create_app(workbench.root)) as client:
        base = "/api/projects/" + meta["id"] + "/ssd-review"
        assert client.post(base + "/preview", json={"content": legacy}).status_code == 400
        assert client.post(base + "/apply", json={"content": legacy}).status_code == 400
    workbench.pool.shutdown()


def test_unrun_gt_identification_is_never_exported_as_absence():
    b = coverage_bundle()
    b["channels"]["GT"]["pending"] = [{"id": "unrun", "needs_semantic": True}]
    assert not review_candidates(b, matching)[0]
    b["gt_identification_run_complete"] = True
    assert [r["id"] for r in review_candidates(b, matching)[0]] == ["G-third"]


def test_fixed_reference_scene_without_business_analysis_is_not_exported():
    b = coverage_bundle()
    row = b["channels"]["G"]["scenarios"][-1]
    row["generation_origin"] = "reference_template"
    assert not review_candidates(b, matching)[0]
    row["analysis"] = "当前用例调用接口时凭证格式不正确，返回认证失败。"
    assert [r["id"] for r in review_candidates(b, matching)[0]] == ["G-third"]
