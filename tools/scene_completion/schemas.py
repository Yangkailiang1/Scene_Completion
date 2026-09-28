"""Scene Completion V5 scene, layered architecture, and source contracts."""

from __future__ import annotations

import copy
import hashlib
from typing import Any


NODE_KINDS = {
    "human_actor", "external_actor", "frontend_ui", "connection_device", "internal_service",
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
SR_SERVICE_TYPES = {
    "display_interaction", "query_retrieval", "resource_mutation",
    "analysis_generation", "release_activation", "unknown",
}
AR_SERVICE_TYPES = {
    "query_read", "command_write", "orchestration", "integration_event",
    "publish_activation", "unknown",
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


def _normalize_entity_operations(value: Any, entities: list[str], use_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailure(["use_case_entity_operations must be a list"])
    known_entities = set(entities)
    uc_by_id = {uc["use_case_id"]: uc for uc in use_cases}
    known_ucs = set(uc_by_id)
    operations, seen = [], set()
    for index, raw in enumerate(value, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"use_case_entity_operations[{index}] must be an object"])
        item = dict(raw)
        uc_id = _text(item.get("use_case_id"))
        entity = _text(item.get("entity"))
        operation = _text(item.get("operation")).upper()
        if uc_id not in known_ucs:
            raise ValidationFailure([f"CRUD operation {index} references unknown use_case_id: {uc_id}"])
        if entity not in known_entities:
            raise ValidationFailure([f"CRUD operation {index} references unknown entity: {entity}"])
        if operation not in {"C", "R", "U", "D"}:
            raise ValidationFailure([f"CRUD operation {index} has invalid operation: {operation}"])
        try:
            step_index = int(item.get("source_step_index"))
        except (TypeError, ValueError):
            raise ValidationFailure([f"CRUD operation {index} needs a valid source_step_index"])
        if not _text(item.get("source_location")):
            raise ValidationFailure([f"CRUD operation {index} needs source_location"])
        if not _text(item.get("evidence")):
            raise ValidationFailure([f"CRUD operation {index} needs evidence"])
        available_steps = {step["step_index"] for step in uc_by_id[uc_id].get("main_flow", []) + uc_by_id[uc_id].get("alternative_flow", [])}
        if step_index not in available_steps:
            raise ValidationFailure([f"CRUD operation {index} source_step_index {step_index} is not present in {uc_id}"])
        status = _text(item.get("mapping_status"), "inferred")
        if status not in {"confirmed", "inferred", "needs_confirmation"}:
            raise ValidationFailure([f"CRUD operation {index} has invalid mapping_status: {status}"])
        op_id = _text(item.get("operation_id"), stable_id("CRUD", uc_id, entity, operation, step_index))
        if op_id in seen:
            raise ValidationFailure([f"duplicate CRUD operation_id: {op_id}"])
        seen.add(op_id)
        item.update({"operation_id": op_id, "use_case_id": uc_id, "entity": entity, "operation": operation,
                     "source_step_index": step_index, "source_location": _text(item.get("source_location")),
                     "mapping_status": status, "evidence": _text(item.get("evidence"))})
        operations.append(item)
    known_operation_ids = {item["operation_id"] for item in operations}
    for item in operations:
        prerequisites = item.get("depends_on_operations", []) or []
        prerequisites = [prerequisites] if isinstance(prerequisites, str) else prerequisites
        if not isinstance(prerequisites, list):
            raise ValidationFailure([f"CRUD operation {item['operation_id']} depends_on_operations must be a list"])
        missing = [value for value in prerequisites if str(value) not in known_operation_ids]
        if missing:
            raise ValidationFailure([f"CRUD operation {item['operation_id']} references unknown prerequisite operation(s): {', '.join(map(str, missing))}"])
        item["depends_on_operations"] = [str(value) for value in prerequisites]
    return operations


def _normalize_frontend_mappings(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailure(["frontend_mappings must be a list"])
    result = []
    for index, raw in enumerate(value, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"frontend_mappings[{index}] must be an object"])
        item = dict(raw)
        if not _text(item.get("actor_id")) or not _text(item.get("frontend_id")):
            raise ValidationFailure([f"frontend_mappings[{index}] needs actor_id and frontend_id"])
        item["use_case_ids"] = list(dict.fromkeys(_text(v) for v in item.get("use_case_ids", []) if _text(v)))
        item["mapping_status"] = _text(item.get("mapping_status"), "needs_confirmation")
        if item["mapping_status"] not in {"confirmed", "inferred", "needs_confirmation"}:
            raise ValidationFailure([f"frontend_mappings[{index}] has invalid mapping_status"])
        result.append(item)
    return result


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
        sr = uc["architecture"].get("sr")
        if isinstance(sr, dict):
            sr_type = _text(sr.get("service_type"), "unknown")
            if sr_type == "display":
                sr_type = "display_interaction"
                sr.setdefault("legacy_service_type", "display")
            elif sr_type == "compute":
                sr_type = "unknown"
                sr.setdefault("legacy_service_type", "compute")
                sr["classification_status"] = "needs_confirmation"
                sr.setdefault("classification_basis", "旧 compute 分类无法安全映射到 SR 业务分类，需重新确认")
            sr.update({
                "service_type": sr_type,
                "classification_status": _text(sr.get("classification_status"), "needs_confirmation" if sr_type == "unknown" else "inferred"),
                "classification_basis": _text(sr.get("classification_basis"), "证据不足，待确认" if sr_type == "unknown" else "待补充分类依据"),
                "source_location": _text(sr.get("source_location") or uc.get("source_location") or (data.get("source") or {}).get("path")),
            })
        ar = uc["architecture"].get("ar")
        if isinstance(ar, list):
            for component in ar:
                if not isinstance(component, dict):
                    continue
                ar_type = _text(component.get("service_type"), "unknown")
                if ar_type not in AR_SERVICE_TYPES:
                    # Old node-oriented display/compute labels carry no safe AR semantics.
                    component.setdefault("legacy_service_type", ar_type)
                    ar_type = "unknown"
                    component["classification_status"] = "needs_confirmation"
                    component.setdefault("classification_basis", "旧节点分类无法安全映射到 AR 技术职责，需重新确认")
                component.update({
                    "service_type": ar_type,
                    "classification_status": _text(component.get("classification_status"), "needs_confirmation" if ar_type == "unknown" else "inferred"),
                    "classification_basis": _text(component.get("classification_basis"), "证据不足，待确认" if ar_type == "unknown" else "待补充分类依据"),
                    "source_location": _text(component.get("source_location") or uc.get("source_location") or (data.get("source") or {}).get("path")),
                })
        normalized_ucs.append(uc)
    data["use_cases"] = normalized_ucs
    data["entities"] = list(dict.fromkeys(_text(entity) for entity in data.get("entities", []) if _text(entity)))
    er_model = data.get("er_model") or {}
    if not isinstance(er_model, dict):
        raise ValidationFailure(["er_model must be an object"])
    er_entities = er_model.get("entities", [])
    if not isinstance(er_entities, list):
        raise ValidationFailure(["er_model.entities must be a list"])
    for entity in er_entities:
        name = _text(entity.get("name")) if isinstance(entity, dict) else _text(entity)
        if name and name not in data["entities"]:
            data["entities"].append(name)
    er_model["entities"] = [dict(entity) if isinstance(entity, dict) else {"name": _text(entity)} for entity in er_entities if _text(entity.get("name") if isinstance(entity, dict) else entity)]
    for index, entity in enumerate(er_model["entities"], 1):
        status = _text(entity.get("mapping_status"), "inferred")
        if status not in {"confirmed", "inferred", "needs_confirmation"}:
            raise ValidationFailure([f"er_model.entities[{index}] has invalid mapping_status: {status}"])
        entity["mapping_status"] = status
        if not _text(entity.get("source_location")):
            raise ValidationFailure([f"er_model.entities[{index}] needs source_location"])
    relationships = er_model.get("relationships", [])
    if not isinstance(relationships, list):
        raise ValidationFailure(["er_model.relationships must be a list"])
    known_entities = set(data["entities"])
    for index, relation in enumerate(relationships, 1):
        if not isinstance(relation, dict):
            raise ValidationFailure([f"er_model.relationships[{index}] must be an object"])
        for field in ("from_entity", "to_entity"):
            if _text(relation.get(field)) not in known_entities:
                raise ValidationFailure([f"er_model.relationships[{index}] references unknown {field}: {relation.get(field)}"])
        if not _text(relation.get("source_location")) or not _text(relation.get("evidence")):
            raise ValidationFailure([f"er_model.relationships[{index}] needs evidence and source_location"])
    data["er_model"] = er_model
    data["use_case_entity_operations"] = _normalize_entity_operations(data.get("use_case_entity_operations"), data["entities"], normalized_ucs)
    semantic_reviews = list(data.get("review_items") or [])
    for entity in er_model["entities"]:
        if entity.get("mapping_status") == "needs_confirmation":
            semantic_reviews.append({"type": "er_entity_confirmation", "entity": entity.get("name", ""), "source_location": entity.get("source_location", ""), "message": entity.get("evidence", "实体映射待确认。")})
    data["review_items"] = semantic_reviews
    data["interfaces"] = _normalize_interfaces(data.get("interfaces"))
    composition = data.get("system_composition") or {}
    if not isinstance(composition, dict):
        raise ValidationFailure(["system_composition must be an object"])
    raw_nodes = composition.get("nodes")
    nodes = _normalize_nodes(raw_nodes) if raw_nodes is not None else _derive_nodes(data, normalized_ucs)
    # Logical SR resource facades expose database access as an analyzable
    # service boundary while leaving the physical database at AR. This is an
    # inferred model abstraction only; it never invents an HTTP endpoint.
    existing_ids = {node["node_id"] for node in nodes}
    resource_service_mappings = []
    for physical in list(nodes):
        if physical.get("kind") not in {"internal_database", "internal_knowledge_base"} or physical.get("layer") != "AR":
            continue
        facade_id = stable_id("SR-RESOURCE", data["project"], physical["node_id"])
        if facade_id not in existing_ids:
            nodes.append({
                "node_id": facade_id,
                "name": f"{physical['name']}资源服务",
                "kind": "internal_service",
                "service_role": "resource_service",
                "resource_ids": [physical["node_id"]],
                "layer": "SR",
                "service_type": "unknown",
                "classification_status": "inferred",
                "classification_basis": "根据物理数据库访问关系建立的 SR 逻辑资源服务抽象，不代表独立部署组件",
                "source_location": physical.get("source_location", (data.get("source") or {}).get("path", "")),
                "mapping_status": "inferred",
            })
            existing_ids.add(facade_id)
        resource_service_mappings.append({
            "resource_service_id": facade_id,
            "resource_id": physical["node_id"],
            "physical_layer": "AR",
            "logical_layer": "SR",
            "mapping_status": "inferred",
            "source_location": physical.get("source_location", ""),
        })
    data["resource_service_mappings"] = resource_service_mappings
    composition["nodes"] = nodes
    classification_reviews = list(data.get("review_items") or [])
    nodes_by_id = {node["node_id"]: node for node in nodes}
    for uc in normalized_ucs:
        sr = (uc.get("architecture") or {}).get("sr") or {}
        if isinstance(sr, dict) and _text(sr.get("service_id")):
            sr_node = nodes_by_id.get(_text(sr.get("service_id")))
            if sr_node and sr_node.get("kind") in {"internal_service", "abstract_service"} and sr_node.get("layer") == "SR":
                if sr_node.get("service_type") and sr_node.get("service_type") != sr["service_type"]:
                    sr_node["_classification_conflict"] = {"mapping": sr["service_type"], "node": sr_node["service_type"], "use_case_id": uc["use_case_id"]}
                sr_node.update({key: sr[key] for key in ("service_type", "classification_status", "classification_basis", "source_location")})
            if sr["service_type"] == "unknown":
                classification_reviews.append({"type": "sr_service_classification", "use_case_id": uc["use_case_id"], "service_id": sr.get("service_id", ""), "abstract_api_id": sr.get("abstract_api_id", ""), "message": "请依据该 RR 用例对应的 SR API 职责确认五类 SR Service 分类。"})
        for component in (uc.get("architecture") or {}).get("ar") or []:
            if not isinstance(component, dict):
                continue
            if component["service_type"] == "unknown":
                classification_reviews.append({"type": "ar_service_classification", "use_case_id": uc["use_case_id"], "microservice_id": component.get("microservice_id", ""), "implementation_api_id": component.get("implementation_api_id", ""), "message": "请依据该 AR 实现接口的技术职责确认 AR Service 分类。"})
    # Stable de-duplication: re-normalizing an already normalized model must not
    # multiply the same classification review item.
    data["review_items"] = list({(item.get("type"), item.get("use_case_id"), item.get("service_id", item.get("microservice_id", "")), item.get("abstract_api_id", item.get("implementation_api_id", ""))): item for item in classification_reviews if isinstance(item, dict)}.values())
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
    # A human actor gets a distinct frontend boundary. Legacy generic UI/device
    # nodes are not treated as supported hardware; devices require explicit
    # evidence on a connection_device node.
    actor_nodes = [node for node in nodes if node.get("kind") == "human_actor"]
    frontend_mappings = data.get("frontend_mappings")
    frontend_mappings = _normalize_frontend_mappings(frontend_mappings) if frontend_mappings is not None else []
    mapping_by_actor = {item["actor_id"]: item for item in frontend_mappings}
    for actor in actor_nodes:
        actor_cases = [uc["use_case_id"] for uc in normalized_ucs if actor["name"] in uc.get("actors", []) or actor["node_id"] in uc.get("actors", [])]
        mapping = mapping_by_actor.get(actor["node_id"])
        frontend_id = mapping.get("frontend_id") if mapping else stable_id("FRONTEND", data["project"], actor["node_id"])
        frontend = next((node for node in nodes if node.get("node_id") == frontend_id), None)
        if frontend is None:
            frontend = {"node_id": frontend_id, "name": f"{actor['name']}端 UI/前端", "kind": "frontend_ui", "layer": "RR",
                        "actor_id": actor["node_id"], "mapping_status": "inferred", "source_location": actor.get("source_location", "")}
            nodes.append(frontend)
        elif frontend.get("kind") != "frontend_ui":
            raise ValidationFailure([f"frontend mapping for {actor['node_id']} references a non-frontend node: {frontend_id}"])
        if mapping is None:
            mapping = {"actor_id": actor["node_id"], "frontend_id": frontend_id, "use_case_ids": actor_cases,
                       "mapping_status": "inferred", "source_location": actor.get("source_location", ""),
                       "basis": "按各 Use Case 的 Actor 关联生成独立前端边界；待具体客户端架构确认"}
            frontend_mappings.append(mapping)
        else:
            mapping["use_case_ids"] = mapping.get("use_case_ids") or actor_cases
        frontend["actor_id"] = actor["node_id"]
        frontend["use_case_ids"] = mapping.get("use_case_ids", actor_cases)
        frontend["mapping_status"] = mapping.get("mapping_status", "needs_confirmation")
    data["frontend_mappings"] = frontend_mappings
    normalized_node_ids = {node["node_id"] for node in nodes}
    normalized_by_id = {node["node_id"]: node for node in nodes}
    normalized_uc_ids = {uc["use_case_id"] for uc in normalized_ucs}
    for mapping in frontend_mappings:
        actor = normalized_by_id.get(mapping["actor_id"])
        frontend = normalized_by_id.get(mapping["frontend_id"])
        if not actor or actor.get("kind") != "human_actor":
            raise ValidationFailure([f"frontend mapping actor_id must reference a human_actor: {mapping['actor_id']}"])
        if not frontend or frontend.get("kind") != "frontend_ui":
            raise ValidationFailure([f"frontend mapping frontend_id must reference a frontend_ui: {mapping['frontend_id']}"])
        if any(use_case_id not in normalized_uc_ids for use_case_id in mapping.get("use_case_ids", [])):
            raise ValidationFailure([f"frontend mapping for {mapping['actor_id']} references unknown use case"])
    # Explicit device support only; no device is inferred from a generic web/mobile UI label.
    data["supported_devices"] = [node["node_id"] for node in nodes if node.get("kind") == "connection_device" and node.get("spec_explicit") is True and _text(node.get("source_location"))]
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
    # Materialize actor and external-dependency participation as first-class
    # RR use-case associations so diagram semantics and rendering agree.
    node_by_id = {node["node_id"]: node for node in nodes}
    abstract_by_uc = {
        node.get("use_case_id"): node for node in nodes
        if node.get("kind") == "abstract_service" and node.get("layer", "RR") == "RR"
    }
    sr_by_uc = {
        node.get("use_case_id"): node for node in nodes
        if node.get("layer") == "SR" and node.get("kind") in {"internal_service", "abstract_service"}
    }
    association_edges = list(composition["edges"])
    # Replace generated actor/frontend participation edges on each normalization
    # pass, retaining unrelated architecture edges.
    association_edges = [edge for edge in association_edges if edge.get("relation") not in {"participates_in", "uses_frontend", "serves_use_case", "supports_device"}]
    existing_associations = {
        (edge.get("from_node"), edge.get("to_node"), edge.get("relation"))
        for edge in association_edges
    }
    review_items = list(composition.get("review_items") or [])
    for uc in normalized_ucs:
        rr_node = abstract_by_uc.get(uc["use_case_id"])
        if not rr_node:
            continue
        for actor in uc.get("actors", []):
            matches = [node for node in nodes if node.get("kind") in {"human_actor", "external_actor", "external_service", "external_database", "external_llm"} and actor in {node.get("node_id"), node.get("name")}]
            if len(matches) == 1:
                relation = "external_participates_in" if matches[0].get("kind") in {"external_service", "external_database", "external_llm"} else "participates_in"
                if matches[0].get("kind") == "human_actor":
                    mapping = mapping_by_actor.get(matches[0]["node_id"]) or next((item for item in frontend_mappings if item.get("actor_id") == matches[0]["node_id"]), {})
                    frontend_id = mapping.get("frontend_id")
                    if frontend_id:
                        for left, right, edge_relation in ((matches[0]["node_id"], frontend_id, "uses_frontend"), (frontend_id, rr_node["node_id"], "serves_use_case")):
                            edge_key = (left, right, edge_relation)
                            if edge_key not in existing_associations:
                                association_edges.append({"edge_id": stable_id("EDGE", *edge_key, uc["use_case_id"]), "from_node": left, "to_node": right,
                                                          "relation": edge_relation, "use_case_id": uc["use_case_id"], "mapping_status": mapping.get("mapping_status", "inferred"),
                                                          "source_location": mapping.get("source_location", uc.get("source_location", ""))})
                                existing_associations.add(edge_key)
                    continue
                edge_key = (matches[0]["node_id"], rr_node["node_id"], relation)
                if edge_key not in existing_associations:
                    association_edges.append({"edge_id": stable_id("EDGE", *edge_key), "from_node": edge_key[0], "to_node": edge_key[1], "relation": edge_key[2], "use_case_id": uc["use_case_id"], "source_location": uc.get("source_location", "")})
                    existing_associations.add(edge_key)
            elif not matches:
                review_items.append({"type": "actor_use_case_association", "use_case_id": uc["use_case_id"], "actor": actor, "message": "Use Case Actor 未匹配到唯一的 Actor 节点。"})
        sr_node = sr_by_uc.get(uc["use_case_id"])
        if not sr_node:
            continue
        for edge in composition["edges"]:
            if edge.get("from_node") != sr_node["node_id"] or edge.get("relation") != "sr_external_dependency":
                continue
            external = node_by_id.get(edge.get("to_node"), {})
            if external.get("kind") not in {"external_service", "external_database", "external_llm"}:
                continue
            edge_key = (rr_node["node_id"], external["node_id"], "uses_external_service")
            if edge_key not in existing_associations:
                association_edges.append({"edge_id": stable_id("EDGE", *edge_key), "from_node": edge_key[0], "to_node": edge_key[1], "relation": edge_key[2], "use_case_id": uc["use_case_id"], "source_location": edge.get("source_location", uc.get("source_location", ""))})
                existing_associations.add(edge_key)
    composition["edges"] = association_edges
    composition["review_items"] = review_items
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
        if str(normalized.get("version")) in {"3", "4", "5", "6", "8", "9"}:
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
    if str(normalized.get("version")) in {"4", "5", "6", "8", "9"}:
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
                if str(normalized.get("version")) in {"6", "7", "8", "9"}:
                    if component.get("service_type") not in AR_SERVICE_TYPES:
                        errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] has invalid AR service_type: {component.get('service_type')}")
                    if component.get("classification_status") not in CLASSIFICATION_STATUS:
                        errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] has invalid classification_status")
                    if component.get("service_type") == "unknown" and component.get("classification_status") != "needs_confirmation":
                        errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] unknown classification must be needs_confirmation")
                    if not _text(component.get("classification_basis")) or not _text(component.get("source_location")):
                        errors.append(f"{uc['use_case_id']}.architecture.ar[{index}] needs classification_basis and source_location")
            if str(normalized.get("version")) in {"6", "7", "8", "9"}:
                if sr.get("service_type") not in SR_SERVICE_TYPES:
                    errors.append(f"{uc['use_case_id']}.architecture.sr has invalid SR service_type: {sr.get('service_type')}")
                if sr.get("classification_status") not in CLASSIFICATION_STATUS:
                    errors.append(f"{uc['use_case_id']}.architecture.sr has invalid classification_status")
                if sr.get("service_type") == "unknown" and sr.get("classification_status") != "needs_confirmation":
                    errors.append(f"{uc['use_case_id']}.architecture.sr unknown classification must be needs_confirmation")
                if not _text(sr.get("classification_basis")) or not _text(sr.get("source_location")):
                    errors.append(f"{uc['use_case_id']}.architecture.sr needs classification_basis and source_location")
            sr_node = nodes_by_id.get(_text(sr.get("service_id")))
            if sr_node and sr_node.get("_classification_conflict"):
                errors.append(f"{uc['use_case_id']} SR service node classification conflicts with architecture.sr mapping")
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
