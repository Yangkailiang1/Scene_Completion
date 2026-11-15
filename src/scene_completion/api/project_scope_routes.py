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

    def body_scope(body: dict):
        scope = body.get("scope")
        if scope not in SCOPES:
            raise HTTPException(400, detail={"message": "请指定有效的项目分析范围"})
        return scope

    @app.get("/api/projects/{rid}/project-results")
    def index(rid: str):
        return results.index(service.run_dir(rid))

    @app.get("/api/projects/{rid}/project-results/{scope}/editor")
    def editor(rid: str, scope: str, revision: str | None = None):
        return JSONResponse(results.editor(require_scope(rid, scope), scope, revision))

    @app.get("/api/projects/{rid}/project-results/{scope}/revisions")
    def revisions(rid: str, scope: str):
        return {"history": results.editor(require_scope(rid, scope), scope)["history"]}

    @app.post("/api/projects/{rid}/project-results/{scope}/revisions")
    def save(rid: str, scope: str, body: dict):
        try:
            results.save_revision(require_scope(rid, scope), scope, body)
            return JSONResponse(results.editor(service.run_dir(rid), scope))
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

        root = require_scope(rid, body_scope(body))
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
