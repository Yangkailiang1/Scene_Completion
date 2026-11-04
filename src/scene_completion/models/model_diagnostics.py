"""Credential-free effective request settings and bounded node diagnostics."""

import json
from pathlib import Path

from scene_completion.infrastructure.storage import read_json
from scene_completion.models.model_settings import public_settings
from scene_completion.workflow.runtime_settings import (
    request_options,
    validate_options,
)


def effective(config, task="agent"):
    from scene_completion.models.deepagents_client import role_for, submission_mode
    from scene_completion.models.model_client import SemanticClient
    from scene_completion.models.model_routing import routed_config

    selected = routed_config(config, task, role_for(task)) or config
    validate_options(selected)
    client = SemanticClient(dict(selected))
    limit = client.output_limit(task)
    body = request_options(
        {
            "model": client.model("agent"),
            "max_tokens": limit,
            "stream": selected.get("stream", True),
        },
        selected,
        task,
    )
    safe = {k: v for k, v in body.items() if k not in {"messages", "tools"}}
    if selected.get("api_key"):
        safe = json.loads(json.dumps(safe).replace(selected["api_key"], "[redacted]"))
    return {
        "task": task,
        "role": role_for(task),
        "model": body["model"],
        "settings": public_settings(selected),
        "request_parameters": safe,
        "submission_mode": submission_mode(selected, task, body["model"]),
        "notes": [
            "输出上限由思考与正文/工具参数如何分配取决于网关；不是正文必得Token数。",
            "实际请求另加系统提示、Skill、工具Schema及历史，逐请求检查上下文预算。",
            "兼容预设不是对客户网关能力的探测；不支持的参数应按网关说明关闭。",
        ],
    }


def node_diagnostics(project, config, task_key=None, limit=20):
    root = Path(project) / "run"
    state = (
        read_json(root / "workflow_tasks.json").get("tasks", {})
        if (root / "workflow_tasks.json").exists()
        else {}
    )
    if task_key and task_key not in state:
        raise ValueError("未知执行节点，请从status或执行图选取真实节点ID")
    rows = (
        [(task_key, state[task_key])]
        if task_key
        else [
            (k, r)
            for k, r in state.items()
            if r.get("status") not in {"passed", "ready", "pending", "running"} or r.get("failure")
        ][-limit:]
    )
    out = []
    from scene_completion.infrastructure.execution_events import EventStore

    store = EventStore(root)
    for key, row in rows:
        with store.connect() as db:
            history = db.execute(
                "SELECT payload FROM events WHERE task_key=? AND kind IN ('request_started','request_finished','request_failed','response_invalid','validation_failed','artifact_io_failed','stream_progress','stream_status','agent_failed') ORDER BY id DESC LIMIT ?",
                (key, limit),
            ).fetchall()
        history = [json.loads(v[0]) for v in reversed(history)]
        recent = []
        for event in history:
            data = event["data"]
            recent.append(
                {
                    "kind": event["kind"],
                    "timestamp": event["timestamp"],
                    "data": {
                        k: v
                        for k, v in data.items()
                        if k not in {"text", "content", "arguments", "reasoning_content"}
                    },
                }
            )
        failures = []
        for p in sorted(
            (root / "agent_rejections").glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            v = read_json(p)
            if v.get("node_key") == key:
                failures.append(
                    {
                        "file": p.relative_to(project).as_posix(),
                        "error": str(v.get("error", ""))[:4000],
                        "reference_mode": v.get("reference_mode"),
                        "reference_error": v.get("reference_error"),
                    }
                )
                if len(failures) >= 3:
                    break
        call_id = next(
            (
                e["data"]["model_call_id"]
                for e in reversed(history)
                if e["data"].get("model_call_id")
            ),
            None,
        )
        request_history = [e for e in history if e["data"].get("model_call_id") == call_id]
        progress = next(
            (e["data"] for e in reversed(request_history) if e["kind"] == "stream_progress"), {}
        )
        finished = next(
            (
                e["data"].get("diagnostic", {})
                for e in reversed(request_history)
                if e["kind"] in {"request_finished", "request_failed"}
            ),
            {},
        )
        started = next(
            (e["data"] for e in reversed(request_history) if e["kind"] == "request_started"), {}
        )
        observation = {
            k: finished.get(k, progress.get(k))
            for k in ("reasoning_bytes", "reasoning_fields", "delta_fields", "response_mode")
        }
        observation["display_enabled_for_request"] = started.get(
            "reasoning_display_enabled", progress.get("reasoning_display_enabled")
        )
        observation["note"] = (
            "仅报告网关实际返回的字段及计数，不包含思考文本。旧记录缺失的值为null；配置变更仅影响后续请求。"
        )
        from scene_completion.infrastructure.storage import fingerprint

        context_file = root / "context_index" / (fingerprint(key) + ".json")
        saved_context = read_json(context_file) if context_file.exists() else {}
        out.append(
            {
                "task_key": key,
                "stage": row["stage"],
                "status": row["status"],
                "failure": row.get("failure"),
                "effective": effective(config, row["stage"]),
                "stream_observation": observation,
                "events": recent,
                "validation_rejections": failures,
                "reference_contract": saved_context.get("reference_contract"),
            }
        )
    from scene_completion.infrastructure.program_version import program_version

    result = {
        "program_version": program_version(),
        "nodes": out,
        "llm_called": False,
        "notes": [
            "诊断只读取已有记录，不调用模型、不重置配额或修复预算。",
            "同一节点需区分输出截断、JSON语法、业务Schema和本地文件写入失败；诊断不返回思考原文，显式开启后思考文本单列在本地节点事件。",
            "program_version.source_commit来自程序VERSION.json或Git；reference_contract.source_ids是允许的文档身份，两者不可互换。旧记录未保存引用模式时显示null，不按当前配置猜测历史请求。",
        ],
    }
    from scene_completion.manager.manager_store import Journal
    from scene_completion.manager.manager_store import settings as manager_settings
    from scene_completion.workflow.node_recovery import settings as recovery_settings

    journal = Journal(project)
    policy = manager_settings(project)["settings"]
    runtime = journal.get("runtime", default={})
    result["manager"] = {
        "enabled": policy["enabled"],
        "mode": policy["mode"],
        "context_limit": policy["context_limit"],
        "compression_ratio": policy["compression_ratio"],
        "runtime": {k: runtime.get(k) for k in ("status", "reason", "error", "retry_at")},
        "active_memory_count": sum(m.get("active", False) for m in journal.memory()),
        "conversation_summary_saved": bool(journal.get("summary", journal.session()["id"])),
        "note": "管理会话压缩不会裁剪业务节点原文；节点上下文/模型调用/语义修复/账号额度是独立预算。浮窗可见不代表Auto托管已启用。",
    }
    result["recovery_policy"] = recovery_settings(project)["settings"]
    text = json.dumps(result, ensure_ascii=False)
    if config.get("api_key"):
        text = text.replace(config["api_key"], "[redacted]")
    return json.loads(text)
