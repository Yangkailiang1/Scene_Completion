"""Confirmed many-to-many coverage shared by metrics and business review."""

POLICY = "coverage-any-confirmed-v2"
COVERED = {"full", "partial"}


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


def review_statuses(bundle, matching):
    """Per-record eligibility and confirmed links; pending sources only block their anchor."""
    units, aliases = matching._units(bundle, "scenarios")
    edges = matching._edges(bundle, "scenarios", units, aliases)
    links = {}
    truth = {r["id"]: r for r in bundle["channels"]["GT"]["scenarios"]}
    for (left, right), status in edges["GT_G"].items():
        if status in COVERED:
            records = [r for r in truth.values() if aliases["GT"].get(r["id"]) == left]
            for r in records:
                decision = next(
                    (
                        d
                        for d in reversed(
                            sorted(
                                bundle.get("decisions", []),
                                key=lambda d: d.get("origin") == "manual",
                            )
                        )
                        if d.get("pair") == "GT_G"
                        and d.get("level") == "scenario"
                        and aliases["GT"].get(d.get("left_id")) == left
                        and aliases["G"].get(d.get("right_id")) == right
                        and d.get("status") == status
                    ),
                    {},
                )
                links.setdefault(right, []).append(
                    {
                        "id": r["id"],
                        "status": status,
                        "condition": r.get("condition", ""),
                        "reason": decision.get("reason", "相同定位及失败条件"),
                    }
                )
    unresolved = {
        aliases["G"].get(p["right_id"])
        for p in matching.semantic_candidates(bundle)
        if p["pair"] == "GT_G"
    }
    pending = bundle["channels"]["GT"].get("pending", []) + [
        r for r in truth.values() if r.get("status") != "active"
    ]
    generation = set(bundle.get("scenario_generation", {}).get("pending_ids", []))
    generation.update(bundle.get("generation_pending", []))
    identified = bundle.get("gt_identification_run_complete")
    # Legacy SSD packets represent an unfinished source task with needs_semantic.
    # Project packets recover the explicit completion proof in the application projection.
    if bundle.get("gt_source_available") is False:
        identified = False
    elif identified is None:
        identified = not any(p.get("needs_semantic") for p in pending)
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
