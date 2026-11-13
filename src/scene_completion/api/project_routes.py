"""Project Routes."""

import json
import time

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from scene_completion.domain.contracts import registry
from scene_completion.infrastructure.paths import PROGRAM_ROOT
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.infrastructure.worker_runtime import read_job
from scene_completion.review.decisions.reviews import Reviews

PROJECT = PROGRAM_ROOT
WEB = PROJECT / "web"


def register(app, service):
    @app.get("/")
    def index():
        return FileResponse(
            WEB / "index.html", headers={"Cache-Control": "no-cache, must-revalidate"}
        )

    @app.get("/api/projects")
    def projects():
        return service.list()

    @app.get("/api/capabilities")
    def capabilities():
        from scene_completion.cli.main import capabilities

        return {**capabilities(), "review_only": service.review_only}

    @app.post("/api/projects")
    def create(body: dict):
        return service.create(body)

    @app.post("/api/test-sources/preview")
    def preview_tests(body: dict):
        from scene_completion.inputs.provenance.test_sources import preview_sources

        return preview_sources(body.get("sources", []))

    @app.get("/api/test-sources/template")
    def test_template():
        path = PROJECT / "examples/tests/mall-exception-tests.xlsx"
        if not path.exists():
            raise HTTPException(404, "测试示例尚未安装")
        return FileResponse(path, filename="mall-exception-tests.xlsx")

    @app.get("/api/projects/{rid}/test-sources")
    def get_test_sources(rid: str):
        return service.test_sources(rid)

    @app.get("/api/projects/{rid}/test-sources/supplement")
    def get_test_supplement(rid: str, case: str | None = None):
        from scene_completion.compat.saved.result_views import ResultView

        v = ResultView(service.run_dir(rid))
        cases = v.cases()
        if case and case not in {c["id"] for c in cases}:
            raise ValueError("未知用例")
        return {
            "cases": cases,
            "case": case,
            "status": v.state.get((case or "") + ":test-supplement", {}).get("status", "not_ready"),
            "tests": v.payload(case + ":test-supplement").get("tests", []) if case else [],
            "pending": v.payload(case + ":test-supplement").get("pending", []) if case else [],
            "source": "独立正向材料补全，自动GT；未读取G/E",
        }

    @app.put("/api/projects/{rid}/test-sources")
    def put_test_sources(rid: str, body: dict):
        return service.test_sources(rid, body)

    @app.get("/api/registry")
    def definitions():
        return registry()

    @app.get("/api/projects/{rid}")
    def snapshot(rid: str, compact: bool = False):
        return service.snapshot(rid, compact=compact)

    @app.get("/api/projects/{rid}/registry")
    def project_definitions(rid: str, version: str | None = None):
        from scene_completion.review.decisions.project_review import registry_view

        return registry_view(service.run_dir(rid), version)

    @app.get("/api/projects/{rid}/patterns")
    def pattern_settings(rid: str, version: str | None = None):
        from scene_completion.analysis.recommendation.pattern_settings import settings

        return settings(service.run_dir(rid), version)

    @app.put("/api/projects/{rid}/patterns")
    def edit_pattern_settings(rid: str, body: dict):
        from scene_completion.analysis.recommendation.pattern_settings import save_settings

        p = service.run_dir(rid)
        job = read_job(p)
        if (
            rid in service.active
            or job.get("status") == "running"
            and job.get("worker_heartbeat", 0) > time.time() - 30
        ):
            raise ValueError("运行中请等待本轮结束后修改模式设置")
        with service.lock:
            return save_settings(p, body)

    @app.get("/api/projects/{rid}/recommendation-history")
    def recommendation_history(rid: str):
        from scene_completion.analysis.recommendation.pattern_settings import history

        return history(service.run_dir(rid))

    @app.post("/api/projects/{rid}/recommendation-history")
    def import_recommendation_history(rid: str, body: dict):
        from scene_completion.analysis.recommendation.pattern_settings import import_history

        with service.lock:
            return import_history(service.run_dir(rid), body)

    @app.get("/api/projects/{rid}/recommendations")
    def recommendations(rid: str, case: str | None = None, test_set: str = "expanded"):
        from scene_completion.analysis.recommendation.pattern_settings import (
            adoption,
            history,
            settings,
        )
        from scene_completion.compat.saved.result_views import ResultView

        p = service.run_dir(rid)
        v = ResultView(p)
        if case and case not in {c["id"] for c in v.cases()}:
            raise ValueError("未知用例")
        result = v.payload(case + ":gap-recommend") if case else {}
        matrix = v.payload(case + ":pattern-applicability") if case else {}
        if test_set not in {"original", "expanded", "business"}:
            raise ValueError("未知测试集")
        evaluation = v.payload(case + ":exception-evaluation") if case else {}
        if test_set == "original":
            evaluation = evaluation.get("original_evaluation", evaluation)
        business = None
        if case and test_set == "business":
            from scene_completion.review.truth.business_truth import snapshot

            business = snapshot(p, case)
            evaluation = business["evaluation"]
        from scene_completion.analysis.recommendation.ranking import comparison_for_view

        comparison = comparison_for_view(evaluation, result)
        from scene_completion.review.truth.business_truth import candidates

        return {
            "cases": v.cases(),
            "case": case,
            "result": result,
            "matrix": matrix,
            "comparison": comparison,
            "evaluation_metrics": evaluation.get("metrics", {}),
            "test_set": test_set,
            "current_settings_hash": settings(p)["version"],
            "human_adoption": adoption(p, result),
            "business_truth": business,
            "feedback": history(p)["feedback"],
            "feedback_revision": history(p)["revision"],
            "duplicate_candidates": {
                s["id"]: [
                    {"id": t["id"], "conditions": t.get("conditions", [])}
                    for t in candidates(s, evaluation.get("GT", []))
                ]
                for s in result.get("Q", [])
            },
        }

    @app.post("/api/projects/{rid}/recommendations/feedback")
    def recommendation_feedback(rid: str, body: dict):
        from scene_completion.analysis.recommendation.pattern_settings import feedback
        from scene_completion.compat.saved.result_views import ResultView

        p = service.run_dir(rid)
        result = ResultView(p).payload(str(body.get("case_id", "")) + ":gap-recommend")
        if not result.get("enabled"):
            raise ValueError("本用例尚未形成推荐")
        if (
            body.get("choice") == "adopt"
            and "reviewer" in body
            and not str(body["reviewer"]).strip()
        ):
            raise ValueError("请填写审核人")
        with service.lock:
            value = feedback(p, body, result, dry_run=body.get("dry_run", False))
            if not body.get("dry_run"):
                from scene_completion.review.truth.business_truth import snapshot

                value = {**value, "business_truth": snapshot(p, body["case_id"])}
            return value

    @app.post("/api/projects/{rid}/patterns/review")
    def pattern_review(rid: str, body: dict):
        from scene_completion.analysis.recommendation.pattern_settings import review_candidate
        from scene_completion.compat.saved.result_views import ResultView

        p = service.run_dir(rid)
        job = read_job(p)
        if (
            rid in service.active
            or job.get("status") == "running"
            and job.get("worker_heartbeat", 0) > time.time() - 30
        ):
            raise ValueError("请等待本轮结束后审核模式前提")
        matrix = ResultView(p).payload(str(body.get("case_id", "")) + ":pattern-applicability")
        if not matrix:
            raise ValueError("本用例尚未形成模式适用性产物")
        with service.lock:
            return review_candidate(p, body, matrix)

    @app.put("/api/projects/{rid}/registry")
    def edit_project_definitions(rid: str, body: dict):
        from scene_completion.review.decisions.project_review import save_registry

        p = service.run_dir(rid)
        job = read_job(p)
        if (
            rid in service.active
            or job.get("status") == "running"
            and job.get("worker_heartbeat", 0) > time.time() - 30
        ):
            raise ValueError("请等待当前执行轮完成再发布关注点版本")
        with service.lock:
            return save_registry(p, body)

    @app.get("/api/projects/{rid}/pending")
    def pending_review_items(
        rid: str,
        status: str = "unresolved",
        case: str | None = None,
        offset: int = 0,
        limit: int = 50,
        search: str = "",
        channel: str | None = None,
        queue: str = "business",
    ):
        from scene_completion.review.decisions.project_review import pending_view

        with service.lock:
            return pending_view(
                service.run_dir(rid), status, case, offset, limit, search, channel, queue
            )

    @app.post("/api/projects/{rid}/pending/{item_id}")
    def review_pending_item(rid: str, item_id: str, body: dict):
        from scene_completion.review.decisions.project_review import decide_pending, pending_items

        with service.lock:
            if "reviewer" not in body:
                return decide_pending(service.run_dir(rid), item_id, body)
            from scene_completion.review.decisions.review_questions import answer

            item = next(
                (i for i in pending_items(service.run_dir(rid)) if i["id"] == item_id), None
            )
            if item is None:
                raise ValueError("问题已变化，请刷新")
            return answer(service.run_dir(rid), item, body, dry_run=body.get("dry_run", False))

    @app.get("/api/model-accounts")
    def model_accounts():
        return service.model_accounts()

    @app.put("/api/model-accounts")
    def save_model_account(body: dict):
        with service.lock:
            return service.model_accounts(body)

    @app.get("/api/projects/{rid}/node-repair")
    def repair_context(rid: str, task_key: str):
        from scene_completion.workflow.recovery.node_repair import export_repair

        return export_repair(service.run_dir(rid), task_key)

    @app.post("/api/projects/{rid}/node-repair")
    def repair_submit(rid: str, body: dict):
        from scene_completion.workflow.recovery.node_repair import submit_repair
        from scene_completion.workflow_core import run_lock

        p = service.run_dir(rid)
        if rid in service.active:
            raise ValueError("请等待本轮执行结束再提交修复，导出和校验不会调用模型")
        with service.lock, run_lock(p / "run"):
            return submit_repair(
                p, body["task_key"], body["repair"], validate_only=body.get("validate_only", False)
            )

    @app.get("/api/projects/{rid}/config")
    def effective_config(rid: str, task: str = "agent", task_key: str | None = None):
        from scene_completion.models.configuration.model_diagnostics import effective

        if task_key:
            p = service.run_dir(rid) / "run/workflow_tasks.json"
            record = read_json(p).get("tasks", {}).get(task_key) if p.exists() else None
            if not record:
                raise ValueError("未知执行节点")
            task = record["stage"]
        return effective(service.model_config(rid), task)

    @app.get("/api/projects/{rid}/diagnostics")
    def diagnostics(rid: str, task_key: str | None = None, limit: int = 20):
        from scene_completion.models.configuration.model_diagnostics import node_diagnostics

        if not 1 <= limit <= 100:
            raise ValueError("limit范围1至100")
        return node_diagnostics(service.run_dir(rid), service.model_config(rid), task_key, limit)

    @app.put("/api/projects/{rid}/config")
    def configure(rid: str, body: dict):
        return service.configure(rid, body)

    @app.put("/api/projects/{rid}/mode")
    def mode(rid: str, body: dict):
        if rid in service.active:
            raise ValueError("运行期间不能切换模式")
        if body.get("review_mode") not in {"manual", "auto"}:
            raise ValueError("invalid review mode")
        p = service.run_dir(rid)
        v = read_json(p / "project.json")
        v["review_mode"] = body["review_mode"]
        write_json(p / "project.json", v)
        return v

    @app.get("/api/projects/{rid}/prompts")
    def node_prompts(rid: str, task_key: str, request_id: str | None = None):
        from scene_completion.models.transport.request_context import view

        return view(service.run_dir(rid) / "run", task_key, request_id)

    @app.get("/api/projects/{rid}/context")
    def model_context(rid: str, task_key: str):
        root = service.run_dir(rid) / "run"
        chosen = None
        pointer = root / "context_index" / (fingerprint(task_key) + ".json")
        if pointer.exists():
            relative = read_json(pointer).get("path", "")
            target = (root / relative).resolve()
            if target.is_relative_to(root.resolve()) and target.is_file():
                chosen = read_json(target)
        if chosen is None:
            for f in sorted(
                (root / "model_contexts").glob("*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            ):
                v = read_json(f)
                if v.get("node_key") == task_key:
                    chosen = v
                    write_json(pointer, {"path": str(f.relative_to(root))})
                    break
        if chosen is None:
            return Response(
                json.dumps(
                    {"status": "未准备模型上下文", "task_key": task_key}, ensure_ascii=False
                ),
                media_type="application/json",
            )
        return Response(
            json.dumps(chosen, ensure_ascii=False, indent=2), media_type="application/json"
        )

    @app.get("/api/projects/{rid}/conversation")
    def conversation(rid: str, task_key: str):
        store = service.conversation(rid, task_key)
        return {
            "messages": store.list(task_key),
            "question": store.pending(task_key),
            "revision": store.revision(task_key),
        }

    @app.post("/api/projects/{rid}/conversation")
    def guidance(rid: str, body: dict):
        if body.get("dry_run"):
            service.conversation(rid, body["task_key"])
            if (
                not isinstance(body.get("text"), str)
                or not body["text"].strip()
                or len(body["text"]) > 30000
            ):
                raise ValueError("消息不能为空或超过30000字符")
            return {"valid": True, "saved": False}
        return service.guide(rid, body["task_key"], body["text"])

    @app.post("/api/projects/{rid}/answer")
    def answer(rid: str, body: dict):
        store = service.conversation(rid, body["task_key"])
        if body.get("dry_run"):
            q = store.pending(body["task_key"])
            if not q or q["detail"]["question_id"] != body["question_id"]:
                raise ValueError("问题已变化，请刷新")
            if (
                not isinstance(body.get("text"), str)
                or not body["text"].strip()
                or len(body["text"]) > 30000
            ):
                raise ValueError("回答不能为空或超过30000字符")
            return {"valid": True, "saved": False}
        value = store.answer(body["task_key"], body["question_id"], body["text"])
        return value

    @app.post("/api/projects/{rid}/rerun-node")
    def rerun(rid: str, body: dict):
        if rid in service.active:
            raise ValueError("请等待当前执行轮结束；运行中指导会在下一次模型调用生效")
        store = service.conversation(rid, body["task_key"])
        if store.pending(body["task_key"]):
            raise ValueError("请先回答当前问题")
        store.append(
            body["task_key"],
            "guidance",
            body.get("text") or "根据本节点最新指导重新执行并生成审核稿。",
        )
        store.invalidate(body["task_key"])
        return service.start(rid)

    @app.get("/api/projects/{rid}/review-history")
    def review_history(rid: str, task_key: str):
        root = service.run_dir(rid) / "run/reviews/versions"
        rows = []
        for f in root.glob("*.json"):
            value = read_json(f)
            if value.get("key") == task_key:
                rows.append({k: v for k, v in value.items() if k not in {"inputs"}})
        return {"versions": sorted(rows, key=lambda v: v.get("updated_at", ""), reverse=True)[:30]}

    @app.get("/api/projects/{rid}/reviews/{key:path}")
    def review(rid: str, key: str):
        v = Reviews(service.run_dir(rid) / "run").read(key)
        if not v:
            raise HTTPException(404, "unknown review")
        return v

    @app.post("/api/projects/{rid}/decision")
    def decide(rid: str, body: dict):
        if rid in service.active:
            raise ValueError("请等待当前任务结束再提交审核")
        return Reviews(service.run_dir(rid) / "run").decide(
            body["key"],
            body["action"],
            expected_revision=body["revision"],
            expected_input_hash=body["input_hash"],
            value=body.get("payload"),
            comment=body.get("comment", ""),
            dry_run=body.get("dry_run", False),
        )

    @app.get("/api/projects/{rid}/api-catalog")
    def api_catalog(rid: str, format: str = "view"):
        from scene_completion.inputs.structured.api_catalog import (
            markdown,
            save_catalog,
            saved_catalog,
        )

        if format not in {"view", "json", "md"}:
            raise HTTPException(400, "unsupported format")
        with service.lock:
            catalog = saved_catalog(service.run_dir(rid) / "run")
            save_catalog(service.run_dir(rid) / "run", catalog)
        if format == "view":
            return catalog
        return Response(
            markdown(catalog)
            if format == "md"
            else json.dumps(catalog, ensure_ascii=False, indent=2),
            media_type="text/markdown" if format == "md" else "application/json",
            headers={"Content-Disposition": f'attachment; filename="api-catalog.{format}"'},
        )
