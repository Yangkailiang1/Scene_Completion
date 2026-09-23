"""V6 concern registry, SSD-exchange routing, and matrix validation."""

from __future__ import annotations

from typing import Any

from .schemas import CONCERN_STATUSES, ValidationFailure, interaction_has_api, node_map, stable_id, validate_scene_model


def _definition(key: str, label: str, group: str, description: str, *, draft: bool = False, examples: list[str] | None = None) -> dict[str, Any]:
    subject = "transport" if key == "common.timeout" else (
        "request_payload" if group == "api_data" else
        "source_node" if group == "human" else
        "target_node" if group.startswith(("external", "internal_service")) or group == "internal_database" else
        "relation" if group == "service_relation" else "target_node"
    )
    layers = ["RR", "SR", "AR"] if key == "common.timeout" else (
        ["RR"] if group == "human" else ["SR"] if group.startswith(("external", "sr_service")) else ["AR"] if group.startswith(("internal", "ar_service", "service_relation")) else []
    )
    return {
        "key": key, "label": label, "group": group, "description": description,
        "draft": draft, "examples": examples or [], "concern_subject": subject,
        "layers": layers,
        "evidence_types": ["requirement", "architecture", "interface_contract", "ssd_structure", "domain_rule"],
        "atomic_exception_types": [description],
    }


CONCERN_DEFINITIONS: dict[str, dict[str, Any]] = {}


def _add(key: str, label: str, group: str, description: str, *, draft: bool = False, examples: list[str] | None = None) -> None:
    CONCERN_DEFINITIONS[key] = _definition(key, label, group, description, draft=draft, examples=examples)


_add("common.timeout", "超时关注点", "common", "延时是否影响需求满足、后续行为执行或系统与环境协调")
for key, label, desc in [
    ("authentication", "身份认证", "无凭证、Token 无效或过期"),
    ("authorization", "权限控制", "水平越权或垂直越权"),
    ("input_data", "输入数据", "数据重复、超长、过大或重复点击"),
]:
    _add(f"human.{key}", label, "human", desc)
for key, label, desc in [
    ("completeness", "数据完整性", "必填数据缺失或请求体为空"),
    ("type", "数据类型", "数据类型与接口定义不符"),
    ("format", "数据格式", "数据不满足格式规范"),
    ("length", "数据长度", "字符串长度超过限制"),
    ("size", "数据大小", "文件或请求体超过限制"),
    ("range", "数据范围", "数值超出允许范围"),
    ("legality", "数据合法性", "非法字符、不允许字段或非法取值"),
]:
    _add(f"api.data.{key}", label, "api_data", desc)
for key, label, desc in [
    ("availability", "外部服务可用性", "服务不可用、连接失败或调用失败"),
    ("contract", "外部接口契约", "返回字段缺失、格式改变或版本不兼容"),
    ("permission", "调用权限", "调用方无权限或权限过期"),
    ("identity", "调用方身份", "调用方身份不明或身份过期"),
]:
    _add(f"external_service.{key}", label, "external_service", desc)
_add("external_database.availability", "数据库服务可用性", "external_database", "连接失败或数据库不可用")
_add("external_database.query_performance", "查询性能", "external_database", "外部数据库查询超时")
_add("external_llm.availability", "外部模型可用性", "external_llm", "模型服务不可用、连接失败或认证失败")
_add("external_llm.contract", "外部接口契约", "external_llm", "LLM 输出字段、格式或版本不符合约定")
_add("external_llm.access_permission", "访问权限", "external_llm", "外部模型调用本系统时无权限")
for key, label, desc in [
    ("semantic_correctness", "语义正确性", "模型输出语义错误或与业务目标不一致"),
    ("instruction_following", "指令遵循", "模型未遵循系统或用户指令"),
    ("prompt_security", "提示词安全", "提示词注入、越权指令或敏感信息泄露"),
    ("context_completeness", "上下文完整性", "模型调用缺少必要上下文"),
    ("output_stability", "输出稳定性", "相同输入输出结构或结果不稳定"),
]:
    _add(f"external_llm.quality.{key}", label, "external_llm_quality", desc, draft=True)
for key, label, desc in [
    ("required_field_completeness", "必填字段完整性", "必要字段缺失"),
    ("uniqueness", "唯一性约束", "名称重复或唯一键冲突"),
    ("field_validity", "字段合法性", "类型错误、非法字符或超长"),
    ("resource_existence", "资源存在性", "查询、修改或删除不存在资源"),
    ("availability", "数据库可用性", "连接失败或数据库宕机"),
    ("persistence", "持久化能力", "写入失败或事务回滚"),
    ("referential_consistency", "关联一致性", "级联删除失效或子对象残留"),
    ("query_performance", "查询性能", "大表联查超时"),
    ("idempotency", "幂等性", "重复请求导致重复操作异常"),
    ("concurrency_consistency", "并发一致性", "并发更新冲突或后写覆盖前写"),
]:
    _add(f"internal_database.{key}", label, "internal_database", desc)
for key, label, desc in [
    ("parameter_validity", "参数有效性", "参数缺失、非法字符、超长或类型不匹配"),
    ("uniqueness", "唯一性约束", "重名或唯一键冲突"),
    ("resource_existence", "资源存在性", "访问不存在资源"),
    ("state_constraint", "状态约束", "当前状态不允许执行操作"),
    ("business_integrity", "业务完整性", "配置缺失或引用对象不完整"),
    ("availability", "服务可用性", "内部处理失败或超时"),
    ("protocol_compatibility", "协议兼容性", "协议、字段格式或版本不一致"),
]:
    _add(f"internal_service.{key}", label, "internal_service", desc)
for key, label, desc in [
    ("parameter_validity", "参数有效性", "参数不满足展示服务接口约束"),
    ("output_completeness", "输出完整性", "展示结果缺少必要字段或内容"),
    ("output_consistency", "输出一致性", "展示结果与当前内部状态不一致"),
    ("availability", "服务可用性", "展示服务不可用或处理失败"),
    ("protocol_compatibility", "协议兼容性", "展示接口协议或字段不兼容"),
    ("timeout", "超时关注点", "展示等待超过要求，影响后续流程或交互"),
]:
    _add(f"internal_service.display.{key}", label, "internal_service_display", desc, draft=True)
for key, label, desc in [
    ("parameter_validity", "参数有效性", "计算参数缺失、非法或类型不匹配"),
    ("calculation_correctness", "计算正确性和精度", "计算结果错误或精度不满足要求"),
    ("business_integrity", "业务完整性", "计算所需配置或引用对象不完整"),
    ("state_constraint", "状态约束", "当前业务状态不允许计算"),
    ("availability", "服务可用性", "计算服务失败或不可用"),
    ("idempotency", "幂等性", "重复计算或重复提交造成错误副作用"),
    ("concurrency_consistency", "并发一致性", "并发计算或更新产生冲突"),
    ("protocol_compatibility", "协议兼容性", "计算接口协议或版本不兼容"),
    ("timeout", "超时关注点", "计算延时影响业务后续行为"),
]:
    _add(f"internal_service.compute.{key}", label, "internal_service_compute", desc, draft=True)
for prefix, entries in {
    "display_interaction": [
        ("display_correctness", "显示正确性", "展示内容与业务结果不一致"),
        ("render_performance", "渲染性能", "渲染耗时影响用户后续操作"),
    ],
    "query_retrieval": [
        ("resource_existence", "资源存在性", "查询资源不存在或已失效"),
        ("result_correctness", "结果正确性", "查询结果错误或不完整"),
        ("data_visibility", "数据可见性", "应展示数据未被正确返回或被错误暴露"),
    ],
    "resource_mutation": [
        ("business_constraint", "业务约束", "当前业务条件不满足变更要求"),
        ("persistence_consistency", "持久化一致性", "操作结果未可靠持久化或局部成功"),
        ("idempotency", "幂等性", "重复请求导致重复变更"),
        ("concurrency_consistency", "并发一致性", "并发变更产生覆盖或冲突"),
    ],
    "analysis_generation": [
        ("result_correctness", "处理正确性", "分析或生成结果错误"),
        ("execution_deadline", "执行时限", "处理耗时影响业务后续行为"),
        ("resource_consumption", "资源消耗", "处理消耗超过可接受资源范围"),
    ],
    "release_activation": [
        ("prerequisite", "发布前置条件", "发布前置条件未满足仍执行发布"),
        ("result_consistency", "发布结果一致性", "发布状态与实际生效状态不一致"),
        ("failure_recovery", "失败恢复", "发布失败后未恢复或留下半成品状态"),
    ],
}.items():
    for key, label, desc in entries:
        _add(f"sr_service.{prefix}.{key}", label, f"sr_service_{prefix}", desc, draft=True)

# AR service classifications describe implementation responsibility, not the
# business function of the RR use case. These first-release concerns are
# intentionally draft and only routed for a classified AR mapping.
for category, key, label, desc in [
    ("query_read", "result_correctness", "AR 查询结果正确性", "实现查询返回错误、遗漏或包含不应可见的数据"),
    ("command_write", "state_transition_consistency", "AR 状态变更一致性", "实现写操作未按允许的状态迁移规则完成"),
    ("orchestration", "partial_failure_recovery", "AR 编排部分失败恢复", "跨组件编排部分成功后未补偿或恢复"),
    ("integration_event", "event_identity", "AR 事件身份与去重", "外部回调或事件身份无法验证，或重复事件未被识别"),
    ("publish_activation", "activation_consistency", "AR 激活一致性", "发布/激活结果与实际生效状态不一致"),
]:
    _add(f"ar_service.{category}.{key}", label, f"ar_service_{category}", desc, draft=True)
for key, label, desc in [
    ("call_order", "调用顺序", "前置操作未完成就执行后续操作"),
    ("dependency_consistency", "依赖一致性", "被依赖资源不存在或失效"),
    ("cascade_operation", "级联操作", "漏删、误删或级联失败"),
    ("cross_service_consistency", "跨服务数据一致性", "一侧成功、一侧失败或版本不一致"),
    ("idempotency", "幂等性", "重复请求导致重复执行"),
    ("concurrency_consistency", "并发一致性", "并发修改或删除产生冲突"),
]:
    _add(f"service_relation.{key}", label, "service_relation", desc)


def list_concerns() -> list[dict[str, Any]]:
    return [dict(value) for value in CONCERN_DEFINITIONS.values()]


def concern_keys() -> set[str]:
    return set(CONCERN_DEFINITIONS)


def _node_kind(nodes: dict[str, dict[str, Any]], node_id: str) -> str:
    return nodes.get(node_id, {}).get("kind", "")


def _concern_kind(kind: str) -> str:
    return "internal_service" if kind in {"abstract_service", "implementation_api"} else kind


def _is_system_boundary(node: dict[str, Any]) -> bool:
    """The RR system node is a boundary, not an analyzable AR service."""
    return bool(node) and (node.get("node_id") == "system" or node.get("layer") == "RR")


def _functional_keys(service_type: str, prefix: str) -> list[str]:
    if service_type not in {"display_interaction", "query_retrieval", "resource_mutation", "analysis_generation", "release_activation"}:
        return []
    prefix = f"{prefix}.{service_type}."
    return sorted(key for key in concern_keys() if key.startswith(prefix))


def _use_case_architecture(model: dict[str, Any], interaction: dict[str, Any]) -> dict[str, Any]:
    uc = next((item for item in model.get("use_cases", []) if item.get("use_case_id") == interaction.get("use_case_id")), {})
    return uc.get("architecture") or {}


def _sr_mapping_for_interaction(model: dict[str, Any], interaction: dict[str, Any]) -> dict[str, Any] | None:
    sr = _use_case_architecture(model, interaction).get("sr") or {}
    if not isinstance(sr, dict):
        return None
    endpoints = {str(interaction.get("from_node", "")), str(interaction.get("to_node", ""))}
    service_id = str(sr.get("service_id", ""))
    if service_id in endpoints:
        return sr
    return None


def _ar_mapping_for_interaction(model: dict[str, Any], interaction: dict[str, Any]) -> dict[str, Any] | None:
    endpoints = {str(interaction.get("from_node", "")), str(interaction.get("to_node", ""))}
    for component in _use_case_architecture(model, interaction).get("ar") or []:
        if not isinstance(component, dict):
            continue
        mapped_endpoints = {str(component.get("microservice_id", "")), str(component.get("implementation_api_node_id", "")), str(component.get("implementation_api_id", ""))}
        if endpoints & mapped_endpoints:
            return component
    return None


def _mapping_endpoint(interaction: dict[str, Any], mapping: dict[str, Any], layer: str) -> str:
    endpoints = [str(interaction.get("from_node", "")), str(interaction.get("to_node", ""))]
    if layer == "SR":
        service_id = str(mapping.get("service_id", ""))
        return service_id if service_id in endpoints else next((value for value in endpoints if value), "")
    mapped_ids = {str(mapping.get("microservice_id", "")), str(mapping.get("implementation_api_node_id", ""))}
    return next((value for value in endpoints if value in mapped_ids), next((value for value in endpoints if value), ""))


def _candidate_keys(model: dict[str, Any], interaction: dict[str, Any]) -> list[str]:
    nodes = node_map(model)
    source_node = nodes.get(interaction.get("from_node"), {})
    target_node = nodes.get(interaction.get("to_node"), {})
    source_kind = _concern_kind(source_node.get("kind", ""))
    target_kind = _concern_kind(target_node.get("kind", ""))
    modern = str(model.get("version")) in {"6", "7", "8"}
    candidates = ["common.timeout"]
    if source_kind == "human_actor":
        candidates.extend(["human.authentication", "human.authorization", "human.input_data"])
    if interaction_has_api(interaction) or interaction.get("is_api") or interaction.get("boundary") == "api":
        candidates.extend(key for key in concern_keys() if key.startswith("api.data."))
    if target_kind == "external_service" and source_kind not in {"external_actor", "external_service"}:
        candidates.extend(["external_service.availability", "external_service.contract"])
    if source_kind == "external_service" and target_kind not in {"external_service", "external_actor"}:
        candidates.extend(["external_service.permission", "external_service.identity"])
    if target_kind == "external_database":
        candidates.extend(["external_database.availability", "external_database.query_performance"])
    if target_kind == "external_llm":
        candidates.extend(["external_llm.availability", "external_llm.contract"])
        if modern:
            candidates.extend(key for key in concern_keys() if key.startswith("external_llm.quality."))
    if source_kind == "external_llm" and target_kind not in {"external_llm", "external_actor"}:
        candidates.append("external_llm.access_permission")
    if target_kind == "internal_database":
        candidates.extend(key for key in concern_keys() if key.startswith("internal_database."))
    if modern:
        sr_mapping = _sr_mapping_for_interaction(model, interaction)
        if sr_mapping and sr_mapping.get("service_type") in {"display_interaction", "query_retrieval", "resource_mutation", "analysis_generation", "release_activation"}:
            candidates.extend(_functional_keys(str(sr_mapping["service_type"]), "sr_service"))
        ar_mapping = _ar_mapping_for_interaction(model, interaction)
        if ar_mapping:
            candidates.extend(key for key in concern_keys() if key.startswith("internal_service.") and key.count(".") == 1)
            ar_type = str(ar_mapping.get("service_type", "unknown"))
            if ar_type != "unknown":
                candidates.extend(key for key in concern_keys() if key.startswith(f"ar_service.{ar_type}."))
    elif target_kind == "internal_service" and not _is_system_boundary(target_node) and target_node.get("layer") == "AR" and target_node.get("kind") in {"internal_service", "implementation_api"}:
        candidates.extend(key for key in concern_keys() if key.startswith("internal_service."))
        service_type = target_node.get("legacy_service_type", target_node.get("service_type", "unknown"))
        if service_type == "display":
            candidates.extend(key for key in concern_keys() if key.startswith("internal_service.display."))
        elif service_type == "compute":
            candidates.extend(key for key in concern_keys() if key.startswith("internal_service.compute."))
    if source_kind == "internal_service" and target_kind == "internal_service" and interaction["from_node"] != interaction["to_node"] and source_node.get("layer") in {"SR", "AR"} and target_node.get("layer") in {"SR", "AR"}:
        candidates.extend(key for key in concern_keys() if key.startswith("service_relation."))
    # Endpoint devices and deployment/runtime nodes are intentionally out of scope.
    if source_node.get("kind") in {"connection_device", "deployment_hardware", "runtime_environment"} or target_node.get("kind") in {"connection_device", "deployment_hardware", "runtime_environment"}:
        candidates = [key for key in candidates if key == "common.timeout"]
    return sorted(set(candidates))


def _fused_exchanges(model: dict[str, Any], fused_ssd: Any) -> list[dict[str, Any]]:
    if not fused_ssd:
        return []
    value = fused_ssd.get("fused", fused_ssd) if isinstance(fused_ssd, dict) else fused_ssd
    messages = value.get("messages", []) if isinstance(value, dict) else []
    if not isinstance(messages, list):
        raise ValidationFailure(["fused SSD messages must be a list"])
    known = {item["interaction_id"] for item in model.get("interactions", [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, raw in enumerate(messages, 1):
        if not isinstance(raw, dict):
            raise ValidationFailure([f"fused SSD message {index} must be an object"])
        exchange_id = raw.get("exchange_id") or stable_id("EXCH", raw.get("use_case_id"), raw.get("ssd_sequence", index))
        if raw.get("interaction_id") in known or str(value.get("version", "3")) in {"4", "5", "6", "7", "8"}:
            grouped.setdefault(exchange_id, []).append(dict(raw))
    result = []
    for exchange_id, members in grouped.items():
        members.sort(key=lambda item: item.get("ssd_sequence", item.get("sequence", 0)))
        request = next((item for item in members if item.get("message_kind") in {"request", "event", "internal_call"}), members[0])
        response = next((item for item in members if item.get("message_kind") in {"response", "internal_return", "feedback"} and item.get("message_id") != request.get("message_id")), None)
        interaction_id = request.get("interaction_id", "")
        exchange = dict(request)
        exchange["exchange_id"] = request.get("exchange_id") or exchange_id
        exchange["matrix_key"] = exchange["exchange_id"]
        exchange["ssd_message_id"] = request.get("message_id", "")
        exchange["request_message_id"] = request.get("message_id", "")
        exchange["response_message_id"] = response.get("message_id", "") if response else ""
        exchange["message"] = request.get("message", "")
        exchange["response_message"] = response.get("message", "") if response else ""
        exchange["response_fields"] = response.get("response_fields", []) if response else request.get("response_fields", [])
        result.append(exchange)
    return result


def _manifest_fused_ssds(ssd_manifest: Any) -> list[dict[str, Any]]:
    if not ssd_manifest:
        return []
    entries = ssd_manifest.get("use_cases", []) if isinstance(ssd_manifest, dict) else []
    result = []
    for entry in entries:
        artifact = (entry.get("artifacts") or {}).get("fused") if isinstance(entry, dict) else None
        path = artifact.get("json") if isinstance(artifact, dict) else ""
        if path:
            from pathlib import Path
            result.append(__import__("json").loads(Path(path).read_text(encoding="utf-8")))
    return result


def plan_concern_matrix(model: dict[str, Any], fused_ssd: Any = None, ssd_manifest: Any = None) -> dict[str, Any]:
    report = validate_scene_model(model)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    normalized = report["normalized_model"]
    items = []
    fused_values = ([fused_ssd] if fused_ssd else []) + _manifest_fused_ssds(ssd_manifest)
    interactions: list[dict[str, Any]] = []
    for value in fused_values:
        interactions.extend(_fused_exchanges(normalized, value))
    if not fused_values:
        interactions = normalized["interactions"]
    if fused_values and not interactions:
        raise ValidationFailure(["fused SSD has no messages linked to model interactions"])
    for interaction in sorted(interactions, key=lambda item: (item.get("sequence", 0), item.get("interaction_id", ""))):
        for key in _candidate_keys(normalized, interaction):
            definition = CONCERN_DEFINITIONS[key]
            sr_mapping = _sr_mapping_for_interaction(normalized, interaction) if key.startswith("sr_service.") else None
            ar_mapping = _ar_mapping_for_interaction(normalized, interaction) if key.startswith("ar_service.") or (key.startswith("internal_service.") and key.count(".") == 1) else None
            mapped_service = sr_mapping or ar_mapping or {}
            concern_subject = definition.get("concern_subject", "target_node")
            if sr_mapping:
                subject_node_id = _mapping_endpoint(interaction, sr_mapping, "SR")
                service_layer = "SR"
            elif ar_mapping:
                subject_node_id = _mapping_endpoint(interaction, ar_mapping, "AR")
                service_layer = "AR"
            else:
                subject_node_id = interaction.get("from_node", "") if concern_subject == "source_node" else interaction.get("to_node", "")
                service_layer = interaction.get("layer", "")
            item = {
                "use_case_id": interaction.get("use_case_id", ""),
                "interaction_id": interaction.get("interaction_id", interaction.get("exchange_id", "")),
                "concern_key": key,
                "concern": definition["label"],
                "status": "pending_review" if str(normalized.get("version")) == "6" else "needs_requirement",
                "basis": "待 Agent 根据需求、接口契约、SSD 结构和对象类型判断" if str(normalized.get("version")) == "6" else "待 Agent 根据需求文档判断",
                "evidence_types": [],
                "concern_subject": concern_subject,
                "subject_node_id": subject_node_id,
                "layer": service_layer,
                "service_classification": mapped_service.get("service_type", ""),
                "classification_status": mapped_service.get("classification_status", ""),
                "classification_basis": mapped_service.get("classification_basis", ""),
                "exception_types": [],
                "source_location": interaction.get("source_location", ""),
                "findings": [],
            }
            for field in ("ssd_id", "message_id", "message", "layer", "source_step_index", "from_node", "to_node", "api", "interface_id", "abstract_api_id", "api_method", "resource_path", "implementation_api_id", "service_id", "exchange_id", "ssd_message_id", "request_message_id", "response_message_id", "response_message"):
                if field in interaction and field != "layer":
                    item[{"message_id": "ssd_message_id"}.get(field, field)] = interaction[field]
            if key == "common.timeout":
                item.update({"requirement_impact": "unknown", "subsequent_behavior_impact": "unknown", "environment_coordination_impact": "unknown"})
            items.append(item)
    result = {"version": str(normalized.get("version", "6")), "project": normalized["project"], "items": items}
    if fused_values:
        result["ssd_ids"] = [value.get("fused", value).get("ssd_id", "") for value in fused_values if isinstance(value.get("fused", value), dict)]
        result["interaction_ids"] = sorted({item["interaction_id"] for item in interactions if item.get("interaction_id")})
        result["exchange_ids"] = sorted({item["exchange_id"] for item in interactions if item.get("exchange_id")})
    return result


def audit_concern_coverage(model: dict[str, Any], matrix: Any, ssd_manifest: Any = None) -> dict[str, Any]:
    """Strict run gate plus distribution diagnostics for agent review."""
    validation = validate_concern_matrix(model, matrix, require_complete=True)
    items = _matrix_items(matrix)
    non_data_applicable = sorted({item.get("concern_key") for item in items if item.get("status") == "applicable" and not str(item.get("concern_key", "")).startswith("api.data.")})
    data_applicable = sorted({item.get("concern_key") for item in items if item.get("status") == "applicable" and str(item.get("concern_key", "")).startswith("api.data.")})
    warnings = list(validation.get("warnings", []))
    if data_applicable and not non_data_applicable and any(not str(item.get("concern_key", "")).startswith("api.data.") and item.get("status") != "not_applicable" for item in items):
        warnings.append("applicable findings are concentrated in api.data.* while other routed concerns remain reviewed without applicable findings")
    normalized = validation.get("normalized_model", {})
    expected_ucs = {uc.get("use_case_id") for uc in normalized.get("use_cases", [])}
    covered_ucs = {item.get("use_case_id") for item in items}
    missing_ucs = sorted(expected_ucs - covered_ucs)
    if missing_ucs:
        validation.setdefault("errors", []).append(f"concern matrix missing use cases: {', '.join(missing_ucs)}")
    validation["warnings"] = warnings
    validation["valid"] = not validation.get("errors")
    validation["report"] = {"use_case_count": len(expected_ucs), "covered_use_case_count": len(covered_ucs), "missing_use_cases": missing_ucs, "applicable_keys": sorted({item.get("concern_key") for item in items if item.get("status") == "applicable"}), "candidate_count": len(items)}
    return validation


def _matrix_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return [item for item in value["items"] if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise ValidationFailure(["concern_matrix must be an object with items or a list"])


def validate_concern_matrix(model: dict[str, Any], matrix: Any, raise_on_error: bool = False, require_complete: bool = False) -> dict[str, Any]:
    report = validate_scene_model(model)
    errors = list(report.get("errors", []))
    warnings = list(report.get("warnings", []))
    normalized = report.get("normalized_model", model)
    try:
        items = _matrix_items(matrix)
    except ValidationFailure as exc:
        errors.extend(exc.errors)
        items = []
    all_interactions = {item["interaction_id"]: item for item in normalized.get("interactions", [])}
    is_v4 = str(normalized.get("version")) in {"4", "5", "6"}
    scoped_ids = set(matrix.get("interaction_ids", [])) if isinstance(matrix, dict) else set()
    interactions = {key: value for key, value in all_interactions.items() if not scoped_ids or key in scoped_ids}
    expected = {interaction_id: set(_candidate_keys(normalized, interaction)) for interaction_id, interaction in interactions.items()}
    if is_v4 and isinstance(matrix, dict) and matrix.get("exchange_ids"):
        expected = {}
        for item in _matrix_items(matrix):
            exchange_id = str(item.get("exchange_id", "")).strip()
            if exchange_id:
                expected.setdefault(exchange_id, set()).add(str(item.get("concern_key", "")))
        # V4 planning records are authoritative for exchange coverage.  Their
        # candidate set is checked below against the routing function.
        exchange_messages = {item.get("exchange_id"): item for item in items if item.get("exchange_id")}
        for exchange_id, message in exchange_messages.items():
            expected[exchange_id] = set(_candidate_keys(normalized, message))
    actual: dict[str, set[str]] = {key: set() for key in expected}
    for index, item in enumerate(items, 1):
        interaction_id = str(item.get("interaction_id", "")).strip()
        concern_key = str(item.get("concern_key", "")).strip()
        exchange_id = str(item.get("exchange_id", "")).strip()
        identity = exchange_id if is_v4 and exchange_id else interaction_id
        if identity not in expected:
            errors.append(f"matrix item {index}: unknown matrix identity {identity or interaction_id}")
            continue
        if concern_key not in CONCERN_DEFINITIONS:
            errors.append(f"matrix item {index}: unknown concern_key {concern_key}")
            continue
        if concern_key in actual[identity]:
            errors.append(f"duplicate concern matrix item: {identity}/{concern_key}")
        actual[identity].add(concern_key)
        status = item.get("status")
        if status not in CONCERN_STATUSES:
            errors.append(f"matrix item {index}: invalid status {status}")
        if not isinstance(item.get("basis"), str):
            errors.append(f"matrix item {index}: basis must be a string")
        if status == "pending_review" and require_complete:
            errors.append(f"matrix item {index}: pending_review is not allowed in a complete matrix")
        if status in {"applicable", "not_applicable", "needs_requirement"} and not item.get("basis", "").strip():
            errors.append(f"matrix item {index}: reviewed status requires non-empty basis")
        if status in {"applicable", "not_applicable", "needs_requirement"} and not isinstance(item.get("evidence_types", []), list):
            errors.append(f"matrix item {index}: evidence_types must be a list")
        if require_complete and status == "needs_requirement" and "待 Agent" in item.get("basis", ""):
            errors.append(f"matrix item {index}: needs_requirement must identify missing requirement evidence")
        if require_complete and status == "not_applicable" and "待 Agent" in item.get("basis", ""):
            errors.append(f"matrix item {index}: not_applicable must provide an exclusion basis")
        if concern_key == "common.timeout":
            for field in ("requirement_impact", "subsequent_behavior_impact", "environment_coordination_impact"):
                if item.get(field) not in {"yes", "no", "unknown", "", None}:
                    errors.append(f"matrix item {index}: invalid {field}")
            impact = [item.get(field) for field in ("requirement_impact", "subsequent_behavior_impact", "environment_coordination_impact")]
            if item.get("status") == "applicable" and "yes" not in impact:
                errors.append(f"matrix item {index}: applicable timeout needs at least one yes impact")
    for interaction_id, keys in expected.items():
        missing = sorted(keys - actual.get(interaction_id, set()))
        extra = sorted(actual.get(interaction_id, set()) - keys)
        if missing:
            errors.append(f"{interaction_id}: missing concern keys: {', '.join(missing)}")
        if extra:
            errors.append(f"{interaction_id}: non-applicable concern keys: {', '.join(extra)}")
    coverage = {
        "total": len(items),
        "pending_review": sum(1 for item in items if item.get("status") == "pending_review"),
        "applicable": sum(1 for item in items if item.get("status") == "applicable"),
        "not_applicable": sum(1 for item in items if item.get("status") == "not_applicable"),
        "needs_requirement": sum(1 for item in items if item.get("status") == "needs_requirement"),
    }
    result = {"valid": not errors, "errors": errors, "warnings": warnings, "normalized_model": normalized, "items": items, "coverage": coverage}
    if raise_on_error and errors:
        raise ValidationFailure(errors)
    return result


def applicable_keys_for_interaction(model: dict[str, Any], interaction_id: str) -> set[str]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    interaction = next((item for item in normalized["interactions"] if item["interaction_id"] == interaction_id), None)
    if interaction is None:
        raise ValidationFailure([f"unknown interaction_id: {interaction_id}"])
    return set(_candidate_keys(normalized, interaction))
