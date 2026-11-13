"""Adapt the supported independent analysis import format to SSD results."""

from copy import deepcopy

from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.ssd.construction import channel, ident, pending, unique
from scene_completion.inputs.documents.ssd_adapter import normalize_extracted_case


def imported_bundle(value):
    """Preserve an existing Code Agent result while changing only its wire shape."""

    original = value.get("bundle", value)
    if original.get("version") != "scene-case-analysis-v1":
        raise ValueError("仅支持 scene-case-analysis-v1 导入结果适配")
    bundle = normalize_extracted_case(
        original["case"],
        original["ssd"],
        original.get("api_parameters"),
        original.get("business_entities"),
        documents=original.get("sources", []),
    )
    # The imported G is the submitted research result. Re-running our generator
    # here would change its meaning and silently invalidate old decisions.
    bundle["channels"] = {name: channel() for name in ("G", "E", "GT")}
    bundle["registry"] = deepcopy(original.get("registry") or default_registry())
    bundle["imported_version"] = original["version"]
    bundle["imported_scope"] = original.get("scope", "all")
    steps = {s["id"]: s for s in bundle["steps"]}
    docs = {d["id"]: d for d in bundle["documents"]}

    def references(rows):
        return [
            {
                "document_id": r.get("document_id") or r["source_id"],
                "start_line": r.get("start_line", r.get("line_start", 1)),
                "end_line": r.get("end_line", r.get("line_end", 1)),
                "quote": r.get("quote", ""),
                "kind": r.get("kind")
                or (
                    "test" if docs.get(r.get("source_id"), {}).get("role") == "test" else "context"
                ),
                **({"json_pointer": r["json_pointer"]} if r.get("json_pointer") else {}),
            }
            for r in rows or []
        ]

    def anchor(row):
        sid = row.get("step_id") or row.get("interaction_id")
        step = steps.get(sid)
        target = row.get("target")
        if target == "operation":
            target = "sender" if step and step["direction"] == "return" else "receiver"
        field = None
        name = row.get("field") or row.get("object")
        location = row.get("data_location")
        if target == "data" or str(row.get("concern_key", "")).startswith("api.data."):
            target = "data"
            candidates = [
                p
                for p in (step or {}).get("data", [])
                if p["name"] == name and (not location or p["location"] == location)
            ]
            if len(candidates) == 1:
                field = candidates[0]["id"]
        if target is None:
            target = (
                "sender" if str(row.get("concern_key", "")).startswith("human.") else "receiver"
            )
        return sid, target, field

    for name in ("G", "E", "GT"):
        old = original["channels"][name]
        output = bundle["channels"][name]
        binding_map = {}
        for n, row in enumerate(old.get("concerns", [])):
            sid, target, field = anchor(row)
            key = row.get("key") or row["concern_key"]
            cid = (
                row.get("id")
                or row.get("binding_id")
                or ident(
                    name + "-concern",
                    original["case"]["id"],
                    sid,
                    target,
                    field,
                    key,
                    row.get("entity_id"),
                )
            )
            if key.startswith("global."):
                output["pending"].append(
                    pending(
                        cid,
                        row.get("concrete_rule", key),
                        references(row.get("source_refs")),
                        reason="全局关注点留待后续，本轮不计分",
                        original=row,
                    )
                )
                continue
            status = (
                "active"
                if row.get("status", "applicable") in {"applicable", "active"}
                else "pending"
            )
            if sid not in steps or target == "data" and field is None:
                status = "unbound"
            concern = {
                "id": cid,
                "step_id": sid,
                "target": target,
                "key": key,
                "label": bundle["registry"]["definitions"].get(key, {}).get("label", key),
                "field_id": field,
                "entity_id": row.get("entity_id"),
                "condition": row.get("condition")
                or row.get("concrete_rule")
                or row.get("basis")
                or key,
                "status": status,
                "source_refs": references(row.get("source_refs")),
                "imported_record": deepcopy(row),
            }
            if row.get("rule_id"):
                concern["rule_id"] = row["rule_id"]
            # Legacy rows may repeat one binding with additional provenance.
            existing = next((c for c in output["concerns"] if c["id"] == cid), None)
            if existing:
                existing["source_refs"] = unique(existing["source_refs"] + concern["source_refs"])
            else:
                output["concerns"].append(concern)
            for old_id in (row.get("binding_id"), row.get("id")):
                if old_id:
                    binding_map[old_id] = cid
        for row in old.get("scenarios", []):
            key = row.get("key") or row["concern_key"]
            condition = (
                row.get("condition")
                or row.get("cause")
                or row.get("steps", {}).get("trigger")
                or "；".join(row.get("conditions", []))
            )
            expected = (
                row.get("expected")
                or row.get("expected_result")
                or "；".join(
                    s.get("action", "")
                    for s in row.get("steps", {}).get("documented_follow_up", [])
                )
            )
            sid, target, field = anchor(row)
            matching = [
                c
                for c in output["concerns"]
                if c["step_id"] == sid
                and c["key"] == key
                and (field is None or c["field_id"] == field)
            ]
            if len(matching) > 1 and row.get("object"):
                exact_object = [
                    c for c in matching if c["imported_record"].get("object") == row["object"]
                ]
                if exact_object:
                    matching = exact_object
            mapped = [
                binding_map[x] for x in row.get("concern_binding_ids", []) if x in binding_map
            ]
            if mapped:
                matching = [c for c in output["concerns"] if c["id"] in mapped]
            if len(matching) == 1:
                target, field = matching[0]["target"], matching[0]["field_id"]
            if key.startswith("global."):
                output["pending"].append(
                    pending(
                        row["id"],
                        condition,
                        references(row.get("source_refs")),
                        reason="全局关注点留待后续，本轮不计分",
                        original=row,
                    )
                )
                continue
            status = (
                "active"
                if row.get("scenario_type", "exception") == "exception"
                and row.get("status") not in {"pending", "unbound"}
                else "pending"
            )
            if sid not in steps or len(matching) != 1 or target == "data" and field is None:
                status = "unbound"
            output["scenarios"].append(
                {
                    "id": row["id"],
                    "step_id": sid,
                    "target": target,
                    "key": key,
                    "field_id": field,
                    "entity_id": matching[0].get("entity_id") if len(matching) == 1 else None,
                    "concern_ids": [c["id"] for c in matching],
                    "condition": condition,
                    "conditions": deepcopy(row.get("conditions", [])),
                    "expected": expected,
                    "source_refs": references(row.get("source_refs")),
                    "status": status,
                    "imported_record": deepcopy(row),
                }
            )
        for n, item in enumerate(old.get("pending", [])):
            output["pending"].append(
                pending(
                    ident(name + "-pending", original["case"]["id"], n),
                    item if isinstance(item, str) else item.get("condition", "待确认"),
                    references(old.get("source_refs")),
                    original=item,
                )
            )
    for pair, rows in original.get("decisions", {}).items():
        for row in rows:
            bundle["decisions"].append(
                {
                    **deepcopy(row),
                    "id": row.get("id") or ident("decision", pair, row["left_id"], row["right_id"]),
                    "pair": pair,
                    "level": "scenario",
                    "origin": row.get("origin", "auto"),
                }
            )
    bundle["pending"] += [
        pending(
            ident("import-pending", original["case"]["id"], n),
            item if isinstance(item, str) else item.get("condition", "待确认"),
            original=item,
        )
        for n, item in enumerate(original.get("pending", []))
    ]
    return bundle
