"""Recompute the committed experiment metrics without network access or credentials."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".cac" / "tools"))

from scene_completion.comparison import compare_scenes
from scene_completion.matching_audit import validate_decisions
from scene_completion.role_reports import export_reports
from scene_completion.semantic_backend import read_json
from scene_completion.sources import fingerprint


def compact(value):
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if k not in {
            "missing_scenarios", "unmatched_generated_scenarios", "matches", "full_matches", "partial_matches"}}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", help="optionally regenerate JSON, Markdown and Excel reports")
    args = parser.parse_args()
    root = Path(__file__).parent / "three_agent_demo"
    generated = read_json(root / "common" / "generated_scenarios.json")
    checker = read_json(root / "common" / "existing_scenarios.json")
    source = read_json(root / "common" / "sources_index.json")
    assert checker["source_hash"] == fingerprint(source)
    summary = read_json(root / "summary.json")
    review_packet = read_json(root / "agent" / "native_review_packet.json")
    review = read_json(root / "agent" / "native_review_results.json")
    assert review == read_json(root / "agent" / "native_review.json")
    assert review["input_hash"] == review_packet["input_hash"] == summary["review"]["native_input_hash"]
    assert (review["model"], review["reasoning_effort"]) == ("gpt-6-luna", "max")
    indexed = {d["review_id"]: d for d in review["decisions"]}
    assert len(indexed) == len(review["decisions"]) == len(review_packet["pairs"]) == 60
    assert set(indexed) == {p["review_id"] for p in review_packet["pairs"]}
    expected_native_links = {}
    for batch_id in {p["batch_id"] for p in review_packet["pairs"]}:
        pairs = [p for p in review_packet["pairs"] if p["batch_id"] == batch_id]
        decisions = validate_decisions(pairs, [
            {**indexed[p["review_id"]], "pair_index": p["pair_index"]} for p in pairs])
        for pair, decision in zip(pairs, decisions):
            if decision["status"] != "unmatched":
                expected_native_links[(pair["checker"]["scenario_id"], pair["generated"]["scenario_id"])] = (
                    decision["status"], decision["missing_behavior"])
    for name in summary["experiments"]:
        directory = root / name
        matches = read_json(directory / "scenario_matches.json")
        if name == "agent":
            actual = {(m["checker_scenario_id"], m["generated_scenario_id"]): (
                m["status"], m["missing_behavior"]) for m in matches["matches"]}
            assert actual == expected_native_links, "native review was not applied completely"
        scores = read_json(directory / "recommendations.json")
        metrics = compare_scenes(generated, checker, matches)
        archived = read_json(directory / "metrics_summary.json")
        archived.pop("expanded_scenarios")
        assert compact(metrics) == archived, name + ": metric snapshot differs"
        expected = set(metrics["overall"]["recommendation_ids"])
        assert scores["complete"] and len(scores["items"]) == len(expected)
        assert {s["scenario_id"] for s in scores["items"]} == expected
        assert scores["items"] == sorted(scores["items"], key=lambda s: (-s["confidence"], s["scenario_id"]))
        for item in scores["items"]:
            assert math.isclose(item["confidence"], .7 * item["support_score"] + .3 * item["missing_score"])
        if args.output_dir:
            export_reports(Path(args.output_dir) / name, generated, checker, matches, metrics, scores)
        print(f"{name}: verified; G={len(generated['scenarios'])}, C={len(checker['scenarios'])}, "
              f"recommendations={len(expected)}")
    base = read_json(root / "embedding_sensitivity" / "scenario_matches.json")
    rerank = read_json(root / "embedding_sensitivity_rerank" / "scenario_matches.json")
    assert base == rerank, "rerank changed matching"
    print("Rerank matching and per-category metric invariants verified.")


if __name__ == "__main__":
    main()
