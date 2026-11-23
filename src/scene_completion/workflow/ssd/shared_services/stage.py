"""Register per-case shared external service aggregation."""

from scene_completion.workflow.semantics import component_version
from scene_completion.workflow.ssd_stages import MERGE_STAGE
from scene_completion.workflow.ssd_stages import label as stage_label
from scene_completion.workflow_core import Task


def _project_scopes(ex, selected):
    from scene_completion.application.shared_service_service import publish
    from scene_completion.domain.project_scopes.validation import validate

    ex.manifest["project_scopes"] = []
    ex.manifest["analysis_policy"] = "interaction-shared-services-v1"
    ex.manifest["project_scope_tasks"] = []
    for cid in selected:
        key = cid + ":shared-services-merge"
        if getattr(ex, "is_preview", False):
            ex.add(
                key,
                MERGE_STAGE,
                [cid + ":ssd-compare"],
                case=cid,
                transform=lambda d: d,
            )
        else:
            ex.scheduler.add(
                Task(
                    key=key,
                    case=cid,
                    stage=MERGE_STAGE,
                    deps=(cid + ":ssd-compare",),
                    version=component_version("ssd-shared-services"),
                    execute=lambda values, record: {
                        "task": "shared-services-merge",
                        "payload": publish(ex.root.parent)["bundle"],
                    },
                    verify=lambda value: validate(value["payload"]),
                    display_label=stage_label(MERGE_STAGE),
                )
            )
        ex.manifest["project_scope_tasks"].append(key)
