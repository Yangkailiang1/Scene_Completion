"""Layered RR/SR/AR SSD generation and deterministic validation."""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .schemas import ValidationFailure, node_map, stable_id, use_case_map, validate_scene_model
from .svg_renderer import render_ssd_svg
from .png_renderer import convert_svg_to_png


SSD_LAYERS = {"RR", "SR", "AR", "fused"}
MESSAGE_KINDS = {"request", "response", "event", "internal_call", "internal_return", "feedback"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _escape(value: Any) -> str:
    return _text(value).replace('"', "'").replace("\n", "\\n")


def _nodes(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return node_map(model)


def _node_by_name(model: dict[str, Any], name: str, allowed: set[str] | None = None) -> dict[str, Any] | None:
    for node in model.get("system_composition", {}).get("nodes", []):
        if node.get("name") == name and (allowed is None or node.get("kind") in allowed):
            return node
    return None


def _system_node(model: dict[str, Any]) -> dict[str, Any]:
    nodes = _nodes(model)
    return nodes.get("system") or next((node for node in nodes.values() if node.get("name") == model.get("system_name")), {})


def _architecture(uc: dict[str, Any]) -> dict[str, Any]:
    return uc.get("architecture") or {}


def _actor_node(model: dict[str, Any], actor: str) -> dict[str, Any] | None:
    return _node_by_name(model, actor, {"human_actor", "external_actor", "external_service"})


def _primary_interaction(model: dict[str, Any], uc: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [item for item in model.get("interactions", []) if item.get("use_case_id") == uc["use_case_id"]]
    nodes = _nodes(model)
    candidates.sort(key=lambda item: (item.get("sequence", 0), item.get("interaction_id", "")))
    for item in candidates:
        source = nodes.get(item.get("from_node"), {})
        target = nodes.get(item.get("to_node"), {})
        if target.get("node_id") == "system" or source.get("kind") in {"human_actor", "external_actor"}:
            return item
    return candidates[0] if candidates else None


def _message(*, ssd_id: str, use_case_id: str, layer: str, sequence: int, exchange_id: str,
             source_step_index: int, source_location: str, source: str, target: str,
             text: str, kind: str, phase: int, interaction_id: str = "",
             explicit: bool = True, **fields: Any) -> dict[str, Any]:
    result = {
        "message_id": stable_id("MSG", ssd_id, exchange_id, kind, sequence, source, target),
        "exchange_id": exchange_id,
        "interaction_id": interaction_id,
        "use_case_id": use_case_id,
        "ssd_id": ssd_id,
        "layer": layer,
        "ssd_sequence": sequence,
        "sequence": sequence,
        "source_step_index": source_step_index,
        "source_location": source_location,
        "from_node": source,
        "to_node": target,
        "message": text,
        "message_kind": kind,
        "explicitness": "explicit" if explicit else "inferred",
        "direction": "internal",
        "request_fields": [],
        "response_fields": [],
        "phase": phase,
    }
    result.update(fields)
    return result


def _actor_action(text: str, actors: list[str]) -> bool:
    return any(actor and actor in text for actor in actors) and not text.startswith(("系统", "在线商城系统"))


def _feedback(text: str) -> bool:
    return text.startswith(("系统返回", "系统展示", "系统提示", "系统向", "系统进入", "系统保存", "系统记录"))


def _rr_messages(model: dict[str, Any], uc: dict[str, Any], ssd_id: str) -> list[dict[str, Any]]:
    actors = uc.get("actors", []) or ["Actor"]
    actor_node = next((_actor_node(model, actor) for actor in actors if _actor_node(model, actor)), None)
    system = _system_node(model)
    if not system:
        raise ValidationFailure(["scene model needs a system node"])
    actor_id = actor_node.get("node_id") if actor_node else stable_id("NODE", "actor", actors[0])
    messages: list[dict[str, Any]] = []
    sequence = 1
    for step in uc.get("main_flow", []):
        text = step["text"]
        index = int(step["step_index"])
        location = step.get("source_location") or uc.get("source_location", "")
        exchange = stable_id("EXCH", uc["use_case_id"], "RR", index)
        if _actor_action(text, actors):
            request = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="RR", sequence=sequence,
                               exchange_id=exchange, source_step_index=index, source_location=location,
                               source=actor_id, target=system["node_id"], text=text, kind="request", phase=10)
            request["direction"] = "incoming"
            messages.append(request)
            sequence += 1
            response = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="RR", sequence=sequence,
                                exchange_id=exchange, source_step_index=index, source_location=location,
                                source=system["node_id"], target=actor_id, text=f"系统受理：{text}",
                                kind="feedback", phase=90, explicit=False)
            response.update({"direction": "outgoing", "reply_to_message_id": request["message_id"],
                             "inference_basis": "RR 层只表达业务受理和可见反馈，不展开具体接口。"})
            messages.append(response)
            sequence += 1
        elif _feedback(text):
            feedback = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="RR", sequence=sequence,
                                exchange_id=exchange, source_step_index=index, source_location=location,
                                source=system["node_id"], target=actor_id, text=text, kind="feedback", phase=90)
            feedback["direction"] = "outgoing"
            messages.append(feedback)
            sequence += 1
    if not any(item.get("to_node") == actor_id and item.get("message_kind") == "feedback" for item in messages):
        last = uc.get("main_flow", [])[-1] if uc.get("main_flow") else {"step_index": 1, "text": "完成用例"}
        exchange = stable_id("EXCH", uc["use_case_id"], "RR", last["step_index"], "final")
        messages.append(_message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="RR", sequence=sequence,
                                 exchange_id=exchange, source_step_index=last["step_index"],
                                 source_location=last.get("source_location", ""), source=system["node_id"],
                                 target=actor_id, text=f"系统返回：{uc.get('postconditions', '处理完成')}",
                                 kind="feedback", phase=90, explicit=False,
                                 direction="outgoing", inference_basis="成功后置条件需要向 Actor 返回可见结果。"))
    return messages


def _sr_messages(model: dict[str, Any], uc: dict[str, Any], ssd_id: str) -> list[dict[str, Any]]:
    arch = _architecture(uc)
    sr = arch.get("sr") or {}
    system = _system_node(model)
    sr_id = _text(sr.get("service_id"))
    if not sr_id:
        raise ValidationFailure([f"{uc['use_case_id']} SR architecture needs service_id"])
    primary = _primary_interaction(model, uc) or {"source_step_index": 1, "source_location": "", "message": uc.get("use_case_name", "处理请求"), "interaction_id": ""}
    step_index = int(primary.get("source_step_index", 1) or 1)
    location = primary.get("source_location", "")
    api_id = _text(sr.get("abstract_api_id"))
    exchange = stable_id("EXCH", uc["use_case_id"], "SR", api_id or step_index)
    request = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="SR", sequence=1,
                       exchange_id=exchange, source_step_index=step_index, source_location=location,
                       source=system["node_id"], target=sr_id, text=f"调用 {api_id}：{primary.get('message', uc.get('use_case_name', '处理请求'))}",
                       kind="request", phase=20, interaction_id=primary.get("interaction_id", ""),
                       abstract_api_id=api_id, service_id=sr_id,
                       request_fields=copy.deepcopy(sr.get("request_fields", [])),
                       response_fields=copy.deepcopy(sr.get("response_fields", [])), direction="internal")
    response = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="SR", sequence=2,
                        exchange_id=exchange, source_step_index=step_index, source_location=location,
                        source=sr_id, target=system["node_id"], text=f"返回 {api_id} 处理结果",
                        kind="response", phase=80, interaction_id=primary.get("interaction_id", ""), explicit=False,
                        abstract_api_id=api_id, service_id=sr_id, response_fields=copy.deepcopy(sr.get("response_fields", [])),
                        reply_to_message_id=request["message_id"], inference_basis="SR 设计用例需要向系统返回接口结果。", direction="internal")
    result = [request, response]
    nodes = _nodes(model)
    for interaction in sorted((x for x in model.get("interactions", []) if x.get("use_case_id") == uc["use_case_id"]), key=lambda x: x.get("sequence", 0)):
        target = nodes.get(interaction.get("to_node"), {})
        if target.get("kind") not in {"external_service", "external_database", "external_llm"}:
            continue
        ex = stable_id("EXCH", uc["use_case_id"], "SR-DEP", interaction.get("interaction_id"))
        req = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="SR", sequence=len(result)+1,
                       exchange_id=ex, source_step_index=int(interaction.get("source_step_index", step_index) or step_index),
                       source_location=interaction.get("source_location", ""), source=interaction["from_node"],
                       target=interaction["to_node"], text=interaction.get("message", "调用外部依赖"), kind="request", phase=35,
                       interaction_id=interaction.get("interaction_id", ""), api=interaction.get("api", ""),
                       api_method=interaction.get("api_method", ""), resource_path=interaction.get("resource_path", ""),
                       request_fields=copy.deepcopy(interaction.get("request_fields", [])), direction=interaction.get("direction", "outgoing"))
        resp = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="SR", sequence=len(result)+2,
                        exchange_id=ex, source_step_index=req["source_step_index"], source_location=req["source_location"],
                        source=interaction["to_node"], target=interaction["from_node"], text=f"返回：{interaction.get('message', '处理结果')}",
                        kind="response", phase=70, interaction_id=interaction.get("interaction_id", ""), explicit=False,
                        api=interaction.get("api", ""), api_method=interaction.get("api_method", ""),
                        resource_path=interaction.get("resource_path", ""), reply_to_message_id=req["message_id"],
                        inference_basis="需求未单独提供外部依赖返回消息，按同步调用补全。", direction="incoming")
        result.extend([req, resp])
    # Preserve explicit AR service/database calls from the design model even
    # when they are not represented by an architecture component mapping.
    for interaction in sorted((x for x in model.get("interactions", []) if x.get("use_case_id") == uc["use_case_id"]), key=lambda x: x.get("sequence", 0)):
        source = nodes.get(interaction.get("from_node"), {})
        target = nodes.get(interaction.get("to_node"), {})
        if source.get("kind") not in {"internal_service", "implementation_api"}:
            continue
        if target.get("kind") not in {"internal_service", "internal_database"}:
            continue
        ex = stable_id("EXCH", uc["use_case_id"], "AR-DIRECT", interaction.get("interaction_id"))
        step = int(interaction.get("source_step_index", step_index) or step_index)
        req = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=len(result)+1,
                       exchange_id=ex, source_step_index=step, source_location=interaction.get("source_location", ""),
                       source=interaction["from_node"], target=interaction["to_node"], text=interaction.get("message", "内部调用"),
                       kind="internal_call", phase=45, interaction_id=interaction.get("interaction_id", ""),
                       api=interaction.get("api", ""), api_method=interaction.get("api_method", ""),
                       resource_path=interaction.get("resource_path", ""), request_fields=copy.deepcopy(interaction.get("request_fields", [])))
        resp = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=len(result)+2,
                        exchange_id=ex, source_step_index=step, source_location=interaction.get("source_location", ""),
                        source=interaction["to_node"], target=interaction["from_node"], text=f"返回：{interaction.get('message', '处理结果')}",
                        kind="internal_return", phase=55, interaction_id=interaction.get("interaction_id", ""),
                        response_fields=copy.deepcopy(interaction.get("response_fields", [])), reply_to_message_id=req["message_id"],
                        explicit=False, inference_basis="设计模型明确存在 AR 内部调用，工具补齐同步返回。")
        result.extend([req, resp])
    # External callbacks into the system are also SR interactions.  They are
    # important for identity/permission concerns and must not be dropped just
    # because the system is the callback target.
    for interaction in sorted((x for x in model.get("interactions", []) if x.get("use_case_id") == uc["use_case_id"]), key=lambda x: x.get("sequence", 0)):
        source = nodes.get(interaction.get("from_node"), {})
        target = nodes.get(interaction.get("to_node"), {})
        if source.get("kind") not in {"external_service", "external_llm", "external_actor"}:
            continue
        if target.get("node_id") != system.get("node_id") and target.get("kind") not in {"internal_service"}:
            continue
        ex = stable_id("EXCH", uc["use_case_id"], "SR-CALLBACK", interaction.get("interaction_id"))
        step = int(interaction.get("source_step_index", step_index) or step_index)
        req = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="SR", sequence=len(result)+1,
                       exchange_id=ex, source_step_index=step, source_location=interaction.get("source_location", ""),
                       source=interaction["from_node"], target=interaction["to_node"], text=interaction.get("message", "外部回调"),
                       kind="event", phase=35, interaction_id=interaction.get("interaction_id", ""),
                       api=interaction.get("api", ""), api_method=interaction.get("api_method", ""), resource_path=interaction.get("resource_path", ""),
                       request_fields=copy.deepcopy(interaction.get("request_fields", [])), direction=interaction.get("direction", "incoming"))
        resp = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="SR", sequence=len(result)+2,
                        exchange_id=ex, source=interaction["to_node"], target=interaction["from_node"], source_step_index=step,
                        source_location=interaction.get("source_location", ""), text=f"返回：{interaction.get('message', '回调处理结果')}",
                        kind="response", phase=70, interaction_id=interaction.get("interaction_id", ""),
                        api=interaction.get("api", ""), api_method=interaction.get("api_method", ""), resource_path=interaction.get("resource_path", ""),
                        reply_to_message_id=req["message_id"], explicit=False, inference_basis="外部回调需要系统确认处理结果。", direction="outgoing")
        result.extend([req, resp])
    return result


def _ar_messages(model: dict[str, Any], uc: dict[str, Any], ssd_id: str) -> list[dict[str, Any]]:
    arch = _architecture(uc)
    sr = arch.get("sr") or {}
    sr_id = _text(sr.get("service_id"))
    nodes = _nodes(model)
    primary = _primary_interaction(model, uc) or {"source_step_index": 1, "source_location": "", "interaction_id": ""}
    default_step = int(primary.get("source_step_index", 1) or 1)
    result: list[dict[str, Any]] = []
    sequence = 1
    dbs = [node for node in nodes.values() if node.get("kind") == "internal_database" and node.get("layer") == "AR"]
    for index, component in enumerate(arch.get("ar") or [], 1):
        micro_id = _text(component.get("microservice_id"))
        impl_id = _text(component.get("implementation_api_node_id") or component.get("implementation_api_id"))
        if not sr_id or not micro_id or not impl_id:
            continue
        step = int(component.get("source_step_index", default_step) or default_step)
        location = component.get("source_location", primary.get("source_location", ""))
        interaction_id = component.get("interaction_id", primary.get("interaction_id", ""))
        ex = stable_id("EXCH", uc["use_case_id"], "AR", component.get("implementation_api_id"), index)
        req1 = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=sequence, exchange_id=ex,
                        source_step_index=step, source_location=location, source=sr_id, target=impl_id,
                        text=f"调用软件实现接口 {component.get('implementation_api_id', impl_id)}", kind="internal_call", phase=30,
                        interaction_id=interaction_id, implementation_api_id=component.get("implementation_api_id", ""),
                        service_id=micro_id, api_method=component.get("method", ""), resource_path=component.get("resource_path", ""))
        result.append(req1); sequence += 1
        micro_ex = stable_id("EXCH", ex, "microservice")
        req2 = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=sequence, exchange_id=micro_ex,
                        source_step_index=step, source_location=location, source=impl_id, target=micro_id,
                        text=f"分发到 {component.get('microservice_name', micro_id)}", kind="internal_call", phase=32,
                        interaction_id=interaction_id, implementation_api_id=component.get("implementation_api_id", ""), service_id=micro_id,
                        reply_to_message_id=req1["message_id"])
        result.append(req2); sequence += 1
        if dbs:
            db = dbs[0]
            db_ex = stable_id("EXCH", ex, "db")
            db_req = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=sequence, exchange_id=db_ex,
                              source_step_index=step, source_location=location, source=micro_id, target=db["node_id"],
                              text=component.get("database_action", "查询或写入内部数据库"), kind="internal_call", phase=40,
                              interaction_id=interaction_id, service_id=micro_id, entity_attribute=component.get("entity_attribute", ""))
            result.append(db_req); sequence += 1
            db_resp = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=sequence, exchange_id=db_ex,
                               source_step_index=step, source_location=location, source=db["node_id"], target=micro_id,
                               text="返回数据库处理结果", kind="internal_return", phase=50, interaction_id=interaction_id,
                               reply_to_message_id=db_req["message_id"], explicit=False, inference_basis="AR 微服务需要接收内部数据库处理结果。")
            result.append(db_resp); sequence += 1
        ret = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=sequence, exchange_id=micro_ex,
                       source_step_index=step, source_location=location, source=micro_id, target=impl_id,
                       text=f"返回 {component.get('implementation_api_id', '实现接口')} 结果", kind="internal_return", phase=60,
                       interaction_id=interaction_id, implementation_api_id=component.get("implementation_api_id", ""), service_id=micro_id,
                       reply_to_message_id=req2["message_id"], explicit=False, inference_basis="微服务处理完成后返回实现接口。")
        result.append(ret); sequence += 1
        final = _message(ssd_id=ssd_id, use_case_id=uc["use_case_id"], layer="AR", sequence=sequence, exchange_id=ex,
                         source_step_index=step, source_location=location, source=impl_id, target=sr_id,
                         text="返回 SR 抽象服务结果", kind="internal_return", phase=65, interaction_id=interaction_id,
                         implementation_api_id=component.get("implementation_api_id", ""), service_id=micro_id,
                         reply_to_message_id=req1["message_id"], explicit=False, inference_basis="软件实现接口向上提供 SR 服务结果。")
        result.append(final); sequence += 1
    return result


def _fuse(rr: dict[str, Any], sr: dict[str, Any], ar: dict[str, Any]) -> dict[str, Any]:
    fused_id = stable_id("SSD", rr.get("use_case_id"), "fused", rr.get("scenario_id", "main"))
    all_messages = []
    for source in (rr, sr, ar):
        for message in source.get("messages", []):
            item = copy.deepcopy(message)
            item["original_ssd_id"] = item.get("ssd_id", "")
            item["ssd_id"] = fused_id
            all_messages.append(item)
    all_messages.sort(key=lambda item: (int(item.get("source_step_index", 0) or 0), int(item.get("phase", 99)), int(item.get("sequence", 0))))
    for index, item in enumerate(all_messages, 1):
        item["ssd_sequence"] = index
        item["sequence"] = index
        item["message_id"] = stable_id("MSG", fused_id, item.get("exchange_id"), item.get("message_kind"), index, item.get("from_node"), item.get("to_node"))
    return {"version": "4", "ssd_id": fused_id, "layer": "fused", "project": rr.get("project", ""),
            "use_case_id": rr.get("use_case_id"), "scenario_id": rr.get("scenario_id", "main"),
            "name": rr.get("name", ""), "messages": all_messages,
            "source_ssds": {"rr": rr.get("ssd_id"), "sr": sr.get("ssd_id"), "ar": ar.get("ssd_id")},
            "review_items": []}


def fuse_ssd(rr_ssd: dict[str, Any], sr_ssd: dict[str, Any], api_map: Any = None) -> dict[str, Any]:
    """Compatibility entry point for callers that already have RR and SR JSON.

    V4 generation normally uses :func:`generate_ssd_bundle`, which can also
    build the AR layer.  This command preserves the public CLI by fusing the
    supplied RR and SR documents and leaving AR empty.
    """
    if str(rr_ssd.get("version")) != "4" or str(sr_ssd.get("version")) != "4":
        raise ValidationFailure(["fuse_ssd requires V4 RR and SR SSDs"])
    validate_ssd(rr_ssd, raise_on_error=True)
    validate_ssd(sr_ssd, raise_on_error=True)
    empty_ar = {"version": "4", "ssd_id": stable_id("SSD", rr_ssd.get("use_case_id"), "AR", "empty"),
                "layer": "AR", "project": rr_ssd.get("project", ""), "use_case_id": rr_ssd.get("use_case_id"),
                "scenario_id": rr_ssd.get("scenario_id", "main"), "name": rr_ssd.get("name", ""), "messages": []}
    return _fuse(rr_ssd, sr_ssd, empty_ar)


def _v4_generate_ssd_bundle(model: dict[str, Any], use_case_id: str, api_map: Any = None) -> dict[str, Any]:
    report = validate_scene_model(model, raise_on_error=True)
    normalized = report["normalized_model"]
    if str(normalized.get("version")) != "4":
        raise ValidationFailure(["generate_ssd requires a V4 scene model"])
    uc = use_case_map(normalized).get(use_case_id)
    if uc is None:
        raise ValidationFailure([f"unknown use_case_id: {use_case_id}"])
    rr_id = stable_id("SSD", use_case_id, "RR", "main")
    sr_id = stable_id("SSD", use_case_id, "SR", "main")
    ar_id = stable_id("SSD", use_case_id, "AR", "main")
    rr = {"version": "4", "ssd_id": rr_id, "layer": "RR", "project": normalized["project"], "use_case_id": use_case_id, "scenario_id": "main", "name": uc["use_case_name"], "messages": _rr_messages(normalized, uc, rr_id)}
    sr = {"version": "4", "ssd_id": sr_id, "layer": "SR", "project": normalized["project"], "use_case_id": use_case_id, "scenario_id": "main", "name": uc["use_case_name"], "messages": _sr_messages(normalized, uc, sr_id)}
    ar = {"version": "4", "ssd_id": ar_id, "layer": "AR", "project": normalized["project"], "use_case_id": use_case_id, "scenario_id": "main", "name": uc["use_case_name"], "messages": _ar_messages(normalized, uc, ar_id)}
    fused = _fuse(rr, sr, ar)
    architecture = _architecture(uc)
    review_items = []
    if not architecture.get("ar"):
        review_items.append({"type": "ar_mapping_missing", "use_case_id": use_case_id, "message": "未找到该 SR 用例到 AR 微服务/Implementation API 的映射，已保留 SR SSD。"})
    for component in architecture.get("ar") or []:
        if not component.get("implementation_api_id") or not component.get("microservice_id"):
            review_items.append({"type": "ar_mapping_incomplete", "use_case_id": use_case_id, "message": "AR 映射缺少 Implementation API 或微服务标识。"})
    fused["review_items"] = review_items
    return {"version": "4", "project": normalized["project"], "use_case_id": use_case_id, "scenario_id": "main", "rr": rr, "sr": sr, "ar": ar, "fused": fused}


def _v4_validate_ssd(ssd: dict[str, Any], model: dict[str, Any] | None = None, raise_on_error: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(ssd, dict):
        errors.append("ssd must be an object")
    else:
        if str(ssd.get("version", "4")) != "4":
            errors.append("ssd version must be 4")
        if ssd.get("layer") not in SSD_LAYERS:
            errors.append(f"invalid ssd layer: {ssd.get('layer')}")
        if not ssd.get("use_case_id"):
            errors.append("ssd needs use_case_id")
        messages = ssd.get("messages") if isinstance(ssd.get("messages"), list) else []
        if not messages and ssd.get("layer") != "AR":
            errors.append("ssd messages must be a non-empty list")
        previous = 0
        seen = set()
        for index, message in enumerate(messages, 1):
            if not isinstance(message, dict):
                errors.append(f"message {index} must be an object")
                continue
            if not message.get("message_id") or message.get("message_id") in seen:
                errors.append(f"message {index} has duplicate or missing message_id")
            seen.add(message.get("message_id"))
            if not message.get("from_node") or not message.get("to_node"):
                errors.append(f"message {index} needs from_node and to_node")
            if not message.get("source_step_index"):
                errors.append(f"message {index} needs source_step_index")
            if message.get("use_case_id") != ssd.get("use_case_id"):
                errors.append(f"message {index} use_case_id does not match SSD")
            if message.get("layer") not in {"RR", "SR", "AR"}:
                errors.append(f"message {index} has invalid layer: {message.get('layer')}")
            seq = message.get("ssd_sequence")
            if not isinstance(seq, int) or seq <= previous:
                errors.append(f"message {index} ssd_sequence must be strictly increasing")
            previous = seq if isinstance(seq, int) else previous
            if message.get("message_kind") not in MESSAGE_KINDS:
                errors.append(f"message {index} has invalid message_kind")
        by_exchange: dict[str, list[dict[str, Any]]] = {}
        for message in messages:
            by_exchange.setdefault(message.get("exchange_id", message.get("message_id", "")), []).append(message)
        for exchange_id, members in by_exchange.items():
            requests = [item for item in members if item.get("message_kind") in {"request", "event", "internal_call"}]
            replies = [item for item in members if item.get("message_kind") in {"response", "internal_return", "feedback"}]
            if requests and not replies and not any(item.get("one_way") for item in requests):
                errors.append(f"exchange {exchange_id} has no response or documented one-way event")
    if model is not None and isinstance(ssd, dict):
        report = validate_scene_model(model)
        errors.extend(report.get("errors", []))
        if report.get("valid"):
            nodes = node_map(report["normalized_model"])
            for message in ssd.get("messages", []):
                if message.get("from_node") not in nodes or message.get("to_node") not in nodes:
                    errors.append(f"message references unknown node: {message.get('from_node')}->{message.get('to_node')}")
            participant_ids = {node_id for message in ssd.get("messages", []) for node_id in (message.get("from_node"), message.get("to_node")) if node_id}
            human_ids = {node_id for node_id in participant_ids if nodes.get(node_id, {}).get("kind") in {"human_actor", "external_actor"}}
            if ssd.get("layer") in {"RR", "fused"} and human_ids and not any(message.get("to_node") in human_ids and message.get("message_kind") in {"response", "feedback"} for message in ssd.get("messages", [])):
                errors.append("human-actor SSD has no final system response/feedback")
    result = {"valid": not errors, "errors": errors}
    if raise_on_error and errors:
        raise ValidationFailure(errors)
    return result


def ssd_to_puml(ssd: dict[str, Any], model: dict[str, Any]) -> str:
    nodes = node_map(model)
    ordered = sorted(ssd.get("messages", []), key=lambda item: item.get("ssd_sequence", 0))
    used: list[str] = []
    for message in ordered:
        for node_id in (message.get("from_node"), message.get("to_node")):
            if node_id not in used:
                used.append(node_id)
    lines = ["@startuml", f"title {_escape(ssd.get('name', ssd.get('use_case_id', 'SSD')))} - {ssd.get('layer', 'fused')} SSD", "hide footbox", "skinparam responseMessageBelowArrow true"]
    for node_id in used:
        node = nodes.get(node_id, {"name": node_id, "kind": "participant"})
        keyword = "actor" if node.get("kind") in {"human_actor", "external_actor"} else "participant"
        lines.append(f'{keyword} "{_escape(node.get("name", node_id))}" as {str(node_id).replace("-", "_")}')
    for message in ordered:
        source = str(message.get("from_node", "")).replace("-", "_")
        target = str(message.get("to_node", "")).replace("-", "_")
        arrow = "-->" if message.get("message_kind") in {"response", "internal_return", "feedback"} else "->"
        label = f"[{message.get('source_step_index')}] {_escape(message.get('message'))}"
        if message.get("layer") != "RR":
            api = message.get("api_method") or message.get("resource_path") or message.get("abstract_api_id") or message.get("implementation_api_id")
            if api:
                label += f"\\n{_escape(api)}"
        lines.append(f"{source} {arrow} {target} : {label}")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def _render_optional_puml(bundle: dict[str, Any], model: dict[str, Any], output: Path, jar: Path) -> None:
    optional = output / "optional"
    optional.mkdir(parents=True, exist_ok=True)
    paths = []
    for layer in ("rr", "sr", "ar", "fused"):
        path = optional / f"{layer}_main.puml"
        path.write_text(ssd_to_puml(bundle[layer], model), encoding="utf-8")
        paths.append(path)
    for fmt in ("svg", "png"):
        command = ["java", "-Djava.awt.headless=true", "-jar", str(jar), f"-t{fmt}", *(str(path) for path in paths)]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f"PlantUML {fmt} rendering failed: {completed.stderr.strip()[:1000]}")


def _v4_write_ssd_bundle(bundle: dict[str, Any], model: dict[str, Any], output_dir: str | Path,
                     plantuml_jar: str | Path | None = None, render: bool = False) -> dict[str, Any]:
    output = Path(output_dir).expanduser().resolve() / bundle["use_case_id"]
    output.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Any] = {}
    for layer in ("rr", "sr", "ar", "fused"):
        ssd = bundle[layer]
        validation = validate_ssd(ssd, model)
        if not validation["valid"]:
            raise ValidationFailure(validation["errors"])
        json_path = output / f"{layer}_main.json"
        svg_path = output / f"{layer}_main.svg"
        json_path.write_text(json.dumps(ssd, ensure_ascii=False, indent=2), encoding="utf-8")
        render_ssd_svg(ssd, model, svg_path)
        paths[layer] = {"json": str(json_path), "svg": str(svg_path), "png": "", "puml": ""}
    jar = Path(plantuml_jar or os.environ.get("PLANTUML_JAR", "")).expanduser()
    if render or jar.is_file():
        if not jar.is_file():
            if render:
                raise RuntimeError("PlantUML JAR is required for optional PlantUML rendering")
        else:
            _render_optional_puml(bundle, model, output, jar)
            for layer in ("rr", "sr", "ar", "fused"):
                paths[layer]["puml"] = str(output / "optional" / f"{layer}_main.puml")
                paths[layer]["png"] = str(output / "optional" / f"{layer}_main.png")
    manifest = {"version": "4", "project": bundle["project"], "use_case_id": bundle["use_case_id"], "scenario_id": "main", "artifacts": paths, "review_items": bundle.get("fused", {}).get("review_items", [])}
    (output / "ssd_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# V5: step-driven RR/SR/AR chain.  Kept below the V4 implementation so old
# fixtures remain readable while V5 models use the corrected semantics.

def _v5_interface(model: dict[str, Any], api_id: str) -> dict[str, Any]:
    for item in model.get("interfaces", []):
        if item.get("abstract_api_id") == api_id or item.get("name") == api_id:
            return item
    return {}


def _v5_actor(model: dict[str, Any], uc: dict[str, Any]) -> str:
    nodes = _nodes(model)
    for name in uc.get("actors", []):
        for node in nodes.values():
            if node.get("name") == name and node.get("kind") in {"human_actor", "external_actor"}:
                return node["node_id"]
    return next((n["node_id"] for n in nodes.values() if n.get("kind") in {"human_actor", "external_actor"}), "actor")


def _v5_step_is_actor(text: str, uc: dict[str, Any]) -> bool:
    return any(str(actor).strip() and str(actor).strip() in text for actor in uc.get("actors", [])) and not text.startswith(("系统", "在线商城系统"))


def _v5_call_step(uc: dict[str, Any], components: list[dict[str, Any]], interface: dict[str, Any]) -> int:
    for step in uc.get("main_flow", []):
        text = str(step.get("text", ""))
        if "API" in text or "接口" in text or any(word in text for word in ("查询", "展示", "创建", "更新", "支付", "发货", "退款", "发布")) and not _v5_step_is_actor(text, uc):
            return int(step.get("step_index", 1))
    return int((components[0] if components else {}).get("source_step_index") or 1)


def _v5_message(ssd_id: str, uc_id: str, seq: int, exchange: str, step: int, loc: str, source: str, target: str, label: str, kind: str, layer: str, phase: int, **fields: Any) -> dict[str, Any]:
    item = _message(ssd_id=ssd_id, use_case_id=uc_id, layer=layer, sequence=seq, exchange_id=exchange, source_step_index=step, source_location=loc, source=source, target=target, text=label, kind=kind, phase=phase, **fields)
    item.setdefault("parent_exchange_id", "")
    item.setdefault("reply_to_message_id", "")
    return item


def _v5_chain(model: dict[str, Any], uc: dict[str, Any], ssd_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    nodes = _nodes(model)
    system = _system_node(model)
    actor = _v5_actor(model, uc)
    arch = _architecture(uc)
    rr_arch, sr_arch, components = arch.get("rr") or {}, arch.get("sr") or {}, arch.get("ar") or []
    sr_id = _text(sr_arch.get("service_id"))
    api_id = _text(sr_arch.get("abstract_api_id"))
    interface = _v5_interface(model, api_id)
    call_step = _v5_call_step(uc, components, interface)
    call_location = _text(sr_arch.get("source_location") or (components[0] if components else {}).get("source_location") or uc.get("source_location"))
    actor_label = nodes.get(actor, {}).get("name", actor)
    system_id = system.get("node_id", "system")
    rr_lifelines = [{"node_id": actor, "label": actor_label, "kind": "actor", "layer": "RR"}, {"node_id": system_id, "label": model.get("system_name", system_id), "kind": "system", "layer": "RR"}]
    sr_lifelines = [{"node_id": system_id, "label": model.get("system_name", system_id), "kind": "system", "layer": "RR"}]
    ar_lifelines = []
    fused_lifelines = list(rr_lifelines)
    rr_messages, sr_messages, ar_messages = [], [], []
    seq_rr = seq_sr = seq_ar = 1
    request_by_exchange: dict[str, dict[str, Any]] = {}

    # RR is deliberately business-level: no HTTP method/path on Actor/System.
    for step in uc.get("main_flow", []):
        index, text, loc = int(step.get("step_index", 1)), str(step.get("text", "")), step.get("source_location", "")
        if _v5_step_is_actor(text, uc):
            ex = stable_id("EXCH", uc["use_case_id"], "RR", index)
            req = _v5_message(rr_id := ssd_id+"-RR", uc["use_case_id"], seq_rr, ex, index, loc, actor, system_id, text, "request", "RR", 10, direction="incoming")
            seq_rr += 1; rr_messages.append(req); request_by_exchange[ex] = req
            rr_messages.append(_v5_message(ssd_id+"-RR", uc["use_case_id"], seq_rr, ex, index, loc, system_id, actor, f"系统受理：{text}", "feedback", "RR", 90, reply_to_message_id=req["message_id"], explicit=False, direction="outgoing", inference_basis="RR 层为每个同步业务动作补齐可见受理反馈。")); seq_rr += 1
        elif text.startswith(("系统", "在线商城系统")) and index != call_step:
            ex = stable_id("EXCH", uc["use_case_id"], "RR", index, "feedback")
            rr_messages.append(_v5_message(ssd_id+"-RR", uc["use_case_id"], seq_rr, ex, index, loc, system_id, actor, text, "feedback", "RR", 90, direction="outgoing")); seq_rr += 1
    if not rr_messages or not any(m.get("to_node") == actor for m in rr_messages):
        last = uc.get("main_flow", [])[-1] if uc.get("main_flow") else {"step_index": 1, "text": "完成用例", "source_location": ""}
        ex = stable_id("EXCH", uc["use_case_id"], "RR", last.get("step_index", 1), "final")
        rr_messages.append(_v5_message(ssd_id+"-RR", uc["use_case_id"], seq_rr, ex, int(last.get("step_index", 1)), last.get("source_location", ""), system_id, actor, f"系统返回：{uc.get('postconditions', '处理完成')}", "feedback", "RR", 90, explicit=False, direction="outgoing", inference_basis="由用例成功后置条件补全最终可见反馈。")); seq_rr += 1
    else:
        last = uc.get("main_flow", [])[-1] if uc.get("main_flow") else {"step_index": 1, "text": "完成用例", "source_location": ""}
        if not any(m.get("to_node") == actor and m.get("source_step_index") == int(last.get("step_index", 1)) for m in rr_messages):
            ex = stable_id("EXCH", uc["use_case_id"], "RR", last.get("step_index", 1), "final")
            rr_messages.append(_v5_message(ssd_id+"-RR", uc["use_case_id"], seq_rr, ex, int(last.get("step_index", 1)), last.get("source_location", ""), system_id, actor, f"系统返回：{uc.get('postconditions', '处理完成')}", "feedback", "RR", 90, explicit=False, direction="outgoing", inference_basis="由用例成功后置条件补全最终可见反馈。")); seq_rr += 1

    # One SR request/response exchange represents the design-use-case API.
    primary_ex = stable_id("EXCH", uc["use_case_id"], "SR", api_id or "service")
    sr_req = _v5_message(ssd_id+"-SR", uc["use_case_id"], seq_sr, primary_ex, call_step, call_location, system_id, sr_id, f"调用 {api_id}：{interface.get('method', '')} {interface.get('path', '')}".strip(), "request", "SR", 20, abstract_api_id=api_id, service_id=sr_id, api_method=interface.get("method", ""), resource_path=interface.get("path", ""), request_fields=copy.deepcopy(interface.get("request_fields", sr_arch.get("request_fields", []))), response_fields=copy.deepcopy(interface.get("response_fields", sr_arch.get("response_fields", []))), direction="internal")
    seq_sr += 1; sr_messages.append(sr_req); request_by_exchange[primary_ex] = sr_req
    sr_lifelines.append({"node_id": sr_id, "label": sr_arch.get("service_name", sr_id), "kind": "sr_service", "layer": "SR", "abstract_api_id": api_id})

    # AR uses one line for ImplementationAPI + microservice.  It may call an
    # internal database or an SR external dependency, then returns in reverse.
    last_ar_target = sr_id
    for index, component in enumerate(components, 1):
        impl = _text(component.get("implementation_api_node_id") or component.get("implementation_api_id"))
        micro = _text(component.get("microservice_id"))
        if not impl or not micro:
            continue
        label = f"ImplementationAPI\n{component.get('microservice_name', micro)}"
        if not any(item.get("node_id") == impl for item in ar_lifelines):
            ar_lifelines.append({"node_id": impl, "label": label, "kind": "implementation_microservice", "layer": "AR", "implementation_api_id": component.get("implementation_api_id", ""), "microservice_id": micro})
        if not any(item.get("node_id") == impl for item in fused_lifelines):
            fused_lifelines.append({"node_id": impl, "label": label, "kind": "implementation_microservice", "layer": "AR", "implementation_api_id": component.get("implementation_api_id", ""), "microservice_id": micro})
        ex = stable_id("EXCH", primary_ex, "AR", component.get("implementation_api_id", impl), index)
        # The AR call belongs to the SR exchange anchored at the design/API
        # step.  Component source_step_index remains evidence, but must not
        # pull the implementation call before its SR dispatch in the SSD.
        step = call_step; loc = component.get("source_location", call_location)
        req = _v5_message(ssd_id+"-AR", uc["use_case_id"], seq_ar, ex, step, loc, sr_id, impl, f"调用 {component.get('implementation_api_id', impl)}：{component.get('method', '')} {component.get('resource_path', '')}".strip(), "internal_call", "AR", 30, parent_exchange_id=primary_ex, implementation_api_id=component.get("implementation_api_id", ""), microservice_id=micro, service_id=micro, api_method=component.get("method", ""), resource_path=component.get("resource_path", ""), request_fields=copy.deepcopy(component.get("request_fields", [])), direction="internal")
        seq_ar += 1; ar_messages.append(req)
        db = next((n for n in nodes.values() if n.get("kind") == "internal_database" and n.get("layer") == "AR"), None)
        dep = next((n for n in nodes.values() if n.get("kind") in {"external_service", "external_database", "external_llm"} and n.get("name", "").lower().replace("service", "") in micro.lower()), None)
        target = db or dep
        nested_req = None
        nested_resp = None
        if target:
            target_layer = "SR" if target.get("kind") in {"external_service", "external_database", "external_llm"} else "AR"
            nested_ex = stable_id("EXCH", ex, "dependency")
            nested_req = _v5_message(ssd_id+"-"+target_layer, uc["use_case_id"], seq_ar, nested_ex, step, loc, impl, target["node_id"], component.get("database_action", "调用依赖处理请求"), "internal_call", target_layer, 40, parent_exchange_id=ex, microservice_id=micro, service_id=micro, entity_attribute=component.get("entity_attribute", ""), direction="internal")
            seq_ar += 1
            nested_resp = _v5_message(ssd_id+"-"+target_layer, uc["use_case_id"], seq_ar, nested_ex, step, loc, target["node_id"], impl, "返回依赖处理结果", "internal_return", target_layer, 50, parent_exchange_id=ex, reply_to_message_id=nested_req["message_id"], explicit=False, inference_basis="同步调用需要逐层返回。", direction="internal")
            seq_ar += 1; ar_messages.extend([nested_req, nested_resp])
            if not any(item.get("node_id") == target["node_id"] for item in fused_lifelines):
                fused_lifelines.append({"node_id": target["node_id"], "label": target.get("name", target["node_id"]), "kind": target.get("kind"), "layer": target_layer})
        ret = _v5_message(ssd_id+"-AR", uc["use_case_id"], seq_ar, ex, step, loc, impl, sr_id, f"返回 {component.get('implementation_api_id', '实现接口')} 结果", "internal_return", "AR", 60, parent_exchange_id=primary_ex, reply_to_message_id=req["message_id"], explicit=False, implementation_api_id=component.get("implementation_api_id", ""), microservice_id=micro, service_id=micro, direction="internal")
        seq_ar += 1; ar_messages.append(ret)
    sr_resp = _v5_message(ssd_id+"-SR", uc["use_case_id"], seq_sr, primary_ex, call_step, call_location, sr_id, system_id, f"返回 {api_id} 结果", "response", "SR", 80, abstract_api_id=api_id, service_id=sr_id, response_fields=copy.deepcopy(interface.get("response_fields", sr_arch.get("response_fields", []))), reply_to_message_id=sr_req["message_id"], explicit=False, inference_basis="SR 服务逐层汇总 AR 结果后返回系统。", direction="internal")
    sr_messages.append(sr_resp)

    common = {"version": "5", "project": model.get("project", ""), "use_case_id": uc["use_case_id"], "scenario_id": "main", "name": uc.get("use_case_name", "")}
    rr = {**common, "ssd_id": stable_id("SSD", uc["use_case_id"], "RR", "main"), "layer": "RR", "lifelines": rr_lifelines, "messages": rr_messages}
    sr = {**common, "ssd_id": stable_id("SSD", uc["use_case_id"], "SR", "main"), "layer": "SR", "lifelines": sr_lifelines + ar_lifelines[:0], "messages": sr_messages}
    ar = {**common, "ssd_id": stable_id("SSD", uc["use_case_id"], "AR", "main"), "layer": "AR", "lifelines": [{"node_id": sr_id, "label": sr_arch.get("service_name", sr_id), "kind": "sr_service", "layer": "SR"}] + ar_lifelines, "messages": ar_messages}
    fused = {**common, "ssd_id": stable_id("SSD", uc["use_case_id"], "fused", "main"), "layer": "fused", "lifelines": fused_lifelines + sr_lifelines[1:] + [x for x in ar_lifelines if x.get("node_id") not in {y.get("node_id") for y in fused_lifelines}], "messages": rr_messages + sr_messages + ar_messages, "source_ssds": {"rr": rr["ssd_id"], "sr": sr["ssd_id"], "ar": ar["ssd_id"]}}
    return rr, sr, ar, fused


def _v5_resequence(ssd: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(ssd)
    # parent chain is visualized in call order: RR, SR request, AR calls,
    # nested dependencies, returns, SR response, RR feedback.
    msgs = sorted(item.get("messages", []), key=lambda m: (int(m.get("source_step_index", 0) or 0), int(m.get("phase", 99)), int(m.get("sequence", 0))))
    old_to_new = {}
    for i, message in enumerate(msgs, 1):
        old = message.get("message_id")
        new = stable_id("MSG", item["ssd_id"], message.get("exchange_id"), message.get("message_kind"), i, message.get("from_node"), message.get("to_node"))
        old_to_new[old] = new; message["message_id"] = new; message["ssd_sequence"] = i; message["sequence"] = i; message["ssd_id"] = item["ssd_id"]
    for message in msgs:
        if message.get("reply_to_message_id") in old_to_new:
            message["reply_to_message_id"] = old_to_new[message["reply_to_message_id"]]
    item["messages"] = msgs
    return item


def _v5_fuse(rr: dict[str, Any], sr: dict[str, Any], ar: dict[str, Any]) -> dict[str, Any]:
    fused = copy.deepcopy(rr)
    fused["ssd_id"] = stable_id("SSD", rr.get("use_case_id"), "fused", "main")
    fused["layer"] = "fused"
    lifelines = []
    seen_lifelines = set()
    for line in rr.get("lifelines", []) + sr.get("lifelines", []) + ar.get("lifelines", []):
        if line.get("node_id") and line.get("node_id") not in seen_lifelines:
            lifelines.append(line); seen_lifelines.add(line["node_id"])
    fused["lifelines"] = lifelines
    messages = copy.deepcopy(rr.get("messages", [])) + copy.deepcopy(sr.get("messages", [])) + copy.deepcopy(ar.get("messages", []))
    messages, dedupe_report = _v6_dedupe_messages(messages)
    fused["messages"] = messages
    fused["dedupe_report"] = dedupe_report
    fused["source_ssds"] = {"rr": rr.get("ssd_id"), "sr": sr.get("ssd_id"), "ar": ar.get("ssd_id")}
    return _v5_resequence(fused)


def _v6_message_identity(message: dict[str, Any]) -> tuple[Any, ...]:
    """Identity for one semantic arrow, independent of generated message_id."""
    return tuple(str(message.get(field, "")).strip() for field in (
        "use_case_id", "layer", "exchange_id", "parent_exchange_id",
        "source_step_index", "from_node", "to_node", "message_kind",
        "abstract_api_id", "implementation_api_id", "api_method", "resource_path",
    ))


def _v6_message_text(message: dict[str, Any]) -> str:
    return " ".join(str(message.get("message", message.get("text", ""))).split())


def _v6_dedupe_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    by_identity: dict[tuple[Any, ...], dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    conflicts: list[str] = []
    removed = 0
    for message in messages:
        identity = _v6_message_identity(message)
        existing = by_identity.get(identity)
        if existing is None:
            item = copy.deepcopy(message)
            item["source_locations"] = [message.get("source_location", "")] if message.get("source_location") else []
            by_identity[identity] = item
            retained.append(item)
            continue
        if _v6_message_text(existing) != _v6_message_text(message):
            conflicts.append(f"semantic duplicate has conflicting text: {identity}")
            continue
        old_id = message.get("message_id")
        if old_id:
            aliases[old_id] = existing.get("message_id", old_id)
        location = message.get("source_location", "")
        if location and location not in existing.setdefault("source_locations", []):
            existing["source_locations"].append(location)
        removed += 1
    if conflicts:
        raise ValidationFailure(conflicts)
    for message in retained:
        reply = message.get("reply_to_message_id")
        if reply in aliases:
            message["reply_to_message_id"] = aliases[reply]
    return retained, {"input_count": len(messages), "output_count": len(retained), "removed_count": removed, "conflicts": conflicts}


def generate_ssd_bundle(model: dict[str, Any], use_case_id: str, api_map: Any = None) -> dict[str, Any]:
    if str(model.get("version")) not in {"5", "6"}:
        return _v4_generate_ssd_bundle(model, use_case_id, api_map)
    normalized = validate_scene_model(model, raise_on_error=True)["normalized_model"]
    uc = use_case_map(normalized).get(use_case_id)
    if uc is None:
        raise ValidationFailure([f"unknown use_case_id: {use_case_id}"])
    rr, sr, ar, fused = _v5_chain(normalized, uc, stable_id("SSD", use_case_id, "bundle"))
    rr = _v5_resequence(rr); sr = _v5_resequence(sr); ar = _v5_resequence(ar)
    fused = _v5_fuse(rr, sr, ar)
    return {"version": "6", "project": normalized["project"], "use_case_id": use_case_id, "scenario_id": "main", "rr": rr, "sr": sr, "ar": ar, "fused": fused, "review_items": []}


def validate_ssd(ssd: dict[str, Any], model: dict[str, Any] | None = None, raise_on_error: bool = False) -> dict[str, Any]:
    if str(ssd.get("version", "")) not in {"5", "6"}:
        return _v4_validate_ssd(ssd, model, raise_on_error)
    errors: list[str] = []
    if ssd.get("layer") not in {"RR", "SR", "AR", "fused"}:
        errors.append("invalid V5 SSD layer")
    messages = ssd.get("messages") if isinstance(ssd.get("messages"), list) else []
    try:
        _, dedupe_report = _v6_dedupe_messages(messages)
        if dedupe_report.get("removed_count"):
            errors.append(f"SSD contains {dedupe_report['removed_count']} semantic duplicate message(s)")
    except ValidationFailure as exc:
        errors.extend(exc.errors)
    previous = 0; seen = set(); by_exchange: dict[str, list[dict[str, Any]]] = {}
    for i, message in enumerate(messages, 1):
        if message.get("message_id") in seen or not message.get("message_id"): errors.append(f"message {i} has duplicate or missing message_id")
        seen.add(message.get("message_id"))
        seq = message.get("ssd_sequence")
        if not isinstance(seq, int) or seq <= previous: errors.append(f"message {i} ssd_sequence must increase")
        previous = seq if isinstance(seq, int) else previous
        if not message.get("from_node") or not message.get("to_node"): errors.append(f"message {i} needs endpoints")
        by_exchange.setdefault(message.get("exchange_id", ""), []).append(message)
    for exchange, items in by_exchange.items():
        if any(i.get("message_kind") in {"request", "internal_call", "event"} for i in items) and not any(i.get("message_kind") in {"response", "internal_return", "feedback"} for i in items):
            if not any(i.get("one_way") for i in items): errors.append(f"exchange {exchange} has no return")
    if model is not None:
        report = validate_scene_model(model)
        errors.extend(report.get("errors", []))
        if report.get("valid"):
            ids = set(node_map(report["normalized_model"]))
            for message in messages:
                if message.get("from_node") not in ids or message.get("to_node") not in ids: errors.append(f"unknown SSD node: {message.get('from_node')}->{message.get('to_node')}")
    result = {"valid": not errors, "errors": errors}
    if raise_on_error and errors: raise ValidationFailure(errors)
    return result


def write_ssd_bundle(bundle: dict[str, Any], model: dict[str, Any], output_dir: str | Path, plantuml_jar: str | Path | None = None, render: bool = False) -> dict[str, Any]:
    if str(bundle.get("version")) not in {"5", "6"}:
        return _v4_write_ssd_bundle(bundle, model, output_dir, plantuml_jar, render)
    output = Path(output_dir).expanduser().resolve() / bundle["use_case_id"]; output.mkdir(parents=True, exist_ok=True)
    paths = {}
    for layer in ("rr", "sr", "ar", "fused"):
        ssd = bundle[layer]; validate_ssd(ssd, model, True)
        jp = output / f"{layer}_main.json"; sp = output / f"{layer}_main.svg"; pp = output / f"{layer}_main.png"
        jp.write_text(json.dumps(ssd, ensure_ascii=False, indent=2), encoding="utf-8"); render_ssd_svg(ssd, model, sp)
        png_result = convert_svg_to_png(sp, pp)
        paths[layer] = {"json": str(jp), "svg": str(sp), "png": png_result.get("png", ""), "png_status": png_result.get("status"), "png_converter": png_result.get("converter", ""), "png_error": png_result.get("error", ""), "puml": ""}
    jar = Path(plantuml_jar or os.environ.get("PLANTUML_JAR", "")).expanduser()
    if jar.is_file() and shutil.which("java"):
        _render_optional_puml(bundle, model, output, jar)
        for layer in ("rr", "sr", "ar", "fused"):
            paths[layer]["puml"] = str(output / "optional" / f"{layer}_main.puml")
            paths[layer]["png"] = str(output / "optional" / f"{layer}_main.png")
    manifest = {"version": "6", "project": bundle["project"], "use_case_id": bundle["use_case_id"], "scenario_id": "main", "artifacts": paths, "review_items": bundle.get("review_items", []), "dedupe_report": bundle.get("fused", {}).get("dedupe_report", {})}
    (output / "ssd_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
