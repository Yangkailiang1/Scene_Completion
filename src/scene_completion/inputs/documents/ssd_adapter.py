"""Adapt previously normalized input artifacts to the shared SSD case contract."""

from copy import deepcopy

from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.ssd.construction import (
    add_concern,
    add_scenario,
    channel,
    ident,
    pending,
    unique,
)


def normalize_extracted_case(
    case,
    fused_ssd,
    api_parameters=None,
    business_entities=None,
    existing=None,
    tests=None,
    documents=None,
):
    from scene_completion.analysis.ssd.inverse import recognize_records
    from scene_completion.analysis.ssd.pipeline import (
        RULE_VERSION,
        VERSION,
        _enrich_fields,
        generate_g,
    )

    case = {"id": case, "name": case} if isinstance(case, str) else deepcopy(case)
    source_docs = []
    for doc in documents or []:
        text = doc.get("content")
        if text is None:
            lines = {row["number"]: row["text"] for row in doc.get("lines", [])}
            text = "\n".join(lines.get(n, "") for n in range(1, max(lines, default=0) + 1))
        source_docs.append(
            {
                "id": doc.get("id") or doc.get("source_id") or ident("document", doc.get("name")),
                "name": doc.get("name") or doc.get("source_id") or "导入材料",
                "role": doc.get("role")
                or ("test" if doc.get("channel") == "test" else "intermediate"),
                "content": text,
            }
        )
    known = {d["id"]: d for d in source_docs}
    excerpt_ids = set()

    def refs(value, channel_name=None):
        output = []
        for ref in value or []:
            sid = ref.get("document_id") or ref.get("source_id")
            if not sid:
                continue
            start = ref.get("start_line", ref.get("line_start", 1))
            end = ref.get("end_line", ref.get("line_end", start))
            if sid not in known:
                doc = {
                    "id": sid,
                    "name": sid + "（来源摘录）",
                    "role": "test" if channel_name == "GT" else "intermediate",
                    "content": "",
                }
                source_docs.append(doc)
                known[sid] = doc
                excerpt_ids.add(sid)
            doc = known[sid]
            if sid in excerpt_ids:
                lines = doc["content"].splitlines()
                while len(lines) < end:
                    lines.append("")
                for offset, line in enumerate(ref.get("quote", "").splitlines()):
                    if start - 1 + offset < len(lines) and not lines[start - 1 + offset]:
                        lines[start - 1 + offset] = line
                doc["content"] = "\n".join(lines)
            lines = doc["content"].splitlines()
            quote = "\n".join(lines[start - 1 : end]) or ref.get("quote", "")
            kind = ref.get("kind") or ("test" if doc["role"] == "test" else "context")
            output.append(
                {
                    "document_id": sid,
                    "start_line": start,
                    "end_line": end,
                    "quote": quote,
                    "kind": kind,
                    **({"json_pointer": ref["json_pointer"]} if ref.get("json_pointer") else {}),
                }
            )
        return unique(output)

    contracts = {}
    apis = api_parameters or {}
    for api in apis if isinstance(apis, list) else apis.get("apis", []):
        fields = []
        for prop in api.get("parameters", api.get("fields", [])):
            fields.append(
                {
                    **deepcopy(prop),
                    "source_refs": refs(prop.get("source_refs")),
                    "constraints": [
                        {**deepcopy(c), "source_refs": refs(c.get("source_refs"))}
                        for c in prop.get("constraints", [])
                    ],
                }
            )
        value = {**deepcopy(api), "fields": fields, "source_refs": refs(api.get("source_refs"))}
        contracts[api["id"]] = value
        if api.get("declared_id"):
            contracts[api["declared_id"]] = value
    steps = []
    for row in (
        fused_ssd
        if isinstance(fused_ssd, list)
        else fused_ssd.get("interactions", fused_ssd.get("steps", []))
    ):
        if row.get("case_id") and row["case_id"] != case["id"]:
            continue
        if isinstance(row.get("data"), list) and row.get("kind"):
            steps.append(deepcopy(row))
            continue

        def person(value):
            position = str(value.get("position", ""))
            return {
                "id": value.get("id") or value["name"],
                "name": value["name"],
                "type": "human"
                if "人类" in position or value.get("type") == "human"
                else "service",
                "technology": value.get("technology")
                or (
                    "database" if "数据库" in position else "llm" if "AI模型" in position else None
                ),
                "external": value.get("external", "外部" in position),
            }

        step = {
            "id": row["id"],
            "order": row.get("sequence", len(steps) + 1),
            "kind": "action" if row.get("step_kind") == "action" else "interaction",
            "layer": row.get("layer", "SR"),
            "direction": row.get("direction", "request"),
            "sender": person(row["sender"]),
            "receiver": person(row["receiver"]),
            "operation": deepcopy(row["operation"]),
            "data": [],
            "api_id": row.get("api_id"),
            "entity_ids": row.get("entity_ids", []),
            "source_refs": refs(row.get("source_refs")),
            "aliases": row.get("aliases", []),
            "parent_id": row.get("parent_id"),
        }
        for field in row.get("data", {}).get("sequence", []):
            location = field.get("location", "business")
            step["data"].append(
                {
                    "id": ident("field", row["id"], location, field["name"]),
                    "name": field["name"],
                    "location": location,
                    "type": field.get("data_type"),
                    "required": field.get("required"),
                    "constraints": [
                        {**deepcopy(c), "source_refs": refs(c.get("source_refs"))}
                        for c in field.get("constraints", [])
                    ],
                    "source_refs": refs(field.get("source_refs")),
                }
            )
        _enrich_fields(step, contracts)
        steps.append(step)
    # Older imports sometimes used parent_id for call nesting rather than the
    # request that produced this response. Recover only an unambiguous reverse
    # endpoint pair and retain the supplied reference for audit.
    for index, step in enumerate(steps):
        if step["direction"] != "return":
            continue
        candidates = [
            r
            for r in steps[:index]
            if r["direction"] == "request"
            and r["kind"] != "action"
            and r["sender"]["id"] == step["receiver"]["id"]
            and r["receiver"]["id"] == step["sender"]["id"]
        ]
        if step.get("parent_id") not in {r["id"] for r in candidates}:
            step["original_parent_id"] = step.get("parent_id")
            step["parent_id"] = candidates[0]["id"] if len(candidates) == 1 else None
    entities = business_entities or []
    if isinstance(entities, dict):
        entities = entities.get("entities", [])

    def normalize_entity(value):
        if isinstance(value, dict):
            return {
                key: refs(item) if key == "source_refs" else normalize_entity(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [normalize_entity(item) for item in value]
        return deepcopy(value)

    entities = normalize_entity(entities)
    bundle = {
        "version": VERSION,
        "case": case,
        "steps": steps,
        "channels": {k: channel() for k in ("G", "E", "GT")},
        "documents": source_docs,
        "decisions": [],
        "pending": [],
        "entities": deepcopy(entities),
        "apis": unique(list(contracts.values())),
        "registry": default_registry(),
        "rule_version": RULE_VERSION,
    }
    bundle["channels"]["G"] = generate_g(bundle)
    by_id = {s["id"]: s for s in steps}
    for channel_name, payload in [("E", existing), ("GT", tests)]:
        if not payload:
            continue
        records = (
            payload
            if isinstance(payload, list)
            else payload.get("scenarios", payload.get("records", payload.get("branches", [])))
        )
        raw_records = []
        for n, record in enumerate(records):
            evidence = list(record.get("source_refs", []))
            evidence += [
                r
                for r in record.get("sources", [])
                if isinstance(r, dict)
                and (r.get("source_id") or r.get("document_id"))
                and (r.get("line_start") or r.get("start_line"))
            ]
            context = [
                {**r, "kind": "context"}
                for prop in ("requirement_refs", "context_refs")
                for r in record.get(prop, [])
            ]
            record_refs = refs(evidence + context, channel_name)
            rid = ident(channel_name + "-scenario", case["id"], record.get("id", n))
            condition = (
                record.get("condition")
                or record.get("trigger")
                or record.get("title")
                or record.get("description")
                or record.get("触发条件")
                or record.get("cause")
                or ""
            )
            expected = (
                record.get("expected")
                or record.get("expected_result")
                or record.get("response")
                or record.get("预期结果")
                or ""
            )
            key = record.get("concern_key") or record.get("key")
            step = by_id.get(record.get("interaction_id") or record.get("step_id"))
            if (
                record.get("scenario_type", "exception") == "exception"
                and record.get("status") not in {"pending", "unbound"}
                and key
                and step
                and key in bundle["registry"]["definitions"]
                and not key.startswith("global.")
            ):
                target = record.get("target") or (
                    "data"
                    if key.startswith("api.data.")
                    else "sender"
                    if key.startswith("human.")
                    else "receiver"
                )
                if target == "operation":
                    target = "receiver"
                field = next(
                    (
                        p
                        for p in step["data"]
                        if p["name"] == record.get("field")
                        and (
                            not record.get("data_location")
                            or p["location"] == record["data_location"]
                        )
                    ),
                    None,
                )
                if target == "data" and field is None:
                    bundle["channels"][channel_name]["pending"].append(
                        pending(
                            rid, condition, record_refs, reason="旧字段无法定位", original=record
                        )
                    )
                    continue
                c = add_concern(
                    bundle["channels"][channel_name],
                    bundle,
                    channel_name,
                    step,
                    key,
                    target,
                    field=field,
                    entity=record.get("entity_id"),
                    condition=condition,
                    refs=record_refs,
                )
                if c:
                    add_scenario(
                        bundle["channels"][channel_name], c, condition, expected, record_refs, rid
                    )
            else:
                raw_records.append(
                    {
                        "id": rid,
                        "condition": condition,
                        "expected": expected,
                        "source_refs": record_refs,
                        "scenario_type": "pending"
                        if record.get("status") in {"pending", "unbound"}
                        else record.get("scenario_type", "exception"),
                        "raw": record,
                    }
                )
        recognized = recognize_records(bundle, raw_records, channel_name)
        for key in ("concerns", "scenarios", "pending"):
            bundle["channels"][channel_name][key].extend(recognized[key])
        # Keep test evidence distinct from the normal SSD context that explains
        # where it was attached. This does not promote requirements into GT.
        for row in (
            bundle["channels"][channel_name]["concerns"]
            + bundle["channels"][channel_name]["scenarios"]
        ):
            step = by_id.get(row.get("step_id"))
            if step:
                row["source_refs"] = unique(
                    row["source_refs"]
                    + [{**deepcopy(r), "kind": "context"} for r in step.get("source_refs", [])]
                )
    return bundle
