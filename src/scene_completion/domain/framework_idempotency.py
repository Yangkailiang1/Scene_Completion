"""User-confirmed default: idempotency on actual SR internal R/U/D requests.

This is an explicit exception to evidence-only G recognition. It never creates
E/GT observations, request keys, HTTP outcomes or unchanged-data assumptions.
"""

from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint

POLICY = "sr-internal-rud-idempotency-v1"
KEY = "service.resource_mutation.idempotency"
RULE = "对同一业务对象、业务状态及请求条件重复执行本次操作，不应产生超出一次执行的额外业务影响；查询响应不要求动态字段或序列化字节完全相同。"


def applicable(interaction, inputs):
    if (
        interaction["direction"] != "request"
        or interaction["sender"]["name"] == interaction["receiver"]["name"]
    ):
        return False
    from scene_completion.analysis.concern_hierarchy import context
    from scene_completion.analysis.interaction_enrichment import resolved_api_id

    ctx = context(interaction, inputs)
    if not ctx["service"] or ctx["external"] or not ctx["kinds"] & {"read", "update", "delete"}:
        return False
    caller = interaction["sender"]["position"]
    if any(word in caller for word in ("人类", "外部", "UI/前端")):
        return False
    if not any(word in caller for word in ("内部服务", "系统边界", "内部数据库", "AI模型")):
        return False
    if not any(
        word in interaction["receiver"]["position"]
        for word in ("内部服务", "系统边界", "内部数据库", "AI模型")
    ):
        return False
    api_id = resolved_api_id(interaction, inputs)
    api = next(
        (
            a
            for a in inputs.get("api-parameters", inputs.get("normal-constraints", {})).get(
                "apis", []
            )
            if a["id"] == api_id
        ),
        {},
    )
    layer = api.get("source_layer") or (
        api_id.split("::", 1)[0] if api_id and "::" in api_id else None
    )
    if layer == "RR":
        return False
    return layer == "SR" or interaction["layer"] == "SR"


def canonical_key(key, interaction, inputs):
    from scene_completion.domain.concern_registry import registry

    defs = registry()["definitions"]
    if (
        defs.get(KEY, {}).get("enabled", False)
        and defs.get(key, {}).get("guard") == "idempotency"
        and applicable(interaction, inputs)
    ):
        return KEY
    return key


def recognized_defaults(inputs):
    from scene_completion.analysis.concern_alignment import interaction_rows
    from scene_completion.domain.concern_registry import registry

    if not registry()["definitions"].get(KEY, {}).get("enabled", False):
        return []
    out = []
    for i in interaction_rows(inputs):
        if not applicable(i, inputs):
            continue
        out.append(
            {
                "interaction_id": i["id"],
                "target": "receiver",
                "object": i["receiver"]["name"],
                "concern_key": KEY,
                "basis": "用户确认的框架默认规则：SR内部接口实际R/U/D操作统一检查幂等性；原文未声明也启用。原文引用仅定位本次调用。",
                "concrete_rule": RULE,
                "source_refs": deepcopy(i["source_refs"]),
                "scope": "service",
                "data_location": None,
                "policy_id": POLICY,
                "activation_evidence": [],
            }
        )
    return out


def scenarios(inputs):
    """One conditional failure unit per recognized actual call, not per R/U/D."""
    from scene_completion.analysis.concern_alignment import interaction_rows
    from scene_completion.analysis.exception_generation import scenario_steps
    from scene_completion.analysis.normal_rules import rule_exceptions
    from scene_completion.domain.concern_registry import inheritance_paths

    rows = {i["id"]: i for i in interaction_rows(inputs)}
    out = []
    seen = set()
    explicit = {s["interaction_id"] for s in rule_exceptions(inputs) if s["concern_key"] == KEY}
    for m in inputs.get("concern-match", {}).get("matches", []):
        i = rows.get(m["interaction_id"])
        if (
            not i
            or m["concern_key"] != KEY
            or m.get("status") != "applicable"
            or i["id"] in seen
            or not applicable(i, inputs)
        ):
            continue
        if i["id"] in explicit:
            continue
        seen.add(i["id"])
        conditions = [
            "同一业务对象与业务前置状态、相同请求条件下重复执行本次操作",
            "重复执行产生超出一次执行的额外业务影响，违反本操作幂等性",
        ]
        out.append(
            {
                "id": "G-idempotency-" + fingerprint([i["case_id"], i["id"], POLICY])[:20],
                "case_id": i["case_id"],
                "interaction_id": i["id"],
                "layer": i["layer"],
                "object": i["receiver"]["name"],
                "operation": i["operation"]["name"],
                "cause": "重复执行违反幂等性",
                "conditions": conditions,
                "concern_key": KEY,
                "field": None,
                "rule_id": None,
                "source_status": "framework_inferred",
                "policy_id": POLICY,
                "derivation": "用户确认的框架默认规则 "
                + POLICY
                + "；不是从原文中提取的幂等要求，来源引用仅证明调用身份及实际操作。",
                "source_refs": deepcopy(i["source_refs"]),
                "steps": scenario_steps(i, conditions),
                "scope": "service",
                "data_location": None,
                "concern_origins": [KEY],
                "concern_paths": inheritance_paths(KEY),
                "scenario_type": "exception",
                "resolution": "conditional",
                "executable": False,
                "pending_details": [
                    "具体业务状态对照、请求重放数据及响应断言仍需准备；不假设幂等键、错误码或固定返回结构"
                ],
            }
        )
    return out
