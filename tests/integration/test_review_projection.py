"""Current read models share export eligibility without rewriting saved model results."""

from copy import deepcopy

import pytest

from scene_completion.application import project_scope_service, ssd_revision_service
from scene_completion.application.result_projection import current_view
from scene_completion.domain.project_scopes import matching
from scene_completion.domain.project_scopes.metrics import analyze
from scene_completion.infrastructure.storage import write_json
from scene_completion.review.offline import adoption
from tests.support.ssd_results import coverage_bundle


def project_bundle(scope="business_chain"):
    b = coverage_bundle()
    b["version"] = "project-scope-v1"
    b["scope"] = {"id": scope, "name": scope}
    b.pop("case")
    b.pop("steps")
    b["anchors"] = (
        [
            {
                "id": "step",
                "kind": "dependency",
                "relation_type": "direct",
                "from_case_id": "A",
                "to_case_id": "B",
            }
        ]
        if scope == "business_chain"
        else [{"id": "step", "kind": "external_service", "name": "数据库", "external": True}]
    )
    b["source_records"] = {"E": [], "GT": [{"id": "timeout", "condition": "超时阈值待确认"}]}
    for channel in b["channels"].values():
        for kind in ("concerns", "scenarios"):
            for row in channel[kind]:
                row["anchor_id"] = row.pop("step_id")
                row["target"] = "dependency" if scope == "business_chain" else "service"
                row["key"] = (
                    "global.call_order"
                    if scope == "business_chain"
                    else "service.base.availability"
                )
    b["channels"]["GT"]["pending"] = [
        {"id": "timeout", "status": "pending", "needs_semantic": True}
    ]
    return b


def proof(root, bundle):
    path = (
        root / "run/artifacts/shared" / f"project--{bundle['scope']['id']}--project-identify.json"
    )
    write_json(
        path,
        {
            "protocol": "scene-workflow-v5",
            "task": "project-identify",
            "payload": {**deepcopy(bundle), "gt_identification_run_complete": True},
        },
    )
    return path


def test_completion_proof_restores_only_matching_current_packet_and_preserves_freeze(tmp_path):
    b = project_bundle()
    project_scope_service.publish(tmp_path, b)
    before = project_scope_service.editor(tmp_path, "business_chain")
    original = deepcopy(before["bundle"])
    assert before["review_statuses"]["G-third"]["reason"] == "identification_pending"
    path = proof(tmp_path, b)
    after = project_scope_service.editor(tmp_path, "business_chain")
    assert after["bundle"] == original
    assert after["review_statuses"]["G-third"]["eligible"]
    assert after["identification_proof"]["source"] == str(path.relative_to(tmp_path))
    # Historical snapshots remain exactly frozen; a mismatched input cannot unlock review.
    assert "review_statuses" not in project_scope_service.editor(tmp_path, "business_chain", 1)
    tampered = deepcopy(b)
    tampered["anchors"][0]["to_case_id"] = "C"
    proof(tmp_path, tampered)
    assert not project_scope_service.editor(tmp_path, "business_chain")["review_statuses"][
        "G-third"
    ]["eligible"]


def test_explicit_unfinished_identification_and_relevant_pending_are_not_unlocked(tmp_path):
    b = project_bundle()
    proof(tmp_path, b)
    b["gt_identification_run_complete"] = False
    view = current_view(tmp_path, {"bundle": b, **analyze(b)}, matching)
    assert view["review_statuses"]["G-third"]["reason"] == "identification_pending"
    b["gt_identification_run_complete"] = True
    b["channels"]["GT"]["pending"][0]["anchor_id"] = "step"
    view = current_view(tmp_path, {"bundle": b, **analyze(b)}, matching)
    assert view["review_statuses"]["G-third"]["reason"] == "source_pending"


def test_partial_links_explain_other_rows_instead_of_claiming_gt_missing(tmp_path):
    b = project_bundle()
    b["gt_identification_run_complete"] = True
    view = current_view(tmp_path, {"bundle": b, **analyze(b)}, matching)
    row = next(
        r
        for r in view["comparison"]["scenarios"]
        if any(x["id"] == "G-second" for x in r["cells"]["G"])
    )
    assert row["cells"]["GT"] == []
    assert row["status"] == "partial"
    assert "已确认GT覆盖" in row["reason"]
    assert row["coverage_by_record"]["G-second"]["links"][0]["status"] == "partial"


def test_combined_reference_contains_zero_review_scope_and_precise_apply_is_idempotent(tmp_path):
    ssd_revision_service.publish(tmp_path, coverage_bundle())
    for scope in ("business_chain", "architecture"):
        b = project_bundle(scope)
        b["gt_identification_run_complete"] = True
        project_scope_service.publish(tmp_path, b)
    summary = adoption.summary(tmp_path)
    assert not (tmp_path / "review_exports").exists()
    payload = adoption.export_payload(tmp_path)
    assert {i["scope"] for i in payload["items"]} == {
        "interaction",
        "shared_services",
    }
    assert summary["excluded"] == payload["excluded"]
    for item in payload["items"]:
        assert len(item["rows"]) == 1
        g = item["rows"][0]["cells"]["G"][0]
        payload["decisions"].append(
            {"item_id": item["id"], "g_id": g["id"], "adopted": True, "comment": "确认补充"}
        )
    ids = [i["id"] for i in payload["items"]]
    result = adoption.feedback(tmp_path, payload, apply=True, item_ids=ids)
    assert result["summary"]["applied"] == 2
    assert (
        adoption.feedback(tmp_path, payload, apply=True, item_ids=ids)["summary"]["unchanged"] == 2
    )
    second = adoption.export_payload(tmp_path)
    assert len(second["items"]) == 2 and all(not i["rows"] for i in second["items"])
    assert all(i["bundle"]["channels"]["G"]["scenarios"] for i in second["items"])
    forged = deepcopy(second)
    forged["items"][0]["review_statuses"]["G-third"]["covered"] = False
    with pytest.raises(ValueError, match="只读上下文"):
        adoption.feedback(tmp_path, forged)
    with pytest.raises(ValueError, match="条目身份"):
        adoption.feedback(tmp_path, second, apply=True, item_ids=["wrong:item"])


def test_index_cache_invalidates_after_a_new_revision_without_running_analyze(
    tmp_path, monkeypatch
):
    view = ssd_revision_service.publish(tmp_path, coverage_bundle())

    def forbidden(*args):
        raise AssertionError("cached metrics must not trigger full analysis")

    with monkeypatch.context() as patch:
        patch.setattr(ssd_revision_service, "analyze", forbidden)
        assert ssd_revision_service.index(tmp_path)["cases"][0]["revision"] == 1
        assert ssd_revision_service.index(tmp_path)["cases"][0]["revision"] == 1
    changed = deepcopy(view["bundle"])
    changed["steps"][0]["operation"]["name"] = "人工改名"
    ssd_revision_service.save_revision(tmp_path, "case", {"base_revision": 1, "bundle": changed})
    assert ssd_revision_service.index(tmp_path)["cases"][0]["revision"] == 2


def test_prior_v2_files_without_reference_metadata_still_preview_and_apply(tmp_path):
    from scene_completion.infrastructure.identity import fingerprint

    ssd_revision_service.publish(tmp_path, coverage_bundle())
    from scene_completion.review.offline import _adoption_v2 as old

    payload = old.export_payload(tmp_path, {"scopes": ["interaction"]})
    for item in payload["items"]:
        item.pop("review_statuses")
        item.pop("identification_proof")
    payload["excluded"].pop("by_scope")
    payload["export_id"] = fingerprint([old.FORMAT, payload["items"], payload["excluded"]])
    write_json(
        tmp_path / "review_exports" / (payload["export_id"] + ".json"),
        {"context_hash": fingerprint([payload["items"], payload["excluded"]])},
    )
    item = payload["items"][0]
    payload["decisions"] = [
        {"item_id": item["id"], "g_id": "G-third", "adopted": True, "comment": "旧文件兼容"}
    ]
    assert adoption.feedback(tmp_path, payload)["summary"]["ready"] == 1
    assert (
        adoption.feedback(tmp_path, payload, apply=True, selected=["case"])["summary"]["applied"]
        == 1
    )
