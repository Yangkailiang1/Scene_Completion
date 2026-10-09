"""Deterministic, unreviewed generation from the existing model and SSD router."""
from __future__ import annotations

from .assembly import _base_scenario
from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS, plan_concern_matrix
from .schemas import stable_id, validate_scene_model
from .sources import fingerprint, source_refs, target_sections, validate_refs
import re


def availability_labels(keys, trigger, nodes):
    """Bind availability classification to declared component boundaries.

    Exact named subjects are structural metadata; no scenario equivalence or
    applicability is decided here, and no generated candidate is removed.
    """
    original = set(keys)
    availability = {"external_service.availability", "service.dependency.availability"}
    if not original & availability:
        return sorted(original), []
    kinds = {"internal_service" if node["kind"] == "abstract_service" else node["kind"]
             for node in nodes if node.get("kind") in {"internal_service", "external_service", "abstract_service"}
             and re.search(r"(?<![A-Za-z0-9_])" + re.escape(node["name"]) + r"(?![A-Za-z0-9_])", trigger)}
    if kinds == {"internal_service"}:
        corrected = (original - availability) | {"service.dependency.availability"}
    elif kinds == {"external_service"}:
        corrected = (original - availability) | {"external_service.availability"}
    else:
        return sorted(original), []
    adjustment = [{"removed": sorted(original - corrected), "added": sorted(corrected - original),
                   "basis": "原模型明确组件边界与触发条件中的唯一服务主体；未改变场景行为"}] if original != corrected else []
    return sorted(corrected), adjustment


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
        "service.workflow.interruption": ("取消支付", "取消状态", "顾客取消", "用户取消", "流程中止"),
    }
    return [key for key, words in vocabulary.items() if any(word.lower() in text.lower() for word in words)]


def generate_scenes(model: dict, index: dict, ssd_manifest: dict | None = None,
                    analysis_layers: str = "SR", artifact_loader=None) -> dict:
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    matrix = plan_concern_matrix(normalized, ssd_manifest=ssd_manifest, analysis_layers=analysis_layers,
                                 artifact_loader=artifact_loader)
    scenes = []
    for uc in normalized["use_cases"]:
        sources = uc.get("scenarios") or [{"scenario_id": uc["use_case_id"] + "-main",
                                         "scenario_type": "main", "steps": uc["main_flow"]}]
        for source in sources:
            scene = _base_scenario(uc, source, normalized, ssd_manifest, artifact_loader=artifact_loader)
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
            scene["extracted_concern_keys"] = sorted(set(supplied))
            scene["concern_keys"], scene["classification_adjustments"] = availability_labels(
                set(supplied) | set(explicit_concerns(scene)), scene.get("trigger", ""),
                normalized["system_composition"]["nodes"])
            scene["source_refs"] = (validate_refs(source["source_refs"], index) if source.get("source_refs")
                                    else source_refs(index, scene.get("source_location", ""), uc["use_case_id"]))
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
            "preconditions": "待需求确认：到达关联检查步骤的分支前置条件；不继承主成功保证",
            "use_case_preconditions": uc.get("preconditions", "待需求确认"),
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
    # Instantiate independently extracted constraints through the concern
    # method. These records originate from documents, never from checker C.
    for uc in normalized["use_cases"]:
        for rule in uc.get("generation_constraints", []):
            keys = rule.get("concern_keys", [])
            if not keys or any(k not in ACTIVE_CONCERN_KEYS for k in keys):
                raise ValueError("generation constraint needs valid concern labels")
            refs = validate_refs(rule.get("source_refs"), index)
            extracted_keys = sorted(set(keys))
            keys, adjustments = availability_labels(keys, rule["trigger"], normalized["system_composition"]["nodes"])
            # Preserve the independent model annotation; an explicitly stated
            # cancellation condition also belongs to workflow interruption.
            # This labels source content and never decides G/C equivalence.
            workflow = explicit_concerns({**rule, "scenario_type": "requirement_exception"})
            if "service.workflow.interruption" in workflow:
                keys = sorted(set(keys) | {"service.workflow.interruption"})
            candidates = [i for i in matrix["items"] if i["use_case_id"] == uc["use_case_id"]]
            candidates = [i for i in candidates if rule.get("check_node_id")
                          and i.get("subject_node_id") == rule["check_node_id"]
                          and i.get("source_step_index") == rule["source_step_index"]]
            candidates.sort(key=lambda i: i.get("concern_key") not in keys)
            anchor = candidates[0] if candidates else {}
            cid = stable_id("CAND", uc["use_case_id"], rule["constraint_id"], extracted_keys)
            scenes.append({
                "scenario_id": stable_id("GEN", normalized["project"], cid),
                "candidate_id": cid, "constraint_id": rule["constraint_id"],
                "use_case_id": uc["use_case_id"], "use_case_name": uc["use_case_name"],
                "scenario_type": "concern_derived_exception", "generation_status": "constraint_instantiation",
                "name": rule["name"], "trigger": rule["trigger"],
                "preconditions": rule.get("preconditions") or "待需求确认：分支条件见触发",
                "use_case_preconditions": uc.get("preconditions", ""),
                "scenario_steps": rule["scenario_steps"],
                "expected_result": rule.get("expected_result") or "待需求确认",
                "recovery": rule.get("recovery") or "待需求确认",
                "concern_keys": sorted(set(keys)), "extracted_concern_keys": extracted_keys,
                "classification_adjustments": adjustments,
                "concern_label_basis": "；".join(["独立语义抽取标签"]
                    + (["依据明确组件边界修正可用性分类"] if adjustments else [])
                    + (["明确取消条件补充流程中止分类"]
                       if "service.workflow.interruption" in keys
                       and "service.workflow.interruption" not in extracted_keys else [])),
                "source_refs": refs,
                "target_sections": target_sections(index, uc["use_case_id"]),
                "source_step_index": rule["source_step_index"], "subject_node_id": rule.get("check_node_id", ""),
                "check_target_name": rule.get("check_target_name", ""),
                "exchange_id": anchor.get("exchange_id", ""), "ssd_message_id": anchor.get("ssd_message_id", ""),
                "interaction_id": anchor.get("interaction_id", ""), "layer": "SR",
                "trace_mapping_status": "mapped" if anchor else "needs_confirmation",
                "implementation_owner_node_ids": [a["microservice_id"] for a in uc["architecture"].get("ar", [])],
                "implementation_owner_names": [a["microservice_name"] for a in uc["architecture"].get("ar", [])],
                "mount_proposal": ({"components": [a["microservice_name"] for a in uc["architecture"].get("ar", [])],
                    "source_sections": target_sections(index, uc["use_case_id"]),
                    "status": "needs_confirmation", "basis": "关联用例已有实现责任组件；具体业务检查与 SSD 交换位置待核实"} if not anchor else None),
                "trace_mapping_reason": ("实际检查组件与业务步骤均有 SSD 交换" if anchor else
                    "组件/步骤缺少对应 SSD 交换，保留检查对象与来源，待补挂载；未绑定邻近交换"),
                "requires_requirement": "待需求确认" in str(rule.get("expected_result", "")),
                "basis": "将独立抽取的业务/接口约束按关注点实例化；未经适用性审查",
            })
    ids = [s["scenario_id"] for s in scenes]
    if len(ids) != len(set(ids)):
        raise ValueError("generator produced duplicate stable scenario IDs")
    return {"schema_version": "three-agent-v1", "role": "generator", "project": normalized["project"],
            "complete": True, "llm_review_used": False, "analysis_layers": matrix["analysis_layers"],
            "input_hash": fingerprint([normalized, index, ssd_manifest]), "scenario_count": len(scenes),
            "candidate_count": len(matrix["items"]),
            "instantiated_constraint_count": sum(s["generation_status"] == "constraint_instantiation" for s in scenes),
            "scenarios": scenes}
