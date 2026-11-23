"""Resolve channel records for inputs predating structured entity and command profiles."""

from copy import deepcopy

from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.workflow.ssd.shared.semantic_execution import _semantic_available


def resolve(ex, bundle, record):
    from scene_completion.workflow.ssd.resolve.contract_binding import apply_result, prepare

    context, maps = prepare(bundle)
    if context and _semantic_available(ex):
        record["_short_id_mapping"] = maps
        value, _ = ex.semantic("ssd-bind", context, record)
        bundle = apply_result(bundle, context, maps, value)
    elif context:
        bundle["contract_binding_pending"] = [
            {"step_id": maps["steps"][s["id"]], "reason": "正向字段约束或操作关联待语义定位"}
            for s in context["steps"]
        ]
    for channel in ("G", "E", "GT"):
        pending = [p for p in bundle["channels"][channel]["pending"] if p.get("needs_semantic")]
        if not pending or not _semantic_available(ex):
            continue
        # Each invocation has just its own source records and shared positive anchors.
        inputs = {
            "case": bundle["case"],
            "steps": bundle["steps"],
            "apis": deepcopy(bundle.get("apis", [])),
            "entities": deepcopy(bundle.get("entities", [])),
            "channel": channel,
            "records": pending,
            "registry": ex.registry_snapshot,
        }
        result, _ = ex.semantic("ssd-resolve", inputs, record)
        allowed = {p["id"] for p in pending}
        resolved = set(result["resolved_ids"])
        if not resolved <= allowed:
            raise ValueError("语义识别引用了本通道以外的记录")
        if any(
            not any(c["source_record_id"] == ident for c in result["concerns"])
            or not any(s["source_record_id"] == ident for s in result["scenarios"])
            for ident in resolved
        ):
            raise ValueError("已解决的来源必须同时保留关注点和具体场景，不能提交空结果丢弃来源")
        from scene_completion.domain.ssd.matching import binding

        steps = {s["id"]: s for s in bundle["steps"]}
        entities = {
            e["id"]: {a["name"] for a in e.get("attributes", [])}
            for e in bundle.get("entities", [])
        }
        concerns = {c["id"]: c for c in result["concerns"]}
        for row in result["scenarios"]:
            if any(
                cid not in concerns
                or concerns[cid]["source_record_id"] != row["source_record_id"]
                or binding(concerns[cid]) != binding(row)
                for cid in row["concern_ids"]
            ):
                raise ValueError("语义场景必须关联同一来源和对象的关注点")
        for row in result["concerns"] + result["scenarios"]:
            if row.get("source_record_id") not in resolved:
                raise ValueError("语义结果必须绑定本次输入来源")
            source = next(p for p in pending if p["id"] == row["source_record_id"])
            if row["step_id"] not in steps or (
                row.get("attribute")
                and (
                    row.get("field_id")
                    or row["attribute"] not in entities.get(row.get("entity_id"), set())
                )
            ):
                raise ValueError("语义识别引用了不存在的步骤、实体或属性")
            row["source_refs"] = deepcopy(source.get("source_refs", []))
        bundle["channels"][channel]["concerns"].extend(result["concerns"])
        bundle["channels"][channel]["scenarios"].extend(result["scenarios"])
        bundle["channels"][channel]["pending"] = [
            p for p in bundle["channels"][channel]["pending"] if p["id"] not in resolved
        ]
    bundle["gt_identification_run_complete"] = bundle.get("gt_source_available", True) and (
        _semantic_available(ex)
        or not any(p.get("needs_semantic") for p in bundle["channels"]["GT"]["pending"])
    )
    return ssd_validation.validate(bundle)
