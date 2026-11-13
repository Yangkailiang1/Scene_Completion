"""Apply scenario eligibility to parsed, source-bound test records."""

import re
from copy import deepcopy

from scene_completion.domain.scenario_types import normal_replay
from scene_completion.inputs.provenance.test_sources import (
    records_for_inputs,
    referenced_record_ids,
)


def normal_replay_record(inputs):
    rows = records_for_inputs(inputs)
    return rows[0] if len(rows) == 1 and normal_replay(rows[0]) else None


def filter_scenarios(value, inputs, task):
    out = deepcopy(value)
    kept = []
    excluded = out.setdefault("excluded", [])
    out["excluded"] = excluded = [
        {k: x[k] for k in ("original_id", "scenario_type", "reason", "source_refs")}
        for x in excluded
    ]
    tests = {r["id"]: r for r in records_for_inputs(inputs)}
    for s in out.get("scenarios", []):
        kind = s.get("scenario_type", "exception")
        reason = "模型明确的场景类型"
        if task == "test-ground-truth":
            ids = referenced_record_ids(s.get("source_refs", []), tests.values())
            kinds = {tests[x]["scenario_type"] for x in ids if x in tests}
            kind = next(iter(kinds)) if len(kinds) == 1 else "pending"
            reason = "测试类型字段严格筛选"
            selected = [tests[x] for x in ids if x in tests]
            if selected and all(normal_replay(r) for r in selected):
                kind = "normal"
                reason = "源表标为异常，但触发仅正常幂等重放且预期返回已有、不重复创建；没有违约失败，不计分，保留原始来源"
        text = s.get("cause", "")
        if task == "exception-generate" and text in {"no_matching_records", "empty_list"}:
            required = [
                r
                for r in inputs.get("normal-rules", {}).get("rules", [])
                if r["interaction_id"] == s["interaction_id"]
                and re.search(
                    r"非空|至少(?:一|1)|必须存在|必须.*匹配|不得为空", r.get("condition", "")
                )
            ]
            if not required:
                kind = "optional"
                reason = "普通集合查询的空结果没有违反非空/必有结果约定，不自动视为异常"
        # A customer's voluntary cancellation and a documented normal fallback
        # aren't violations. Cancellation failure is a distinct real fault.
        if re.search(r"^(?:顾客|用户|商家|开发者)(?:主动)?取消(?:支付|订单|操作)$", text.strip()):
            kind = "normal"
            reason = "普通主动取消，不是失败"
        s["scenario_type"] = kind
        if kind == "exception":
            kept.append(s)
        else:
            excluded.append(
                {
                    "original_id": s["id"],
                    "scenario_type": kind,
                    "reason": reason,
                    "source_refs": s["source_refs"],
                }
            )
    out["scenarios"] = kept
    return out
