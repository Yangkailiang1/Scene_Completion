"""Read-only current-result explanations; frozen snapshots and model decisions stay intact."""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from scene_completion.domain.coverage import review_statuses
from scene_completion.infrastructure.result_cache import read_snapshot
from scene_completion.infrastructure.storage import read_json


def identification_proof(project, bundle):
    if "gt_identification_run_complete" in bundle:
        return bundle["gt_identification_run_complete"], "结果中的执行标记"
    scope = bundle.get("scope", {}).get("id")
    if not scope:
        return None, None
    path = Path(project) / "run/artifacts/shared" / f"project--{scope}--project-identify.json"
    if not path.is_file():
        return None, None
    try:
        value = read_json(path).get("payload", {})
    except (OSError, ValueError):
        return None, None
    # Bind legacy completion proof to the same source inputs and structural anchors.
    if (
        value.get("version") == bundle.get("version")
        and value.get("scope") == bundle.get("scope")
        and value.get("anchors") == bundle.get("anchors")
        and value.get("documents") == bundle.get("documents")
        and value.get("source_records") is not None
        and value.get("source_records") == bundle.get("source_records")
        and value.get("gt_identification_run_complete") is True
    ):
        return True, str(path.relative_to(project))
    return None, None


CASE_REPORT_VERSION = "current-case-report-v1"


@lru_cache(maxsize=12)
def _project_saved_case(path, identity):
    from scene_completion.domain.current_scope import case_report

    return case_report(read_snapshot(path, isolate=False)["bundle"])


def stored_case_report(project, view, *, isolate=False):
    from scene_completion.infrastructure.ssd_repository import revision_path

    keys = ("metrics", "metrics_by_level", "comparison", "completeness", "scenario_diagnostic")
    if view.get("case_report_version") == CASE_REPORT_VERSION and all(key in view for key in keys):
        return {}
    path = revision_path(project, view["bundle"]["case"]["id"], view["revision"])
    stat = path.stat()
    report = _project_saved_case(path, (stat.st_mtime_ns, stat.st_size, stat.st_ino))
    return deepcopy(report) if isolate else report


def review_proof(project, bundle, matching):
    complete, proof = identification_proof(project, bundle)
    if complete is None and bundle.get("scope") and bundle.get("source_records", {}).get("GT"):
        complete = False
    if complete is not None:
        bundle = {**bundle, "gt_identification_run_complete": complete}
    return review_statuses(bundle, matching), {"complete": complete, "source": proof}


def current_view(project, view, matching, *, compact=False):
    local = view["bundle"]
    if local.get("version") == "ssd-case-v1":
        view = {**view, **stored_case_report(project, view, isolate=not compact)}
        from scene_completion.domain.current_scope import allowed

        view["scope_excluded_ids"] = [
            r["id"]
            for data in local["channels"].values()
            for kind in ("concerns", "scenarios", "pending")
            for r in data.get(kind, [])
            if not allowed(r)
        ]
    statuses, proof = review_proof(project, local, matching)
    view["review_statuses"] = statuses
    view["identification_proof"] = proof
    scenarios = []
    for source in view["comparison"]["scenarios"]:
        row = source.copy()
        coverage = {}
        for record in row["cells"]["G"]:
            status = statuses.get(record["id"])
            if status:
                coverage[record["id"]] = deepcopy(status)
        row["coverage_by_record"] = coverage
        if any(s["covered"] for s in coverage.values()):
            row["reason"] = "已确认GT覆盖；关联记录可能位于其他表格行，见覆盖依据"
            if row["status"] == "single":
                row["status"] = "partial"
        scenarios.append(row)
    view["comparison"] = {**view["comparison"], "scenarios": scenarios}
    return compact_editor(view) if compact else view


def compact_editor(view):
    """The browser resolves comparison cells from the editable records by ID."""
    return {
        **view,
        "bundle": {k: v for k, v in view["bundle"].items() if k != "machine_g"},
        "comparison": {
            kind: [
                {
                    **row,
                    "cells": {
                        c: [{"id": r["id"]} for r in records] for c, records in row["cells"].items()
                    },
                }
                for row in rows
            ]
            for kind, rows in view["comparison"].items()
        },
    }
