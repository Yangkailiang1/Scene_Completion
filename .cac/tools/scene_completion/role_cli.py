"""CLI orchestration for three roles; packet mode supports real child Agents."""
from __future__ import annotations

import time
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
from .sources import fingerprint, index_sources
from .ssd import generate_ssd_bundle, validate_ssd, write_ssd_bundle
from .three_roles import (checker_packets, checker_validator, embedding_matches,
                          embedding_recommendations, match_packets, matching_validator,
                          merge_checker, merge_matches, merge_recommendations,
                          recommendation_packets, recommendation_validator)


def register_commands(sub):
    pipeline = sub.add_parser("scene-pipeline", help="generate, independently check, compare and recommend scenes")
    pipeline.add_argument("--model", required=True)
    pipeline.add_argument("--spec-document", action="append", required=True)
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
                  "recommendation": recommendation_validator(index)}
    result = run_agent_packets(root, _client(args, root.parent.parent), validators[stage],
                               args.worker_index, args.worker_count, args.batch_id)
    return result, 0 if result["complete"] else 2


def run_pipeline(args):
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    manifest = {"schema_version": "three-agent-v1", "complete": False, "stages": {},
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
        index = index_sources(args.spec_document)
        write_json(root / "sources_index.json", index)
        write_json(root / "scene_model.json", model)
        manifest["input_hash"] = fingerprint([model, index])
        manifest["source_versions"] = [{"document": d["document"], "hash": d["content_hash"]} for d in index["documents"]]
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
            if checker.get("source_hash") != fingerprint(index):
                raise ValueError("checker input was extracted from different source documents")
        else:
            checker_packets(index, model["use_cases"], checker_dir)
            if args.agent_mode == "external":
                run_agent_packets(checker_dir, semantic_client(), checker_validator(index))
            checker = merge_checker(index, checker_dir, model["use_cases"])
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
        metrics = compare_scenes(generated, checker, matches)
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
        stage("export", "complete")
        return manifest, 0
    except Exception as exc:
        # Never expose HTTP response content or authentication data.
        for name in ("matching", "recommendation"):
            if manifest["stages"].get(name, {}).get("status") == "running":
                stage(name, "failed", error_type=type(exc).__name__, rerank=args.rerank)
        stage("failed", "incomplete", error_type=type(exc).__name__)
        raise
