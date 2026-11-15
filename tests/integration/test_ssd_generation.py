from copy import deepcopy

import pytest

from scene_completion.analysis.ssd.generation import (
    apply_result,
    batches,
    capture_machine,
    context_identity,
    validate_result,
)
from scene_completion.analysis.ssd.pipeline import build_cases
from scene_completion.application import ssd_revision_service as service
from scene_completion.domain.contracts import schema
from tests.support.paths import ROOT


@pytest.fixture
def case():
    return build_cases(ROOT / "datasets/mini-mall", ["UC-001"])[0]


def describe(case):
    for inputs in batches(case):
        apply_result(
            case,
            inputs,
            {
                "analyses": [
                    {
                        "scenario_id": row["id"],
                        "analysis": f"{inputs['case']['name']}：{row['condition']}",
                    }
                    for row in inputs["templates"]
                ],
                "supplements": [],
            },
        )
    return capture_machine(case)


def test_generation_projection_keeps_all_fixed_variants_and_no_inverse_material(case):
    original = list(batches(case))
    assert original
    assert schema("ssd-generate")["required"] == ["analyses", "supplements"]
    case["channels"]["E"] = {"private": "ONLY_IN_E"}
    case["channels"]["GT"] = {"private": "ONLY_IN_GT"}
    case["documents"] = [{"content": "PRIVATE_TEST_DOCUMENT"}]
    case["decisions"] = [{"answer": "PRIVATE_MATCH"}]
    for step in case["steps"]:
        step["source_refs"] = [{"quote": "PRIVATE_QUOTATION"}]
    assert list(batches(case)) == original
    ids = {t["id"] for p in original for t in p["templates"]}
    fixed = [s for s in case["channels"]["G"]["scenarios"] if s["key"] == "human.authentication"]
    assert len(fixed) == 5
    assert all(s["id"] in ids for s in fixed)
    before = deepcopy(case["channels"]["G"]["scenarios"])
    describe(case)
    assert case["scenario_generation"]["complete"]
    assert not list(batches(case))
    for old, updated in zip(before, case["channels"]["G"]["scenarios"]):
        assert all(
            old[k] == updated[k] for k in ("id", "condition", "expected", "concern_ids", "step_id")
        )


def test_missing_duplicate_or_foreign_template_and_supplement_rejected(case):
    inputs = next(batches(case))
    valid = {
        "analyses": [{"scenario_id": r["id"], "analysis": "业务分析"} for r in inputs["templates"]],
        "supplements": [],
    }
    validate_result(valid, inputs)
    for change in ("missing", "duplicate", "foreign", "empty", "wrong_concern"):
        output = deepcopy(valid)
        if change == "missing":
            output["analyses"].pop()
        elif change == "duplicate":
            output["analyses"].append(output["analyses"][0])
        elif change == "foreign":
            output["analyses"][0]["scenario_id"] = "other-case"
        elif change == "empty":
            output["analyses"][0]["analysis"] = " "
        else:
            output["supplements"] = [
                {"concern_id": "other-step", "condition": "c", "expected": "e", "analysis": "a"}
            ]
        with pytest.raises(ValueError):
            validate_result(output, inputs)


def test_step_revision_invalidates_only_changed_context_keeps_human_edits(tmp_path, case):
    machine = describe(case)
    first = service.publish(tmp_path, machine)
    edited = deepcopy(first["bundle"])
    scenarios = edited["channels"]["G"]["scenarios"]
    selected = next(s for s in scenarios if s.get("analysis"))
    selected["analysis"] = "人工补充的认证描述"
    removed = next(s for s in scenarios if s.get("analysis") and s["id"] != selected["id"])
    scenarios.remove(removed)
    step = next(s for s in edited["steps"] if s["id"] == selected["step_id"])
    old_context = context_identity(edited, step)
    step["operation"]["name"] += "调整"
    assert context_identity(edited, step) != old_context
    second = service.save_revision(
        tmp_path,
        case["case"]["id"],
        {
            "base_revision": first["revision"],
            "bundle": edited,
        },
    )
    rows = {s["id"]: s for s in second["bundle"]["channels"]["G"]["scenarios"]}
    assert rows[selected["id"]]["analysis"] == "人工补充的认证描述"
    assert rows[selected["id"]]["analysis_origin"] == "manual"
    assert removed["id"] not in rows
    assert second["bundle"]["scenario_generation"]["pending_ids"]
    for row in rows.values():
        if row["step_id"] != selected["step_id"] and row.get("analysis"):
            assert (
                row["generation_context"]
                == next(s for s in machine["channels"]["G"]["scenarios"] if s["id"] == row["id"])[
                    "generation_context"
                ]
            )
    # Re-running changes machine analyses; deletes and human edits survive.
    rerun = deepcopy(machine)
    rerun["channels"]["G"]["scenarios"][0]["analysis"] = "新的机器描述"
    capture_machine(rerun)
    published = service.publish(tmp_path, rerun)
    current = {s["id"]: s for s in published["bundle"]["channels"]["G"]["scenarios"]}
    assert removed["id"] not in current
    assert current[selected["id"]]["analysis"] == "人工补充的认证描述"
    assert published["bundle"]["steps"] == second["bundle"]["steps"]
    assert published["original_metrics_by_level"] == first["metrics_by_level"]


def test_scenario_rates_aggregate_counts_not_percentages(tmp_path, case):
    first = service.publish(tmp_path, case)
    second = deepcopy(case)
    second["case"]["id"] = "another-case"
    second["channels"]["GT"]["scenarios"] = []
    second["channels"]["GT"]["concerns"] = []
    service.publish(tmp_path, second)
    result = service.index(tmp_path)
    for level in ("concern", "scenario"):
        for metric in first["metrics"]:
            for count in ("numerator", "denominator"):
                assert result["metrics_by_level"][level][metric][count] == sum(
                    c["metrics_by_level"][level][metric][count] for c in result["cases"]
                )


def test_model_short_handles_restore_exact_stable_template_ids(case):
    from scene_completion.analysis.ssd.generation import model_packet, restore_handles

    inputs = next(batches(case))
    projected, mapping = model_packet(inputs)
    assert projected["templates"][0]["id"] == "T01"
    output = {
        "analyses": [
            {"scenario_id": row["id"], "analysis": "业务失败说明"} for row in projected["templates"]
        ],
        "supplements": [],
    }
    validate_result(output, projected)
    restored = restore_handles(output, mapping)
    apply_result(case, inputs, restored)
    assert {r["scenario_id"] for r in restored["analyses"]} == {
        r["id"] for r in inputs["templates"]
    }
    output["analyses"][0]["scenario_id"] = "T999"
    with pytest.raises(ValueError, match="未知模板"):
        restore_handles(output, mapping)
