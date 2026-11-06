"""Read saved failure decisions; never infer new matches or alter evaluation."""

from scene_completion.analysis.assignment import full_assignment


def summarize(report):
    if not {"G", "E", "GT", "M"} <= report.keys():
        return {"status": "未评测", "value": None, "loss_items": [], "conflicts": []}

    def ids(rows):
        return {s["id"] if isinstance(s, dict) else s for s in rows}

    e, gt, m = (ids(report[k]) for k in ("E", "GT", "M"))
    pairs = report.get("full_matches", {})
    covered = {
        p["checker_scenario_id"] for p in pairs.get("GT_E", []) if p["generated_scenario_id"] in e
    }
    missing = gt - covered
    candidates = report.get(
        "full_candidate_pairs_GT_G",
        [
            {
                "left_id": p["checker_scenario_id"],
                "right_id": p["generated_scenario_id"],
                "status": "full",
            }
            for p in pairs.get("GT_G", [])
        ],
    )
    hits = full_assignment(candidates, missing, m)
    missed = missing - {p["checker_scenario_id"] for p in hits}
    conflicts = []
    g_e = {
        p["checker_scenario_id"]: p["generated_scenario_id"]
        for p in pairs.get("G_E", [])
        if p["generated_scenario_id"] in e
    }
    for p in candidates:
        if p["status"] == "full" and p["left_id"] in missed and p["right_id"] in g_e:
            conflicts.append(
                {
                    "GT": p["left_id"],
                    "G": p["right_id"],
                    "E": g_e[p["right_id"]],
                    "reason": "G对应GT且被E覆盖，但GT未对应E；需核查三方判断，不能自动传递命中",
                }
            )
    return {
        "status": "适用" if missing else "不适用",
        "value": 100 * len(missed) / len(missing) if missing else None,
        "numerator": len(missed),
        "denominator": len(missing),
        "unit": "独立失败场景（当前保存粒度）",
        "note": "场景缺失诊断，与关注点层漏报率分别展示；重复GT及三方冲突仍需核查",
        "loss_items": [
            {k: s.get(k) for k in ["id", "interaction_id", "concern_key", "cause"]}
            for s in report["GT"]
            if s["id"] in missed
        ],
        "conflicts": conflicts,
    }
