"""Three confirmed categories. E is reference, never subtracted from this report."""

from copy import deepcopy

from scene_completion.domain.coverage import COVERED, review_statuses


def classify(bundle, matcher, statuses=None, *, include_records=True):
    statuses = statuses if statuses is not None else review_statuses(bundle, matcher)
    units, aliases = matcher._units(bundle, "scenarios")
    edges = matcher._edges(bundle, "scenarios", units, aliases)["GT_G"]
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

    def cells(g=None, truth=None):
        exemplar = g or truth
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
    incomplete = {
        matcher.binding(r)
        for r in bundle["channels"]["G"]["scenarios"]
        if statuses[r["id"]]["reason"] in {"generation_pending", "inactive"}
    }
    identified = bundle.get(
        "gt_identification_run_complete",
        not any(r.get("needs_semantic") for r in bundle["channels"]["GT"].get("pending", [])),
    )
    generation = set(bundle.get("generation_pending", [])) | set(
        bundle.get("scenario_generation", {}).get("pending_ids", [])
    )
    for tid, truth in units["GT"].items():
        if tid in covered_truth:
            continue
        anchor = truth.get("step_id", truth.get("anchor_id"))
        generated = anchor not in generation and matcher.binding(truth) not in incomplete
        if tid in undecided_truth or not generated or not identified:
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
