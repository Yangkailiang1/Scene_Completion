"""Rebuild saved results offline; acceptance additionally needs recorded review."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from . import interaction_batches as batches
from .interaction_cli import merge_model, versions, architecture_proposals
from .interaction_protocol import PROTOCOL, build_ssd, route_mounts, validate_generated
from .interaction_metrics import compare, adoption, EVALUATION_POLICY
from .semantic_backend import collect_packets, read_json
from .sources import fingerprint
from .interaction_versions import packet_versions, replay_versions
from .interaction_execution_identity import validate_result_execution


def replay(directory):
    root = Path(directory)
    run = read_json(root / "run_manifest.json")
    if run.get("protocol") != PROTOCOL or not run.get("complete"):
        raise ValueError("offline replay requires a complete new-protocol run")
    if run.get('evaluation_policy') != EVALUATION_POLICY:
        raise ValueError('evaluation scope differs from current RR/SR one-to-one policy; rerun and rebuild reports')
    if replay_versions(run.get("tool_versions", {})) != replay_versions(versions()):
        raise ValueError("tools or skill changed since this run; create a new versioned round")
    index = read_json(root / "sources_index.json")
    base = read_json(root / "generator_base_identity.json")
    from .interaction_scope import selected_use_case_ids, assessment_base, select_cases, comparison_verification_enabled
    selected = selected_use_case_ids(root)
    scoped_base = assessment_base(base, selected)
    if fingerprint(index) != run["source_hash"]:
        raise ValueError("source version changed")

    def collect(name, validator, prepare):
        folder = root / "batches" / name
        with TemporaryDirectory(prefix="scene-replay-") as temporary:
            expected = prepare(Path(temporary))
        if read_json(folder / "manifest.json") != expected:
            raise ValueError("stage assignment differs from source-derived complete packet universe: " + name)
        rows, status = collect_packets(folder, validator)
        if not status["complete"]:
            raise ValueError("incomplete stage " + name)
        manifest = read_json(folder / "manifest.json")
        execution_evidence = []
        for item in manifest["batches"]:
            packet = read_json(folder / "packets" / (item["batch_id"] + ".json"))
            result = read_json(folder / "results" / (item["batch_id"] + ".json"))
            if packet["input"].get("execution_versions") != packet_versions(name):
                raise ValueError("stage model or execution version mismatch")
            validate_result_execution(result, result_path=folder / "results" / (item["batch_id"] + ".json"))
            evidence = result.get("execution_model_evidence", {})
            execution_evidence.append({"batch_id": item["batch_id"], "evidence": evidence})
            if name == "interaction-checker" and result.get("baseline_execution") and not run.get("checker_baseline_import"):
                raise ValueError("imported checker proof requires explicit baseline provenance")
        if fingerprint(execution_evidence) != run["stages"][name].get("execution_evidence_hash"):
            raise ValueError("model execution evidence changed since run")
        return rows

    model_rows = collect("interaction-model", batches.model_validator(index), lambda d: batches.model_packets(base, index, d))
    model = merge_model(select_cases(model_rows, selected), scoped_base, index)
    if model != read_json(root / "scene_model.json"):
        raise ValueError("model is not reproducible from independent normal extraction")
    from .interaction_origins import audit_model_origins
    from .interaction_model_audit import model_audit_packets, model_audit_validator
    model_audit = collect('interaction-model-audit', model_audit_validator(index), lambda d: model_audit_packets(root / 'batches/interaction-model', index, d, use_case_ids=selected))
    from .interaction_scope import strict_source_quality
    source_quality_passed=all(r['passed'] for r in model_audit)
    if ((strict_source_quality(root) and not source_quality_passed)
            or read_json(root / 'model_source_audit.json') != {'complete': True, 'passed': source_quality_passed, 'items': model_audit}):
        raise ValueError('normal graph source coverage audit is unresolved or changed')
    origins = audit_model_origins(model, index, model_audit)
    if not origins['passed'] or origins != read_json(root / 'model_origin_checks.json'):
        raise ValueError('normal SSD exchange origins are unresolved or changed')
    from .interaction_graph_checks import check_graph_anchors
    anchors = check_graph_anchors(model, index, model_audit)
    if not anchors['passed'] or anchors != read_json(root / 'model_graph_checks.json'):
        raise ValueError('normal graph request steps or RR data vocabulary are unresolved or changed')
    authorization = read_json(root / "model_authorization.json")
    proposals = architecture_proposals(model, base)
    if model["model_gaps"] or authorization.get("model_hash") != fingerprint(model) or authorization.get("proposals") != proposals or {p["proposal_id"] for p in proposals} - set(authorization.get("approved_proposal_ids", [])):
        raise ValueError("model gaps or required architecture confirmations are unresolved")
    ssd = build_ssd(model)
    mounts = route_mounts(ssd)
    from .interaction_scope import saved_scope_mounts
    mounts = saved_scope_mounts(root, ssd, mounts)
    if ssd != read_json(root / "diagrams" / "ssd.json") or mounts != read_json(root / "concern_mounts.json"):
        raise ValueError("SSD or mounts were altered")
    generated = collect("interaction-generation", batches.generation_validator(index), lambda d: batches.generation_packets(ssd, mounts, d))
    generated += [s for uc in model["use_cases"] for s in uc["normal_scenarios"]]
    validate_generated(generated, ssd, mounts, index)
    if generated != read_json(root / "generated_scenarios.json")["scenarios"]:
        raise ValueError("G changed or exceptions were appended outside SSD generation")
    if run.get('checker_baseline_import', {}).get('retained_source_packets'):
        checker_prepare = lambda d: read_json(root/'checker_baseline_snapshot/batches/interaction-checker/manifest.json')
    else:
        checker_prepare = lambda d: batches.checker_packets(base, index, d)
    checked = collect("interaction-checker", batches.checker_validator(index), checker_prepare)
    from .interaction_audit import checker_audit_packets, checker_audit_validator
    audited = collect("interaction-checker-audit", checker_audit_validator(index), lambda d: checker_audit_packets(root / "batches/interaction-checker", index, d))
    if not all(row["passed"] for row in audited) or read_json(root / "checker_source_audit.json") != {"complete": True, "passed": True, "items": audited}:
        raise ValueError("checker source audit is unresolved or changed")
    if run.get("checker_baseline_import"):
        from .interaction_baseline import verify_import
        baseline = verify_import(root, index)
        if baseline["baseline_hash"] != run["checker_baseline_import"]["baseline_hash"] or checked != baseline["scenarios"]:
            raise ValueError("fixed C changed across optimization rounds")
    if checked != read_json(root / "existing_scenarios.json")["scenarios"]:
        raise ValueError("C differs from independent extraction")
    from .interaction_participants import participant_packets, participant_validator, write_participants
    actors = collect('interaction-participants', participant_validator(index), lambda d: participant_packets(root / 'batches/interaction-model', index, d, use_case_ids=selected))
    if not all(r['passed'] for r in actors):
        raise ValueError('participant model omissions remain unresolved')
    checked = select_cases(checked, selected)
    if checked != read_json(root / 'assessment_checker_scenarios.json')['scenarios']:
        raise ValueError('representative checker assessment selection changed')
    pairs = collect("interaction-matching", batches.pair_validator, lambda d: batches.pair_packets(generated, checked, d))
    if pairs != read_json(root / "scenario_matches.json")["pairs"]:
        raise ValueError("saved matches differ from complete pair decisions")
    verify_all = comparison_verification_enabled(root)
    verified = collect("interaction-verification", batches.pair_validator, lambda d: batches.pair_packets([s for s in generated if s["scenario_type"] == "exception"] if verify_all else [], checked if verify_all else [], d, "interaction-verification"))
    left = {(p["checker_scenario_id"], p["generated_scenario_id"]): batches.comparison_signature(p) for p in pairs}
    right = {(p["checker_scenario_id"], p["generated_scenario_id"]): batches.comparison_signature(p) for p in verified}
    if verify_all and left != right:
        raise ValueError("independent comparison disagrees")
    metrics = compare(generated, checked, pairs)
    if metrics != read_json(root / "metrics.json"):
        raise ValueError("saved metrics differ from rebuilt metrics")
    test_index = read_json(root / "test_sources_index.json")
    tests = collect("interaction-test-conditions", batches.test_validator(test_index), lambda d: batches.test_packets(scoped_base, test_index, d))
    if tests != read_json(root / "test_conditions.json")["scenarios"]:
        raise ValueError("acceptance tests changed")
    unmatched = set(metrics["layers"]["combined"]["overall"]["unmatched_generated_ids"])
    recommended = [s for s in generated if s["scenario_id"] in unmatched]
    recs = collect("interaction-recommendation", batches.recommendation_validator(index), lambda d: batches.recommendation_packets(recommended, ssd, d, index))
    recs.sort(key=lambda r: (-r["confidence"], r["scenario_id"]))
    if recs != read_json(root / "recommendations.json")["items"] or {r["scenario_id"] for r in recs} != unmatched:
        raise ValueError("recommendation set or scores changed")
    from .interaction_equivalence import equivalence_packets, equivalence_validator, recommendation_units
    equivalents = collect('interaction-equivalence', equivalence_validator, lambda d: equivalence_packets(recommended, ssd, d))
    units = recommendation_units(recommended, ssd, equivalents)
    if units != read_json(root / 'recommendation_units.json'):
        raise ValueError('recommendation equivalence units changed')
    adoption_result = adoption(units['units'], tests,
        collect("interaction-adoption", batches.pair_validator, lambda d: batches.pair_packets(units['units'], tests, d, "interaction-adoption")), equivalence=units)
    if adoption_result != read_json(root / "adoption.json"):
        raise ValueError("all-recommendation test adoption differs from replay")
    result_hash = fingerprint([generated, checked, pairs, metrics, adoption_result])
    return {"complete": True, "protocol": PROTOCOL, "result_hash": result_hash,
        'evaluation_policy': EVALUATION_POLICY,
        'evaluation_scope': run.get('evaluation_scope'), 'comparison_verification': run.get('comparison_verification', 'all'),
        'source_quality_passed':source_quality_passed, 'source_quality_gate':run.get('source_quality_gate','strict'),
        "coverage_threshold_met": metrics["coverage_threshold_met"], "miss_rates": {k: v["overall"]["miss_rate"] for k, v in metrics["layers"].items()}}


def evaluate(directory):
    root = Path(directory)
    result = replay(root)
    from .interaction_evidence import verify_validation, verify_effect_review
    reasons = []
    if not verify_effect_review(root, result):
        reasons.append("source-bound gpt-6-luna/max effect review is missing or unresolved")
    if not verify_validation(root, result):
        reasons.append("full regression and same-version resume evidence missing")
    return {**result, "accepted": not reasons, "reasons": reasons}
