"""Deterministic, unreviewed generation from the existing model and SSD router."""
from __future__ import annotations

from .assembly import _base_scenario
from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS, plan_concern_matrix
from .schemas import stable_id, validate_scene_model
from .sources import fingerprint, source_refs, target_sections


def explicit_concerns(scenario: dict) -> list[str]:
    """Classify explicit branches; never use this to decide scene equivalence."""
    if scenario["scenario_type"] != "requirement_exception":
        return []
    text = " ".join(str(scenario.get(k, "")) for k in ("name", "trigger", "expected_result"))
    vocabulary = {
        "common.timeout": ("超时", "TIMEOUT"),
        "human.authentication": ("未登录", "认证失败", "凭证", "Token"),
        "human.authorization": ("越权", "无权限", "权限不足"),
        "api.data.completeness": ("必填", "为空", "缺少参数"),
        "api.data.type": ("类型不符", "数据类型"),
        "api.data.format": ("格式错误", "格式非法", "INVALID_PRODUCT_ID"),
        "api.data.range": ("范围", "价格非法", "INVALID_QUERY_PARAM"),
        "external_service.availability": ("服务不可用", "UNAVAILABLE", "连接失败"),
    }
    return [key for key, words in vocabulary.items() if any(word.lower() in text.lower() for word in words)]


def generate_scenes(model: dict, index: dict, ssd_manifest: dict | None = None,
                    analysis_layers: str = "SR") -> dict:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    matrix = plan_concern_matrix(normalized, ssd_manifest=ssd_manifest, analysis_layers=analysis_layers)
    scenes = []
    for uc in normalized["use_cases"]:
        sources = uc.get("scenarios") or [{"scenario_id": uc["use_case_id"] + "-main",
                                         "scenario_type": "main", "steps": uc["main_flow"]}]
        for source in sources:
            scene = _base_scenario(uc, source, normalized, ssd_manifest)
            scene["source_scenario_id"] = scene["scenario_id"]
            scene["scenario_id"] = stable_id("GEN", normalized["project"], scene["scenario_id"])
            if scene["scenario_type"] != "main_success":
                # UC success pre/postconditions are context, not branch outcomes.
                scene["use_case_preconditions"] = uc.get("preconditions", "")
                scene["use_case_postconditions"] = uc.get("postconditions", "")
                scene["preconditions"] = source.get("preconditions") or "待需求确认：该分支前置条件未单独描述"
                scene["postconditions"] = source.get("postconditions") or "待需求确认：该分支后置条件未单独描述"
                scene["expected_result"] = source.get("expected_result") or "待需求确认：该分支预期结果未单独描述"
                scene["recovery"] = source.get("recovery") or "待需求确认：该分支恢复方式未单独描述"
            supplied = source.get("concern_keys", [])
            if source.get("concern_key"):
                supplied = list(supplied) + [source["concern_key"]]
            if not isinstance(supplied, list) or any(key not in ACTIVE_CONCERN_KEYS for key in supplied):
                raise ValueError("invalid supplied explicit concern labels")
            scene["concern_keys"] = sorted(set(supplied) | set(explicit_concerns(scene)))
            scene["source_refs"] = source_refs(index, scene.get("source_location", ""), uc["use_case_id"])
            scene["target_sections"] = target_sections(index, uc["use_case_id"])
            scene["generation_status"] = "explicit"
            scenes.append(scene)
    ucs = {uc["use_case_id"]: uc for uc in normalized["use_cases"]}
    for item in matrix["items"]:
        uc = ucs[item["use_case_id"]]
        definition = CONCERN_DEFINITIONS[item["concern_key"]]
        anchor = item.get("source_step_index", 0)
        prefix = [step["text"] for step in uc["main_flow"] if step.get("step_index", 0) < (anchor or 0)]
        subject = item.get("message") or item.get("relation_evidence") or uc["use_case_name"]
        scenes.append({
            **{key: item.get(key, "") for key in ("candidate_id", "exchange_id", "ssd_message_id",
               "request_message_id", "response_message_id", "interaction_id", "layer", "source_step_index",
               "subject_node_id", "concern_subject", "payload_direction", "source_location")},
            "scenario_id": stable_id("GEN", normalized["project"], item["candidate_id"]),
            "use_case_id": uc["use_case_id"], "use_case_name": uc["use_case_name"],
            "scenario_type": "concern_derived_exception",
            "name": f"{definition['label']}：{subject}",
            "preconditions": uc.get("preconditions", "待需求确认"),
            "trigger": f"执行「{subject}」时：{definition['description']}",
            "scenario_steps": prefix + [f"在「{subject}」检查：{definition['description']}",
                                       "异常响应及恢复方式待需求确认"],
            "expected_result": "待需求确认：应明确该异常下的系统响应",
            "recovery": "待需求确认", "concern_keys": [item["concern_key"]],
            "generation_status": "unreviewed_candidate", "requires_requirement": True,
            "source_refs": source_refs(index, item.get("source_location", ""), uc["use_case_id"]),
            "target_sections": target_sections(index, uc["use_case_id"]),
            "basis": "按现有 SSD 交换与关注点注册表路由生成，未经适用性审查",
        })
    ids = [s["scenario_id"] for s in scenes]
    if len(ids) != len(set(ids)):
        raise ValueError("generator produced duplicate stable scenario IDs")
    return {"schema_version": "three-agent-v1", "role": "generator", "project": normalized["project"],
            "complete": True, "llm_review_used": False, "analysis_layers": matrix["analysis_layers"],
            "input_hash": fingerprint([normalized, index, ssd_manifest]), "scenario_count": len(scenes),
            "candidate_count": len(matrix["items"]), "scenarios": scenes}
