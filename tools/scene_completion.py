#!/usr/bin/env python3
"""Agent-facing CLI for Scene Completion V2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scene_completion.assembly import assemble_results
from scene_completion.concerns import plan_concern_matrix, validate_concern_matrix
from scene_completion.diagrams import render_diagrams, validate_diagram_spec
from scene_completion.document_extract import extract_document
from scene_completion.exporters import export_workbooks
from scene_completion.knowledge import load_concern, load_diagram_knowledge, list_concerns, list_diagram_knowledge
from scene_completion.schemas import ValidationFailure, validate_scene_model


def _read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, value) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Portable Scene Completion V2 tools")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="extract text from a source document")
    extract.add_argument("--input", required=True)
    extract.add_argument("--output", required=True)
    validate = sub.add_parser("validate-model", help="validate and normalize scene_model.json")
    validate.add_argument("--input", required=True)
    sub.add_parser("list-concerns", help="list V2 concern definitions")
    load = sub.add_parser("load-concern", help="load one V2 concern reference")
    load.add_argument("--key", required=True)
    sub.add_parser("list-diagram-knowledge", help="list diagram-generation references")
    load_diagram = sub.add_parser("load-diagram-knowledge", help="load one diagram reference")
    load_diagram.add_argument("--key", required=True)
    plan = sub.add_parser("plan-concerns", help="create a full candidate concern matrix")
    plan.add_argument("--model", required=True)
    plan.add_argument("--output", required=True)
    validate_matrix = sub.add_parser("validate-concerns", help="validate a V2 concern matrix")
    validate_matrix.add_argument("--model", required=True)
    validate_matrix.add_argument("--input", required=True)
    validate_diagram = sub.add_parser("validate-diagrams", help="validate the two V2 diagram sources")
    validate_diagram.add_argument("--model", required=True)
    validate_diagram.add_argument("--input", required=True)
    render = sub.add_parser("render-diagrams", help="materialize and optionally render the two diagrams")
    render.add_argument("--model", required=True)
    render.add_argument("--input", required=True)
    render.add_argument("--output-dir", required=True)
    render.add_argument("--plantuml-jar")
    render.add_argument("--require-render", action="store_true")
    assemble = sub.add_parser("assemble", help="assemble V2 findings and export artifacts")
    assemble.add_argument("--model", required=True)
    assemble.add_argument("--concern-matrix", required=True)
    assemble.add_argument("--semantic-findings", required=True)
    assemble.add_argument("--diagram-manifest")
    assemble.add_argument("--output-dir", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            result = extract_document(args.input)
            _write_json(args.output, result)
            print(json.dumps({"status": "success", "output": str(Path(args.output).resolve())}, ensure_ascii=False))
            return 0
        if args.command == "validate-model":
            report = validate_scene_model(_read_json(args.input))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["valid"] else 2
        if args.command == "list-concerns":
            print(json.dumps({"version": "2", "concerns": list_concerns()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "load-concern":
            print(json.dumps(load_concern(args.key), ensure_ascii=False, indent=2))
            return 0
        if args.command == "list-diagram-knowledge":
            print(json.dumps({"version": "2", "references": list_diagram_knowledge()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "load-diagram-knowledge":
            print(json.dumps(load_diagram_knowledge(args.key), ensure_ascii=False, indent=2))
            return 0
        if args.command == "plan-concerns":
            result = plan_concern_matrix(_read_json(args.model))
            _write_json(args.output, result)
            print(json.dumps({"status": "success", "output": str(Path(args.output).resolve()), "count": len(result["items"])}, ensure_ascii=False))
            return 0
        if args.command == "validate-concerns":
            result = validate_concern_matrix(_read_json(args.model), _read_json(args.input))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        if args.command == "validate-diagrams":
            result = validate_diagram_spec(_read_json(args.model), _read_json(args.input))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] else 2
        if args.command == "render-diagrams":
            result = render_diagrams(_read_json(args.model), _read_json(args.input), args.output_dir, args.plantuml_jar, args.require_render)
            print(json.dumps({"status": "success", "manifest": result}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "assemble":
            manifest = _read_json(args.diagram_manifest) if args.diagram_manifest else None
            bundle = assemble_results(_read_json(args.model), _read_json(args.concern_matrix), _read_json(args.semantic_findings), manifest)
            artifacts = export_workbooks(bundle, args.output_dir)
            print(json.dumps({"status": "success", "artifacts": artifacts}, ensure_ascii=False, indent=2))
            return 0
    except (ValidationFailure, FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
