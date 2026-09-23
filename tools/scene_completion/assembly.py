"""V3 concern validation, stable IDs, and complete scenario assembly."""

from __future__ import annotations

import hashlib
import json
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
    return (interaction_order.get(item.get("interaction_id"), 999999), item.get("source_step_index", 999999), item.get("concern_key", ""), digest)


def _use_case_actor(uc: dict[str, Any]) -> str:
    return "、".join(uc.get("actors", [])) or "未指定Actor"


def _finding_scenario_steps(uc: dict[str, Any], raw: dict[str, Any], anchor: int) -> list[str]:
    supplied = [str(item.get("text") if isinstance(item, dict) else item).strip() for item in raw.get("scenario_steps", []) if str(item.get("text") if isinstance(item, dict) else item).strip()]
    main = [step["text"] for step in uc.get("main_flow", []) if step.get("step_index", 0) <= anchor]
    if not main or not supplied:
        return supplied or main
    if supplied[: len(main)] == main:
        return supplied
    return main + supplied


def _normalize_findings(model: dict[str, Any], matrix_items: list[dict[str, Any]], raw_findings: Any) -> list[dict[str, Any]]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    nodes = node_map(normalized)
    interactions = {item["interaction_id"]: item for item in normalized["interactions"]}
    matrix = {(item.get("interaction_id", ""), item["concern_key"]): item for item in matrix_items}
    matrix_by_exchange = {(item.get("exchange_id", ""), item["concern_key"]): item for item in matrix_items if item.get("exchange_id")}
    use_cases = use_case_map(normalized)
    findings = _finding_list(raw_findings)
    if not findings:
        findings = [
            {
                **finding,
                "interaction_id": finding.get("interaction_id") or item.get("interaction_id", ""),
                "exchange_id": finding.get("exchange_id") or item.get("exchange_id", ""),
                "concern_key": finding.get("concern_key") or item.get("concern_key", ""),
                "use_case_id": finding.get("use_case_id") or item.get("use_case_id", ""),
                "source_step_index": finding.get("source_step_index") or item.get("source_step_index"),
                "source_node": finding.get("source_node") or item.get("from_node", ""),
                "target_node": finding.get("target_node") or item.get("to_node", ""),
                "source_location": finding.get("source_location") or item.get("source_location", ""),
                "layer": finding.get("layer") or item.get("layer", ""),
                "concern_subject": finding.get("concern_subject") or item.get("concern_subject", ""),
                "basis": finding.get("basis") or item.get("basis", ""),
                "interaction_message": finding.get("interaction_message") or item.get("message", ""),
                "request_message_id": finding.get("request_message_id") or item.get("request_message_id", ""),
                "response_message_id": finding.get("response_message_id") or item.get("response_message_id", ""),
            }
            for item in matrix_items if item.get("status") == "applicable"
            for finding in item.get("findings", []) if isinstance(finding, dict)
        ]
    errors = []
    result = []
    for index, raw in enumerate(findings, 1):
        interaction_id = str(raw.get("interaction_id", "")).strip()
        concern_key = str(raw.get("concern_key", "")).strip()
        interaction = interactions.get(interaction_id)
        matrix_item = matrix_by_exchange.get((str(raw.get("exchange_id", "")).strip(), concern_key)) or matrix.get((interaction_id, concern_key))
        if interaction is None and matrix_item:
            interaction_id = str(matrix_item.get("interaction_id", "")).strip()
            interaction = interactions.get(interaction_id)
        if interaction is None and matrix_item is None:
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
        use_case_id = raw.get("use_case_id") or matrix_item.get("use_case_id") or (interaction or {}).get("use_case_id")
        uc = use_cases.get(use_case_id)
        if uc is None:
            errors.append(f"finding {index}: unknown use_case_id {use_case_id}")
            continue
        try:
            anchor = int(raw.get("source_step_index") or matrix_item.get("source_step_index") or (interaction or {}).get("source_step_index") or 0)
            steps = _finding_scenario_steps(uc, raw, anchor)
        except (TypeError, ValueError, ValidationFailure) as exc:
            errors.extend(exc.errors if isinstance(exc, ValidationFailure) else [f"finding {index}: invalid source_step_index"])
            continue
        required = ["exception_desc", "trigger", "recovery"]
        missing = [key for key in required if not str(raw.get(key, "")).strip()]
        if missing:
            errors.append(f"finding {index}: missing {', '.join(missing)}")
            continue
        source_node_id = raw.get("source_node") or matrix_item.get("from_node") or (interaction or {}).get("from_node", "")
        target_node_id = raw.get("target_node") or matrix_item.get("to_node") or (interaction or {}).get("to_node", "")
        if source_node_id not in nodes or target_node_id not in nodes:
            errors.append(f"finding {index}: unknown SSD source/target node {source_node_id}->{target_node_id}")
            continue
        item = {
            "interaction_id": interaction_id,
            "exchange_id": raw.get("exchange_id") or matrix_item.get("exchange_id") or stable_id("EXCH", use_case_id, interaction_id),
            "ssd_message_id": raw.get("ssd_message_id") or matrix_item.get("ssd_message_id") or matrix_item.get("message_id", ""),
            "request_message_id": raw.get("request_message_id") or matrix_item.get("request_message_id", ""),
            "response_message_id": raw.get("response_message_id") or matrix_item.get("response_message_id", ""),
            "use_case_id": use_case_id,
            "use_case_name": uc.get("use_case_name", ""),
            "actor": _use_case_actor(uc),
            "source_node": source_node_id,
            "target_node": target_node_id,
            "source_node_name": nodes[source_node_id]["name"],
            "target_node_name": nodes[target_node_id]["name"],
            "interaction_message": raw.get("interaction_message") or matrix_item.get("message") or (interaction or {}).get("message", ""),
            "layer": raw.get("layer") or matrix_item.get("layer", "SR"),
            "concern_key": concern_key,
            "concern": CONCERN_DEFINITIONS[concern_key]["label"],
            "concern_subject": raw.get("concern_subject") or matrix_item.get("concern_subject", "target_node"),
            "basis": raw.get("basis") or matrix_item.get("basis", ""),
            "exception_type": str(raw.get("exception_type") or (raw.get("exception_types") or ["未分类异常"])[0]).strip(),
            "exception_types": raw.get("exception_types", []),
            "exception_desc": str(raw["exception_desc"]).strip(),
            "trigger": str(raw["trigger"]).strip(),
            "scenario_steps": steps,
            "expected_result": str(raw.get("expected_result") or raw.get("handling") or "系统返回异常结果并保持状态可追踪。").strip(),
            "recovery": str(raw["recovery"]).strip(),
            "entity_attribute": raw.get("entity_attribute"),
            "source_step_index": anchor,
            "source_location": raw.get("source_location") or matrix_item.get("source_location") or (interaction or {}).get("source_location", ""),
            "scenario_origin": "concern_derived_exception",
            "scenario_type": "concern_derived_exception",
            "status": "applicable",
            "requirement_impact": raw.get("requirement_impact", matrix_item.get("requirement_impact", "")),
            "subsequent_behavior_impact": raw.get("subsequent_behavior_impact", matrix_item.get("subsequent_behavior_impact", "")),
            "environment_coordination_impact": raw.get("environment_coordination_impact", matrix_item.get("environment_coordination_impact", "")),
        }
        result.append(item)
    if errors:
        raise ValidationFailure(errors)
    return result


def _attach_ids(findings: list[dict[str, Any]], model: dict[str, Any]) -> None:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    order = {item["interaction_id"]: index for index, item in enumerate(normalized["interactions"], 1)}
    findings.sort(key=lambda item: _stable_sort(item, order))
    for item in findings:
        atom = item.get("exception_type") or item.get("exception_desc")
        identity = item.get("exchange_id") or item.get("interaction_id")
        item["prediction_id"] = stable_id("PRED", normalized["project"], item["use_case_id"], identity, item["concern_key"], atom, item["exception_desc"])
        item["exception_id"] = item["prediction_id"]
        item["scenario_id"] = stable_id("SCN", normalized["project"], item["use_case_id"], identity, item["concern_key"], atom, item["exception_desc"])


def _diagram_paths(diagram_manifest: dict[str, Any] | None, use_case_id: str) -> tuple[str, str]:
    for entry in (diagram_manifest or {}).get("use_cases", []):
        if entry.get("use_case_id") != use_case_id:
            continue
        artifacts = entry.get("artifacts", {}) or {}
        fused = artifacts.get("fused", {}) or {}
        return fused.get("puml", ""), fused.get("svg") or fused.get("png", "")
    return "", ""


def _ssd_trace(diagram_manifest: dict[str, Any] | None, use_case_id: str, anchor: int) -> dict[str, str]:
    for entry in (diagram_manifest or {}).get("use_cases", []):
        if entry.get("use_case_id") != use_case_id:
            continue
        fused = (entry.get("artifacts", {}) or {}).get("fused", {}) or {}
        path = fused.get("json", "")
        if not path:
            continue
        try:
            messages = json.loads(open(path, encoding="utf-8").read()).get("messages", [])
        except (OSError, ValueError, TypeError):
            continue
        candidates = [item for item in messages if item.get("message_kind") in {"request", "event", "internal_call"}]
        message = next((item for item in candidates if item.get("source_step_index") == anchor), None)
        if message is None and candidates:
            eligible = [item for item in candidates if int(item.get("source_step_index", 0) or 0) <= int(anchor or 0)]
            message = sorted(eligible or candidates, key=lambda item: (abs(int(item.get("source_step_index", 0) or 0) - int(anchor or 0)), item.get("ssd_sequence", 0)))[0]
        if message:
            return {"interaction_id": message.get("interaction_id", ""), "exchange_id": message.get("exchange_id", ""), "ssd_message_id": message.get("message_id", "")}
    return {"interaction_id": "", "exchange_id": "", "ssd_message_id": ""}


def _base_scenario(uc: dict[str, Any], scenario: dict[str, Any], model: dict[str, Any], diagram_manifest: dict[str, Any] | None) -> dict[str, Any]:
    use_case_id = uc["use_case_id"]
    scenario_type = "main_success" if scenario.get("scenario_type") == "main" else scenario.get("scenario_type", "alternative")
    source_id = scenario.get("scenario_id", f"{use_case_id}-main")
    scenario_id = stable_id("SCN", model["project"], use_case_id, scenario_type, source_id)
    puml, rendered = _diagram_paths(diagram_manifest, use_case_id)
    steps = [step.get("text", "") for step in scenario.get("steps", [])]
    trace_anchor = scenario.get("anchor_step_index", 0) or (scenario.get("steps") or [{}])[0].get("step_index", 1)
    trace = _ssd_trace(diagram_manifest, use_case_id, trace_anchor)
    anchor_step = int(scenario.get("anchor_step_index", 0) or 0)
    step_conditions = []
    for step in uc.get("main_flow", []):
        if int(step.get("step_index", 0) or 0) == anchor_step:
            condition = step.get("preconditions") or step.get("condition") or step.get("entry_condition")
            if condition:
                step_conditions.append(f"执行步骤 {anchor_step} 前：{condition}")
    full_preconditions = str(uc.get("preconditions", "未指定"))
    if step_conditions:
        full_preconditions += "；" + "；".join(step_conditions)
    if anchor_step > 1 and not step_conditions:
        full_preconditions += f"；到达主流程步骤 {anchor_step} 前已完成步骤 1-{anchor_step - 1}"
    return {
        "scenario_id": scenario_id,
        "prediction_id": "",
        "scenario_type": scenario_type,
        "scenario_origin": scenario.get("source_type", "requirements"),
        "use_case_id": use_case_id,
        "use_case_name": uc.get("use_case_name", ""),
        "actor": _use_case_actor(uc),
        "source_node": "",
        "target_node": "",
        "source_node_name": _use_case_actor(uc),
        "target_node_name": model.get("system_name", ""),
        "interaction_id": trace["interaction_id"],
        "exchange_id": trace["exchange_id"],
        "ssd_message_id": trace["ssd_message_id"],
        "source_step_index": scenario.get("anchor_step_index", 0),
        "anchor_label": scenario.get("anchor_label", str(scenario.get("anchor_step_index", 0))),
        "interaction_message": "",
        "concern_key": "",
        "concern": "",
        "concern_subject": "",
        "basis": "",
        "exception_type": "",
        "exception_desc": "",
        "preconditions": full_preconditions,
        "trigger": scenario.get("trigger") or uc.get("trigger", "未明确"),
        "scenario_steps": steps,
        "expected_result": scenario.get("expected_result") or uc.get("postconditions", "未指定"),
        "postconditions": uc.get("postconditions", "未指定"),
        "recovery": scenario.get("recovery", ""),
        "source_location": scenario.get("source_location") or uc.get("source_location", ""),
        "diagram_paths": rendered,
        "ssd_paths": puml,
        "source_type": scenario.get("source_type", "requirements"),
    }


def _scenario_catalog(findings: list[dict[str, Any]], model: dict[str, Any], diagram_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    use_cases = use_case_map(normalized)
    scenarios: list[dict[str, Any]] = []
    if str(normalized.get("version")) in {"3", "4", "5", "6"}:
        for uc in normalized["use_cases"]:
            for source in uc.get("scenarios", []):
                scenarios.append(_base_scenario(uc, source, normalized, diagram_manifest))
    for item in findings:
        uc = use_cases[item["use_case_id"]]
        # Requirement branches are authoritative.  A semantic finding that
        # repeats the same explicit exception (same UC/anchor and matching
        # exception text) is evidence for that branch, not a second scenario.
        duplicate_requirement = False
        for existing in scenarios:
            if existing.get("scenario_type") != "requirement_exception":
                continue
            if existing.get("use_case_id") != item.get("use_case_id"):
                continue
            if int(existing.get("source_step_index", 0) or 0) != int(item.get("source_step_index", 0) or 0):
                continue
            existing_text = " ".join(str(existing.get(key, "")) for key in ("exception_desc", "expected_result", "trigger", "scenario_steps"))
            if any(text and text in existing_text for text in (item.get("exception_desc", ""), item.get("exception_type", ""))):
                duplicate_requirement = True
                break
        if duplicate_requirement:
            existing["merged_concern_keys"] = sorted(set(existing.get("merged_concern_keys", [])) | {item.get("concern_key", "")})
            item["merged_requirement_scenario_id"] = existing.get("scenario_id", "")
            continue
        scenario = {
            **item,
            "scenario_origin": "concern_derived_exception",
            "scenario_type": "concern_derived_exception",
            "preconditions": uc.get("preconditions", "未指定"),
            "postconditions": uc.get("postconditions", "未指定"),
            "use_case_name": uc.get("use_case_name", ""),
            "anchor_label": str(item.get("source_step_index", 0)),
            "diagram_paths": _diagram_paths(diagram_manifest, item["use_case_id"])[1],
            "ssd_paths": _diagram_paths(diagram_manifest, item["use_case_id"])[0],
            "source_type": "concern_derived",
        }
        scenarios.append(scenario)
    deduped: list[dict[str, Any]] = []
    by_signature: dict[tuple[Any, ...], dict[str, Any]] = {}
    for scenario in scenarios:
        if scenario.get("scenario_type") == "concern_derived_exception":
            signature = (scenario.get("use_case_id"), scenario.get("source_step_index"), scenario.get("concern_key"), scenario.get("exception_type"), scenario.get("exception_desc"))
            if signature in by_signature:
                continue
        by_signature[(scenario.get("scenario_id"), scenario.get("scenario_type"), scenario.get("source_step_index"))] = scenario
        deduped.append(scenario)
    return deduped


def _link_predictions_to_scenarios(findings: list[dict[str, Any]], scenarios: list[dict[str, Any]], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Give explicit requirement exceptions predictions and link merged evidence once."""
    by_id = {scenario.get("scenario_id"): scenario for scenario in scenarios}
    source_predictions = []
    for scenario in scenarios:
        if scenario.get("scenario_type") != "requirement_exception":
            continue
        prediction_id = stable_id("PRED", model["project"], scenario.get("use_case_id"), "requirement_exception", scenario.get("scenario_id"))
        scenario["prediction_id"] = prediction_id
        scenario["concern_key"] = "unclassified.requirement_exception"
        scenario["concern"] = "需求明确异常"
        scenario["exception_type"] = scenario.get("name", "需求异常")
        scenario["exception_desc"] = scenario.get("expected_result") or scenario.get("trigger") or scenario.get("name", "需求中明确的异常分支")
        source_predictions.append({
            "prediction_id": prediction_id,
            "scenario_id": scenario.get("scenario_id", ""),
            "use_case_id": scenario.get("use_case_id", ""),
            "use_case_name": scenario.get("use_case_name", ""),
            "actor": scenario.get("actor", ""),
            "source_step_index": scenario.get("source_step_index", 0),
            "anchor_label": scenario.get("anchor_label", ""),
            "concern_key": scenario["concern_key"],
            "concern": scenario["concern"],
            "exception_type": scenario["exception_type"],
            "exception_desc": scenario["exception_desc"],
            "trigger": scenario.get("trigger", ""),
            "expected_result": scenario.get("expected_result", ""),
            "recovery": scenario.get("recovery", ""),
            "scenario_steps": scenario.get("scenario_steps", []),
            "source_location": scenario.get("source_location", ""),
            "source_type": scenario.get("source_type", "requirements"),
            "layer": "RR",
            "ssd_message_id": scenario.get("ssd_message_id", ""),
            "exchange_id": scenario.get("exchange_id", ""),
        })
    derived = []
    for item in findings:
        merged_id = item.pop("merged_requirement_scenario_id", "")
        if merged_id and merged_id in by_id:
            requirement = by_id[merged_id]
            item["scenario_id"] = merged_id
            item["prediction_id"] = requirement["prediction_id"]
            requirement.setdefault("merged_concern_keys", [])
            if item.get("concern_key") not in requirement["merged_concern_keys"]:
                requirement["merged_concern_keys"].append(item.get("concern_key"))
            requirement["concern_evidence"] = requirement.get("concern_evidence", []) + [{"concern_key": item.get("concern_key"), "basis": item.get("basis", ""), "ssd_message_id": item.get("ssd_message_id", "")}]
            continue
        scenario = next((candidate for candidate in scenarios if candidate.get("scenario_id") == item.get("scenario_id")), None)
        if scenario:
            scenario["prediction_id"] = item.get("prediction_id", "")
        derived.append(item)
    return source_predictions + derived


def _enrich_matrix_findings(matrix_items: list[dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for finding in findings:
        key = (str(finding.get("exchange_id", "")), str(finding.get("concern_key", "")))
        indexed.setdefault(key, []).append(finding)
    result = []
    for raw in matrix_items:
        item = dict(raw)
        matching = indexed.get((str(item.get("exchange_id", "")), str(item.get("concern_key", ""))), [])
        if matching:
            item["findings"] = matching
            item["exception_types"] = sorted({str(f.get("exception_type", "")).strip() for f in matching if str(f.get("exception_type", "")).strip()})
            latest_basis = next((str(f.get("basis", "")).strip() for f in matching if str(f.get("basis", "")).strip()), "")
            if latest_basis:
                item["basis"] = latest_basis
        if item.get("concern_key") == "common.timeout":
            for field in ("requirement_impact", "subsequent_behavior_impact", "environment_coordination_impact"):
                if item.get(field) == "unknown":
                    item[field] = ""
        result.append(item)
    return result


def assemble_v3_results(model: dict[str, Any], concern_matrix: Any, semantic_findings: Any, diagram_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    report = validate_scene_model(model)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    normalized = report["normalized_model"]
    matrix_report = validate_concern_matrix(normalized, concern_matrix, require_complete=str(normalized.get("version")) == "6")
    if not matrix_report["valid"]:
        raise ValidationFailure(matrix_report["errors"])
    findings = _normalize_findings(normalized, matrix_report["items"], semantic_findings)
    _attach_ids(findings, normalized)
    scenarios = _scenario_catalog(findings, normalized, diagram_manifest)
    findings = _link_predictions_to_scenarios(findings, scenarios, normalized)
    matrix_items = _enrich_matrix_findings(matrix_report["items"], findings)
    result_by_key: dict[str, list[dict[str, Any]]] = {key: [] for key in CONCERN_DEFINITIONS}
    for item in findings:
        result_by_key.setdefault(item["concern_key"], []).append(item)
    exception_tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in findings:
        exception_tree.setdefault(item["use_case_id"], {}).setdefault(str(item.get("source_step_index", 0)), []).append(item)
    review_items = []
    for node in normalized["system_composition"]["nodes"]:
        if node.get("kind") == "internal_service" and node.get("service_type") == "unknown":
            review_items.append({"type": "service_type_confirmation", "node_id": node["node_id"], "message": f"请确认 Service《{node['name']}》属于展示型还是计算型。"})
    for item in matrix_report["items"]:
        if item.get("status") == "needs_requirement":
            review_items.append({"type": "concern_requirement_confirmation", "interaction_id": item.get("interaction_id", ""), "exchange_id": item.get("exchange_id", ""), "use_case_id": item.get("use_case_id", ""), "concern_key": item["concern_key"], "message": "需求文档不足以确定该关注点是否适用。"})
        if item.get("status") == "pending_review":
            review_items.append({"type": "concern_review_pending", "interaction_id": item.get("interaction_id", ""), "exchange_id": item.get("exchange_id", ""), "concern_key": item["concern_key"], "message": "该候选关注点尚未完成 Agent 判断。"})
    for use_case_manifest in (diagram_manifest or {}).get("use_cases", []):
        for review_item in use_case_manifest.get("review_items", []):
            if review_item not in review_items:
                review_items.append(review_item)
    exchange_catalog = normalized["interactions"]
    if str(normalized.get("version")) == "5":
        exchange_catalog = []
        seen_exchange = set()
        for item in matrix_report["items"]:
            exchange_id = item.get("exchange_id")
            if exchange_id and exchange_id not in seen_exchange:
                exchange_catalog.append(dict(item))
                seen_exchange.add(exchange_id)
    return {
        "version": str(normalized.get("version", "3")),
        "project": normalized["project"],
        "scene_model": normalized,
        "system_composition": normalized["system_composition"],
        "interaction_catalog": exchange_catalog,
        "concern_matrix": matrix_items,
        "checkpoint_results": result_by_key,
        "exception_tree": exception_tree,
        "scenario_catalog": scenarios,
        "review_items": review_items,
        "diagram_manifest": diagram_manifest or {"version": "3", "status": "skipped", "artifacts": []},
        "findings": findings,
    }


def assemble_v2_results(model: dict[str, Any], concern_matrix: Any, semantic_findings: Any, diagram_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retain V2 finding-only behavior for existing fixtures."""
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
    result_by_key: dict[str, list[dict[str, Any]]] = {key: [] for key in CONCERN_DEFINITIONS}
    for item in findings:
        result_by_key[item["concern_key"]].append(item)
    exception_tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in findings:
        exception_tree.setdefault(item["use_case_id"] or "unassigned", {}).setdefault(item["interaction_id"], []).append(item)
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
        "findings": findings,
    }


def assemble_results(model: dict[str, Any], concern_matrix: Any, semantic_findings: Any, diagram_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    if str(normalized.get("version")) in {"3", "4", "5", "6"}:
        return assemble_v3_results(normalized, concern_matrix, semantic_findings, diagram_manifest)
    return assemble_v2_results(normalized, concern_matrix, semantic_findings, diagram_manifest)
