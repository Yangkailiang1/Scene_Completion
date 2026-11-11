"""Bounded operational indexes; business evidence remains in scoped node tools."""

import json
from collections import Counter
from copy import deepcopy


def execution_summary(state, limit=12):
    rows = state.get("pending_nodes", [])
    statuses = Counter(r.get("status", "unknown") for r in rows)
    roots = [r for r in rows if r.get("status") not in {"pending", "running", "blocked_dependency"}]
    result = {
        k: deepcopy(state[k])
        for k in (
            "project",
            "name",
            "complete",
            "execution_complete",
            "review_complete",
            "unresolved_questions",
            "review_only",
            "completed",
            "total",
            "job",
        )
        if k in state
    }
    if "job" in result:
        result["job"] = {
            k: result["job"][k]
            for k in ("status", "error_type", "finished_at")
            if k in result["job"]
        }
    selected = []
    for r in roots[:limit]:
        failure = r.get("failure") or {}
        text = json.dumps(failure, ensure_ascii=False)
        category = failure.get("failure_category")
        if category == "provider_context_limit":
            action = (
                "网关拒绝了上下文长度。请核对实际模型窗口、分词方式和输出预留，再缩小输入范围。"
            )
        elif category == "context_budget_exceeded" or "task context exceeds" in text:
            action = "上下文超限：检查完整请求预算及节点取片；重复同一请求不会解决。管理会话压缩不会压缩此节点原文。"
        elif r.get("status") == "budget_exhausted":
            action = "核对账号Token额度与预留；不得重置账本，不等同于语义修复次数。"
        elif r.get("status") in {"rejected", "failed"}:
            action = "读取本节点diagnose及rejected_output，检查剩余语义/恢复预算，再作有据修复；禁止原样重复重试。"
        else:
            action = "读取本节点诊断，核对配置、等待条件与恢复策略。"
        selected.append(
            {
                "id": r.get("id", r.get("task_key")),
                "status": r.get("status"),
                "stage": r.get("stage"),
                "failure_category": category,
                "failure_preview": text[:1200],
                "action": action,
            }
        )
    result.update(
        pending_count=len(rows),
        status_counts=dict(statuses),
        root_failure_count=len(roots),
        root_failures=selected,
        omitted_root_failures=max(0, len(roots) - limit),
        note="这是进度索引，不是完整节点上下文。用status分页或diagnose读取具体节点；先解决根失败，再处理blocked_dependency。",
    )
    return result


def memory_index(memories, max_chars=12000):
    """Do not paste arbitrarily large durable memory into every system prompt."""
    active = [m for m in memories if m.get("active")]
    raw = json.dumps(active, ensure_ascii=False)
    if len(raw) <= max_chars:
        return raw
    rows = []
    for m in active:
        item = {k: m.get(k) for k in ("id", "category", "revision", "scope", "source")}
        item["preview"] = m.get("text", "")[:180]
        if len(json.dumps(rows + [item], ensure_ascii=False)) > max_chars:
            break
        rows.append(item)
    return json.dumps(
        {
            "active_count": len(active),
            "indexed": rows,
            "omitted_count": len(active) - len(rows),
            "note": "记忆索引，非完整决定。执行前通过memory {id}读取相关完整记录；未展示的内容并未删除。",
        },
        ensure_ascii=False,
    )
