"""Direct application-service transport for terminal agents without a web server."""

from urllib.parse import parse_qs, unquote, urlsplit

from scene_completion.application.project_service import Workbench
from scene_completion.infrastructure.storage import read_json, write_json
from scene_completion.infrastructure.worker_runtime import pid_alive, read_job


class LocalWorkbench:
    def __init__(self, root, env_file=None):
        self.service = Workbench(root, env_file=env_file)

    def call(self, path, body=None, method=None):
        body = body or {}
        parsed = urlsplit(path)
        parts = [unquote(p) for p in parsed.path.strip("/").split("/")]
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        service = self.service
        if parts == ["projects"]:
            return service.create(body) if body else service.list()
        if parts == ["projects", "from-input-bundle"]:
            from scene_completion.application.input_service import create_bundle

            return create_bundle(service, body)
        if len(parts) < 2 or parts[0] != "projects":
            raise ValueError("本地模式不支持此操作；请使用capabilities列出的本地命令")
        rid = parts[1]
        project = service.run_dir(rid)
        endpoint = "/".join(parts[2:])
        job = read_job(project)
        alive = job.get("status") == "running" and job.get("pid") and pid_alive(job["pid"])
        if endpoint == "config":
            if body:
                return service.configure(rid, body)
            from scene_completion.models.configuration.model_diagnostics import effective

            return effective(service.model_config(rid), query.get("task", "agent"))
        if endpoint == "prompts":
            from scene_completion.models.transport.request_context import view

            return view(project / "run", query["task_key"], query.get("request_id"))
        if endpoint == "ssd-results":
            from scene_completion.application.ssd_revision_service import index

            return index(project)
        if endpoint == "project-results":
            from scene_completion.application.shared_service_service import index

            return index(project)
        if endpoint.startswith("project-results/") and endpoint.endswith("/editor"):
            if parts[3] == "shared_services":
                from scene_completion.application.shared_service_service import editor

                return editor(project, parts[3], query.get("revision"))
            from scene_completion.application.project_scope_service import editor

            return editor(project, parts[3], query.get("revision"))
        if endpoint.startswith("results/") and endpoint.endswith("/editor"):
            from scene_completion.application.ssd_revision_service import editor

            return editor(project, parts[3], query.get("revision"))
        if endpoint == "execution-status":
            return service.execution_status(rid)
        if endpoint == "run":
            return service.start(rid, body)
        if endpoint == "execution-control":
            from scene_completion.application.execution_control import control

            return control(service, rid, body)
        if endpoint == "events/history":
            from scene_completion.infrastructure.execution_events import EventStore

            return {
                "events": EventStore(project / "run").read(
                    int(query.get("after", 0)),
                    task_key=query.get("task_key"),
                    limit=int(query.get("limit", 200)),
                )
            }
        if endpoint == "supplied-cases":
            return service.supplied_case_preview(rid, parse_qs(parsed.query).get("case", []))
        if endpoint == "diagnostics":
            from scene_completion.application.recovery_handoff import prepare_handoff
            from scene_completion.models.configuration.model_diagnostics import node_diagnostics

            return {
                **node_diagnostics(
                    project,
                    service.model_config(rid),
                    query.get("task_key"),
                    int(query.get("limit", 20)),
                ),
                "handoff": prepare_handoff(project, write=not alive),
            }
        if endpoint == "node-repair":
            from scene_completion.workflow.recovery.node_repair import export_repair, submit_repair
            from scene_completion.workflow_core import run_lock

            if method == "POST" or body:
                if alive:
                    raise ValueError("worker仍在运行，请等待结束后提交修复")
                with run_lock(project / "run"):
                    return submit_repair(
                        project,
                        body["task_key"],
                        body["repair"],
                        validate_only=body.get("validate_only", False),
                    )
            return export_repair(project, query["task_key"], batch=query.get("batch"))
        if endpoint == "rerun-node":
            from scene_completion.application.node_recovery_service import rerun

            return rerun(service, rid, body)
        if endpoint == "mode" and method == "PUT":
            if alive:
                raise ValueError("运行中不能切换模式")
            if body.get("review_mode") not in {"auto", "manual"}:
                raise ValueError("无效审核模式")
            meta = read_json(project / "project.json")
            meta["review_mode"] = body["review_mode"]
            write_json(project / "project.json", meta)
            return meta
        if not endpoint:
            return service.snapshot(rid)
        raise ValueError("本地模式不支持该入口：" + endpoint)
