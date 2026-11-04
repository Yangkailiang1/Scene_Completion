"""Inspect actual model requests without storing connection credentials."""

import time
from copy import deepcopy
from pathlib import Path
from threading import RLock
from uuid import uuid4

from scene_completion.infrastructure.execution_events import context
from scene_completion.infrastructure.storage import fingerprint, read_json, write_json
from scene_completion.models.context_budget import check

_LOCK = RLock()


def prepare(client, body, stage=None):
    """Persist even a blocked preflight; no request is sent by this function."""
    error = None
    try:
        measurement = check(body, client.config)
    except RuntimeError as exc:
        error = exc
        measurement = exc.response_diagnostic
    root = client.config.get("run_root")
    if root:
        _, fields = context()
        key = fields.get("task_key") or stage or "agent"

        # Connection credentials are never part of a prompt. Be defensive about
        # extra gateway parameters without rewriting business Schema keys.
        def redact(v, *, schema_or_message=False):
            if isinstance(v, dict):
                return {
                    k: "[redacted]"
                    if v.get("role") == "assistant"
                    and k in {"reasoning_content", "reasoning", "reasoning_details"}
                    else "[redacted]"
                    if not schema_or_message
                    and k.lower() in {"api_key", "authorization", "access_token", "secret"}
                    else redact(
                        x,
                        schema_or_message=schema_or_message
                        or k in {"messages", "tools", "response_format"},
                    )
                    for k, x in v.items()
                }
            if isinstance(v, list):
                return [redact(x, schema_or_message=schema_or_message) for x in v]
            if isinstance(v, str) and client.api_key:
                if v == client.api_key:
                    return "[redacted]"
                if len(client.api_key) >= 8:
                    return v.replace(client.api_key, "[redacted]")
            return v

        value = redact(body)
        ident = fingerprint([key, fields.get("model_call_id") or uuid4().hex, value])
        row = {
            "id": ident,
            "task_key": key,
            "stage": stage,
            "attempt": fields.get("attempt"),
            "at": time.time(),
            "model": value.get("model"),
            "status": "context_blocked" if error else "prepared",
            "request": value,
            "budget": measurement,
            "note": "最终组装的请求（凭证已脱敏；历史推理回传值不落盘，以redacted标记）；prepared不代表供应商已收到。工具/schema/正文历史均在请求内，旧日志不能倒推出完整请求。",
        }
        path = Path(root) / "model_contexts/requests" / (ident + ".json")
        index_path = Path(root) / "context_request_index" / (fingerprint(key) + ".json")
        with _LOCK:
            if path.exists():
                previous = read_json(path)
                if (
                    previous.get("budget") == measurement
                    and previous.get("status") == row["status"]
                ):
                    if error:
                        raise error
                    return measurement
            write_json(path, row)
            index = read_json(index_path) if index_path.exists() else {"requests": []}
            meta = {k: v for k, v in row.items() if k != "request"}
            meta["path"] = path.relative_to(root).as_posix()
            index["requests"] = [meta] + [r for r in index["requests"] if r["id"] != ident]
            write_json(index_path, index)
    if error:
        raise error
    return measurement


def view(root, key, request_id=None):
    root = Path(root)
    path = root / "context_request_index" / (fingerprint(key) + ".json")
    rows = read_json(path).get("requests", []) if path.exists() else []
    if request_id is None:
        return {
            "task_key": key,
            "requests": [{k: v for k, v in r.items() if k != "path"} for r in rows],
            "latest": rows[0]["id"] if rows else None,
        }
    row = next((r for r in rows if r["id"] == request_id), None)
    if row is None:
        raise ValueError("请求记录不存在，旧记录无法还原完整提示词")
    target = (root / row["path"]).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("请求记录路径无效")
    value = read_json(target)
    if value.get("task_key") != key:
        raise ValueError("请求记录不属于当前节点")
    return deepcopy(value)
