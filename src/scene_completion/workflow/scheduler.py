"""Adapt the generic scheduler to Scene task records and workbench events."""

from pathlib import Path

from scene_completion.infrastructure.execution_events import EventStore, bind, phase
from scene_completion.infrastructure.storage import write_json
from scene_completion.models.request_admission import CallGate as CallGate
from scene_completion.workflow_core import Scheduler as CoreScheduler
from scene_completion.workflow_core import SchedulerHooks
from scene_completion.workflow_core import Task as Task
from scene_completion.workflow_core import TaskBlocked as TaskBlocked
from scene_completion.workflow_core import TaskRejected as TaskRejected
from scene_completion.workflow_core import run_lock as run_lock


class SceneSchedulerHooks(SchedulerHooks):
    def __init__(self, root, events):
        self.root = root
        self.events = events

    def task_registered(self, tasks, task):
        from scene_completion.infrastructure.execution_graph import expected_files
        from scene_completion.models.deepagents_client import role_for

        write_json(
            self.root / "workflow_graph.json",
            {
                "nodes": [
                    {
                        "id": t.key,
                        "case": t.case,
                        "stage": t.stage,
                        "role": role_for(t.stage),
                        "label": getattr(t, "display_label", None),
                        "deps": list(t.deps),
                        "expected_files": expected_files(t.key, t.case, t.stage),
                    }
                    for t in tasks.values()
                ]
            },
        )
        self.events.append("graph_updated", node_id=task.key)

    def status_changed(self, task, record, event):
        from scene_completion.models.deepagents_client import role_for

        self.events.append(
            "task_status",
            task_key=task.key,
            role=role_for(task.stage),
            case=task.case,
            attempt=record.get("rounds", 0) + 1,
            status=event,
            phase={"started": "preparing", "repairing": "preparing", "passed": "complete"}.get(
                event, event
            ),
            failure=record.get("failure"),
        )

    def execution_context(self, task, record):
        from scene_completion.models.deepagents_client import role_for

        return bind(
            self.events,
            task_key=task.key,
            role=role_for(task.stage),
            case=task.case,
            attempt=record["rounds"] + 1,
        )

    def phase(self, name):
        phase(name)

    def priority(self, task, priority_cases):
        shared = task.case == "shared"
        if shared and task.stage in {"source-index", "document-context"}:
            group = 0
        elif shared and task.stage in {
            "components",
            "api-map",
            "use-case-extract",
            "use-case-align",
            "existing-branches",
            "api-index",
        }:
            group = 1
        else:
            group = 2
        case = -1 if shared and priority_cases else super().priority(task, priority_cases)
        return group, case

    def dependency_value(self, value):
        return value.get("payload", value) if isinstance(value, dict) else value

    def keep_initial_failure(self, task, failure):
        return task.stage == "business-crud" and (
            failure.get("transport_failure") or failure.get("failure_category")
        )

    def before_save(self, task, value):
        from scene_completion.analysis.artifact_exports import export_task
        from scene_completion.infrastructure.execution_graph import artifact_folder

        if isinstance(value, dict) and "payload" in value and "task" in value:
            export_task(
                artifact_folder(self.root, task.key, task.case),
                task.stage,
                value["payload"],
                artifact_name=(
                    task.key if task.case == "shared" else task.key[len(task.case) + 1 :]
                ).replace(":", "--"),
            )

    def result_metadata(self, task, value):
        proof = value.get("metadata", {}).get("execution", {}) if isinstance(value, dict) else {}
        from scene_completion.inputs.artifact_imports import record_use

        record_use(self.root.parent, task.key, proof)
        origin = (
            "已有文件输入"
            if proof.get("provider")
            in {"colleague_import", "colleague_structure", "supplied_files"}
            else "恢复后生成"
            if proof.get("execution_model_evidence", {}).get("recovery")
            else "原流程生成"
        )
        import_sources = (
            [
                {
                    "file_id": proof["file_id"],
                    "name": proof.get("file_name", proof["file_id"]),
                    "revision": proof["revision"],
                }
            ]
            if proof.get("provider") == "colleague_import"
            else []
        )
        if proof.get("provider") == "colleague_structure":
            import_sources = proof.get("source_files", [])
        if proof.get("import_sources"):
            import_sources = proof["import_sources"]
            origin = "已有文件输入（补充合并）"
        if proof.get("input_sources"):
            import_sources = list(
                {x["file_id"]: x for x in import_sources + proof["input_sources"]}.values()
            )
            if origin == "原流程生成":
                origin = "已有文件输入（补充依据）"
        return {"import_sources": import_sources, "provenance": origin}

    def fault(self, task, record):
        from scene_completion.workflow.node_recovery import fault_package

        fault_package(self.root, task.key, record)


class Scheduler(CoreScheduler):
    def __init__(self, root, concurrency=1, auto_repair="bounded", max_rounds=2):
        self.events = EventStore(root)
        super().__init__(
            root,
            concurrency,
            auto_repair,
            max_rounds,
            hooks=SceneSchedulerHooks(Path(root), self.events),
        )
