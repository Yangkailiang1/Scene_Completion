"""Task schemas are registered within the domain after base contracts exist."""

from copy import deepcopy

from scene_completion.domain.contracts import (
    INTERACTION,
    REFS,
    S,
    arr,
    enum,
    obj,
)

KINDS = ("sequence", "dependency_consistency", "cascade", "idempotency")

CASE = obj(
    id=S,
    name=S,
    goal=S,
    actors=arr(S),
    layer=enum("RR", "SR"),
    source_ranges=arr(
        obj(
            source_id=S,
            start={"type": "integer", "minimum": 1},
            end={"type": "integer", "minimum": 1},
        )
    ),
    source_refs=REFS,
)


CASE_GROUP = obj(
    id=S,
    rr_ids=arr(S),
    sr_ids=arr(S),
    status=enum("confirmed", "pending"),
    reason=S,
    source_refs=REFS,
)


FUSED_LINK = obj(
    rr_id=S, sr_ids=arr(S), status=enum("confirmed", "pending"), basis=S, source_refs=REFS
)


def register_use_cases():
    from scene_completion.domain.contracts import INPUT_KEYS, SCHEMAS, TASKS

    SCHEMAS.update(
        {
            "use-case-extract": obj(cases=arr(CASE)),
            "use-case-align": obj(groups=arr(CASE_GROUP)),
            "fused-ssd": obj(
                interactions=arr(INTERACTION),
                rr_sr_links=arr(FUSED_LINK),
                pending=arr(obj(interaction_id=S, reason=S, source_refs=REFS)),
            ),
        }
    )
    INPUT_KEYS.update(
        {
            "use-case-extract": {"documents", "layer"},
            "use-case-align": {"rr-cases", "sr-cases"},
            "fused-ssd": {"RR", "SR", "components", "case-group"},
        }
    )
    TASKS.update(
        {
            "use-case-extract": ("scene-use-cases", "用例抽取"),
            "use-case-align": ("scene-use-case-align", "RR/SR用例对应"),
            "fused-ssd": ("scene-fused-ssd", "完整SSD建模"),
        }
    )


def register_test_alignment():
    from scene_completion.domain.contracts import (
        INPUT_KEYS,
        REFS,
        SCHEMAS,
        STR,
        TASKS,
        S,
        arr,
        enum,
        obj,
    )

    case = obj(id=S, name=S, association=STR, source_refs=REFS)
    test = obj(
        id=S,
        case_id=S,
        name=S,
        scenario_type=enum("exception", "normal", "optional", "pending"),
        declared_type=STR,
        preconditions=STR,
        trigger=STR,
        expected_result=STR,
        test_data=STR,
        test_steps=STR,
        source_refs=REFS,
    )
    test["required"] = [k for k in test["required"] if k not in {"test_data", "test_steps"}]
    test["properties"].update(source_location={"type": "object"}, classification_reason=STR)
    case["properties"]["source_case_id"] = STR
    SCHEMAS["test-inventory"] = obj(
        cases=arr(case), tests=arr(test), pending=arr(obj(reason=S, source_refs=REFS))
    )
    SCHEMAS["test-case-align"] = obj(
        matches=arr(
            obj(
                test_case_id=S,
                case_group_id={"type": ["string", "null"]},
                status=enum("confirmed", "pending", "unmatched"),
                basis=S,
                source_refs=REFS,
            )
        )
    )
    INPUT_KEYS.update(
        {
            "test-inventory": {"test-documents"},
            "test-case-align": {"test-inventory", "rr-cases", "sr-cases", "case-groups"},
        }
    )
    TASKS.update(
        {
            "test-inventory": ("scene-test-inventory", "独立测试用例与场景整理"),
            "test-case-align": ("scene-test-case-align", "测试与需求用例对应"),
        }
    )


def register_atomic_steps():
    from scene_completion.domain.contracts import (
        ENRICHED_INTERACTION,
        INPUT_KEYS,
        INTERACTION,
        NULL_S,
        REFS,
        SCHEMAS,
        TASKS,
        S,
        arr,
        enum,
        obj,
    )

    SCHEMAS["interaction-normalize"] = obj(
        steps=arr(
            obj(
                key=S,
                origin_ids=arr(S),
                kind=enum("action", "request", "return"),
                layer=enum("RR", "SR"),
                sender=S,
                receiver=S,
                operation=S,
                request_ref=NULL_S,
                validates=arr(S),
                source_refs=REFS,
            )
        ),
        pending=arr(obj(interaction_id=S, reason=S, source_refs=REFS)),
    )
    TASKS["interaction-normalize"] = ("scene-interaction-normalize", "交互最小步骤规范化")
    INPUT_KEYS["interaction-normalize"] = {
        "candidate",
        "normal-documents",
        "components",
        "case-group",
    }
    for contract in (INTERACTION, ENRICHED_INTERACTION):
        contract["properties"].update(
            source_step_ids=arr(S),
            validates=arr(S),
            execution_order={"type": "integer", "minimum": 1},
        )
    SCHEMAS["fused-ssd"]["properties"]["normalization"] = {"type": "object"}


def register_exception_scopes():
    from scene_completion.domain.contracts import (
        INPUT_KEYS,
        SCHEMAS,
        TASKS,
        S,
        arr,
        enum,
        obj,
    )

    SCHEMAS["exception-scope"] = obj(
        units=arr(
            obj(
                source_id=S,
                trigger=S,
                scope=enum("interaction", "global", "pending"),
                global_kind=enum(None, *KINDS),
                entity_ids=arr(S),
                related_cases=arr(S),
                reason=S,
            )
        )
    )
    SCHEMAS["exception-scope"]["properties"].update(version=S)
    SCHEMAS["existing-locations"] = deepcopy(SCHEMAS["existing-bind"])
    TASKS["existing-locations"] = ("scene-existing-bind", "已有异常实际计分定位")
    INPUT_KEYS["existing-locations"] = {"bindings", "identified-concerns", "fused-ssd"}
    TASKS["exception-scope"] = ("scene-exception-scope", "异常分析粒度分流")
    INPUT_KEYS["exception-scope"] = {
        "channel",
        "source-records",
        "case-catalogue",
        "entity-index",
    }
    from scene_completion.domain.schema_definitions import BRANCH

    BRANCH["properties"].update(original_id=S, scope_unit_id=S, trigger_condition=S)
