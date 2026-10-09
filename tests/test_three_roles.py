"""Behavioral tests for independent extraction, complete batches, and set metrics."""
import copy
import json
import math
from pathlib import Path

import pytest

from tests.test_scene_completion import sample_model
from scene_completion.comparison import compare_scenes
from scene_completion.generator import generate_scenes
from scene_completion.semantic_backend import SemanticClient, collect_packets, prepare_packets, read_json, write_json
from scene_completion.sources import fingerprint, index_sources, validate_refs
from scene_completion.three_roles import (
    checker_packets, checker_validator, embedding_matches, embedding_recommendations,
    finish_recommendations, match_packets, matching_validator, merge_matches,
    recommendation_packets, recommendation_validator,
)


def sources(tmp_path):
    doc = tmp_path / "requirements.md"
    doc.write_text("# Requirements\n\n\n## UC-001: Browse\nLogin required.\nQuery times out.\nReturn error.\n", encoding="utf-8")
    return index_sources([str(doc)])


def scene(sid, keys=None, kind="requirement_exception", uc="UC-001"):
    return {"scenario_id": sid, "use_case_id": uc, "use_case_name": "Browse",
            "scenario_type": kind, "name": sid, "trigger": "query timeout",
            "preconditions": "logged in", "scenario_steps": ["query", "error"],
            "expected_result": "error", "recovery": "retry", "concern_keys": keys or []}


def dataset(scenes):
    return {"complete": True, "scenarios": scenes}


def matched(gen, ref, links):
    return {"complete": True, "backend": "agent", "input_hash": fingerprint([gen, ref]), "matches": links}


def link(c, g, status="partial"):
    return {"checker_scenario_id": c, "generated_scenario_id": g, "status": status,
            "evidence": "same timeout condition", "missing_behavior": ["recovery"] if status == "partial" else []}


def test_original_lines_chapters_fences_and_citations(tmp_path):
    index = sources(tmp_path)
    chapter = index["documents"][0]["chapters"][1]
    assert chapter["line_start"] == 4
    assert chapter["heading_path"] == ["Requirements", "UC-001: Browse"]
    refs = validate_refs([{"document": "requirements.md", "line_start": 6, "line_end": 7}], index)
    assert refs[0]["chapter_id"] == chapter["chapter_id"]
    with pytest.raises(ValueError):
        validate_refs([{"document": "requirements.md", "line_start": 6, "line_end": 99}], index)
    doc = tmp_path / "fenced.md"
    doc.write_text("# A\n" + chr(96)*3 + "\n## fake\n" + chr(96)*3 + "\n## Real\n", encoding="utf-8")
    assert [c["title"] for c in index_sources([str(doc)])["documents"][0]["chapters"]] == ["A", "Real"]


def test_short_or_nonempty_fence_cannot_close_long_fence(tmp_path):
    doc = tmp_path / "fenced.md"
    tick = chr(96)
    doc.write_text("# A\n" + tick*4 + "md\n## Fake\n" + tick*3 +
                   "\n## Still fake\n" + tick*4 + "code\n## Also fake\n" +
                   tick*4 + "\n## Real\n", encoding="utf-8")
    assert [c["title"] for c in index_sources([str(doc)])["documents"][0]["chapters"]] == ["A", "Real"]


def test_checker_ids_distinguish_preconditions_and_steps(tmp_path):
    index = sources(tmp_path)
    manifest = checker_packets(index, sample_model()["use_cases"], tmp_path / "checker")
    packet = read_json(tmp_path / "checker" / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    main = scene("ignore", kind="main_success")
    guest = scene("ignore")
    admin = {**guest, "preconditions": "administrator", "scenario_steps": ["admin query", "error"]}
    for s in (main, guest, admin):
        s["source_refs"] = [{"document": "requirements.md", "line_start": 5, "line_end": 7}]
    output = checker_validator(index)(packet, {"covered_section_ids": [s["chapter_id"] for s in packet["input"]["sections"]],
                                              "scenarios": [main, guest, admin]})
    assert len({s["scenario_id"] for s in output}) == 3


def test_generator_preserves_supplied_explicit_concern_labels(tmp_path):
    model = sample_model()
    uc = model["use_cases"][0]
    uc["scenarios"] = [{"scenario_id": "main", "scenario_type": "main", "steps": uc["main_flow"]},
        {"scenario_id": "explicit", "scenario_type": "requirement_exception", "anchor_step_index": 1,
         "steps": ["reject operation"], "trigger": "access denied", "expected_result": "reject",
         "concern_keys": ["human.authorization"]}]
    output = generate_scenes(model, sources(tmp_path))
    explicit = next(s for s in output["scenarios"] if s["scenario_type"] == "requirement_exception")
    assert "human.authorization" in explicit["concern_keys"]
    assert explicit["preconditions"].startswith("待需求确认")
    assert explicit["postconditions"].startswith("待需求确认")
    assert explicit["use_case_preconditions"] == uc["preconditions"]


def test_support_scale_review_downgrades_context_and_binds_direct_quotes():
    from scene_completion.support_audit import verify_support, check_support
    candidate = scene("G")
    candidate["trigger"] = "string exceeds maximum length"
    evidence = {"text": "SKU name is required; SKU format is validated.",
                "source_ref": {"document": "requirements.md", "line_start": 5, "line_end": 6}}
    packet = {"input": {"candidates": [candidate], "evidence": {"G": [evidence]}}}
    initial = {"items": [{"scenario_id": "G", "support_score": .75, "missing_score": .85,
                         "basis": "fields are documented but no length limits are provided",
                         "evidence_refs": [evidence["source_ref"]]}]}
    with pytest.raises(ValueError): check_support(packet, initial["items"][0])
    class Client:
        def model(self, kind): return "fixture"
        def agent(self, request):
            return {"verdicts": [{"scenario_id": "G", "evidence_level": "context",
                                  "reason": "required/format validation does not define a length limit",
                                  "support_quote": "", "evidence_index": 0}]}
    verified = verify_support(packet, initial, Client())
    assert verified["items"][0]["support_score"] == .5
    assert verified["items"][0]["initial_support_score"] == .75
    check_support(packet, verified["items"][0])
    assert verify_support(packet, verified, Client()) == verified
    # A fabricated high-support quotation cannot be accepted.
    review = verified["items"][0]["support_verification"]
    review.update(evidence_level="explicit_constraint", support_quote="maximum length is 100")
    with pytest.raises(ValueError): check_support(packet, verified["items"][0])


def test_semantic_assessments_cannot_accept_different_failure_conditions():
    from scene_completion.matching_audit import validate_decisions
    pair = {"pair_index": 0, "generated": {"trigger": "signature invalid"},
            "checker": {"trigger": "duplicate eventId"}}
    decision = {"pair_index": 0, "generated_trigger_quote": "signature invalid",
                "checker_trigger_quote": "duplicate eventId", "status": "partial",
                "same_specific_trigger": False, "shared_core_behavior": True,
                "same_expected_outcome": False, "compatible_constraints": True,
                "evidence": "different failures on the same endpoint", "missing_behavior": ["response"]}
    result = validate_decisions([pair], [decision])
    assert result[0]["status"] == "unmatched" and result[0]["llm_status"] == "partial"


def test_semantic_pair_audit_rejects_invented_trigger_and_removes_false_link(tmp_path):
    from scene_completion.matching_audit import verify_matching, audited_matching_validator
    gen, ref = scene("G"), scene("C")
    ref["trigger"] = "category invalid"
    gen["trigger"] = "service unavailable"
    packet = {"input": {"generated": [gen], "checker": [ref]}}
    raw = {"checked_generated_ids": ["G"], "checked_checker_ids": ["C"], "matches": [link("C", "G", "full")]}
    with pytest.raises(ValueError):
        audited_matching_validator(packet, raw)
    class Client:
        def model(self, kind): return "fixture"
        def agent(self, request):
            return {"decisions": [{"pair_index": 0, "checker_trigger_quote": ref["trigger"],
                                  "generated_trigger_quote": gen["trigger"], "status": "unmatched",
                                  "same_specific_trigger": False, "shared_core_behavior": False,
                                  "same_expected_outcome": False, "compatible_constraints": True,
                                  "evidence": "invalid category and unavailable service are distinct conditions",
                                  "missing_behavior": []}]}
    result = verify_matching(packet, raw, Client())
    assert not result["matches"] and result["semantic_verification"]["decisions"][0]["status"] == "unmatched"
    assert audited_matching_validator(packet, result) == []
    result["semantic_verification"]["decisions"][0]["checker_trigger_quote"] = "invented timeout"
    with pytest.raises(ValueError): audited_matching_validator(packet, result)


def test_full_link_cannot_contain_behavior_gaps():
    packet = {"input": {"generated": [scene("G")], "checker": [scene("C")]}}
    raw = {"checked_generated_ids": ["G"], "checked_checker_ids": ["C"], "matches": [link("C", "G", "full")]}
    raw["matches"][0]["missing_behavior"] = ["recovery unknown"]
    with pytest.raises(ValueError): matching_validator(packet, raw)


def test_failed_semantic_verification_preserves_retry_and_blocks_metrics(tmp_path):
    from scene_completion.semantic_backend import run_agent_packets
    from scene_completion.matching_audit import audited_matching_validator
    gen, ref = dataset([scene("G")]), dataset([scene("C")])
    manifest = match_packets(gen, ref, tmp_path)
    batch = manifest["batches"][0]
    proposal = {**batch, "checked_generated_ids": ["G"], "checked_checker_ids": ["C"],
                "matches": [link("C", "G", "full")]}
    target = tmp_path / "results" / (batch["batch_id"] + ".json")
    write_json(target, proposal)
    class Client:
        def agent(self, packet): raise RuntimeError("verification transport unavailable")
    status = run_agent_packets(tmp_path, Client(), matching_validator)
    assert not status["complete"] and read_json(target) == proposal
    _, collected = collect_packets(tmp_path, audited_matching_validator)
    assert not collected["complete"] and collected["errors"]
    with pytest.raises(ValueError):
        compare_scenes(gen, ref, merge_matches(gen, ref, tmp_path))


def test_native_semantic_review_requires_complete_scope_and_exact_quotations(tmp_path):
    from scene_completion.matching_audit import verify_matching, native_review_packet, apply_native_review, validate_native_review_binding
    gen, ref = dataset([scene("G")]), dataset([scene("C")])
    batch = match_packets(gen, ref, tmp_path)["batches"][0]
    packet = read_json(tmp_path / "packets" / (batch["batch_id"] + ".json"))
    decision = {"pair_index": 0, "checker_trigger_quote": "query timeout", "generated_trigger_quote": "query timeout",
                "same_specific_trigger": True, "shared_core_behavior": True, "same_expected_outcome": True,
                "compatible_constraints": True, "status": "full", "evidence": "same query timeout and error",
                "missing_behavior": []}
    class Client:
        def model(self, kind): return "initial-model"
        def agent(self, packet): return {"decisions": [decision]}
    proposed = {**batch, "checked_checker_ids": ["C"], "checked_generated_ids": ["G"],
                "matches": [link("C", "G", "full")], "decisions": [link("C", "G", "full")]}
    target = tmp_path / "results" / (batch["batch_id"] + ".json")
    write_json(target, verify_matching(packet, proposed, Client()))
    bound = native_review_packet(tmp_path)
    review = {"input_hash": bound["input_hash"], "model": "gpt-6-luna", "reasoning_effort": "max", "decisions": []}
    before = read_json(target)
    with pytest.raises(ValueError): apply_native_review(tmp_path, review)
    assert read_json(target) == before
    corrected = {**decision, "review_id": bound["pairs"][0]["review_id"], "same_specific_trigger": False,
                 "status": "unmatched", "evidence": "independent semantic review rejects this proposed relationship"}
    review["decisions"] = [corrected]
    corrected["generated_trigger_quote"] = "fabricated"
    with pytest.raises(ValueError): apply_native_review(tmp_path, review)
    assert read_json(target) == before
    corrected["generated_trigger_quote"] = "query timeout"
    result = apply_native_review(tmp_path, review)
    assert result["accepted_pair_count"] == 0
    assert merge_matches(gen, ref, tmp_path)["complete"]
    assert merge_matches(gen, ref, tmp_path)["verification_models"] == ["gpt-6-luna"]
    assert validate_native_review_binding(tmp_path) == bound
    altered = {**review, "decisions": [{**corrected, "evidence": "different valid rationale"}]}
    with pytest.raises(ValueError, match="differ from applied"):
        validate_native_review_binding(tmp_path, altered)
    with pytest.raises(ValueError, match="gpt-6-luna"):
        validate_native_review_binding(tmp_path, {**review, "model": "other-model"})
    with pytest.raises(ValueError): apply_native_review(tmp_path, review)  # stale review cannot be reapplied


def test_generator_is_complete_and_does_not_require_review(tmp_path, monkeypatch):
    import scene_completion.review as review
    monkeypatch.setattr(review, "_post_chat_completions", lambda *args: pytest.fail("generator used LLM"))
    generated = generate_scenes(sample_model(), sources(tmp_path))
    assert generated["complete"] and not generated["llm_review_used"]
    assert generated["candidate_count"] > 0
    candidates = [s for s in generated["scenarios"] if s["generation_status"] == "unreviewed_candidate"]
    assert len(candidates) == generated["candidate_count"]
    assert all(s["expected_result"].startswith("待需求确认") and s["candidate_id"] for s in candidates)
    assert len({s["scenario_id"] for s in generated["scenarios"]}) == generated["scenario_count"]


def test_checker_packet_has_no_generated_scenarios_or_model_branches(tmp_path):
    index = sources(tmp_path)
    model = sample_model()
    model["use_cases"][0]["scenarios"] = [{"name": "PRIVATE_GENERATED_BRANCH"}]
    manifest = checker_packets(index, model["use_cases"], tmp_path / "checker")
    packet = read_json(tmp_path / "checker" / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    assert "PRIVATE_GENERATED_BRANCH" not in json.dumps(packet)
    assert "generated" not in packet["input"]
    assert "6: Query times out." in packet["input"]["sections"][0]["numbered_text"]


def test_checker_rejects_missing_sections_and_forged_citations(tmp_path):
    index = sources(tmp_path)
    manifest = checker_packets(index, sample_model()["use_cases"], tmp_path / "checker")
    packet = read_json(tmp_path / "checker" / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    raw = scene("ignored", kind="main_success")
    raw["source_refs"] = [{"document": "requirements.md", "line_start": 5, "line_end": 7}]
    result = {"covered_section_ids": [s["chapter_id"] for s in packet["input"]["sections"]], "scenarios": [raw]}
    assert checker_validator(index)(packet, result)[0]["scenario_id"].startswith("CHK-")
    result["covered_section_ids"] = []
    with pytest.raises(ValueError):
        checker_validator(index)(packet, result)
    result["covered_section_ids"] = [s["chapter_id"] for s in packet["input"]["sections"]]
    raw["source_refs"][0]["line_end"] = 100
    with pytest.raises(ValueError):
        checker_validator(index)(packet, result)


def test_partial_counts_and_multilabel_group_counts_deduplicate():
    timeout, auth = "common.timeout", "human.authentication"
    gen = dataset([scene("G1", [timeout, auth]), scene("G2", [timeout]), scene("G3", [auth])])
    ref = dataset([scene("C1", [timeout, auth]), scene("C2", [timeout]), scene("C3", [auth])])
    report = compare_scenes(gen, ref, matched(gen, ref, [link("C1", "G1"), link("C1", "G2", "full")]))
    assert report["overall"]["miss_rate"]["rate"] == 2/3
    assert report["overall"]["existing_completeness"]["rate"] == 2/3
    assert report["by_concern"][timeout]["miss_rate"]["rate"] == .5
    assert report["by_concern"][auth]["existing_completeness"]["rate"] == .5
    assert report["overall"]["recommendation_ids"] == ["G3"]
    assert report["overall"]["partial_checker_ids"] == ["C1"]
    assert report["by_group"]["human"]["checker_count"] == 2


def test_multiple_keys_in_same_group_are_not_summed():
    keys = ["api.data.type", "api.data.format"]
    gen, ref = dataset([scene("G", keys)]), dataset([scene("C", keys)])
    report = compare_scenes(gen, ref, matched(gen, ref, [link("C", "G")]))
    assert report["by_group"]["api_data"]["generated_count"] == 1
    assert report["by_concern"]["api.data.type"]["generated_count"] == 1


def test_classification_mismatch_is_not_a_concern_match():
    gen = dataset([scene("G", ["common.timeout"])])
    ref = dataset([scene("C", ["external_service.availability"])])
    report = compare_scenes(gen, ref, matched(gen, ref, [link("C", "G", "full")]))
    assert report["overall"]["miss_rate"]["rate"] == 0
    assert report["by_concern"]["external_service.availability"]["miss_rate"]["rate"] == 1
    assert len(report["classification_discrepancies"]) == 1


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "incomplete", "stale", "partial_without_gaps"])
def test_metrics_reject_invalid_or_incomplete_matches(mutation):
    gen, ref = dataset([scene("G")]), dataset([scene("C")])
    matches = matched(gen, ref, [link("C", "G")])
    if mutation == "duplicate": matches["matches"].append(link("C", "G"))
    if mutation == "unknown": matches["matches"][0]["generated_scenario_id"] = "X"
    if mutation == "incomplete": matches["complete"] = False
    if mutation == "stale": matches["input_hash"] = "wrong"
    if mutation == "partial_without_gaps": matches["matches"][0]["missing_behavior"] = []
    with pytest.raises(ValueError): compare_scenes(gen, ref, matches)


def test_empty_denominators_and_special_categories():
    gen, ref = dataset([]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    assert report["overall"]["miss_rate"]["rate"] is None
    assert report["by_concern"]["common.timeout"]["existing_completeness"]["rate"] is None
    gen = dataset([scene("G", kind="main_success")])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    assert report["special_categories"]["main_success"]["generated_count"] == 1


def test_full_tile_universe_and_missing_batch_gate(tmp_path):
    gen, ref = dataset([scene(f"G{i}") for i in range(5)]), dataset([scene("C")])
    directory = tmp_path / "matching"
    manifest = match_packets(gen, ref, directory, tile_size=20)
    assert len(manifest["batches"]) == 1
    result = merge_matches(gen, ref, directory)
    assert not result["complete"]
    batch = manifest["batches"][0]
    packet = read_json(directory / "packets" / (batch["batch_id"] + ".json"))
    raw = {"batch_id": batch["batch_id"], "input_hash": batch["input_hash"],
           "checked_generated_ids": [s["scenario_id"] for s in gen["scenarios"]],
           "checked_checker_ids": ["C"], "matches": [],
           "decisions": [{**link("C", f"G{i}", "unmatched"), "missing_behavior": []} for i in range(5)]}
    write_json(directory / "results" / (batch["batch_id"] + ".json"), raw)
    assert merge_matches(gen, ref, directory)["complete"]
    raw["checked_generated_ids"] = ["G0"]
    write_json(directory / "results" / (batch["batch_id"] + ".json"), raw)
    assert not merge_matches(gen, ref, directory)["complete"]


class VectorClient:
    def __init__(self, score): self.score = score
    def model(self, kind): return "fixture"
    def embeddings(self, texts):
        return [[1, 0] if '"G"' in text else [self.score, math.sqrt(1-self.score**2)] for text in texts]


@pytest.mark.parametrize("score,status", [(.85, "full"), (.70, "partial"), (.69, None)])
def test_embedding_threshold_boundaries(score, status):
    gen, ref = dataset([scene("G")]), dataset([scene("C")])
    result = embedding_matches(gen, ref, VectorClient(score))
    assert ([m["status"] for m in result["matches"]] == [status]) if status else not result["matches"]


def test_embeddings_and_rerank_reorder_indices_and_reject_incomplete():
    config = {"base_url": "https://example.invalid/v1", "embedding_model": "fixture", "rerank_model": "fixture"}
    def transport(url, key, body, *args):
        if url.endswith("/embeddings"):
            return {"data": [{"index": i, "embedding": [i+1, 1]} for i in reversed(range(len(body["input"])))]}
        return {"results": [{"index": 1, "relevance_score": .9}, {"index": 0, "relevance_score": .2}]}
    client = SemanticClient(config, transport)
    client.api_key = "fixture"
    assert client.embeddings(["a", "b"]) == [[1, 1], [2, 1]]
    ranked = client.rerank("a", [{"text": "a"}, {"text": "b"}])
    assert ranked[0]["text"] == "b"
    assert ranked[0]["rerank_score"] == .9
    client.transport = lambda *args: {"results": [{"index": 0, "relevance_score": .9}]}
    with pytest.raises(ValueError): client.rerank("a", [{"text": "a"}, {"text": "b"}])


def test_agent_resume_skips_valid_cached_batches(tmp_path):
    from scene_completion.semantic_backend import run_agent_packets
    manifest = prepare_packets(tmp_path, "matching",
                               [{"generated": [scene("G")], "checker": [scene("C")]}], [], {})
    packet = read_json(tmp_path / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    result = {"batch_id": packet["batch_id"], "input_hash": packet["input_hash"],
              "checked_generated_ids": ["G"], "checked_checker_ids": ["C"], "matches": []}
    write_json(tmp_path / "results" / (packet["batch_id"] + ".json"), result)
    class Client:
        def agent(self, packet): pytest.fail("cached successful batch was repeated")
    assert run_agent_packets(tmp_path, Client(), matching_validator)["batches"][0]["status"] == "cached"


def test_rerank_preserves_candidate_set_and_uses_evidence(tmp_path):
    index = sources(tmp_path)
    g = scene("G", ["common.timeout"])
    gen, ref = dataset([g]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    class Client:
        def embeddings(self, texts): return [[1., 0.] for _ in texts]
        def rerank(self, query, evidence): return [{**e, "rerank_score": .6} for e in evidence]
    base = embedding_recommendations(report, ref, index, Client())
    enhanced = embedding_recommendations(report, ref, index, Client(), True)
    assert [s["scenario_id"] for s in base["items"]] == [s["scenario_id"] for s in enhanced["items"]] == ["G"]
    assert enhanced["items"][0]["support_score"] == .6
    assert report["overall"]["miss_rate"]["denominator"] == 0
    assert enhanced["items"][0]["confidence_kind"].endswith("not_probability")


def test_recommendation_rejects_omissions_and_unverified_positive_support(tmp_path):
    index = sources(tmp_path)
    gen, ref = dataset([scene("G")]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    manifest = recommendation_packets(report, index, tmp_path / "rec")
    packet = read_json(tmp_path / "rec" / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    raw = {"items": [{"scenario_id": "G", "support_score": .8, "missing_score": .9,
                      "basis": "evidence", "evidence_refs": []}]}
    with pytest.raises(ValueError): recommendation_validator(index)(packet, raw)
    with pytest.raises(ValueError): finish_recommendations(report, [], "agent", False, True)
    raw["items"][0]["support_score"] = 0
    assert recommendation_validator(index)(packet, raw)[0]["support_score"] == 0


def test_changed_match_set_reuses_only_identical_candidate_scores(tmp_path):
    index = sources(tmp_path)
    gen, ref = dataset([scene("G1"), scene("G2")]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    root = tmp_path / "recommendation"
    manifest = recommendation_packets(report, index, root)
    batch = manifest["batches"][0]
    original = {**batch, "model": "ecnu-max", "items": [
        {"scenario_id": sid, "support_score": 0, "missing_score": .7,
         "basis": "no supplied evidence proves failure", "evidence_refs": []} for sid in ["G1", "G2"]]}
    write_json(root / "results" / (batch["batch_id"] + ".json"), original)
    # Add a new unmatched candidate: the two scores remain reusable and only G3 is pending.
    gen["scenarios"].append(scene("G3"))
    updated = compare_scenes(gen, ref, matched(gen, ref, []))
    new = recommendation_packets(updated, index, root)
    known = read_json(root / "results" / (new["batches"][0]["batch_id"] + ".json"))
    assert known == original  # unchanged packet keeps its actual model and proofs
    assert not (root / "results" / (new["batches"][1]["batch_id"] + ".json")).exists()
    # A changed failure mechanism must not reuse G1's old score.
    gen["scenarios"][0]["trigger"] = "different mechanism"
    changed = compare_scenes(gen, ref, matched(gen, ref, []))
    last = recommendation_packets(changed, index, root)
    uncached = read_json(root / "packets" / (last["batches"][-1]["batch_id"] + ".json"))
    assert {s["scenario_id"] for s in uncached["input"]["candidates"]} == {"G1", "G3"}
    regrouped = read_json(root / "results" / (last["batches"][0]["batch_id"] + ".json"))
    assert regrouped["model"] == "ecnu-max" and regrouped["source_executions"] == [
        {"scenario_id": "G2", "model": "ecnu-max", "batch_id": batch["batch_id"], "input_hash": batch["input_hash"]}]


def test_recommendation_without_execution_identity_is_regenerated_not_relabelled(tmp_path):
    from scene_completion.semantic_backend import run_agent_packets
    index = sources(tmp_path)
    gen, ref = dataset([scene("G")]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    manifest = recommendation_packets(report, index, tmp_path)
    batch = manifest["batches"][0]
    target = tmp_path / "results" / (batch["batch_id"] + ".json")
    write_json(target, {**batch, "items": [{"scenario_id": "G", "support_score": 0,
               "missing_score": .9, "basis": "old unknown-model score", "evidence_refs": []}]})
    class Client:
        config = {}
        calls = 0
        def model(self, kind): return "ecnu-max"
        def agent(self, packet):
            self.calls += 1
            return {"items": [{"scenario_id": "G", "support_score": 0, "missing_score": .5,
                               "basis": "new actual execution", "evidence_refs": []}]}
    client = Client()
    assert run_agent_packets(tmp_path, client, recommendation_validator(index))["complete"]
    assert client.calls == 1 and read_json(target)["model"] == "ecnu-max"
    assert read_json(target)["items"][0]["basis"] == "new actual execution"
    saved = read_json(target)
    recommendation_packets(report, index, tmp_path)
    assert read_json(target) == saved
    assert run_agent_packets(tmp_path, client, recommendation_validator(index))["batches"][0]["status"] == "cached"
    assert client.calls == 1


def test_score_cache_prefers_verified_cap_over_older_uncalibrated_score(tmp_path):
    from scene_completion.support_audit import verify_support, audited_recommendation_validator
    index = sources(tmp_path)
    gen, ref = dataset([scene("G")]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    root = tmp_path / "recommendation"
    manifest = recommendation_packets(report, index, root)
    batch = manifest["batches"][0]
    packet = read_json(root / "packets" / (batch["batch_id"] + ".json"))
    evidence_ref = packet["input"]["evidence"]["G"][0]["source_ref"]
    raw = {**batch, "items": [{"scenario_id": "G", "support_score": .75, "missing_score": .8,
                              "basis": "only interface background", "evidence_refs": [evidence_ref]}]}
    class Client:
        def model(self, kind): return "fixture"
        def agent(self, request):
            return {"verdicts": [{"scenario_id": "G", "evidence_level": "context",
                                  "support_quote": "", "evidence_index": 0, "reason": "no mechanism constraint"}]}
    write_json(root / "results" / (batch["batch_id"] + ".json"), verify_support(packet, raw, Client()))
    old = prepare_packets(root, "recommendation", [packet["input"]], ["older rubric"], packet["output_contract"])
    other = old["batches"][0]
    write_json(root / "results" / (other["batch_id"] + ".json"), {**other, "items": raw["items"]})
    recommendation_packets(report, index, root)
    scores, status = collect_packets(root, audited_recommendation_validator(index))
    assert status["complete"] and scores[0]["support_score"] == .5


def test_waiting_pipeline_removes_stale_formal_outputs_and_keeps_dependencies(tmp_path):
    from argparse import Namespace
    from scene_completion.role_cli import run_pipeline
    index = sources(tmp_path)
    model_path = tmp_path / "model.json"
    write_json(model_path, sample_model())
    root = tmp_path / "run"
    write_json(root / "metrics.json", {"complete": True, "stale": True})
    write_json(root / "scenario_matches.json", {"complete": True, "input_hash": "OLD"})
    args = Namespace(output_dir=str(root), model=str(model_path),
                     spec_document=[str(tmp_path / "requirements.md")], ssd_manifest=None,
                     match_backend="agent", recommend_backend="agent", agent_mode="packets",
                     analysis_layers="SR", checker_input=None, full_threshold=.85, partial_threshold=.7,
                     rerank=False, env_file=None, config=None)
    result, code = run_pipeline(args)
    assert code == 0 and not result["complete"]
    assert result["stages"]["checker"]["status"] == "awaiting_agents"
    assert not (root / "metrics.json").exists()
    assert not (root / "scenario_matches.json").exists()
    assert (root / "dependencies" / "crud_dependency_graph.json").exists()


def test_rerank_failure_does_not_silently_fall_back(tmp_path):
    index = sources(tmp_path)
    gen, ref = dataset([scene("G")]), dataset([])
    report = compare_scenes(gen, ref, matched(gen, ref, []))
    class Client:
        def embeddings(self, texts): return [[1., 0.] for _ in texts]
        def rerank(self, *args): raise RuntimeError("fixture failure")
    with pytest.raises(RuntimeError):
        embedding_recommendations(report, ref, index, Client(), True)


def test_pipeline_marks_rerank_failure_as_incomplete_recommendation(tmp_path, monkeypatch):
    from argparse import Namespace
    import scene_completion.role_cli as cli
    index = sources(tmp_path)
    model = tmp_path / "model.json"
    write_json(model, sample_model())
    checker = tmp_path / "checker.json"
    write_json(checker, {**dataset([]), "scenario_count": 0, "source_hash": fingerprint(index)})
    root = tmp_path / "run"
    args = Namespace(output_dir=str(root), model=str(model), spec_document=[str(tmp_path / "requirements.md")],
                     ssd_manifest=None, match_backend="embedding", recommend_backend="embedding",
                     agent_mode="packets", analysis_layers="SR", checker_input=str(checker),
                     full_threshold=.85, partial_threshold=.7, rerank=True, env_file=None, config=None)
    monkeypatch.setattr(cli, "embedding_matches", lambda g, c, *args: {
        **matched(g, c, []), "backend": "embedding"})
    def fail(*args): raise RuntimeError("rerank unavailable")
    monkeypatch.setattr(cli, "embedding_recommendations", fail)
    with pytest.raises(RuntimeError): cli.run_pipeline(args)
    status = read_json(root / "run_manifest.json")
    assert not status["complete"] and status["stages"]["recommendation"]["status"] == "failed"
    assert status["stages"]["recommendation"]["rerank"] is True
    assert not (root / "report.md").exists()
    assert not (root / "metrics.json").exists()


def test_evidence_skips_empty_trailing_chunks_and_splits_long_lines(tmp_path):
    from scene_completion.sources import evidence_fragments
    doc = tmp_path / "long.md"
    doc.write_text("# UC-001\n" + "x"*9000 + "\n\n\n", encoding="utf-8")
    fragments = evidence_fragments(index_sources([str(doc)]), "UC-001", width=2)
    assert all(e["text"].strip() and len(e["text"]) <= 8192 for e in fragments)
    assert sum(e["text"].count("x") for e in fragments) == 9000
