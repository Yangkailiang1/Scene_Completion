"""Colleague use-case JSON is independent test evidence, never positive input.

Offsets/pointers refer to the uploaded file. EV@ labels inside it are plain
unverified text, not references to unseen documents. No instructions execute.
"""

import json
import re
from bisect import bisect_right

from scene_completion.infrastructure.storage import fingerprint


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("JSON含重复属性：" + key)
        out[key] = value
    return out


def parsed(text):
    text = text.lstrip("\ufeff")

    def invalid(value):
        raise ValueError("JSON不允许非有限数值：" + value)

    value = json.loads(text, object_pairs_hook=_unique, parse_constant=invalid)
    decoder = json.JSONDecoder()
    spans = {}

    def ws(n):
        while n < len(text) and text[n].isspace():
            n += 1
        return n

    def walk(n, path, depth=0):
        if depth > 100:
            raise ValueError("JSON嵌套过深")
        n = ws(n)
        start = n
        if text[n] == "{":
            n = ws(n + 1)
            if text[n] != "}":
                while True:
                    key, n = decoder.raw_decode(text, n)
                    n = walk(ws(n) + 1, path + (key,), depth + 1)
                    n = ws(n)
                    if text[n] == "}":
                        break
                    n = ws(n + 1)
            n += 1
        elif text[n] == "[":
            n = ws(n + 1)
            index = 0
            if text[n] != "]":
                while True:
                    n = walk(n, path + (index,), depth + 1)
                    index += 1
                    n = ws(n)
                    if text[n] == "]":
                        break
                    n = ws(n + 1)
            n += 1
        else:
            _, n = decoder.raw_decode(text, n)
        spans[path] = (start, n)
        return n

    walk(0, ())
    return value, spans


def json_cases(text):
    value, spans = parsed(text)
    if isinstance(value, list):
        rows = value
        prefix = ()
    elif isinstance(value, dict) and any(k in value for k in ("usecases", "use_cases", "cases")):
        key = next(k for k in ("usecases", "use_cases", "cases") if k in value)
        rows = value[key]
        prefix = (key,)
    elif (
        isinstance(value, dict)
        and "id" in value
        and "name" in value
        and ("extensions" in value or "Extensions" in value)
    ):
        rows = [value]
        prefix = None
    else:
        raise ValueError("测试JSON需为用例数组，包含id、name和extensions数组")
    if not isinstance(rows, list) or not rows or any(not isinstance(c, dict) for c in rows):
        raise ValueError("测试JSON的用例列表格式无效或为空")
    out = []
    seen = set()
    for n, c in enumerate(rows):
        if any(not isinstance(c.get(k), str) or not c[k].strip() for k in ("id", "name")):
            raise ValueError("JSON用例缺少非空id或name")
        if c["id"] in seen:
            raise ValueError("JSON用例ID重复：" + c["id"])
        seen.add(c["id"])
        key = "extensions" if "extensions" in c else "Extensions"
        if not isinstance(c.get(key), list):
            raise ValueError(c["id"] + " 的extensions必须为数组")
        owner = (prefix + (n,)) if prefix is not None else ()
        out.append((c, owner, key))
    return out, spans


def kind_of(extension):
    from scene_completion.inputs.test_sources import KINDS

    for field in ("scenario_type", "type", "kind", "场景类型", "类型"):
        if field in extension:
            value = str(extension[field]).strip()
            kind = {**KINDS, "alternative_success": "normal", "undetermined": "pending"}.get(
                value.casefold(), "pending"
            )
            return kind, value, "原文件场景类型字段"
    note = str(extension.get("note", ""))
    expected = str(extension.get("expected_result", ""))
    if "成功备选" in note:
        return "normal", "alternative_success", "原文件明确标注成功备选，不参与异常计分"
    if re.search(r"是否.*(?:异常|降级).*未定|空值处理策略|异常与正常.*(?:未定|待确认)", note):
        return "pending", "undetermined", "场景适用前提或是否失败尚不明确"
    # Literal failure outcomes support typed indexing; unknown business meaning
    # is not guessed. Unknown response codes do not erase an explicit failure.
    if re.search(
        r"\bHTTP\s*[45]\d\d\b|(?:返回|明确|可诊断)(?:的)?(?:错误|失败)|拒绝|阻止无效",
        expected,
        re.I,
    ):
        return (
            "exception",
            "literal_failure_outcome",
            "根据本分支明示失败预期识别；关注点和实际交互仍需独立逆向分析",
        )
    return (
        "pending",
        "undetermined",
        "没有明确场景类型或失败预期，保留待确认；分叉点未知不等于非异常",
    )


def catalogue(document, strict=False):
    if not document["name"].split("#", 1)[0].lower().endswith(".json"):
        return None
    lines = document["lines"]
    text = "\n".join(r["text"] for r in lines).lstrip("\ufeff")
    try:
        rows, spans = json_cases(text)
    except (ValueError, IndexError, RecursionError):
        if strict:
            raise
        return None  # A downstream source slice need not remain a complete JSON.
    newlines = [n for n, c in enumerate(text) if c == "\n"]
    base = lines[0]["number"] if lines else 1

    def pointer(path):
        return (
            "/" + ("/".join(str(k).replace("~", "~0").replace("/", "~1") for k in path))
            if path
            else ""
        )

    def refs(path):
        start, end = spans[path]
        lo = bisect_right(newlines, start) + base
        hi = bisect_right(newlines, max(start, end - 1)) + base
        if hi - lo < 100:
            return [
                {
                    "source_id": document["source_id"],
                    "line_start": lo,
                    "line_end": hi,
                    "quote": text[start:end],
                }
            ]
        # Long evidence arrays split along actual physical lines, never invent rows.
        result = []
        chunk = text[start:end].splitlines()
        for n in range(0, len(chunk), 90):
            result.append(
                {
                    "source_id": document["source_id"],
                    "line_start": lo + n,
                    "line_end": lo + min(n + 90, len(chunk)) - 1,
                    "quote": "\n".join(chunk[n : n + 90]),
                }
            )
        return result

    cases = []
    records = []
    pending = []
    for case, owner, extkey in rows:
        association = case["id"] + "：" + case["name"]
        cid = "test-case-" + fingerprint([document["source_id"], association])[:20]
        context = []
        for k in (
            "id",
            "name",
            "purpose",
            "actors",
            "preconditions",
            "postconditions",
            "trigger",
            "main_success",
        ):
            if owner + (k,) in spans:
                context += refs(owner + (k,))
        cases.append(
            {
                "id": cid,
                "name": case["name"],
                "association": association,
                "source_refs": context or refs(owner + ("id",)),
                "source_case_id": case["id"],
            }
        )
        if not case[extkey]:
            pending.append(
                {
                    "reason": case["id"] + " 未提供扩展测试分支；不能将主成功路径当作异常GT",
                    "source_refs": refs(owner + (extkey,)),
                }
            )
        seen = set()
        for n, ext in enumerate(case[extkey]):
            path = owner + (extkey, n)
            if not isinstance(ext, dict) or any(
                not isinstance(ext.get(k), str) or not ext[k].strip()
                for k in ("id", "condition", "expected_result")
            ):
                raise ValueError("JSON扩展分支缺少id、condition或expected_result：" + pointer(path))
            if ext["id"] in seen:
                raise ValueError("扩展ID重复：" + case["id"] + " / " + ext["id"])
            seen.add(ext["id"])
            sid = case["id"] + "::" + ext["id"]
            kind, declared, reason = kind_of(ext)
            source_refs = refs(path)

            def show(v):
                return "\n".join(str(x) for x in v) if isinstance(v, list) else str(v or "")

            row = {
                "测试ID": sid,
                "测试名称": ext["condition"],
                "类型": {
                    "exception": "异常",
                    "normal": "正常",
                    "optional": "可选",
                    "pending": "待确认",
                }[kind],
                "前置条件": show(case.get("preconditions")),
                "触发条件": ext["condition"],
                "关联需求": association,
                "测试目标": str(case.get("purpose", "")),
                "预期结果": ext["expected_result"],
                "需求依据": show(ext.get("evidence", [])),
                "测试数据": show(ext.get("test_data")),
                "测试步骤": show(ext.get("steps")),
                "关注点": "",
                "来源方式": "同事逆向用例JSON",
                "可执行性/待确认事项": str(ext.get("note", "")),
                "id": sid,
                "case_id": cid,
                "case_name": case["name"],
                "scenario_type": kind,
                "declared_type": declared,
                "classification_reason": reason,
                "source_id": document["source_id"],
                "name": document["name"],
                "row": source_refs[0]["line_start"],
                "source_refs": source_refs,
                "source_format": "recovered_usecase_json",
                "source_location": {
                    "format": "json",
                    "file": document["name"],
                    "json_pointer": pointer(path),
                    "case_id": case["id"],
                    "extension_id": ext["id"],
                    "scene_id": ext.get("scene_id"),
                    "line_start": source_refs[0]["line_start"],
                    "line_end": source_refs[-1]["line_end"],
                },
                "context_rows": sorted(
                    {n for ref in context for n in range(ref["line_start"], ref["line_end"] + 1)}
                ),
            }
            records.append(row)
    tests = [
        {
            "id": r["id"],
            "case_id": r["case_id"],
            "name": r["测试名称"],
            "scenario_type": r["scenario_type"],
            "declared_type": r["declared_type"],
            "preconditions": r["前置条件"],
            "trigger": r["触发条件"],
            "expected_result": r["预期结果"],
            "test_data": r["测试数据"],
            "test_steps": r["测试步骤"],
            "source_refs": r["source_refs"],
            "source_location": r["source_location"],
            "classification_reason": r["classification_reason"],
        }
        for r in records
    ]
    return {"cases": cases, "tests": tests, "records": records, "pending": pending}
