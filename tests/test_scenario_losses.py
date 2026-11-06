from scene_completion.analysis.scenario_losses import summarize


def test_conflicting_three_way_decisions_are_reported_not_silently_closed():
    report = {
        "G": [{"id": "g"}],
        "E": [{"id": "e"}],
        "GT": [{"id": "t", "cause": "唯一性冲突", "interaction_id": "s4"}],
        "M": [],
        "full_matches": {
            "G_E": [{"checker_scenario_id": "g", "generated_scenario_id": "e"}],
            "GT_G": [{"checker_scenario_id": "t", "generated_scenario_id": "g"}],
            "GT_E": [],
        },
    }
    result = summarize(report)
    assert (result["numerator"], result["denominator"]) == (1, 1)
    assert result["conflicts"][0]["GT"] == "t"
    assert report["full_matches"]["GT_E"] == []


def test_reassign_saved_candidate_edges_within_missing_sets_not_selected_overall_pairs():
    report = {
        "G": [{"id": "g"}, {"id": "covered"}],
        "E": [{"id": "e"}],
        "GT": [{"id": "t1"}, {"id": "t2"}],
        "M": [{"id": "g"}],
        "full_matches": {"G_E": [], "GT_E": [], "GT_G": []},
        "full_candidate_pairs_GT_G": [
            {"left_id": "t1", "right_id": "covered", "status": "full"},
            {"left_id": "t1", "right_id": "g", "status": "full"},
            {"left_id": "t2", "right_id": "g", "status": "full"},
        ],
    }
    result = summarize(report)
    assert (result["numerator"], result["denominator"]) == (1, 2)
    assert result["value"] == 50


def test_empty_denominator_is_not_applicable_and_absent_evaluation_is_unassessed():
    assert summarize({})["status"] == "未评测"
    result = summarize({k: [] for k in ("G", "E", "GT", "M")})
    assert result["status"] == "不适用" and result["value"] is None
