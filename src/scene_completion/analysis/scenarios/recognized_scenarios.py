"""Expand validated positive observations without consulting E, GT or matches.

Recognition and normal-rule extraction are independent. An omitted normal-rule
row must not discard a specific, evidenced condition already recognized in Gc.
These are conditional violations, not invented executable tests or protocols.
"""

import re

from scene_completion.infrastructure.storage import fingerprint


def evidenced_rules(inputs, security_covered=()):
    from scene_completion.analysis.matching.concern_alignment import definite

    keys = {
        "service.business_attribute_constraint": "business",
        "service_relation.data_isolation": "authorization",
        "service_relation.authentication": "authentication",
        "service_relation.authorization": "authorization",
    }
    known = {
        (r["interaction_id"], r["concern_key"], compact(r["condition"]))
        for r in inputs.get("normal-rules", {}).get("rules", [])
        if r["concern_key"]
        not in {"service_relation.authentication", "service_relation.authorization"}
    }
    for match in definite(inputs.get("concern-match", {})).values():
        key = match["concern_key"]
        if key not in keys:
            continue
        if (match["interaction_id"], key) in security_covered:
            continue
        for guard in match.get("activation_evidence", []):
            condition = guard.get("condition", "").strip()
            if (
                guard.get("kind") != keys[key]
                or guard.get("status") != "explicit"
                or not guard.get("source_refs")
                or guard.get("value") is False
                or not condition
                or len(condition) > 500
                or condition.startswith(("{", "["))
            ):
                continue
            # Token mechanisms retain their own granular security patterns.
            # Caller allowlists are also authentication, but do not imply that
            # a token, signature, expiry or revocation mechanism exists.
            if key.endswith(".authentication") and (
                not re.search(r"身份|调用方|service[-_]?id|caller", condition, re.I)
                or re.search(r"token|凭证|签名|有效期|撤销", condition, re.I)
            ):
                continue
            identity = (match["interaction_id"], key, compact(condition))
            if identity in known:
                continue
            known.add(identity)
            yield {
                "id": "recognized-rule-" + fingerprint(identity)[:20],
                "interaction_id": match["interaction_id"],
                "concern_key": key,
                "condition": condition,
                "violation": "不满足明示规则：" + condition,
                "fields": [],
                "source_refs": guard["source_refs"],
                "activation_evidence": [guard],
                "resolution": "conditional",
                "pending_details": ["具体执行数据及故障注入方式尚未准备"],
                "recognized_binding_id": match["binding_id"],
                "object": match["object"],
            }


def compact(text):
    return re.sub(r"\s+", "", text).rstrip("。.;；")


def scenarios(inputs, security_covered=()):
    from scene_completion.analysis.interactions.interaction_enrichment import interactions
    from scene_completion.analysis.scenarios.exception_generation import scenario_steps

    rows = {i["id"]: i for i in interactions(inputs)}
    out = []
    for r in evidenced_rules(inputs, security_covered):
        i = rows.get(r["interaction_id"])
        if not i:
            continue
        scene = {
            "id": "G-" + r["id"],
            "case_id": i["case_id"],
            "interaction_id": i["id"],
            "layer": i["layer"],
            "object": r["object"],
            "operation": i["operation"]["name"],
            "cause": r["violation"],
            "conditions": [r["violation"]],
            "concern_key": r["concern_key"],
            "field": None,
            "rule_id": r["id"],
            "source_status": "framework_inferred",
            "derivation": "已通过证据校验的关注点规则取反；不补造具体机制或响应",
            "source_refs": r["source_refs"],
            "activation_evidence": r["activation_evidence"],
            "steps": scenario_steps(i, [r["violation"]]),
            "scope": "service",
            "data_location": None,
            "resolution": r["resolution"],
            "executable": False,
            "pending_details": r["pending_details"],
        }
        # A declared caller allowlist may also be a discrete field range.
        # Preserve its independent bindings on one concrete failure unit.
        guard = r["activation_evidence"][0]
        field = guard.get("field")
        if guard.get("constraint_kind") == "enum" and field:
            from scene_completion.analysis.interactions.interaction_enrichment import parameters_for

            params = [p for p in parameters_for(i, inputs) if p["name"] == field]
            enums = [
                c
                for p in params
                for c in p["constraints"]
                if c["kind"] == "enum" and c["status"] == "explicit"
            ]
            if len(params) == len(enums) == 1:
                scene.update(
                    object=field,
                    field=field,
                    scope="interface",
                    data_location=params[0]["location"],
                    failure_rule={"kind": "enum", "value": enums[0]["value"]},
                )
        out.append(scene)
    return out
