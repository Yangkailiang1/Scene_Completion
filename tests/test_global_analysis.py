"""V5 global units have project identities, independent of SSD interactions."""
from scene_completion.global_analysis import (
    compare_concerns, compare_scenarios, evaluate, recommend, rate,
)


def binding(identity, concern="global.cascade"):
    return {"id": identity, "dependency_id": "dep-1", "object": "记忆库", "concern_key": concern}


def scenario(identity, cause, concern="global.cascade"):
    return {**binding(identity, concern), "cause": cause, "conditions": ["删除记忆实例后"]}


def test_one_global_concern_can_expand_to_two_independent_cascade_failures():
    g = {"matches": [binding("g-1"), binding("g-duplicate")], "pending": []}
    e = {"matches": [binding("e-1")], "pending": []}
    truth = {"matches": [binding("t-1")], "pending": []}
    concerns = compare_concerns(g, e, truth)
    assert (concerns["G_count"], concerns["E_count"], concerns["M_count"]) == (1, 1, 0)
    generated = {"scenarios": [scenario("g-repo", "记忆库未删除"),
                               scenario("g-policy", "记忆策略未删除")], "pending": []}
    existing = {"scenarios": [scenario("e-repo", "记忆库未删除")], "pending": []}
    gt = {"scenarios": [scenario("t-repo", "记忆库未删除"),
                        scenario("t-policy", "记忆策略未删除")], "pending": []}
    scenes = compare_scenarios(generated, existing, gt)
    assert scenes["G_count"] == 2 and len(scenes["M"]) == 1
    assert scenes["M"][0]["cause"] == "记忆策略未删除"
    chosen = recommend(scenes["M"], {"global_top_k": 10, "risk_weight": .7}, [], run_id="run-1")
    result = evaluate(concerns, scenes, chosen, gt)
    assert result["metrics"]["recommendation_adoption"] == rate(1, 1)
    assert result["metrics"]["recommendation_false_positive"] == rate(0, 2)


def test_global_scene_deduplicates_multiple_concern_labels_and_does_not_use_truth_to_rank():
    rows = [scenario("g-1", "上界越界", "global.dependency"),
            scenario("g-2", "上界越界", "global.sequence")]
    compared = compare_scenarios({"scenarios": rows}, {"scenarios": []})
    assert compared["G_count"] == 1 and len(compared["M"]) == 1
    chosen = recommend(compared["M"], {"global_top_k": 1, "risk_weight": .7}, [], run_id="r")
    assert len(chosen["Q"]) == 1
    assert "GT" not in chosen and chosen["ranked"][0]["history_score"] == .5


def test_global_report_is_exported_without_a_completed_use_case(tmp_path):
    from scene_completion.artifact_exports import export_missing_report
    from scene_completion.storage import read_json
    global_result = {
        "business-dependencies": {"dependencies": [{"id": "dep-1", "dependency_type": "cascade",
            "from_case_id": "UC-06", "to_case_id": "UC-11", "from_entity_id": "instance",
            "to_entity_id": "repository"}]},
        "global-concern-compare": {"rows": []},
        "global-scenario-compare": {"rows": []},
        "global-evaluation": {"metrics": {"generation_effectiveness": rate(1, 2)}},
    }
    export_missing_report(tmp_path, {"cases": {}, "global": global_result,
        "recommendation": {"enabled": True}, "evaluation_status": {}})
    report = (tmp_path / "missing_report.md").read_text()
    assert "全局业务依赖" in report and "UC-06" in report and "UC-11" in report
    assert "generation_effectiveness" in report
    assert read_json(tmp_path / "missing_report.json")["global"] == global_result
