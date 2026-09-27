"""V3 concern validation, stable IDs, and complete scenario assembly."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Any

from .concerns import CONCERN_DEFINITIONS, CONCERN_REGISTRY_VERSION, validate_concern_matrix
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
    matrix_by_candidate = {item.get("candidate_id"): item for item in matrix_items if item.get("candidate_id")}
    use_cases = use_case_map(normalized)
    findings = _finding_list(raw_findings)
    if not findings:
        findings = [
            {
                **finding,
                "interaction_id": finding.get("interaction_id") or item.get("interaction_id", ""),
                "candidate_id": finding.get("candidate_id") or item.get("candidate_id", ""),
                "concern_layer": finding.get("concern_layer") or item.get("concern_layer", item.get("layer", "")),
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
        matrix_item = matrix_by_candidate.get(str(raw.get("candidate_id", "")).strip()) or matrix_by_exchange.get((str(raw.get("exchange_id", "")).strip(), concern_key)) or matrix.get((interaction_id, concern_key))
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
            "candidate_id": raw.get("candidate_id") or matrix_item.get("candidate_id", ""),
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
            "layer": raw.get("concern_layer") or raw.get("layer") or matrix_item.get("concern_layer", matrix_item.get("layer", "SR")),
            "exchange_layer": matrix_item.get("exchange_layer", matrix_item.get("layer", "SR")),
            "api": raw.get("api") or matrix_item.get("api", ""),
            "interface_id": raw.get("interface_id") or matrix_item.get("interface_id", ""),
            "abstract_api_id": raw.get("abstract_api_id") or matrix_item.get("abstract_api_id", ""),
            "implementation_api_id": raw.get("implementation_api_id") or matrix_item.get("implementation_api_id", ""),
            "service_id": raw.get("service_id") or matrix_item.get("service_id", ""),
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


def _canonical_availability_type(item: dict[str, Any]) -> str:
    raw = str(item.get("exception_type", "")).strip().casefold()
    unavailable_terms = ("连接失败", "无法连接", "不可用", "宕机", "unavailable", "databaseunavailable", "connection refused")
    if any(term in raw for term in unavailable_terms):
        return "database_unavailable"
    return " ".join(raw.split())


def _database_failure_outcome_signature(value: Any) -> str:
    text = " ".join(str(value or "").casefold().split())
    compact = re.sub(r"[\s，。、“”‘’：:；;,.!?！？]", "", text)
    resource = next((term for term in ("商品", "订单", "库存", "价格", "退款", "物流") if term in compact), "")
    if any(term in compact for term in ("失败", "不可用", "错误")):
        return f"operation_failed:{resource}"
    return compact


def _database_failure_recovery_signature(value: Any) -> str:
    text = " ".join(str(value or "").casefold().split())
    compact = re.sub(r"[\s，。、“”‘’：:；;,.!?！？]", "", text)
    if any(term in compact for term in ("重试", "回到主流程", "继续主流程")):
        return "notify_then_retry_or_resume"
    if any(term in compact for term in ("结束", "终止")):
        return "notify_then_terminate"
    return compact


def _merge_equivalent_database_failures(findings: list[dict[str, Any]], model: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge equivalent DB-availability failures without losing SSD evidence."""
    nodes = node_map(model)
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    result: list[dict[str, Any]] = []
    for item in findings:
        target = nodes.get(item.get("target_node", ""), {})
        is_database_outage = (
            item.get("concern_key") == "internal_database.availability"
            and target.get("kind") in {"internal_database", "internal_knowledge_base"}
            and _canonical_availability_type(item) == "database_unavailable"
        )
        if not is_database_outage:
            result.append(item)
            continue
        signature = (
            item.get("use_case_id"), item.get("source_step_index"), item.get("target_node"),
            item.get("concern_key"), "database_unavailable",
            _database_failure_outcome_signature(item.get("expected_result")),
            _database_failure_recovery_signature(item.get("recovery")),
        )
        existing = merged.get(signature)
        trace_ref = {key: item.get(key, "") for key in (
            "interaction_id", "exchange_id", "ssd_message_id", "request_message_id", "response_message_id",
            "source_node", "target_node", "source_node_name", "target_node_name", "layer", "api",
            "abstract_api_id", "implementation_api_id", "service_id", "interaction_message", "source_location",
        )}
        if existing is None:
            item["trace_refs"] = [trace_ref]
            item["source_exception_types"] = [item.get("exception_type", "")]
            item["related_exchange_ids"] = [trace_ref["exchange_id"]] if trace_ref.get("exchange_id") else []
            item["related_ssd_message_ids"] = [trace_ref["ssd_message_id"]] if trace_ref.get("ssd_message_id") else []
            item["source_exception_descriptions"] = [item.get("exception_desc", "")] if item.get("exception_desc") else []
            merged[signature] = item
            result.append(item)
            continue
        if trace_ref not in existing["trace_refs"]:
            existing["trace_refs"].append(trace_ref)
        raw_type = item.get("exception_type", "")
        if raw_type and raw_type not in existing["source_exception_types"]:
            existing["source_exception_types"].append(raw_type)
        raw_desc = item.get("exception_desc", "")
        if raw_desc and raw_desc not in existing["source_exception_descriptions"]:
            existing["source_exception_descriptions"].append(raw_desc)
        existing["trace_refs"].sort(key=lambda ref: (str(ref.get("exchange_id", "")), str(ref.get("ssd_message_id", ""))))
        existing["source_exception_types"].sort()
        existing["source_exception_descriptions"].sort()
        existing["related_exchange_ids"] = sorted({ref.get("exchange_id", "") for ref in existing["trace_refs"] if ref.get("exchange_id")})
        existing["related_ssd_message_ids"] = sorted({ref.get("ssd_message_id", "") for ref in existing["trace_refs"] if ref.get("ssd_message_id")})
        existing["exception_type"] = "数据库不可用"
    return result


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
            return {
                "interaction_id": message.get("interaction_id", ""),
                "exchange_id": message.get("exchange_id", ""),
                "ssd_message_id": message.get("message_id", ""),
                "source_node": message.get("from_node", ""),
                "target_node": message.get("to_node", ""),
                "layer": message.get("layer", ""),
                "interaction_message": message.get("message", ""),
                "source_location": message.get("source_location", ""),
            }
    return {"interaction_id": "", "exchange_id": "", "ssd_message_id": "", "source_node": "", "target_node": "", "layer": "", "interaction_message": "", "source_location": ""}


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
        "source_node": trace["source_node"],
        "target_node": trace["target_node"],
        "source_node_name": node_map(model).get(trace["source_node"], {}).get("name", _use_case_actor(uc)),
        "target_node_name": node_map(model).get(trace["target_node"], {}).get("name", model.get("system_name", "")),
        "layer": trace["layer"],
        "interaction_id": trace["interaction_id"],
        "exchange_id": trace["exchange_id"],
        "ssd_message_id": trace["ssd_message_id"],
        "source_step_index": scenario.get("anchor_step_index", 0),
        "anchor_label": scenario.get("anchor_label", str(scenario.get("anchor_step_index", 0))),
        "interaction_message": trace["interaction_message"],
        "trace_mapping_status": "mapped" if trace["source_node"] and trace["target_node"] else "needs_confirmation",
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
        "name": scenario.get("name", ""),
        "scenario_source": "spec_exception_branch" if scenario_type == "requirement_exception" else "spec_scenario",
        "spec_explicitness": "unverified",
        "spec_sources": [scenario.get("source_location")] if scenario.get("source_location") else [],
    }


def _normalized_phrase(value: Any) -> str:
    return re.sub(r"[\s，。、“”‘’：:；;（）()【】\[\]→\-]", "", str(value or "")).lower()


def _spec_lines(source_documents: list[dict[str, Any]] | None) -> list[tuple[str, int, str]]:
    result = []
    for source in source_documents or []:
        text = str(source.get("text", ""))
        name = str(source.get("name") or Path(str(source.get("path", ""))).name)
        result.extend((name, index, line.strip()) for index, line in enumerate(text.splitlines(), 1) if line.strip())
    return result


def _find_spec_sources(scenario: dict[str, Any], spec_lines: list[tuple[str, int, str]], trust_location: bool = False) -> list[str]:
    explicit = str(scenario.get("source_location", ""))
    if trust_location and explicit and any(name in explicit for name, _, _ in spec_lines):
        # Extracted scenario locations are authoritative, but still validate that
        # the cited document/line exists when the source text was supplied.
        match = re.search(r":(\d+)(?:-\d+)?$", explicit)
        doc_name = next((name for name, _, _ in spec_lines if name in explicit), "")
        if doc_name and match and any(name == doc_name and line_no == int(match.group(1)) for name, line_no, _ in spec_lines):
            return [explicit]
    phrases = [scenario.get(key, "") for key in ("trigger", "exception_desc", "expected_result", "name")]
    normalized = [phrase for phrase in (_normalized_phrase(p) for p in phrases) if len(phrase) >= 8]
    matches = []
    for name, line_no, line in spec_lines:
        candidate = _normalized_phrase(line)
        if any(phrase in candidate or (len(candidate) >= 12 and candidate in phrase) for phrase in normalized):
            matches.append(f"{name}:{line_no}")
    return list(dict.fromkeys(matches))


def _finding_branch_match(item: dict[str, Any], scenario: dict[str, Any]) -> bool:
    if item.get("use_case_id") != scenario.get("use_case_id"):
        return False
    sid = str(scenario.get("source_scenario_id") or scenario.get("scenario_id") or "")
    # Prefer explicit branch references in finding text over broad evidence/basis,
    # which may mention multiple neighboring branches.
    direct = " ".join(str(item.get(key, "")) for key in ("exception_desc", "trigger", "expected_result", "scenario_steps"))
    if sid and sid in direct:
        return True
    step_gap = abs(int(item.get("source_step_index", 0) or 0) - int(scenario.get("source_step_index", 0) or 0))
    if step_gap > 1:
        return False
    if sid and sid in str(item.get("basis", "")):
        direct_ids = re.findall(r"[A-Z0-9]+(?:-[A-Z0-9]+)+-\d+\.[a-z]", direct)
        if direct_ids:
            return sid in direct_ids
    item_trigger = _normalized_phrase(" ".join(str(item.get(key, "")) for key in ("trigger", "exception_desc")))
    branch_trigger = _normalized_phrase(" ".join(str(scenario.get(key, "")) for key in ("trigger", "name")))
    # Require a distinctive condition phrase, not generic overlap such as
    # “查询失败”. This accommodates small wording/anchor differences while
    # keeping unrelated exceptions in the same UC separate.
    if item_trigger and branch_trigger:
        shorter, longer = sorted((item_trigger, branch_trigger), key=len)
        if len(shorter) >= 5 and shorter in longer:
            return True
        item_grams = {item_trigger[index:index + 4] for index in range(max(0, len(item_trigger) - 3))}
        branch_grams = {branch_trigger[index:index + 4] for index in range(max(0, len(branch_trigger) - 3))}
        generic = {"不符合要求", "返回失败", "返回资源", "系统提示", "异常触发", "导致失败", "无法正常", "操作失败", "查询失败", "请求失败"}
        if (item_grams & branch_grams) - generic:
            return True
    item_result = _normalized_phrase(item.get("expected_result", ""))
    branch_result = _normalized_phrase(scenario.get("expected_result", ""))
    shorter, longer = sorted((item_result, branch_result), key=len)
    return bool(len(shorter) >= 6 and shorter in longer)


def _scenario_catalog(findings: list[dict[str, Any]], model: dict[str, Any], diagram_manifest: dict[str, Any] | None, source_documents: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    use_cases = use_case_map(normalized)
    spec_lines = _spec_lines(source_documents)
    scenarios: list[dict[str, Any]] = []
    if str(normalized.get("version")) in {"3", "4", "5", "6", "8"}:
        for uc in normalized["use_cases"]:
            for source in uc.get("scenarios", []):
                scenarios.append(_base_scenario(uc, source, normalized, diagram_manifest))
                scenarios[-1]["source_scenario_id"] = source.get("scenario_id", "")
                if spec_lines:
                    sources = _find_spec_sources(scenarios[-1], spec_lines, trust_location=True)
                    scenarios[-1]["spec_sources"] = sources
                    scenarios[-1]["spec_explicitness"] = "yes" if sources else "no"
    for item in findings:
        uc = use_cases[item["use_case_id"]]
        # Requirement branches are authoritative.  A semantic finding that
        # repeats the same explicit exception (same UC/anchor and matching
        # exception text) is evidence for that branch, not a second scenario.
        matching_requirements = []
        for existing in scenarios:
            if existing.get("scenario_type") == "requirement_exception" and _finding_branch_match(item, existing):
                matching_requirements.append(existing)
        if matching_requirements:
            # A finding should map to at most one authoritative branch. If the
            # match is ambiguous, use the branch whose outcome is most similar.
            existing = matching_requirements[0]
            item["merged_requirement_scenario_id"] = existing.get("scenario_id", "")
            existing.setdefault("merged_concern_keys", [])
            if item.get("concern_key") and item["concern_key"] not in existing["merged_concern_keys"]:
                existing["merged_concern_keys"].append(item["concern_key"])
            existing.setdefault("concern_evidence", []).append({
                "concern_key": item.get("concern_key", ""), "concern": item.get("concern", ""),
                "basis": item.get("basis", ""), "candidate_id": item.get("candidate_id", ""),
                "exchange_id": item.get("exchange_id", ""), "ssd_message_id": item.get("ssd_message_id", ""),
                "source_location": item.get("source_location", ""),
            })
            existing.setdefault("merged_candidate_ids", [])
            if item.get("candidate_id") and item["candidate_id"] not in existing["merged_candidate_ids"]:
                existing["merged_candidate_ids"].append(item["candidate_id"])
            existing.setdefault("trace_refs", []).extend(item.get("trace_refs") or [{"exchange_id": item.get("exchange_id", ""), "ssd_message_id": item.get("ssd_message_id", "")}])
            existing.setdefault("mapped_exception_types", []).append(str(item.get("exception_type", "")).strip())
            existing["scenario_source"] = "spec_exception_branch+concern_mapping"
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
            "scenario_source": "concern_completion",
            "spec_explicitness": "unverified" if not spec_lines else "no",
            "spec_sources": [],
        }
        if spec_lines:
            sources = _find_spec_sources(scenario, spec_lines)
            scenario["spec_sources"] = sources
            scenario["spec_explicitness"] = "yes" if sources else "no"
        item["spec_explicitness"] = scenario["spec_explicitness"]
        item["spec_sources"] = list(scenario["spec_sources"])
        item["scenario_source"] = scenario["scenario_source"]
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
        keys = list(dict.fromkeys(key for key in scenario.get("merged_concern_keys", []) if key in CONCERN_DEFINITIONS))
        # The scenario's primary taxonomy should reflect the SR business
        # service classification; AR-backed database evidence remains attached
        # as supporting evidence rather than replacing the SR concern.
        branch_text = _normalized_phrase(" ".join(str(scenario.get(key, "")) for key in ("name", "trigger", "expected_result")))
        preferred = []
        if any(word in branch_text for word in ("重复", "幂等", "并发")):
            preferred.extend(key for key in keys if "concurrency_idempotency" in key or key.endswith(".idempotency"))
        if "格式" in branch_text:
            preferred.extend(key for key in keys if key == "api.data.format")
        if any(word in branch_text for word in ("不存在", "下架", "失效")):
            preferred.extend(key for key in keys if key == "service.query_retrieval.resource_existence")
        primary_key = next((key for key in preferred if key in keys), next((key for key in keys if key.startswith("service.")), keys[0] if keys else ""))
        scenario["concern_keys"] = keys
        scenario["concern_key"] = primary_key
        labels = list(dict.fromkeys(CONCERN_DEFINITIONS[key]["label"] for key in keys))
        scenario["concern"] = "、".join(labels) if labels else "需求异常｜待分类"
        scenario["exception_origin"] = "requirement_branch"
        scenario["exception_type"] = scenario.get("name", "需求异常")
        if "service.query_retrieval.resource_existence" in keys:
            if "下架" in branch_text or "失效" in branch_text or "不可用" in branch_text:
                scenario["exception_type"] = "资源已失效/不可用"
            elif "不存在" in branch_text:
                scenario["exception_type"] = "资源不存在"
        scenario["exception_desc"] = scenario.get("expected_result") or scenario.get("trigger") or scenario.get("name", "需求中明确的异常分支")
        refs = scenario.get("trace_refs", [])
        scenario["trace_refs"] = [dict(item) for item in { (str(ref.get("exchange_id", "")), str(ref.get("ssd_message_id", ""))): ref for ref in refs if ref.get("exchange_id") or ref.get("ssd_message_id") }.values()]
        evidence = scenario.get("concern_evidence", [])
        scenario["concern_evidence"] = list({
            (str(ref.get("candidate_id", "")), str(ref.get("concern_key", "")), str(ref.get("exchange_id", "")), str(ref.get("ssd_message_id", "")), str(ref.get("basis", ""))): ref
            for ref in evidence
        }.values())
        source_predictions.append({
            "prediction_id": prediction_id,
            "scenario_id": scenario.get("scenario_id", ""),
            "use_case_id": scenario.get("use_case_id", ""),
            "use_case_name": scenario.get("use_case_name", ""),
            "actor": scenario.get("actor", ""),
            "source_step_index": scenario.get("source_step_index", 0),
            "anchor_label": scenario.get("anchor_label", ""),
            "concern_key": scenario.get("concern_key", ""),
            "concern": scenario["concern"],
            "concern_keys": keys,
            "exception_origin": "requirement_branch",
            "exception_type": scenario["exception_type"],
            "exception_desc": scenario["exception_desc"],
            "trigger": scenario.get("trigger", ""),
            "expected_result": scenario.get("expected_result", ""),
            "recovery": scenario.get("recovery", ""),
            "scenario_steps": scenario.get("scenario_steps", []),
            "source_location": scenario.get("source_location", ""),
            "source_type": scenario.get("source_type", "requirements"),
            "layer": scenario.get("layer") or "RR",
            "source_node": scenario.get("source_node", ""),
            "target_node": scenario.get("target_node", ""),
            "source_node_name": scenario.get("source_node_name", ""),
            "target_node_name": scenario.get("target_node_name", ""),
            "interaction_message": scenario.get("interaction_message", ""),
            "ssd_message_id": scenario.get("ssd_message_id", ""),
            "exchange_id": scenario.get("exchange_id", ""),
            "spec_explicitness": scenario.get("spec_explicitness", "unverified"),
            "spec_sources": scenario.get("spec_sources", []),
            "scenario_source": scenario.get("scenario_source", "spec_exception_branch"),
            "trace_refs": scenario.get("trace_refs", []),
            "concern_evidence": scenario.get("concern_evidence", []),
        })
    derived = []
    for item in findings:
        merged_id = item.pop("merged_requirement_scenario_id", "")
        if merged_id and merged_id in by_id:
            requirement = by_id[merged_id]
            item["scenario_id"] = merged_id
            item["prediction_id"] = requirement["prediction_id"]
            item["spec_explicitness"] = requirement.get("spec_explicitness", "unverified")
            item["spec_sources"] = list(requirement.get("spec_sources", []))
            item["scenario_source"] = requirement.get("scenario_source", "spec_exception_branch+concern_mapping")
            requirement.setdefault("merged_candidate_ids", [])
            if item.get("candidate_id") and item["candidate_id"] not in requirement["merged_candidate_ids"]:
                requirement["merged_candidate_ids"].append(item["candidate_id"])
            requirement.setdefault("merged_concern_keys", [])
            if item.get("concern_key") not in requirement["merged_concern_keys"]:
                requirement["merged_concern_keys"].append(item.get("concern_key"))
            item["exception_origin"] = "requirement_branch+concern_mapping"
            continue
        scenario = next((candidate for candidate in scenarios if candidate.get("scenario_id") == item.get("scenario_id")), None)
        if scenario:
            scenario["prediction_id"] = item.get("prediction_id", "")
        derived.append(item)
    for prediction in source_predictions:
        requirement = by_id.get(prediction.get("scenario_id"), {})
        if requirement.get("merged_candidate_ids"):
            prediction["merged_candidate_ids"] = list(requirement["merged_candidate_ids"])
            prediction["merged_concern_keys"] = list(requirement.get("merged_concern_keys", []))
    return source_predictions + derived


def _enrich_matrix_findings(matrix_items: list[dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: dict[str, list[dict[str, Any]]] = {}
    merged_index: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        candidate_id = str(finding.get("candidate_id", ""))
        if candidate_id:
            indexed.setdefault(candidate_id, []).append(finding)
        for candidate_id in finding.get("merged_candidate_ids", []):
            merged_index.setdefault(str(candidate_id), []).append(finding)
        else:
            for ref in finding.get("trace_refs") or [{"exchange_id": finding.get("exchange_id", "")}]:
                key = str(ref.get("exchange_id", "")) + "|" + str(finding.get("concern_key", ""))
                indexed.setdefault(key, []).append(finding)
    result = []
    for raw in matrix_items:
        item = dict(raw)
        candidate_id = str(item.get("candidate_id", ""))
        matching = indexed.get(candidate_id, []) or indexed.get(str(item.get("exchange_id", "")) + "|" + str(item.get("concern_key", "")), [])
        merged = merged_index.get(candidate_id, [])
        if merged:
            item["prediction_ids"] = sorted(set(item.get("prediction_ids", [])) | {str(f.get("prediction_id", "")) for f in merged if f.get("prediction_id")})
            item["scenario_ids"] = sorted(set(item.get("scenario_ids", [])) | {str(f.get("scenario_id", "")) for f in merged if f.get("scenario_id")})
        if matching:
            item["findings"] = matching
            item["exception_types"] = sorted({str(f.get("exception_type", "")).strip() for f in matching if str(f.get("exception_type", "")).strip()})
            item["exception_count"] = len(matching)
            item["prediction_ids"] = sorted({str(f.get("prediction_id", "")) for f in matching if f.get("prediction_id")})
            item["scenario_ids"] = sorted({str(f.get("scenario_id", "")) for f in matching if f.get("scenario_id")})
            latest_basis = next((str(f.get("basis", "")).strip() for f in matching if str(f.get("basis", "")).strip()), "")
            if latest_basis:
                item["basis"] = latest_basis
        if item.get("concern_key") == "common.timeout":
            for field in ("requirement_impact", "subsequent_behavior_impact", "environment_coordination_impact"):
                if item.get(field) == "unknown":
                    item[field] = ""
        item.setdefault("exception_count", len(item.get("findings", [])))
        item.setdefault("prediction_ids", [])
        item.setdefault("scenario_ids", [])
        result.append(item)
    return result


def assemble_v3_results(model: dict[str, Any], concern_matrix: Any, semantic_findings: Any, diagram_manifest: dict[str, Any] | None = None, source_documents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    report = validate_scene_model(model)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    normalized = report["normalized_model"]
    matrix_report = validate_concern_matrix(normalized, concern_matrix, require_complete=str(normalized.get("version")) == "8")
    if not matrix_report["valid"]:
        raise ValidationFailure(matrix_report["errors"])
    findings = _normalize_findings(normalized, matrix_report["items"], semantic_findings)
    findings = _merge_equivalent_database_failures(findings, normalized)
    _attach_ids(findings, normalized)
    scenarios = _scenario_catalog(findings, normalized, diagram_manifest, source_documents)
    findings = _link_predictions_to_scenarios(findings, scenarios, normalized)
    matrix_items = _enrich_matrix_findings(matrix_report["items"], findings)
    result_by_key: dict[str, list[dict[str, Any]]] = {key: [] for key in CONCERN_DEFINITIONS}
    for item in findings:
        result_by_key.setdefault(item["concern_key"], []).append(item)
    exception_tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in findings:
        exception_tree.setdefault(item["use_case_id"], {}).setdefault(str(item.get("source_step_index", 0)), []).append(item)
    review_items = list(normalized.get("review_items") or [])
    for item in matrix_report["items"]:
        if item.get("status") == "needs_requirement":
            review_items.append({"type": "concern_requirement_confirmation", "interaction_id": item.get("interaction_id", ""), "exchange_id": item.get("exchange_id", ""), "use_case_id": item.get("use_case_id", ""), "concern_key": item["concern_key"], "message": "需求文档不足以确定该关注点是否适用。"})
        if item.get("status") == "pending_review":
            review_items.append({"type": "concern_review_pending", "interaction_id": item.get("interaction_id", ""), "exchange_id": item.get("exchange_id", ""), "concern_key": item["concern_key"], "message": "该候选关注点尚未完成 Agent 判断。"})
    for scenario in scenarios:
        if scenario.get("scenario_type") == "requirement_exception" and scenario.get("trace_mapping_status") != "mapped":
            review_items.append({"type": "requirement_exception_trace_missing", "use_case_id": scenario.get("use_case_id", ""), "scenario_id": scenario.get("scenario_id", ""), "source_location": scenario.get("source_location", ""), "message": "需求异常分支未能映射到 SSD 请求的来源/目标节点，需人工确认。"})
    manifest_messages: dict[str, list[dict[str, Any]]] = {}
    for entry in (diagram_manifest or {}).get("use_cases", []):
        fused_path = ((entry.get("artifacts") or {}).get("fused") or {}).get("json", "")
        if not fused_path:
            continue
        try:
            manifest_messages[entry.get("use_case_id", "")] = json.loads(open(fused_path, encoding="utf-8").read()).get("messages", [])
        except (OSError, ValueError, TypeError):
            continue
    for edge in normalized["system_composition"].get("edges", []):
        if edge.get("relation") != "uses_external_service" or not edge.get("use_case_id"):
            continue
        external_id = edge.get("to_node", "")
        messages = manifest_messages.get(edge["use_case_id"], [])
        if external_id and not any(external_id in {message.get("from_node"), message.get("to_node")} for message in messages):
            external = node_map(normalized).get(external_id, {})
            review_items.append({"type": "external_dependency_not_in_ssd", "use_case_id": edge["use_case_id"], "node_id": external_id, "source_location": edge.get("source_location", ""), "message": f"架构依赖《{external.get('name', external_id)}》未在该用例融合 SSD 中找到调用消息；需确认调用映射，不据此生成异常。"})
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
        "analysis_layers": concern_matrix.get("analysis_layers", ["SR"]) if isinstance(concern_matrix, dict) else ["SR"],
        "registry_version": CONCERN_REGISTRY_VERSION,
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
    review_items = list(normalized.get("review_items") or [])
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


def assemble_results(model: dict[str, Any], concern_matrix: Any, semantic_findings: Any, diagram_manifest: dict[str, Any] | None = None, source_documents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    if str(normalized.get("version")) in {"3", "4", "5", "6", "8"}:
        return assemble_v3_results(normalized, concern_matrix, semantic_findings, diagram_manifest, source_documents)
    return assemble_v2_results(normalized, concern_matrix, semantic_findings, diagram_manifest)
