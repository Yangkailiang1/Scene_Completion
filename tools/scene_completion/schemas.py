"""Scene Completion V5 scene, layered architecture, and source contracts."""

from __future__ import annotations

import copy
import hashlib
from typing import Any


NODE_KINDS = {
    "human_actor", "external_actor", "connection_device", "internal_service",
    "internal_database", "internal_knowledge_base", "external_service",
    "external_database", "external_llm", "deployment_hardware", "runtime_environment",
    "abstract_service", "implementation_api",
}
LAYERS = {"RR", "SR", "AR"}
SERVICE_TYPES = {
    "display_interaction", "query_retrieval", "resource_mutation",
    "analysis_generation", "release_activation", "unknown",
    # Accepted at the input boundary for V5 migration.
    "display", "compute",
}
CLASSIFICATION_STATUS = {"confirmed", "inferred", "needs_confirmation"}
INTERACTION_DIRECTIONS = {"incoming", "outgoing", "internal"}
CONCERN_STATUSES = {"pending_review", "applicable", "not_applicable", "needs_requirement"}


class ValidationFailure(ValueError):
    """Raised when a public V2 contract is invalid."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(_text(part) for part in parts)
    return f"{prefix}-{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:10].upper()}"


def _step_text(step: Any) -> str:
    if isinstance(step, dict):
        return _text(step.get("text") or step.get("description"))
    return _text(step)


def normalize_steps(steps: Any) -> list[dict[str, Any]]:
    if steps is None:
        return []
    if not isinstance(steps, list):
        raise ValidationFailure(["main_flow/alternative_flow must be a list"])
    result = []
    for index, raw in enumerate(steps, 1):
        item = dict(raw) if isinstance(raw, dict) else {}
        text = _step_text(raw)
        if not text:
            raise ValidationFailure([f"empty step at index {index}"])
        try:
            step_index = int(item.get("step_index", index))
        except (TypeError, ValueError):
            raise ValidationFailure([f"invalid step_index at index {index}"])
        if step_index < 1:
            raise ValidationFailure([f"step_index must be >= 1 at index {index}"])
        item.update({"step_index": step_index, "text": text})
        if item.get("direction") not in {"input", "output"}:
            item.pop("direction", None)
        result.append(item)
    return result


def _anchor_value(value: Any) -> int:
    """Accept ``4`` and branch anchors such as ``4.a`` while validating the main step."""
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        text = _text(value)
        prefix = text.split(".", 1)[0]
        try:
            return int(prefix)
        except ValueError:
            raise ValidationFailure([f"invalid anchor_step_index: {value}"])


def _normalize_scenarios(value: Any, use_case_id: str, main_flow: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None:
        return [{"scenario_id": f"{use_case_id}-main", "scenario_type": "main", "name": "主成功场景", "anchor_step_index": 0, "steps": copy.deepcopy(main_flow)}]
    if not isinstance(value, list):
        raise ValidationFailure([f"{use_case_id}.scenarios must be a list"])
    result = []
    for index, raw in enumerate(value, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"{use_case_id}.scenarios[{index}] must be an object"])
        item = dict(raw)
        anchor = _anchor_value(item.get("anchor_step_index", 0))
        scenario_type = _text(item.get("scenario_type"), "alternative")
        if scenario_type == "main":
            anchor = 0
        item.update({
            "scenario_id": _text(item.get("scenario_id"), f"{use_case_id}-scenario-{index:02d}"),
            "scenario_type": scenario_type,
            "name": _text(item.get("name"), f"场景 {index}"),
            "anchor_step_index": anchor,
            "anchor_label": _text(item.get("anchor_label"), str(item.get("anchor_step_index", anchor))),
            "steps": normalize_steps(item.get("steps", item.get("flow", []))),
            "source_type": _text(item.get("source_type"), "requirements"),
            "source_location": _text(item.get("source_location")),
            "trigger": _text(item.get("trigger")),
            "expected_result": _text(item.get("expected_result")),
            "recovery": _text(item.get("recovery")),
        })
        result.append(item)
    return result


def _normalize_interfaces(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailure(["interfaces must be a list"])
    result = []
    for index, raw in enumerate(value, 1):
        item = dict(raw) if isinstance(raw, dict) else {}
        name = _text(item.get("name") or item.get("id") or raw)
        if not name:
            raise ValidationFailure([f"interfaces[{index}] needs a name"])
        item["name"] = name
        result.append(item)
    return result


def _kind_scope(kind: str) -> str:
    return "external" if kind in {"human_actor", "external_actor", "external_service", "external_database", "external_llm"} else "internal"


def _default_layer(kind: str) -> str:
    if kind in {"external_service", "external_database", "external_llm"}:
        return "SR"
    if kind in {"internal_database", "internal_knowledge_base", "implementation_api", "internal_service"}:
        return "AR"
    if kind == "abstract_service":
        return "RR"
    return "RR"


def _normalize_nodes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValidationFailure(["system_composition.nodes must be a list"])
    result, seen = [], set()
    for index, raw in enumerate(value, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"system_composition.nodes[{index}] must be an object"])
        item = dict(raw)
        kind, name = _text(item.get("kind")), _text(item.get("name"))
        if kind not in NODE_KINDS:
            raise ValidationFailure([f"node {name or index} has invalid kind: {kind}"])
        if not name:
            raise ValidationFailure([f"system_composition.nodes[{index}] needs name"])
        node_id = _text(item.get("node_id") or item.get("id"), stable_id("NODE", kind, name))
        if node_id in seen:
            raise ValidationFailure([f"duplicate node_id: {node_id}"])
        seen.add(node_id)
        item.update({"node_id": node_id, "name": name, "kind": kind})
        item.setdefault("scope", _kind_scope(kind))
        layer = _text(item.get("layer"), _default_layer(kind))
        if layer not in LAYERS:
            raise ValidationFailure([f"node {node_id} has invalid layer: {layer}"])
        item["layer"] = layer
        if kind == "internal_service":
            service_type = _text(item.get("service_type"), "unknown")
            if service_type not in SERVICE_TYPES:
                raise ValidationFailure([f"node {node_id} has invalid service_type: {service_type}"])
            if service_type == "display":
                service_type = "display_interaction"
                item.setdefault("legacy_service_type", "display")
            elif service_type == "compute":
                service_type = "unknown"
                item.setdefault("legacy_service_type", "compute")
            item["service_type"] = service_type
            item["classification_status"] = _text(item.get("classification_status"), "needs_confirmation" if service_type == "unknown" else "inferred")
            if item["classification_status"] not in CLASSIFICATION_STATUS:
                raise ValidationFailure([f"node {node_id} has invalid classification_status"])
        if kind == "abstract_service":
            item["use_case_id"] = _text(item.get("use_case_id"))
            if not item["use_case_id"]:
                raise ValidationFailure([f"abstract service {node_id} needs use_case_id"])
        result.append(item)
    return result


def actor_records(model: dict[str, Any]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw in model.get("actors", []) if isinstance(model.get("actors", []), list) else []:
        raw = {"name": raw} if isinstance(raw, str) else raw
        if not isinstance(raw, dict):
            continue
        name = _text(raw.get("name"))
        if name:
            records[name] = dict(raw)
    for uc in model.get("use_cases", []):
        for name in uc.get("actors", []):
            records.setdefault(name, {"name": name})
    for name, record in records.items():
        category = _text(record.get("category")).lower()
        if category not in {"human", "non_human"}:
            category = "human" if any(token in name.lower() for token in ("user", "用户", "顾客", "管理员", "admin")) else "non_human"
        record.update({"name": name, "category": category})
    return list(records.values())


def _derive_nodes(data: dict[str, Any], use_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = [{"node_id": "system", "name": data["system_name"], "kind": "internal_service", "service_type": "unknown", "classification_status": "needs_confirmation"}]
    seen = {"system"}
    for actor in actor_records({**data, "use_cases": use_cases}):
        node_id = stable_id("NODE", actor["name"])
        if node_id in seen:
            continue
        kind = "human_actor" if actor["category"] == "human" else "external_actor"
        nodes.append({"node_id": node_id, "name": actor["name"], "kind": kind, "scope": "external"})
        seen.add(node_id)
    return nodes


def _normalize_edges(value: Any, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailure(["system_composition.edges must be a list"])
    ids = {node["node_id"] for node in nodes}
    names = {node["name"]: node["node_id"] for node in nodes}
    result, seen = [], set()
    for index, raw in enumerate(value, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"system_composition.edges[{index}] must be an object"])
        item = dict(raw)
        source = names.get(_text(item.get("from_node") or item.get("from")), _text(item.get("from_node") or item.get("from")))
        target = names.get(_text(item.get("to_node") or item.get("to")), _text(item.get("to_node") or item.get("to")))
        if source not in ids or target not in ids:
            raise ValidationFailure([f"edge {index} references unknown node"])
        edge_id = _text(item.get("edge_id") or item.get("id"), stable_id("EDGE", source, target, item.get("relation", index)))
        if edge_id in seen:
            raise ValidationFailure([f"duplicate edge_id: {edge_id}"])
        seen.add(edge_id)
        item.update({"edge_id": edge_id, "from_node": source, "to_node": target})
        result.append(item)
    return result


def _normalize_interactions(value: Any, model: dict[str, Any], nodes: list[dict[str, Any]], use_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValidationFailure(["interactions must be a list"])
    ids = {node["node_id"] for node in nodes}
    names = {node["name"]: node["node_id"] for node in nodes}
    uc_ids = {uc["use_case_id"] for uc in use_cases}
    result, seen = [], set()
    for index, raw in enumerate(value, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"interactions[{index}] must be an object"])
        item = dict(raw)
        source_name = _text(item.get("from_node") or item.get("from"))
        target_name = _text(item.get("to_node") or item.get("to"))
        source, target = names.get(source_name, source_name), names.get(target_name, target_name)
        if source not in ids or target not in ids:
            raise ValidationFailure([f"interaction {index} references unknown node"])
        direction = _text(item.get("direction"), "internal")
        if direction not in INTERACTION_DIRECTIONS:
            raise ValidationFailure([f"interaction {index} has invalid direction: {direction}"])
        try:
            source_step = int(item.get("source_step_index", 0))
            sequence = int(item.get("sequence", index))
        except (TypeError, ValueError):
            raise ValidationFailure([f"interaction {index} has invalid sequence or source_step_index"])
        message = _text(item.get("message"), "未命名交互")
        use_case_id = _text(item.get("use_case_id")) or None
        if use_case_id and use_case_id not in uc_ids:
            raise ValidationFailure([f"interaction {index} references unknown use_case_id: {use_case_id}"])
        interaction_id = _text(item.get("interaction_id") or item.get("id"), stable_id("INT", model["project"], use_case_id, source, target, message, item.get("api"), source_step))
        if interaction_id in seen:
            raise ValidationFailure([f"duplicate interaction_id: {interaction_id}"])
        seen.add(interaction_id)
        item.update({"interaction_id": interaction_id, "from_node": source, "to_node": target, "direction": direction, "message": message, "source_step_index": source_step, "sequence": sequence, "use_case_id": use_case_id, "source_location": _text(item.get("source_location"))})
        for field in ("layer", "ssd_id", "interface_id", "abstract_api_id", "implementation_api_id", "service_id", "api_method", "resource_path", "ar_mapping_status"):
            if field in item and item[field] is not None:
                item[field] = _text(item[field])
        for field in ("request_fields", "response_fields"):
            if field in item and item[field] is not None and not isinstance(item[field], list):
                raise ValidationFailure([f"interaction {interaction_id} {field} must be a list"])
        result.append(item)
    return result


def normalize_model(model: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise ValidationFailure(["scene model must be an object"])
    data = copy.deepcopy(model)
    data["version"] = _text(data.get("version"), "6")
    data["project"] = _text(data.get("project"), "scene_completion")
    data["system_name"] = _text(data.get("system_name"), data["project"])
    data.setdefault("source", {})
    data.setdefault("actors", [])
    data.setdefault("entities", [])
    data.setdefault("er_model", {})
    data.setdefault("interfaces", [])
    data.setdefault("use_cases", [])
    normalized_ucs = []
    for position, raw_uc in enumerate(data["use_cases"], 1):
        if not isinstance(raw_uc, dict):
            raise ValidationFailure([f"use_cases[{position}] must be an object"])
        uc = dict(raw_uc)
        uc["use_case_id"] = _text(uc.get("use_case_id"), f"UC-{position:03d}")
        uc["use_case_name"] = _text(uc.get("use_case_name"), uc["use_case_id"])
        actors = uc.get("actors", [])
        actors = [actors] if isinstance(actors, str) else actors
        uc["actors"] = [_text(actor) for actor in actors if _text(actor)]
        uc["preconditions"] = _text(uc.get("preconditions"), "未指定")
        uc["postconditions"] = _text(uc.get("postconditions"), "未指定")
        uc["main_flow"] = normalize_steps(uc.get("main_flow", []))
        uc["alternative_flow"] = normalize_steps(uc.get("alternative_flow", []))
        extension_flows = uc.get("extension_flows", [])
        if extension_flows is None:
            extension_flows = []
        if not isinstance(extension_flows, list):
            raise ValidationFailure([f"{uc['use_case_id']}.extension_flows must be a list"])
        uc["extension_flows"] = [dict(flow) for flow in extension_flows if isinstance(flow, dict)]
        trigger = _text(uc.get("trigger"))
        uc["trigger_inferred"] = not bool(trigger)
        uc["trigger"] = trigger or (uc["main_flow"][0]["text"] if uc["main_flow"] else "未明确")
        uc["scenarios"] = _normalize_scenarios(uc.get("scenarios"), uc["use_case_id"], uc["main_flow"])
        architecture = uc.get("architecture") or uc.get("layer_mapping") or {}
        if not isinstance(architecture, dict):
            raise ValidationFailure([f"{uc['use_case_id']}.architecture must be an object"])
        uc["architecture"] = copy.deepcopy(architecture)
        normalized_ucs.append(uc)
    data["use_cases"] = normalized_ucs
    data["entities"] = [_text(entity) for entity in data.get("entities", []) if _text(entity)]
    data["interfaces"] = _normalize_interfaces(data.get("interfaces"))
    composition = data.get("system_composition") or {}
    if not isinstance(composition, dict):
        raise ValidationFailure(["system_composition must be an object"])
    raw_nodes = composition.get("nodes")
    nodes = _normalize_nodes(raw_nodes) if raw_nodes is not None else _derive_nodes(data, normalized_ucs)
    composition["nodes"] = nodes
    existing_abstract = {node.get("use_case_id") for node in nodes if node.get("kind") == "abstract_service" and node.get("layer", "RR") == "RR"}
    for uc in normalized_ucs:
        if uc["use_case_id"] not in existing_abstract:
            nodes.append({
                "node_id": stable_id("ABSTRACT", data["project"], uc["use_case_id"]),
                "name": f"{uc['use_case_name']}抽象服务",
                "kind": "abstract_service",
                "layer": "RR",
                "use_case_id": uc["use_case_id"],
                "scope": "internal",
                "classification_status": "inferred",
                "source_location": uc.get("source_location", ""),
            })
    abstract_use_cases = set()
    known_use_cases = {uc["use_case_id"] for uc in normalized_ucs}
    for node in nodes:
        if node.get("kind") != "abstract_service":
            continue
        use_case_id = node.get("use_case_id")
        if use_case_id not in known_use_cases:
            raise ValidationFailure([f"abstract service {node['node_id']} references unknown use_case_id: {use_case_id}"])
        if node.get("layer", "RR") == "RR" and use_case_id in abstract_use_cases:
            raise ValidationFailure([f"duplicate abstract_service for use_case_id: {use_case_id}"])
        if node.get("layer", "RR") == "RR":
            abstract_use_cases.add(use_case_id)
    composition["edges"] = _normalize_edges(composition.get("edges"), nodes)
    data["system_composition"] = composition
    data["interactions"] = _normalize_interactions(data.get("interactions"), data, nodes, normalized_ucs)
    if not isinstance(data.get("concern_matrix", []), list):
        raise ValidationFailure(["concern_matrix must be a list"])
    return data


def use_case_map(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {uc["use_case_id"]: uc for uc in model.get("use_cases", [])}


def node_map(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["node_id"]: node for node in model.get("system_composition", {}).get("nodes", [])}


def interaction_has_api(interaction: dict[str, Any]) -> bool:
    return any(str(interaction.get(field, "")).strip() for field in (
        "api", "interface_id", "abstract_api_id", "implementation_api_id", "api_method", "resource_path"
    ))


def validate_scene_model(model: dict[str, Any], raise_on_error: bool = False) -> dict[str, Any]:
    errors, warnings = [], []
    try:
        normalized = normalize_model(model)
    except ValidationFailure as exc:
        report = {"valid": False, "errors": exc.errors, "warnings": []}
        if raise_on_error:
            raise
        return report
    if not normalized["use_cases"]:
        errors.append("use_cases must not be empty")
    seen_ucs = set()
    for uc in normalized["use_cases"]:
        uid = uc["use_case_id"]
        if uid in seen_ucs:
            errors.append(f"duplicate use_case_id: {uid}")
        seen_ucs.add(uid)
        if not uc["actors"]:
            warnings.append(f"{uid} has no actors")
        if not uc["main_flow"]:
            errors.append(f"{uid} has no main_flow")
        if str(normalized.get("version")) in {"3", "4", "5", "6"}:
            main_scenarios = [scenario for scenario in uc.get("scenarios", []) if scenario.get("scenario_type") == "main"]
            if len(main_scenarios) != 1:
                errors.append(f"{uid} must have exactly one main_success scenario")
        if uc.get("trigger_inferred"):
            warnings.append(f"{uid} trigger was inferred")
        scenario_ids = set()
        main_indexes = {step["step_index"] for step in uc["main_flow"]}
        for scenario in uc["scenarios"]:
            sid = scenario["scenario_id"]
            if sid in scenario_ids:
                errors.append(f"duplicate scenario_id in {uid}: {sid}")
            scenario_ids.add(sid)
            anchor = scenario["anchor_step_index"]
            if anchor < 0 or (main_indexes and anchor not in ({0} | main_indexes)):
                errors.append(f"{uid}/{sid} anchor_step_index outside main_flow")
            if scenario.get("scenario_type") not in {"main", "main_success", "alternative", "requirement_exception", "concern_derived_exception"}:
                errors.append(f"{uid}/{sid} has invalid scenario_type: {scenario.get('scenario_type')}")
    node_ids = {node["node_id"] for node in normalized["system_composition"]["nodes"]}
    system_names = {node.get("name") for node in normalized["system_composition"]["nodes"] if node.get("node_id") == "system" or node.get("kind") == "internal_service" and node.get("name") == normalized.get("system_name")}
    for uc in normalized["use_cases"]:
        invalid_actors = sorted(set(uc.get("actors", [])) & system_names)
        if invalid_actors:
            errors.append(f"{uc['use_case_id']} uses system node as Actor: {', '.join(invalid_actors)}")
    for interaction in normalized["interactions"]:
        if interaction["from_node"] not in node_ids or interaction["to_node"] not in node_ids:
            errors.append(f"interaction {interaction['interaction_id']} references unknown node")
    if str(normalized.get("version")) in {"4", "5", "6"}:
        nodes_by_id = node_map(normalized)
        for uc in normalized["use_cases"]:
            architecture = uc.get("architecture") or {}
            rr = architecture.get("rr") or {}
            sr = architecture.get("sr") or {}
            ar = architecture.get("ar") or []
            for section, value, required in (
                ("rr", rr, ("service_id", "service_name", "abstract_api_id")),
                ("sr", sr, ("design_use_case_id", "service_id", "service_name", "abstract_api_id")),
            ):
                if not isinstance(value, dict):
                    errors.append(f"{uc['use_case_id']}.architecture.{section} must be an object")
                    continue
                for field in required:
                    if not _text(value.get(field)):
                        errors.append(f"{uc['use_case_id']}.architecture.{section} needs {field}")
                service_id = _text(value.get("service_id"))
                if service_id and service_id in nodes_by_id and nodes_by_id[service_id].get("layer") not in {"RR", "SR"}:
                    errors.append(f"{uc['use_case_id']}.architecture.{section}.service_id must reference RR/SR node")
            if not isinstance(ar, list):
                errors.append(f"{uc['use_case_id']}.architecture.ar must be a list")
            for index, component in enumerate(ar if isinstance(ar, list) else [], 1):
                if not isinstance(component, dict):
                    errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] must be an object")
                    continue
                for field in ("microservice_id", "microservice_name", "implementation_api_id", "software_interface"):
                    if not _text(component.get(field)):
                        errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] needs {field}")
                node_id = _text(component.get("microservice_id"))
                if node_id and node_id in nodes_by_id and nodes_by_id[node_id].get("layer") != "AR":
                    errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] microservice must be AR")
    if not normalized["interactions"]:
        warnings.append("no interactions were extracted")
    report = {"valid": not errors, "errors": errors, "warnings": warnings, "normalized_model": normalized}
    if raise_on_error and errors:
        raise ValidationFailure(errors)
    return report


def _entity_attributes(model: dict[str, Any]) -> dict[str, set[str]]:
    er = model.get("er_model") or {}
    er = er.get("final_er_model", er) if isinstance(er, dict) else {}
    result = {}
    for entity in er.get("entities", []) if isinstance(er, dict) else []:
        if isinstance(entity, dict):
            name = _text(entity.get("name"))
            if name:
                result[name] = {_text(attr) for attr in entity.get("attributes", []) if _text(attr)}
    return result


def validate_entity_attribute(model: dict[str, Any], value: str | None, require_attribute: bool = False) -> bool:
    if not value:
        return not require_attribute
    if "." not in value:
        return not require_attribute and value in _entity_attributes(model)
    entity, attribute = [part.strip() for part in value.split(".", 1)]
    return attribute in _entity_attributes(model).get(entity, set())
