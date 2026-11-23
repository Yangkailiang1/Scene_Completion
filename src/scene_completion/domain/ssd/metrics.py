"""Pure comparison views, completeness and metrics for SSD case results."""

from copy import deepcopy

from scene_completion.domain.coverage import (
    GRAIN_POLICY,
    POLICY,
    counts,
    gt_identification_complete,
    review_statuses,
    unassessed_gt,
)
from scene_completion.domain.result_rows import display_rows
from scene_completion.domain.ssd import g_grain, matching
from scene_completion.domain.ssd.matching import (
    PAIRS,
    _assignment,
    _edges,
    _records,
    _text,
    _units,
    display_binding,
    semantic_candidates,
)
from scene_completion.infrastructure.identity import fingerprint


def _rate(n, d):
    return {
        "value": 100 * n / d if d else None,
        "numerator": n,
        "denominator": d,
        "status": "适用" if d else "不适用",
    }


def completeness(bundle):
    counts = {
        "pending_records": sum(
            row.get("status") != "active" or kind == "pending" for _, kind, row in _records(bundle)
        ),
        "pending_case_items": len(bundle.get("pending", [])),
        "contract_binding_pending": len(bundle.get("contract_binding_pending", [])),
        "revision_issues": len(bundle.get("revision_issues", [])),
        "semantic_pairs": len(semantic_candidates(bundle)),
        "generation_pending": len(bundle.get("scenario_generation", {}).get("pending_ids", [])),
    }
    return {**counts, "complete": not any(counts.values())}


def analyze(bundle):
    comparison, diagnostics, metrics = {}, {}, {}
    pending_pairs = semantic_candidates(bundle)
    semantic_records = {
        (channel, item[key])
        for item in pending_pairs
        for channel, key in zip(PAIRS[item["pair"]], ("left_id", "right_id"))
    }
    g_aligned = bundle.get("coverage_policy") == GRAIN_POLICY
    identified = not g_aligned or gt_identification_complete(bundle)
    for kind in ("concerns", "scenarios"):
        units, aliases = _units(bundle, kind)
        edges = _edges(bundle, kind, units, aliases)
        sets = {k: set(v) for k, v in units.items()}
        relevant = [
            pair for pair in pending_pairs if kind == "scenarios" and pair["pair"] == "GT_G"
        ]
        undecided_g = {aliases["G"].get(pair["right_id"]) for pair in relevant}
        undecided_truth = {aliases["GT"].get(pair["left_id"]) for pair in relevant}
        g_assessed = sets["G"]
        if g_aligned:
            if kind == "scenarios":
                statuses = review_statuses(
                    bundle, matching, comparison=(aliases, edges, pending_pairs)
                )
                g_assessed = {gid for gid in sets["G"] if statuses[gid]["complete"]}
                undecided_truth = unassessed_gt(
                    bundle, matching, units["GT"], statuses, undecided_truth
                )
            elif not identified:
                undecided_truth = sets["GT"]
            truth, hits, valid = g_grain.counts(
                units, edges, scenarios=kind == "scenarios", undecided=undecided_truth
            )
            if not identified and kind == "concerns":
                g_assessed = valid
            if bundle.get("gt_source_available") is False:
                truth, hits, valid, g_assessed = set(), set(), set(), set()
        elif bundle.get("coverage_policy") == POLICY:
            truth, hits, valid = counts(edges, sets)
        else:
            ge = _assignment(edges["G_E"], sets["G"], sets["E"])
            te = _assignment(edges["GT_E"], sets["GT"], sets["E"])
            missing = sets["G"] - {a for a, _ in ge}
            truth = sets["GT"] - {a for a, _ in te}
            hits = {a for a, _ in _assignment(edges["GT_G"], truth, missing)}
            valid = {b for _, b in _assignment(edges["GT_G"], sets["GT"], sets["G"])}
        if not g_aligned:
            if bundle.get("gt_source_available") is False:
                g_assessed = set()
            elif bundle.get("gt_source_available") is True:
                g_assessed = g_assessed - (undecided_g - valid)
                covered_truth = {
                    left
                    for (left, _), status in edges["GT_G"].items()
                    if status in {"full", "partial"}
                }
                truth -= undecided_truth - covered_truth
        rates = {
            "missing_exception_miss_rate": _rate(len(truth) - len(hits), len(truth)),
            "generation_validity": _rate(len(valid), len(g_assessed)),
        }
        unassessed = {
            "generation_validity": sets["G"] - g_assessed,
            "missing_exception_miss_rate": sets["GT"] & undecided_truth,
        }
        for name, rate in rates.items():
            if bundle.get("gt_source_available") is False or (
                g_aligned and not rate["denominator"] and (not identified or unassessed[name])
            ):
                rate["status"] = "未评估"
        if kind == "concerns":
            metrics = rates
        else:
            diagnostics = {
                **rates,
                "missing_truth_ids": sorted(key[1] if g_aligned else key for key in truth - hits),
                "counts": g_grain.unit_counts(sets, edges)
                if g_aligned
                else {k: len(v) for k, v in sets.items()},
            }
        if g_aligned:
            comparison[kind] = g_grain.rows(bundle, kind, units, aliases, edges)
            continue
        groups = {}
        for channel in ("G", "E", "GT"):
            for record in bundle["channels"][channel][kind]:
                anchor = display_binding(record)
                if kind == "scenarios":
                    anchor += (_text(record.get("condition")), _text(record.get("expected")))
                row = groups.setdefault(
                    anchor,
                    {
                        "id": kind + "-" + fingerprint(anchor)[:20],
                        "step_id": record.get("step_id"),
                        "target": record.get("target"),
                        "key": record.get("key"),
                        "field_id": record.get("field_id"),
                        "cells": {"G": [], "E": [], "GT": []},
                    },
                )
                row["cells"][channel].append(deepcopy(record))
        # Explicit semantic matches collect differently worded scenarios into one row.
        if kind in {"concerns", "scenarios"}:
            for pair, matches in edges.items():
                a, b = PAIRS[pair]
                for (left, right), status in matches.items():
                    if status != "full":
                        continue
                    first = next(
                        (
                            k
                            for k, r in groups.items()
                            if any(aliases[a].get(x["id"]) == left for x in r["cells"][a])
                        ),
                        None,
                    )
                    second = next(
                        (
                            k
                            for k, r in groups.items()
                            if any(aliases[b].get(x["id"]) == right for x in r["cells"][b])
                        ),
                        None,
                    )
                    if (
                        first is not None
                        and second is not None
                        and first != second
                        and groups[first]["step_id"] == groups[second]["step_id"]
                    ):
                        for c in ("G", "E", "GT"):
                            groups[first]["cells"][c].extend(groups[second]["cells"][c])
                        del groups[second]
        for row in groups.values():
            cells = row["cells"]
            confirmed = {
                right
                for (_, right), status in edges["GT_G"].items()
                if status in {"full", "partial"}
            }
            undecided = {
                aliases["G"].get(p["right_id"]) for p in pending_pairs if p["pair"] == "GT_G"
            }
            row["coverage_by_record"] = {
                r["id"]: {
                    "covered": aliases["G"].get(r["id"]) in confirmed,
                    "complete": aliases["G"].get(r["id"]) in confirmed
                    or aliases["G"].get(r["id"]) not in undecided,
                }
                for r in cells["G"]
            }
            count = sum(bool(c) for c in cells.values())
            pending = any(r["status"] != "active" for c in cells.values() for r in c)
            all_full = count == 3 and all(
                any(
                    edges[pair].get((aliases[a].get(x["id"]), aliases[b].get(y["id"]))) == "full"
                    for x in cells[a]
                    for y in cells[b]
                )
                for pair, (a, b) in PAIRS.items()
            )
            pair_statuses = [
                edges[pair].get((aliases[a].get(x["id"]), aliases[b].get(y["id"])))
                for pair, (a, b) in PAIRS.items()
                for x in cells[a]
                for y in cells[b]
            ]
            row["status"] = (
                "pending"
                if pending
                else "triple"
                if all_full
                else (
                    "partial"
                    if count == 3 or "partial" in pair_statuses
                    else "unmatched"
                    if "none" in pair_statuses
                    else "pair"
                    if count == 2
                    else "single"
                )
            )
            row["reason"] = {
                "pending": "待修正或重新挂载，暂不计分",
                "triple": "三方完整对应",
                "partial": "存在部分对应或三方判定冲突",
                "pair": "一方缺少对应结果",
                "single": "其余两方缺少对应结果",
                "unmatched": "已判定双方不匹配",
            }[row["status"]]
            if kind == "scenarios" and any(
                (c, r["id"]) in semantic_records for c, rows in cells.items() for r in rows
            ):
                row["status"] = "pending"
                row["reason"] = "同一关注点下存在待语义比较的场景，尚未判定是否对应"
        comparison[kind] = list(groups.values())
    for channel in ("G", "E", "GT"):
        for row in bundle["channels"][channel].get("pending", []):
            comparison["scenarios"].append(
                {
                    "id": "pending-" + channel + "-" + row["id"],
                    "step_id": row.get("step_id"),
                    "target": row.get("target"),
                    "key": row.get("key"),
                    "field_id": row.get("field_id"),
                    "cells": {c: [deepcopy(row)] if c == channel else [] for c in ("G", "E", "GT")},
                    "status": "pending",
                    "reason": row.get("reason", "待确认，暂不计分"),
                }
            )
    return {
        "coverage_policy": bundle.get("coverage_policy", "coverage-one-to-one-v1"),
        "comparison": comparison if g_aligned else display_rows(bundle, comparison),
        "metrics": metrics,
        "scenario_diagnostic": diagnostics,
        "metrics_by_level": {
            "concern": metrics,
            "scenario": {key: diagnostics[key] for key in metrics},
        },
        "completeness": completeness(bundle),
    }
