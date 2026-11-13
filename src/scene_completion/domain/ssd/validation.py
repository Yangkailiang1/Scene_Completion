"""Validation of the shared SSD case result contract."""

from copy import deepcopy

from scene_completion.domain.ssd.matching import PAIRS, semantic_candidates

VERSION = "ssd-case-v1"


def validate(bundle):
    """Validate identities/references; missing semantics stays visible, never fabricated."""
    value = deepcopy(bundle)
    if value.get("version") != VERSION or not value.get("case", {}).get("id"):
        raise ValueError("无效的 SSD 用例结果版本或用例 ID")
    if set(value.get("channels", {})) != {"G", "E", "GT"}:
        raise ValueError("结果必须包含 G、E、GT 三个通道")
    steps = value.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("步骤必须为列表")
    ids = [s.get("id") for s in steps]
    if any(not isinstance(s, str) or not s for s in ids) or len(set(ids)) != len(ids):
        raise ValueError("步骤 ID 必须非空且唯一")
    step_map = dict(zip(ids, steps))
    for n, step in enumerate(steps, 1):
        step["order"] = n
        if step.get("kind") not in {"interaction", "action"}:
            raise ValueError("步骤类型无效")
        for role in ("sender", "receiver"):
            party = step.get(role, {})
            if not party.get("id") or not party.get("name"):
                raise ValueError("步骤必须指定发送方与接收方")
        if step["kind"] == "action" and step["sender"]["id"] != step["receiver"]["id"]:
            raise ValueError("本地 action 的发送方与接收方必须相同")
        if step.get("direction") not in {"request", "return"}:
            raise ValueError("步骤方向无效")
        fields = [f.get("id") for f in step.get("data", [])]
        if any(not f for f in fields) or len(set(fields)) != len(fields):
            raise ValueError("步骤内字段 ID 必须非空且唯一")
        parent = step.get("parent_id")
        if parent:
            request = step_map.get(parent)
            if not request or ids.index(parent) >= n - 1:
                raise ValueError("响应必须位于其请求之后")
            if step.get("direction") == "return" and (
                request.get("direction") != "request"
                or request["sender"]["id"] != step["receiver"]["id"]
                or request["receiver"]["id"] != step["sender"]["id"]
            ):
                raise ValueError("响应与请求参与者不对应")
        for ref in step.get("validates", []):
            if ref not in step_map or ids.index(ref) >= n - 1:
                raise ValueError("本地检查必须引用前面的步骤")
    for channel in ("G", "E", "GT"):
        data = value["channels"][channel]
        for kind in ("concerns", "scenarios", "pending"):
            data.setdefault(kind, [])
            if not isinstance(data[kind], list):
                raise ValueError("通道记录必须为列表")
            record_ids = [r.get("id") for r in data[kind]]
            if any(not isinstance(i, str) or not i for i in record_ids):
                raise ValueError("每条记录必须有稳定 ID")
            if len(set(record_ids)) != len(record_ids):
                raise ValueError("通道内记录 ID 重复")
        concern_ids = {c["id"] for c in data["concerns"]}
        for kind in ("concerns", "scenarios"):
            for row in data[kind]:
                if row.get("status") not in {"active", "pending", "unbound"}:
                    raise ValueError("记录状态无效")
                step = step_map.get(row.get("step_id"))
                if (
                    not step
                    or step.get("binding_issue")
                    or row.get("field_id")
                    and row["field_id"] not in {f["id"] for f in step.get("data", [])}
                ):
                    row["status"] = "unbound"
                    row["binding_issue"] = "原步骤或字段已移除，请重新挂载"
                if row.get("target") not in {"sender", "data", "receiver"}:
                    row["status"] = "unbound"
                    row["binding_issue"] = "请选择发送方、数据或接收方"
                if str(row.get("key", "")).startswith("global."):
                    raise ValueError("本轮不纳入全局关注点")
                if kind == "scenarios" and (
                    not row.get("concern_ids") or not set(row.get("concern_ids", [])) <= concern_ids
                ):
                    row["status"] = "unbound"
                    row["binding_issue"] = "关联关注点已移除，请重新挂载"
    for decision in value.get("decisions", []):
        if (
            decision.get("pair") not in PAIRS
            or decision.get("level") not in {"concern", "scenario"}
            or decision.get("status") not in {"full", "partial", "none"}
        ):
            raise ValueError("匹配判定无效")
        a, b = PAIRS[decision["pair"]]
        key = "concerns" if decision["level"] == "concern" else "scenarios"
        if decision.get("left_id") not in {r["id"] for r in value["channels"][a][key]} or (
            decision.get("right_id") not in {r["id"] for r in value["channels"][b][key]}
        ):
            raise ValueError("匹配判定引用了不存在的记录")
    value["semantic_pending"] = semantic_candidates(value)
    return value
