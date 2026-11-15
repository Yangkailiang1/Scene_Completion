"""Project-scope DAG on the existing scheduler, semantic transport and budget ledger."""

from copy import deepcopy

from scene_completion.analysis.project_scopes.pipeline import (
    add_observations,
    generate_g,
    structure_bundles,
    structure_inputs,
)
from scene_completion.application import project_scope_service as results
from scene_completion.application.ssd_revision_service import _diff, _patch
from scene_completion.domain.project_scopes.matching import PAIRS, semantic_candidates
from scene_completion.domain.project_scopes.validation import KEYS, SCOPES, validate
from scene_completion.domain.ssd.construction import ident
from scene_completion.infrastructure import project_scope_repository as repository
from scene_completion.infrastructure.code_retry import revision as code_retry_revision
from scene_completion.infrastructure.storage import fingerprint
from scene_completion.workflow.recovery.node_repair import repair_revision
from scene_completion.workflow.semantics import code_version
from scene_completion.workflow_core import Task


def available(ex):
    return (
        getattr(ex, "client", None) is not None
        or getattr(ex, "mode", "packets") in {"external", "responses"}
        or getattr(ex, "mocks", None) is not None
    )


def semantic_identity(ex):
    return {
        "available": available(ex),
        "mode": getattr(ex, "mode", "packets"),
        "mock": getattr(ex, "mocks", None) is not None,
        "artifact_identity": getattr(ex, "artifact_identity", {}),
        "tasks": {
            t: code_version(t)
            for t in (
                "project-structure",
                "project-scope-identify",
                "project-scope-generate",
                "project-scope-compare",
            )
        },
    }


def positive(value):
    """Model context excludes output channels and duplicated citation text."""
    if isinstance(value, dict):
        return {
            k: positive(v)
            for k, v in value.items()
            if k not in {"source_refs", "channels", "documents", "source_records", "decisions"}
        }
    if isinstance(value, list):
        return [positive(v) for v in value]
    return value


def _task(ex, key, stage, deps, fn, *, scope=None, identity=None):
    if getattr(ex, "is_preview", False):
        ex.add(key, stage, deps, case="shared", transform=lambda d: d)
        return key
    reviewed = None
    if scope and stage == "project-compare" and repository.exists(ex.root.parent, scope):
        state = repository.state(ex.root.parent, scope)
        reviewed = fingerprint(state["overrides"]) if state["overrides"] else None

    def execute(values, record):
        result = fn({k: v.get("payload", v) for k, v in values.items()}, record)
        return {
            "task": stage,
            "payload": result,
            "metadata": {
                "execution": {
                    "provider": "project_scope_workflow",
                    "version": "project-scopes-v1",
                    "semantic_batches": record.get("semantic_sources", {}),
                }
            },
        }

    def verify(value):
        payload = value["payload"]
        if stage == "project-prepare":
            for bundle in payload.values():
                validate(bundle)
        else:
            validate(payload)

    ex.scheduler.add(
        Task(
            key=key,
            case="shared",
            stage=stage,
            deps=tuple(deps),
            version=fingerprint(
                [
                    code_version(stage),
                    semantic_identity(ex),
                    ex.registry_snapshot,
                    identity,
                    reviewed,
                    repair_revision(ex.root, key),
                ]
                + (
                    ["code_retry", code_retry_revision(ex.root, key)]
                    if code_retry_revision(ex.root, key)
                    else []
                )
                + (
                    [ex.conversations.revision(key)]
                    if getattr(ex, "conversations", None) and ex.conversations.revision(key)
                    else []
                )
            ),
            execute=execute,
            verify=verify,
            display_label={
                "project-prepare": "抽取用例依赖与外部服务",
                "project-identify": "独立识别原文与测试项目关注点",
                "project-generate": "项目模板与业务场景分析",
                "project-compare": "项目三方比较与发布",
            }[stage],
        )
    )
    return key


def _prepare(ex, bundles, documents, record):
    originals, inputs = structure_inputs(bundles, documents)
    parts = []
    if available(ex):
        chunks, current, size = [], [], 0
        for line in inputs["source_lines"]:
            if current and size + len(line["text"]) > 14000:
                chunks.append(current)
                current, size = [], 0
            current.append(line)
            size += len(line["text"])
        if current:
            chunks.append(current)
        for lines in chunks:
            context = {
                k: deepcopy(inputs[k])
                for k in ("cases", "entities", "known_external_services", "human_parties")
            }
            context["source_lines"] = lines
            payload, _ = ex.semantic("project-structure", context, record)
            parts.append(payload)
    return structure_bundles(
        bundles,
        originals,
        inputs,
        parts,
        ex.registry_snapshot,
        pending_reason=None if available(ex) else "尚未配置语义执行，项目依赖和外部服务抽取待运行",
    )


def _identify(ex, bundle, record):
    record = {} if record is None else record
    bundle = deepcopy(bundle)
    for channel in ("E", "GT"):
        own = bundle["source_records"][channel]
        if not own:
            continue
        if not available(ex) or not bundle["anchors"]:
            reason = (
                "尚未配置语义执行，独立来源待识别"
                if not available(ex)
                else "原始异常已保留，尚无可确认的项目关系或服务锚点，需人工定位"
            )
            bundle["channels"][channel]["pending"] += [
                {
                    **deepcopy(r),
                    "status": "pending",
                    "reason": reason,
                    "needs_semantic": available(ex),
                }
                for r in own
            ]
            continue
        for start in range(0, len(own), 24):
            records = own[start : start + 24]
            context = {
                "scope": bundle["scope"]["id"],
                "channel": channel,
                "anchors": positive(bundle["anchors"]),
                "cases": bundle["cases"],
                "allowed_keys": sorted(KEYS[bundle["scope"]["id"]]),
                "records": deepcopy(records),
            }
            anchor_handles = {}
            source_handles = {}
            for n, anchor in enumerate(context["anchors"], 1):
                handle = f"A{n:02d}"
                anchor_handles[handle] = anchor["id"]
                anchor["id"] = handle
            for n, source in enumerate(context["records"], 1):
                handle = f"R{n:02d}"
                source_handles[handle] = source["id"]
                source["id"] = handle
                source.pop("original_id", None)
            record["_short_id_mapping"] = {"anchors": anchor_handles, "sources": source_handles}
            payload, _ = ex.semantic("project-scope-identify", context, record)
            for collection in ("observations", "pending", "excluded"):
                for item in payload[collection]:
                    item["source_record_id"] = source_handles[item["source_record_id"]]
                    if collection == "observations":
                        item["anchor_id"] = anchor_handles[item["anchor_id"]]
            add_observations(bundle, channel, payload, records)
    bundle["gt_identification_run_complete"] = available(ex) or not bundle["source_records"]["GT"]
    return validate(bundle)


def _generate(ex, bundle, record):
    bundle = deepcopy(bundle)
    templates = [r for r in bundle["channels"]["G"]["scenarios"] if r.get("template_id")]
    if not available(ex):
        bundle["generation_pending"] = [r["id"] for r in templates]
        return validate(bundle)
    anchors = {a["id"]: a for a in bundle["anchors"]}
    for aid in anchors:
        rows = [r for r in templates if r["anchor_id"] == aid]
        anchor = anchors[aid]
        case_ids = {
            anchor.get("from_case_id"),
            anchor.get("to_case_id"),
            *anchor.get("case_ids", []),
        }
        facts = []
        for item in bundle.get("positive_cases", []):
            if item["case"]["id"] not in case_ids:
                continue
            relevant = [
                s
                for s in item["steps"]
                if s.get("direction") == "request"
                and (
                    anchor.get("kind") == "dependency"
                    and s.get("sender", {}).get("type") == "human"
                    or anchor.get("kind") == "external_service"
                    and s.get("receiver", {}).get("id") == anchor.get("identity")
                    or anchor.get("kind") == "external_service"
                    and s.get("receiver", {}).get("name") == anchor.get("name")
                )
            ]
            facts.append(
                {
                    "case": item["case"],
                    "steps": [
                        {
                            k: s.get(k)
                            for k in (
                                "id",
                                "sender",
                                "receiver",
                                "operation",
                                "api_id",
                                "entity_ids",
                            )
                        }
                        for s in relevant
                    ],
                }
            )
        for start in range(0, len(rows), 24):
            batch = rows[start : start + 24]
            context = {
                "scope": bundle["scope"]["id"],
                "anchor": positive(anchor),
                "positive_cases": positive(facts),
                "templates": [
                    {
                        "id": r["id"],
                        "concern_id": r["concern_ids"][0],
                        "key": r["key"],
                        "template_id": r["template_id"],
                        "condition": r["condition"],
                        "expected": r.get("expected", ""),
                    }
                    for r in batch
                ],
            }
            handles = {}
            for n, template in enumerate(context["templates"], 1):
                handle = f"T{n:02d}"
                handles[handle] = template["id"]
                template["id"] = handle
            payload, _ = ex.semantic("project-scope-generate", context, record)
            for item in payload["analyses"]:
                item["scenario_id"] = handles[item["scenario_id"]]
            analyses = {r["scenario_id"]: r["analysis"] for r in payload["analyses"]}
            for row in batch:
                row.update(
                    analysis=analyses[row["id"]],
                    generation_status="complete",
                    generation_version=code_version("project-scope-generate"),
                )
            concerns = {r["id"]: r for r in bundle["channels"]["G"]["concerns"]}
            for row in payload["supplements"]:
                concern = concerns[row["concern_id"]]
                if any(
                    s["concern_ids"] == [concern["id"]]
                    and s["condition"] == row["condition"]
                    and s.get("expected", "") == row["expected"]
                    for s in bundle["channels"]["G"]["scenarios"]
                ):
                    continue
                bundle["channels"]["G"]["scenarios"].append(
                    {
                        **deepcopy(concern),
                        "id": ident(
                            "G-project-supplement", concern["id"], row["condition"], row["expected"]
                        ),
                        "concern_ids": [concern["id"]],
                        "condition": row["condition"],
                        "expected": row["expected"],
                        "analysis": row["analysis"],
                        "generation_origin": "model_supplement",
                        "generation_version": code_version("project-scope-generate"),
                        "generation_status": "complete",
                    }
                )
    bundle["generation_pending"] = []
    return validate(bundle)


def _compare_pairs(ex, bundle, record):
    bundle = deepcopy(bundle)
    if not available(ex):
        return validate(bundle)
    candidates = semantic_candidates(bundle)
    for pair, (a, b) in PAIRS.items():
        left = {r["id"]: r for r in bundle["channels"][a]["scenarios"]}
        right = {r["id"]: r for r in bundle["channels"][b]["scenarios"]}
        pairs = [
            {"left": left[p["left_id"]], "right": right[p["right_id"]]}
            for p in candidates
            if p["pair"] == pair
        ]
        for start in range(0, len(pairs), 24):
            payload, _ = ex.semantic(
                "project-scope-compare", {"pair": pair, "pairs": pairs[start : start + 24]}, record
            )
            bundle["decisions"].extend(
                {
                    **d,
                    "id": ident("project-auto", pair, d),
                    "pair": pair,
                    "level": "scenario",
                    "origin": "auto",
                }
                for d in payload["decisions"]
            )
    return validate(bundle)


def _reuse_decisions(ex, bundle):
    scope = bundle["scope"]["id"]
    if not repository.exists(ex.root.parent, scope):
        return bundle
    state = repository.state(ex.root.parent, scope)
    identity = semantic_identity(ex)
    present = {(d["pair"], d["left_id"], d["right_id"], d["level"]) for d in bundle["decisions"]}
    for old in (state["baseline"], state.get("previous_baseline")):
        if not old or old.get("semantic_identity") != identity:
            continue
        for decision in old.get("decisions", []):
            key = (decision["pair"], decision["left_id"], decision["right_id"], decision["level"])
            if key in present or decision.get("origin") != "auto":
                continue
            kind = "concerns" if decision["level"] == "concern" else "scenarios"

            def endpoint(container, channel, rid):
                row = next(
                    (r for r in container["channels"][channel][kind] if r["id"] == rid), None
                )
                return {k: v for k, v in row.items() if k != "source_refs"} if row else None

            if all(
                endpoint(bundle, ch, rid) is not None
                and endpoint(bundle, ch, rid) == endpoint(old, ch, rid)
                for ch, rid in zip(
                    PAIRS[decision["pair"]], (decision["left_id"], decision["right_id"])
                )
            ):
                bundle["decisions"].append(deepcopy(decision))
                present.add(key)
    return bundle


def _compare(ex, generated, identified, record):
    machine = deepcopy(generated)
    for channel in ("E", "GT"):
        machine["channels"][channel] = deepcopy(identified["channels"][channel])
    machine["excluded"] = deepcopy(identified.get("excluded", {}))
    machine["gt_identification_run_complete"] = identified.get(
        "gt_identification_run_complete", False
    )
    machine = _compare_pairs(ex, _reuse_decisions(ex, machine), record)
    machine["semantic_identity"] = semantic_identity(ex)
    snapshot = results.publish(ex.root.parent, machine)
    effective = snapshot["bundle"]
    if available(ex) and results.editable(effective) != results.editable(machine):
        reviewed = deepcopy(effective)
        if reviewed.get("generation_pending"):
            original_g = deepcopy(machine["channels"]["G"])
            human_g = deepcopy(reviewed["channels"]["G"])
            for row in human_g["scenarios"]:
                if row.pop("generation_status", None) == "needs_regeneration":
                    row["status"] = "active"
            for row in original_g["scenarios"]:
                # System generation state is not a human edit.
                row.pop("generation_status", None)
            reviewed["channels"]["G"] = generate_g(reviewed)
            reviewed = _generate(ex, reviewed, record)
            reviewed["channels"]["G"] = _patch(
                reviewed["channels"]["G"], _diff(original_g, human_g)
            )
            reviewed["generation_pending"] = []
            results.invalidate(effective, reviewed)
        reviewed = _compare_pairs(ex, reviewed, record)
        if results.editable(reviewed) != results.editable(effective):
            try:
                results.save_revision(
                    ex.root.parent,
                    machine["scope"]["id"],
                    {
                        "base_revision": snapshot["revision"],
                        "bundle": reviewed,
                        "reason": "自动复核人工修订的项目场景与对应",
                    },
                )
            except results.RevisionConflict as conflict:
                from scene_completion.workflow_core import TaskBlocked

                raise TaskBlocked(
                    "pending",
                    {
                        "reason": "项目人工修订已更新，请继续运行复核",
                        "review_conflict": conflict.current_revision,
                    },
                ) from conflict
    return machine


def build_project_scopes(ex, prepare_keys, documents=None):
    """Register project stages after case preparation; no direct model/network calls."""
    keys = list(prepare_keys)
    if not keys:
        return []
    material = deepcopy(documents or [])
    prepare = _task(
        ex,
        "project:project-prepare",
        "project-prepare",
        keys,
        lambda values, record: _prepare(ex, [values[k] for k in keys], material, record),
        identity=fingerprint(material),
    )
    final = []
    for scope in SCOPES:
        prefix = "project:" + scope + ":"
        identified = _task(
            ex,
            prefix + "project-identify",
            "project-identify",
            [prepare],
            lambda values, record, s=scope: _identify(ex, values[prepare][s], record),
            scope=scope,
        )
        generated = _task(
            ex,
            prefix + "project-generate",
            "project-generate",
            [prepare],
            lambda values, record, s=scope: _generate(ex, values[prepare][s], record),
            scope=scope,
        )
        compared = _task(
            ex,
            prefix + "project-compare",
            "project-compare",
            [identified, generated],
            lambda values, record, a=identified, b=generated: _compare(
                ex, values[b], values[a], record
            ),
            scope=scope,
        )
        final.append(compared)
    ex.manifest["project_scopes"] = list(SCOPES)
    return final
