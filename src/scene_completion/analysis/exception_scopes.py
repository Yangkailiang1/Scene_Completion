"""Independent source-unit routing. Generated answers never decide E/GT scope."""

from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint

VERSION = "independent-exception-scope-v1"
KINDS = ("sequence", "dependency_consistency", "cascade", "idempotency")


def register():
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
    TASKS["exception-scope"] = ("scene-exception-scope", "异常分析粒度分流")
    INPUT_KEYS["exception-scope"] = {
        "channel",
        "source-records",
        "case-catalogue",
        "entity-index",
    }
    from scene_completion.domain.schema_definitions import BRANCH

    BRANCH["properties"].update(original_id=S, scope_unit_id=S, trigger_condition=S)


def records_from_tests(records):
    return [
        {
            "id": r["id"],
            "case_hint": r.get("case_id") or r.get("case_name"),
            "description": r.get("触发条件") or r.get("description") or r.get("测试名称", ""),
            "expected": r.get("预期结果", ""),
            "source_refs": deepcopy(r.get("source_refs", [])),
        }
        for r in records
        if r.get("scenario_type") == "exception"
    ]


def validate_scope(value, inputs):
    originals = {r["id"]: r for r in inputs["source-records"]}
    entities = {r["id"] for r in inputs["entity-index"]["entities"]}
    cases = {c["id"] for c in inputs["case-catalogue"]}
    seen = set()
    for unit in value["units"]:
        if unit["source_id"] not in originals or not unit["trigger"].strip():
            raise ValueError(
                "scope unit requires a real original source and independent failure trigger"
            )
        if not set(unit["entity_ids"]) <= entities or not set(unit["related_cases"]) <= cases:
            raise ValueError(
                "scope unit uses unknown business entity/use case; entity IDs="
                + str(sorted(entities))
                + "; case IDs="
                + str(sorted(cases))
                + "; supplied="
                + str([unit["entity_ids"], unit["related_cases"]])
            )
        if unit["scope"] == "global" and (
            not unit["global_kind"] or not unit["entity_ids"] or not unit["related_cases"]
        ):
            raise ValueError(
                "global unit needs kind, business entities and related cases; uncertain goes pending"
            )
        if unit["scope"] != "global" and unit["global_kind"] is not None:
            raise ValueError("only global units have a global kind")
        seen.add(unit["source_id"])
    if seen != originals.keys():
        raise ValueError(
            "scope routing must account for every exception source record, including pending"
        )


def interaction_branches(branches, scope):
    originals = {b["id"]: b for b in branches["branches"]}
    return {
        "branches": [
            {
                **deepcopy(originals[u["source_id"]]),
                "id": "scope-" + fingerprint([u["source_id"], u["scope"], u["trigger"]])[:24],
                "original_id": u["source_id"],
                "scope_unit_id": "scope-"
                + fingerprint([u["source_id"], u["scope"], u["trigger"]])[:24],
                "trigger_condition": u["trigger"],
                "description": u["trigger"],
            }
            for u in scope["units"]
            if u["scope"] == "interaction"
        ]
    }


def selected_test_ids(scope):
    return {u["source_id"] for u in scope["units"] if u["scope"] == "interaction"}


def global_records(scope, records, kind=None):
    own = {r["id"]: r for r in records}
    return [
        {**deepcopy(own[u["source_id"]]), "scope_unit": deepcopy(u), "description": u["trigger"]}
        for u in scope["units"]
        if u["scope"] == "global" and (kind is None or u["global_kind"] == kind)
    ]


def canonical_dependencies(value, groups, cases=()):
    """Identity normalization only; never infer an edge or its condition."""
    aliases = {a: g["id"] for g in groups for a in [g["id"], *g["rr_ids"], *g["sr_ids"]]}
    for c in cases:
        if c["id"] in aliases:
            aliases[c["name"]] = aliases[c["id"]]
    result = deepcopy(value)
    for d in result["dependencies"]:
        for k in ("from_case_id", "to_case_id"):
            d[k] = aliases.get(d[k], d[k])
        d["id"] = dependency_identity(d)
    return result


def dependency_identity(d):
    # Several conditions on the same directed business relation are scenarios
    # under one concern, not additional relations.
    return (
        "dependency-"
        + fingerprint(
            [
                d[k]
                for k in (
                    "dependency_type",
                    "from_case_id",
                    "to_case_id",
                    "from_entity_id",
                    "to_entity_id",
                )
            ]
        )[:24]
    )


def inverse_dependencies(records):
    out = {}
    kinds = {"sequence": "order", "dependency_consistency": "consistency", "cascade": "cascade"}
    for r in records:
        u = r["scope_unit"]
        if u["global_kind"] not in kinds:
            continue
        cases = u["related_cases"]
        entities = u["entity_ids"]
        d = {
            "from_case_id": cases[0],
            "to_case_id": cases[-1],
            "from_entity_id": entities[0],
            "to_entity_id": entities[-1],
            "dependency_type": kinds[u["global_kind"]],
            "condition": u["trigger"],
            "obligation": u["trigger"],
            "cascade_group": None,
            "source_refs": r["source_refs"],
        }
        d["id"] = dependency_identity(d)
        if d["id"] in out:
            out[d["id"]]["source_refs"] += d["source_refs"]
        else:
            out[d["id"]] = d
    return list(out.values())


def documents_at_units(documents, records):
    from scene_completion.workflow.task_partitions import _documents_at

    return _documents_at(documents, [ref for r in records for ref in r["source_refs"]])
