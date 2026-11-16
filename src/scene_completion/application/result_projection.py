"""Read-only current-result explanations; frozen snapshots and model decisions stay intact."""

from copy import deepcopy
from pathlib import Path

from scene_completion.domain.coverage import review_statuses
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


def current_view(project, view, matching):
    local = view["bundle"]
    if local.get("version") == "ssd-case-v1":
        from scene_completion.domain.current_scope import case_report

        view.update(case_report(local))
        from scene_completion.domain.current_scope import allowed

        view["scope_excluded_ids"] = [
            r["id"]
            for data in local["channels"].values()
            for kind in ("concerns", "scenarios", "pending")
            for r in data.get(kind, [])
            if not allowed(r)
        ]
    complete, proof = identification_proof(project, local)
    if complete is None and local.get("scope") and local.get("source_records", {}).get("GT"):
        complete = False
    if complete is not None:
        local = {**local, "gt_identification_run_complete": complete}
    statuses = review_statuses(local, matching)
    view["review_statuses"] = statuses
    view["identification_proof"] = {"complete": complete, "source": proof}
    for row in view["comparison"]["scenarios"]:
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
    return view
