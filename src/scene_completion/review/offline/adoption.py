"""Current business report and frozen v2 review compatibility."""

from copy import deepcopy
from pathlib import Path

from scene_completion.domain.business_report import classify
from scene_completion.domain.current_scope import POLICY, filtered
from scene_completion.infrastructure.result_cache import cached_index
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.review.offline import _adoption_v2 as legacy
from scene_completion.review.offline.ssd_review import _safe_json

FORMAT = "business-adoption-v3"
SCOPES = {"interaction": "用例交互", "shared_services": "共用外部服务"}


def _selected(groups, body):
    for category, rows in groups.items():
        groups[category] = [
            r
            for r in rows
            if (body.get("anchor_ids") is None or r["anchor_id"] in body["anchor_ids"])
            and (
                body.get("record_ids") is None
                or {
                    r["id"],
                    *[x["id"] for records in r["cells"].values() for x in records],
                }.intersection(body["record_ids"])
            )
        ]
    return groups


def _collect(project, body=None, *, include_snapshot=True):
    from scene_completion.application import (
        shared_service_service as shared,
    )
    from scene_completion.application import (
        ssd_revision_service as cases,
    )
    from scene_completion.domain.project_scopes import matching as shared_matching
    from scene_completion.domain.ssd import matching

    body = body or {}
    for key in ("scopes", "case_ids", "anchor_ids", "record_ids", "item_ids"):
        if key in body and (
            not isinstance(body[key], list) or any(not isinstance(i, str) for i in body[key])
        ):
            raise ValueError(key + "必须为身份列表")
    items = []
    scopes = body.get("scopes") or list(SCOPES)
    if any(s not in SCOPES for s in scopes):
        raise ValueError("当前仅分析交互与共用外部服务，历史范围请使用只读入口")
    catalog = list(cases.review_catalog(project))
    import re

    catalog.sort(
        key=lambda c: [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", c["id"])]
    )
    for case in catalog if "interaction" in scopes else []:
        if body.get("case_ids") is not None and case["id"] not in body["case_ids"]:
            continue
        view = cases.review_view(project, case["id"], case["revision"])
        own = filtered(view["bundle"], ordinary=True, isolate=False)
        generated = {r["id"] for r in own["channels"]["G"]["scenarios"]}
        status = {k: v for k, v in view["review_statuses"].items() if k in generated}
        groups, excluded = classify(own, matching, status, include_records=include_snapshot)
        groups = _selected(groups, body)
        rows = groups["g_only"]
        for r in rows:
            r["id"] = (
                "adoption-"
                + fingerprint(["interaction", case["id"], r["cells"]["G"][0]["id"]])[:24]
            )
        groups["g_only"] = rows
        items.append(
            {
                "id": "interaction:" + case["id"],
                "scope": "interaction",
                "key": case["id"],
                "name": case["name"],
                "base_revision": view["revision"],
                **({"bundle": deepcopy(view["bundle"])} if include_snapshot else {}),
                **(
                    {"reference_excluded_ids": _reference_exclusions(view["bundle"], own)}
                    if include_snapshot
                    else {}
                ),
                "counts": {
                    c: {k: len(data[k]) for k in ("concerns", "scenarios", "pending")}
                    for c, data in own["channels"].items()
                },
                "rows": rows,
                "categories": groups,
                "report_excluded": excluded,
                "review_statuses": status,
                "identification_proof": view["identification_proof"],
                "report_version": 3,
            }
        )
    if (
        "shared_services" in scopes
        and body.get("case_ids") is None
        and (body.get("anchor_ids") is None or "interaction" not in scopes)
    ):
        view = shared.editor(project)
        if view["bundle"]["anchors"]:
            groups, excluded = classify(
                view["bundle"],
                shared_matching,
                view["review_statuses"],
                include_records=include_snapshot,
            )
            groups = _selected(groups, body)
            items.append(
                {
                    "id": "shared_services:project",
                    "scope": "shared_services",
                    "key": "shared_services",
                    "name": "共用外部服务",
                    "base_revision": view["revision"],
                    **({"bundle": view["bundle"]} if include_snapshot else {}),
                    **(
                        {
                            "counts": {
                                c: {k: len(data[k]) for k in ("concerns", "scenarios", "pending")}
                                for c, data in view["bundle"]["channels"].items()
                            }
                        }
                        if not include_snapshot
                        else {}
                    ),
                    "rows": groups["g_only"],
                    "categories": groups,
                    "report_excluded": excluded,
                    "review_statuses": view["review_statuses"],
                    "identification_proof": view["identification_proof"],
                    "report_version": 3,
                }
            )
    if body.get("item_ids") is not None:
        if set(body["item_ids"]) - {i["id"] for i in items}:
            raise ValueError("请选择有效的审核条目身份")
        items = [i for i in items if i["id"] in body["item_ids"]]
    case_catalog = {
        c["id"]: {"id": c["id"], "name": c["name"], "complete": c["completeness"]["complete"]}
        for c in catalog
    }
    manifest = Path(project) / "run/run_manifest.json"
    if manifest.exists():
        for cid in read_json(manifest).get("ssd_cases", []):
            case_catalog.setdefault(cid, {"id": cid, "name": cid, "complete": False})
    if body.get("case_ids") is not None:
        case_catalog = {k: v for k, v in case_catalog.items() if k in body["case_ids"]}
    report = {
        "title": "需求异常场景识别结果",
        "analysis_policy": POLICY,
        "cases": sorted(case_catalog.values(), key=lambda c: c["id"]),
        "case_count": len(case_catalog),
        "case_details_included": "interaction" in scopes,
        "counts": {},
    }
    for category in ("covered", "g_only", "gt_only"):
        per_case = sum(len(i["categories"][category]) for i in items if i["scope"] == "interaction")
        common = sum(
            len(i["categories"][category]) for i in items if i["scope"] == "shared_services"
        )
        report["counts"][category] = {
            "cases": per_case,
            "shared_services": common,
            "total": per_case + common,
        }
    by_scope = {}
    for scope in SCOPES:
        selected = [i for i in items if i["scope"] == scope]
        by_scope[scope] = {
            "available": bool(selected),
            "exported": sum(len(i["rows"]) for i in selected),
            "covered": sum(len(i["categories"]["covered"]) for i in selected),
            "unfinished": sum(len(i["report_excluded"]) for i in selected),
            "inactive": 0,
            "source_pending": 0,
            "items": [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "revision": i["base_revision"],
                    "counts": i.get("counts")
                    or {
                        c: {k: len(data[k]) for k in ("concerns", "scenarios", "pending")}
                        for c, data in i["bundle"]["channels"].items()
                    },
                    "reasons": {},
                }
                for i in selected
            ],
        }
    excluded = {
        k: sum(v[k] for v in by_scope.values())
        for k in ("exported", "covered", "unfinished", "inactive", "source_pending")
    }
    excluded["by_scope"] = by_scope
    return {
        "format": FORMAT,
        "items": items,
        "excluded": excluded,
        "report": report,
        "decisions": [],
    }


def _reference_exclusions(bundle, ordinary):
    excluded = []
    for channel, data in bundle["channels"].items():
        for kind in ("concerns", "scenarios", "pending"):
            kept = {r["id"] for r in ordinary["channels"][channel][kind]}
            excluded.extend(r["id"] for r in data.get(kind, []) if r["id"] not in kept)
    return excluded


def _summary(project, body=None):
    p = _collect(project, body, include_snapshot=False)
    return {"format": FORMAT, "excluded": p["excluded"], "report": p["report"]}


@cached_index(
    "ssd_results",
    "project_results",
    "shared_service_results",
    files=(
        "run/run_manifest.json",
        "run/artifacts/shared/project--architecture--project-identify.json",
    ),
)
def _all_summary(project):
    return _summary(project)


def summary(project, body=None):
    return _summary(project, body) if body else _all_summary(project)


def export_payload(project, body=None):
    p = _collect(project, body)
    p["export_id"] = fingerprint([FORMAT, p["items"], p["excluded"], p["report"]])
    write_json(
        Path(project) / "review_exports" / (p["export_id"] + ".json"),
        {
            "context_hash": fingerprint([p["items"], p["excluded"]]),
            "report_hash": fingerprint(p["report"]),
        },
    )
    return p


def parse(content):
    # The same safe embedded JSON parser accepts both frozen formats.
    import json

    if isinstance(content, dict):
        value = deepcopy(content)
    elif isinstance(content, str) and len(content) <= 32 * 1024 * 1024:
        text = content.lstrip("\ufeff \r\n\t")
        if not text.startswith("{"):
            parser = legacy._PayloadParser()
            parser.feed(text)
            if parser.count != 1 or parser.active:
                raise ValueError("审核HTML须包含一份完整数据")
            text = "".join(parser.parts)
        value = json.loads(text)
    else:
        raise ValueError("请提供不超过32MB的审核文件")
    if not isinstance(value, dict) or value.get("format") not in {FORMAT, legacy.FORMAT}:
        raise ValueError("无效的业务报告格式")
    converted = {k: v for k, v in value.items() if k != "report"}
    converted["format"] = legacy.FORMAT
    legacy.parse(converted)
    return value


def render_html(content):
    p = parse(content)
    if p["format"] == legacy.FORMAT:
        return legacy.render_html(p)
    from scene_completion.review.offline._business_report_template import TEMPLATE

    return TEMPLATE.replace("__ADOPTION_JSON__", _safe_json(p))


def export_html(project, body=None):
    return render_html(export_payload(project, body))


def feedback(project, content, *, apply=False, selected=None, item_ids=None):
    p = parse(content)
    if p["format"] == FORMAT:
        export_id = p.get("export_id", "")
        if (
            not isinstance(export_id, str)
            or len(export_id) != 64
            or any(c not in "0123456789abcdef" for c in export_id)
        ):
            raise ValueError("缺少有效导出身份")
        manifest = Path(project) / "review_exports" / (str(p.get("export_id", "")) + ".json")
        if not manifest.is_file() or read_json(manifest).get("report_hash") != fingerprint(
            p.get("report")
        ):
            raise ValueError("报告统计或只读内容已变化，拒绝回导")
    converted = {k: v for k, v in p.items() if k != "report"}
    converted["format"] = legacy.FORMAT
    result = legacy.feedback(
        project,
        converted,
        apply=apply,
        selected=selected,
        item_ids=item_ids,
        historical_readonly=True,
    )
    result["format"] = p["format"]
    return result


def accepts(content):
    try:
        parse(content)
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
