"""V5 diagram validation and dependency-free SVG rendering."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .schemas import ValidationFailure, validate_scene_model
from .svg_renderer import render_system_composition_svg
from .overview import build_system_composition_semantics
from .png_renderer import convert_svg_to_png
from .graphs import build_use_case_dependency_graph, render_use_case_dependency_svg


def _puml_check(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or "@startuml" not in value or "@enduml" not in value:
        return [f"{label}.puml must contain @startuml and @enduml"]
    return []


def _system_composition_arrow_errors(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    if "->" in value or "<-" in value:
        return ["system_composition_diagram.puml must use undirected '--' lines, not arrows"]
    return []


def _system_composition_display_errors(value: Any, nodes: list[dict[str, Any]]) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    missing = []
    for node in nodes:
        node_id = str(node.get("node_id", ""))
        name = str(node.get("name", ""))
        if node_id and node_id not in value and name and name not in value:
            missing.append(node_id)
    return [f"system composition diagram does not display node_ids: {', '.join(missing)}"] if missing else []


def validate_diagram_spec(model: dict[str, Any], spec: dict[str, Any], raise_on_error: bool = False) -> dict[str, Any]:
    model_report = validate_scene_model(model)
    errors = list(model_report.get("errors", []))
    warnings = list(model_report.get("warnings", []))
    normalized = model_report.get("normalized_model", model)
    if not isinstance(spec, dict):
        errors.append("diagram spec must be an object")
        result = {"valid": False, "errors": errors, "warnings": warnings}
        if raise_on_error:
            raise ValidationFailure(errors)
        return result
    if str(spec.get("version", "5")) not in {"4", "5"}:
        errors.append("diagram spec version must be 4 or 5")
    for key, label in (("system_composition_diagram", "system_composition_diagram"),):
        diagram = spec.get(key)
        if not isinstance(diagram, dict):
            errors.append(f"{key} must be an object")
            continue
        if diagram.get("puml"):
            errors.extend(_puml_check(diagram.get("puml"), label))
        if key == "system_composition_diagram":
            errors.extend(_system_composition_arrow_errors(diagram.get("puml")))
            errors.extend(_system_composition_display_errors(diagram.get("puml"), normalized.get("system_composition", {}).get("nodes", [])))
    if isinstance(spec.get("interaction_concern_diagram"), dict):
        if spec["interaction_concern_diagram"].get("puml"):
            errors.extend(_puml_check(spec["interaction_concern_diagram"].get("puml"), "interaction_concern_diagram"))
    if isinstance(spec.get("use_case_diagram"), dict):
        if spec["use_case_diagram"].get("puml"):
            errors.extend(_puml_check(spec["use_case_diagram"].get("puml"), "use_case_diagram"))
    node_ids = {node["node_id"] for node in normalized.get("system_composition", {}).get("nodes", [])}
    interaction_ids = {item["interaction_id"] for item in normalized.get("interactions", [])}
    declared_nodes = set(spec.get("system_composition_diagram", {}).get("node_ids", node_ids))
    declared_interactions = set(spec.get("interaction_concern_diagram", {}).get("interaction_ids", interaction_ids))
    unknown_nodes = sorted(declared_nodes - node_ids)
    unknown_interactions = sorted(declared_interactions - interaction_ids)
    missing_nodes = sorted(node_ids - declared_nodes)
    missing_interactions = sorted(interaction_ids - declared_interactions)
    if unknown_nodes:
        errors.append(f"diagram spec references unknown node_ids: {', '.join(unknown_nodes)}")
    if unknown_interactions:
        errors.append(f"diagram spec references unknown interaction_ids: {', '.join(unknown_interactions)}")
    if missing_nodes:
        errors.append(f"system composition diagram is missing node_ids: {', '.join(missing_nodes)}")
    if missing_interactions:
        errors.append(f"interaction concern diagram is missing interaction_ids: {', '.join(missing_interactions)}")
    if isinstance(spec.get("use_case_diagram"), dict):
        use_case_ids = {uc.get("use_case_id") for uc in normalized.get("use_cases", [])}
        declared_use_cases = set(spec["use_case_diagram"].get("use_case_ids", use_case_ids))
        unknown_use_cases = sorted(declared_use_cases - use_case_ids)
        missing_use_cases = sorted(use_case_ids - declared_use_cases)
        if unknown_use_cases:
            errors.append(f"use case diagram references unknown use_case_ids: {', '.join(unknown_use_cases)}")
        if missing_use_cases:
            errors.append(f"use case diagram is missing use_case_ids: {', '.join(missing_use_cases)}")
    ssd_artifacts = spec.get("ssd_artifacts", [])
    if ssd_artifacts is not None and not isinstance(ssd_artifacts, list):
        errors.append("ssd_artifacts must be a list")
    seen_ssd = set()
    for index, artifact in enumerate(ssd_artifacts or [], 1):
        if not isinstance(artifact, dict):
            errors.append(f"ssd_artifacts[{index}] must be an object")
            continue
        use_case_id = artifact.get("use_case_id")
        if use_case_id not in {uc.get("use_case_id") for uc in normalized.get("use_cases", [])}:
            errors.append(f"ssd_artifacts[{index}] references unknown use_case_id: {use_case_id}")
        key = (use_case_id, artifact.get("scenario_id", "main"))
        if key in seen_ssd:
            errors.append(f"duplicate ssd artifact: {key[0]}/{key[1]}")
        seen_ssd.add(key)
        if artifact.get("fused_puml"):
            errors.extend(_puml_check(artifact.get("fused_puml"), f"ssd_artifacts[{index}].fused_puml"))
    result = {"valid": not errors, "errors": errors, "warnings": warnings, "normalized_model": normalized}
    if raise_on_error and errors:
        raise ValidationFailure(errors)
    return result


def find_plantuml_jar(explicit: str | Path | None = None) -> Path | None:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("PLANTUML_JAR"):
        candidates.append(Path(os.environ["PLANTUML_JAR"]).expanduser())
    package_root = Path(__file__).resolve().parents[2]
    candidates.extend(sorted((package_root / "scripts" / "assets").glob("plantuml*.jar")))
    return next((path.resolve() for path in candidates if path.is_file()), None)


def render_diagrams(model: dict[str, Any], spec: dict[str, Any], output_dir: str | Path, plantuml_jar: str | Path | None = None, require_render: bool = False, require_png: bool = False) -> dict[str, Any]:
    report = validate_diagram_spec(model, spec)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_specs = []
    if spec.get("system_composition_diagram", {}).get("puml"):
        source_specs.append(("system_composition", spec["system_composition_diagram"]["puml"]))
    if isinstance(spec.get("interaction_concern_diagram"), dict) and spec["interaction_concern_diagram"].get("puml"):
        source_specs.append(("interaction_concern", spec["interaction_concern_diagram"]["puml"]))
    if isinstance(spec.get("use_case_diagram"), dict) and spec["use_case_diagram"].get("puml"):
        source_specs.append(("use_case", spec["use_case_diagram"]["puml"]))
    records, puml_paths = [], []
    for kind, puml in source_specs:
        path = output / f"{kind}.puml"
        path.write_text(puml.strip() + "\n", encoding="utf-8")
        puml_paths.append(path)
        records.append({"kind": kind, "puml": str(path), "svg": "", "png": "", "rendered": False, "source_location": spec.get(f"{kind}_diagram", {}).get("source_location", "")})
    # SVG is the default and requires only the Python standard library.
    overview_svg = output / "system_composition.svg"
    # Always render the canonical normalized model.  Validation may synthesize
    # one RR abstract service per use case; using the raw input here silently
    # dropped those services from the overview on another machine.
    normalized = report["normalized_model"]
    dependency_graph = build_use_case_dependency_graph(normalized)
    normalized["use_case_dependency_graph"] = dependency_graph
    render_system_composition_svg(normalized, overview_svg)
    overview_png = output / "system_composition.png"
    overview_png_result = convert_svg_to_png(overview_svg, overview_png, require=require_png)
    overview_json = output / "system_composition.json"
    overview_json.write_text(json.dumps(build_system_composition_semantics(normalized, "participation"), ensure_ascii=False, indent=2), encoding="utf-8")
    dependency_composition_svg = render_system_composition_svg(normalized, output / "system_composition_dependencies.svg", view="dependencies")
    dependency_composition_png_result = convert_svg_to_png(dependency_composition_svg, output / "system_composition_dependencies.png", require=require_png)
    dependency_composition_json = output / "system_composition_dependencies.json"
    dependency_composition_json.write_text(json.dumps(build_system_composition_semantics(normalized, "dependencies"), ensure_ascii=False, indent=2), encoding="utf-8")
    dependency_json = output / "use_case_dependency_graph.json"
    dependency_json.write_text(json.dumps(dependency_graph, ensure_ascii=False, indent=2), encoding="utf-8")
    dependency_svg = render_use_case_dependency_svg(dependency_graph, output / "use_case_dependency_graph.svg")
    dependency_png_result = convert_svg_to_png(dependency_svg, output / "use_case_dependency_graph.png", require=require_png)
    records.insert(0, {"kind": "system_composition_dependencies", "json": str(dependency_composition_json), "svg": str(dependency_composition_svg), "png": dependency_composition_png_result.get("png", ""), "png_status": dependency_composition_png_result.get("status"), "rendered": True})
    records.insert(0, {"kind": "system_composition", "json": str(overview_json), "svg": str(overview_svg), "png": overview_png_result.get("png", ""), "png_status": overview_png_result.get("status"), "png_converter": overview_png_result.get("converter", ""), "png_error": overview_png_result.get("error", ""), "rendered": True, "source_location": spec.get("system_composition_diagram", {}).get("source_location", "")})
    jar = find_plantuml_jar(plantuml_jar)
    status, error = "rendered", ""
    if jar and shutil.which("java"):
        failures = []
        for fmt in ("svg", "png"):
            command = ["java", "-Djava.awt.headless=true", "-jar", str(jar), f"-t{fmt}", *(str(path) for path in puml_paths)]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode:
                failures.append(f"{fmt}: {completed.stderr.strip()[:1000]}")
        if failures:
            status, error = "render_failed", " | ".join(failures)
    if require_render and status != "rendered":
        raise RuntimeError(error)
    for record in records:
        if not record.get("puml"):
            continue
        puml = Path(record["puml"])
        svg, png = puml.with_suffix(".svg"), puml.with_suffix(".png")
        record["svg"] = str(svg) if svg.exists() else ""
        record["png"] = str(png) if png.exists() else ""
        record["rendered"] = bool(record["svg"] and record["png"])
    manifest = {"version": str(normalized.get("version", "10")), "project": spec.get("project") or normalized.get("project"), "status": status, "error": error, "png_status": overview_png_result.get("status"), "png_converter": overview_png_result.get("converter", ""), "png_error": overview_png_result.get("error", ""), "artifacts": records, "system_composition": {"json": str(overview_json), "svg": str(overview_svg), "png": overview_png_result.get("png", ""), "view": "participation"}, "system_composition_dependencies": {"json": str(dependency_composition_json), "svg": str(dependency_composition_svg), "png": dependency_composition_png_result.get("png", ""), "view": "dependencies", "edge_count": len(dependency_graph.get("edges", [])), "cycle_count": len(dependency_graph.get("layout", {}).get("cycles", []))}, "use_case_dependency_graph": {"json": str(dependency_json), "svg": str(dependency_svg), "png": dependency_png_result.get("png", ""), "edge_count": len(dependency_graph.get("edges", [])), "review_items": dependency_graph.get("review_items", [])}, "node_ids": sorted({node["node_id"] for node in normalized["system_composition"]["nodes"]}), "interaction_ids": sorted({item["interaction_id"] for item in normalized["interactions"]})}
    manifest_path = output / "diagram_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    return manifest


def write_diagram_manifest(manifest: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
