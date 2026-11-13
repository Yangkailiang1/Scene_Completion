from copy import deepcopy

import pytest

from scene_completion.analysis.ssd.pipeline import build_cases, generate_g
from scene_completion.application import ssd_revision_service as results
from scene_completion.domain.ssd import matching as ssd_matching
from scene_completion.domain.ssd import metrics as ssd_metrics
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.review.offline import ssd_review as ssd_review
from tests.support.paths import ROOT


@pytest.fixture(scope="module")
def mini_cases():
    return build_cases(ROOT / "datasets/mini-mall")


def save(project, current, bundle):
    return results.save_revision(
        project,
        bundle["case"]["id"],
        {
            "base_revision": current["revision"],
            "bundle": bundle,
            "reason": "test",
        },
    )


def get_record(bundle, channel, identity, kind="concerns"):
    return next(r for r in bundle["channels"][channel][kind] if r["id"] == identity)


def test_five_cases_publish_editor_and_aggregate_metrics(tmp_path, mini_cases):
    assert len(mini_cases) == 5
    for original in mini_cases:
        saved = results.publish(tmp_path, original)
        assert saved["revision"] == 1
        assert saved["bundle"] == ssd_validation.validate(original)
        assert saved == results.editor(tmp_path, original["case"]["id"])
        assert saved["metrics"] == saved["original_metrics"]
        assert results.publish(tmp_path, original)["revision"] == 1
    aggregate = results.index(tmp_path)
    assert len(aggregate["cases"]) == 5
    for metric in ("missing_exception_miss_rate", "generation_validity"):
        for key in ("numerator", "denominator"):
            assert aggregate["metrics"][metric][key] == sum(
                c["metrics"][metric][key] for c in aggregate["cases"]
            )


def test_incomplete_scope_counts_semantics_and_revision_gaps(tmp_path, mini_cases):
    bundle = deepcopy(mini_cases[0])
    bundle["pending"] = [{"id": "order-gap", "reason": "待补充执行顺序"}]
    bundle["revision_issues"] = [{"id": "lost-edit", "reason": "人工修订待重新定位"}]
    saved = results.publish(tmp_path, bundle)
    progress = saved["completeness"]
    assert progress["pending_case_items"] == 1
    assert progress["revision_issues"] == 1
    assert progress["semantic_pairs"] == len(ssd_matching.semantic_candidates(bundle)) > 0
    assert not progress["complete"]
    assert results.index(tmp_path)["cases"][0]["pending_count"] == (
        progress["pending_records"] + progress["semantic_pairs"] + 2
    )


def test_semantic_pending_clears_on_decision_and_returns_after_edit(tmp_path, mini_cases):
    first = results.publish(tmp_path, mini_cases[0])
    edited = deepcopy(first["bundle"])
    candidate = edited["semantic_pending"][0]
    edited["decisions"].append(
        {
            **candidate,
            "id": "human-scene",
            "level": "scenario",
            "status": "none",
            "origin": "manual",
        }
    )
    second = save(tmp_path, first, edited)
    assert candidate not in second["bundle"]["semantic_pending"]
    edited = deepcopy(second["bundle"])
    channel = ssd_matching.PAIRS[candidate["pair"]][0]
    get_record(edited, channel, candidate["left_id"], "scenarios")["condition"] += "人工变更"
    third = save(tmp_path, second, edited)
    assert candidate in third["bundle"]["semantic_pending"]


def test_manual_edit_preserves_original_and_has_immutable_revision(tmp_path, mini_cases):
    first = results.publish(tmp_path, mini_cases[0])
    edited = deepcopy(first["bundle"])
    edited["channels"]["E"]["concerns"][0]["condition"] = "人工修正的触发条件"
    second = save(tmp_path, first, edited)
    assert second["revision"] == 2
    assert len(second["history"]) == 2
    assert second["original_metrics"] == first["metrics"]
    assert results.editor(tmp_path, edited["case"]["id"], 1) == first
    assert results.editor(tmp_path, edited["case"]["id"], "original")["bundle"] == first["bundle"]
    with pytest.raises(results.RevisionConflict) as error:
        save(tmp_path, first, edited)
    assert error.value.current_revision == 2
    assert results.editor(tmp_path, edited["case"]["id"])["revision"] == 2


def test_step_edit_regenerates_rules_and_preserves_manual_g_edit(tmp_path, mini_cases):
    first = results.publish(tmp_path, mini_cases[0])
    bundle = deepcopy(first["bundle"])
    manual = bundle["channels"]["G"]["concerns"][-1]
    identity = manual["id"]
    manual["label"] = "人工保留的关注点名称"
    second = save(tmp_path, first, bundle)
    changed = deepcopy(second["bundle"])
    step = next(
        s
        for s in changed["steps"]
        if s["kind"] == "interaction"
        and s["direction"] == "request"
        and s["receiver"]["type"] == "service"
        and s["id"] != manual["step_id"]
    )
    step["receiver"]["type"] = "human"
    expected = generate_g(changed)
    third = save(tmp_path, second, changed)
    actual = third["bundle"]["channels"]["G"]
    assert {r["id"] for r in actual["concerns"]} == {r["id"] for r in expected["concerns"]}
    assert get_record(third["bundle"], "G", identity)["label"] == "人工保留的关注点名称"
    assert third["original_metrics"] == first["metrics"]


def test_publish_new_baseline_keeps_human_changes_and_deletions(tmp_path, mini_cases):
    machine = deepcopy(mini_cases[0])
    first = results.publish(tmp_path, machine)
    edited = deepcopy(first["bundle"])
    items = edited["channels"]["E"]["concerns"]
    altered, deleted = items[0]["id"], items[1]["id"]
    items[0]["label"] = "手工名称"
    items[:] = [r for r in items if r["id"] != deleted]
    save(tmp_path, first, edited)
    get_record(machine, "E", altered)["condition"] = "新一轮机器抽取"
    added = deepcopy(machine["channels"]["E"]["concerns"][0])
    added["id"] += "-added"
    machine["channels"]["E"]["concerns"].append(added)
    rerun = results.publish(tmp_path, machine)
    rows = rerun["bundle"]["channels"]["E"]["concerns"]
    assert deleted not in {r["id"] for r in rows}
    assert added["id"] in {r["id"] for r in rows}
    merged = get_record(rerun["bundle"], "E", altered)
    assert merged["label"] == "手工名称"
    assert merged["condition"] == "新一轮机器抽取"


def test_changed_records_invalidate_old_manual_decisions(tmp_path, mini_cases):
    first = results.publish(tmp_path, mini_cases[0])
    bundle = deepcopy(first["bundle"])
    left, right = bundle["channels"]["G"]["concerns"][0], bundle["channels"]["E"]["concerns"][0]
    bundle["decisions"].append(
        {
            "id": "human-match",
            "level": "concern",
            "pair": "G_E",
            "left_id": left["id"],
            "right_id": right["id"],
            "status": "full",
            "reason": "人工确认",
            "origin": "manual",
        }
    )
    second = save(tmp_path, first, bundle)
    modified = deepcopy(second["bundle"])
    get_record(modified, "E", right["id"])["condition"] = "含义已改变"
    third = save(tmp_path, second, modified)
    assert not any(d["id"] == "human-match" for d in third["bundle"]["decisions"])


def test_remove_action_keeps_orphaned_source_records_visible(tmp_path, mini_cases):
    first = results.publish(tmp_path, mini_cases[0])
    bundle = deepcopy(first["bundle"])
    action = next(s for s in bundle["steps"] if s["kind"] == "action")
    concern = deepcopy(bundle["channels"]["E"]["concerns"][0])
    concern.update(id="human-local-concern", step_id=action["id"], field_id=None)
    bundle["channels"]["E"]["concerns"].append(concern)
    second = save(tmp_path, first, bundle)
    removed = deepcopy(second["bundle"])
    removed["steps"] = [s for s in removed["steps"] if s["id"] != action["id"]]
    third = save(tmp_path, second, removed)
    orphan = get_record(third["bundle"], "E", "human-local-concern")
    assert orphan["status"] == "unbound"
    assert orphan["binding_issue"]
    assert any(
        row["status"] == "pending"
        for row in third["comparison"]["concerns"]
        if any(r["id"] == concern["id"] for r in row["cells"]["E"])
    )


def metric_fixture():
    actor = {"id": "service", "name": "service", "type": "service"}
    bundle = {
        "version": "ssd-case-v1",
        "case": {"id": "metric", "name": "metric"},
        "steps": [
            {
                "id": "s",
                "kind": "action",
                "direction": "request",
                "order": 1,
                "sender": actor,
                "receiver": actor,
                "data": [],
            }
        ],
        "channels": {},
        "documents": [],
        "decisions": [],
    }
    for channel, keys in {"G": "abc", "E": "a", "GT": "abd"}.items():
        bundle["channels"][channel] = {
            "concerns": [
                {
                    "id": channel + k,
                    "step_id": "s",
                    "target": "receiver",
                    "key": k,
                    "condition": k,
                    "status": "active",
                    "source_refs": [],
                }
                for k in keys
            ],
            "scenarios": [],
            "pending": [],
        }
    return bundle


def test_metrics_deduplicate_and_exclude_pending_and_zero_denominator():
    bundle = metric_fixture()
    duplicate = {**bundle["channels"]["G"]["concerns"][1], "id": "duplicate"}
    bundle["channels"]["G"]["concerns"].extend(
        [duplicate, {**duplicate, "id": "pending", "key": "pending", "status": "pending"}]
    )
    report = ssd_metrics.analyze(ssd_validation.validate(bundle))
    miss, valid = (
        report["metrics"]["missing_exception_miss_rate"],
        report["metrics"]["generation_validity"],
    )
    assert (miss["numerator"], miss["denominator"], miss["value"]) == (1, 2, 50)
    assert (valid["numerator"], valid["denominator"]) == (2, 3)
    for channel in bundle["channels"].values():
        channel["concerns"] = []
    empty = ssd_metrics.analyze(bundle)["metrics"]
    assert all(m["value"] is None and m["denominator"] == 0 for m in empty.values())


def test_real_offline_export_preview_apply_and_receipt_persist(tmp_path, mini_cases):
    first = results.publish(tmp_path, mini_cases[0])
    html = ssd_review.export_html(tmp_path, {"case_ids": [first["bundle"]["case"]["id"]]})
    feedback = ssd_review._parse(html)
    assert feedback["cases"][0]["rows"]
    entry = feedback["cases"][0]
    record = entry["bundle"]["channels"]["E"]["concerns"][0]
    record["condition"] = "离线人工确认的异常"
    assert ssd_review.preview_feedback(tmp_path, feedback)["cases"][0]["status"] == "ready"
    assert ssd_review.apply_feedback(tmp_path, feedback)["cases"][0]["status"] == "applied"
    current = results.editor(tmp_path, entry["case_id"])
    assert current["bundle"]["review_feedback"]
    assert get_record(current["bundle"], "E", record["id"])["condition"] == "离线人工确认的异常"
    assert ssd_review.apply_feedback(tmp_path, feedback)["cases"][0]["status"] == "unchanged"
    assert results.editor(tmp_path, entry["case_id"])["revision"] == current["revision"]


def test_publish_removes_decisions_whose_machine_records_disappear(tmp_path):
    machine = metric_fixture()
    first = results.publish(tmp_path, machine)
    modified = deepcopy(first["bundle"])
    modified["decisions"] = [
        {
            "id": "reviewed",
            "level": "concern",
            "pair": "G_E",
            "left_id": "Ga",
            "right_id": "Ea",
            "status": "full",
            "reason": "已确认",
            "origin": "manual",
        }
    ]
    save(tmp_path, first, modified)
    machine["channels"]["E"]["concerns"] = []
    updated = results.publish(tmp_path, machine)
    assert not updated["bundle"]["decisions"]


def test_removing_step_invalidates_source_test_manual_match(tmp_path, mini_cases):
    original = deepcopy(mini_cases[0])
    action = next(s for s in original["steps"] if s["kind"] == "action")
    for channel in ("E", "GT"):
        original["channels"][channel]["concerns"].append(
            {
                "id": channel + "-action",
                "step_id": action["id"],
                "target": "receiver",
                "key": "service.access",
                "condition": "本地校验",
                "status": "active",
                "field_id": None,
                "source_refs": [],
            }
        )
    original["decisions"] = [
        {
            "id": "action-match",
            "level": "concern",
            "pair": "GT_E",
            "left_id": "GT-action",
            "right_id": "E-action",
            "status": "full",
            "reason": "已确认",
            "origin": "manual",
        }
    ]
    first = results.publish(tmp_path, original)
    edited = deepcopy(first["bundle"])
    edited["steps"] = [s for s in edited["steps"] if s["id"] != action["id"]]
    current = save(tmp_path, first, edited)
    assert not any(d["id"] == "action-match" for d in current["bundle"]["decisions"])
