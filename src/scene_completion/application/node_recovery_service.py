"""Shared local/HTTP rerun entry; keep submitted repair bindings intact."""

from scene_completion.infrastructure.storage import read_json
from scene_completion.infrastructure.worker_runtime import live_job, read_job
from scene_completion.workflow.recovery.node_repair import repair_revision
from scene_completion.workflow_core import run_lock


def _run_scope(project, key, state, job):
    previous = job.get("run_options")
    known = dict(previous) if isinstance(previous, dict) else {}
    graph_path = project / "run/workflow_graph.json"
    graph = read_json(graph_path).get("nodes", []) if graph_path.is_file() else []
    node = next((node for node in graph if node["id"] == key), None)
    if node is None and not state:
        raise ValueError("找不到需要重跑的节点")
    prefix, separator, _ = key.partition(":")
    case = (node or {}).get("case") or state.get("case") or (prefix if separator else None)
    shared = case in {None, "shared", "project"}
    # Older terminal job records did not retain run_options. Their current graph
    # is narrower evidence than the project-wide default.
    cases = known.get("case_ids")
    graph_cases = {item.get("case") for item in graph} - {None, "shared", "project"}
    if isinstance(cases, list) and (shared or not cases or case in cases):
        return known
    if shared:
        if not graph_cases:
            raise ValueError("无法确认共享节点的原运行范围，请先明确用例范围")
        selected = sorted(graph_cases)
    else:
        selected = [case]
    known["case_ids"] = selected
    if "priority_cases" in known:
        known["priority_cases"] = [
            case_id for case_id in known["priority_cases"] if case_id in selected
        ]
    return known


def rerun(service, rid, body):
    project = service.run_dir(rid)
    with run_lock(project / "dispatch"):
        return _rerun_locked(service, rid, body, project)


def _rerun_locked(service, rid, body, project):
    job = read_job(project)
    if rid in service.active or live_job(job):
        raise ValueError("worker仍在运行，请等待执行轮结束后重跑")
    key = body["task_key"]
    store = service.conversation(rid, key)
    if store.pending(key):
        raise ValueError("请先回答当前问题")
    state_file = project / "run/workflow_tasks.json"
    state = read_json(state_file).get("tasks", {}).get(key, {}) if state_file.exists() else {}
    options = _run_scope(project, key, state, job)
    failure = state.get("failure") or {}
    repair_ready = repair_revision(project / "run", key) and state.get("status") != "passed"
    if body.get("text"):
        store.append(key, "guidance", body["text"])
        store.invalidate(key)
    elif not repair_ready:
        from scene_completion.infrastructure.code_retry import request

        request(project / "run", key, failure)
    if key.endswith(":shared-services-merge") and not body.get("text"):
        return service._start(rid, options, shared_service_retry=key)
    return service._start(rid, options)
