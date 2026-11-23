"""Align, compare and publish the three SSD channels."""

from copy import deepcopy

from scene_completion.application import ssd_revision_service as ssd_results
from scene_completion.domain.coverage import GRAIN_POLICY, binary_status
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE
from scene_completion.domain.ssd import matching as ssd_matching
from scene_completion.domain.ssd import validation as ssd_validation
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.workflow.ssd.generate.stage import _generate
from scene_completion.workflow.ssd.shared.machine_history import _machine_baselines
from scene_completion.workflow.ssd.shared.semantic_execution import (
    _semantic_available,
    _semantic_cache_identity,
)


def _review_material(bundle):
    return {
        "steps": bundle.get("steps", []),
        "channels": bundle.get("channels", {}),
        "decisions": [d for d in bundle.get("decisions", []) if d.get("origin") == "manual"],
    }


def _review_identity(ex, cid):
    try:
        effective = ssd_results.editor(ex.root.parent, cid)["bundle"]
        baseline = ssd_results.editor(ex.root.parent, cid, "original")["bundle"]
    except ValueError:
        return None
    material = _review_material(effective)
    return fingerprint(material) if material != _review_material(baseline) else None


def _compare_pairs(ex, bundle, record):
    """Use the result layer's candidate contract without publishing a baseline."""
    bundle = deepcopy(bundle)
    if not _semantic_available(ex):
        return ssd_validation.validate(bundle)
    candidates = ssd_matching.semantic_candidates(bundle)
    for pair, (a, b) in ssd_matching.PAIRS.items():
        left = {r["id"]: r for r in bundle["channels"][a]["scenarios"]}
        right = {r["id"]: r for r in bundle["channels"][b]["scenarios"]}
        pairs = [
            (left[p["left_id"]], right[p["right_id"]]) for p in candidates if p["pair"] == pair
        ]
        for offset in range(0, len(pairs), 24):
            batch = pairs[offset : offset + 24]
            projected = [{"left": x, "right": y} for x, y in batch]
            if pair == "GT_E":
                for comparison in projected:
                    for side in ("left", "right"):
                        comparison[side] = {
                            k: v for k, v in comparison[side].items() if k != "aligned_concern_ids"
                        }
            result, _ = ex.semantic(
                "ssd-semantic-compare",
                {
                    "pair": pair,
                    "pairs": projected,
                    **(
                        {"coverage_policy": GRAIN_POLICY}
                        if bundle.get("coverage_policy") == GRAIN_POLICY
                        else {}
                    ),
                },
                record,
            )
            expected = {(x["id"], y["id"]) for x, y in batch}
            actual = {(d["left_id"], d["right_id"]) for d in result["decisions"]}
            if actual != expected or len(actual) != len(result["decisions"]):
                raise ValueError("语义比较必须逐对返回全部候选，不能新增或遗漏")
            bundle.setdefault("decisions", []).extend(
                {
                    **d,
                    "id": "auto-" + fingerprint([pair, d])[:20],
                    "level": "scenario",
                    "pair": pair,
                    "origin": "auto",
                    **(
                        {"status": binary_status(d["status"])}
                        if bundle.get("coverage_policy") == GRAIN_POLICY
                        else {}
                    ),
                }
                for d in result["decisions"]
            )
    return ssd_validation.validate(bundle)


def _reuse_machine_decisions(ex, bundle, semantic_identity):
    """Reuse unchanged pairs across human edits or a newly published preparation."""

    def semantic_record(record):
        if record is None:
            return None
        # Citation repairs change provenance, not the judged failure. Keep all
        # other fields strict so conditions, outcomes and bindings invalidate.
        return {key: value for key, value in record.items() if key != "source_refs"}

    bundle = deepcopy(bundle)
    existing = {
        (d["level"], d["pair"], d["left_id"], d["right_id"]) for d in bundle.get("decisions", [])
    }
    for baseline in _machine_baselines(ex, bundle["case"]["id"]):
        if not baseline or baseline.get("semantic_comparison_identity") != semantic_identity:
            continue
        for decision in baseline.get("decisions", []):
            identity = (
                decision["level"],
                decision["pair"],
                decision["left_id"],
                decision["right_id"],
            )
            if identity in existing or decision.get("origin") != "auto":
                continue
            a, b = ssd_matching.PAIRS[decision["pair"]]
            kind = "scenarios" if decision["level"] == "scenario" else "concerns"
            unchanged = all(
                semantic_record(
                    next((r for r in bundle["channels"][channel][kind] if r["id"] == ident), None)
                )
                == semantic_record(
                    next((r for r in baseline["channels"][channel][kind] if r["id"] == ident), None)
                )
                and any(r["id"] == ident for r in bundle["channels"][channel][kind])
                for channel, ident in ((a, decision["left_id"]), (b, decision["right_id"]))
            )
            if unchanged:
                bundle.setdefault("decisions", []).append(deepcopy(decision))
                existing.add(identity)
    return bundle


def _compare(ex, bundle, record):
    """Publish machine analysis, then independently review the effective human version."""
    from scene_completion.workflow.semantics import code_version

    semantic_identity = {
        "logic": code_version("ssd-compare"),
        **_semantic_cache_identity(ex, "ssd-compare"),
        **(
            {"guidance_revision": ex.conversations.revision(bundle["case"]["id"] + ":ssd-compare")}
            if getattr(ex, "conversations", None)
            and ex.conversations.revision(bundle["case"]["id"] + ":ssd-compare")
            else {}
        ),
    }
    if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE:
        bundle = {**bundle, "coverage_policy": GRAIN_POLICY}
    if bundle.get("coverage_policy") == GRAIN_POLICY and _semantic_available(ex):
        from scene_completion.workflow.ssd.compare import alignment

        bundle = deepcopy(bundle)

        def semantic(task, inputs):
            result, _ = ex.semantic(task, inputs, record)
            return result

        alignment.align(bundle, semantic)
    machine = _reuse_machine_decisions(ex, bundle, semantic_identity)
    machine = _compare_pairs(ex, machine, record)
    machine["semantic_comparison_identity"] = semantic_identity
    snapshot = ssd_results.publish(ex.root.parent, machine)
    effective = snapshot["bundle"]
    if _semantic_available(ex) and effective.get("scenario_generation", {}).get("pending_ids"):
        pending_machine = deepcopy(effective)
        pending_machine["channels"]["G"] = deepcopy(effective["machine_g"])
        enriched = _generate(ex, pending_machine, record)
        snapshot = ssd_results.enrich_effective(
            ex.root.parent, machine["case"]["id"], snapshot["revision"], enriched
        )
        effective = snapshot["bundle"]
    if _semantic_available(ex) and _review_material(effective) != _review_material(machine):
        reviewed = _compare_pairs(ex, effective, record)
        if reviewed.get("decisions", []) != effective.get("decisions", []):
            try:
                ssd_results.save_revision(
                    ex.root.parent,
                    machine["case"]["id"],
                    {
                        "base_revision": snapshot["revision"],
                        "bundle": reviewed,
                        "reason": "自动复核人工修订的未决场景对应",
                    },
                )
            except ssd_results.RevisionConflict as conflict:
                from scene_completion.workflow_core import TaskBlocked

                # Do not cache this stage as complete: even an unrelated note
                # edit can conflict while leaving the semantic signature intact.
                raise TaskBlocked(
                    "pending",
                    {
                        "review_conflict": conflict.current_revision,
                        "reason": "人工修订已更新，重新运行可复核剩余对应",
                    },
                ) from conflict
    return machine
