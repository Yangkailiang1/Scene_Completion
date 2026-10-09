"""CLI orchestration for three roles; packet mode supports real child Agents."""
from __future__ import annotations

import time
import hashlib
from pathlib import Path

from .comparison import compare_scenes, scene_map
from .generator import generate_scenes
from .assessment import build_crud_dependency_graph
from .graphs import (build_use_case_dependency_graph, build_sr_service_dependency_graph,
                     render_crud_dependency_svg, render_use_case_dependency_svg,
                     render_sr_service_dependency_svg)
from .review import load_ecnu_env_file, _resolve_env_reference
from .role_reports import export_reports
from .semantic_backend import SemanticClient, read_json, run_agent_packets, write_json
from .sources import fingerprint, index_sources, validate_refs
from .ssd import generate_ssd_bundle, validate_ssd, write_ssd_bundle
from .three_roles import (checker_packets, checker_validator, embedding_matches,
                          embedding_recommendations, match_packets, matching_validator,
                          merge_checker, merge_matches, merge_recommendations,
                          recommendation_packets, recommendation_validator)
from .generator_model import generator_model_packets, merge_generator_model, model_packet_validator
from .coverage_diagnostics import coverage_diagnostics
from .svg_renderer import render_system_composition_svg
from .overview import build_system_composition_semantics
from .placements import export_placements, annotate_composition_evidence
from .checker_taxonomy import taxonomy_packets, taxonomy_validator


def tool_versions():
    directory = Path(__file__).parent
    versions = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in
            ("generator_model.py", "generator.py", "ssd.py", "concerns.py", "three_roles.py",
             "matching_audit.py", "comparison.py", "semantic_backend.py", "role_reports.py", "placements.py",
             "role_cli.py", "coverage_diagnostics.py", "checker_taxonomy.py", "sources.py", "schemas.py",
             "assembly.py", "support_audit.py", "taxonomy_audit.py", "knowledge.py")}
    versions["scene_completion.py"] = hashlib.sha256((directory.parent / "scene_completion.py").read_bytes()).hexdigest()
    return versions


def validate_execution_models(directory, expected="ecnu-max"):
    """Check actual batch identities, including pre-native semantic proofs."""
    root = Path(directory)
    for batch in read_json(root / "manifest.json")["batches"]:
        result = read_json(root / "results" / (batch["batch_id"] + ".json"))
        if result.get("model") != expected:
            raise ValueError("actual batch model differs from formal ecnu-max execution")
        for execution in result.get("source_executions", []):
            if (execution.get("model") != expected or not execution.get("scenario_id") or
                    not execution.get("batch_id") or not execution.get("input_hash")):
                raise ValueError("reused score execution differs from formal ecnu-max provenance")
        fields = ("semantic_verification", "support_verification", "classification_verification")
        proofs = [record.get(field) for record in [result, *result.get("items", [])] for field in fields]
        for proof in proofs:
            while isinstance(proof, dict):
                model = proof.get("model")
                if model != expected and not (
                        proof.get("provider") == "native_subagent" and model == "gpt-6-luna"):
                    raise ValueError("actual verification model differs from formal execution")
                proof = proof.get("prior_verification")


def register_commands(sub):
    pipeline = sub.add_parser("scene-pipeline", help="generate, independently check, compare and recommend scenes")
    pipeline.add_argument("--model", required=True)
    pipeline.add_argument("--spec-document", action="append", help="legacy: all documents also feed checker")
    pipeline.add_argument("--requirement-document", action="append")
    pipeline.add_argument("--design-document", action="append")
    pipeline.add_argument("--output-dir", required=True)
    pipeline.add_argument("--ssd-manifest")
    pipeline.add_argument("--analysis-layers", default="SR")
    pipeline.add_argument("--match-backend", choices=("agent", "embedding"), default="agent")
    pipeline.add_argument("--recommend-backend", choices=("agent", "embedding"), default="agent")
    pipeline.add_argument("--agent-mode", choices=("packets", "external"), default="packets")
    pipeline.add_argument("--checker-input", help="reuse complete independent checker JSON with identical sources")
    pipeline.add_argument("--full-threshold", type=float, default=.85)
    pipeline.add_argument("--partial-threshold", type=float, default=.70)
    pipeline.add_argument("--rerank", action="store_true")
    pipeline.add_argument("--env-file", default=".env")
    pipeline.add_argument("--config")
    worker = sub.add_parser("run-agent-batches", help="process assigned semantic batches with ECNU; resumable")
    worker.add_argument("--stage-dir", required=True)
    worker.add_argument("--sources-index", required=True)
    worker.add_argument("--worker-index", type=int, default=0)
    worker.add_argument("--worker-count", type=int, default=1)
    worker.add_argument("--batch-id", action="append", help="only retry these assigned manifest batch IDs")
    worker.add_argument("--env-file", default=".env")
    worker.add_argument("--config")
    prep = sub.add_parser("prepare-generator-model", help="independently extract cited generator constraints and dependencies")
    prep.add_argument("--base-model", required=True)
    prep.add_argument("--requirement-document", action="append", required=True)
    prep.add_argument("--design-document", action="append", default=[])
    prep.add_argument("--output-dir", required=True)
    prep.add_argument("--agent-mode", choices=("packets", "external"), default="packets")
    prep.add_argument("--env-file", default=".env")
    prep.add_argument("--config")
    evaluation = sub.add_parser("evaluate-generator", help="recompute exception acceptance and verify completed source-bound run")
    evaluation.add_argument("--output-dir", required=True)
    for command in ("prepare-checker-taxonomy", "prepare-generator-taxonomy"):
        taxonomy_audit = sub.add_parser(command, help="classify source-backed conditions without changing scenes")
        taxonomy_audit.add_argument("--output-dir", required=True, help="existing pipeline output directory")
    for name in ("prepare-matching-review", "apply-matching-review"):
        command = sub.add_parser(name, help="prepare/apply a complete native subagent semantic review")
        command.add_argument("--stage-dir", required=True)
        command.add_argument("--review-file", required=True)


def run_matching_review(args):
    from .matching_audit import native_review_packet, apply_native_review
    if args.command == "prepare-matching-review":
        packet = native_review_packet(args.stage_dir)
        write_json(args.review_file, packet)
        return {"complete": True, "pair_count": len(packet["pairs"]), "input_hash": packet["input_hash"]}, 0
    return apply_native_review(args.stage_dir, read_json(args.review_file)), 0


def _client(args, root):
    if args.env_file:
        load_ecnu_env_file(args.env_file)
    config = read_json(args.config) if args.config else {}
    config.setdefault("cache_dir", str(root / ".scene_cache"))
    return SemanticClient(config)


def run_worker(args):
    index = read_json(args.sources_index)
    root = Path(args.stage_dir)
    stage = read_json(root / "manifest.json")["stage"]
    validators = {"checker": checker_validator(index), "matching": matching_validator,
                  "recommendation": recommendation_validator(index), "generator-model": model_packet_validator(index),
                  "checker-taxonomy": taxonomy_validator(index), "generator-taxonomy": taxonomy_validator(index)}
    client = _client(args, root.parent.parent)
    if stage in {"checker-taxonomy", "generator-taxonomy"}: client.config["taxonomy_sources_index"] = index
    result = run_agent_packets(root, client, validators[stage],
                               args.worker_index, args.worker_count, args.batch_id)
    return result, 0 if result["complete"] else 2


def run_prepare_taxonomy(args):
    root = Path(args.output_dir)
    generator = args.command == "prepare-generator-taxonomy"
    return taxonomy_packets(read_json(root / ("generated_scenarios.json" if generator else "existing_scenarios.json")),
                            read_json(root / ("sources_index.json" if generator else "checker_sources_index.json")),
                            root / "batches" / ("generator-taxonomy" if generator else "checker-taxonomy"),
                            "generator" if generator else "checker"), 0


def role_source_indexes(args):
    requirements = getattr(args, "requirement_document", None) or []
    designs = getattr(args, "design_document", None) or []
    legacy = getattr(args, "spec_document", None) or []
    if requirements or designs:
        if not requirements or legacy:
            raise ValueError("explicit roles require requirements and cannot mix legacy spec-document")
        index = index_sources(requirements + designs)
        req_names = {Path(p).name for p in requirements}
        for document in index["documents"]:
            document["role"] = "requirement" if document["document"] in req_names else "design"
        checker_index = {"schema_version": index["schema_version"],
                         "documents": [d for d in index["documents"] if d["role"] == "requirement"]}
        return index, checker_index
    if not legacy:
        raise ValueError("need requirement-document or legacy spec-document")
    index = index_sources(legacy)
    return index, index


def run_prepare_model(args):
    root = Path(args.output_dir).resolve()
    index, _ = role_source_indexes(args)
    base = read_json(args.base_model)
    write_json(root / "sources_index.json", index)
    stage_dir = root / "batches" / "generator-model"
    generator_model_packets(base, index, stage_dir)
    if args.agent_mode == "external":
        run_agent_packets(stage_dir, _client(args, root), model_packet_validator(index))
    model = merge_generator_model(base, index, stage_dir)
    if model.get("complete") is not True:
        write_json(root / "run_manifest.json", model)
        return model, 2 if args.agent_mode == "external" else 0
    write_json(root / "scene_model.json", model)
    summary = {"complete": True, "model": str(root / "scene_model.json"),
               "source_hash": fingerprint(index), "use_case_count": len(model["use_cases"]),
               "constraint_count": sum(len(u.get("generation_constraints", [])) for u in model["use_cases"]),
               "dependency_count": sum(len(a.get("dependencies", [])) for u in model["use_cases"] for a in u["architecture"].get("ar", [])),
               "agent_model": _client(args, root).model("agent") if args.agent_mode == "external" else "packet-worker"}
    summary["tool_versions"] = tool_versions()
    summary["skill_hash"] = model["generator_provenance"]["skill_hash"]
    write_json(root / "run_manifest.json", summary)
    return summary, 0


def run_evaluate(args):
    root = Path(args.output_dir)
    manifest = read_json(root / "run_manifest.json")
    required = {"generator", "checker", "matching", "recommendation", "export"}
    if (not manifest.get("complete") or not required <= set(manifest.get("stages", {}))
            or any(manifest["stages"][name].get("status") != "complete" for name in required)):
        raise ValueError("evaluation requires all generator/checker/matching/recommendation/export stages complete")
    generated, checker, matches = [read_json(root / (name + ".json")) for name in
                                   ("generated_scenarios", "existing_scenarios", "scenario_matches")]
    checker_index = read_json(root / "checker_sources_index.json")
    if checker["source_hash"] != fingerprint(checker_index) or any(d.get("role") != "requirement" for d in checker_index["documents"]):
        raise ValueError("acceptance checker must be bound exclusively to requirement documents")
    index = read_json(root / "sources_index.json")
    if matches.get("backend") != "agent" or manifest.get("models", {}).get("agent") != "ecnu-max":
        raise ValueError("formal acceptance requires ecnu-max semantic matching")
    # The frozen independent C may predate model-identity recording. Re-extracting
    # it just to fill metadata would change the agreed before/after denominator.
    for stage in ("generator-taxonomy", "checker-taxonomy", "matching",
                  "recommendation-rerank" if manifest.get("rerank") else "recommendation"):
        directory = root / "batches" / stage
        if not (directory / "manifest.json").exists():
            raise ValueError("formal acceptance requires completed independent classification and semantic batches")
        validate_execution_models(directory)
    if generated.get("llm_review_used") is not False:
        raise ValueError("generator acceptance forbids applicability filtering")
    model = read_json(root / "scene_model.json")
    proven_generated = generate_scenes(model, index, read_json(root / "diagrams" / "diagram_manifest.json"),
                                      generated.get("analysis_layers", "SR"),
                                      artifact_loader=getattr(args, "artifact_loader", None))
    if (root / "batches" / "generator-taxonomy" / "manifest.json").exists():
        from .checker_taxonomy import apply_taxonomy_audit
        proven_generated = apply_taxonomy_audit(proven_generated, index, root / "batches" / "generator-taxonomy", "generator")
    if not proven_generated.get("complete") or proven_generated != generated:
        raise ValueError("saved generator differs from unfiltered generation or independent source classification evidence")
    provenance = model.get("generator_provenance", {})
    if (not provenance.get("complete") or provenance.get("source_hash") != fingerprint(index) or
            provenance.get("method") != "independent-source-constraints"):
        raise ValueError("generator acceptance needs independent source-bound semantic preparation")
    proven_checker = merge_checker(checker_index, root / "batches" / "checker",
                                   model["use_cases"])
    if not proven_checker["complete"] or proven_checker["scenarios"] != checker["scenarios"]:
        raise ValueError("saved checker differs from validated independent extraction/classification batches")
    for collection, citations in ((generated, index), (checker, checker_index)):
        for scenario in collection["scenarios"]:
            validate_refs(scenario.get("source_refs"), citations)
    proven = merge_matches(generated, checker, root / "batches" / "matching")
    if not proven["complete"]:
        raise ValueError("matching batch evidence is incomplete or stale")
    from .matching_audit import validate_native_review_binding
    validate_native_review_binding(root / "batches" / "matching")
    exception_ids = {s["scenario_id"] for s in generated["scenarios"] if s["scenario_type"] in
                     {"requirement_exception", "concern_derived_exception"}}
    covered = {m["checker_scenario_id"] for m in proven["matches"] if m["generated_scenario_id"] in exception_ids}
    missing = [s for s in checker["scenarios"] if s["scenario_type"] == "requirement_exception" and s["scenario_id"] not in covered]
    proven_links = {(m["checker_scenario_id"], m["generated_scenario_id"]): m for m in proven["matches"]}
    if missing:
        recovered = merge_matches(generated, {**checker, "scenarios": missing, "scenario_count": len(missing)},
                                  root / "batches" / "matching-recovery")
        if not recovered["complete"]:
            raise ValueError("uncovered exceptions need complete independent recovery comparison")
        validate_execution_models(root / "batches" / "matching-recovery")
        validate_native_review_binding(root / "batches" / "matching-recovery")
        from .matching_audit import exclude_native_rejections
        proven_links.update({(m["checker_scenario_id"], m["generated_scenario_id"]): m
                             for m in exclude_native_rejections(recovered["matches"], root / "batches" / "matching")})
    if {(m["checker_scenario_id"], m["generated_scenario_id"]): m for m in matches["matches"]} != proven_links:
        raise ValueError("saved accepted links differ from independently verified batch evidence")
    metrics = compare_scenes(generated, checker, matches)
    saved = read_json(root / "metrics.json")
    for key in ("exception_overall", "generation_contributions", "concern_method_details", "acceptance",
                "by_concern_exception", "by_group_exception"):
        if metrics[key] != saved[key]:
            raise ValueError("saved exception metrics differ from recomputed input sets")
    rec = read_json(root / "recommendations.json")
    if not rec.get("complete") or {i["scenario_id"] for i in rec["items"]} != set(metrics["overall"]["recommendation_ids"]):
        raise ValueError("recommendation set incomplete or differs from unmatched G")
    verified_rec = merge_recommendations(metrics, index, root / "batches" /
                                        ("recommendation-rerank" if manifest.get("rerank") else "recommendation"),
                                        bool(manifest.get("rerank")))
    if not verified_rec["complete"] or verified_rec["items"] != rec["items"]:
        raise ValueError("saved recommendations differ from validated batch evidence")
    result = {"complete": True, "acceptance": metrics["acceptance"],
              "generator_count": len(generated["scenarios"]), "checker_exception_count": metrics["exception_overall"]["checker_count"],
              "explicit_covered": metrics["generation_contributions"]["explicit"]["matched_checker_count"],
              "concern_covered": metrics["generation_contributions"]["concern_derived"]["matched_checker_count"],
              "input_hash": matches["input_hash"], "checker_source_hash": checker["source_hash"]}
    write_json(root / "evaluation.json", result)
    return result, 0 if result["acceptance"]["passed"] else 2


def run_pipeline(args):
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    manifest = {"schema_version": "three-agent-v1", "complete": False, "stages": {},
                "tool_versions": tool_versions(),
                "match_backend": args.match_backend, "recommend_backend": args.recommend_backend,
                "agent_mode": args.agent_mode, "rerank": args.rerank,
                "thresholds": {"full": args.full_threshold, "partial": args.partial_threshold, "calibrated": False}}

    def stage(name, status, **extra):
        manifest["stages"][name] = {"status": status, **extra}
        manifest["elapsed_seconds"] = time.perf_counter() - started
        write_json(root / "run_manifest.json", manifest)
        print(f"{name}: {status}", flush=True)

    try:
        # A resumed/incomplete run must not leave a previous formal report visible.
        for filename in ("scenario_matches.json", "metrics.json", "recommendations.json", "report.md", "scene_assessment.xlsx"):
            (root / filename).unlink(missing_ok=True)
        model = read_json(args.model)
        if args.env_file:
            load_ecnu_env_file(args.env_file)
        import os
        configured = read_json(args.config) if args.config else {}
        manifest["models"] = {kind: _resolve_env_reference(configured.get(kind + "_model") or os.environ.get(env, ""))
            for kind, env in (("agent", "ECNU_MAX_MODEL"), ("embedding", "ECNU_EMBEDDING_TEXT"),
                              ("rerank", "ECNU_RERANK"))}
        index, checker_index = role_source_indexes(args)
        if model.get("generator_provenance", {}).get("source_hash") not in {None, fingerprint(index)}:
            raise ValueError("prepared generator model belongs to different requirement/design versions")
        write_json(root / "sources_index.json", index)
        write_json(root / "checker_sources_index.json", checker_index)
        write_json(root / "scene_model.json", model)
        manifest["input_hash"] = fingerprint([model, index])
        manifest["source_versions"] = [{"document": d["document"], "hash": d["content_hash"]} for d in index["documents"]]
        manifest["checker_source_hash"] = fingerprint(checker_index)
        manifest["checker_documents"] = [d["document"] for d in checker_index["documents"]]
        if args.ssd_manifest:
            ssd = read_json(args.ssd_manifest)
        else:
            entries = []
            for uc in model["use_cases"]:
                bundle = generate_ssd_bundle(model, uc["use_case_id"])
                for value in (bundle["rr"], bundle["sr"], bundle["ar"], bundle["fused"]):
                    if not validate_ssd(value, model)["valid"]:
                        raise ValueError("invalid generated SSD")
                entries.append(write_ssd_bundle(bundle, model, root / "diagrams"))
            ssd = {"use_cases": entries}
            write_json(root / "diagrams" / "diagram_manifest.json", ssd)
        generated = generate_scenes(model, index, ssd, args.analysis_layers)
        label_dir = root / "batches" / "generator-taxonomy"
        if (label_dir / "manifest.json").exists():
            from .checker_taxonomy import apply_taxonomy_audit
            generated = apply_taxonomy_audit(generated, index, label_dir, "generator")
            if not generated["complete"]:
                stage("generator", "awaiting_agents", directory=str(label_dir),
                      batch_status=generated["taxonomy_audit"]["batch_status"])
                return manifest, 0
        dependency_dir = root / "dependencies"
        dependency_dir.mkdir(exist_ok=True)
        crud = build_crud_dependency_graph(model)
        uc_dependencies = build_use_case_dependency_graph(model)
        service_dependencies = build_sr_service_dependency_graph(model, ssd)
        for name, graph in (("crud_dependency_graph", crud), ("use_case_dependency_graph", uc_dependencies),
                            ("sr_service_dependency_graph", service_dependencies)):
            write_json(dependency_dir / f"{name}.json", graph)
        render_crud_dependency_svg(crud, model["use_cases"], dependency_dir / "crud_dependency_graph.svg")
        render_use_case_dependency_svg(uc_dependencies, dependency_dir / "use_case_dependency_graph.svg")
        render_sr_service_dependency_svg(service_dependencies, dependency_dir / "sr_service_dependency_graph.svg")
        (dependency_dir / "crud_dependency_graph.dot").write_text(crud["dot"], encoding="utf-8")
        (dependency_dir / "crud_dependency_edges.md").write_text(crud["edge_list_markdown"], encoding="utf-8")
        manifest["dependencies"] = {"crud_edges": len(crud["edges"]), "use_case_edges": len(uc_dependencies["edges"]),
                                    "service_edges": len(service_dependencies["edges"])}
        write_json(root / "generated_scenarios.json", generated)
        architecture = export_placements(model, generated, root)
        write_json(root / "system_composition.json", annotate_composition_evidence(build_system_composition_semantics(model), architecture))
        render_system_composition_svg(model, root / "system_composition.svg")
        stage("generator", "complete", count=generated["scenario_count"], llm_review_used=False)
        client = None

        def semantic_client():
            nonlocal client
            if client is None:
                client = _client(args, root)
            return client

        checker_dir = root / "batches" / "checker"
        if args.checker_input:
            checker = read_json(args.checker_input)
            scene_map(checker)
            if checker.get("source_hash") != fingerprint(checker_index):
                raise ValueError("checker input was extracted from different source documents")
        else:
            checker_packets(checker_index, model["use_cases"], checker_dir)
            if args.agent_mode == "external":
                run_agent_packets(checker_dir, semantic_client(), checker_validator(checker_index))
            checker = merge_checker(checker_index, checker_dir, model["use_cases"])
        write_json(root / "existing_scenarios.json", checker)
        if not checker["complete"]:
            stage("checker", "failed" if args.agent_mode == "external" else "awaiting_agents",
                  directory=str(checker_dir), batch_status=checker["batch_status"])
            return manifest, 2 if args.agent_mode == "external" else 0
        stage("checker", "complete", count=checker["scenario_count"])
        match_dir = root / "batches" / "matching"
        stage("matching", "running")
        if args.match_backend == "agent":
            match_packets(generated, checker, match_dir)
            if args.agent_mode == "external":
                run_agent_packets(match_dir, semantic_client(), matching_validator)
            matches = merge_matches(generated, checker, match_dir)
        else:
            matches = embedding_matches(generated, checker, semantic_client(), args.full_threshold, args.partial_threshold)
        write_json(root / "scenario_matches.json", matches)
        if not matches["complete"]:
            stage("matching", "failed" if args.agent_mode == "external" else "awaiting_agents",
                  directory=str(match_dir), batch_status=matches["batch_status"])
            return manifest, 2 if args.agent_mode == "external" else 0
        if args.match_backend == "agent":
            exception_ids = {s["scenario_id"] for s in generated["scenarios"]
                             if s["scenario_type"] in {"requirement_exception", "concern_derived_exception"}}
            accepted_c = {m["checker_scenario_id"] for m in matches["matches"]
                          if m["generated_scenario_id"] in exception_ids}
            missing = [s for s in checker["scenarios"] if s["scenario_type"] == "requirement_exception"
                       and s["scenario_id"] not in accepted_c]
            if missing:
                recovery_checker = {**checker, "scenarios": missing, "scenario_count": len(missing)}
                recovery_dir = root / "batches" / "matching-recovery"
                match_packets(generated, recovery_checker, recovery_dir)
                if args.agent_mode == "external":
                    run_agent_packets(recovery_dir, semantic_client(), matching_validator)
                recovered = merge_matches(generated, recovery_checker, recovery_dir)
                if not recovered["complete"]:
                    stage("matching", "failed" if args.agent_mode == "external" else "awaiting_agents",
                          directory=str(recovery_dir), batch_status=recovered["batch_status"])
                    return manifest, 2 if args.agent_mode == "external" else 0
                unique = {(m["checker_scenario_id"], m["generated_scenario_id"]): m for m in matches["matches"]}
                from .matching_audit import exclude_native_rejections
                unique.update({(m["checker_scenario_id"], m["generated_scenario_id"]): m
                               for m in exclude_native_rejections(recovered["matches"], match_dir)})
                matches["matches"] = list(unique.values())
                matches["recovery_batch_status"] = recovered["batch_status"]
                matches["verification_models"] = sorted(set(matches.get("verification_models", [])) |
                                                         set(recovered.get("verification_models", [])))
                write_json(root / "scenario_matches.json", matches)
        metrics = compare_scenes(generated, checker, matches)
        metrics["coverage_diagnostics"] = coverage_diagnostics(generated, checker, matches)
        write_json(root / "coverage_diagnostics.json", metrics["coverage_diagnostics"])
        stage("matching", "complete", links=len(matches["matches"]), verification_models=matches.get("verification_models", []))
        rec_dir = root / "batches" / ("recommendation-rerank" if args.rerank else "recommendation")
        stage("recommendation", "running")
        if args.recommend_backend == "agent":
            recommendation_packets(metrics, index, rec_dir, semantic_client() if args.rerank else None, args.rerank)
            if args.agent_mode == "external":
                run_agent_packets(rec_dir, semantic_client(), recommendation_validator(index))
            recommendations = merge_recommendations(metrics, index, rec_dir, args.rerank)
        else:
            recommendations = embedding_recommendations(metrics, checker, index, semantic_client(), args.rerank)
        write_json(root / "recommendations.json", recommendations)
        if not recommendations["complete"]:
            stage("recommendation", "failed" if args.agent_mode == "external" else "awaiting_agents",
                  directory=str(rec_dir), batch_status=recommendations["batch_status"])
            return manifest, 2 if args.agent_mode == "external" else 0
        stage("recommendation", "complete", count=recommendations["recommendation_count"])
        # Publish formal metrics only after every semantic stage has completed.
        write_json(root / "metrics.json", metrics)
        manifest["artifacts"] = export_reports(root, generated, checker, matches, metrics, recommendations)
        if client:
            manifest["models"] = {kind: client.model(kind) for kind in
                                  (["agent", "embedding", "rerank"] if args.rerank else
                                   ["agent", "embedding"] if "embedding" in {args.match_backend, args.recommend_backend} else ["agent"])}
        manifest["complete"] = True
        manifest["acceptance"] = metrics.get("acceptance")
        stage("export", "complete")
        return manifest, 0
    except Exception as exc:
        # Never expose HTTP response content or authentication data.
        for name in ("matching", "recommendation"):
            if manifest["stages"].get(name, {}).get("status") == "running":
                stage(name, "failed", error_type=type(exc).__name__, rerank=args.rerank)
        stage("failed", "incomplete", error_type=type(exc).__name__)
        raise
