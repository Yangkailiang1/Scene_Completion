"""Portable SSD discrepancy review, with data-only feedback import."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser

from ._ssd_review_template import TEMPLATE

FORMAT = "ssd-review-v1"
DATA_ID = "ssd-review-data"
EDITABLE = {"channels", "decisions", "review_notes", "review_feedback"}


def _results():
    from scene_completion.application import ssd_revision_service as ssd_results

    return ssd_results


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_json(value):
    return (
        _canonical(value)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def export_html(project, body=None):
    """Export selected discrepancy rows and enough context for offline provenance."""
    body = body or {}
    service = _results()
    available = service.index(project)["cases"]
    requested = body.get("case_ids")
    chosen = set(requested) if requested is not None else None
    record_ids = body.get("record_ids")
    selected = set(record_ids) if record_ids is not None else None
    known = {c["id"] for c in available}
    if chosen is not None and chosen - known:
        raise ValueError("未知用例：" + "、".join(sorted(chosen - known)))
    cases = []
    for case in available:
        if chosen is not None and case["id"] not in chosen:
            continue
        view = service.editor(project, case["id"])
        rows = []
        for collection, level in (("concerns", "concern"), ("scenarios", "scenario")):
            for row in view.get("comparison", {}).get(collection, []):
                if row.get("status") == "triple":
                    continue
                ids = {row["id"]} | {
                    record["id"] for records in row.get("cells", {}).values() for record in records
                }
                if selected is not None and not ids.intersection(selected):
                    continue
                rows.append({**deepcopy(row), "level": level})
        if not rows:
            continue
        bundle = deepcopy(view["bundle"])
        cases.append(
            {
                "case_id": case["id"],
                "name": case.get("name", case["id"]),
                "base_revision": view["revision"],
                "baseline": deepcopy(bundle),
                "bundle": bundle,
                "rows": rows,
            }
        )
    payload = {
        "format": FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "cases": cases,
    }
    return TEMPLATE.replace("__SSD_REVIEW_JSON__", _safe_json(payload))


class _PayloadParser(HTMLParser):
    """Extract a single JSON island; never evaluate scripts or external resources."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == DATA_ID:
            if attributes.get("type") != "application/json":
                raise ValueError("校对数据必须是 application/json")
            self.count += 1
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def _parse(content):
    if isinstance(content, str):
        if len(content) > 32 * 1024 * 1024:
            raise ValueError("校对文件超过 32 MB")
        text = content.lstrip("\ufeff \r\n\t")
        if text.startswith("{"):
            payload = json.loads(text)
        else:
            parser = _PayloadParser()
            parser.feed(text)
            if parser.count != 1 or parser.active:
                raise ValueError("HTML 中须包含且仅包含一份完整的校对 JSON 数据")
            payload = json.loads("".join(parser.parts))
    elif isinstance(content, dict):
        payload = deepcopy(content)
    else:
        raise ValueError("请提供校对 HTML 或 JSON")
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise ValueError("不支持的校对文件格式")
    if not isinstance(payload.get("cases"), list):
        raise ValueError("校对文件缺少 cases")
    ids = []
    for case in payload["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise ValueError("校对用例缺少稳定 ID")
        ids.append(case["case_id"])
        if "base_revision" not in case:
            raise ValueError("校对用例缺少导出时的版本")
        for key in ("baseline", "bundle"):
            bundle = case.get(key)
            if not isinstance(bundle, dict) or bundle.get("case", {}).get("id") != case["case_id"]:
                raise ValueError("校对用例身份不一致")
    if len(ids) != len(set(ids)):
        raise ValueError("校对文件包含重复用例")
    return payload


def _diff(before, after, path=""):
    """Readable paths follow record IDs, so changing list order creates no noise."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            changes.extend(_diff(before.get(key), after.get(key), f"{path}/{key}"))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        if all(isinstance(item, dict) and "id" in item for item in before + after):
            return _diff(
                {item["id"]: item for item in before}, {item["id"]: item for item in after}, path
            )
    return [{"path": path or "/", "before": before, "after": after}]


def _feedback_id(case):
    # A later edit of the same HTML is a new feedback revision, not a duplicate.
    identity = {"case_id": case["case_id"], "base_revision": case["base_revision"]}
    identity["changes"] = _diff(case["baseline"], case["bundle"])
    return "offline-" + hashlib.sha256(_canonical(identity).encode()).hexdigest()[:24]


def _inspect(project, case):
    current = _results().editor(project, case["case_id"])
    baseline, proposed, live = case["baseline"], case["bundle"], current["bundle"]
    changes = _diff(baseline, proposed)
    conflicts = []
    for key in (baseline.keys() | proposed.keys()) - EDITABLE:
        if baseline.get(key) != proposed.get(key):
            conflicts.append(f"禁止在校对文件中修改原始上下文：{key}")
    # Replaying feedback must never replace original documents/steps with an export.
    for key in (baseline.keys() | live.keys()) - EDITABLE:
        if baseline.get(key) != live.get(key):
            conflicts.append(f"原始上下文已变化：{key}；请重新导出")
    feedback_id = _feedback_id(case)
    already_applied = any(x.get("id") == feedback_id for x in live.get("review_feedback", []))
    proposed_editable = {k: proposed.get(k) for k in EDITABLE - {"review_feedback"}}
    live_editable = {k: live.get(k) for k in EDITABLE - {"review_feedback"}}
    if conflicts:
        status = "conflict"
    elif already_applied or not changes or proposed_editable == live_editable:
        status = "unchanged"
    elif current["revision"] != case["base_revision"]:
        status = "conflict"
        conflicts.append("结果已被其他修订更新；请重新导出并核对，现有修改不会被覆盖")
    else:
        status = "ready"
    return {
        "case_id": case["case_id"],
        "name": case.get("name", case["case_id"]),
        "status": status,
        "base_revision": case["base_revision"],
        "current_revision": current["revision"],
        "changes": changes,
        "conflicts": conflicts,
        "feedback_id": feedback_id,
    }, current


def _summary(cases):
    return {
        status: sum(case["status"] == status for case in cases)
        for status in ("ready", "unchanged", "conflict", "applied")
    }


def preview_feedback(project, content):
    payload = _parse(content)
    cases = []
    for case in payload["cases"]:
        try:
            item, _ = _inspect(project, case)
        except (ValueError, KeyError, FileNotFoundError) as exc:
            item = {
                "case_id": case["case_id"],
                "name": case.get("name", case["case_id"]),
                "status": "conflict",
                "conflicts": [str(exc)],
                "changes": [],
            }
        cases.append(item)
    return {"format": FORMAT, "cases": cases, "summary": _summary(cases)}


def apply_feedback(project, content, case_ids=None):
    payload = _parse(content)
    selected = set(case_ids) if case_ids is not None else None
    cases = []
    for case in payload["cases"]:
        if selected is not None and case["case_id"] not in selected:
            continue
        try:
            item, current = _inspect(project, case)
            if item["status"] == "ready":
                bundle = deepcopy(current["bundle"])
                for key in EDITABLE - {"review_feedback"}:
                    if key in case["bundle"]:
                        bundle[key] = deepcopy(case["bundle"][key])
                    else:
                        bundle.pop(key, None)
                bundle.setdefault("review_feedback", []).append(
                    {
                        "id": item["feedback_id"],
                        "base_revision": case["base_revision"],
                    }
                )
                saved = _results().save_revision(
                    project,
                    case["case_id"],
                    {
                        "base_revision": current["revision"],
                        "bundle": bundle,
                        "reason": "离线校对回导",
                    },
                )
                item["status"] = "applied"
                item["revision"] = saved["revision"]
        except (ValueError, KeyError, FileNotFoundError) as exc:
            item = {
                "case_id": case["case_id"],
                "name": case.get("name", case["case_id"]),
                "status": "conflict",
                "conflicts": [str(exc)],
                "changes": [],
            }
        cases.append(item)
    return {"format": FORMAT, "cases": cases, "summary": _summary(cases)}
