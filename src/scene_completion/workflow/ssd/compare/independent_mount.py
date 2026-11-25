"""Bound standalone placements using the case's positive facts and one source."""

import re

from scene_completion.domain.current_scope import AVAILABILITY, current_registry
from scene_completion.domain.ssd import (
    actor_security,
    concern_policy,
    external_databases,
    interface_fields,
    llm_responses,
)
from scene_completion.workflow.ssd.resolve.entity_semantics import ENTITY_KEYS
from scene_completion.workflow.ssd.resolve.operations import (
    functional,
    functional_owner,
    in_operation_scope,
)
from scene_completion.workflow.ssd.shared import binding_targets, failure_context


def database_anchors(bundle, source, actual):
    appearances = external_databases.occurrences(bundle["steps"])
    anchors = {ident: rows[0] for ident, rows in appearances.items()}
    at_actual = {
        ident for ident, rows in appearances.items() if any(s["id"] == actual for s, _ in rows)
    }
    text = source["condition"]
    named = {
        ident
        for ident, (step, target) in anchors.items()
        if any(
            re.search(
                r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])",
                text,
                re.I,
            )
            for name in (ident, step[target]["name"])
            if name and name != "数据库"
        )
    }
    if named and at_actual:
        selected = named & at_actual
    else:
        selected = named or at_actual or anchors.keys()
    return {ident: anchor for ident, anchor in anchors.items() if ident in selected}


def special_character_anchors(bundle, source, actual):
    """Require the actual database boundary or positive evidence naming the database."""
    anchors = database_anchors(bundle, source, actual)
    actual_step = next((s for s in bundle["steps"] if s["id"] == actual), None)
    if actual_step:
        roles = external_databases.roles(actual_step)
        confirmed = {party["id"] for party in roles.values()}
        result = [anchor for ident, anchor in anchors.items() if ident in confirmed]
        receiver = actual_step["receiver"]
        if receiver.get("technology") == "database" and not receiver.get("external"):
            result.append((actual_step, "receiver"))
        return result
    text = source["condition"]
    named = [
        (step, target)
        for step, target in anchors.values()
        if any(
            re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text, re.I)
            for name in (step[target]["id"], step[target]["name"])
            if name and name != "数据库"
        )
    ]
    if named:
        return named
    if len(anchors) == 1 and re.search(r"数据库.{0,18}(?:写入|存储|读取|查询|处理|执行)", text):
        return list(anchors.values())
    return []


def options(
    bundle,
    source,
    keys,
    actual,
    steps,
    entities,
    fields,
    units,
    *,
    failure=None,
    condition=None,
    context=(),
):
    definitions = current_registry(bundle["registry"])["definitions"]
    anchors = {}
    for unit in bundle.get("field_anchors", {}).get("units", []):
        anchors.setdefault(unit["step_id"], set()).add((unit["entity"], unit["attribute"]))
    parameter = source.get("parameter") or {}
    declared_field = parameter.get("name") or source.get("field_name") or source.get("field_id")
    explicit_command = interface_fields.command_id(source)
    links = bundle.get("command_bindings", {})
    matches = (
        {field["id"] for _, field in interface_fields.candidates(bundle, actual, source)}
        if parameter.get("name") or source.get("field_name")
        else set()
    )
    if source.get("field_id"):
        matches.add(source["field_id"])
    requests = failure_context.auth_requests(steps, actual)
    related = {actual, *requests}
    if actual in steps:
        step = steps[actual]
        db_steps = {s["id"]: s for s in bundle["steps"]}
        related.update(
            [
                step.get("parent_id"),
                *step.get("validates", []),
                db_steps[actual].get("delegated_from"),
            ]
        )
    if explicit_command:
        related.update(
            interface_fields.related_steps(links[explicit_command])
            if explicit_command in links
            else []
        )
    result = []

    def add(step_id, key, target, entity_id=None, attribute=None, field_id=None, unit_id=None):
        result.append(
            {
                "step_id": step_id,
                "key": key,
                "target": target,
                "entity_id": entity_id,
                "attribute": attribute,
                "field_id": field_id,
                "operation_unit_id": unit_id,
            }
        )

    database_only = failure in {"database_access", "database_unavailable"}
    if llm_responses.KEY in keys and definitions.get(llm_responses.KEY, {}).get("enabled", True):
        text = condition or source["condition"]
        if llm_responses.failure_variant(text):
            for step, target in llm_responses.placements(
                bundle, text, actual, context=[source["condition"], *context]
            ):
                add(step["id"], llm_responses.KEY, target)
    consolidated = concern_policy.applies(bundle)
    database_keys = (
        {AVAILABILITY} & keys if consolidated else {AVAILABILITY, concern_policy.DATABASE} & keys
    )
    if database_keys:
        for step, target in database_anchors(bundle, source, actual).values():
            for key in sorted(database_keys):
                definition = definitions.get(key, {})
                if definition.get("enabled", True) and definition.get("kind") == "check":
                    add(step["id"], key, target)
    if (
        consolidated
        and concern_policy.DATABASE in keys
        and definitions.get(concern_policy.DATABASE, {}).get("enabled", True)
    ):
        for step, target in special_character_anchors(
            bundle, {**source, "condition": condition or source["condition"]}, actual
        ):
            add(step["id"], concern_policy.DATABASE, target)

    for unit in units:
        if not unit.get("external_crud_owner") or not in_operation_scope(
            unit, actual, explicit_command
        ):
            continue
        for key in sorted(keys):
            definition = definitions.get(key, {})
            if (
                functional(key)
                and definition.get("enabled", True)
                and definition.get("kind") == "check"
                and set(unit["crud"]).intersection(definition["operation_kinds"])
            ):
                add(unit["step_id"], key, "receiver", unit_id=unit["id"])

    for sid, step in steps.items():
        if (actual or explicit_command) and sid not in related:
            continue
        caller = failure_context.request_actor(step)
        for key in sorted(keys):
            definition = definitions.get(key, {})
            if not definition.get("enabled", True) or definition.get("kind") != "check":
                continue
            if key in ENTITY_KEYS:
                if not declared_field:
                    explicit_entity, attr = source.get("entity_id"), source.get("attribute")
                    for entity, attributes in entities.items():
                        if explicit_entity and entity != explicit_entity:
                            continue
                        for attribute in attributes:
                            if (not attr or attribute == attr) and (
                                entity in step["entities"]
                                or (entity, attribute) in anchors.get(sid, ())
                            ):
                                add(sid, key, "entity", entity, attribute)
                if source.get("entity_id") or key == "service.business_attribute_constraint":
                    continue
                for field in fields.values():
                    if (
                        sid in field["related_steps"]
                        and step["direction"] == "request"
                        and field.get("location") != "response"
                        and (not explicit_command or field["command_id"] == explicit_command)
                        and (not declared_field or field["id"] in matches)
                    ):
                        add(sid, key, "interface", field_id=field["id"])
            elif key.startswith("human.") and caller == "human":
                if (
                    consolidated
                    and key == concern_policy.AUTH
                    and concern_policy.subtype(key, condition or source["condition"])
                    == "missing_credential"
                    and concern_policy.optional_auth(
                        bundle, next(s for s in bundle["steps"] if s["id"] == sid)
                    )
                ):
                    continue
                add(sid, key, "sender")
            elif (
                key.startswith("service_relation.")
                and key not in actor_security.SERVICE_KEYS
                and caller == "service"
            ):
                add(sid, key, "receiver")
            elif (
                key == AVAILABILITY
                and not database_only
                and caller
                and step["receiver_external"]
                and step["receiver_technology"] != "database"
            ):
                add(sid, key, "receiver")
            elif (
                not consolidated
                and key == "database.special_characters"
                and step["receiver_technology"] == "database"
                and not step["receiver_external"]
            ):
                add(sid, key, "receiver")
            elif functional(key):
                for unit in units:
                    if (
                        functional_owner(unit)
                        and not unit.get("external_crud_owner")
                        and sid in unit["related_steps"]
                        and step["receiver_id"] == unit["receiver_id"]
                        and set(unit["crud"]).intersection(definition["operation_kinds"])
                    ):
                        add(sid, key, "receiver", unit_id=unit["id"])
    return result


def permitted(binding, candidates, steps, units):
    resolved, note = binding_targets.resolve(binding, steps, units)
    if resolved and resolved in candidates:
        return True, None
    return False, (note or {}).get("reason")


def confirmed_binding(source, part, candidates):
    """Only bypass semantic work when the source explicitly fixes the location."""
    if not (actual := part["failure_step_id"]):
        return candidates[0] if len(candidates) == 1 and part.get("explicit_failure") else None
    at_actual = [candidate for candidate in candidates if candidate["step_id"] == actual]
    candidates = at_actual or candidates
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    if (
        candidate["target"] in {"sender", "receiver"}
        or source.get("entity_id")
        and source.get("attribute")
        or source.get("field_id")
        or (source.get("parameter") or {}).get("name")
        or source.get("field_name")
    ):
        return candidate
    return None
