"""Execution Routes."""

import json
import time

from fastapi import HTTPException, Query, Request

from scene_completion.infrastructure.paths import PROGRAM_ROOT

PROJECT = PROGRAM_ROOT
WEB = PROJECT / "web"


def register(app, service):
    @app.get("/api/projects/{rid}/supplied-cases")
    def supplied_cases(rid: str, case: list[str] | None = Query(default=None)):
        return service.supplied_case_preview(rid, case or [])

    @app.post("/api/projects/{rid}/run")
    def start(rid: str, body: dict | None = None):
        return service.start(rid, body)

    @app.post("/api/projects/{rid}/execution-control")
    def execution_control(rid: str, body: dict):
        from scene_completion.application.execution_control import control

        return control(service, rid, body)

    @app.get("/api/projects/{rid}/execution-status")
    def execution_status(rid: str):
        return service.execution_status(rid)

    @app.get("/api/projects/{rid}/graph")
    def graph(rid: str):
        from scene_completion.infrastructure.execution_graph import graph_snapshot

        return graph_snapshot(service.run_dir(rid) / "run")

    @app.get("/api/projects/{rid}/events/history")
    def history(rid: str, after: int = 0, task_key: str | None = None, limit: int = 500):
        from scene_completion.infrastructure.execution_events import EventStore

        return {
            "events": EventStore(service.run_dir(rid) / "run").read(
                after, task_key=task_key, limit=limit
            )
        }

    @app.get("/api/projects/{rid}/events")
    async def events(rid: str, request: Request, after: int = 0, tail: bool = False):
        import asyncio

        from fastapi.responses import StreamingResponse

        from scene_completion.infrastructure.execution_events import EventStore

        store = EventStore(service.run_dir(rid) / "run")
        try:
            cursor = max(after, int(request.headers.get("Last-Event-ID", "0")))
        except ValueError:
            raise HTTPException(400, "invalid event cursor")
        fresh_tail = tail and cursor == 0
        if fresh_tail:
            cursor = store.latest_id()

        async def stream():
            nonlocal cursor
            if fresh_tail:
                # Establish a resume cursor without replaying all model deltas.
                # Node history is loaded separately when a node is selected.
                yield (
                    "id: "
                    + str(cursor)
                    + "\nevent: cursor\ndata: "
                    + json.dumps({"id": cursor})
                    + "\n\n"
                )
            heartbeat = time.monotonic()
            while not await request.is_disconnected():
                rows = store.read(cursor)
                for row in rows:
                    cursor = row["id"]
                    yield (
                        "id: "
                        + str(cursor)
                        + "\nevent: execution\ndata: "
                        + json.dumps(row, ensure_ascii=False)
                        + "\n\n"
                    )
                if time.monotonic() - heartbeat > 10:
                    yield ": heartbeat\n\n"
                    heartbeat = time.monotonic()
                await asyncio.sleep(0.2)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
