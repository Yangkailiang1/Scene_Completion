"""Current interaction scope; historical snapshots are never rewritten on read."""

from copy import deepcopy

from scene_completion.domain.ssd import actor_security, concern_policy, interface_fields
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


def current_registry(value, *, consolidated=False, path_policy=True, name_characters=True):
    result = deepcopy(value)
    result["definitions"][AVAILABILITY]["scope"] = "interaction"
    result["definitions"][AVAILABILITY]["description"] = (
        "在实际外部服务交互生成可用性关注点，项目汇总按服务身份与故障类型合并，保留全部调用出处。"
    )
    for key in RETIRED | actor_security.SERVICE_KEYS:
        if key in result["definitions"]:
            result["definitions"][key]["enabled"] = False
    result["profiles"]["base"] = list(
        dict.fromkeys([*result["profiles"].get("base", []), AVAILABILITY])
    )
    result["profiles"]["relation"] = [
        key
        for key in result["profiles"].get("relation", [])
        if key not in actor_security.SERVICE_KEYS
    ]
    result["profiles"]["business_chain"] = []
    result["profiles"]["architecture"] = []
    result["scopes"] = {"interaction": "交互级关注点"}
    if consolidated:
        from scene_completion.domain.concern_templates import reference_catalog, scenario_metadata

        if path_policy:
            from scene_completion.domain.concern_registry import default_registry

            key = concern_policy.PATH_CHARACTERS
            if key not in result["definitions"]:
                result["definitions"][key] = deepcopy(default_registry()["definitions"][key])
            if name_characters:
                result["definitions"][key].update(
                    label="特殊字符",
                    description="检查路径占位符及 CREATE 操作的 name 输入是否包含需安全处理的特殊字符。",
                )
        for key, definition in result["definitions"].items():
            if not concern_policy.enabled(key, path_policy=path_policy):
                definition["enabled"] = False
        result["definitions"][concern_policy.FIELD]["label"] = "字段约束"
        result["reference_templates"] = reference_catalog(consolidated=True)
        if path_policy and name_characters:
            result["reference_templates"]["by_key"][concern_policy.PATH_CHARACTERS].append(
                {
                    **scenario_metadata(
                        concern_policy.PATH_CHARACTERS,
                        "create_name_characters",
                        "reference_template",
                    ),
                    "label": "创建时名称含特殊字符",
                    "condition": "创建操作的 name 输入包含需安全处理的特殊字符",
                    "expected": "按输入约定安全处理，避免将数据解释为指令或路径",
                }
            )
    result["taxonomy_note"] = (
        "交互关注点；外部服务在调用处生成、按服务与故障合并；业务链路退出当前范围。"
    )
    result["analysis_policy"] = POLICY
    result["hash"] = fingerprint({k: v for k, v in result.items() if k != "hash"})
    return result


def excluded_ids(bundle):
    steps = {step["id"]: step for step in bundle["steps"]}
    return {
        row["id"]
        for data in bundle["channels"].values()
        for kind in ("concerns", "scenarios", "pending")
        for row in data.get(kind, [])
        if not allowed(row)
        or (
            concern_policy.applies(bundle)
            and row.get("key")
            and (
                not concern_policy.enabled(
                    row["key"], path_policy=concern_policy.path_inputs(bundle)
                )
                or row["key"] == concern_policy.FIELD
                and interface_fields.output_only(row.get("condition"))
            )
        )
        or (
            row.get("key") in actor_security.SERVICE_KEYS
            or kind != "pending"
            and row.get("status") == "active"
            and not actor_security.in_scope(
                row.get("key"), row.get("target"), steps.get(row.get("step_id"))
            )
        )
    }


def filtered(bundle, *, ordinary=False, isolate=True, historical_security=False):
    result = (
        deepcopy(bundle)
        if isolate
        else {
            **bundle,
            "channels": {name: data.copy() for name, data in bundle["channels"].items()},
            **(
                {"scenario_generation": bundle["scenario_generation"].copy()}
                if "scenario_generation" in bundle
                else {}
            ),
        }
    )
    excluded = set() if historical_security else excluded_ids(bundle)
    for data in result["channels"].values():
        for kind in ("concerns", "scenarios", "pending"):
            data[kind] = [
                r
                for r in data.get(kind, [])
                if allowed(r)
                and r["id"] not in excluded
                and (not ordinary or r.get("key") != AVAILABILITY)
            ]
    ids = {
        c: {k: {r["id"] for r in d[k]} for k in ("concerns", "scenarios", "pending")}
        for c, d in result["channels"].items()
    }
    retained = {c: d["concerns"] | d["scenarios"] for c, d in ids.items()}
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
        if r["id"] not in ids[c][k]
    }
    result["generation_pending"] = [
        i for i in result.get("generation_pending", []) if i not in removed
    ]
    if "scenario_generation" in result:
        result["scenario_generation"]["pending_ids"] = [
            i for i in result["scenario_generation"].get("pending_ids", []) if i not in removed
        ]
    result["scope_exclusions"] = [
        deepcopy(r) if isolate else r
        for data in bundle["channels"].values()
        for kind in ("concerns", "scenarios", "pending")
        for r in data.get(kind, [])
        if not allowed(r) or r.get("id") in excluded
    ]
    result["analysis_policy"] = POLICY
    return result


def case_report(bundle, *, historical_security=False):
    from scene_completion.domain.ssd.metrics import analyze

    full = filtered(bundle, isolate=False, historical_security=historical_security)
    result = analyze(full)
    if any(
        r.get("key") == AVAILABILITY
        for data in full["channels"].values()
        for kind in ("concerns", "scenarios", "pending")
        for r in data[kind]
    ):
        ordinary = analyze(
            filtered(bundle, ordinary=True, isolate=False, historical_security=historical_security)
        )
        for key in ("metrics", "metrics_by_level", "scenario_diagnostic"):
            result[key] = ordinary[key]
    result["analysis_policy"] = POLICY
    return result
