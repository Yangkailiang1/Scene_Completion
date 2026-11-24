"""Register per-case shared external service aggregation."""

from scene_completion.workflow.semantics import component_version
from scene_completion.workflow.ssd_stages import MERGE_STAGE
from scene_completion.workflow.ssd_stages import label as stage_label
from scene_completion.workflow_core import Scheduler, Task


def _project_scopes(ex, selected):
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
            ex.scheduler.add(_task(ex.root, cid, deps=(cid + ":ssd-compare",)))
        ex.manifest["project_scope_tasks"].append(key)


def _task(root, cid, *, deps=(), upstream_hash=None):
    from scene_completion.application.shared_service_service import publish
    from scene_completion.domain.project_scopes.validation import validate
    from scene_completion.infrastructure.identity import fingerprint

    version = component_version("ssd-shared-services")
    return Task(
        key=cid + ":" + MERGE_STAGE,
        case=cid,
        stage=MERGE_STAGE,
        deps=deps,
        version=fingerprint([version, upstream_hash]) if upstream_hash else version,
        execute=lambda values, record: {
            "task": MERGE_STAGE,
            "payload": publish(root.parent)["bundle"],
        },
        verify=lambda value: validate(value["payload"]),
        display_label=stage_label(MERGE_STAGE),
    )


def retry_published(root, key):
    """Run only the merge, using the previously verified comparison and saved revisions."""
    from scene_completion.domain.ssd.validation import validate
    from scene_completion.infrastructure import ssd_repository
    from scene_completion.infrastructure.code_retry import revision
    from scene_completion.infrastructure.identity import fingerprint
    from scene_completion.infrastructure.storage import read_json, write_json
    from scene_completion.workflow.ssd.pipeline import update_report_manifest

    scheduler = Scheduler(root, auto_repair="off")
    records = scheduler.state["tasks"]
    graph = read_json(root / "workflow_graph.json")
    node = next((node for node in graph["nodes"] if node["id"] == key), None)
    if not node or node.get("stage") != MERGE_STAGE:
        raise ValueError("找不到共用外部服务汇总节点")
    cid = node["case"]
    compared = records.get(cid + ":ssd-compare", {})
    if compared.get("status") != "passed" or not ssd_repository.exists(root.parent, cid):
        raise ValueError("该用例没有已完成并发布的三方比较，请先恢复比较节点")
    saved = scheduler.store.load_output(compared)
    if saved["task"] != "ssd-compare" or validate(saved["payload"])["case"]["id"] != cid:
        raise ValueError("缓存的三方比较与当前用例不一致")
    identity = fingerprint([compared["output_hash"], revision(root, key)])
    scheduler.add(_task(root, cid, upstream_hash=identity))
    scheduler.run()
    manifest_path = root / "run_manifest.json"
    manifest = read_json(manifest_path)
    statuses = {
        entry["id"]: records.get(entry["id"], {}).get("status", "pending")
        for entry in graph["nodes"]
    }
    manifest["tasks"] = statuses
    update_report_manifest(
        root.parent, manifest, complete=all(status == "passed" for status in statuses.values())
    )
    write_json(manifest_path, manifest)
    return manifest
