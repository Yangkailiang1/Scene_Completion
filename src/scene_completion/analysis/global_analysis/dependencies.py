"""Project-wide concern/scenario comparison and recommendation.

Global records are keyed by dependency, never by a fabricated SSD message.
The three source channels supply their own observations. This module only
compares validated observations; it does not infer concerns from the registry.
"""

from __future__ import annotations

from copy import deepcopy


def _unique(rows, key):
    return list({key(row): row for row in rows}.values())


def anchor_key(row):
    if row.get("business_operation_id"):
        return "business_operation", row["business_operation_id"]
    return "dependency", row["dependency_id"]


def concern_key(row):
    return anchor_key(row), row["object"], row["concern_key"]


def scenario_key(row):
    # One independent failure is one scene, even if several concerns explain it.
    return (
        anchor_key(row),
        row["object"],
        row["cause"].strip().casefold(),
        tuple(sorted(x.strip().casefold() for x in row["conditions"])),
    )


def compare_concerns(g, e, gt=None):
    """Exact global anchors; no case-level multiplication of a shared edge."""
    g_rows = _unique(g["matches"], concern_key)
    e_rows = _unique(e["matches"], concern_key)
    gt_rows = _unique(gt["matches"], concern_key) if gt is not None else None
    g_set = {concern_key(x) for x in g_rows}
    e_set = {concern_key(x) for x in e_rows}
    truth = {concern_key(x) for x in gt_rows} if gt_rows is not None else None
    missing = g_set - e_set
    rows = []
    maps = {
        "G": {concern_key(x): x["id"] for x in g_rows},
        "E": {concern_key(x): x["id"] for x in e_rows},
        "GT": {concern_key(x): x["id"] for x in gt_rows or []},
    }
    for key in sorted(g_set | e_set | (truth or set())):
        rows.append(
            {
                "anchor": {
                    "anchor_kind": key[0][0],
                    "dependency_id" if key[0][0] == "dependency" else "business_operation_id": key[
                        0
                    ][1],
                    "object": key[1],
                    "concern_key": key[2],
                },
                "cells": {channel: maps[channel].get(key) for channel in maps},
                "missing": key in missing,
                "reason": "同一全局依赖、对象和关注点ID精确匹配",
            }
        )
    result = {
        "rows": rows,
        "G_count": len(g_set),
        "E_count": len(e_set),
        "M_count": len(missing),
        "M_ids": [x["id"] for x in g_rows if concern_key(x) in missing],
        "pending": g.get("pending", []) + e.get("pending", []) + (gt or {}).get("pending", []),
    }
    if truth is not None:
        uncovered = truth - e_set
        result["metrics"] = {
            "missing_omission": rate(len(uncovered - missing), len(uncovered)),
            "generation_effectiveness": rate(len(g_set & truth), len(g_set)),
        }
    else:
        result["metrics"] = {
            "missing_omission": not_evaluated(),
            "generation_effectiveness": not_evaluated(),
        }
    return result


def validate_decisions(left, right, decisions):
    """A semantic judgment cannot cross a global operation or dependency."""
    lm, rm = {s["id"]: s for s in left}, {s["id"]: s for s in right}
    seen = set()
    for decision in decisions:
        pair = decision["left_id"], decision["right_id"]
        if pair in seen or pair[0] not in lm or pair[1] not in rm:
            raise ValueError("global comparison requires unique pairs of existing scenario IDs")
        seen.add(pair)
        a, b = lm[pair[0]], rm[pair[1]]
        if (anchor_key(a), a["object"]) != (anchor_key(b), b["object"]):
            raise ValueError(
                "global comparison cannot cross business operation/dependency and object"
            )


def compare_scenarios(g, e, gt=None, decisions=None):
    """Exact anchors first; saved full semantic decisions resolve paraphrases."""
    from scene_completion.analysis.matching.assignment import full_assignment
    from scene_completion.analysis.matching.result_alignment import align_rows

    channels = {
        "G": _unique(g["scenarios"], scenario_key),
        "E": _unique(e["scenarios"], scenario_key),
        "GT": _unique((gt or {}).get("scenarios", []), scenario_key),
    }
    saved, pairs = {}, {}
    for purpose, (lc, rc) in {"G_E": ("G", "E"), "GT_G": ("GT", "G"), "GT_E": ("GT", "E")}.items():
        left, right = channels[lc], channels[rc]
        submitted = (decisions or {}).get(purpose, [])
        validate_decisions(left, right, submitted)
        exact = [
            {
                "left_id": a["id"],
                "right_id": b["id"],
                "status": "full",
                "reason": "同一全局定位及独立失败条件精确一致",
            }
            for a in left
            for b in right
            if scenario_key(a) == scenario_key(b)
        ]
        saved[purpose] = submitted + exact
        pairs[purpose] = full_assignment(saved[purpose])
    covered = {p["checker_scenario_id"] for p in pairs["G_E"]}
    rows = []
    for row in align_rows(channels, pairs, saved):
        anchor = row["anchor"]
        scope = anchor_key(anchor)
        rows.append(
            {
                "anchor": {
                    "anchor_kind": scope[0],
                    "dependency_id" if scope[0] == "dependency" else "business_operation_id": scope[
                        1
                    ],
                    "object": anchor["object"],
                    "cause": anchor["cause"],
                    "conditions": anchor["conditions"],
                    "concern_keys": sorted(
                        {s["concern_key"] for values in row["cells"].values() for s in values}
                    ),
                },
                "cells": {
                    k: values[0]["id"] if values else None for k, values in row["cells"].items()
                },
                "status": row["status"],
                "matching": row["matching"],
                "missing": bool(row["cells"]["G"] and row["cells"]["G"][0]["id"] not in covered),
                "reason": "同一全局定位；独立失败条件由精确规则或已保存的完整语义判断对应",
            }
        )
    return {
        "rows": rows,
        "G_count": len(channels["G"]),
        "E_count": len(channels["E"]),
        "GT_count": len(channels["GT"]) if gt is not None else None,
        "M": [s for s in channels["G"] if s["id"] not in covered],
        "full_matches": pairs,
        "decisions": saved,
        "pending": g.get("pending", []) + e.get("pending", []) + (gt or {}).get("pending", []),
    }


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": 100 * numerator / denominator if denominator else None,
        "status": "适用" if denominator else "不适用",
    }


def not_evaluated():
    return {"numerator": None, "denominator": None, "value": None, "status": "未评测"}


def recommend(missing, settings, history, *, run_id):
    """Risk floor and reviewed local history, with no GT or current E input."""
    risk_values = {"low": 0.25, "normal": 0.5, "high": 0.75, "critical": 1.0}
    risk_levels = settings.get("global_risk", {})
    k = max(0, int(settings.get("global_top_k", 10)))
    weight = float(settings.get("risk_weight", 0.7))
    selected_history = [
        h
        for h in history
        if h.get("human_reviewed")
        and h.get("run_id") != run_id
        and h.get("decision") in {"adopt", "not_needed"}
    ]
    ranked = []
    for scenario in _unique(missing, scenario_key):
        level = risk_levels.get(scenario["concern_key"], "normal")
        if level not in risk_values:
            level = "normal"
        related = [
            h
            for h in selected_history
            if h.get("concern_key") == scenario["concern_key"] and h.get("granularity") == "global"
        ]
        historical = (1 + sum(h["decision"] == "adopt" for h in related)) / (2 + len(related))
        score = weight * risk_values[level] + (1 - weight) * historical
        ranked.append(
            {
                "scenario_id": scenario["id"],
                "priority": score,
                "risk_level": level,
                "history_score": historical,
                "history_count": len(related),
                "mandatory": level == "critical",
                "scenario": scenario,
            }
        )
    ranked.sort(key=lambda x: (-x["priority"], x["scenario"]["concern_key"], x["scenario_id"]))
    mandatory = [x for x in ranked if x["mandatory"]]
    chosen = {
        x["scenario_id"]
        for x in mandatory + [x for x in ranked if not x["mandatory"]][: max(0, k - len(mandatory))]
    }
    for n, row in enumerate(ranked, 1):
        row.update(
            rank=n,
            selected=row["scenario_id"] in chosen,
            reason="关键风险保底" if row["mandatory"] else "风险与项目内已审核历史排序",
        )
    return {
        "Q": [x["scenario"] for x in ranked if x["selected"]],
        "ranked": ranked,
        "settings": {"top_k": k, "risk_weight": weight},
        "history_count": len(selected_history),
        "run_id": run_id,
    }


def evaluate(concerns, scenarios, recommendation, gt_scenarios=None):
    metrics = deepcopy(concerns["metrics"])
    if gt_scenarios is None:
        metrics.update(
            recommendation_adoption=not_evaluated(),
            recommendation_false_positive=not_evaluated(),
            baseline_adoption=not_evaluated(),
            baseline_false_positive=not_evaluated(),
        )
    else:
        truth = {scenario_key(s) for s in gt_scenarios["scenarios"]}

        def scored(rows):
            keys = {scenario_key(s) for s in rows}
            if "full_matches" in scenarios:
                from scene_completion.analysis.matching.assignment import full_assignment

                selected = {s["id"] for s in rows}
                candidates = scenarios.get("decisions", {}).get("GT_G")
                if candidates is None:
                    candidates = [
                        {
                            "left_id": p["checker_scenario_id"],
                            "right_id": p["generated_scenario_id"],
                            "status": "full",
                        }
                        for p in scenarios["full_matches"]["GT_G"]
                    ]
                hits = len(full_assignment(candidates, right_ids=selected))
            else:
                hits = len(keys & truth)
            return rate(hits, len(keys)), rate(len(keys) - hits, len(truth))

        metrics["baseline_adoption"], metrics["baseline_false_positive"] = scored(scenarios["M"])
        metrics["recommendation_adoption"], metrics["recommendation_false_positive"] = scored(
            recommendation["Q"]
        )
    return {
        "granularity": "global",
        "metrics": metrics,
        "concern_count": concerns["G_count"],
        "scenario_count": scenarios["G_count"],
        "missing_count": len(scenarios["M"]),
        "recommendation_count": len(recommendation["Q"]),
        "formula_notes": {"recommendation_false_positive": "|Q−GT|/|GT|；可超过100%"},
    }


def aggregate_metrics(scopes):
    """Aggregate counts, never average percentages or merge counting units."""
    out = {}
    for unit in ("concern", "scenario"):
        names = (
            ("missing_omission", "generation_effectiveness")
            if unit == "concern"
            else (
                "baseline_adoption",
                "baseline_false_positive",
                "recommendation_adoption",
                "recommendation_false_positive",
            )
        )
        out[unit] = {}
        for name in names:
            values = [
                scope["metrics"][name] for scope in scopes if name in scope.get("metrics", {})
            ]
            assessed = [v for v in values if v["status"] != "未评测"]
            out[unit][name] = (
                rate(sum(v["numerator"] for v in assessed), sum(v["denominator"] for v in assessed))
                if assessed
                else not_evaluated()
            )
            out[unit][name]["evaluated_scopes"] = len(assessed)
    return {
        "scopes": len(scopes),
        "metrics": out,
        "complete": all(s.get("complete", False) for s in scopes),
    }
