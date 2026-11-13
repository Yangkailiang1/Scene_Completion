"""Local review application: Markdown sources, persisted artifacts and two run modes."""

import json

from scene_completion.api import execution_routes, project_routes, result_routes
from scene_completion.application.project_service import Workbench as Workbench
from scene_completion.infrastructure.paths import PROGRAM_ROOT

PROJECT = PROGRAM_ROOT
WEB = PROJECT / "web"


def create_app(root=None, client_factory=None, env_file=None):
    from fastapi import FastAPI, Request
    from fastapi.responses import Response
    from fastapi.staticfiles import StaticFiles

    service = Workbench(root or PROJECT / ".workbench", client_factory, env_file)
    app = FastAPI(title="场景完整性审核")
    app.state.workbench = service
    project_routes.register(app, service)
    execution_routes.register(app, service)
    result_routes.register(app, service)

    @app.middleware("http")
    async def local_write(request: Request, call_next):
        if service.review_only and request.method not in {"GET", "HEAD", "OPTIONS"}:
            import re

            allowed = re.fullmatch(
                r"/api/projects/[a-f0-9]{32}/(?:pending/[a-f0-9]+|recommendations/feedback|analysis-scopes)",
                request.url.path,
            )
            if not allowed and request.url.path != "/api/runtime/control":
                return Response(
                    json.dumps(
                        {"detail": "业务审核模式禁止模型执行和配置变更；请导出反馈交回研发"},
                        ensure_ascii=False,
                    ),
                    status_code=403,
                    media_type="application/json",
                )
        # Local UI writes are same-origin; cross-site forms must not start model jobs.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return Response("Origin mismatch", status_code=403)
        try:
            import re
            from contextlib import nullcontext

            from scene_completion.domain.concern_registry import registry_scope
            from scene_completion.review.decisions.project_review import project_registry

            match = re.match(r"/api/projects/([a-f0-9]{32})(?:/|$)", request.url.path)
            scope = (
                registry_scope(project_registry(service.run_dir(match[1])))
                if match
                else nullcontext()
            )
            with scope:
                return await call_next(request)
        except ValueError as e:
            return Response(
                json.dumps(
                    {
                        "detail": str(e),
                        **(
                            {"import_preview": e.import_preview}
                            if hasattr(e, "import_preview")
                            else {}
                        ),
                    },
                    ensure_ascii=False,
                ),
                status_code=400,
                media_type="application/json",
            )

    if (WEB / "assets").exists():
        app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")
    app.mount("/static", StaticFiles(directory=WEB), name="static")
    from scene_completion.manager.manager_api import register as register_manager

    register_manager(app, service)
    from scene_completion.manager.quality_api import register as register_quality

    register_quality(app, service)
    from scene_completion.review.handoff.review_api import register

    register(app, service, PROJECT)
    from scene_completion.api.inputs import register as register_inputs
    from scene_completion.application.input_service import InputWatcher

    register_inputs(app, service)

    @app.on_event("startup")
    def start_input_watcher():
        if not service.review_only and not service.worker:
            from scene_completion.infrastructure.worker_runtime import Guardian

            service.input_watcher = InputWatcher(service)
            service.guardian = Guardian(service)
            from scene_completion.manager.manager_runtime import ManagerHost

            service.manager_host = ManagerHost(service)
            from scene_completion.manager.quality_runtime import QualityHost

            service.quality_host = QualityHost(service)

    @app.on_event("shutdown")
    def stop_input_watcher():
        if service.input_watcher:
            service.input_watcher.close()
        if service.guardian:
            service.guardian.close()
        if service.manager_host:
            service.manager_host.close()
        if getattr(service, "quality_host", None):
            service.quality_host.close()

    return app
