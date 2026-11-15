"""Offline project-scope review using the shared self-contained HTML reader."""

import json
from copy import deepcopy
from datetime import datetime, timezone

from scene_completion.application import project_scope_service as results
from scene_completion.infrastructure.identity import fingerprint
from scene_completion.review.offline._ssd_review_template import TEMPLATE
from scene_completion.review.offline.ssd_review import _diff, _PayloadParser, _safe_json

FORMAT = "project-review-v1"
EDITABLE = {"channels", "decisions", "review_notes"}


def export_review(project, body):
    from scene_completion.review.offline.adoption import export_html

    return export_html(project, body)


def export_legacy_review(project, body):
    scope = body.get("scope")
    if scope not in {"business_chain", "architecture"}:
        raise ValueError("请指定有效的项目分析范围")
    view = results.editor(project, scope)
    selected = set(body["record_ids"]) if body.get("record_ids") is not None else None
    anchors = set(body["anchor_ids"]) if body.get("anchor_ids") is not None else None
    rows = []
    for kind, level in (("concerns", "concern"), ("scenarios", "scenario")):
        for row in view["comparison"][kind]:
            ids = {row["id"]} | {r["id"] for records in row["cells"].values() for r in records}
            if row["status"] == "triple" or (
                anchors is not None and row.get("anchor_id") not in anchors
            ):
                continue
            if selected is not None and not ids.intersection(selected):
                continue
            rows.append({**deepcopy(row), "level": level})
    bundle = deepcopy(view["bundle"])
    payload = {
        "format": FORMAT,
        "scope": scope,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "cases": [
            {
                "scope": scope,
                "name": bundle["scope"]["name"],
                "base_revision": view["revision"],
                "baseline": deepcopy(bundle),
                "bundle": bundle,
                "rows": rows,
            }
        ],
    }
    return (
        TEMPLATE.replace("SSD 差异校对", "项目差异校对")
        .replace("SSD差异校对", "项目差异校对")
        .replace("__SSD_REVIEW_JSON__", _safe_json(payload))
    )


def _parse(content):
    if isinstance(content, str):
        if len(content) > 32 * 1024 * 1024:
            raise ValueError("审核文件超过 32 MB")
        content = content.lstrip("\ufeff \r\n\t")
        if not content.startswith("{"):
            parser = _PayloadParser()
            parser.feed(content)
            if parser.count != 1 or parser.active:
                raise ValueError("HTML 须包含且仅包含一份完整的审核 JSON")
            content = "".join(parser.parts)
        payload = json.loads(content)
    elif isinstance(content, dict):
        payload = deepcopy(content)
    else:
        raise ValueError("请提供审核 HTML 或 JSON")
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ValueError("不支持的项目审核格式")
    if payload.get("scope") not in {"business_chain", "architecture"}:
        raise ValueError("未知项目审核范围")
    entries = payload.get("cases")
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError("审核文件须包含一个明确的项目范围")
    entry = entries[0]
    if entry.get("scope") != payload["scope"] or type(entry.get("base_revision")) is not int:
        raise ValueError("项目范围或修订身份不一致")
    for key in ("baseline", "bundle"):
        if entry.get(key, {}).get("scope", {}).get("id") != payload["scope"]:
            raise ValueError("审核原始版与修订版的范围不一致")
    return payload, entry


def _inspect(project, payload, entry):
    current = results.editor(project, payload["scope"])
    baseline, proposed, live = entry["baseline"], entry["bundle"], current["bundle"]
    changes = _diff(baseline, proposed)
    feedback_id = (
        "project-offline-" + fingerprint([payload["scope"], entry["base_revision"], changes])[:24]
    )
    item = {
        "scope": payload["scope"],
        "base_revision": entry["base_revision"],
        "current_revision": current["revision"],
        "changes": changes,
        "conflicts": [],
        "feedback_id": feedback_id,
    }
    # Compare against the actual exported revision, never trust a supplied baseline.
    actual = results.editor(project, payload["scope"], entry["base_revision"])["bundle"]
    if baseline != actual:
        item["conflicts"].append("导出原始版与工作台修订不一致，请重新导出")
    for key in (baseline.keys() | proposed.keys()) - EDITABLE:
        if baseline.get(key) != proposed.get(key):
            item["conflicts"].append("审核文件不可修改原始上下文：" + key)
    already = any(x.get("id") == feedback_id for x in live.get("review_feedback", []))
    same = all(proposed.get(k) == live.get(k) for k in EDITABLE)
    if item["conflicts"]:
        item["status"] = "conflict"
    elif already or not changes or same:
        item["status"] = "unchanged"
    elif current["revision"] != entry["base_revision"]:
        item["status"] = "conflict"
        item["conflicts"].append("结果已有新修订，请重新导出核对；不会覆盖当前修改")
    else:
        item["status"] = "ready"
    return item, current


def preview_feedback(project, content, *, adoption_only=False):
    from scene_completion.review.offline import adoption

    if adoption.accepts(content):
        rows = adoption.feedback(project, content)["cases"]
        return (
            rows[0]
            if rows
            else {"scope": None, "status": "unchanged", "changes": [], "conflicts": []}
        )
    if adoption_only:
        raise ValueError("请使用business-adoption-v2审核文件，当前采纳入口不修改E/G")
    payload, entry = _parse(content)
    return _inspect(project, payload, entry)[0]


def apply_feedback(project, content, scope=None, *, adoption_only=False):
    from scene_completion.review.offline import adoption

    if adoption.accepts(content):
        if scope not in {"business_chain", "architecture"}:
            raise ValueError("请选择要应用的项目范围")
        rows = adoption.feedback(project, content, apply=True, selected=[scope])["cases"]
        return (
            rows[0]
            if rows
            else {"scope": scope, "status": "unchanged", "changes": [], "conflicts": []}
        )
    if adoption_only:
        raise ValueError("请使用business-adoption-v2审核文件，当前采纳入口不修改E/G")
    payload, entry = _parse(content)
    if scope != payload["scope"]:
        raise ValueError("请选择并确认要应用的项目范围")
    item, current = _inspect(project, payload, entry)
    if item["status"] != "ready":
        return item
    bundle = deepcopy(current["bundle"])
    for key in EDITABLE:
        if key in entry["bundle"]:
            bundle[key] = deepcopy(entry["bundle"][key])
        else:
            bundle.pop(key, None)
    bundle.setdefault("review_feedback", []).append(
        {"id": item["feedback_id"], "base_revision": entry["base_revision"]}
    )
    try:
        saved = results.save_revision(
            project,
            scope,
            {
                "base_revision": current["revision"],
                "bundle": bundle,
                "reason": "离线业务审核回导",
            },
        )
    except results.RevisionConflict as error:
        return {
            **item,
            "status": "conflict",
            "current_revision": error.current_revision,
            "conflicts": [str(error)],
        }
    return {**item, "status": "applied", "revision": saved["revision"]}
