"""Project-scope publication and human revisions, separate from immutable history."""

import time
from copy import deepcopy

from scene_completion.application.ssd_revision_service import RevisionConflict, _diff, _patch
from scene_completion.domain.project_scopes.matching import PAIRS, binding
from scene_completion.domain.project_scopes.metrics import _rate, analyze
from scene_completion.domain.project_scopes.validation import SCOPES, validate
from scene_completion.domain.ssd.construction import ident
from scene_completion.infrastructure import project_scope_repository as repository
from scene_completion.infrastructure.result_cache import cached_index

EDITABLE = {
    "anchors",
    "channels",
    "decisions",
    "review_notes",
    "review_feedback",
    "generation_pending",
}


def editable(bundle):
    return {k: deepcopy(bundle.get(k, [])) for k in EDITABLE}


def report(bundle):
    out = analyze(bundle)
    out["metrics_by_level"] = {
        "concern": out["metrics"],
        "scenario": {k: out["scenario_diagnostic"][k] for k in out["metrics"]},
    }
    return out


def invalidate(previous, updated):
    removed = set()
    for channel in ("E", "G", "GT"):
        for kind in ("concerns", "scenarios"):
            old = {r["id"]: r for r in previous["channels"][channel][kind]}
            new = {r["id"]: r for r in updated["channels"][channel][kind]}
            removed |= {(channel, k) for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    original = {d["id"]: d for d in previous.get("decisions", [])}
    kept = []
    for d in updated.get("decisions", []):
        a, b = PAIRS[d["pair"]]
        kind = "concerns" if d["level"] == "concern" else "scenarios"
        left = next((r for r in updated["channels"][a][kind] if r["id"] == d["left_id"]), None)
        right = next((r for r in updated["channels"][b][kind] if r["id"] == d["right_id"]), None)
        if not left or not right or binding(left) != binding(right):
            continue
        if ((a, d["left_id"]) in removed or (b, d["right_id"]) in removed) and original.get(
            d["id"]
        ) == d:
            continue
        kept.append(d)
    updated["decisions"] = kept


def _store(project, bundle, baseline, revision, history, overrides, reason, previous=None):
    calculated = report(bundle)
    original = report(baseline)
    history = [
        *history,
        {
            "revision": revision,
            "created_at": time.time(),
            "reason": reason,
            "metrics": calculated["metrics"],
            "metrics_by_level": calculated["metrics_by_level"],
        },
    ]
    snapshot = {
        "bundle": bundle,
        "revision": revision,
        **calculated,
        "original_metrics": original["metrics"],
        "original_metrics_by_level": original["metrics_by_level"],
        "history": history,
    }
    repository.store(
        project,
        bundle["scope"]["id"],
        revision,
        snapshot,
        {
            "scope": bundle["scope"],
            "revision": revision,
            "baseline": baseline,
            "overrides": overrides,
            "history": history,
            "previous_baseline": previous,
        },
    )
    return snapshot


def editor(project, scope, revision=None):
    state = repository.state(project, scope)
    if revision == "original":
        bundle = deepcopy(state["baseline"])
        result = report(bundle)
        return {
            "bundle": bundle,
            "revision": "original",
            **result,
            "original_metrics": result["metrics"],
            "original_metrics_by_level": result["metrics_by_level"],
            "history": state["history"],
        }
    view = repository.revision(
        project, scope, state["revision"] if revision in (None, "current") else revision
    )
    if revision in (None, "current"):
        from scene_completion.application.result_projection import current_view
        from scene_completion.domain.project_scopes import matching

        return current_view(project, view, matching)
    return view


def publish(project, bundle):
    baseline = validate(bundle)
    scope = bundle["scope"]["id"]
    with repository.locked(project):
        if not repository.exists(project, scope):
            return _store(project, baseline, baseline, 1, [], {}, "机器原始结果")
        state = repository.state(project, scope)
        if state["baseline"] == baseline:
            return editor(project, scope)
        issues = []
        effective = {**baseline, **_patch(editable(baseline), state["overrides"], issues)}
        effective["revision_issues"] = issues
        invalidate(editor(project, scope)["bundle"], effective)
        effective = validate(effective)
        return _store(
            project,
            effective,
            baseline,
            state["revision"] + 1,
            state["history"],
            state["overrides"],
            "自动运行更新；保留人工修订",
            state["baseline"],
        )


def _promote(bundle):
    for ch in ("E", "G", "GT"):
        kept = []
        data = bundle["channels"][ch]
        for row in data.get("pending", []):
            if row.get("status") != "active":
                kept.append(row)
                continue
            if any(not row.get(k) for k in ("anchor_id", "target", "key", "condition")):
                raise ValueError("确认异常须指定真实项目锚点、对象、关注点和失败条件")
            cid = ident(
                ch + "-project-concern", bundle["scope"]["id"], row["anchor_id"], row["key"]
            )
            if not any(r["id"] == cid for r in data["concerns"]):
                data["concerns"].append({**deepcopy(row), "id": cid})
            data["scenarios"].append(
                {
                    **deepcopy(row),
                    "id": ident(ch + "-project-scenario", row["id"]),
                    "concern_ids": [cid],
                    "expected": row.get("expected", ""),
                }
            )
        data["pending"] = kept


def save_revision(project, scope, body):
    with repository.locked(project):
        state = repository.state(project, scope)
        if body.get("base_revision") != state["revision"]:
            raise RevisionConflict(state["revision"])
        current = editor(project, scope)["bundle"]
        submitted = body.get("bundle")
        if not isinstance(submitted, dict) or any(
            submitted.get(k) != current.get(k) for k in ("scope", "version", "documents")
        ):
            raise ValueError("不可更改项目范围、版本或原始文档")
        updated = {**current, **editable(submitted)}
        updated["coverage_policy"] = "coverage-any-confirmed-v2"
        _promote(updated)
        if current["anchors"] != updated["anchors"]:
            old = {a["id"]: a for a in current["anchors"]}
            changed = [a["id"] for a in updated["anchors"] if old.get(a["id"]) != a]
            updated["generation_pending"] = sorted(
                set(updated.get("generation_pending", [])) | set(changed)
            )
            for row in updated["channels"]["G"]["scenarios"]:
                if row.get("anchor_id") in changed:
                    row["status"] = "pending"
                    row["generation_status"] = "needs_regeneration"
        invalidate(current, updated)
        updated = validate(updated)
        if editable(current) == editable(updated):
            return editor(project, scope)
        overrides = _diff(editable(state["baseline"]), editable(updated))
        return _store(
            project,
            updated,
            state["baseline"],
            state["revision"] + 1,
            state["history"],
            overrides,
            str(body.get("reason") or "人工修正"),
        )


@cached_index("ssd_results", "project_results")
def index(project):
    from scene_completion.application import ssd_revision_service

    scopes, by_scope = [], {}
    for scope, name in SCOPES.items():
        if not repository.exists(project, scope):
            scopes.append(
                {
                    "id": scope,
                    "name": name,
                    "available": False,
                    "complete": False,
                    "anchor_count": 0,
                }
            )
            continue
        snap = repository.revision(project, scope, repository.state(project, scope)["revision"])
        progress = snap["completeness"]
        scopes.append(
            {
                "id": scope,
                "name": name,
                "available": True,
                "revision": snap["revision"],
                "anchor_count": len(snap["bundle"]["anchors"]),
                "metrics": snap["metrics"],
                "metrics_by_level": snap["metrics_by_level"],
                "completeness": progress,
                "complete": progress["complete"],
                "pending_count": sum(v for k, v in progress.items() if k != "complete"),
            }
        )
        by_scope[scope] = {**snap["metrics_by_level"], "complete": progress["complete"]}
    interaction = ssd_revision_service.index(project)
    if interaction["cases"]:
        from scene_completion.infrastructure import ssd_repository

        reports = [
            ssd_repository.revision(project, c["id"], c["revision"]) for c in interaction["cases"]
        ]
        by_scope["interaction"] = {
            "concern": interaction["metrics"],
            "scenario": {
                k: _rate(
                    sum(s["scenario_diagnostic"][k]["numerator"] for s in reports),
                    sum(s["scenario_diagnostic"][k]["denominator"] for s in reports),
                )
                for k in interaction["metrics"]
            },
            "complete": all(r["completeness"]["complete"] for r in reports),
        }
    overall = {
        level: {
            key: _rate(
                sum(s[level][key]["numerator"] for s in by_scope.values()),
                sum(s[level][key]["denominator"] for s in by_scope.values()),
            )
            for key in ("missing_exception_miss_rate", "generation_validity")
        }
        for level in ("concern", "scenario")
    }
    return {
        "version": "project-scopes-v1",
        "scopes": scopes,
        "metrics": {
            "by_scope": by_scope,
            "overall": overall,
            "complete": len(by_scope) == 3 and all(s["complete"] for s in by_scope.values()),
        },
    }
