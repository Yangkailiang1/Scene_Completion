"""Set metrics with independent deduplication per concern and group."""
from __future__ import annotations

from .concerns import ACTIVE_CONCERN_KEYS, CONCERN_DEFINITIONS
from .sources import fingerprint


def scene_map(value: dict) -> dict:
    if not isinstance(value, dict) or value.get("complete") is not True:
        raise ValueError("scene input must be complete")
    scenes = value.get("scenarios")
    if not isinstance(scenes, list):
        raise ValueError("scenarios must be an array")
    result = {}
    for scene in scenes:
        if not isinstance(scene, dict) or not isinstance(scene.get("scenario_id"), str) or not scene["scenario_id"]:
            raise ValueError("scenario needs a nonempty ID")
        if scene["scenario_id"] in result:
            raise ValueError("duplicate scenario ID")
        keys = scene.get("concern_keys", [])
        if not isinstance(keys, list) or any(k not in ACTIVE_CONCERN_KEYS for k in keys):
            raise ValueError("unknown concern label")
        if not scene.get("use_case_id"):
            raise ValueError("scenario needs a use case")
        result[scene["scenario_id"]] = scene
    return result


def compare_scenes(generated: dict, checker: dict, matches: dict) -> dict:
    gen, ref = scene_map(generated), scene_map(checker)
    if matches.get("complete") is not True or matches.get("input_hash") != fingerprint([generated, checker]):
        raise ValueError("matching must be complete and bound to these input versions")
    links, seen = matches.get("matches"), set()
    if not isinstance(links, list):
        raise ValueError("matches must be an array")
    for link in links:
        pair = (link.get("checker_scenario_id"), link.get("generated_scenario_id"))
        if pair[0] not in ref or pair[1] not in gen or pair in seen:
            raise ValueError("unknown or duplicate match pair")
        seen.add(pair)
        if link.get("status") not in {"full", "partial", "unmatched"} or not str(link.get("evidence", "")).strip():
            raise ValueError("invalid match status/evidence")
        if link["status"] == "partial" and not link.get("missing_behavior"):
            raise ValueError("partial match needs missing_behavior")
        if link["status"] == "full" and link.get("missing_behavior"):
            raise ValueError("full match cannot contain missing behavior")

    def summarize(cids: set, gids: set) -> dict:
        accepted = [x for x in links if x["status"] in {"full", "partial"}
                    and x["checker_scenario_id"] in cids and x["generated_scenario_id"] in gids]
        covered = {x["checker_scenario_id"] for x in accepted}
        matched = {x["generated_scenario_id"] for x in accepted}
        full_refs = {x["checker_scenario_id"] for x in accepted if x["status"] == "full"}
        partial_refs = {x["checker_scenario_id"] for x in accepted if x["status"] == "partial"}
        missing, recommend = sorted(cids - covered), sorted(gids - matched)
        return {
            "checker_count": len(cids), "generated_count": len(gids),
            "miss_rate": {"numerator": len(missing), "denominator": len(cids),
                          "rate": len(missing) / len(cids) if cids else None},
            "existing_completeness": {"numerator": len(matched), "denominator": len(gids),
                                     "rate": len(matched) / len(gids) if gids else None},
            "full_checker_ids": sorted({x["checker_scenario_id"] for x in accepted if x["status"] == "full"}),
            "partial_checker_ids": sorted({x["checker_scenario_id"] for x in accepted if x["status"] == "partial"}),
            "partial_only_checker_ids": sorted(partial_refs - full_refs),
            "matched_checker_ids": sorted(covered), "matched_generated_ids": sorted(matched),
            "missing_checker_ids": missing, "recommendation_ids": recommend,
            "missing_scenarios": [ref[x] for x in missing],
            "matched_checker_scenarios": [ref[x] for x in sorted(covered)],
            "unmatched_generated_scenarios": [gen[x] for x in recommend],
        }

    overall = summarize(set(ref), set(gen))
    keys = sorted(ACTIVE_CONCERN_KEYS)
    by_concern = {key: {"label": CONCERN_DEFINITIONS[key]["label"], **summarize(
        {sid for sid, s in ref.items() if key in s.get("concern_keys", [])},
        {sid for sid, s in gen.items() if key in s.get("concern_keys", [])})} for key in keys}
    groups = sorted({CONCERN_DEFINITIONS[key]["group"] for key in keys})
    by_group = {}
    for group in groups:
        group_keys = {key for key in keys if CONCERN_DEFINITIONS[key]["group"] == group}
        by_group[group] = summarize(
            {sid for sid, s in ref.items() if group_keys.intersection(s.get("concern_keys", []))},
            {sid for sid, s in gen.items() if group_keys.intersection(s.get("concern_keys", []))})
    # The headline evaluates exception completion, independently of success and
    # optional flows. Keep the original all-scenario metric for comparison.
    exception_cids = {sid for sid, s in ref.items() if s.get("scenario_type") == "requirement_exception"}
    exception_gids = {sid for sid, s in gen.items()
                      if s.get("scenario_type") in {"requirement_exception", "concern_derived_exception"}}
    exception_overall = summarize(exception_cids, exception_gids)
    by_concern_exception = {key: {"label": CONCERN_DEFINITIONS[key]["label"], **summarize(
        {sid for sid in exception_cids if key in ref[sid].get("concern_keys", [])},
        {sid for sid in exception_gids if key in gen[sid].get("concern_keys", [])})} for key in keys}
    by_group_exception = {}
    for group in groups:
        group_keys = {key for key in keys if CONCERN_DEFINITIONS[key]["group"] == group}
        by_group_exception[group] = summarize(
            {sid for sid in exception_cids if group_keys.intersection(ref[sid].get("concern_keys", []))},
            {sid for sid in exception_gids if group_keys.intersection(gen[sid].get("concern_keys", []))})
    contribution_gids = {
        "explicit": {sid for sid in exception_gids if gen[sid].get("generation_status") == "explicit"},
        "concern_derived": {sid for sid in exception_gids if gen[sid].get("generation_status") != "explicit"},
    }
    contributions = {key: summarize(exception_cids, gids) for key, gids in contribution_gids.items()}
    concern_method_details = {kind: summarize(exception_cids, {
        sid for sid in contribution_gids["concern_derived"] if gen[sid].get("generation_status") == kind})
        for kind in ("constraint_instantiation", "unreviewed_candidate")}
    for key, value in contributions.items():
        covered = set(value["matched_checker_ids"])
        other = set(contributions["concern_derived" if key == "explicit" else "explicit"]["matched_checker_ids"])
        exclusive, shared = sorted(covered - other), sorted(covered & other)
        value.update({"matched_checker_count": len(covered),
                      "exclusive_checker_ids": exclusive, "exclusive_checker_count": len(exclusive),
                      "shared_checker_ids": shared, "shared_checker_count": len(shared)})
    exception_rate = exception_overall["miss_rate"]
    acceptance = {"metric": "exception_overall.miss_rate", "threshold": 0.05, "operator": "<",
                  "matching_complete": True, "denominator": exception_rate["denominator"],
                  "rate": exception_rate["rate"],
                  "passed": exception_rate["denominator"] > 0 and exception_rate["rate"] < 0.05}
    special = {}
    for category, types in {"main_success": {"main_success"}, "alternative": {"alternative"},
                            "unclassified_exception": {"requirement_exception", "concern_derived_exception"}}.items():
        def included(s):
            return s.get("scenario_type") in types and (category != "unclassified_exception" or not s.get("concern_keys"))
        special[category] = summarize({sid for sid, s in ref.items() if included(s)},
                                      {sid for sid, s in gen.items() if included(s)})
    discrepancies = [x for x in links if x["status"] != "unmatched"
                     and set(ref[x["checker_scenario_id"]].get("concern_keys", []))
                     != set(gen[x["generated_scenario_id"]].get("concern_keys", []))]
    def label_coverage(scenes):
        explicit = [s for s in scenes.values() if s.get("scenario_type") == "requirement_exception"]
        return {"explicit_exception_count": len(explicit),
                "classified_count": sum(bool(s.get("concern_keys")) for s in explicit),
                "unclassified_ids": sorted(s["scenario_id"] for s in explicit if not s.get("concern_keys"))}
    return {"schema_version": "three-agent-v1", "complete": True,
            "input_hash": matches["input_hash"], "match_backend": matches["backend"],
            "accepted_statuses": ["full", "partial"], "overall": overall,
            "exception_overall": exception_overall, "generation_contributions": contributions,
            "concern_method_details": concern_method_details,
            "by_concern_exception": by_concern_exception, "by_group_exception": by_group_exception,
            "acceptance": acceptance,
            "by_concern": by_concern, "by_group": by_group, "special_categories": special,
            "classification_discrepancies": discrepancies, "matches": links,
            "full_matches": [m for m in links if m["status"] == "full"],
            "partial_matches": [m for m in links if m["status"] == "partial"],
            "classification_coverage": {"generator": label_coverage(gen), "checker": label_coverage(ref)},
            "note": "分类内分别去重，分类数不可相加；部分匹配计重合，置信度不是概率。"}
