"""Versioned shared-service revisions over a read-only projection of case results."""

from copy import deepcopy
from pathlib import Path

from scene_completion.application import ssd_revision_service as cases
from scene_completion.application.ssd_revision_service import RevisionConflict, _diff, _patch
from scene_completion.domain.current_scope import POLICY
from scene_completion.domain.project_scopes import matching
from scene_completion.domain.project_scopes.metrics import analyze
from scene_completion.domain.project_scopes.validation import validate
from scene_completion.domain.shared_services.aggregation import build
from scene_completion.infrastructure import project_scope_repository, ssd_repository
from scene_completion.infrastructure.result_cache import cached_index
from scene_completion.infrastructure.storage import read_json, write_json
from scene_completion.workflow_core.storage import run_lock

KEY = "shared_services"
EDITABLE = ("channels", "decisions", "review_notes", "review_feedback", "display_rows")


def root(project):
    return Path(project) / "shared_service_results"


def _fresh(project):
    from scene_completion.application.result_projection import identification_proof

    views = [
        ssd_repository.revision(project, s["case"]["id"], s["revision"])
        for s in ssd_repository.states(project)
    ]
    legacy = None
    if project_scope_repository.exists(project, "architecture"):
        s = project_scope_repository.state(project, "architecture")
        legacy = project_scope_repository.revision(project, "architecture", s["revision"])
        complete, _ = identification_proof(project, legacy["bundle"])
        if complete is not None:
            legacy = {
                **legacy,
                "bundle": {**legacy["bundle"], "gt_identification_run_complete": complete},
            }
    from scene_completion.domain.concern_registry import default_registry
    from scene_completion.domain.current_scope import current_registry

    value = build(views, legacy)
    registry = next((v["bundle"]["registry"] for v in views if v["bundle"].get("registry")), None)
    value["registry"] = current_registry(registry or default_registry())
    return validate(value)


def _state(project):
    p = root(project) / "state.json"
    return read_json(p) if p.exists() else {"revision": 0, "overrides": {}, "history": []}


def _view(bundle, revision, history, original=None):
    from scene_completion.domain.coverage import review_statuses

    r = analyze(bundle)
    initial = analyze(original) if original is not None else r
    r["metrics_by_level"] = {
        "concern": r["metrics"],
        "scenario": {k: r["scenario_diagnostic"][k] for k in r["metrics"]},
    }
    return {
        **r,
        "bundle": bundle,
        "revision": revision,
        "history": history,
        "original_metrics": initial["metrics"],
        "original_metrics_by_level": {
            "concern": initial["metrics"],
            "scenario": {k: initial["scenario_diagnostic"][k] for k in initial["metrics"]},
        },
        "review_statuses": review_statuses(bundle, matching),
        "identification_proof": {
            "complete": bundle.get("gt_identification_run_complete"),
            "source": "调用成员识别状态",
        },
    }


def editor(project, scope=KEY, revision=None):
    state = _state(project)
    if revision and revision != "original":
        p = root(project) / "revisions" / (str(int(revision)) + ".json")
        if not p.exists():
            raise ValueError("该共享服务历史版本不存在")
        return read_json(p)
    baseline = _fresh(project)
    if revision == "original":
        return _view(baseline, "original", state["history"])
    issues = []
    effective = {
        **baseline,
        **_patch(
            {k: baseline.get(k, []) for k in EDITABLE},
            state["overrides"],
            issues,
        ),
    }
    effective["revision_issues"] = issues
    if state["revision"]:
        previous = read_json(root(project) / "revisions" / (str(state["revision"]) + ".json"))[
            "bundle"
        ]
        for issue in issues:
            parts = issue.get("path", "").split("/")
            # _patch paths are /channels/G/scenarios (record ID is in issue.id).
            if len(parts) == 4 and parts[1] == "channels" and parts[3] in {"concerns", "scenarios"}:
                channel, kind = parts[2:]
                old = next(
                    (r for r in previous["channels"][channel][kind] if r["id"] == issue["id"]), None
                )
                if old and not any(
                    r["id"] == old["id"] for r in effective["channels"][channel][kind]
                ):
                    effective["channels"][channel][kind].append(
                        {**deepcopy(old), "status": "unbound", "binding_issue": issue["reason"]}
                    )
        needed = set()

        def referenced(value):
            if isinstance(value, dict):
                if value.get("document_id"):
                    needed.add(value["document_id"])
                for item in value.values():
                    referenced(item)
            elif isinstance(value, list):
                for item in value:
                    referenced(item)

        referenced(effective["channels"])
        existing = {d["id"] for d in effective["documents"]}
        effective["documents"].extend(
            deepcopy(d) for d in previous.get("documents", []) if d["id"] in needed - existing
        )
    kept = []
    for decision in effective.get("decisions", []):
        channel_left, channel_right = decision["pair"].split("_")
        kind = "scenarios" if decision["level"] == "scenario" else "concerns"
        left = next(
            (
                r
                for r in effective["channels"][channel_left][kind]
                if r["id"] == decision["left_id"]
            ),
            None,
        )
        right = next(
            (
                r
                for r in effective["channels"][channel_right][kind]
                if r["id"] == decision["right_id"]
            ),
            None,
        )
        if left and right and matching.binding(left) == matching.binding(right):
            kept.append(decision)
        else:
            effective.setdefault("pending", []).append(
                {
                    "id": decision["id"],
                    "reason": "服务成员变化，原人工判定待重新定位",
                    "original_decision": deepcopy(decision),
                }
            )
    effective["decisions"] = kept
    # Source versions always come from current member snapshots, not a human override.
    effective = validate(effective)
    number = state["revision"] + int(
        state.get("sources") is not None and state["sources"] != baseline["source_versions"]
    )
    return _view(effective, number, state["history"], baseline)


def _store(project, bundle, baseline, state, reason):
    def editable(b):
        return {k: deepcopy(b.get(k, [])) for k in EDITABLE}

    number = state["revision"] + 1
    history = [*state["history"], {"revision": number, "reason": reason}]
    view = _view(bundle, number, history, baseline)
    write_json(root(project) / "revisions" / (str(number) + ".json"), view)
    write_json(
        root(project) / "state.json",
        {
            "revision": number,
            "history": history,
            "sources": baseline["source_versions"],
            "overrides": _diff(editable(baseline), editable(bundle)),
            "analysis_policy": POLICY,
        },
    )
    return view


def save_revision(project, scope, body):
    with ssd_repository.locked(project), run_lock(root(project)):
        current = editor(project)
        submitted = body.get("bundle", {})
        if (
            body.get("base_revision") != current["revision"]
            or submitted.get("source_versions") != current["bundle"]["source_versions"]
        ):
            raise RevisionConflict(current["revision"])
        for k in ("version", "scope", "documents", "anchors", "registry"):
            if submitted.get(k) != current["bundle"].get(k):
                raise ValueError("不可改写共用服务的原始身份、出处或调用成员")
        updated = deepcopy(current["bundle"])
        for k in EDITABLE:
            if k in submitted:
                updated[k] = deepcopy(submitted[k])
        updated = validate(updated)
        old_rows = {
            (c, k, r["id"]): r
            for c, data in current["bundle"]["channels"].items()
            for k in ("concerns", "scenarios")
            for r in data[k]
        }
        new_rows = {
            (c, k, r["id"]): r
            for c, data in updated["channels"].items()
            for k in ("concerns", "scenarios")
            for r in data[k]
        }

        def identity(row):
            return (
                None
                if row is None
                else (
                    matching.binding(row),
                    row.get("condition"),
                    row.get("expected"),
                    row.get("status"),
                )
            )

        changed = {
            key
            for key in old_rows.keys() | new_rows.keys()
            if identity(old_rows.get(key)) != identity(new_rows.get(key))
        }
        old_decisions = {d["id"]: d for d in current["bundle"]["decisions"]}
        updated["decisions"] = [
            d
            for d in updated["decisions"]
            if old_decisions.get(d["id"]) != d
            or not any(
                (channel, "scenarios" if d["level"] == "scenario" else "concerns", d[side + "_id"])
                in changed
                for channel, side in zip(d["pair"].split("_"), ("left", "right"), strict=True)
            )
        ]
        updated = validate(updated)
        if updated == current["bundle"]:
            return current
        return _store(
            project,
            updated,
            _fresh(project),
            _state(project),
            str(body.get("reason") or "共用外部服务人工修订"),
        )


def publish(project):
    with ssd_repository.locked(project), run_lock(root(project)):
        current = editor(project)
        state = _state(project)
        if state.get("sources") == current["bundle"]["source_versions"]:
            return current
        return _store(
            project,
            current["bundle"],
            _fresh(project),
            state,
            "交互发布后合并外部服务；保留人工修订",
        )


@cached_index("ssd_results", "project_results", "shared_service_results")
def index(project):
    from scene_completion.domain.ssd.metrics import _rate

    current = cases.index(project)
    shared = editor(project)
    values = {
        "interaction": {
            **current["metrics_by_level"],
            "complete": all(c["completeness"]["complete"] for c in current["cases"]),
            "available": bool(current["cases"]),
        },
        KEY: {
            **shared["metrics_by_level"],
            "complete": shared["completeness"]["complete"],
            "available": bool(shared["bundle"]["anchors"]),
        },
    }
    overall = {
        level: {
            k: _rate(
                sum(v[level][k]["numerator"] for v in values.values()),
                sum(v[level][k]["denominator"] for v in values.values()),
            )
            for k in current["metrics"]
        }
        for level in ("concern", "scenario")
    }
    return {
        "version": "project-scopes-v1",
        "analysis_policy": POLICY,
        "scopes": [
            {
                "id": KEY,
                "name": "共用外部服务",
                "available": bool(shared["bundle"]["anchors"]),
                "revision": shared["revision"],
                "anchor_count": len(shared["bundle"]["anchors"]),
                "complete": shared["completeness"]["complete"],
                "pending_count": sum(
                    v
                    for k, v in shared["completeness"].items()
                    if k != "complete" and isinstance(v, int)
                ),
            }
        ],
        "legacy_scopes": [
            s
            for s in ("business_chain", "architecture")
            if project_scope_repository.exists(project, s)
        ],
        "metrics": {
            "by_scope": values,
            "overall": overall,
            "complete": all(v["complete"] for v in values.values()),
        },
    }
