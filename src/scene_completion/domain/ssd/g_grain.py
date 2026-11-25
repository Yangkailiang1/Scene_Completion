"""Use a G obligation as the shared unit of display and coverage."""

from collections import defaultdict
from copy import deepcopy

from scene_completion.domain.coverage import COVERED
from scene_completion.domain.scenario_conditions import disjoint
from scene_completion.domain.ssd import concern_policy
from scene_completion.domain.ssd.matching import display_binding
from scene_completion.domain.ssd.validation_scope import compatible
from scene_completion.infrastructure.identity import fingerprint


def _links(edges):
    e, gt, gt_to_g, gt_to_e = (defaultdict(set) for _ in range(4))
    for (gid, eid), status in edges["G_E"].items():
        if status in COVERED:
            e[gid].add(eid)
    for (tid, gid), status in edges["GT_G"].items():
        if status in COVERED:
            gt[gid].add(tid)
            gt_to_g[tid].add(gid)
    for (tid, eid), status in edges["GT_E"].items():
        if status in COVERED:
            gt_to_e[tid].add(eid)
    return e, gt, gt_to_g, gt_to_e


def counts(units, edges, *, scenarios, undecided=()):
    e, gt, gt_to_g, gt_to_e = _links(edges)
    truth, hit = set(), set()
    for tid, test in units["GT"].items():
        targets = gt_to_g.get(tid)
        if not targets and tid not in gt_to_e and tid not in undecided:
            truth.add(("GT", tid))
        for gid in targets or ():
            same_failure = any(
                edges["GT_E"].get((tid, eid)) != "none"
                and (
                    not scenarios
                    or (
                        not disjoint(test.get("condition"), units["E"][eid].get("condition"))
                        and not concern_policy.different_subtypes(test, units["E"][eid])
                        and (
                            edges["GT_E"].get((tid, eid)) in COVERED
                            or test.get("failure_subtype") == units["E"][eid].get("failure_subtype")
                        )
                        and compatible(test.get("condition"), units["E"][eid].get("condition"))
                    )
                )
                for eid in e.get(gid, ())
            )
            if not same_failure:
                obligation = ("G", gid)
                truth.add(obligation)
                hit.add(obligation)
    return truth, hit, set(gt)


def unit_counts(sets, edges):
    e, gt, gt_to_g, _ = _links(edges)
    return {
        "G": len(sets["G"]),
        "E": len(e) + len(sets["E"] - set().union(*e.values())),
        "GT": len(gt) + len(sets["GT"] - gt_to_g.keys()),
    }


def rows(bundle, kind, units, aliases, edges, *, isolate=True):
    e, gt, gt_to_g, gt_to_e = _links(edges)
    records = {ch: defaultdict(list) for ch in ("G", "E", "GT")}
    inactive = []
    for channel, groups in records.items():
        for row in bundle["channels"][channel][kind]:
            representative = aliases[channel].get(row["id"])
            if representative is None:
                inactive.append((channel, row))
            else:
                groups[representative].append(row)

    def cell(channel, ids):
        values = [r for key in sorted(ids) for r in records[channel][key]]
        return sorted(values, key=lambda row: bool(row.get("validation_summary")))

    def view(identity, anchor, cells, *, generated=None, truth=None, pending=False):
        present = sum(bool(v) for v in cells.values())
        return {
            "id": identity,
            **{k: anchor.get(k) for k in ("step_id", "target", "key", "field_id", "entity_id")},
            "cells": deepcopy(cells) if isolate else cells,
            "status": "pending" if pending else ("single", "single", "pair", "triple")[present],
            "reason": "待重新挂载" if pending else "按 G 义务归组" if generated else "独立来源记录",
            **({"generated_id": generated} if generated else {}),
            **({"truth_id": truth} if truth else {}),
        }

    result = [
        view(
            "g-" + kind + "-" + gid,
            generated,
            {"G": [generated], "E": cell("E", e[gid]), "GT": cell("GT", gt[gid])},
            generated=gid,
        )
        for gid, generated in units["G"].items()
    ]
    for row in result:
        row["generated_member_ids"] = [r["id"] for r in records["G"][row["generated_id"]]]
    used_e = set().union(*e.values())
    for tid, source in units["GT"].items():
        if tid not in gt_to_g:
            linked = gt_to_e[tid]
            result.append(
                view(
                    "gt-" + kind + "-" + tid,
                    source,
                    {"G": [], "E": cell("E", linked), "GT": cell("GT", {tid})},
                    truth=tid,
                )
            )
            used_e.update(linked)
    independent = [
        ("E", source, cell("E", {eid})) for eid, source in units["E"].items() if eid not in used_e
    ]
    independent.extend((ch, source, [source]) for ch, source in inactive)
    extra = {}
    for channel, source, members in independent:
        manually_grouped = source.get("display_row_id")
        key = (
            (source.get("step_id"), manually_grouped)
            if manually_grouped
            else (channel, source["id"], display_binding(source))
        )
        existing = extra.get(key)
        if existing:
            existing["cells"][channel].extend(deepcopy(members))
        else:
            extra[key] = view(
                "independent-" + fingerprint(key)[:20],
                source,
                {ch: members if ch == channel else [] for ch in records},
                pending=source.get("status") != "active",
            )
    return result + list(extra.values())
