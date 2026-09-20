"""V2 concern registry, candidate routing, and concern-matrix validation."""

from __future__ import annotations

from typing import Any

from .schemas import CONCERN_STATUSES, ValidationFailure, node_map, stable_id, validate_scene_model


def _definition(key: str, label: str, group: str, description: str, *, draft: bool = False, examples: list[str] | None = None) -> dict[str, Any]:
    return {"key": key, "label": label, "group": group, "description": description, "draft": draft, "examples": examples or []}


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


def _candidate_keys(model: dict[str, Any], interaction: dict[str, Any]) -> list[str]:
    nodes = node_map(model)
    source_kind = _node_kind(nodes, interaction["from_node"])
    target_kind = _node_kind(nodes, interaction["to_node"])
    candidates = ["common.timeout"]
    if source_kind == "human_actor":
        candidates.extend(["human.authentication", "human.authorization", "human.input_data"])
    if interaction.get("api") or interaction.get("is_api") or interaction.get("boundary") == "api":
        candidates.extend(key for key in concern_keys() if key.startswith("api.data."))
    if target_kind == "external_service" and source_kind not in {"external_actor", "external_service"}:
        candidates.extend(["external_service.availability", "external_service.contract"])
    if source_kind == "external_service" and target_kind not in {"external_service", "external_actor"}:
        candidates.extend(["external_service.permission", "external_service.identity"])
    if target_kind == "external_database":
        candidates.extend(["external_database.availability", "external_database.query_performance"])
    if target_kind == "external_llm":
        candidates.extend(["external_llm.availability", "external_llm.contract"])
    if source_kind == "external_llm" and target_kind not in {"external_llm", "external_actor"}:
        candidates.append("external_llm.access_permission")
    if target_kind == "internal_database":
        candidates.extend(key for key in concern_keys() if key.startswith("internal_database."))
    if target_kind == "internal_service":
        candidates.extend(key for key in concern_keys() if key.startswith("internal_service."))
        service_type = nodes[interaction["to_node"]].get("service_type", "unknown")
        if service_type == "display":
            candidates.extend(key for key in concern_keys() if key.startswith("internal_service.display."))
        elif service_type == "compute":
            candidates.extend(key for key in concern_keys() if key.startswith("internal_service.compute."))
    if source_kind == "internal_service" and target_kind == "internal_service" and interaction["from_node"] != interaction["to_node"]:
        candidates.extend(key for key in concern_keys() if key.startswith("service_relation."))
    return sorted(set(candidates))


def plan_concern_matrix(model: dict[str, Any]) -> dict[str, Any]:
    report = validate_scene_model(model)
    if not report["valid"]:
        raise ValidationFailure(report["errors"])
    normalized = report["normalized_model"]
    items = []
    for interaction in sorted(normalized["interactions"], key=lambda item: (item["sequence"], item["interaction_id"])):
        for key in _candidate_keys(normalized, interaction):
            item = {
                "interaction_id": interaction["interaction_id"],
                "concern_key": key,
                "concern": CONCERN_DEFINITIONS[key]["label"],
                "status": "needs_requirement",
                "basis": "待 Agent 根据需求文档判断",
                "exception_types": [],
                "source_location": interaction.get("source_location", ""),
                "findings": [],
            }
            if key == "common.timeout":
                item.update({"requirement_impact": "unknown", "subsequent_behavior_impact": "unknown", "environment_coordination_impact": "unknown"})
            items.append(item)
    return {"version": "2", "project": normalized["project"], "items": items}


def _matrix_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return [item for item in value["items"] if isinstance(item, dict)]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise ValidationFailure(["concern_matrix must be an object with items or a list"])


def validate_concern_matrix(model: dict[str, Any], matrix: Any, raise_on_error: bool = False) -> dict[str, Any]:
    report = validate_scene_model(model)
    errors = list(report.get("errors", []))
    warnings = list(report.get("warnings", []))
    normalized = report.get("normalized_model", model)
    try:
        items = _matrix_items(matrix)
    except ValidationFailure as exc:
        errors.extend(exc.errors)
        items = []
    interactions = {item["interaction_id"]: item for item in normalized.get("interactions", [])}
    expected = {interaction_id: set(_candidate_keys(normalized, interaction)) for interaction_id, interaction in interactions.items()}
    actual: dict[str, set[str]] = {key: set() for key in interactions}
    for index, item in enumerate(items, 1):
        interaction_id = str(item.get("interaction_id", "")).strip()
        concern_key = str(item.get("concern_key", "")).strip()
        if interaction_id not in interactions:
            errors.append(f"matrix item {index}: unknown interaction_id {interaction_id}")
            continue
        if concern_key not in CONCERN_DEFINITIONS:
            errors.append(f"matrix item {index}: unknown concern_key {concern_key}")
            continue
        if concern_key in actual[interaction_id]:
            errors.append(f"duplicate concern matrix item: {interaction_id}/{concern_key}")
        actual[interaction_id].add(concern_key)
        status = item.get("status")
        if status not in CONCERN_STATUSES:
            errors.append(f"matrix item {index}: invalid status {status}")
        if not isinstance(item.get("basis"), str):
            errors.append(f"matrix item {index}: basis must be a string")
        if concern_key == "common.timeout":
            for field in ("requirement_impact", "subsequent_behavior_impact", "environment_coordination_impact"):
                if item.get(field) not in {"yes", "no", "unknown"}:
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
    result = {"valid": not errors, "errors": errors, "warnings": warnings, "normalized_model": normalized, "items": items}
    if raise_on_error and errors:
        raise ValidationFailure(errors)
    return result


def applicable_keys_for_interaction(model: dict[str, Any], interaction_id: str) -> set[str]:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    interaction = next((item for item in normalized["interactions"] if item["interaction_id"] == interaction_id), None)
    if interaction is None:
        raise ValidationFailure([f"unknown interaction_id: {interaction_id}"])
    return set(_candidate_keys(normalized, interaction))
