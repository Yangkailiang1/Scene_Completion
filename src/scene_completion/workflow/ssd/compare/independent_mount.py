"""Bound standalone placements using the case's positive facts and one source."""

import re

from scene_completion.domain.current_scope import AVAILABILITY, current_registry
from scene_completion.domain.ssd import external_databases, interface_fields
from scene_completion.workflow.ssd.resolve.entity_semantics import ENTITY_KEYS
from scene_completion.workflow.ssd.resolve.operations import functional
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


def options(bundle, source, keys, actual, steps, entities, fields, units, *, failure=None):
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
    database_keys = {AVAILABILITY, "database.special_characters"} & keys
    if database_keys:
        for step, target in database_anchors(bundle, source, actual).values():
            for key in sorted(database_keys):
                definition = definitions.get(key, {})
                if definition.get("enabled", True) and definition.get("kind") == "check":
                    add(step["id"], key, target)

    for sid, step in steps.items():
        if (actual or explicit_command) and sid not in related:
            continue
        request = failure_context.auth_request(step)
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
            elif key.startswith("human.") and request == "human.authentication":
                add(sid, key, "sender")
            elif (
                key.startswith("service_relation.") and request == "service_relation.authentication"
            ):
                add(sid, key, "receiver")
            elif (
                key == AVAILABILITY
                and not database_only
                and request
                and step["receiver_external"]
                and step["receiver_technology"] != "database"
            ):
                add(sid, key, "receiver")
            elif (
                key == "database.special_characters"
                and step["receiver_technology"] == "database"
                and not step["receiver_external"]
            ):
                add(sid, key, "receiver")
            elif functional(key):
                for unit in units:
                    if (
                        not unit.get("functional_owner_id")
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
