"""G-without-GT business adoption; feedback cannot rewrite source results."""

import json
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.coverage import review_candidates
from scene_completion.infrastructure.identity import fingerprint
from scene_completion.infrastructure.storage import read_json, write_json
from scene_completion.review.offline.ssd_review import _PayloadParser, _safe_json

FORMAT = "business-adoption-v2"
SCOPES = {
    "interaction": "交互级场景",
    "business_chain": "业务链路场景",
    "architecture": "项目架构场景",
    "shared_services": "共用外部服务",
}


def _service(scope):
    if scope == "shared_services":
        from scene_completion.application import shared_service_service
        from scene_completion.domain.project_scopes import matching

        return shared_service_service, matching
    if scope == "interaction":
        from scene_completion.application import ssd_revision_service
        from scene_completion.domain.ssd import matching

        return ssd_revision_service, matching
    from scene_completion.application import project_scope_service
    from scene_completion.domain.project_scopes import matching

    return project_scope_service, matching


def _requirement_refs(bundle, record):
    anchors = bundle.get("steps", bundle.get("anchors", []))
    anchor = next(
        (s for s in anchors if s["id"] == record.get("step_id", record.get("anchor_id"))), {}
    )
    field = next((f for f in anchor.get("data", []) if f["id"] == record.get("field_id")), {})
    refs = record.get("requirement_refs") or field.get("source_refs", []) + anchor.get(
        "source_refs", []
    )
    originals = {d["id"] for d in bundle.get("documents", []) if d.get("role") in {"RR", "SR"}}
    return [r for r in refs if r["document_id"] in originals]


def _collect(project, body=None):
    body = body or {}
    scopes = body.get("scopes", [body["scope"]] if body.get("scope") else list(SCOPES))
    items, by_scope = [], {}
    totals = {"covered": 0, "unfinished": 0, "inactive": 0, "exported": 0, "source_pending": 0}
    for scope in scopes:
        if scope not in SCOPES:
            raise ValueError("未知审核范围")
        service, matching = _service(scope)
        keys = (
            [
                c["id"]
                for c in service.index(project)["cases"]
                if body.get("case_ids") is None or c["id"] in body["case_ids"]
            ]
            if scope == "interaction"
            else [scope]
        )
        summary = {**dict.fromkeys(totals, 0), "available": False, "items": [], "reasons": {}}
        by_scope[scope] = summary
        for key in sorted(keys):
            try:
                view = service.editor(project, key)
            except ValueError:
                continue
            bundle = view["bundle"]
            statuses = view["review_statuses"]
            row_ids = {
                g["id"]: row["id"]
                for row in view["comparison"]["scenarios"]
                for g in row["cells"]["G"]
            }
            selected = [
                g
                for g in bundle["channels"]["G"]["scenarios"]
                if (
                    body.get("anchor_ids") is None
                    or g.get("anchor_id", g.get("step_id")) in body["anchor_ids"]
                )
                and (
                    body.get("record_ids") is None
                    or {g["id"], row_ids.get(g["id"])}.intersection(body["record_ids"])
                )
            ]
            selected_bundle = {
                **bundle,
                "channels": {
                    **bundle["channels"],
                    "G": {**bundle["channels"]["G"], "scenarios": selected},
                },
            }
            eligible, counters = review_candidates(selected_bundle, matching, statuses)
            rows = []
            for g in eligible:
                cells = {"G": [deepcopy(g)]}
                for ch in ("E", "GT"):
                    cells[ch] = [
                        deepcopy(r)
                        for r in bundle["channels"][ch]["scenarios"]
                        if matching.binding(r) == matching.binding(g)
                    ]
                for test_record in cells["GT"]:
                    test_record["requirement_refs"] = _requirement_refs(bundle, test_record)
                rows.append(
                    {
                        "id": "adoption-" + fingerprint([scope, key, g["id"]])[:24],
                        "anchor_id": g.get("anchor_id", g.get("step_id")),
                        "key": g["key"],
                        "cells": cells,
                    }
                )
            summary["available"] = True
            for name in totals:
                totals[name] += counters[name]
                summary[name] += counters[name]
            reasons = {}
            for g in selected:
                reason = statuses[g["id"]]["reason"]
                reasons[reason] = reasons.get(reason, 0) + 1
                summary["reasons"][reason] = summary["reasons"].get(reason, 0) + 1
            item = {
                "id": scope + ":" + key,
                "scope": scope,
                "key": key,
                "name": bundle.get("case", bundle.get("scope", {})).get("name", key),
                "base_revision": view["revision"],
                "bundle": deepcopy(bundle),
                "rows": rows,
                "review_statuses": statuses,
                "identification_proof": view["identification_proof"],
            }
            summary["items"].append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "revision": view["revision"],
                    "counts": {
                        ch: {
                            kind: len(bundle["channels"][ch].get(kind, []))
                            for kind in ("concerns", "scenarios", "pending")
                        }
                        for ch in ("E", "G", "GT")
                    },
                    "reasons": reasons,
                }
            )
            # Keep empty review lists: these bundles supply the complete read-only reference.
            items.append(item)
    totals["by_scope"] = by_scope
    return {"format": FORMAT, "items": items, "decisions": [], "excluded": totals}


def summary(project, body=None):
    payload = _collect(project, body)
    return {"format": FORMAT, "excluded": payload["excluded"]}


def export_payload(project, body=None):
    payload = _collect(project, body)
    payload["export_id"] = fingerprint([FORMAT, payload["items"], payload["excluded"]])
    write_json(
        Path(project) / "review_exports" / (payload["export_id"] + ".json"),
        {"context_hash": fingerprint([payload["items"], payload["excluded"]])},
    )
    return payload


def export_html(project, body=None):
    return render_html(export_payload(project, body))


def render_html(content):
    """Restyle a frozen reviewed payload without a new export, revision, or decision."""
    from scene_completion.review.offline._adoption_template import TEMPLATE

    return TEMPLATE.replace("__ADOPTION_JSON__", _safe_json(parse(content)))


def parse(content):
    if isinstance(content, dict):
        value = deepcopy(content)
    elif isinstance(content, str) and len(content) <= 32 * 1024 * 1024:
        text = content.lstrip("\ufeff \r\n\t")
        if not text.startswith("{"):
            parser = _PayloadParser()
            parser.feed(text)
            if parser.count != 1 or parser.active:
                raise ValueError("审核HTML须包含一份完整数据")
            text = "".join(parser.parts)
        value = json.loads(text)
    else:
        raise ValueError("请提供不超过32MB的审核文件")
    if (
        not isinstance(value, dict)
        or value.get("format") != FORMAT
        or not isinstance(value.get("items"), list)
        or not isinstance(value.get("decisions"), list)
    ):
        raise ValueError("无效的业务采纳文件")
    if any(
        not isinstance(r, dict)
        or not isinstance(r.get("id"), str)
        or r.get("scope") not in SCOPES
        or not isinstance(r.get("key"), str)
        or type(r.get("base_revision")) is not int
        or not isinstance(r.get("bundle"), dict)
        or not isinstance(r.get("rows"), list)
        for r in value["items"]
    ):
        raise ValueError("审核条目结构无效")
    if any(not isinstance(d, dict) for d in value["decisions"]):
        raise ValueError("审核决定必须为对象")
    if len({r["id"] for r in value["items"]}) != len(value["items"]):
        raise ValueError("审核范围重复")
    return value


def _business_members(record):
    """Calling context is requirement evidence, never fabricated test provenance."""
    return [
        {
            **deepcopy(m),
            "source": "business_review",
            "source_kind": "业务审核补充",
            "source_refs": [],
            "requirement_refs": deepcopy(m.get("requirement_refs", []) + m.get("source_refs", [])),
        }
        for m in record.get("members", [])
    ]


def _inspect(project, item, decisions):
    scope = item.get("scope")
    if scope not in SCOPES:
        raise ValueError("无效审核范围")
    service, _ = _service(scope)
    key = item["key"]
    actual = (
        {"bundle": item["bundle"]}
        if scope == "shared_services"
        else service.editor(project, key, item["base_revision"])
    )
    current = service.editor(project, key)
    conflicts = []
    if item["bundle"] != actual["bundle"]:
        conflicts.append("不可修改原文、上下文或三方原始结果")
    known = {r["id"]: r for r in actual["bundle"]["channels"]["G"]["scenarios"]}
    exported = {r["cells"]["G"][0]["id"] for r in item["rows"]}
    if not exported <= known.keys() or any(
        r["cells"]["G"] != [known[r["cells"]["G"][0]["id"]]] for r in item["rows"]
    ):
        conflicts.append("导出的G场景被篡改")
    selected = [r for r in decisions if r.get("item_id") == item["id"]]
    if len({r.get("g_id") for r in selected}) != len(selected):
        conflicts.append("同一场景存在重复审核决定")
    if any(
        r.get("g_id") not in exported
        or type(r.get("adopted")) is not bool
        or not isinstance(r.get("comment", ""), str)
        or set(r) - {"item_id", "g_id", "adopted", "comment"}
        for r in selected
    ):
        conflicts.append("只允许审核导出场景的采纳和意见")
    feedback_id = (
        "adoption-"
        + fingerprint(
            [item["id"], item["base_revision"], sorted(selected, key=lambda r: r.get("g_id", ""))]
        )[:24]
    )
    applied = any(r.get("id") == feedback_id for r in current["bundle"].get("review_feedback", []))
    if (
        selected
        and not applied
        and scope == "shared_services"
        and item["bundle"].get("source_versions") != current["bundle"].get("source_versions")
    ):
        conflicts.append("共用服务的调用成员已有新修订，请重新导出")
    if not conflicts and selected and not applied and current["revision"] != item["base_revision"]:
        conflicts.append("结果已有新修订，请重新导出核对")
    status = "conflict" if conflicts else "unchanged" if applied or not selected else "ready"
    return (
        {
            "case_id": item["key"],
            "scope": scope,
            "item_id": item["id"],
            "name": item["name"],
            "status": status,
            "base_revision": item["base_revision"],
            "current_revision": current["revision"],
            "changes": [
                {
                    "path": r["g_id"],
                    "before": None,
                    "after": {"adopted": r["adopted"], "comment": r.get("comment", "")},
                }
                for r in selected
            ],
            "conflicts": conflicts,
            "feedback_id": feedback_id,
        },
        current,
        selected,
    )


def feedback(
    project, content, *, apply=False, selected=None, item_ids=None, historical_readonly=False
):
    value = parse(content)
    export_id = value.get("export_id", "")
    if (
        not isinstance(export_id, str)
        or len(export_id) != 64
        or any(c not in "0123456789abcdef" for c in export_id)
    ):
        raise ValueError("缺少有效导出身份")
    manifest = Path(project) / "review_exports" / (export_id + ".json")
    if not manifest.is_file() or read_json(manifest).get("context_hash") != fingerprint(
        [value["items"], value.get("excluded")]
    ):
        raise ValueError("审核文件的只读上下文或导出场景已变化，拒绝回导")
    if set(value) - {"format", "items", "decisions", "excluded", "export_id"}:
        raise ValueError("审核文件只允许修改采纳决定和意见")
    keys = {i["id"] for i in value["items"]}
    if any(r.get("item_id") not in keys for r in value["decisions"]):
        raise ValueError("审核决定引用未知范围")
    if item_ids is not None and (
        not isinstance(item_ids, list)
        or any(not isinstance(i, str) or i not in keys for i in item_ids)
    ):
        raise ValueError("请选择有效的审核条目身份")
    result = []
    # Validate/apply the shared item before case feedback changes member revisions.
    # Existing source-vector checks still reject all changes made before this import.
    for item in sorted(value["items"], key=lambda i: i["scope"] != "shared_services"):
        if historical_readonly and item["scope"] == "architecture":
            result.append(
                {
                    "case_id": item["key"],
                    "scope": "architecture",
                    "item_id": item["id"],
                    "name": item["name"],
                    "status": "conflict",
                    "changes": [],
                    "conflicts": [
                        "历史架构结果只读；请重新导出共用外部服务报告后审核，原文件仍可查看"
                    ],
                }
            )
            continue
        if item["scope"] == "business_chain":
            result.append(
                {
                    "case_id": item["key"],
                    "scope": "business_chain",
                    "item_id": item["id"],
                    "name": item["name"],
                    "status": "not_applicable",
                    "changes": [],
                    "conflicts": ["历史业务链路已退出当前分析范围，不应用此反馈"],
                }
            )
            continue
        if apply and item_ids is not None and item["id"] not in item_ids:
            continue
        if (
            apply
            and item_ids is None
            and selected is not None
            and not {item["id"], item["key"], item["scope"]}.intersection(selected)
        ):
            continue
        row, current, decisions = _inspect(project, item, value["decisions"])
        if apply and row["status"] == "ready":
            service, matching = _service(item["scope"])
            bundle = deepcopy(current["bundle"])
            truth = bundle["channels"]["GT"]
            for decision in decisions:
                g = next(
                    r
                    for r in item["bundle"]["channels"]["G"]["scenarios"]
                    if r["id"] == decision["g_id"]
                )
                bundle.setdefault("review_notes", []).append(
                    {"id": row["feedback_id"] + g["id"], "origin": "business_review", **decision}
                )
                if not decision["adopted"]:
                    continue
                cid = "business-concern-" + fingerprint(matching.binding(g))[:24]
                existing = next(
                    (r for r in truth["concerns"] if matching.binding(r) == matching.binding(g)),
                    None,
                )
                if existing:
                    cid = existing["id"]
                else:
                    parent = next(
                        r
                        for r in item["bundle"]["channels"]["G"]["concerns"]
                        if r["id"] in g["concern_ids"]
                    )
                    truth["concerns"].append(
                        {
                            **deepcopy(parent),
                            "id": cid,
                            "origin": "business_review",
                            "source_refs": [],
                            "requirement_refs": deepcopy(parent.get("source_refs", [])),
                            "source_kind": "业务审核补充",
                            "members": _business_members(parent),
                        }
                    )
                sid = "business-scenario-" + fingerprint([item["id"], g["id"]])[:24]
                if not any(r["id"] == sid for r in truth["scenarios"]):
                    truth["scenarios"].append(
                        {
                            **deepcopy(g),
                            "id": sid,
                            "concern_ids": [cid],
                            "origin": "business_review",
                            "source_kind": "业务审核补充",
                            "source_refs": [],
                            "requirement_refs": deepcopy(g.get("source_refs", [])),
                            "adopted_from_g": g["id"],
                            "review_comment": decision.get("comment", ""),
                            "status": "active",
                            "members": _business_members(g),
                        }
                    )
                bundle["decisions"].append(
                    {
                        "id": "business-match-" + sid,
                        "level": "scenario",
                        "pair": "GT_G",
                        "left_id": sid,
                        "right_id": g["id"],
                        "status": "full",
                        "origin": "manual",
                        "reason": "业务审核采纳：" + decision.get("comment", ""),
                    }
                )
            bundle.setdefault("review_feedback", []).append(
                {"id": row["feedback_id"], "format": FORMAT}
            )
            try:
                saved = service.save_revision(
                    project,
                    item["key"],
                    {
                        "base_revision": current["revision"],
                        "bundle": bundle,
                        "reason": "业务采纳审核补充GT",
                    },
                )
                row.update(status="applied", revision=saved["revision"])
            except service.RevisionConflict as error:
                row.update(
                    status="conflict",
                    current_revision=error.current_revision,
                    conflicts=["保存前结果已有新修订，请重新导出核对"],
                )

        result.append(row)
    return {
        "format": FORMAT,
        "cases": result,
        "summary": {
            s: sum(r["status"] == s for r in result)
            for s in ("ready", "unchanged", "conflict", "applied", "not_applicable")
        },
    }


def accepts(content):
    if isinstance(content, dict):
        return content.get("format") == FORMAT
    if not isinstance(content, str):
        return False
    try:
        text = content.lstrip("\ufeff \r\n\t")
        if not text.startswith("{"):
            parser = _PayloadParser()
            parser.feed(text)
            text = "".join(parser.parts)
        return json.loads(text).get("format") == FORMAT
    except (ValueError, AttributeError):
        return False
