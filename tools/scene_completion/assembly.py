"""V2 concern-matrix validation, stable IDs, and scenario assembly."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from .concerns import CONCERN_DEFINITIONS, validate_concern_matrix
from .schemas import ValidationFailure, node_map, stable_id, use_case_map, validate_scene_model


def _finding_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict) and isinstance(value.get("findings"), list):
        return [item for item in value["findings"] if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise ValidationFailure(["semantic findings must be an object with findings or a list"])


def _scenario_steps(value: Any, index: int) -> list[str]:
    if not isinstance(value, list):
        raise ValidationFailure([f"finding {index}: scenario_steps must be a non-empty list"])
    result = []
    for item in value:
        text = item.get("text") if isinstance(item, dict) else item
        text = str(text or "").strip()
        if text:
            result.append(text)
    if not result:
        raise ValidationFailure([f"finding {index}: scenario_steps must be a non-empty list"])
    return result


def _stable_sort(item: dict[str, Any], interaction_order: dict[str, int]) -> tuple[Any, ...]:
    digest = hashlib.sha1(str(item.get("exception_desc", "")).encode("utf-8")).hexdigest()
    return (interaction_order.get(item.get("interaction_id"), 999999), item.get("concern_key", ""), digest)


def _normalize_findings(model: dict[str, Any], matrix_items: list[dict[str, Any]], raw_findings: Any) -> list[dict[str, Any]]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    nodes = node_map(normalized)
    interactions = {item["interaction_id"]: item for item in normalized["interactions"]}
    matrix = {(item["interaction_id"], item["concern_key"]): item for item in matrix_items}
    use_cases = use_case_map(normalized)
    findings = _finding_list(raw_findings)
    if not findings:
        findings = [finding for item in matrix_items if item.get("status") == "applicable" for finding in item.get("findings", []) if isinstance(finding, dict)]
    errors = []
    result = []
    for index, raw in enumerate(findings, 1):
        interaction_id = str(raw.get("interaction_id", "")).strip()
        concern_key = str(raw.get("concern_key", "")).strip()
        interaction = interactions.get(interaction_id)
        matrix_item = matrix.get((interaction_id, concern_key))
        if interaction is None:
            errors.append(f"finding {index}: unknown interaction_id {interaction_id}")
            continue
        if concern_key not in CONCERN_DEFINITIONS:
            errors.append(f"finding {index}: unknown concern_key {concern_key}")
            continue
        if matrix_item is None:
            errors.append(f"finding {index}: no concern matrix item for {interaction_id}/{concern_key}")
            continue
        if matrix_item.get("status") != "applicable":
            errors.append(f"finding {index}: findings require applicable status for {interaction_id}/{concern_key}")
            continue
        use_case_id = raw.get("use_case_id") or interaction.get("use_case_id")
        if use_case_id and use_case_id not in use_cases:
            errors.append(f"finding {index}: unknown use_case_id {use_case_id}")
            continue
        try:
            steps = _scenario_steps(raw.get("scenario_steps"), index)
        except ValidationFailure as exc:
            errors.extend(exc.errors)
            continue
        required = ["exception_desc", "trigger", "recovery"]
        missing = [key for key in required if not str(raw.get(key, "")).strip()]
        if missing:
            errors.append(f"finding {index}: missing {', '.join(missing)}")
            continue
        source = nodes[interaction["from_node"]]["name"]
        target = nodes[interaction["to_node"]]["name"]
        item = {
            "interaction_id": interaction_id,
            "use_case_id": use_case_id,
            "source_node": source,
            "target_node": target,
            "interaction_message": interaction["message"],
            "concern_key": concern_key,
            "concern": CONCERN_DEFINITIONS[concern_key]["label"],
            "basis": matrix_item.get("basis", ""),
            "exception_desc": str(raw["exception_desc"]).strip(),
            "actor": str(raw.get("actor") or source).strip(),
            "trigger": str(raw["trigger"]).strip(),
            "scenario_steps": steps,
            "recovery": str(raw["recovery"]).strip(),
            "entity_attribute": raw.get("entity_attribute"),
            "source_location": raw.get("source_location") or interaction.get("source_location", ""),
            "status": "applicable",
        }
        result.append(item)
    if errors:
        raise ValidationFailure(errors)
    return result


def _attach_ids(findings: list[dict[str, Any]], model: dict[str, Any]) -> None:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    order = {item["interaction_id"]: index for index, item in enumerate(normalized["interactions"], 1)}
    findings.sort(key=lambda item: _stable_sort(item, order))
    counts = defaultdict(int)
    for item in findings:
        base = stable_id("EXC", normalized["project"], item["interaction_id"], item["concern_key"], item["exception_desc"], item["trigger"])
        counts[base] += 1
        suffix = "" if counts[base] == 1 else f"-{counts[base]:02d}"
        item["exception_id"] = f"{base}{suffix}"
        item["prediction_id"] = item["exception_id"]
        item["scenario_id"] = item["exception_id"]


def _scenario_catalog(findings: list[dict[str, Any]], model: dict[str, Any], diagram_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    nodes = node_map(model)
    use_cases = use_case_map(model)
    artifacts = (diagram_manifest or {}).get("artifacts", [])
    result = []
    for item in findings:
        interaction = next(entry for entry in model["interactions"] if entry["interaction_id"] == item["interaction_id"])
        uc = use_cases.get(item.get("use_case_id"), {})
        diagram_paths = []
        for artifact in artifacts:
            if artifact.get("kind") in {"interaction_concern", "system_composition"}:
                path = artifact.get("svg") or artifact.get("png") or artifact.get("puml")
                if path:
                    diagram_paths.append(path)
        result.append({
            **item,
            "use_case_name": uc.get("use_case_name", ""),
            "preconditions": uc.get("preconditions", "未指定"),
            "postconditions": uc.get("postconditions", "未指定"),
            "api": interaction.get("api", ""),
            "diagram_paths": "\n".join(diagram_paths),
            "source_location": item.get("source_location") or uc.get("source_location", ""),
            "from_kind": nodes[interaction["from_node"]]["kind"],
            "to_kind": nodes[interaction["to_node"]]["kind"],
        })
    return result


def assemble_v2_results(
    model: dict[str, Any],
    concern_matrix: Any,
    semantic_findings: Any,
    diagram_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = validate_scene_model(model)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    normalized = report["normalized_model"]
    matrix_report = validate_concern_matrix(normalized, concern_matrix)
    if not matrix_report["valid"]:
        raise ValidationFailure(matrix_report["errors"])
    findings = _normalize_findings(normalized, matrix_report["items"], semantic_findings)
    _attach_ids(findings, normalized)
    scenarios = _scenario_catalog(findings, normalized, diagram_manifest)
    result_by_key = {key: [] for key in CONCERN_DEFINITIONS}
    for item in findings:
        result_by_key[item["concern_key"]].append(item)
    exception_tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in findings:
        uc_key = item.get("use_case_id") or "unassigned"
        exception_tree.setdefault(uc_key, {}).setdefault(item["interaction_id"], []).append(item)
    review_items = []
    for node in normalized["system_composition"]["nodes"]:
        if node.get("kind") == "internal_service" and node.get("service_type") == "unknown":
            review_items.append({"type": "service_type_confirmation", "node_id": node["node_id"], "message": f"请确认 Service《{node['name']}》属于展示型还是计算型。"})
    for item in matrix_report["items"]:
        if item.get("status") == "needs_requirement":
            review_items.append({"type": "concern_requirement_confirmation", "interaction_id": item["interaction_id"], "concern_key": item["concern_key"], "message": "需求文档不足以确定该关注点是否适用。"})
    return {
        "version": "2",
        "project": normalized["project"],
        "scene_model": normalized,
        "system_composition": normalized["system_composition"],
        "interaction_catalog": normalized["interactions"],
        "concern_matrix": matrix_report["items"],
        "checkpoint_results": result_by_key,
        "exception_tree": exception_tree,
        "scenario_catalog": scenarios,
        "review_items": review_items,
        "diagram_manifest": diagram_manifest or {"version": "2", "status": "skipped", "artifacts": []},
    }


def assemble_results(model: dict[str, Any], concern_matrix: Any, semantic_findings: Any, diagram_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Public V2 assembly entry point."""
    return assemble_v2_results(model, concern_matrix, semantic_findings, diagram_manifest)
