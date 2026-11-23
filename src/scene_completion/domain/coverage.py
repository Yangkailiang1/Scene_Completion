"""Confirmed many-to-many coverage shared by metrics and business review."""

from collections import defaultdict

POLICY = "coverage-any-confirmed-v2"
GRAIN_POLICY = "coverage-g-obligation-v3"
COVERED = {"full", "partial"}


def binary_status(status):
    return "full" if status in COVERED else status


def covered(edges, left, right):
    return {
        (a, b) for (a, b), status in edges.items() if status in COVERED and a in left and b in right
    }


def counts(edges, sets):
    ge = covered(edges["G_E"], sets["G"], sets["E"])
    te = covered(edges["GT_E"], sets["GT"], sets["E"])
    missing = sets["G"] - {a for a, _ in ge}
    truth = sets["GT"] - {a for a, _ in te}
    hits = {a for a, _ in covered(edges["GT_G"], truth, missing)}
    valid = {b for _, b in covered(edges["GT_G"], sets["GT"], sets["G"])}
    return truth, hits, valid


REASONS = {
    "eligible": "可审核",
    "covered": "已覆盖",
    "matching_pending": "匹配未完成",
    "identification_pending": "GT识别未完成",
    "source_pending": "关联测试待确认",
    "generation_pending": "生成未完成",
    "inactive": "挂载待修正",
}


def gt_identification_complete(bundle):
    if bundle.get("gt_source_available") is False:
        return False
    identified = bundle.get("gt_identification_run_complete")
    if identified is not None:
        return identified
    gt = bundle["channels"]["GT"]
    return not any(
        row.get("needs_semantic")
        for row in gt.get("pending", [])
        + [r for r in gt["scenarios"] if r.get("status") != "active"]
    )


def unassessed_gt(bundle, matching, truth, statuses, pending):
    """Exclude unmatched tests whose corresponding generation or matching is unfinished."""
    if not gt_identification_complete(bundle):
        return set(truth)
    incomplete = {
        matching.binding(row)
        for row in bundle["channels"]["G"]["scenarios"]
        if statuses[row["id"]]["reason"] in {"generation_pending", "inactive"}
    }
    generation = set(bundle.get("generation_pending", [])) | set(
        bundle.get("scenario_generation", {}).get("pending_ids", [])
    )
    return pending | {
        ident
        for ident, row in truth.items()
        if row.get("step_id", row.get("anchor_id")) in generation
        or matching.binding(row) in incomplete
    }


def review_statuses(bundle, matching, *, comparison=None):
    """Per-record eligibility and confirmed links; pending sources only block their anchor."""
    if comparison is None:
        units, aliases = matching._units(bundle, "scenarios")
        edges = matching._edges(bundle, "scenarios", units, aliases)
        candidates = matching.semantic_candidates(bundle)
    else:
        aliases, edges, candidates = comparison
    links = defaultdict(list)
    truth = bundle["channels"]["GT"]["scenarios"]
    truth_records = defaultdict(list)
    for row in truth:
        truth_records[aliases["GT"].get(row["id"])].append(row)
    decisions = {
        (
            aliases["GT"].get(d["left_id"]),
            aliases["G"].get(d["right_id"]),
            d["status"],
        ): d
        for d in sorted(bundle.get("decisions", []), key=lambda d: d.get("origin") == "manual")
        if d.get("pair") == "GT_G" and d.get("level") == "scenario"
    }
    for (left, right), status in edges["GT_G"].items():
        if status not in COVERED:
            continue
        decision = decisions.get((left, right, status), {})
        links[right].extend(
            {
                "id": row["id"],
                "status": binary_status(status)
                if bundle.get("coverage_policy") == GRAIN_POLICY
                else status,
                "condition": row.get("condition", ""),
                "reason": decision.get("reason", "相同定位及失败条件"),
            }
            for row in truth_records[left]
        )
    unresolved = {aliases["G"].get(p["right_id"]) for p in candidates if p["pair"] == "GT_G"}
    pending = bundle["channels"]["GT"].get("pending", []) + [
        r for r in truth if r.get("status") != "active"
    ]
    generation = set(bundle.get("scenario_generation", {}).get("pending_ids", []))
    generation.update(bundle.get("generation_pending", []))
    identified = gt_identification_complete(bundle)
    result = {}
    for row in bundle["channels"]["G"]["scenarios"]:
        ident = aliases["G"].get(row["id"])
        anchor = row.get("step_id", row.get("anchor_id"))
        source_pending = any(
            p.get("step_id", p.get("anchor_id")) == anchor
            and anchor is not None
            and all(
                not p.get(k) or p[k] == row.get(k)
                for k in ("key", "field_id", "entity_id", "attribute", "target")
            )
            for p in pending
        )
        generated = row["id"] not in generation and anchor not in generation
        if (
            row.get("reference_template") or row.get("generation_origin") == "reference_template"
        ) and not row.get("analysis"):
            generated = False
        reason = (
            "inactive"
            if row.get("status") != "active" or not anchor
            else "covered"
            if ident in links
            else "generation_pending"
            if not generated
            else "identification_pending"
            if not identified
            else "source_pending"
            if source_pending
            else "matching_pending"
            if ident in unresolved
            else "eligible"
        )
        result[row["id"]] = {
            "reason": reason,
            "label": REASONS[reason],
            "eligible": reason == "eligible",
            "covered": reason == "covered",
            "complete": reason in {"eligible", "covered"},
            "links": links.get(ident, []),
            "representative_id": ident,
        }
    return result


def review_candidates(bundle, matching, statuses=None):
    statuses = review_statuses(bundle, matching) if statuses is None else statuses
    eligible, seen = [], set()
    counters = {
        "covered": 0,
        "unfinished": 0,
        "inactive": 0,
        "exported": 0,
        "source_pending": len(bundle["channels"]["GT"].get("pending", []))
        + sum(r.get("status") != "active" for r in bundle["channels"]["GT"]["scenarios"]),
    }
    for row in bundle["channels"]["G"]["scenarios"]:
        status = statuses[row["id"]]
        ident = status["representative_id"] or row["id"]
        if ident in seen:
            continue
        seen.add(ident)
        reason = status["reason"]
        if reason == "eligible":
            eligible.append(row)
            counters["exported"] += 1
        elif reason == "covered":
            counters["covered"] += 1
        elif reason == "inactive":
            counters["inactive"] += 1
        else:
            counters["unfinished"] += 1
    return eligible, counters
