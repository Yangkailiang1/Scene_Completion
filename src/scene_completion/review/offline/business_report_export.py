"""Editable offline report based on the confirmed, saved scenario classification."""

from scene_completion.domain.concern_registry import registry
from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.current_scope import allowed
from scene_completion.review.offline import adoption
from scene_completion.review.offline._teacher_report_template import TEMPLATE, TITLE
from scene_completion.review.offline.ssd_review import _safe_json

FORMAT = "ssd-business-report-v1"
CATEGORIES = ("covered", "g_only", "gt_only")
EVIDENCE_FIELDS = ("id", "condition", "expected", "source_refs", "requirement_refs")


def _evidence(record):
    return {key: record[key] for key in EVIDENCE_FIELDS if record.get(key)}


def _step_text(step):
    return next(
        (
            ref["quote"]
            for ref in step.get("source_refs", [])
            if ref.get("kind") == "origin"
            and not ref.get("json_pointer")
            and (ref.get("origin") or {}).get("match") != "pending"
            and ref.get("quote")
        ),
        step.get("description") or step.get("operation", {}).get("name") or "",
    ).strip()


def _interaction_context(primary, cells, steps, *, aligned):
    candidates = [cells["E"]] if aligned and cells["G"] else []
    candidates.extend(([primary], cells["GT"]))
    for records in candidates:
        verified_ids = dict.fromkeys(
            ident
            for record in records
            if not record.get("failure_step_pending")
            for ident in (record.get("failure_step_id"), *record.get("failure_step_ids", []))
            if ident in steps
        )
        if verified_ids:
            return "实际失败步骤", [steps[ident] for ident in verified_ids]
    ident = primary.get("step_id")
    return "关联步骤", [steps[ident]] if ident in steps else []


def _shared_call_context(primary, service, catalog):
    members = {
        (member.get("case_id"), member.get("step_id")) for member in primary.get("members", [])
    }
    calls = [
        call
        for call in service.get("calls", [])
        if (call.get("case_id"), call.get("step_id")) in members
    ]
    contexts = []
    for call in calls:
        text = _step_text({**call, "operation": {"name": call.get("operation")}})
        if not text:
            continue
        case_id = call.get("case_id")
        name = catalog.get(case_id, {}).get("name", case_id)
        contexts.append(
            {
                "text": f"{name} · {text}" if name else text,
                "source_refs": call.get("source_refs", []),
            }
        )
    return contexts


def _scenario_text(primary, cells, steps, service, catalog, *, aligned):
    if service:
        step_label = "关联外部服务调用"
        evidence = _shared_call_context(primary, service, catalog)
        context = evidence[0]["text"] if evidence else service.get("name", "")
        if len(evidence) > 1:
            context += f"（另有 {len(evidence) - 1} 个调用，见原文与依据）"
    else:
        step_label, related = _interaction_context(primary, cells, steps, aligned=aligned)
        evidence = [
            {"text": text, "source_refs": step.get("source_refs", [])}
            for step in related
            if (text := _step_text(step))
        ]
        context = "\n".join(dict.fromkeys(item["text"] for item in evidence))
    condition = primary.get("condition") or primary.get("label") or ""
    return "\n".join(
        line
        for line in (
            f"{step_label} · {context}" if context else "",
            f"具体异常 · {condition}" if condition else "",
        )
        if line
    ), evidence


def _scene(row, category, definitions, concerns, steps, services, catalog, *, aligned):
    primary = row["cells"]["GT" if category == "gt_only" else "G"][0]
    step = steps.get(row["anchor_id"], {})
    service = services.get(row["anchor_id"], {})
    text, step_evidence = _scenario_text(
        primary, row["cells"], steps, service, catalog, aligned=aligned
    )
    result = {
        "id": row["id"],
        "text": text,
        "step_evidence": step_evidence,
        "classification": row["classification_reason"],
        "links": row["links"],
        "evidence": {
            channel: [
                {
                    **_evidence(record),
                    "members": [
                        {**_evidence(member), "case_id": member.get("case_id")}
                        for member in record.get("members", [])
                    ],
                }
                for record in rows
            ]
            for channel, rows in row["cells"].items()
        },
    }
    if category != "g_only":
        return result

    concern = next(
        (concerns[cid] for cid in primary.get("concern_ids", []) if cid in concerns),
        {},
    )
    label = definitions.get(row["key"], {}).get("label") or concern.get("label") or row["key"]
    target = concern.get("target") or primary.get("target")
    context = ""
    if target in {"sender", "receiver"}:
        party = step.get(target) or {}
        if party.get("name"):
            side = "发送方" if target == "sender" else "接收方"
            context = f"{side} {party['name']}"
    elif target == "service":
        if service.get("name"):
            context = f"外部服务 {service['name']}"
    elif primary.get("entity_id"):
        context = ".".join(filter(None, (primary.get("entity_id"), primary.get("attribute"))))
    elif primary.get("field_id"):
        field = next((f for f in step.get("data", []) if f["id"] == primary["field_id"]), None)
        if field:
            context = field["name"]
    analysis = primary.get("analysis") or concern.get("analysis")
    result["concern_key"] = row["key"]
    result["concern"] = label
    result["reason"] = "\n".join(
        part for part in (f"{context} · {label}" if context else "", analysis) if part
    )
    return result


def _group(item, catalog):
    bundle = item["bundle"]
    case_id = item["key"] if item["scope"] == "interaction" else None
    definitions = bundle.get("registry", {}).get("definitions", {})
    concerns = {concern["id"]: concern for concern in bundle["channels"]["G"]["concerns"]}
    steps = {step["id"]: step for step in bundle.get("steps", [])}
    services = {service["id"]: service for service in bundle.get("anchors", [])}
    return {
        "id": item["id"],
        "case_id": case_id,
        "name": item["name"],
        "complete": catalog.get(case_id, {}).get("complete", True),
        "revision": item["base_revision"],
        "bundle": {"documents": bundle.get("documents", [])},
        "categories": {
            category: [
                _scene(
                    row,
                    category,
                    definitions,
                    concerns,
                    steps,
                    services,
                    catalog,
                    aligned=bundle.get("coverage_policy") == GRAIN_POLICY,
                )
                for row in rows
            ]
            for category, rows in item["categories"].items()
        },
        "excluded": item["report_excluded"],
    }


def export_html(project, body=None):
    snapshot = adoption._collect(project, body, include_reference=False)
    report = snapshot["report"]
    catalog = {case["id"]: case for case in report["cases"]}
    groups = [_group(item, catalog) for item in snapshot["items"]]
    if report["case_details_included"] and not (body or {}).get("item_ids"):
        published = {group["case_id"] for group in groups}
        groups.extend(
            {
                "id": "interaction:" + case["id"],
                "case_id": case["id"],
                "name": case["name"],
                "complete": False,
                "bundle": {"documents": []},
                "categories": {category: [] for category in CATEGORIES},
                "excluded": [],
            }
            for case in catalog.values()
            if case["id"] not in published
        )
    groups.sort(key=lambda group: group["case_id"] is None)
    payload = {
        "format": FORMAT,
        "report": {
            **report,
            "title": TITLE,
            "groups": groups,
            "concern_options": {
                key: definition["label"]
                for key, definition in registry()["definitions"].items()
                if definition.get("enabled", True)
                and definition.get("kind", "check") == "check"
                and definition.get("scope", "interaction") == "interaction"
                and allowed({"key": key})
            },
        },
        "edits": {"groups": {}, "scenes": {}, "causes": {"g_only": [], "gt_only": []}},
    }
    return TEMPLATE.replace("__TEACHER_REPORT_JSON__", _safe_json(payload), 1)
