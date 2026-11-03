"""Deterministic file recognition and structured format conversion."""

import json
import re
from pathlib import Path

from scene_completion.domain.contracts import PROTOCOL
from scene_completion.infrastructure.storage import fingerprint

TASKS = {
    "components",
    "api-map",
    "api-parameters",
    "rr-ssd",
    "sr-ssd",
    "fused-ssd",
    "object-operations",
    "business-entities",
}
ROOTS = {
    "components": {"components", "relations"},
    "api-map": {"services"},
    "api-parameters": {"apis"},
    "rr-ssd": {"interactions"},
    "sr-ssd": {"interactions"},
    "fused-ssd": {"interactions", "rr_sr_links", "pending"},
    "object-operations": {"objects"},
    "business-entities": {"entities", "pending"},
}


def role_hint(name, text):
    name = name.lower()
    if Path(name).suffix.lower() == ".json":
        from scene_completion.inputs.recovered_tests import json_cases

        try:
            json_cases(text)
            return "test"
        except (ValueError, IndexError, RecursionError):
            pass
    # A recovery/test body is stronger evidence than an arbitrary file name.
    if re.search(
        r"测试逆向|测试逆向恢复|^\s*[-*]\s+(?:exception|alternative_success|undetermined)〔SC@",
        text,
        re.M,
    ):
        return "test"
    if re.search(
        r"(^|[_. -])test(?:[_ -]?(?:spec|cases?|scenarios?))?([_. -]|$)|测试|逆向|recovered", name
    ):
        return "test"
    from scene_completion.inputs.test_sources import cells, is_test_header

    if any(
        is_test_header(cells(line)) for line in text.splitlines() if line.lstrip().startswith("|")
    ):
        return "test"
    if re.search(r"ssd|系统组成|对象操作|接口映射|接口参数|api[-_ ]?(?:map|parameters)", name):
        return "artifact"
    if re.search(r"rr.?spec|系统需求|需求_spec", name):
        return "RR"
    if re.search(r"sr.?spec|功能设计|设计_spec", name):
        return "SR"
    return "artifact"


def _infer(value):
    if not isinstance(value, dict):
        return None
    for task in ("fused-ssd", "components", "api-map", "api-parameters", "object-operations"):
        if ROOTS[task] <= set(value):
            return task
    rows = value.get("interactions")
    if isinstance(rows, list) and rows:
        layers = {r.get("layer") for r in rows if isinstance(r, dict)}
        if layers == {"RR"}:
            return "rr-ssd"
        if layers == {"SR"}:
            return "sr-ssd"
    return None


def _tables(text):
    from scene_completion.inputs.test_sources import cells

    header = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            header = None
            continue
        parts = cells(line)
        if all(re.fullmatch(r":?-{2,}:?", x.strip()) for x in parts):
            continue
        if header is None:
            header = parts
            continue
        yield dict(zip(header, parts))


def deterministic(text, name):
    """Return envelopes; free prose is handled by the scoped conversion agent."""
    try:
        value = json.loads(text)
    except ValueError:
        blocks = re.findall(r"```(?:json)?\s*\n([\s\S]*?)```", text, re.I)
        value = None
        for block in blocks:
            try:
                candidate = json.loads(block)
                if (
                    _infer(candidate)
                    or isinstance(candidate, dict)
                    and candidate.get("task") in TASKS
                ):
                    value = candidate
                    break
            except ValueError:
                pass
    if isinstance(value, dict):
        if isinstance(value.get("artifacts"), list):
            return value["artifacts"]
        task = value.get("task") or _infer(value)
        if task in TASKS:
            payload = value.get("payload", value)
            hint = value.get("case_id") or (
                payload.get("interactions", [{}])[0].get("case_id")
                if payload.get("interactions")
                else None
            )
            return [
                {
                    "task": task,
                    "case_hint": hint,
                    "coverage": value.get(
                        "coverage", "complete" if value.get("protocol") == PROTOCOL else "partial"
                    ),
                    "payload": payload,
                }
            ]
    services = {}
    for row in _tables(text):

        def pick(*keys):
            return next((row[k].strip("` ") for k in keys if row.get(k)), None)

        svc = pick("服务名称", "服务", "Service")
        method = pick("HTTP方法", "请求方法", "方法", "method")
        path = pick("接口地址", "路径", "path", "URL")
        name_ = pick("API名称", "接口名称", "名称", "API")
        if svc and (path or name_):
            services.setdefault(svc, []).append(
                {
                    "id": pick("API编号", "接口编号", "id")
                    or "api-" + fingerprint([svc, method, path, name_])[:16],
                    "name": name_ or path,
                    "method": method.upper() if method else None,
                    "address": path,
                    "source_refs": [],
                }
            )
    if services:
        return [
            {
                "task": "api-map",
                "case_hint": None,
                "coverage": "partial",
                "payload": {
                    "services": [
                        {"name": k, "interfaces": v, "source_refs": []} for k, v in services.items()
                    ]
                },
            }
        ]
    return []
