"""Current interaction scope; historical snapshots are never rewritten on read."""

from copy import deepcopy

from scene_completion.infrastructure.identity import fingerprint

POLICY = "interaction-shared-services-v1"
ENTITY_PROFILE = "entity-interaction-v1"
COMMAND_PROFILE = "command-interaction-v2"
COMMAND_OPERATION_PROFILE = "command-interaction-v3"
FIRST_CALL_PROFILES = {COMMAND_PROFILE, COMMAND_OPERATION_PROFILE}
COMMAND_PROFILES = {"command-interaction-v1", *FIRST_CALL_PROFILES}
STRUCTURED_PROFILES = {ENTITY_PROFILE, *COMMAND_PROFILES}
AVAILABILITY = "service.base.availability"
RETIRED = {
    "service_relation.data_isolation",
    "service_relation.cross_service_consistency",
    "global.call_order",
    "global.dependency_consistency",
    "global.cascade_operation",
    "global.idempotency",
}


def allowed(row):
    return row.get("key") not in RETIRED and not str(row.get("key", "")).startswith("global.")


def current_registry(value):
    result = deepcopy(value)
    result["definitions"][AVAILABILITY]["scope"] = "interaction"
    result["definitions"][AVAILABILITY]["description"] = (
        "在实际外部服务交互生成可用性关注点，项目汇总按服务身份与故障类型合并，保留全部调用出处。"
    )
    for key in RETIRED:
        if key in result["definitions"]:
            result["definitions"][key]["enabled"] = False
    result["profiles"]["base"] = list(
        dict.fromkeys([*result["profiles"].get("base", []), AVAILABILITY])
    )
    result["profiles"]["business_chain"] = []
    result["profiles"]["architecture"] = []
    result["scopes"] = {"interaction": "交互级关注点"}
    result["taxonomy_note"] = (
        "交互关注点；外部服务在调用处生成、按服务与故障合并；业务链路退出当前范围。"
    )
    result["analysis_policy"] = POLICY
    result["hash"] = fingerprint({k: v for k, v in result.items() if k != "hash"})
    return result


def filtered(bundle, *, ordinary=False):
    result = deepcopy(bundle)
    for data in result["channels"].values():
        for kind in ("concerns", "scenarios", "pending"):
            data[kind] = [
                r
                for r in data.get(kind, [])
                if allowed(r) and (not ordinary or r.get("key") != AVAILABILITY)
            ]
    retained = {
        c: {r["id"] for k in ("concerns", "scenarios") for r in d[k]}
        for c, d in result["channels"].items()
    }
    result["decisions"] = [
        d
        for d in result.get("decisions", [])
        if d["left_id"] in retained[d["pair"].split("_")[0]]
        and d["right_id"] in retained[d["pair"].split("_")[1]]
    ]
    result["pending"] = [r for r in result.get("pending", []) if allowed(r)]
    removed = {
        r["id"]
        for c, data in bundle["channels"].items()
        for k in ("concerns", "scenarios", "pending")
        for r in data.get(k, [])
        if r["id"] not in {x["id"] for x in result["channels"][c].get(k, [])}
    }
    result["generation_pending"] = [
        i for i in result.get("generation_pending", []) if i not in removed
    ]
    if "scenario_generation" in result:
        result["scenario_generation"]["pending_ids"] = [
            i for i in result["scenario_generation"].get("pending_ids", []) if i not in removed
        ]
    result["scope_exclusions"] = [
        deepcopy(r)
        for data in bundle["channels"].values()
        for kind in ("concerns", "scenarios", "pending")
        for r in data.get(kind, [])
        if not allowed(r)
    ]
    result["analysis_policy"] = POLICY
    return result


def case_report(bundle):
    from scene_completion.domain.ssd.metrics import analyze

    result = analyze(filtered(bundle))
    ordinary = analyze(filtered(bundle, ordinary=True))
    for key in ("metrics", "metrics_by_level", "scenario_diagnostic"):
        result[key] = ordinary[key]
    result["analysis_policy"] = POLICY
    return result
