#!/usr/bin/env python3
"""Agent-facing CLI for Scene Completion V6."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scene_completion.assembly import assemble_results
from scene_completion.concerns import audit_concern_coverage, plan_concern_matrix, validate_concern_matrix
from scene_completion.diagrams import render_diagrams, validate_diagram_spec
from scene_completion.document_extract import extract_document
from scene_completion.exporters import export_workbooks
from scene_completion.knowledge import load_concern, load_diagram_knowledge, list_concerns, list_diagram_knowledge
from scene_completion.png_renderer import convert_svg_to_png
from scene_completion.schemas import ValidationFailure, validate_scene_model
from scene_completion.ssd import fuse_ssd, generate_ssd_bundle, validate_ssd, write_ssd_bundle
from scene_completion.graphs import build_use_case_dependency_graph, render_use_case_dependency_svg, validate_use_case_dependency_graph, build_sr_service_dependency_graph, render_sr_service_dependency_svg
from scene_completion.svg_renderer import render_system_composition_svg
from scene_completion.overview import build_system_composition_semantics
from scene_completion.review import load_ecnu_env_file, review_concerns
from scene_completion.metrics import attach_metrics_to_run_manifest, metrics_dir_from_argv, write_stage_metric


def _read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, value) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _main_impl(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Portable Scene Completion V6 tools")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="extract text from a source document")
    extract.add_argument("--input", required=True)
    extract.add_argument("--output", required=True)
    validate = sub.add_parser("validate-model", help="validate and normalize scene_model.json")
    validate.add_argument("--input", required=True)
    validate.add_argument("--output")
    sub.add_parser("list-concerns", help="list V6 concern definitions")
    load = sub.add_parser("load-concern", help="load one concern reference")
    load.add_argument("--key", required=True)
    sub.add_parser("list-diagram-knowledge", help="list diagram-generation references")
    load_diagram = sub.add_parser("load-diagram-knowledge", help="load one diagram reference")
    load_diagram.add_argument("--key", required=True)
    plan = sub.add_parser("plan-concerns", help="create a full candidate concern matrix")
    plan.add_argument("--model", required=True)
    plan.add_argument("--fused-ssd", help="optional fused SSD JSON; route candidates from its standardized messages")
    plan.add_argument("--ssd-manifest", help="diagram_manifest.json containing every use case fused SSD")
    plan.add_argument("--analysis-layers", default="SR", help="comma-separated analysis layers: SR (default) or SR,AR")
    plan.add_argument("--output", required=True)
    validate_matrix = sub.add_parser("validate-concerns", help="validate a V6 concern matrix")
    validate_matrix.add_argument("--model", required=True)
    validate_matrix.add_argument("--input", required=True)
    validate_matrix.add_argument("--require-complete", action="store_true")
    audit = sub.add_parser("audit-run", help="strictly audit complete SSD and concern coverage")
    audit.add_argument("--model", required=True)
    audit.add_argument("--ssd-manifest", required=True)
    audit.add_argument("--concern-matrix", required=True)
    review = sub.add_parser("review-concerns", help="review pending concerns externally, with the Agent, or with automatic fallback")
    review.add_argument("--model", required=True)
    review.add_argument("--ssd-manifest", required=True)
    review.add_argument("--concern-matrix", required=True)
    review.add_argument("--mode", choices=("external", "agent", "auto", "merge-agent"), default="external")
    review.add_argument("--config", help="OpenAI-compatible endpoint configuration (external/auto modes)")
    review.add_argument("--env-file", help="safely load ECNU_MAX_* values from a .env file")
    review.add_argument("--agent-batch-dir", help="directory for bounded Agent review packets")
    review.add_argument("--agent-results", help="Agent judgement batches JSON (merge-agent mode)")
    review.add_argument("--output", required=True)
    validate_diagram = sub.add_parser("validate-diagrams", help="validate V5 diagram sources")
    validate_diagram.add_argument("--model", required=True)
    validate_diagram.add_argument("--input", required=True)
    render = sub.add_parser("render-diagrams", help="generate dependency-free SVG and optionally render PlantUML diagrams")
    render.add_argument("--model", required=True)
    render.add_argument("--input", required=True)
    render.add_argument("--output-dir", required=True)
    render.add_argument("--plantuml-jar")
    render.add_argument("--require-render", action="store_true")
    render.add_argument("--require-png", action="store_true", help="fail if no local SVG-to-PNG converter is available")
    render_png = sub.add_parser("render-png", help="convert one generated SVG to PNG")
    render_png.add_argument("--input-svg", required=True)
    render_png.add_argument("--output-png", required=True)
    render_png.add_argument("--require-png", action="store_true")
    generate_ssd = sub.add_parser("generate-ssd", help="generate RR/SR/AR/fused main-flow SSDs per RR use case")
    generate_ssd.add_argument("--model", required=True)
    generate_ssd.add_argument("--use-case")
    generate_ssd.add_argument("--api-map")
    generate_ssd.add_argument("--output-dir", required=True)
    generate_ssd.add_argument("--plantuml-jar")
    generate_ssd.add_argument("--render", action="store_true")
    fuse = sub.add_parser("fuse-ssd", help="fuse RR/SR/AR SSDs")
    fuse.add_argument("--rr", required=True)
    fuse.add_argument("--sr", required=True)
    fuse.add_argument("--api-map")
    fuse.add_argument("--output", required=True)
    validate_ssd_parser = sub.add_parser("validate-ssd", help="validate one SSD JSON")
    validate_ssd_parser.add_argument("--input", required=True)
    validate_ssd_parser.add_argument("--model")
    dep = sub.add_parser("render-dependency-graph", help="render semantic RR use-case dependency graph")
    dep.add_argument("--model", required=True)
    dep.add_argument("--output-dir", required=True)
    dep.add_argument("--require-png", action="store_true")
    sr_dep = sub.add_parser("render-service-dependency-graph", help="render evidence-backed SR service dependency graph")
    sr_dep.add_argument("--model", required=True)
    sr_dep.add_argument("--ssd-manifest")
    sr_dep.add_argument("--output-dir", required=True)
    sr_dep.add_argument("--require-png", action="store_true")
    assemble = sub.add_parser("assemble", help="assemble V5 findings and export artifacts")
    assemble.add_argument("--model", required=True)
    assemble.add_argument("--concern-matrix", required=True)
    assemble.add_argument("--semantic-findings", required=True)
    assemble.add_argument("--diagram-manifest")
    assemble.add_argument("--ssd-manifest")
    assemble.add_argument("--spec-document", action="append", default=[], help="source Markdown spec used to verify explicit exception provenance; repeatable")
    assemble.add_argument("--output-dir", required=True)
    assemble.add_argument("--require-png", action="store_true", help="require all required overview/dependency/SSD PNG artifacts")

    for command_parser in sub.choices.values():
        command_parser.add_argument("--metrics-dir", help="optional per-run directory for privacy-safe stage metrics")

    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            result = extract_document(args.input)
            _write_json(args.output, result)
            print(json.dumps({"status": "success", "output": str(Path(args.output).resolve())}, ensure_ascii=False))
            return 0
        if args.command == "validate-model":
            report = validate_scene_model(_read_json(args.input))
            if args.output and report.get("normalized_model"):
                _write_json(args.output, report["normalized_model"])
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["valid"] else 2
        if args.command == "list-concerns":
            print(json.dumps({"version": "6", "concerns": list_concerns()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "load-concern":
            print(json.dumps(load_concern(args.key), ensure_ascii=False, indent=2))
            return 0
        if args.command == "list-diagram-knowledge":
            print(json.dumps({"version": "6", "references": list_diagram_knowledge()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "load-diagram-knowledge":
            print(json.dumps(load_diagram_knowledge(args.key), ensure_ascii=False, indent=2))
            return 0
        if args.command == "plan-concerns":
            result = plan_concern_matrix(_read_json(args.model), _read_json(args.fused_ssd) if args.fused_ssd else None, _read_json(args.ssd_manifest) if args.ssd_manifest else None, args.analysis_layers)
            _write_json(args.output, result)
            print(json.dumps({"status": "success", "output": str(Path(args.output).resolve()), "count": len(result["items"])}, ensure_ascii=False))
            return 0
        if args.command == "validate-concerns":
            result = validate_concern_matrix(_read_json(args.model), _read_json(args.input), require_complete=args.require_complete)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        if args.command == "audit-run":
            result = audit_concern_coverage(_read_json(args.model), _read_json(args.concern_matrix), _read_json(args.ssd_manifest))
            output = Path(args.concern_matrix).with_name("concern_coverage_report.json")
            _write_json(output, result.get("report", {}))
            print(json.dumps({**result, "coverage_report": str(output)}, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        if args.command == "review-concerns":
            if args.env_file and args.mode in {"external", "auto"}:
                load_ecnu_env_file(args.env_file)
            if args.mode == "merge-agent" and not args.agent_results:
                raise ValidationFailure(["--agent-results is required with --mode merge-agent"])
            if args.mode in {"external", "auto"} and not args.config and args.mode == "external":
                raise ValidationFailure(["--config is required with --mode external"])
            result = review_concerns(
                _read_json(args.model), _read_json(args.ssd_manifest), _read_json(args.concern_matrix),
                _read_json(args.config) if args.config else {}, args.output,
                mode=args.mode,
                agent_results=_read_json(args.agent_results) if args.agent_results else None,
                agent_batch_dir=args.agent_batch_dir,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("valid") or result.get("accepted") else 2
        if args.command == "validate-diagrams":
            result = validate_diagram_spec(_read_json(args.model), _read_json(args.input))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        if args.command == "render-diagrams":
            result = render_diagrams(_read_json(args.model), _read_json(args.input), args.output_dir, args.plantuml_jar, args.require_render, args.require_png)
            print(json.dumps({"status": "success", "manifest": result}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "render-png":
            result = convert_svg_to_png(args.input_svg, args.output_png, require=args.require_png)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("status") == "rendered" else 2
        if args.command == "generate-ssd":
            model = _read_json(args.model)
            api_map = _read_json(args.api_map) if args.api_map else None
            use_cases = [args.use_case] if args.use_case else [item["use_case_id"] for item in validate_scene_model(model, raise_on_error=True)["normalized_model"]["use_cases"]]
            manifests = []
            for use_case_id in use_cases:
                bundle = generate_ssd_bundle(model, use_case_id, api_map)
                manifests.append(write_ssd_bundle(bundle, model, args.output_dir, args.plantuml_jar, args.render))
            root = Path(args.output_dir).expanduser().resolve()
            root.mkdir(parents=True, exist_ok=True)
            manifest = {"version": str(model.get("version", "6")), "project": model.get("project", ""), "use_cases": manifests}
            (root / "diagram_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"status": "success", "output": str(root / "diagram_manifest.json"), "use_case_count": len(manifests)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "fuse-ssd":
            rr = _read_json(args.rr)
            sr = _read_json(args.sr)
            api_map = _read_json(args.api_map) if args.api_map else None
            result = fuse_ssd(rr, sr, api_map)
            _write_json(args.output, result)
            print(json.dumps({"status": "success", "output": str(Path(args.output).resolve()), "review_items": len(result.get("review_items", []))}, ensure_ascii=False))
            return 0
        if args.command == "validate-ssd":
            value = _read_json(args.input)
            ssd = value.get("fused", value) if isinstance(value, dict) else value
            result = validate_ssd(ssd, _read_json(args.model) if args.model else None)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        if args.command == "render-dependency-graph":
            model = _read_json(args.model)
            graph = build_use_case_dependency_graph(model)
            validate_use_case_dependency_graph(model, graph, True)
            output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
            graph_path = output / "use_case_dependency_graph.json"
            _write_json(graph_path, graph)
            svg = render_use_case_dependency_svg(graph, output / "use_case_dependency_graph.svg")
            png = convert_svg_to_png(svg, output / "use_case_dependency_graph.png", require=args.require_png)
            print(json.dumps({"status": "success", "json": str(graph_path), "svg": str(svg), "png": png}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "render-service-dependency-graph":
            model = _read_json(args.model)
            graph = build_sr_service_dependency_graph(model, _read_json(args.ssd_manifest) if args.ssd_manifest else None)
            output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
            graph_path = output / "sr_service_dependency_graph.json"
            _write_json(graph_path, graph)
            svg = render_sr_service_dependency_svg(graph, output / "sr_service_dependency_graph.svg")
            png_result = convert_svg_to_png(svg, output / "sr_service_dependency_graph.png", require=args.require_png)
            print(json.dumps({"status": "success", "json": str(graph_path), "svg": str(svg), "png": png_result}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "assemble":
            manifest = _read_json(args.diagram_manifest) if args.diagram_manifest else None
            if args.ssd_manifest:
                ssd_manifest = _read_json(args.ssd_manifest)
                if manifest and isinstance(manifest, dict) and isinstance(ssd_manifest, dict):
                    manifest = {**manifest, "use_cases": ssd_manifest.get("use_cases", manifest.get("use_cases", []))}
                else:
                    manifest = ssd_manifest
            model_value = _read_json(args.model)
            output_root = Path(args.output_dir).expanduser().resolve()
            output_root.mkdir(parents=True, exist_ok=True)
            normalized = validate_scene_model(model_value, raise_on_error=True)["normalized_model"]
            use_case_dependency = build_use_case_dependency_graph(normalized)
            normalized["use_case_dependency_graph"] = use_case_dependency
            composition_svg = render_system_composition_svg(normalized, output_root / "system_composition.svg")
            composition_png = convert_svg_to_png(composition_svg, output_root / "system_composition.png", require=args.require_png)
            composition_semantics = build_system_composition_semantics(normalized, "participation")
            _write_json(output_root / "system_composition.json", composition_semantics)
            dependency_composition_svg = render_system_composition_svg(normalized, output_root / "system_composition_dependencies.svg", view="dependencies")
            dependency_composition_png = convert_svg_to_png(dependency_composition_svg, output_root / "system_composition_dependencies.png", require=args.require_png)
            dependency_composition_semantics = build_system_composition_semantics(normalized, "dependencies")
            _write_json(output_root / "system_composition_dependencies.json", dependency_composition_semantics)
            use_case_dependency_json = output_root / "use_case_dependency_graph.json"
            _write_json(use_case_dependency_json, use_case_dependency)
            use_case_dependency_svg = render_use_case_dependency_svg(use_case_dependency, output_root / "use_case_dependency_graph.svg")
            use_case_dependency_png = convert_svg_to_png(use_case_dependency_svg, output_root / "use_case_dependency_graph.png", require=args.require_png)
            _write_json(output_root / "er_model.json", normalized.get("er_model", {}))
            _write_json(output_root / "use_case_entity_crud.json", {"entities": normalized.get("entities", []), "operations": normalized.get("use_case_entity_operations", [])})
            dependency = build_sr_service_dependency_graph(normalized, manifest)
            dependency_json = output_root / "sr_service_dependency_graph.json"
            _write_json(dependency_json, dependency)
            dependency_svg = render_sr_service_dependency_svg(dependency, output_root / "sr_service_dependency_graph.svg")
            dependency_png = convert_svg_to_png(dependency_svg, output_root / "sr_service_dependency_graph.png", require=args.require_png)
            manifest = dict(manifest or {})
            manifest["system_composition"] = {"json": str(output_root / "system_composition.json"), "svg": str(composition_svg), "png": composition_png.get("png", ""), "png_status": composition_png.get("status"), "view": "participation"}
            manifest["system_composition_dependencies"] = {"json": str(output_root / "system_composition_dependencies.json"), "svg": str(dependency_composition_svg), "png": dependency_composition_png.get("png", ""), "png_status": dependency_composition_png.get("status"), "view": "dependencies", "edge_count": len(use_case_dependency.get("edges", [])), "cycle_count": len(use_case_dependency.get("layout", {}).get("cycles", []))}
            manifest["use_case_dependency_graph"] = {"json": str(use_case_dependency_json), "svg": str(use_case_dependency_svg), "png": use_case_dependency_png.get("png", ""), "png_status": use_case_dependency_png.get("status"), "edge_count": len(use_case_dependency.get("edges", [])), "review_items": use_case_dependency.get("review_items", [])}
            manifest["sr_service_dependency_graph"] = {"json": str(dependency_json), "svg": str(dependency_svg), "png": dependency_png.get("png", ""), "png_status": dependency_png.get("status"), "edge_count": len(dependency.get("edges", [])), "review_items": dependency.get("review_items", [])}
            if args.require_png and manifest.get("use_cases"):
                missing = [
                    entry.get("use_case_id", "")
                    for entry in manifest["use_cases"]
                    if not Path((((entry.get("artifacts") or {}).get("fused") or {}).get("png", ""))).is_file()
                ]
                if missing:
                    raise ValidationFailure(["required fused SSD PNG artifacts missing for: " + ", ".join(missing)])
            source_documents = []
            for source_path in args.spec_document:
                path = Path(source_path).expanduser().resolve()
                source_documents.append({"path": str(path), "name": path.name, "text": path.read_text(encoding="utf-8")})
            bundle = assemble_results(model_value, _read_json(args.concern_matrix), _read_json(args.semantic_findings), manifest, source_documents)
            bundle["diagram_manifest"]["system_composition"] = manifest["system_composition"]
            bundle["diagram_manifest"]["system_composition_dependencies"] = manifest["system_composition_dependencies"]
            bundle["diagram_manifest"]["use_case_dependency_graph"] = manifest["use_case_dependency_graph"]
            bundle["scene_model"]["use_case_dependency_graph"] = use_case_dependency
            bundle["system_composition"] = composition_semantics
            bundle["system_composition"]["use_case_dependency_graph"] = use_case_dependency
            bundle["system_composition_dependencies"] = dependency_composition_semantics
            artifacts = export_workbooks(bundle, args.output_dir)
            print(json.dumps({"status": "success", "artifacts": artifacts}, ensure_ascii=False, indent=2))
            return 0
    except (ValidationFailure, FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 2


def main(argv=None) -> int:
    """Run a CLI stage and, when requested, persist privacy-safe timing metrics."""
    import time

    arguments = list(sys.argv[1:] if argv is None else argv)
    stage = arguments[0] if arguments else "unknown"
    metrics_dir = metrics_dir_from_argv(arguments)
    started = time.perf_counter()
    status = "failed"
    code = 2
    try:
        code = _main_impl(arguments)
        status = "success" if code == 0 else "failed"
        return code
    finally:
        if metrics_dir is not None:
            write_stage_metric(metrics_dir, stage, time.perf_counter() - started, status, arguments)
            if stage == "assemble" and code == 0:
                output_dirs = []
                for index, token in enumerate(arguments):
                    if token == "--output-dir" and index + 1 < len(arguments):
                        output_dirs.append(arguments[index + 1])
                    elif token.startswith("--output-dir="):
                        output_dirs.append(token.split("=", 1)[1])
                if output_dirs:
                    attach_metrics_to_run_manifest(output_dirs[-1], metrics_dir)


if __name__ == "__main__":
    raise SystemExit(main())
