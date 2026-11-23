"""Three confirmed categories. E is reference, never subtracted from this report."""

from copy import deepcopy

from scene_completion.domain.coverage import COVERED, GRAIN_POLICY, review_statuses, unassessed_gt


def classify(bundle, matcher, statuses=None, *, include_records=True):
    statuses = statuses if statuses is not None else review_statuses(bundle, matcher)
    units, aliases = matcher._units(bundle, "scenarios")
    all_edges = matcher._edges(bundle, "scenarios", units, aliases)
    edges = all_edges["GT_G"]
    confirmed = {(a, b) for (a, b), s in edges.items() if s in COVERED}
    covered_truth = {a for a, _ in confirmed}
    covered_generated = {b for _, b in confirmed}
    pending = matcher.semantic_candidates(bundle)
    undecided_truth = {aliases["GT"].get(p["left_id"]) for p in pending if p["pair"] == "GT_G"}
    groups = {"covered": [], "g_only": [], "gt_only": []}
    excluded = []
    copy_record = deepcopy if include_records else lambda row: {"id": row["id"]}
    existing = {}
    for row in bundle["channels"]["E"]["scenarios"]:
        existing.setdefault(matcher.binding(row), []).append(row)
    truth_order = {tid: index for index, tid in enumerate(units["GT"])}
    linked = {}
    for tid, gid in confirmed:
        linked.setdefault(gid, []).append(tid)
    projected = {}
    if bundle.get("coverage_policy") == GRAIN_POLICY:
        from scene_completion.domain.ssd import g_grain

        for row in g_grain.rows(bundle, "scenarios", units, aliases, all_edges, isolate=False):
            if row.get("generated_id"):
                projected["G", row["generated_id"]] = row["cells"]
            elif row.get("truth_id"):
                projected["GT", row["truth_id"]] = row["cells"]

    def cells(g=None, truth=None):
        exemplar = g or truth
        aligned = projected.get(("G" if g else "GT", exemplar["id"]))
        if aligned is not None:
            return {
                channel: [copy_record(row) for row in rows] for channel, rows in aligned.items()
            }
        return {
            "G": [copy_record(g)] if g else [],
            "GT": [
                copy_record(units["GT"][tid])
                for tid in sorted(linked.get(g["id"], []), key=truth_order.__getitem__)
            ]
            if g
            else [copy_record(truth)],
            "E": [copy_record(r) for r in existing.get(matcher.binding(exemplar), [])],
        }

    for gid, g in units["G"].items():
        status = statuses[g["id"]]
        row = {
            "id": gid,
            "anchor_id": g.get("anchor_id", g.get("step_id")),
            "key": g["key"],
            "cells": cells(g=g),
            "classification_reason": status["label"],
            "links": status.get("links", []),
        }
        if gid in covered_generated:
            groups["covered"].append(row)
        elif status["eligible"]:
            groups["g_only"].append(row)
        else:
            excluded.append({"channel": "G", "id": gid, "reason": status["label"]})
    unassessed = unassessed_gt(bundle, matcher, units["GT"], statuses, undecided_truth)
    for tid, truth in units["GT"].items():
        if tid in covered_truth:
            continue
        if tid in unassessed:
            excluded.append({"channel": "GT", "id": tid, "reason": "匹配或生成未完成"})
            continue
        groups["gt_only"].append(
            {
                "id": tid,
                "anchor_id": truth.get("anchor_id", truth.get("step_id")),
                "key": truth["key"],
                "cells": cells(truth=truth),
                "classification_reason": "已完成比较，方法未覆盖此测试场景",
                "links": [],
            }
        )
    for channel, data in bundle["channels"].items():
        for kind in ("scenarios", "pending"):
            for row in data.get(kind, []):
                if kind == "pending" or row.get("status") != "active":
                    excluded.append(
                        {
                            "channel": channel,
                            "id": row["id"],
                            "reason": row.get("reason")
                            or row.get("binding_issue")
                            or "待确认／未挂载",
                        }
                    )
    return groups, excluded
