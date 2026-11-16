"""Project-scope results and revision routes."""

from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response


def register(app, service):
    from scene_completion.application import project_scope_service as results
    from scene_completion.domain.project_scopes.validation import SCOPES
    from scene_completion.infrastructure import project_scope_repository as repository

    def require_scope(rid: str, scope: str):
        root = service.run_dir(rid)
        if scope not in SCOPES:
            raise HTTPException(404, detail={"message": "未知的项目分析范围", "scope": scope})
        if not repository.exists(root, scope):
            raise HTTPException(
                404,
                detail={
                    "message": "该分析范围尚无项目结果，请先运行流程",
                    "scope": scope,
                },
            )
        return root

    @app.get("/api/projects/{rid}/project-results")
    def index(rid: str):
        from scene_completion.application.shared_service_service import index

        return index(service.run_dir(rid))

    @app.get("/api/projects/{rid}/project-results/{scope}/editor")
    def editor(rid: str, scope: str, revision: str | None = None):
        if scope == "shared_services":
            from scene_completion.application.shared_service_service import editor

            return JSONResponse(editor(service.run_dir(rid), scope, revision))
        return JSONResponse(results.editor(require_scope(rid, scope), scope, revision))

    @app.get("/api/projects/{rid}/project-results/{scope}/revisions")
    def revisions(rid: str, scope: str):
        if scope == "shared_services":
            from scene_completion.application.shared_service_service import editor

            return {"history": editor(service.run_dir(rid))["history"]}
        return {"history": results.editor(require_scope(rid, scope), scope)["history"]}

    @app.post("/api/projects/{rid}/project-results/{scope}/revisions")
    def save(rid: str, scope: str, body: dict):
        try:
            if scope == "shared_services":
                from scene_completion.application.shared_service_service import save_revision

                return JSONResponse(save_revision(service.run_dir(rid), scope, body))
            raise HTTPException(
                400, detail="历史业务链路及架构结果只读，请使用当前交互和共用服务结果"
            )
        except results.RevisionConflict as error:
            raise HTTPException(
                409,
                detail={
                    "message": str(error),
                    "current_revision": error.current_revision,
                },
            ) from error

    @app.post("/api/projects/{rid}/project-review/export")
    def export_review(rid: str, body: dict):
        from scene_completion.application.project_scope_review import export_review

        root = service.run_dir(rid)
        try:
            return Response(
                export_review(root, body),
                media_type="text/html",
                headers={"Content-Disposition": 'attachment; filename="project-review.html"'},
            )
        except ValueError as error:
            raise HTTPException(400, detail={"message": str(error)}) from error

    @app.post("/api/projects/{rid}/project-review/preview")
    def preview_feedback(rid: str, body: dict):
        from scene_completion.application.project_scope_review import preview_feedback

        try:
            return preview_feedback(service.run_dir(rid), body.get("content"), adoption_only=True)
        except ValueError as error:
            raise HTTPException(400, detail={"message": str(error)}) from error

    @app.post("/api/projects/{rid}/project-review/apply")
    def apply_feedback(rid: str, body: dict):
        from scene_completion.application.project_scope_review import apply_feedback

        try:
            return apply_feedback(
                service.run_dir(rid), body.get("content"), body.get("scope"), adoption_only=True
            )
        except ValueError as error:
            raise HTTPException(400, detail={"message": str(error)}) from error
