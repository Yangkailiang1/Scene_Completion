"""Prepare local terminal-agent diagnostics; never launch an agent or spend tokens."""

from pathlib import Path

from scene_completion.infrastructure.storage import fingerprint, read_json, write_json


def prepare_handoff(project, *, write=True):
    project = Path(project)
    root = project / "run"
    job = read_json(project / "job.json") if (project / "job.json").exists() else {}
    state = (
        read_json(root / "workflow_tasks.json") if (root / "workflow_tasks.json").exists() else {}
    )
    tasks = state.get("tasks", {})
    nodes = []
    crashed = job.get("status") in {"error", "interrupted"}
    if crashed and (root / "execution_events.sqlite3").exists():
        # A worker may die between the durable started event and scheduler state save.
        import json

        from scene_completion.infrastructure.execution_events import EventStore

        latest = {}
        with EventStore(root).connect() as db:
            for key, payload in db.execute(
                "SELECT task_key,payload FROM events WHERE kind='task_status' ORDER BY id"
            ):
                latest[key] = json.loads(payload)
        for key, event in latest.items():
            if key and event["data"].get("status") in {"started", "repairing", "running"}:
                tasks[key] = {**tasks.get(key, {}), "status": "running", "interrupted_event": event}
    for key, row in tasks.items():
        if row.get("status") in {"passed", "blocked_dependency"} or (
            row.get("status") == "running" and not crashed
        ):
            continue
        failure = row.get("failure") or (
            {"type": "WorkerExited", "error": job.get("message", "worker exited")}
            if crashed and row.get("status") == "running"
            else {}
        )
        text = str(failure).lower()
        category = (
            "needs_user"
            if any(
                k in text
                for k in ("budget", "quota", "unknown_usage", "usage_unresolved", "awaiting_answer")
            )
            or row.get("status") == "awaiting_answer"
            else "code_failure"
            if failure.get("traceback")
            or row.get("status") == "failed"
            or failure.get("type") == "WorkerExited"
            else "model_result"
            if any(p.get("node_key") == key for p in _packets(root))
            else "code_failure"
        )
        from scene_completion.workflow.recovery.node_repair import batch_inventory

        nodes.append(
            {
                "node": key,
                "stage": row.get("stage"),
                "status": row.get("status"),
                "identity": row.get("identity"),
                "category": category,
                "failure": failure,
                "interrupted_event": row.get("interrupted_event"),
                "batches": batch_inventory(root, key),
                "reproduce": {
                    "command": "run --wait",
                    "node": key,
                    "data_dir": str(project.parent),
                },
            }
        )
    report = {
        "version": "code-agent-handoff-v1",
        "project": project.name,
        "state": "needs_user"
        if any(n["category"] == "needs_user" for n in nodes)
        else "needs_agent"
        if nodes or crashed
        else "complete",
        "nodes": nodes,
        "job": {k: job[k] for k in ("status", "error_type", "message", "exit_code") if k in job},
        "run_options": job.get("run_options", {}),
        "diagnostic_files": [
            str(p.relative_to(project))
            for p in (
                project / "error.log",
                root / "worker.log",
                root / "workflow_tasks.json",
                root / "run_manifest.json",
            )
            if p.exists()
        ],
        "instructions": "通过scene.py --local --data-dir DATA操作；诊断→repair-export --node NODE --batch BATCH→独立上下文修复payload→repair-submit --validate-only→提交→run --wait。脚本故障修源码并检查后恢复，不能伪造正式产物。G/E/GT按节点材料隔离；额度或未决用量由用户处理。",
    }
    report["identity"] = fingerprint(report)
    if write and report["state"] != "complete":
        destination = root / "code_agent_handoff" / (report["identity"] + ".json")
        write_json(destination, report)
        write_json(root / "code_agent_handoff/current.json", report)
        report["file"] = str(destination.relative_to(project))
    elif write and (root / "code_agent_handoff/current.json").exists():
        write_json(root / "code_agent_handoff/current.json", report)
    return report


def _packets(root):
    for file in (root / "packets").glob("*.json"):
        try:
            yield read_json(file)
        except (OSError, ValueError):
            continue
