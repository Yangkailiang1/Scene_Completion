"""Machine publication and human revision use cases for SSD results."""

import time
from copy import deepcopy

from scene_completion.domain.ssd.matching import PAIRS, binding
from scene_completion.domain.ssd.metrics import _rate, analyze
from scene_completion.domain.ssd.validation import VERSION, validate
from scene_completion.infrastructure import ssd_repository as repository
from scene_completion.infrastructure.result_cache import cached_index
from scene_completion.infrastructure.storage import fingerprint

EDITABLE = {
    "steps",
    "channels",
    "decisions",
    "review_notes",
    "review_feedback",
    "display_rows",
    "coverage_policy",
}


class RevisionConflict(ValueError):
    def __init__(self, revision):
        super().__init__("结果已被更新，请刷新后重新应用修改")
        self.current_revision = revision


def _diff(base, changed):
    """Recursive differences with stable-id arrays; explicit deletions survive reruns."""
    if isinstance(base, dict) and isinstance(changed, dict):
        return {
            k: {"delete": True}
            if k not in changed
            else {"replace": changed[k]}
            if k not in base
            else _diff(base[k], changed[k])
            for k in base.keys() | changed.keys()
            if base.get(k) != changed.get(k)
        }
    if (
        isinstance(base, list)
        and isinstance(changed, list)
        and all(isinstance(r, dict) and r.get("id") for r in base + changed)
    ):
        left, right = ({r["id"]: r for r in rows} for rows in (base, changed))
        return {
            "$records": _diff(left, right),
            "$order": [r["id"] for r in changed] if list(left) != list(right) else None,
        }
    return {"replace": deepcopy(changed)}


def _patch(base, delta, issues=None, path=""):
    if "replace" in delta:
        return deepcopy(delta["replace"])
    if "$records" in delta:
        rows = {r["id"]: r for r in base}
        for ident, change in delta["$records"].items():
            if change.get("delete"):
                rows.pop(ident, None)
            elif ident not in rows and "replace" not in change:
                if issues is not None:
                    issues.append(
                        {"id": ident, "path": path, "reason": "原记录消失，人工修订待重新定位"}
                    )
            else:
                rows[ident] = _patch(rows.get(ident, {}), change, issues, path + "/" + ident)
        order = delta.get("$order") or list(rows)
        return [rows[k] for k in order if k in rows] + [
            v for k, v in rows.items() if k not in order
        ]
    value = deepcopy(base)
    for key, change in delta.items():
        if change.get("delete"):
            value.pop(key, None)
        else:
            value[key] = _patch(value.get(key, {}), change, issues, path + "/" + key)
    return value


def _editable(bundle):
    return {k: deepcopy(bundle.get(k, [])) for k in EDITABLE}


def _baseline_report(bundle):
    from scene_completion.domain.current_scope import POLICY, case_report

    if bundle.get("analysis_policy", bundle.get("registry", {}).get("analysis_policy")) == POLICY:
        return case_report(bundle)
    return analyze(bundle)


def _store(project, bundle, baseline, revision, history, overrides, reason, previous=None):
    from scene_completion.application.result_projection import CASE_REPORT_VERSION
    from scene_completion.domain.current_scope import case_report

    report = case_report(bundle)
    item = {
        "revision": revision,
        "created_at": time.time(),
        "reason": reason,
        "metrics": report["metrics"],
    }
    history = [*history, item]
    original_report = _baseline_report(baseline)
    saved = {
        "bundle": bundle,
        "revision": revision,
        "case_report_version": CASE_REPORT_VERSION,
        **report,
        "original_metrics": original_report["metrics"],
        "original_metrics_by_level": original_report["metrics_by_level"],
        "history": history,
    }
    repository.store(
        project,
        bundle["case"]["id"],
        revision,
        saved,
        {
            "case": bundle["case"],
            "revision": revision,
            "baseline": baseline,
            "overrides": overrides,
            "history": history,
            "previous_baseline": previous,
        },
    )
    return saved


def publish(project, bundle):
    baseline = validate(bundle)
    cid = baseline["case"]["id"]
    with repository.locked(project):
        if not repository.exists(project, cid):
            return _store(project, baseline, baseline, 1, [], {}, "机器原始结果")
        state = repository.state(project, cid)
        if state["baseline"] == baseline:
            return editor(project, cid)
        issues = []
        effective = {**baseline, **_patch(_editable(baseline), state["overrides"], issues)}
        if "machine_g" in baseline:
            from scene_completion.workflow.ssd.generate.scenarios import (
                refresh_status,
                regenerate_machine,
            )

            machine_g = (
                deepcopy(baseline["machine_g"])
                if effective["steps"] == baseline["steps"]
                else regenerate_machine(effective, baseline)
            )
            effective["machine_g"] = machine_g
            effective["channels"]["G"] = _patch(
                machine_g, state["overrides"].get("channels", {}).get("G", {}), issues
            )
            refresh_status(effective)
        effective["revision_issues"] = issues
        previous = editor(project, cid)["bundle"]
        _invalidate(previous, effective)
        effective = validate(effective)
        _invalidate(previous, effective)
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


def editor(project, case_id, revision=None, *, compact=False):
    from scene_completion.application.result_projection import compact_editor, current_view

    if revision == "original":
        state = repository.state(project, case_id)
        baseline = state["baseline"]
        report = _baseline_report(baseline)
        view = {
            "bundle": baseline,
            "revision": "original",
            **report,
            "original_metrics": report["metrics"],
            "original_metrics_by_level": report["metrics_by_level"],
            "history": state["history"],
        }
        return compact_editor(view) if compact else view
    number = repository.head(project, case_id)["revision"] if revision is None else int(revision)
    view = repository.revision(project, case_id, number, isolate=not compact)
    if revision is None:
        from scene_completion.domain.ssd import matching

        return current_view(project, view, matching, compact=compact)
    return compact_editor(view) if compact else view


def review_view(project, case_id, revision):
    from scene_completion.application.result_projection import review_proof
    from scene_completion.domain.ssd import matching

    view = repository.revision(project, case_id, revision, isolate=False)
    statuses, proof = review_proof(project, view["bundle"], matching)
    return {
        "bundle": view["bundle"],
        "revision": view["revision"],
        "review_statuses": statuses,
        "identification_proof": proof,
    }


def review_catalog(project):
    from scene_completion.application.result_projection import CASE_REPORT_VERSION
    from scene_completion.domain.current_scope import filtered
    from scene_completion.domain.ssd.metrics import completeness

    for state in repository.heads(project):
        view = repository.revision(project, state["case"]["id"], state["revision"], isolate=False)
        progress = (
            view.get("completeness")
            if view.get("case_report_version") == CASE_REPORT_VERSION
            else completeness(filtered(view["bundle"], isolate=False))
        )
        yield {**state["case"], "revision": state["revision"], "completeness": progress}


def _invalidate(previous, bundle):
    changed = set()
    for channel in ("G", "E", "GT"):
        for kind in ("concerns", "scenarios"):
            old = {r["id"]: r for r in previous["channels"][channel][kind]}
            new = {r["id"]: r for r in bundle["channels"][channel][kind]}
            for ident in old.keys() | new.keys():
                if old.get(ident) != new.get(ident):
                    changed.add((channel, ident))
    old_decisions = {d["id"]: d for d in previous.get("decisions", [])}
    kept = []
    for d in bundle.get("decisions", []):
        a, b = PAIRS[d["pair"]]
        if ((a, d["left_id"]) in changed or (b, d["right_id"]) in changed) and (
            old_decisions.get(d["id"]) == d
        ):
            continue
        kind = "concerns" if d["level"] == "concern" else "scenarios"
        if d["left_id"] in {r["id"] for r in bundle["channels"][a][kind]} and (
            d["right_id"] in {r["id"] for r in bundle["channels"][b][kind]}
        ):
            kept.append(d)
    bundle["decisions"] = kept


def _promote_pending(bundle):
    """An explicit human confirmation promotes a pending source into both levels."""
    for channel in ("G", "E", "GT"):
        records = bundle["channels"][channel]
        pending = []
        for row in records.get("pending", []):
            if row.get("status") != "active":
                pending.append(row)
                continue
            if not all(row.get(k) for k in ("step_id", "target", "key", "condition", "expected")):
                raise ValueError("确认异常前请补充步骤、对象、关注点、失败条件和预期结果")
            concern = next((r for r in records["concerns"] if binding(r) == binding(row)), None)
            if concern is None:
                concern = {
                    **deepcopy(row),
                    "id": "manual-concern-" + fingerprint(binding(row))[:20],
                    "label": row.get("label", row["key"]),
                    "origin": "manual",
                }
                records["concerns"].append(concern)
            else:
                concern["status"] = "active"
            scenario = {**deepcopy(row), "concern_ids": [concern["id"]], "origin": "manual"}
            if not any(s["id"] == scenario["id"] for s in records["scenarios"]):
                records["scenarios"].append(scenario)
        records["pending"] = pending


def save_revision(project, case_id, body):
    with repository.locked(project):
        state = repository.state(project, case_id)
        if body.get("base_revision") != state["revision"]:
            raise RevisionConflict(state["revision"])
        current = editor(project, case_id)["bundle"]
        submitted = body.get("bundle")
        if not isinstance(submitted, dict):
            raise ValueError("请提交完整的可编辑用例结果")
        for key in ("case", "version", "documents"):
            if submitted.get(key) != current.get(key):
                raise ValueError("不可改写用例身份、版本或原始文档")
        updated = {**current, **_editable(submitted)}
        updated["coverage_policy"] = "coverage-any-confirmed-v2"
        _promote_pending(updated)
        if current["steps"] != updated["steps"]:
            from scene_completion.workflow.ssd.generate.fixed import generate_g
            from scene_completion.workflow.ssd.shared.step_bindings import rebind_steps

            updated = rebind_steps(current, updated)

            remaining = {s["id"] for s in updated["steps"]}
            removed = {s["id"] for s in current["steps"]} - remaining
            for step in updated["steps"]:
                if step.get("parent_id") in removed:
                    step["orphaned_parent_id"] = step.pop("parent_id")
                    step["binding_issue"] = "请求步骤已删除，请重新选择配对请求"
                if set(step.get("validates", [])) & removed:
                    step["orphaned_validates"] = [s for s in step["validates"] if s in removed]
                    step["validates"] = [s for s in step["validates"] if s not in removed]
                if step.get("parent_id") in remaining and step.get("orphaned_parent_id"):
                    step.pop("orphaned_parent_id", None)
                    step.pop("binding_issue", None)
            # Regenerate only the changed-step policy output, then retain G human differences.
            before_g = current.get("machine_g", generate_g(current))
            if "machine_g" in current:
                from scene_completion.workflow.ssd.generate.scenarios import regenerate_machine

                after_g = regenerate_machine(updated, current)
                updated["machine_g"] = deepcopy(after_g)
            else:
                after_g = generate_g(updated)
            delta_g = _diff(before_g, updated["channels"]["G"])
            updated["channels"]["G"] = _patch(after_g, delta_g)
            fields = {s["id"]: {f["id"] for f in s.get("data", [])} for s in updated["steps"]}
            for kind in ("concerns", "scenarios"):
                kept = {r["id"] for r in updated["channels"]["G"][kind]}
                for row in current["channels"]["G"][kind]:
                    if row["id"] not in kept and (
                        row.get("step_id") not in fields
                        or (row.get("field_id") and row["field_id"] not in fields[row["step_id"]])
                    ):
                        updated["channels"]["G"][kind].append(
                            {
                                **deepcopy(row),
                                "status": "unbound",
                                "binding_issue": "步骤或字段已删除",
                            }
                        )
        if "machine_g" in updated:
            from scene_completion.workflow.ssd.generate.scenarios import refresh_status

            # A reviewer-authored analysis is not a stale model result.
            old_g = {r["id"]: r for r in current["channels"]["G"]["scenarios"]}
            for row in updated["channels"]["G"]["scenarios"]:
                if row.get("analysis") and row.get("analysis") != old_g.get(row["id"], {}).get(
                    "analysis"
                ):
                    row["analysis_origin"] = "manual"
            refresh_status(updated)
        _invalidate(current, updated)
        updated = validate(updated)
        _invalidate(current, updated)
        if _editable(current) == _editable(updated):
            return editor(project, case_id)
        overrides = _diff(_editable(state["baseline"]), _editable(updated))
        if "machine_g" in updated:
            overrides.setdefault("channels", {})["G"] = _diff(
                updated["machine_g"], updated["channels"]["G"]
            )
        return _store(
            project,
            updated,
            state["baseline"],
            state["revision"] + 1,
            state["history"],
            overrides,
            str(body.get("reason") or "人工修正"),
        )


@cached_index("ssd_results")
def index(project):
    from scene_completion.application.result_projection import stored_case_report

    cases = []
    for state in repository.heads(project):
        cid = state["case"]["id"]
        result = repository.revision(project, cid, state["revision"], isolate=False)
        report = {**result, **stored_case_report(project, result)}
        progress = report["completeness"]
        pending = sum(v for k, v in progress.items() if k != "complete")
        cases.append(
            {
                **state["case"],
                "revision": result["revision"],
                "metrics": report["metrics"],
                "metrics_by_level": report["metrics_by_level"],
                "original_metrics_by_level": result["original_metrics_by_level"]
                if "original_metrics_by_level" in result
                else analyze(repository.state(project, cid)["baseline"])["metrics_by_level"],
                "pending_count": pending,
                "completeness": progress,
            }
        )
    metrics = {
        key: _rate(
            sum(c["metrics"][key]["numerator"] for c in cases),
            sum(c["metrics"][key]["denominator"] for c in cases),
        )
        for key in ("missing_exception_miss_rate", "generation_validity")
    }
    levels = {
        name: {
            level: {
                key: _rate(
                    sum(c[name][level][key]["numerator"] for c in cases),
                    sum(c[name][level][key]["denominator"] for c in cases),
                )
                for key in metrics
            }
            for level in ("concern", "scenario")
        }
        for name in ("metrics_by_level", "original_metrics_by_level")
    }
    return {"version": VERSION, "cases": cases, "metrics": metrics, **levels}


def enrich_effective(project, case_id, base_revision, generated):
    """Save analyses of manually edited SSD context without treating them as human overrides."""
    from scene_completion.workflow.ssd.generate.scenarios import refresh_status

    with repository.locked(project):
        state = repository.state(project, case_id)
        if base_revision != state["revision"]:
            raise RevisionConflict(state["revision"])
        current = editor(project, case_id)["bundle"]
        updated = deepcopy(current)
        delta = _diff(current["machine_g"], current["channels"]["G"])
        updated["machine_g"] = deepcopy(generated["channels"]["G"])
        updated["channels"]["G"] = _patch(updated["machine_g"], delta)
        refresh_status(updated)
        _invalidate(current, updated)
        updated = validate(updated)
        overrides = _diff(_editable(state["baseline"]), _editable(updated))
        overrides.setdefault("channels", {})["G"] = delta
        return _store(
            project,
            updated,
            state["baseline"],
            state["revision"] + 1,
            state["history"],
            overrides,
            "重新分析已修订步骤的场景；保留人工修正",
        )
