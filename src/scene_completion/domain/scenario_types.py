"""Exception-only evaluation eligibility; exclusions remain auditable."""

import re
from copy import deepcopy

PROCESSOR_VERSION = "exception-only-post-response-v1"


def filter_branches(value):
    out = deepcopy(value)
    kept = []
    excluded = out.setdefault("excluded", [])
    out["excluded"] = excluded = [
        {k: x[k] for k in ("original_id", "scenario_type", "reason", "source_refs")}
        for x in excluded
    ]
    for b in out["branches"]:
        kind = b.get("scenario_type", "exception")
        text = b["description"]
        reason = "独立原文分支类型判断"
        normal_cancel = re.search(r"(?:顾客|用户|商家)(?:主动)?取消支付", text) and not re.search(
            r"取消.*(?:失败|错误|拒绝)", text
        )
        normal_empty = (
            re.search(r"无(?:匹配|符合条件)|未匹配", text)
            and re.search(r"空列表|total\s*=\s*0|暂无", text)
            and not re.search(r"应当存在|必须.*(?:商品|记录)|HTTP\s*[45]\d\d", text)
        )
        if normal_cancel or normal_empty:
            kind = "optional"
            reason = "原文明示普通取消或允许的空结果成功替代分支，不是违约失败"
        b["scenario_type"] = kind
        if kind == "exception":
            kept.append(b)
        else:
            excluded.append(
                {
                    "original_id": b["id"],
                    "scenario_type": kind,
                    "reason": reason,
                    "source_refs": b["source_refs"],
                }
            )
    out["branches"] = kept
    return out


def normal_replay(record):
    trigger = record.get("触发条件", "")
    expected = record.get("预期结果", "")
    return bool(
        re.search(r"重复(?:提交|请求)|相同\s*(?:幂等键|idempotencyKey|requestId)", trigger, re.I)
        and not re.search(
            r"失败|错误|异常|失效|冲突|不同|不一致|越权|未|多次|重复(?:创建|扣款|写入|生成)",
            trigger,
        )
        and re.search(r"返回已有.*不重复|幂等命中.*不重复", expected)
    )
