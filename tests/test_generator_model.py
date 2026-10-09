"""Source separation, resumable generation, anchors and exhaustive comparisons."""
import copy
from types import SimpleNamespace

import pytest

from scene_completion.generator import generate_scenes, availability_labels
from scene_completion.concerns import plan_concern_matrix
from scene_completion.generator_model import generator_model_packets, merge_generator_model, model_packet_validator
from scene_completion.role_cli import role_source_indexes, run_evaluate, run_pipeline
from scene_completion.matching_audit import validate_decisions
from scene_completion.semantic_backend import read_json, write_json
from scene_completion.ssd import generate_ssd_bundle
from scene_completion.three_roles import checker_packets, match_packets, matching_validator, normalize_matching_summary
from tests.test_scene_completion import sample_model
from tests.test_three_roles import dataset, scene


def fixture(tmp_path):
    req, design = tmp_path / "req.md", tmp_path / "design.md"
    req.write_text("# Requirements\n## UC-001\nRequest order.\nCancel payment and stop.\n", encoding="utf-8")
    design.write_text("# Design\n## UC-001\nCall payment service.\nTimeout returns pending.\n", encoding="utf-8")
    index, checker_index = role_source_indexes(SimpleNamespace(requirement_document=[str(req)],
        design_document=[str(design)], spec_document=None))
    model = sample_model()
    model["use_cases"][0]["scenarios"] = [{"name": "SECRET_OLD_SCENE"}]
    stage = tmp_path / "generator-model"
    manifest = generator_model_packets(model, index, stage)
    packet = read_json(stage / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    refs = [{"document": "req.md", "line_start": 4, "line_end": 4}]
    branch = {"name": "cancel", "trigger": "cancel payment", "scenario_type": "requirement_exception",
        "anchor_step_index": 1, "steps": ["cancel payment", "stop"], "expected_result": "stop",
        "recovery": "待需求确认", "concern_keys": ["service.workflow.interruption"], "source_refs": refs}
    output = {"covered_section_ids": [s["chapter_id"] for s in packet["input"]["sections"]],
        "main_flow": [{"text": "Request order", "source_refs": refs}], "scenarios": [branch],
        "constraints": [{"name": "cancel check", "trigger": "cancel payment", "scenario_steps": ["cancel payment", "stop"],
            "source_step_index": 1, "check_target_name": "OrderService", "expected_result": "stop",
            "concern_keys": ["service.workflow.interruption"], "source_refs": refs}], "dependencies": []}
    return model, index, checker_index, stage, packet, output


def test_generator_and_checker_inputs_are_separated(tmp_path):
    model, index, checker_index, stage, packet, output = fixture(tmp_path)
    assert {s["role"] for s in packet["input"]["sections"]} == {"requirement", "design"}
    assert "SECRET_OLD_SCENE" not in str(packet)
    assert "checker_scenarios" not in packet["input"]
    checker_dir = tmp_path / "checker"
    manifest = checker_packets(checker_index, model["use_cases"], checker_dir)
    checker = read_json(checker_dir / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    assert {s["document"] for s in checker["input"]["sections"]} == {"req.md"}
    assert "Timeout returns pending" not in str(checker)


def test_generator_model_resume_and_specific_cancel_path(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    assert not merge_generator_model(model, index, stage)["complete"]
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
               {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    assert prepared["complete"]
    assert merge_generator_model(model, index, stage) == prepared
    generated = generate_scenes(prepared, index)
    concrete = next(s for s in generated["scenarios"] if s["generation_status"] == "constraint_instantiation")
    assert concrete["scenario_steps"] == ["cancel payment", "stop"]
    assert concrete["expected_result"] == "stop"
    assert concrete["concern_keys"] == ["service.workflow.interruption"]
    assert concrete["source_refs"][0]["document"] == "req.md"
    assert concrete["trace_mapping_status"] == "needs_confirmation"
    assert concrete["mount_proposal"]["status"] == "needs_confirmation"
    assert concrete["implementation_owner_names"] == [a["microservice_name"]
        for a in prepared["use_cases"][0]["architecture"]["ar"]]
    assert not generated["llm_review_used"]


def test_generic_candidates_do_not_inherit_success_guarantees(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    output["preconditions"] = "OrderService is available; target order exists"
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
               {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    generic = [s for s in generate_scenes(prepared, index)["scenarios"]
               if s["generation_status"] == "unreviewed_candidate"]
    assert generic
    assert all(s["preconditions"] != output["preconditions"] for s in generic)
    assert all(s["use_case_preconditions"] == output["preconditions"] for s in generic)


def test_same_trigger_different_outcomes_and_sources_keep_distinct_ids(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    other = {**copy.deepcopy(output["constraints"][0]), "expected_result": "queue for review"}
    output["constraints"].append(other)
    output["constraints"].append(copy.deepcopy(other))
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
               {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    assert len({r["constraint_id"] for r in prepared["use_cases"][0]["generation_constraints"]}) == 3
    scenes = generate_scenes(prepared, index)
    assert len({s["scenario_id"] for s in scenes["scenarios"]}) == len(scenes["scenarios"])
    assert merge_generator_model(model, index, stage) == prepared


def test_declared_system_service_annotation_maps_to_existing_implementation(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    service = model["use_cases"][0]["architecture"]["ar"][0]["microservice_name"]
    output["dependencies"] = [{"caller_name": f"在线商城系统（{service}）", "target_name": "OrderTable",
        "target_kind": "internal_database", "operation": "read order", "direction": "outgoing",
        "source_step_index": 1, "source_refs": output["constraints"][0]["source_refs"]}]
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
               {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    dependency = prepared["use_cases"][0]["architecture"]["ar"][0]["dependencies"][0]
    assert dependency["caller_name"] == service
    assert dependency["extracted_dependency"]["caller_name"].startswith("在线商城系统（")


def test_human_interactions_and_facade_returns_do_not_add_service_components(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    actor = next(n["name"] for n in model["system_composition"]["nodes"] if n["kind"] == "human_actor")
    service = model["use_cases"][0]["architecture"]["ar"][0]["microservice_name"]
    base = {"caller_name": service, "operation": "return response", "direction": "outgoing",
            "source_step_index": 1, "source_refs": output["constraints"][0]["source_refs"]}
    output["dependencies"] = [{**base, "target_name": actor, "target_kind": "external_service"},
                              {**base, "target_name": "OnlineMallSystem", "target_kind": "internal_service"}]
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
               {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    arch = prepared["use_cases"][0]["architecture"]
    assert not arch["ar"][0]["dependencies"]
    assert arch["human_interactions"] and arch["facade_returns"]
    assert not any(n["name"] == "OnlineMallSystem" or (n["name"] == actor and n["kind"] == "external_service")
                   for n in prepared["system_composition"]["nodes"])


def test_local_dispatch_does_not_create_cross_uc_self_dependency(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    local = model["use_cases"][0]["architecture"]["ar"][0]
    duplicate = {"node_id": "other-uc", "name": local["microservice_name"], "kind": "internal_service"}
    model["system_composition"]["nodes"].insert(0, duplicate)
    output["constraints"][0]["check_target_name"] = local["microservice_name"]
    output["dependencies"] = [{"caller_name": model["system_name"], "target_name": local["microservice_name"],
        "target_kind": "internal_service", "operation": "dispatch", "direction": "outgoing", "source_step_index": 1,
        "source_refs": output["constraints"][0]["source_refs"]}]
    manifest = generator_model_packets(model, index, stage)
    packet = read_json(stage / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
        {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    uc = prepared["use_cases"][0]
    assert uc["architecture"]["ar"][0]["dependencies"] == []
    assert uc["architecture"]["ar"][0]["dispatch_source_refs"]
    assert uc["generation_constraints"][0]["check_node_id"] == local["microservice_id"]


@pytest.mark.parametrize("mutation", ["missing_section", "outside_section", "bad_anchor", "unknown_key"])
def test_generator_rejects_incomplete_or_invented_evidence(tmp_path, mutation):
    _, index, _, _, packet, output = fixture(tmp_path)
    data = copy.deepcopy(output)
    if mutation == "missing_section": data["covered_section_ids"] = []
    if mutation == "outside_section": data["constraints"][0]["source_refs"][0]["line_end"] = 999
    if mutation == "bad_anchor": data["constraints"][0]["source_step_index"] = 2
    if mutation == "unknown_key": data["constraints"][0]["concern_keys"] = ["invented.concern"]
    with pytest.raises(ValueError): model_packet_validator(index)(packet, data)


def test_matching_one_c_eight_g_and_all_unmatched_decisions(tmp_path):
    generated = dataset([scene(f"G{i}") for i in range(19)])
    checker = dataset([scene("C1"), scene("C2")])
    manifest = match_packets(generated, checker, tmp_path, tile_size=100)
    assert len(manifest["batches"]) == 6
    for batch in manifest["batches"]:
        packet = read_json(tmp_path / "packets" / (batch["batch_id"] + ".json"))
        gs, cs = packet["input"]["generated"], packet["input"]["checker"]
        assert len(cs) == 1 and 1 <= len(gs) <= 8
        result = {"checked_generated_ids": [g["scenario_id"] for g in gs],
            "checked_checker_ids": [c["scenario_id"] for c in cs], "matches": [],
            "decisions": [{"checker_scenario_id": cs[0]["scenario_id"], "generated_scenario_id": g["scenario_id"],
                "status": "unmatched", "evidence": "different failure object", "missing_behavior": []} for g in gs]}
        assert matching_validator(packet, result) == []
        result["decisions"].pop()
        with pytest.raises(ValueError, match="EVERY pair"): matching_validator(packet, result)


def test_explicit_roles_reject_legacy_mixture():
    with pytest.raises(ValueError):
        role_source_indexes(SimpleNamespace(requirement_document=["req.md"], design_document=[], spec_document=["legacy.md"]))


def test_pair_summary_is_derived_without_changing_semantic_status(tmp_path):
    manifest = match_packets(dataset([scene("G1")]), dataset([scene("C1")]), tmp_path)
    packet = read_json(tmp_path / "packets" / (manifest["batches"][0]["batch_id"] + ".json"))
    d = {"checker_scenario_id": "C1", "generated_scenario_id": "G1", "status": "partial",
         "evidence": "same timeout, recovery absent", "missing_behavior": ["recovery"]}
    raw = {"checked_generated_ids": ["G1"], "checked_checker_ids": ["C1"],
           "decisions": [d], "matches": [{**d, "evidence": "timeout condition agrees"}]}
    normalized = normalize_matching_summary(packet, raw)
    assert normalized["matches"] == [d]
    assert normalized["raw_match_summary"] == raw["matches"]
    assert raw["matches"][0]["evidence"] == "timeout condition agrees"
    assert normalize_matching_summary(packet, {k: v for k, v in raw.items() if k != "matches"})["matches"] == [d]
    nullable = normalize_matching_summary(packet, {**raw, "matches": None})
    assert nullable["matches"] == [d] and nullable["raw_match_summary"] is None
    with pytest.raises(ValueError):
        normalize_matching_summary(packet, {**raw, "matches": None, "decisions": []})
    raw["matches"][0]["status"] = "full"
    with pytest.raises(ValueError, match="contradicts"):
        normalize_matching_summary(packet, raw)


def test_availability_classification_uses_actual_component_boundary():
    nodes = [{"name": "LogisticsService", "kind": "external_service"},
             {"name": "ProductDisplayService", "kind": "abstract_service"},
             {"name": "LogisticsServiceAdapter", "kind": "internal_service"},
             {"name": "ProductCatalogService", "kind": "internal_service"}]
    original = ["external_service.availability", "service.dependency.availability"]
    keys, changes = availability_labels(original, "LogisticsServiceAdapter 服务不可用", nodes)
    assert keys == ["service.dependency.availability"] and changes
    keys, changes = availability_labels(original, "调用 LogisticsService 不可用", nodes)
    assert keys == ["external_service.availability"] and changes
    assert availability_labels(original, "ProductDisplayService不可用", nodes)[0] == ["service.dependency.availability"]
    # Ambiguous two-service subjects require explicit evidence, not guessing.
    assert availability_labels(original, "LogisticsServiceAdapter 调用 LogisticsService 失败", nodes)[0] == sorted(original)


def test_explicit_internal_dependency_mounts_sr_checks():
    model = sample_model()
    model["version"] = "8"
    model["use_cases"][0]["architecture"]["ar"][0]["dependencies"] = [{
        "target_node_id": "display", "operation": "read order display", "direction": "outgoing",
        "source_step_index": 1, "source_location": "design.md:3-4"}]
    fused = generate_ssd_bundle(model, "UC-001")["fused"]
    matrix = plan_concern_matrix(model, fused_ssd=fused)
    mounted = [s for s in matrix["items"] if s["concern_key"] == "service.dependency.availability"]
    assert mounted and all(s["subject_node_id"] == "display" for s in mounted)
    dependency_exchanges = {m["exchange_id"] for m in fused["messages"] if m.get("dependency_node_id") == "display"}
    assert {s["exchange_id"] for s in mounted} <= dependency_exchanges


def test_generation_can_replay_archived_ssd_without_original_paths(tmp_path):
    model, index, _, stage, packet, output = fixture(tmp_path)
    write_json(stage / "results" / (packet["batch_id"] + ".json"),
               {**output, "batch_id": packet["batch_id"], "input_hash": packet["input_hash"]})
    prepared = merge_generator_model(model, index, stage)
    fused = generate_ssd_bundle(prepared, "UC-001")["fused"]
    original = tmp_path / "original_fused.json"
    write_json(original, fused)
    manifest = {"use_cases": [{"use_case_id": "UC-001",
                 "artifacts": {"fused": {"json": str(original), "svg": "recorded.svg"}}}]}
    expected = generate_scenes(prepared, index, manifest)
    original.unlink()
    calls = []
    def load(path):
        calls.append(path)
        assert path == str(original)
        return fused
    assert generate_scenes(prepared, index, manifest, artifact_loader=load) == expected
    assert calls and all(s["exchange_id"] for s in expected["scenarios"]
                         if s["generation_status"] == "explicit")
    with pytest.raises(FileNotFoundError):
        generate_scenes(prepared, index, manifest)


def test_explicit_match_does_not_hide_unmatched_routed_check_locations():
    from scene_completion.coverage_diagnostics import coverage_diagnostics
    key = "service.workflow.interruption"
    base = {"use_case_id": "UC", "scenario_type": "requirement_exception", "name": "cancel",
            "trigger": "cancel", "scenario_steps": ["stop"], "expected_result": "stopped",
            "source_refs": [], "concern_keys": [key]}
    explicit = {**base, "scenario_id": "E", "generation_status": "explicit"}
    routed = {**base, "scenario_id": "D", "scenario_type": "concern_derived_exception",
              "candidate_id": "CAND", "generation_status": "constraint_instantiation",
              "trace_mapping_status": "needs_confirmation", "mount_proposal": {"components": ["PaymentAdapter"]}}
    checker = {**base, "scenario_id": "C"}
    matches = {"matches": [{"checker_scenario_id": "C", "generated_scenario_id": "E",
                            "status": "full", "evidence": "same cancellation", "missing_behavior": []}]}
    row = coverage_diagnostics({"scenarios": [explicit, routed]}, {"scenarios": [checker]}, matches)[0]
    assert row["explicit_covered"] and not row["concern_covered"]
    assert row["matched_generated_ids"] == ["E"]
    assert row["candidate_ids"] == ["CAND"] and row["unmatched_routed_generated_ids"] == ["D"]
    assert row["unmapped_check_ids"] == ["D"] and row["suggested_check_locations"] == [routed["mount_proposal"]]


def test_contradictory_success_after_cancel_cannot_be_partial():
    pair = {"pair_index": 0, "checker": {"trigger": "cancel payment"}, "generated": {"trigger": "cancel payment"}}
    decision = {"pair_index": 0, "checker_trigger_quote": "cancel payment", "generated_trigger_quote": "cancel payment",
        "same_specific_trigger": True, "shared_core_behavior": True, "same_expected_outcome": False,
        "compatible_constraints": False, "status": "partial", "evidence": "generated path completes a cancelled payment",
        "missing_behavior": ["stop processing"]}
    assert validate_decisions([pair], [decision])[0]["status"] == "unmatched"


def test_evaluation_rejects_missing_required_stages(tmp_path):
    write_json(tmp_path / "run_manifest.json", {"complete": True, "stages": {}})
    with pytest.raises(ValueError, match="all generator/checker"):
        run_evaluate(SimpleNamespace(output_dir=str(tmp_path)))
    assert not (tmp_path / "evaluation.json").exists()


def test_formal_model_identity_checks_actual_batches_and_prior_proofs(tmp_path):
    from scene_completion.role_cli import validate_execution_models
    write_json(tmp_path / "manifest.json", {"batches": [{"batch_id": "B"}]})
    target = tmp_path / "results" / "B.json"
    write_json(target, {"model": "other-model"})
    with pytest.raises(ValueError, match="actual batch model"):
        validate_execution_models(tmp_path)
    result = {"model": "ecnu-max", "semantic_verification": {
        "model": "gpt-6-luna", "provider": "native_subagent",
        "prior_verification": {"model": "other-model"}}}
    write_json(target, result)
    with pytest.raises(ValueError, match="actual verification model"):
        validate_execution_models(tmp_path)
    write_json(target, {"model": "ecnu-max", "items": [{"support_verification": {"model": "other-model"}}]})
    with pytest.raises(ValueError, match="actual verification model"):
        validate_execution_models(tmp_path)
    write_json(target, {"model": "ecnu-max", "items": [{"support_verification": {}}]})
    with pytest.raises(ValueError, match="actual verification model"):
        validate_execution_models(tmp_path)
    write_json(target, {"model": "ecnu-max", "source_executions": [{"model": "other-model"}]})
    with pytest.raises(ValueError, match="reused score execution"):
        validate_execution_models(tmp_path)
    result["semantic_verification"]["prior_verification"]["model"] = "ecnu-max"
    write_json(target, result)
    validate_execution_models(tmp_path)
    write_json(target, {"model": "ecnu-max", "classification_verification": {"model": "other-model"}})
    with pytest.raises(ValueError, match="actual verification model"):
        validate_execution_models(tmp_path)


def test_stale_generator_source_cannot_publish_previous_formal_metrics(tmp_path):
    model, index, checker_index, _, _, _ = fixture(tmp_path)
    model["generator_provenance"] = {"source_hash": "old-source-version"}
    write_json(tmp_path / "model.json", model)
    output = tmp_path / "run"
    write_json(output / "metrics.json", {"acceptance": "obsolete"})
    args = SimpleNamespace(output_dir=str(output), model=str(tmp_path / "model.json"),
        requirement_document=[str(tmp_path / "req.md")], design_document=[str(tmp_path / "design.md")],
        spec_document=None, env_file=None, config=None, match_backend="agent", recommend_backend="agent",
        agent_mode="packets", rerank=False, full_threshold=.85, partial_threshold=.70)
    with pytest.raises(ValueError, match="different requirement/design versions"):
        run_pipeline(args)
    assert not (output / "metrics.json").exists()
