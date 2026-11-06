"""Result Routes."""

import json

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from scene_completion.infrastructure.paths import PROGRAM_ROOT
from scene_completion.infrastructure.storage import read_json, write_json

PROJECT = PROGRAM_ROOT
WEB = PROJECT / "web"


def register(app, service):
    @app.get("/api/projects/{rid}/analysis-scopes")
    def analysis_scopes(rid: str):
        from scene_completion.review.scope_reviews import view

        return view(service.run_dir(rid))

    @app.put("/api/projects/{rid}/analysis-scopes")
    def update_analysis_scopes(rid: str, body: dict):
        from scene_completion.review.scope_reviews import save

        return save(service.run_dir(rid), body)

    @app.get("/api/projects/{rid}/results")
    def results_index(rid: str, include_artifacts: bool = True):
        from scene_completion.analysis.result_views import ResultView

        return ResultView(service.run_dir(rid)).index(include_artifacts=include_artifacts)

    @app.get("/api/projects/{rid}/results/metrics")
    def results_metrics(rid: str, test_set: str = "expanded", scope: str | None = None):
        from scene_completion.analysis.result_views import ResultView

        return ResultView(service.run_dir(rid), evaluation_scope=scope).metrics(test_set)

    @app.get("/api/projects/{rid}/results/global")
    def results_global(rid: str, test_set: str = "original"):
        from scene_completion.analysis.result_views import ResultView

        return ResultView(service.run_dir(rid)).global_detail(test_set)

    @app.get("/api/projects/{rid}/results/project-metrics")
    def results_project_metrics(rid: str, test_set: str = "original", scope: str | None = None):
        from scene_completion.analysis.result_views import ResultView

        return ResultView(service.run_dir(rid), evaluation_scope=scope).project_metrics(test_set)

    @app.get("/api/projects/{rid}/results/{case_id}")
    def results_case(rid: str, case_id: str, test_set: str = "expanded", scope: str | None = None):
        from scene_completion.analysis.result_views import ResultView

        return ResultView(service.run_dir(rid), evaluation_scope=scope).detail(case_id, test_set)

    @app.get("/api/projects/{rid}/results/{case_id}/scenarios/{channel}/{scenario_id}")
    def result_scenario(
        rid: str, case_id: str, channel: str, scenario_id: str, test_set: str = "expanded"
    ):
        from scene_completion.analysis.result_views import ResultView

        return ResultView(service.run_dir(rid)).scenario(case_id, channel, scenario_id, test_set)

    @app.get("/api/projects/{rid}/usage")
    def usage(
        rid: str,
        format: str = "json",
        view: str = "summary",
        task_key: str | None = None,
        role: str | None = None,
        model: str | None = None,
        case: str | None = None,
        search: str = "",
        offset: int = 0,
        limit: int = 50,
        after: float | None = None,
        session_id: str | None = None,
        account: str | None = None,
        sort: str = "tokens",
    ):
        from scene_completion.models.usage_index import indexed_usage, usage_csv

        project = service.run_dir(rid)
        prices = (
            read_json(project / "usage_prices.json")
            if (project / "usage_prices.json").exists()
            else {}
        )
        report = indexed_usage(
            project / "run",
            view="export" if format in {"csv", "download"} else view,
            task_key=task_key,
            role=role,
            model=model,
            case=case,
            search=search,
            offset=offset,
            limit=limit,
            after=after,
            prices=prices,
            session_id=session_id,
            account=account,
            sort=sort,
        )
        if format == "csv":
            return Response(
                usage_csv(report),
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="task-usage.csv"'},
            )
        if format not in {"json", "download"}:
            raise ValueError(
                "usage format must be json, download or csv; use the embedded workbench view"
            )
        return Response(json.dumps(report, ensure_ascii=False), media_type="application/json")

    @app.put("/api/projects/{rid}/usage/prices")
    def usage_prices(rid: str, body: dict):
        import math

        project = service.run_dir(rid)
        prices = {}
        for model, price in body.items():
            if (
                not isinstance(model, str)
                or not model.strip()
                or not isinstance(price, dict)
                or set(price) - {"input", "cached_input", "output"}
                or not {"input", "output"} <= set(price)
            ):
                raise ValueError("按模型填写每百万Token输入/输出单价，币种为人民币")
            if any(
                type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in price.values()
            ):
                raise ValueError("单价必须是非负有限数值")
            prices[model] = price
        write_json(project / "usage_prices.json", prices)
        return {
            "prices": prices,
            "currency": "CNY",
            "unit": "每百万Token",
            "status": "仅用于估算，不是实际账单",
        }

    @app.get("/api/projects/{rid}/file")
    def file(rid: str, path: str):
        p = service.run_dir(rid)
        f = (p / path).resolve()
        if not f.is_relative_to(p) or not f.is_file() or f.name.endswith((".local.json", ".lock")):
            raise HTTPException(404, "file unavailable")
        if not (
            path.startswith("run/artifacts/")
            or path.startswith("run/reviews/previews/")
            or path.startswith("run/report_versions/")
            or path.startswith("sources/")
            or path.startswith("imports/files/")
            and ("/original/" in path or not f.name.endswith("record.json"))
            or path in {"run/missing_report.json", "run/missing_report.md"}
        ):
            raise HTTPException(404, "file unavailable")
        return FileResponse(f)

    @app.get("/api/projects/{rid}/export")
    def export(rid: str):
        return Response(
            service.export(rid),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="scene-review.zip"'},
        )
