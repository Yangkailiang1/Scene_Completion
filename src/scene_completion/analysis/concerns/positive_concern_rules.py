"""User-mandated call checks and narrowly evidenced positive business rules.

Only G consumes these rules. Call topology is evidence of policy applicability,
not a claim that a requirement explicitly described an authentication protocol.
E and GT remain independently recognized from their own exception sources.
"""

import re
from copy import deepcopy

from scene_completion.domain.concern_registry import registry
from scene_completion.infrastructure.storage import fingerprint

POLICY = "mandatory-call-concerns-v1"
POSITIVE = "evidenced-positive-concerns-v1"


def rows(inputs):
    from scene_completion.analysis.concerns.concern_hierarchy import context
    from scene_completion.analysis.concerns.normal_rules import rule_matches
    from scene_completion.analysis.interactions.interaction_enrichment import parameters_for
    from scene_completion.analysis.matching.concern_alignment import interaction_rows

    if inputs.get("recognition_scope") == "data":
        return []
    interactions = interaction_rows(inputs)
    definitions = registry()["definitions"]
    result = []

    def add(i, key, target, condition, refs, policy, guard=None):
        if key not in definitions or not definitions[key].get("enabled", True) or not refs:
            return
        result.append(
            {
                "interaction_id": i["id"],
                "target": target,
                "object": i[target]["name"],
                "concern_key": key,
                "concrete_rule": condition,
                "basis": (
                    "用户确认的必挂载策略；原文仅证明本次调用身份与边界，不冒充原文明示的认证机制。"
                    if policy == POLICY
                    else "当前操作的明示正向要求；未读取E、GT或比较结果。"
                )
                + condition,
                "source_refs": deepcopy(refs),
                "policy_id": policy,
                "activation_evidence": [
                    {
                        "kind": guard or definitions[key].get("guard") or "business",
                        "condition": condition,
                        "value": True if policy == POLICY else condition,
                        "unit": None,
                        "status": "explicit",
                        "field": None,
                        "constraint_kind": None,
                        "source_refs": deepcopy(refs),
                    }
                ],
            }
        )

    for i in interactions:
        ctx = context(i, inputs)
        refs = i.get("source_refs") or i["operation"].get("source_refs", [])
        # A real business R/U/D checks an existing target; existence is not
        # inferred from spelling of a URL or from tests. Explicit local owners
        # take precedence over the delegating calls.
        if i["direction"] == "request":
            text = i["operation"]["name"]
            if re.search(r"(?:核对|检查|校验|验证).*存在|存在性|check.*exist", text, re.I):
                for kind in ctx["kinds"] & {"read", "update", "delete"}:
                    key = (
                        "service.query_retrieval.resource_existence"
                        if kind == "read"
                        else "service.crud." + kind + ".resource_existence"
                    )
                    add(i, key, "receiver", text, refs, POSITIVE, "resource_lookup")
        if (
            i["direction"] != "request"
            or i.get("step_kind") == "action"
            or i["sender"]["name"] == i["receiver"]["name"]
        ):
            continue
        if ctx["service"] and ctx["external"]:
            add(
                i,
                "service.base.availability",
                "receiver",
                "本次外部Service调用应可达且可执行当前操作",
                refs,
                POLICY,
            )
        if "人类" in i["sender"]["position"]:
            add(
                i,
                "human.authentication",
                "sender",
                "人类调用方应通过身份认证",
                refs,
                POLICY,
                "authentication",
            )
            add(
                i,
                "human.authorization",
                "sender",
                "人类调用方应具有执行本次操作的权限",
                refs,
                POLICY,
                "authorization",
            )
        material = {
            **inputs,
            "api-parameters": inputs.get("api-parameters", inputs.get("normal-constraints", {})),
        }
        params = parameters_for(i, material)
        names = {p["name"] for p in params}
        for p in params:
            for rule in p.get("constraints", []):
                if rule.get("status") != "explicit" or rule.get("kind") != "other":
                    continue
                text = str(rule.get("value", ""))
                if re.search(
                    r"不得.*(?:service[-_]?id|租户).*访问|(?:service[-_]?id|租户).*不得.*访问|数据隔离",
                    text,
                    re.I,
                ):
                    add(
                        i,
                        "service_relation.data_isolation",
                        "receiver",
                        text,
                        rule["source_refs"],
                        POSITIVE,
                        "authorization",
                    )
                # This is a conditional business relation, not a plain numeric
                # comparison such as minPrice <= maxPrice or a field format.
                fields = {
                    n
                    for n in names
                    if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text)
                }
                if (
                    len(fields) >= 2
                    and re.search(r"时|when|如果|若|一致|只能", text, re.I)
                    and ctx["kinds"] & {"create", "update"}
                ):
                    add(
                        i,
                        "service.business_attribute_constraint",
                        "receiver",
                        text,
                        rule["source_refs"],
                        POSITIVE,
                    )
    # An existence rule must actually mention existence and belong to an R/U/D
    # business effect. Merely having an identifier in a create URL is not proof.
    by_id = {i["id"]: i for i in interactions}
    for m in rule_matches(
        {
            **inputs,
            "normal-rules": {
                "rules": [
                    r
                    for r in inputs.get("normal-rules", {}).get("rules", [])
                    if r["concern_key"] in definitions
                ]
            },
        }
    ):
        i = by_id.get(m["interaction_id"])
        if (
            i
            and i["direction"] == "return"
            and m["concern_key"] == "service.business_attribute_constraint"
        ):
            from scene_completion.analysis.concerns.concern_hierarchy import (
                response_business_contract,
            )

            if any(
                response_business_contract(g, i, inputs) for g in m.get("activation_evidence", [])
            ):
                add(i, m["concern_key"], "sender", m["concrete_rule"], m["source_refs"], POSITIVE)
        if (
            i
            and "resource_existence" in m["concern_key"]
            and context(i, inputs)["kinds"] & {"read", "update", "delete"}
            and re.search(r"存在|exist", m.get("concrete_rule") or "", re.I)
        ):
            add(i, m["concern_key"], "receiver", m["concrete_rule"], m["source_refs"], POSITIVE)
    return list({fingerprint(r): r for r in result}.values())
