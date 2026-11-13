"""Pure comparison views, completeness and metrics for SSD case results."""

from copy import deepcopy

from scene_completion.domain.ssd.matching import (
    PAIRS,
    _assignment,
    _edges,
    _records,
    _text,
    _units,
    binding,
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
        "revision_issues": len(bundle.get("revision_issues", [])),
        "semantic_pairs": len(semantic_candidates(bundle)),
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
    for kind in ("concerns", "scenarios"):
        units, aliases = _units(bundle, kind)
        edges = _edges(bundle, kind, units, aliases)
        sets = {k: set(v) for k, v in units.items()}
        ge = _assignment(edges["G_E"], sets["G"], sets["E"])
        te = _assignment(edges["GT_E"], sets["GT"], sets["E"])
        missing = sets["G"] - {a for a, _ in ge}
        truth = sets["GT"] - {a for a, _ in te}
        hits = _assignment(edges["GT_G"], truth, missing)
        valid = _assignment(edges["GT_G"], sets["GT"], sets["G"])
        rates = {
            "missing_exception_miss_rate": _rate(len(truth) - len(hits), len(truth)),
            "generation_validity": _rate(len(valid), len(sets["G"])),
        }
        if kind == "concerns":
            metrics = rates
        else:
            diagnostics = {
                **rates,
                "missing_truth_ids": sorted(truth - {a for a, _ in hits}),
                "counts": {k: len(v) for k, v in sets.items()},
            }
        groups = {}
        for channel in ("G", "E", "GT"):
            for record in bundle["channels"][channel][kind]:
                anchor = binding(record)
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
                    if first is not None and second is not None and first != second:
                        for c in ("G", "E", "GT"):
                            groups[first]["cells"][c].extend(groups[second]["cells"][c])
                        del groups[second]
        for row in groups.values():
            cells = row["cells"]
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
        "comparison": comparison,
        "metrics": metrics,
        "scenario_diagnostic": diagnostics,
        "completeness": completeness(bundle),
    }
