"""HTTP parameter and response adapters for project input services."""

import scene_completion.inputs.imports.artifact_imports as artifacts
from scene_completion.application import input_service
from scene_completion.application.input_service import watch_settings


def register(app, service):

    @app.post("/api/input-bundles/preview")
    def bundle_preview(body: dict):
        from scene_completion.inputs.documents.input_bundles import discover

        return discover(
            directory=body.get("directory"), paths=body.get("paths"), files=body.get("files")
        )[0]

    @app.post("/api/projects/from-input-bundle")
    def create_bundle(body: dict):
        return input_service.create_bundle(service, body)

    @app.post("/api/projects/{rid}/input-bundles")
    def bundle_import(rid: str, body: dict):
        return input_service.bundle_import(service, rid, body)

    @app.get("/api/projects/{rid}/imports")
    def imports(rid: str, item: str | None = None):
        return artifacts.view(service.run_dir(rid), item)

    @app.get("/api/projects/{rid}/import-plan")
    def import_plan(rid: str):
        from scene_completion.application.import_plan import build

        return build(service.run_dir(rid)) or {
            "nodes": [],
            "edges": [],
            "files": [],
            "preview_only": True,
            "summary": {},
            "roles": [],
            "definition_available": False,
            "case_expansion_pending": True,
        }

    @app.post("/api/projects/{rid}/imports")
    def upload(rid: str, body: dict):
        p = service.run_dir(rid)
        result = artifacts.receive(p, body.get("files", []))
        if service.input_watcher:
            service.input_watcher.convert_pending(p)
        return result

    @app.put("/api/projects/{rid}/imports/{iid}")
    def decide(rid: str, iid: str, body: dict):
        return input_service.decide(service, rid, iid, body)

    @app.post("/api/projects/{rid}/input-scan")
    def input_scan(rid: str, body: dict):
        return input_service.input_scan(service, rid, body)

    @app.get("/api/projects/{rid}/input-scan")
    def input_settings(rid: str):
        return watch_settings(service.run_dir(rid))

    @app.get("/api/projects/{rid}/recovery")
    def recovery(rid: str):
        from scene_completion.workflow.recovery.node_recovery import records, settings

        p = service.run_dir(rid)
        return {**settings(p), "ledger": records(p)}

    @app.put("/api/projects/{rid}/recovery")
    def recovery_update(rid: str, body: dict):
        from scene_completion.workflow.recovery.node_recovery import settings

        p = service.run_dir(rid)
        input_service.idle(service, p)
        return settings(p, body)
