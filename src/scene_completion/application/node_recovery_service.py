"""Shared local/HTTP rerun entry; keep submitted repair bindings intact."""

from scene_completion.infrastructure.storage import read_json
from scene_completion.infrastructure.worker_runtime import pid_alive, read_job
from scene_completion.workflow.recovery.node_repair import repair_revision


def rerun(service, rid, body):
    project = service.run_dir(rid)
    job = read_job(project)
    if rid in service.active or (
        job.get("status") == "running" and job.get("pid") and pid_alive(job["pid"])
    ):
        raise ValueError("worker仍在运行，请等待执行轮结束后重跑")
    key = body["task_key"]
    store = service.conversation(rid, key)
    if store.pending(key):
        raise ValueError("请先回答当前问题")
    state_file = project / "run/workflow_tasks.json"
    state = read_json(state_file).get("tasks", {}).get(key, {}) if state_file.exists() else {}
    failure = state.get("failure") or {}
    repair_ready = repair_revision(project / "run", key) and state.get("status") != "passed"
    if body.get("text"):
        store.append(key, "guidance", body["text"])
        store.invalidate(key)
    elif not repair_ready:
        from scene_completion.infrastructure.code_retry import request

        request(project / "run", key, failure)
    return service.start(rid)
