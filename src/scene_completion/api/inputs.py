"""Server-owned folder discovery and project-scoped colleague import APIs."""

import json
import os
import time
from pathlib import Path
from threading import Event, RLock, Thread

import scene_completion.inputs.artifact_imports as artifacts
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json

LOCK = RLock()
EXCLUDED = {
    "node_modules",
    ".git",
    ".env",
    "python",
    "__pycache__",
    "model_cache",
    "data",
    ".workbench",
    "imports",
    "run",
}


def watch_settings(project, body=None):
    p = Path(project) / "input-watch.json"
    value = (
        read_json(p)
        if p.exists()
        else {"directory": None, "watch": False, "observed": {}, "last_scan": None, "revision": 0}
    )
    if body is None:
        return {k: v for k, v in value.items() if k != "observed"}
    if body.get("expected_revision") is not None and body["expected_revision"] != value["revision"]:
        raise ValueError("扫描设置已变化")
    directory = Path(body.get("directory") or value.get("directory") or "").expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("input目录不存在，请填写服务所在电脑的本地目录")
    if directory == Path(directory.anchor):
        raise ValueError("不能将整个磁盘登记为input目录")
    if (
        (directory / "serve.py").exists()
        or (directory / ".git").exists()
        or (directory / "python.exe").exists()
    ):
        raise ValueError("请登记专用材料目录，不扫描程序或凭证目录")
    row = {
        **value,
        "directory": str(directory),
        "watch": body.get("watch", value["watch"]),
        "mode": body.get("mode", value.get("mode", "auto")),
        "revision": value["revision"] + 1,
    }
    if row["mode"] not in {"auto", "bundle", "generic"}:
        raise ValueError("扫描模式必须为auto、bundle或generic")
    if type(row["watch"]) is not bool:
        raise ValueError("watch必须为布尔值")
    if str(directory) != value.get("directory"):
        row["observed"] = {}
    if body.get("dry_run"):
        return {"saved": False, **{k: v for k, v in row.items() if k != "observed"}}
    write_json(p, row)
    return watch_settings(project)


def scan(project, service=None):
    project = Path(project)
    cfg = project / "input-watch.json"
    with LOCK:
        if not cfg.exists():
            return {"received": [], "waiting": 0}
        setting = read_json(cfg)
        root = Path(setting["directory"]).resolve()
        received = []
        waiting = 0
        seen = {}
        if not root.is_dir():
            return {"error": "input目录当前不可访问", "received": []}
        bundle_preview = bundle_files = None
        allowed = None
        if setting.get("mode", "auto") != "generic":
            from scene_completion.inputs.input_bundles import discover

            bundle_preview, bundle_files = discover(directory=str(root))
            if bundle_files or setting.get("mode") == "bundle":
                if bundle_preview["issues"]:
                    return {
                        **bundle_preview,
                        "received": [],
                        "waiting": 0,
                        "error": "同类文件有多个版本，请在五文件预览中选择",
                    }
                allowed = {f["path"] for f in bundle_preview["files"]}

        def paths():
            for directory, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".")
                    and d not in EXCLUDED
                    and not (Path(directory) / d).is_symlink()
                ]
                for name in files:
                    yield Path(directory) / name

        for n, path in enumerate(paths()):
            if n > 10000:
                raise ValueError("input目录文件过多，请登记专用材料目录")
            relative = path.relative_to(root)
            if allowed is not None and str(relative) not in allowed:
                continue
            if any(p.startswith(".") or p in EXCLUDED for p in relative.parts):
                continue
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            if path.suffix.lower() not in {".md", ".markdown", ".json", ".xlsx"} or any(
                x in path.name.lower()
                for x in (".local.", "api-key", "api_key", "credential", "token-budget", "ledger")
            ):
                continue
            stat = path.stat()
            if stat.st_size > 20 * 1024 * 1024:
                continue
            identity = [stat.st_size, stat.st_mtime_ns]
            old = setting["observed"].get(str(relative), {})
            count = old.get("stable", 0) + 1 if old.get("stat") == identity else 1
            record = {"stat": identity, "stable": count, "hash": old.get("hash")}
            seen[str(relative)] = record
            if count < 2:
                waiting += 1
                continue
            data = path.read_bytes()
            if [path.stat().st_size, path.stat().st_mtime_ns] != identity:
                waiting += 1
                continue
            digest = fingerprint(data.hex())
            if digest == old.get("hash"):
                continue
            import base64

            extra = {}
            if bundle_files:
                extra = next(
                    (
                        {k: f[k] for k in ("relative_path", "behavior_context") if k in f}
                        for f in bundle_files.values()
                        if f.get("relative_path") == str(relative)
                    ),
                    {},
                )
            received += artifacts.receive(
                project,
                [{"name": path.name, "content_base64": base64.b64encode(data).decode(), **extra}],
            )["received"]
            record["hash"] = digest
        adopted = None
        if (
            service is not None
            and bundle_files
            and not waiting
            and setting.get("last_bundle_hash") != bundle_preview["preview_hash"]
        ):
            from scene_completion.infrastructure.worker_runtime import read_job

            if project.name not in service.active and read_job(project).get("status") != "running":
                from scene_completion.inputs.input_bundles import apply

                adopted = apply(service, project, bundle_preview, bundle_files)
                setting["last_bundle_hash"] = bundle_preview["preview_hash"]
        setting.update(observed=seen, last_scan=time.time())
        write_json(cfg, setting)
        return {
            "received": received,
            "waiting": waiting,
            "scanned_at": setting["last_scan"],
            **({"bundle": bundle_preview, "adopted": bool(adopted)} if allowed is not None else {}),
        }


class InputWatcher:
    def __init__(self, service):
        self.service = service
        self.stop_event = Event()
        self.converting = set()
        self.guard = RLock()
        self.thread = Thread(target=self.loop, name="scene-input-watch", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()

    def loop(self):
        while not self.stop_event.wait(5):
            for p in self.service.root.glob("*/project.json"):
                try:
                    setting = watch_settings(p.parent)
                    if (
                        setting.get("watch")
                        or setting.get("directory")
                        and setting.get("last_scan") is None
                    ):
                        scan(p.parent, self.service)
                    self.convert_pending(p.parent)
                except Exception as e:
                    write_json(
                        p.parent / "imports/watch-error.json",
                        {"error": type(e).__name__, "message": str(e), "at": time.time()},
                    )

    def convert_pending(self, project):
        for row in artifacts.view(project)["items"]:
            if row["status"] != "needs_conversion":
                continue
            key = (project.name, row["id"])
            with self.guard:
                if key in self.converting:
                    continue
                self.converting.add(key)
            self.service.pool.submit(self.convert, project, row["id"])

    def convert(self, project, iid):
        try:
            from scene_completion.cli.task_commands import client_for
            from scene_completion.workflow.scheduler import CallGate

            config = self.service.model_config(project.name)
            config["run_root"] = str(project / "run")
            client = (
                self.service.client_factory(config, project / "run")
                if self.service.client_factory
                else client_for(config, project / "run")
            )
            if hasattr(client, "post"):
                gate = self.service.gates.setdefault(
                    project.name, CallGate(min(3, config.get("max_concurrency", 2)))
                )
                client.shared_call_gate = gate
                original = client.post
                client.post = lambda *a, **kw: gate.call(original, *a, **kw)
            artifacts.convert(project, iid, client)
        except Exception as e:
            # One failure is visible, not requeued every five seconds indefinitely.
            with artifacts.LOCK:
                index = artifacts.load(project)
                if iid in index["items"]:
                    row = read_json(project / index["items"][iid]["record"])
                    row.update(
                        status="conversion_failed", error=str(e), revision=row["revision"] + 1
                    )
                    write_json(project / index["items"][iid]["record"], row)
                    index["items"][iid]["status"] = "conversion_failed"
                    artifacts.save(project, index)
        finally:
            with self.guard:
                self.converting.discard((project.name, iid))


def register(app, service):
    def idle(project):
        from scene_completion.infrastructure.worker_runtime import read_job

        if project.name in service.active or read_job(project).get("status") == "running":
            raise ValueError("当前执行中，请等本轮结束后确认替换；新文件可先转换为候选")

    @app.post("/api/input-bundles/preview")
    def bundle_preview(body: dict):
        from scene_completion.inputs.input_bundles import discover

        return discover(
            directory=body.get("directory"), paths=body.get("paths"), files=body.get("files")
        )[0]

    @app.post("/api/projects/from-input-bundle")
    def create_bundle(body: dict):
        from scene_completion.inputs.input_bundles import apply, discover, validate_files

        preview, files = discover(
            directory=body.get("directory"), paths=body.get("paths"), files=body.get("files")
        )
        if not preview["valid"] or any(k not in files for k in ("RR", "SR")):
            raise ValueError("请提供唯一的RR、SR结构模型，先核对导入预览")
        if body.get("expected_hash") and body["expected_hash"] != preview["preview_hash"]:
            raise ValueError("文件已变化，请重新预览")
        if body.get("dry_run"):
            return preview
        validate_files(files)
        import base64

        sources = {
            role: [
                {
                    "name": files[role]["name"],
                    "content": base64.b64decode(files[role]["content_base64"]).decode("utf-8-sig"),
                }
            ]
            for role in ("RR", "SR")
        }
        if "test" in files:
            sources["test"] = [
                {
                    "name": files["test"]["name"],
                    "content": base64.b64decode(files["test"]["content_base64"]).decode(
                        "utf-8-sig"
                    ),
                }
            ]
        meta = service.create(
            {
                "name": body.get("name", ""),
                "sources": sources,
                "review_mode": body.get("review_mode", "manual"),
                "evaluation_scope": body.get("evaluation_scope", "SR"),
                "case_ids": body.get("case_ids", []),
            }
        )
        imported = apply(
            service,
            service.run_dir(meta["id"]),
            preview,
            files,
            adopt_partial=bool(body.get("adopt_partial", False)),
        )
        return {**meta, "input_bundle": imported}

    @app.post("/api/projects/{rid}/input-bundles")
    def bundle_import(rid: str, body: dict):
        from scene_completion.inputs.input_bundles import apply, discover

        p = service.run_dir(rid)
        preview, files = discover(
            directory=body.get("directory"), paths=body.get("paths"), files=body.get("files")
        )
        if body.get("dry_run"):
            return preview
        return apply(
            service,
            p,
            preview,
            files,
            expected_hash=body.get("expected_hash"),
            adopt_partial=bool(body.get("adopt_partial", False)),
            replace=bool(body.get("replace", False)),
        )

    @app.get("/api/projects/{rid}/imports")
    def imports(rid: str, item: str | None = None):
        return artifacts.view(service.run_dir(rid), item)

    @app.get("/api/projects/{rid}/import-plan")
    def import_plan(rid: str):
        from scene_completion.analysis.import_plan import build

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
        p = service.run_dir(rid)
        idle(p)
        if body.get("action") == "retry_conversion":
            with artifacts.LOCK:
                index = artifacts.load(p)
                row = artifacts.view(p, iid)
                if body.get("expected_revision") != row["revision"]:
                    raise ValueError("版本已变化")
                if body.get("dry_run"):
                    return {"saved": False, "valid": True}
                row.update(status="needs_conversion", revision=row["revision"] + 1)
                write_json(p / index["items"][iid]["record"], row)
                index["items"][iid]["status"] = "needs_conversion"
                artifacts.save(p, index)
            if service.input_watcher:
                service.input_watcher.convert_pending(p)
            return {"saved": True}
        if body.get("action") == "accept_source":
            return accept_source(service, p, artifacts.view(p, iid), body)
        return artifacts.decide(p, iid, body)

    @app.post("/api/projects/{rid}/input-scan")
    def input_scan(rid: str, body: dict):
        p = service.run_dir(rid)
        setting = watch_settings(p, body)
        if body.get("dry_run"):
            return setting
        result = scan(p, service)

        # The second stable sample is performed by the server, even without watch.
        def second():
            time.sleep(5)
            scan(p, service)
            if service.input_watcher:
                service.input_watcher.convert_pending(p)

        service.pool.submit(second)
        return {**result, "settings": setting}

    @app.get("/api/projects/{rid}/input-scan")
    def input_settings(rid: str):
        return watch_settings(service.run_dir(rid))

    @app.get("/api/projects/{rid}/recovery")
    def recovery(rid: str):
        from scene_completion.workflow.node_recovery import records, settings

        p = service.run_dir(rid)
        return {**settings(p), "ledger": records(p)}

    @app.put("/api/projects/{rid}/recovery")
    def recovery_update(rid: str, body: dict):
        from scene_completion.workflow.node_recovery import settings

        p = service.run_dir(rid)
        idle(p)
        return settings(p, body)


def deepcopy_json(value):
    return json.loads(json.dumps(value))


def accept_source(service, p, row, body):
    iid = row["id"]
    if body.get("expected_revision") != row["revision"]:
        raise ValueError("版本已变化")
    role = body.get("role", row["role"])
    if role not in {"RR", "SR", "test"}:
        raise ValueError("请选择来源用途")
    raw = (p / row["original"]).read_bytes()
    import base64

    from scene_completion.inputs.test_sources import decode_source

    decoded = {"name": row["name"], "content_base64": base64.b64encode(raw).decode()}
    if Path(row["name"]).suffix.lower() != ".xlsx":
        decoded["content"] = raw.decode("utf-8-sig")
    decode_source(decoded, role)
    if role == "test":
        import base64

        from scene_completion.inputs.test_sources import preview_sources

        if not preview_sources([decoded])["valid"]:
            raise ValueError("测试文件未通过导入预览")
    meta = read_json(p / "project.json")
    old = deepcopy_json(meta)
    same = [f for f in meta["sources"][role] if f["name"] == row["name"]]
    if same and not body.get("replace"):
        raise ValueError("已有同名来源，请确认替换或选择其他用途")
    if body.get("dry_run"):
        return {"saved": False, "valid": True, "role": role}
    write_json(p / "source_versions" / (fingerprint(old) + ".json"), old)
    meta["sources"][role] = [
        f for f in meta["sources"][role] if not (body.get("replace") and f["name"] == row["name"])
    ] + [{"name": row["name"], "path": row["original"], "source_id": "input-source-" + row["id"]}]
    if role == "test":
        version = fingerprint(
            [
                (f["name"], fingerprint((p / f["path"]).read_bytes().hex()))
                for f in meta["sources"][role]
            ]
        )[:20]
        history = p / "test_source_versions.json"
        versions = (
            read_json(history)
            if history.exists()
            else [
                {
                    "id": old.get("test_source_version", fingerprint(old["sources"]["test"])[:20]),
                    "sources": old["sources"]["test"],
                    "created_at": old["created_at"],
                }
            ]
        )
        versions.append(
            {"id": version, "sources": meta["sources"][role], "created_at": time.time()}
        )
        write_json(history, versions)
        meta["test_source_version"] = version
    write_json(p / "project.json", meta)
    with artifacts.LOCK:
        index = artifacts.load(p)
        row.update(status="source_active", role=role, revision=row["revision"] + 1)
        write_json(p / index["items"][iid]["record"], row)
        index["items"][iid]["status"] = "source_active"
        artifacts.save(p, index)
    return {"saved": True, "next": "显式run后仅重算受来源影响的节点"}
