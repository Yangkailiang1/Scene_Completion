"""Project results use actual dependency/service anchors, never synthetic SSD steps."""

from copy import deepcopy

from scene_completion.domain.project_scopes.matching import PAIRS, binding, semantic_candidates

VERSION = "project-scope-v1"
SCOPES = {"business_chain": "业务链路", "architecture": "项目架构"}
KEYS = {
    "business_chain": {
        "service_relation.data_isolation",
        "global.dependency_consistency",
        "global.call_order",
        "global.cascade_operation",
    },
    "architecture": {"service.base.availability"},
}


def validate(bundle):
    value = deepcopy(bundle)
    scope = value.get("scope", {}).get("id")
    if value.get("version") != VERSION or scope not in SCOPES:
        raise ValueError("无效的项目范围结果")
    if set(value.get("channels", {})) != {"E", "G", "GT"}:
        raise ValueError("项目结果必须包含三个独立通道")
    anchors = value.get("anchors", [])
    ids = [a.get("id") for a in anchors]
    if any(not isinstance(a, str) or not a for a in ids) or len(ids) != len(set(ids)):
        raise ValueError("项目锚点ID必须唯一且非空")
    known_cases = {c["id"] for c in value.get("cases", [])}
    for anchor in anchors:
        if scope == "business_chain":
            if anchor.get("kind") != "dependency" or anchor.get("relation_type") not in {
                "direct",
                "cascade",
            }:
                raise ValueError("业务链路必须使用直接依赖或级联依赖锚点")
            if not anchor.get("from_case_id") or not anchor.get("to_case_id"):
                raise ValueError("业务链路必须指定两端用例")
            if known_cases and not {anchor["from_case_id"], anchor["to_case_id"]} <= known_cases:
                raise ValueError("依赖边引用不存在的用例")
            if anchor["from_case_id"] == anchor["to_case_id"]:
                raise ValueError("业务链路是不同用例之间的依赖")
        elif (
            anchor.get("kind") != "external_service"
            or not anchor.get("name")
            or anchor.get("external") is not True
        ):
            raise ValueError("架构关注点必须挂载到已确认的外部服务")
    amap = {a["id"]: a for a in anchors}
    for channel in ("E", "G", "GT"):
        data = value["channels"][channel]
        for kind in ("concerns", "scenarios", "pending"):
            rows = data.setdefault(kind, [])
            rids = [r.get("id") for r in rows]
            if any(not isinstance(i, str) or not i for i in rids) or len(rids) != len(set(rids)):
                raise ValueError("通道记录必须有唯一稳定ID")
        concerns = {r["id"]: r for r in data["concerns"]}
        for kind in ("concerns", "scenarios"):
            for row in data[kind]:
                if row.get("key") not in KEYS[scope]:
                    raise ValueError("关注点不属于当前项目范围")
                if row.get("status") not in {"active", "pending", "unbound"}:
                    raise ValueError("项目记录状态无效")
                anchor = amap.get(row.get("anchor_id"))
                if not anchor:
                    row.update(
                        status="unbound", binding_issue="原依赖边或外部服务已移除，请重新挂载"
                    )
                if row.get("target") != ("dependency" if scope == "business_chain" else "service"):
                    raise ValueError("项目记录对象与范围不一致")
                if (
                    row["key"] == "global.cascade_operation"
                    and anchor
                    and anchor["relation_type"] != "cascade"
                ):
                    row.update(status="unbound", binding_issue="级联关注点只适用于级联关系")
                if kind == "scenarios" and (
                    not row.get("concern_ids")
                    or any(
                        i not in concerns or binding(concerns[i]) != binding(row)
                        for i in row["concern_ids"]
                    )
                ):
                    row.update(status="unbound", binding_issue="关联关注点已移除或挂载不一致")
    for decision in value.get("decisions", []):
        if (
            decision.get("pair") not in PAIRS
            or decision.get("level") not in {"concern", "scenario"}
            or decision.get("status") not in {"full", "partial", "none"}
        ):
            raise ValueError("项目匹配判定无效")
        left, right = PAIRS[decision["pair"]]
        kind = "concerns" if decision["level"] == "concern" else "scenarios"
        a = next(
            (r for r in value["channels"][left][kind] if r["id"] == decision.get("left_id")), None
        )
        b = next(
            (r for r in value["channels"][right][kind] if r["id"] == decision.get("right_id")), None
        )
        if not a or not b or binding(a) != binding(b):
            raise ValueError("匹配必须引用同一项目锚点与关注点中的两方记录")
    value["semantic_pending"] = semantic_candidates(value)
    return value
