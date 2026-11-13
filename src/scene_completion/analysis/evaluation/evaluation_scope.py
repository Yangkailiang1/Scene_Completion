"""Read-only RR/SR metric scopes. URL prefixes never establish ownership.

Analysis and frozen matches remain intact. Recompute counts over a selected
universe; never turn an unknown interface or a missing GT into a zero score.
"""

from copy import deepcopy

SCOPES = {"all", "RR", "SR"}


def validate_scope(scope):
    if scope not in SCOPES:
        raise ValueError("指标范围须为all、RR或SR")
    return scope


def interaction_layers(inputs):
    from scene_completion.analysis.interactions.interaction_enrichment import resolved_api_id
    from scene_completion.analysis.matching.concern_alignment import interaction_rows

    rows = interaction_rows(inputs)
    by_id = {i["id"]: i for i in rows}
    apis = inputs.get("api-parameters", inputs.get("normal-constraints", {})).get("apis", [])
    api_by_id = {a["id"]: a for a in apis}
    out = {}
    context = {
        **inputs,
        "rr-ssd": {"interactions": [r for r in rows if r["layer"] == "RR"]},
        "sr-ssd": {"interactions": [r for r in rows if r["layer"] == "SR"]},
    }
    for i in rows:
        # Resolve returns against their own request. The compact result input
        # can contain only enriched/fused rows rather than separate projections.
        api_id = resolved_api_id(i, context)
        a = api_by_id.get(api_id, {})
        layer = a.get("source_layer")
        if layer not in {"RR", "SR"} and api_id and "::" in api_id:
            layer = api_id.split("::", 1)[0]
        request = by_id.get(i.get("parent_id"), i) if i["direction"] == "return" else i
        if layer not in {"RR", "SR"}:
            views = request.get("source_views", [])
            has_RR = any(v.get("layer") == "RR" for v in views if isinstance(v, dict))

            def internal(party):
                return any(
                    s in party.get("position", "")
                    for s in ("内部服务", "内部数据库", "系统边界", "AI模型")
                ) and not any(s in party.get("position", "") for s in ("外部", "人类", "UI/前端"))

            if (
                request["layer"] == "SR"
                and not has_RR
                and (
                    request["sender"]["name"] != request["receiver"]["name"]
                    or request.get("step_kind") == "action"
                )
                and all(internal(request[k]) for k in ("sender", "receiver"))
            ):
                layer = "SR"
                basis = (
                    "SR显式本地action；不代表额外接口调用"
                    if request.get("step_kind") == "action"
                    else "SR中的实际内部Service交互；未借用另一层接口约束"
                )
            else:
                layer = None
                basis = "未能确定实际接口定义来源，不以展示层级或路径前缀猜测"
        else:
            basis = "实际关联接口的定义来源"
        out[i["id"]] = {"layer": layer, "api_id": api_id, "basis": basis}
    return out


def selected(item, layers, scope):
    if scope == "all":
        return True
    iid = item.get("canonical_interaction_id") or item.get("interaction_id")
    layer = layers.get(iid, {}).get("layer")
    if iid not in layers:
        layer = item.get("api_source_layer")
    return layer == scope


def concern_view(value, layers, scope):
    from scene_completion.analysis.matching.concern_alignment import compare

    if scope == "all" or not value:
        return deepcopy(value)
    names = {"G": "G_c", "E": "E_c", "GT": "GT_c"}
    parts = {}
    excluded = {}
    for channel, key in names.items():
        if channel == "GT" and key not in value:
            continue
        rows = value.get(key, [])
        parts[channel] = {"matches": [m for m in rows if selected(m, layers, scope)]}
        excluded[channel] = [m for m in rows if not selected(m, layers, scope)]
    result = compare(parts.get("G", {}), parts.get("E", {}), parts.get("GT"))
    result["excluded"] = {
        channel: deepcopy(value.get("excluded", {}).get(channel, [])) for channel in names
    }
    result["evaluation_scope"] = {
        "layer": scope,
        "excluded_binding_counts": {k: len(v) for k, v in excluded.items()},
        "unresolved_interaction_ids": sorted(
            {
                m["interaction_id"]
                for rows in excluded.values()
                for m in rows
                if not layers.get(m["interaction_id"], {}).get("layer")
            }
        ),
        "note": "RR/SR仅按实际接口归属；其他层与未定位项不进入本范围分母",
    }
    return result


def report_view(report, concerns, inputs, scope):
    validate_scope(scope)
    if scope == "all":
        return deepcopy(report)
    from scene_completion.analysis.matching.concern_alignment import attach_report
    from scene_completion.analysis.matching.exception_comparison import compare_report
    from scene_completion.analysis.recommendation.ranking import evaluate

    layers = interaction_layers(inputs)
    c = concern_view(concerns, layers, scope)
    if not report or not {"G", "E", "GT"} <= set(report):
        return (
            {
                "metrics": c.get("metrics", {}),
                "concern_level": c,
                "matching_version": c.get("version"),
                "evaluation_scope": c.get("evaluation_scope", {"layer": scope}),
            }
            if c
            else {}
        )
    if report.get("evaluation_scope", {}).get("layer") == scope:
        return deepcopy(report)

    def keep(rows):
        return [s for s in rows if selected(s, layers, scope)]

    pairs = report.get("full_matches", {})

    def decisions(name):
        return [
            {
                "left_id": p["checker_scenario_id"],
                "right_id": p["generated_scenario_id"],
                "status": "full",
                "reason": "复用已保存完整匹配",
            }
            for p in pairs.get(name, [])
        ]

    out = compare_report(
        keep(report["G"]),
        keep(report["E"]),
        keep(report["GT"]),
        decisions("G_E"),
        report.get("full_candidate_pairs_GT_G", decisions("GT_G")),
        decisions("GT_E"),
    )
    rec = deepcopy(inputs.get("gap-recommend", report.get("recommendation", {})))
    if rec.get("enabled"):
        mids = {s["id"] for s in out["M"]}
        rec["Q"] = [s for s in rec.get("Q", []) if s["id"] in mids and selected(s, layers, scope)]
    out = evaluate(out, rec)
    if c:
        out = attach_report(out, c)
    for k in ("test_set", "test_set_hash", "test_set_notes", "formula_notes"):
        if k in report:
            out[k] = deepcopy(report[k])
    if report.get("original_evaluation"):
        original = report["original_evaluation"]
        original_concerns = original.get("concern_level", concerns.get("original_evaluation", {}))
        out["original_evaluation"] = report_view(original, original_concerns, inputs, scope)
    out["evaluation_scope"] = {
        **c.get("evaluation_scope", {}),
        "layer": scope,
        "excluded_scenario_counts": {
            k: len(report[k]) - len(out[k])
            for k in ("G", "E", "GT", "M")
            if k in report and k in out
        },
        "source": "由已保存结果按实际接口定义来源重新计数，未调用模型，未改写原报告",
    }
    return out
