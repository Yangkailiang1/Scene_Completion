"""Editable offline report based on the confirmed, saved scenario classification."""

from scene_completion.review.offline import adoption
from scene_completion.review.offline._teacher_report_template import TEMPLATE
from scene_completion.review.offline.ssd_review import _safe_json

FORMAT = "ssd-business-report-v1"
CATEGORIES = ("covered", "g_only", "gt_only")
EVIDENCE_FIELDS = ("id", "condition", "expected", "source_refs", "requirement_refs")


def _evidence(record):
    return {key: record[key] for key in EVIDENCE_FIELDS if record.get(key)}


def _scene(row, category, definitions, concerns, steps, services):
    primary = row["cells"]["GT" if category == "gt_only" else "G"][0]
    result = {
        "id": row["id"],
        "text": primary.get("condition") or primary.get("label") or "",
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
    step = steps.get(row["anchor_id"], {})
    target = concern.get("target") or primary.get("target")
    context = ""
    if target in {"sender", "receiver"}:
        party = step.get(target) or {}
        if party.get("name"):
            side = "发送方" if target == "sender" else "接收方"
            context = f"{side} {party['name']}"
    elif target == "service":
        service = services.get(row["anchor_id"], {})
        if service.get("name"):
            context = f"外部服务 {service['name']}"
    elif primary.get("entity_id"):
        context = ".".join(filter(None, (primary.get("entity_id"), primary.get("attribute"))))
    elif primary.get("field_id"):
        field = next((f for f in step.get("data", []) if f["id"] == primary["field_id"]), None)
        if field:
            context = field["name"]
    analysis = primary.get("analysis") or concern.get("analysis")
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
                _scene(row, category, definitions, concerns, steps, services) for row in rows
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
        "report": {**report, "groups": groups},
        "edits": {"groups": {}, "scenes": {}, "causes": {"g_only": [], "gt_only": []}},
    }
    return TEMPLATE.replace("__TEACHER_REPORT_JSON__", _safe_json(payload), 1)
