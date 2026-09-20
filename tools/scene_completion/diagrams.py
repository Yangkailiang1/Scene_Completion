"""V2 two-diagram validation and PlantUML rendering."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .schemas import ValidationFailure, validate_scene_model


def _puml_check(value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or "@startuml" not in value or "@enduml" not in value:
        return [f"{label}.puml must contain @startuml and @enduml"]
    return []


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
    if spec.get("version", "2") != "2":
        errors.append("diagram spec version must be 2")
    for key, label in (("system_composition_diagram", "system_composition_diagram"), ("interaction_concern_diagram", "interaction_concern_diagram")):
        diagram = spec.get(key)
        if not isinstance(diagram, dict):
            errors.append(f"{key} must be an object")
            continue
        errors.extend(_puml_check(diagram.get("puml"), label))
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
    candidates.extend(sorted((package_root / "tools").glob("plantuml*.jar")))
    return next((path.resolve() for path in candidates if path.is_file()), None)


def render_diagrams(model: dict[str, Any], spec: dict[str, Any], output_dir: str | Path, plantuml_jar: str | Path | None = None, require_render: bool = False) -> dict[str, Any]:
    report = validate_diagram_spec(model, spec)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_specs = [
        ("system_composition", spec["system_composition_diagram"]["puml"]),
        ("interaction_concern", spec["interaction_concern_diagram"]["puml"]),
    ]
    records, puml_paths = [], []
    for kind, puml in source_specs:
        path = output / f"{kind}.puml"
        path.write_text(puml.strip() + "\n", encoding="utf-8")
        puml_paths.append(path)
        records.append({"kind": kind, "puml": str(path), "svg": "", "png": "", "rendered": False, "source_location": spec.get(f"{kind}_diagram", {}).get("source_location", "")})
    jar = find_plantuml_jar(plantuml_jar)
    status, error = "puml_only", "PlantUML JAR or java executable not found"
    if jar and shutil.which("java"):
        failures = []
        for fmt in ("svg", "png"):
            command = ["java", "-jar", str(jar), f"-t{fmt}", *(str(path) for path in puml_paths)]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode:
                failures.append(f"{fmt}: {completed.stderr.strip()[:1000]}")
        if failures:
            status, error = "render_failed", " | ".join(failures)
        else:
            status, error = "rendered", ""
    if require_render and status != "rendered":
        raise RuntimeError(error)
    for record in records:
        puml = Path(record["puml"])
        svg, png = puml.with_suffix(".svg"), puml.with_suffix(".png")
        record["svg"] = str(svg) if svg.exists() else ""
        record["png"] = str(png) if png.exists() else ""
        record["rendered"] = bool(record["svg"] and record["png"])
    manifest = {"version": "2", "project": spec.get("project") or model.get("project"), "status": status, "error": error, "artifacts": records, "node_ids": sorted({node["node_id"] for node in model["system_composition"]["nodes"]}), "interaction_ids": sorted({item["interaction_id"] for item in model["interactions"]})}
    manifest_path = output / "diagram_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest"] = str(manifest_path)
    return manifest


def write_diagram_manifest(manifest: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
