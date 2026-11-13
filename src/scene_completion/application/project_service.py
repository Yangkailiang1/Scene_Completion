"""Project operations shared by HTTP and CLI."""

import io
import json
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from uuid import uuid4

from scene_completion.domain.contracts import PROTOCOL
from scene_completion.infrastructure.paths import PROGRAM_ROOT
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.infrastructure.worker_runtime import read_job
from scene_completion.review.decisions.project_review import project_scoped

PROJECT = PROGRAM_ROOT
WEB = PROJECT / "web"


class Workbench:
    def __init__(self, root, client_factory=None, env_file=None, worker=False):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.env_file = Path(env_file or PROJECT / ".env")
        self.review_only = (self.root / ".review-mode.json").exists()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.active = set()
        self.lock = Lock()
        self.client_factory = client_factory
        self.gates = {}
        self.dialogue_active = set()
        self.worker = worker
        self.input_watcher = None
        self.guardian = None
        self.manager_host = None
        self.local_url = __import__("os").environ.get(
            "SCENE_WORKBENCH_URL", "http://127.0.0.1:8765"
        )

    def run_dir(self, run_id):
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise ValueError("invalid project id")
        p = self.root / run_id
        if not (p / "project.json").is_file():
            raise ValueError("unknown project")
        return p.resolve()

    def create(self, body):
        name = body.get("name", "").strip()
        if not name:
            raise ValueError("请填写项目名称")
        if body.get("review_mode", "manual") not in {"manual", "auto"}:
            raise ValueError("invalid review mode")
        sources = body.get("sources", {})
        saved = {}
        supplied_default = body.get("supplied_only_default") is True
        if not supplied_default and (not sources.get("RR") or not sources.get("SR")):
            raise ValueError("请提供RR和SR Markdown或结构模型JSON")
        from scene_completion.inputs.provenance.test_sources import (
            ImportValidationError,
            preview_sources,
        )

        imported = preview_sources(sources.get("test", []))
        if not imported["valid"]:
            raise ImportValidationError(imported)
        from scene_completion.analysis.evaluation.evaluation_scope import validate_scope

        evaluation_scope = validate_scope(body.get("evaluation_scope", "all"))
        case_ids = body.get("case_ids", [])
        if not isinstance(case_ids, list) or any(
            not isinstance(x, str) or not x.strip() for x in case_ids
        ):
            raise ValueError("invalid use-case scope")
        rid = uuid4().hex
        p = self.root / rid
        p.mkdir()
        for role in ("RR", "SR", "AR", "test"):
            saved[role] = []
            for idx, d in enumerate(sources.get(role, [])):
                from scene_completion.inputs.provenance.test_sources import decode_source

                content, suffix = decode_source(d, role)
                filename = f"sources/{role}-{idx}{suffix}"
                target = p / filename
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(content)
                saved[role].append({"path": filename, "name": Path(d["name"]).name})
        from scene_completion.analysis.concerns.normal_rules import RULESET_VERSION

        meta = {
            "evaluation_scope": evaluation_scope,
            "case_ids": case_ids,
            "id": rid,
            "name": name,
            "review_mode": body.get("review_mode", "manual"),
            "created_at": time.time(),
            "sources": saved,
            "protocol": PROTOCOL,
            "ruleset_version": RULESET_VERSION,
        }
        if supplied_default:
            meta["supplied_only_default"] = True
        write_json(p / "project.json", meta)
        from scene_completion.review.decisions.project_review import project_registry

        project_registry(p)
        return meta

    def test_sources(self, rid, body=None):
        from scene_completion.inputs.documents.source_documents import read_project_documents
        from scene_completion.inputs.provenance.test_sources import decode_source, preview

        p = self.run_dir(rid)
        meta = read_json(p / "project.json")
        history = p / "test_source_versions.json"
        versions = (
            read_json(history)
            if history.exists()
            else [
                {
                    "id": fingerprint(meta["sources"]["test"])[:20],
                    "sources": meta["sources"]["test"],
                    "created_at": meta["created_at"],
                }
            ]
        )
        current = meta.get("test_source_version", versions[-1]["id"])
        if body is not None:
            if rid in self.active or read_job(p).get("status") == "running":
                raise ValueError("运行期间不能切换测试集")
            if body.get("expected_version") != current:
                raise ValueError("测试集已变化，请刷新")
            if body.get("dry_run"):
                from scene_completion.inputs.provenance.test_sources import preview_sources

                if body.get("version") and not any(v["id"] == body["version"] for v in versions):
                    raise ValueError("未知测试集版本")
                checked = (
                    preview_sources(body.get("sources", []))
                    if not body.get("version")
                    else {"valid": True}
                )
                if not checked["valid"]:
                    raise ValueError("测试来源校验失败：" + json.dumps(checked, ensure_ascii=False))
                return {
                    "valid": True,
                    "saved": False,
                    "preview": checked,
                    "expected_version": current,
                }
            if body.get("version"):
                selected = next((x for x in versions if x["id"] == body["version"]), None)
                if selected is None:
                    raise ValueError("未知测试集版本")
                sources = selected["sources"]
                current = selected["id"]
            else:
                raw = body.get("sources", [])
                if not raw:
                    raise ValueError("请上传测试文件")
                decoded = [(d, decode_source(d, "test")) for d in raw]
                current = fingerprint(
                    [(d["name"], fingerprint(data.hex())) for d, (data, suffix) in decoded]
                )[:20]
                sources = []
                for idx, (d, (data, suffix)) in enumerate(decoded):
                    filename = f"sources/tests-{current}/test-{idx}{suffix}"
                    target = p / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    sources.append({"path": filename, "name": Path(d["name"]).name})
                checked = preview(read_project_documents(p, sources, "test"))
                if not checked["valid"]:
                    from scene_completion.inputs.provenance.test_sources import (
                        ImportValidationError,
                    )

                    raise ImportValidationError(checked)
                if not any(x["id"] == current for x in versions):
                    versions.append({"id": current, "sources": sources, "created_at": time.time()})
            import shutil

            archive = p / "run/report_versions" / ("test-source-" + str(time.time_ns()))
            for name in (
                "missing_report.json",
                "missing_report.md",
                "run_manifest.json",
                "workflow_tasks.json",
                "workflow_graph.json",
            ):
                f = p / "run" / name
                if f.exists():
                    archive.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, archive / name)
            meta["sources"]["test"] = sources
            meta["test_source_version"] = current
            write_json(p / "project.json", meta)
            write_json(history, versions)
        from scene_completion.compat.saved.result_views import ResultView

        results = ResultView(p)
        return {
            "version": current,
            "versions": versions,
            "preview": preview(read_project_documents(p, meta["sources"]["test"], "test")),
            "sources": meta["sources"]["test"],
            "catalogue": results.payload("test-inventory"),
            "alignment": results.payload("test-case-align"),
            "alignment_stale": results.test_source_changed,
            "requirement_cases": results.cases(),
        }

    def list(self):
        return sorted(
            [read_json(p) for p in self.root.glob("*/project.json")],
            key=lambda x: x["created_at"],
            reverse=True,
        )

    def model_config(self, rid):
        from scene_completion.models.configuration.model_settings import resolve

        p = self.run_dir(rid)
        value = resolve(
            read_json(p / "model.local.json") if (p / "model.local.json").exists() else {},
            self.env_file,
            self.root,
        )
        value.update(
            _live_project=str(p),
            _live_accounts_root=str(self.root),
            _live_env_file=str(self.env_file),
        )
        return value

    def model_accounts(self, body=None):
        from scene_completion.models.configuration.model_accounts import (
            public_accounts,
            save_account,
        )

        if body is not None:
            aid = body.get("id")
            for m in self.list():
                p = self.run_dir(m["id"])
                c = read_json(p / "model.local.json") if (p / "model.local.json").exists() else {}
                j = read_job(p)
                if (
                    aid
                    and c.get("model_account_id") == aid
                    and (
                        m["id"] in self.active
                        or j.get("status") == "running"
                        and j.get("worker_heartbeat", 0) > time.time() - 30
                    )
                ):
                    raise ValueError("此连接正在执行项目，请结束本轮后修改")
            return save_account(self.root, body, self.env_file)
        return public_accounts(self.root, self.env_file)

    def configure(self, rid, body):
        p = self.run_dir(rid)
        read_job(p)
        # Provider settings are read at each future model call. Existing requests keep their own snapshot.
        from scene_completion.application.runtime_settings import KEYS, PRESETS, validate_options

        allowed = KEYS | {"model_account_id", "base_url", "agent_model", "api_key", "preset"}
        if set(body) - allowed:
            raise ValueError("不支持的配置键：" + ",".join(sorted(set(body) - allowed)))
        previous = read_json(p / "model.local.json") if (p / "model.local.json").exists() else {}
        config = dict(previous)
        if "model_account_id" in body and body["model_account_id"] != previous.get(
            "model_account_id"
        ):
            # Switching credentials must not inherit routing, provider options or quota files.
            for k in KEYS | {
                "api_key",
                "api_key_env",
                "base_url",
                "token_budget_ledger",
                "token_budget_limit",
                "provider_token_budget_limit",
                "provider_token_budget_ledgers",
                "provider_token_budget_lock",
                "token_budget_reasoning_reserve",
            }:
                config.pop(k, None)
        if "preset" in body:
            if body["preset"] not in PRESETS:
                raise ValueError("未知兼容预设")
            config.update(PRESETS[body["preset"]])
        if "model_profiles" in body:
            safe_profile_keys = KEYS - {
                "model_profiles",
                "task_models",
                "role_models",
                "thinking_override",
            }
            if not isinstance(body["model_profiles"], dict) or any(
                not isinstance(v, dict) or set(v) - safe_profile_keys
                for v in body["model_profiles"].values()
            ):
                raise ValueError("模型配置只接受公开运行参数，不能修改凭证或配额账本")
            body = {
                **body,
                "model_profiles": {
                    m: {**config.get("model_profiles", {}).get(m, {}), **v}
                    for m, v in body["model_profiles"].items()
                },
            }
        if "thinking" in body:
            body = {**body, "thinking_override": body["thinking"]}
        config.update(
            {k: v for k, v in body.items() if k != "preset" and not (k == "api_key" and not v)}
        )
        if not config.get("agent_model", "").strip():
            raise ValueError("请选择实际模型标识")
        from scene_completion.models.configuration.model_settings import resolve

        resolved_url = resolve(config, self.env_file, self.root).get("base_url", "")
        if not config.get("model_account_id") and not (resolved_url).startswith(
            ("http://", "https://")
        ):
            raise ValueError("请选择模型连接或填写API地址")
        config.update(
            agent_runtime="deepagents",
            structured_output="json_object",
            max_retries=0,
            adaptive_concurrency=True,
        )
        config = validate_options(config, defaults=True)
        validated = resolve(config, self.env_file, self.root)
        from scene_completion.models.configuration.model_routing import routed_config

        for task, role in [("agent", "modeler"), ("agent", "checker"), ("agent", "recommender")] + [
            (t, "modeler") for t in config.get("task_models", {})
        ]:
            routed_config(validated, task, role)
        write_json(p / "model.local.json", config)
        try:
            (p / "model.local.json").chmod(0o600)
        except OSError:
            pass
        from scene_completion.models.configuration.model_settings import public_settings

        return public_settings(validated)

    def require_current_project(self, rid: str) -> str:
        """Reject obsolete protocols without rewriting preserved project data."""
        meta = read_json(self.run_dir(rid) / "project.json")
        if meta.get("protocol") != PROTOCOL:
            raise ValueError("仅支持当前 scene-workflow-v5；旧数据已保留，请创建新项目")
        return rid

    def start(self, rid, options=None):
        if self.review_only:
            raise ValueError("业务审核包只保存确认记录；请交回研发后重跑")
        hold = self.run_dir(rid) / "run/pause_requested.json"
        if hold.exists() and read_json(hold).get("by") == "user":
            raise ValueError("项目已由用户暂停／停止；请明确点击继续运行，不自动恢复")
        if (self.root / "manager-maintenance.json").exists():
            raise ValueError("程序正在安全重启或回退，暂不接受新执行；请查看管理Agent操作记录")
        rid = self.require_current_project(rid)
        from scene_completion.workflow_core import run_lock

        with run_lock(self.run_dir(rid) / "dispatch"):
            return self._start(rid, options)

    def supplied_case_preview(self, rid, case_ids=()):
        from scene_completion.inputs.imports.artifact_imports import snapshot
        from scene_completion.inputs.structured.supplied_api import supplied_interfaces
        from scene_completion.inputs.structured.supplied_cases import inspect_cases

        root = self.run_dir(rid)
        rows = snapshot(root)
        preview, _, _, accepted = inspect_cases(rows, case_ids)
        if accepted:
            _, _, contracts, _, pending = supplied_interfaces(root, rows, accepted)
            preview.update(sr_interface_count=len(contracts), sr_api_pending=pending)
        return preview

    def _start(self, rid, options=None):
        if self.review_only:
            raise ValueError("业务审核包只保存确认记录；请交回研发后重跑")
        rid = self.require_current_project(rid)
        p = self.run_dir(rid)
        from scene_completion.infrastructure.worker_runtime import read_job

        job = read_job(p)
        options = dict(options or {})
        previous_scope = job.get("run_options", {})
        if "supplied_only" not in options and previous_scope.get("supplied_only"):
            options["supplied_only"] = True
            if "case_ids" not in options and "case_ids" in previous_scope:
                options["case_ids"] = previous_scope["case_ids"]
        project = read_json(p / "project.json")
        if project.get("supplied_only_default"):
            options["supplied_only"] = True
        if set(options) - {"case_ids", "priority_cases", "supplied_only"}:
            raise ValueError("不支持的运行范围参数")
        for k in ("case_ids", "priority_cases"):
            if k in options and (
                not isinstance(options[k], list)
                or any(not isinstance(x, str) or not x.strip() for x in options[k])
            ):
                raise ValueError("用例范围必须为非空编号列表")
        from scene_completion.infrastructure.worker_runtime import pid_alive

        if job.get("status") == "running" and (
            job.get("worker_heartbeat", 0) > time.time() - 30
            or job.get("pid")
            and pid_alive(job["pid"])
        ):
            raise ValueError("项目正在由联调工作进程执行")
        if "supplied_only" in options and type(options["supplied_only"]) is not bool:
            raise ValueError("仅运行已校验用例选项必须为布尔值")
        if options.get("supplied_only"):
            selected = options.get("case_ids", project.get("case_ids")) or []
            if not self.supplied_case_preview(rid, selected)["accepted"]:
                raise ValueError("没有通过正式校验的已有 SSD 用例")
        config = self.model_config(rid)
        if not self.client_factory and (not config["api_key"] or not config["base_url"]):
            raise ValueError("请在.env或项目中配置模型地址和密钥")
        with self.lock:
            if rid in self.active:
                raise ValueError("项目正在运行")
            self.active.add(rid)
        write_json(
            p / "job.json",
            {
                "status": "running",
                "started_at": time.time(),
                "worker_heartbeat": time.time(),
                "run_options": options,
            },
        )
        if self.client_factory or self.worker:
            self.pool.submit(self._execute, rid)
        else:
            from scene_completion.infrastructure.worker_runtime import monitor, spawn

            try:
                process = spawn(self, rid)
            except Exception:
                with self.lock:
                    self.active.discard(rid)
                write_json(p / "job.json", {"status": "error", "message": "项目进程启动失败"})
                raise
            from threading import Thread

            Thread(
                target=monitor, args=(self, rid, process), daemon=True, name="scene-project-monitor"
            ).start()
        return {"status": "running", "project_id": rid}

    @project_scoped
    def _execute(self, rid):
        p = self.run_dir(rid)
        try:
            from scene_completion.application.execution import Execution, build_pipeline
            from scene_completion.application.model_factory import client_for
            from scene_completion.inputs.documents.source_documents import (
                read_project_documents,
            )
            from scene_completion.workflow_core import run_lock

            project = read_json(p / "project.json")
            config = self.model_config(rid)
            config.setdefault("supplement_tests", False)
            config.setdefault("scenario_patterns", True)
            from scene_completion.analysis.recommendation.pattern_settings import history, settings

            write_json(p / "run/pattern_settings_used.json", settings(p)["settings"])
            write_json(p / "run/recommendation_history_used.json", history(p)["items"])
            config["review_mode"] = project["review_mode"]
            config["run_root"] = str(p / "run")
            with run_lock(p / "run"):
                client = (
                    self.client_factory(config, p / "run")
                    if self.client_factory
                    else client_for(config, p / "run")
                )
                options = read_json(p / "job.json").get("run_options", {})
                config["priority_cases"] = options.get("priority_cases", [])
                ex = Execution(
                    p / "run",
                    mode="external",
                    client=client,
                    config=config,
                    case_ids=options.get("case_ids", project.get("case_ids")),
                    supplied_only=options.get("supplied_only", False),
                )
                self.gates[rid] = ex.gate
                docs = {
                    role: read_project_documents(
                        p,
                        project["sources"].get(role, []),
                        "test" if role == "test" else "existing",
                    )
                    for role in ("RR", "SR", "AR", "test")
                }
                build_pipeline(ex, docs["RR"], docs["SR"], docs["test"], ar=docs["AR"])
                manifest = ex.finish()
                hold = (
                    read_json(p / "run/pause_requested.json")
                    if (p / "run/pause_requested.json").exists()
                    else {}
                )
                status = (
                    ("paused" if hold.get("action") == "pause" else "interrupted")
                    if hold.get("by") == "user"
                    else "complete"
                    if manifest["complete"]
                    else "complete_with_questions"
                    if manifest.get("execution_complete")
                    else "waiting"
                )
                write_json(
                    p / "job.json",
                    {
                        "status": status,
                        "reason": "user_" + hold["action"] if hold.get("by") == "user" else None,
                        "finished_at": time.time(),
                    },
                )
        except Exception as e:
            # Preserve actual diagnostics server-side without returning credentials.
            write_json(
                p / "job.json",
                {
                    "status": "error",
                    "error_type": type(e).__name__,
                    "message": "执行未完成，请查看任务状态与运行日志",
                    "finished_at": time.time(),
                },
            )
            import traceback

            (p / "error.log").write_text(traceback.format_exc(), encoding="utf8")
        finally:
            with self.lock:
                self.active.discard(rid)

    def execution_status(self, rid):
        p = self.run_dir(rid)
        r = p / "run"
        project = read_json(p / "project.json")
        graph = (
            read_json(r / "workflow_graph.json")
            if (r / "workflow_graph.json").exists()
            else {"nodes": []}
        )
        nodes = {n["id"]: n for n in graph["nodes"]}
        records = (
            read_json(r / "workflow_tasks.json").get("tasks", {})
            if (r / "workflow_tasks.json").exists()
            else {}
        )
        active = {k: v for k, v in records.items() if k in nodes}
        from scene_completion.infrastructure.worker_runtime import read_job

        job = read_job(p)
        if (
            job["status"] == "running"
            and rid not in self.active
            and job.get("worker_heartbeat", 0) < time.time() - 30
        ):
            job = {"status": "interrupted", "message": "执行进程已退出，可继续运行"}
        manifest = read_json(r / "run_manifest.json") if (r / "run_manifest.json").exists() else {}
        from scene_completion.infrastructure.execution_events import EventStore
        from scene_completion.review.decisions.project_review import pending_view

        review = pending_view(p, queue="all", limit=1)
        unresolved = review["counts"].get("unresolved", 0) + review["counts"].get("needs_info", 0)
        return {
            "project": rid,
            "name": project["name"],
            "job": job,
            "complete": bool(manifest.get("complete")),
            "execution_complete": bool(
                manifest.get("execution_complete", manifest.get("complete"))
            ),
            "review_complete": not unresolved,
            "unresolved_questions": unresolved,
            "review_only": self.review_only,
            "completed": sum(v["status"] == "passed" for v in active.values()),
            "total": len(nodes),
            "event_cursor": EventStore(r).latest_id(),
            "pending_nodes": [
                {
                    "id": k,
                    "stage": v["stage"],
                    "status": v["status"],
                    "failure": v.get("failure"),
                    "expected_files": nodes[k].get("expected_files", []),
                }
                for k, v in active.items()
                if v["status"] != "passed"
            ],
        }

    def snapshot(self, rid, compact=False):
        p = self.run_dir(rid)
        run = p / "run"
        if compact:
            from scene_completion.infrastructure.worker_runtime import read_job

            return {
                "project": read_json(p / "project.json"),
                "job": read_job(p),
                "manifest": read_json(run / "run_manifest.json")
                if (run / "run_manifest.json").exists()
                else None,
                "tasks": {"tasks": {}, "events": []},
                "reviews": [],
                "artifacts": [],
                "config": {},
                "review_only": self.review_only,
                "compact": True,
            }
        reviews = []
        for f in (run / "reviews").glob("*.json"):
            v = read_json(f)
            reviews.append({k: x for k, x in v.items() if k not in {"inputs", "payload"}})
        artifacts = [
            {
                "path": str(f.relative_to(p)).replace("\\", "/"),
                "name": f.name,
                "bytes": f.stat().st_size,
            }
            for folder in (run / "artifacts", run / "reviews/previews", run / "report_versions")
            for f in folder.rglob("*")
            if f.is_file()
        ]
        records = (
            read_json(run / "workflow_tasks.json")["tasks"]
            if (run / "workflow_tasks.json").exists()
            else {}
        )
        prefixes = {}
        for key, record in records.items():
            case = record.get("case", "shared")
            stem = (key if case == "shared" else key[len(case) + 1 :]).replace(":", "--")
            prefixes[
                "run/artifacts/"
                + ("shared" if case == "shared" else fingerprint(case)[:12])
                + "/"
                + stem
            ] = key
            preview_stem = record["stage"] if ":" in key else key
            prefixes["run/reviews/previews/" + fingerprint(key) + "/" + preview_stem] = key
        for artifact in artifacts:
            artifact["task_key"] = prefixes.get(artifact["path"].rsplit(".", 1)[0])
        artifacts = [
            a
            for a in artifacts
            if "/reviews/previews/" not in a["path"]
            or records.get(a.get("task_key"), {}).get("status") in {"passed", "awaiting_review"}
        ]
        for name in ("missing_report.json", "missing_report.md"):
            if (run / name).exists():
                artifacts.append(
                    {"path": "run/" + name, "name": name, "bytes": (run / name).stat().st_size}
                )
        from scene_completion.infrastructure.worker_runtime import read_job

        job = read_job(p)
        if (
            job["status"] == "running"
            and rid not in self.active
            and job.get("worker_heartbeat", 0) < time.time() - 30
        ):
            job = {"status": "interrupted", "message": "上次进程已退出，可继续运行并复用成功结果"}
        from scene_completion.models.configuration.model_settings import public_settings

        try:
            config = public_settings(self.model_config(rid))
        except ValueError as e:
            raw = read_json(p / "model.local.json") if (p / "model.local.json").exists() else {}
            config = {
                k: raw[k]
                for k in ("model_account_id", "agent_model", "max_concurrency", "max_tokens")
                if k in raw
            }
            config.update(credential_configured=False, configuration_error=str(e))
        from scene_completion.review.decisions.project_review import pending_view

        questions = pending_view(p, queue="all", limit=1)
        return {
            "project": read_json(p / "project.json"),
            "job": job,
            "manifest": read_json(run / "run_manifest.json")
            if (run / "run_manifest.json").exists()
            else None,
            "tasks": read_json(run / "workflow_tasks.json")
            if (run / "workflow_tasks.json").exists()
            else {"tasks": {}, "events": []},
            "reviews": reviews,
            "artifacts": artifacts,
            "config": config,
            "review_only": self.review_only,
            "review_summary": {
                "unresolved": questions["counts"].get("unresolved", 0)
                + questions["counts"].get("needs_info", 0),
                "counts": questions["counts"],
            },
        }

    def conversation(self, rid, key):
        from scene_completion.review.decisions.node_conversations import Conversations

        p = self.run_dir(rid)
        graph = (
            read_json(p / "run/workflow_graph.json")
            if (p / "run/workflow_graph.json").exists()
            else {"nodes": []}
        )
        tasks = (
            read_json(p / "run/workflow_tasks.json").get("tasks", {})
            if (p / "run/workflow_tasks.json").exists()
            else {}
        )
        if key not in tasks and key not in {n["id"] for n in graph["nodes"]}:
            raise ValueError("请选择已创建的实际节点")
        store = Conversations(p / "run")
        return store

    def guide(self, rid, key, text):
        store = self.conversation(rid, key)
        row = store.append(key, "guidance", text)
        tasks = read_json(self.run_dir(rid) / "run/workflow_tasks.json").get("tasks", {})
        if tasks.get(key, {}).get("status") not in {"running", "awaiting_answer"}:
            store.invalidate(key)
            self.pool.submit(self._dialogue, rid, key)
        return row

    @project_scoped
    def _dialogue(self, rid, key):
        with self.lock:
            if (rid, key) in self.dialogue_active:
                return
            self.dialogue_active.add((rid, key))
        from scene_completion.application.model_factory import client_for
        from scene_completion.infrastructure.execution_events import EventStore, bind, emit

        p = self.run_dir(rid)
        store = self.conversation(rid, key)
        try:
            packets = []
            for f in (p / "run/packets").glob("*.json"):
                value = read_json(f)
                if value.get("node_key") == key:
                    packets.append((f.stat().st_mtime, value))
            task_packet = max(packets, key=lambda a: a[0])[1] if packets else None
            if not task_packet:
                store.append(key, "assistant", "指导已保存，将在该节点下一次模型调用时生效。")
                return
            config = self.model_config(rid)
            from scene_completion.domain.task_catalog import role_for
            from scene_completion.models.configuration.model_routing import routed_config

            config = (
                routed_config(config, task_packet["task"], role_for(task_packet["task"])) or config
            )
            client = client_for(config, p / "run")
            from scene_completion.inputs.provenance.indexed_context import EvidenceContext
            from scene_completion.models.clients.deepagents_client import compact_input

            context_packet = (
                EvidenceContext(task_packet).packet
                if config.get("indexed_context", False)
                else task_packet
            )
            messages = [
                {
                    "role": "system",
                    "content": "你是该节点的业务对话助手。只根据允许任务包回答指导和疑问。不得读取其他任务、E、GT或比较答案，不修改或伪造正式产物；需要重做时说明点击重新执行本节点。",
                },
                {
                    "role": "user",
                    "content": "允许任务上下文："
                    + json.dumps(
                        {
                            "task": context_packet["task"],
                            "input": compact_input(context_packet["input"]),
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ]
            messages += [
                {"role": "assistant" if m["kind"] == "assistant" else "user", "content": m["text"]}
                for m in store.list(key)[-20:]
                if m["kind"] in {"assistant", "guidance", "answer"}
            ]
            with bind(
                EventStore(p / "run"),
                task_key=key,
                role="dialogue",
                case="node",
                attempt=0,
                model_call_id="dialogue-" + uuid4().hex,
            ):
                body = {
                    "model": client.model("agent"),
                    "messages": messages,
                    "max_tokens": client.output_limit("dialogue"),
                    "stream": config.get("stream", True),
                }
                if body["stream"] and config.get("stream_usage", True):
                    body["stream_options"] = {"include_usage": True}
                from scene_completion.application.runtime_settings import request_options

                body = request_options(body, config, "dialogue")
                emit(
                    "request_started",
                    requested_model=body["model"],
                    purpose="dialogue",
                    input_bytes=len(json.dumps(body, ensure_ascii=False).encode()),
                )
                from scene_completion.models.transport.request_admission import CallGate

                gate = self.gates.setdefault(rid, CallGate(config.get("max_concurrency", 1)))
                try:
                    response = gate.call(client.post, "/chat/completions", body)
                except Exception as e:
                    emit(
                        "request_failed",
                        requested_model=body["model"],
                        diagnostic=getattr(e, "response_diagnostic", getattr(e, "details", {})),
                    )
                    raise
                emit(
                    "request_finished",
                    requested_model=body["model"],
                    provider_model=response.get("model"),
                    usage=response.get("usage"),
                )
                store.append(
                    key,
                    "assistant",
                    response["choices"][0]["message"].get("content") or "回复为空；指导仍已保存。",
                )
        except Exception as e:
            store.append(
                key, "system", "对话未完成：" + type(e).__name__ + "；指导已保存，可稍后重试。"
            )
        finally:
            with self.lock:
                self.dialogue_active.discard((rid, key))

    def _resume(self, rid):
        while rid in self.active:
            time.sleep(0.2)
        try:
            self.start(rid)
        except ValueError:
            pass

    def export(self, rid):
        from scene_completion.inputs.structured.api_catalog import save_catalog, saved_catalog

        with self.lock:
            save_catalog(self.run_dir(rid) / "run", saved_catalog(self.run_dir(rid) / "run"))
        p = self.run_dir(rid)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
            for f in p.rglob("*"):
                if (
                    not f.is_file()
                    or f.name.endswith((".local.json", ".lock"))
                    or f.name == "error.log"
                    or "manager" in f.relative_to(p).parts
                    or "execution_events.sqlite3" in f.name
                    or any(s in f.parts for s in ("model_cache", "native"))
                ):
                    continue
                z.write(f, str(f.relative_to(p)))
            if (p / "run/execution_events.sqlite3").exists():
                from scene_completion.infrastructure.execution_events import EventStore

                z.writestr(
                    "run/execution_events.jsonl", "".join(EventStore(p / "run").dump_jsonl())
                )
                from scene_completion.review.decisions.node_conversations import Conversations

                tasks = (
                    read_json(p / "run/workflow_graph.json").get("nodes", [])
                    if (p / "run/workflow_graph.json").exists()
                    else []
                )
                z.writestr(
                    "run/node_conversations.json",
                    json.dumps(
                        {n["id"]: Conversations(p / "run").list(n["id"]) for n in tasks},
                        ensure_ascii=False,
                    ),
                )
        return stream.getvalue()
