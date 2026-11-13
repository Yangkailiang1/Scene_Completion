"""Deduplicate one explicitly injected caller-field failure within its own test.

Only a single literal enum violation with an independently recognized caller
guard qualifies. Multiple fields, values, messages and unknown predicates stay
separate for semantic review. No G/E or matching result is consulted.
"""

import json
import re

from scene_completion.infrastructure.storage import fingerprint


def merge_caller_enum(units, record, inputs):
    from scene_completion.analysis.interactions.interaction_enrichment import parameters_for

    if len(units) < 2 or len({s["interaction_id"] for s in units}) != 1:
        return []
    keys = {s["concern_key"] for s in units}
    security = {
        "service_relation.authentication",
        "service_relation.authorization",
        "service_relation.data_isolation",
    }
    if not keys & security or not keys <= security | {"api.data.range"}:
        return []
    iid = units[0]["interaction_id"]
    i = next(
        (i for i in inputs.get("fused-ssd", {}).get("interactions", []) if i["id"] == iid), None
    )
    if not i or i["direction"] != "request":
        return []
    material = {**inputs, "api-parameters": inputs.get("normal-constraints", {})}
    assignments = []
    for p in parameters_for(i, material):
        pattern = (
            r"(?<![A-Za-z0-9_])(?:" + re.escape(p["location"]) + r"\.)?" + re.escape(p["name"])
        )
        matches = re.findall(pattern + r"\s*=\s*([^\s，,；;。]+)", record["触发条件"])
        if matches:
            assignments.append((p, matches))
    if len(assignments) != 1 or len(assignments[0][1]) != 1:
        return []
    p, values = assignments[0]
    literal = values[0].strip("\"'`")
    try:
        literal = json.loads(literal)
    except (ValueError, TypeError):
        pass
    enums = [
        r["value"] for r in p["constraints"] if r["kind"] == "enum" and r["status"] == "explicit"
    ]
    if len(enums) != 1 or not isinstance(enums[0], list) or literal in enums[0]:
        return []
    guards = [
        g
        for m in inputs.get("identified-concerns", {}).get("matches", [])
        if m["interaction_id"] == iid
        and m["concern_key"] in security
        and m.get("status") == "applicable"
        for g in m.get("activation_evidence", [])
    ]
    if not any(
        g.get("field") == p["name"]
        and g.get("constraint_kind") == "enum"
        and g.get("status") == "explicit"
        and g.get("source_refs")
        for g in guards
    ):
        return []
    primary = next((s for s in units if s.get("field") == p["name"]), units[0])
    primary.update(
        object=p["name"],
        field=p["name"],
        data_location=p["location"],
        scope="interface",
        conditions=[record["触发条件"]],
        cause=record["触发条件"],
        failure_rule={"kind": "enum", "value": enums[0]},
    )
    primary["concern_origins"] = sorted(
        keys | {k for s in units for k in s.get("concern_origins", [])}
    )
    for field in ("source_refs", "source_unit_ids", "concern_binding_ids", "element_anchors"):
        rows = [
            v for s in units for v in s.get(field, [s["id"]] if field == "source_unit_ids" else [])
        ]
        primary[field] = list({fingerprint(v): v for v in rows}.values())
    primary.setdefault("quality_notes", []).append(
        "同一测试在同一报文只注入一个已声明的调用方枚举违例；关联多个关注点，独立失败仅计一次"
    )
    return [s["id"] for s in units if s is not primary]
