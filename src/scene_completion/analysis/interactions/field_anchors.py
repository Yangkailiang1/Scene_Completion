"""Select one display anchor for each stable entity obligation."""

import re
from copy import deepcopy

from scene_completion.domain.current_scope import FIRST_CALL_PROFILES, STRUCTURED_PROFILES
from scene_completion.infrastructure.storage import fingerprint

VERSION = "field-anchors-v3-sysoperation-entities"

CHECK_PROSE = re.compile(r"校验|检查|核对|验证|判断|ensure|validate|check", re.I)


def _clean(party):
    return {"name": party["name"], "position": party.get("position") or ""}


def business_steps(steps):
    """Ordered steps that carry a business interaction, excluding returns."""
    return [
        step
        for step in sorted(steps, key=lambda s: s.get("order", 0))
        if step.get("direction") != "return"
    ]


def entry_step(steps):
    """The first business request: where a use case actually begins."""
    ordered = business_steps(steps)
    for step in ordered:
        if step.get("kind") != "action":
            return step
    return ordered[0] if ordered else None


def check_steps(steps, entity):
    """Local steps whose own prose says they check this entity."""
    found = []
    for step in business_steps(steps):
        if step.get("kind") != "action":
            continue
        text = (step.get("operation") or {}).get("name", "")
        if not CHECK_PROSE.search(text):
            continue
        if entity in (step.get("entity_ids") or []) or re.search(
            r"(?<![A-Za-z0-9_])" + re.escape(entity) + r"(?![A-Za-z0-9_])", text
        ):
            found.append(step)
    return found


def entity_steps(steps, entity):
    """Every step whose ``data_ref`` reaches this entity."""
    return [step for step in business_steps(steps) if entity in (step.get("entity_ids") or [])]


def unit_id(case_id, entity, attribute, concern_key):
    return "unit-" + fingerprint([case_id, entity, attribute, concern_key])[:24]


def _atom_row(atom):
    return {
        "operation": atom.get("operation"),
        "value": atom.get("value"),
        "value_pending": atom.get("value_pending"),
        **{
            k: atom[k]
            for k in ("exclusive", "failure_condition", "applicable_operations")
            if k in atom
        },
        "source_refs": deepcopy(atom.get("source_refs") or []),
    }


def resolve_step(bundle, entity):
    """The single interaction an entity's constraints mount on.

    The first business step, in declared order, whose ``data_ref`` reaches this
    entity. Later steps naming the same entity do not mount the constraints
    again: one entity attribute is one concern inside a use case, however many
    messages happen to carry the entity.

    Falls back to the use case's first business request only when no step names
    the entity at all; reports the reason when nothing can host it.
    """
    reached = entity_steps(bundle.get("steps") or [], entity)
    if reached:
        return reached[0], "首个声明该实体的交互"
    entry = entry_step(bundle.get("steps") or [])
    if entry is None:
        return None, "用例没有可挂载的业务步骤"
    return entry, "用例首个业务请求"


def anchors(bundle):
    """Map every constrained entity attribute to one step."""
    case_id = bundle["case"]["id"]
    units = {}
    pending = []
    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    steps = bundle.get("steps") or []
    first_call = bundle.get("analysis_profile") in FIRST_CALL_PROFILES
    entity_locations = _entity_locations(bundle) if first_call else {}
    for entity in bundle.get("entities") or []:
        name = entity["id"]
        for attribute in entity.get("attributes") or []:
            for atom in attribute.get("atoms") or []:
                operation_step = None
                if first_call:
                    step, reason, operation_step = _first_entity_anchor(
                        entity_locations.get(name, []), atom
                    )
                elif entity_only:
                    step, reason, operation_step = _entity_anchor(
                        steps, name, attribute["name"], atom
                    )
                else:
                    step, reason = resolve_step(bundle, name)
                if step is None:
                    pending.append(
                        {"entity": name, "reason": reason, "attributes": [attribute["name"]]}
                    )
                    continue
                concern = atom["concern_key"]
                identity = unit_id(case_id, name, attribute["name"], concern)
                if entity_only and atom.get("applicable_operations"):
                    identity = (
                        "unit-"
                        + fingerprint([identity, sorted(atom["applicable_operations"])])[:24]
                    )
                if identity in units:
                    row = _atom_row(atom)
                    if row not in units[identity]["atoms"]:
                        units[identity]["atoms"].append(row)
                    continue
                units[identity] = {
                    "unit_id": identity,
                    "case_id": case_id,
                    "entity": name,
                    "attribute": attribute["name"],
                    "concern_key": concern,
                    "operation": atom.get("operation"),
                    "value": atom.get("value"),
                    "value_pending": atom.get("value_pending"),
                    "atoms": [_atom_row(atom)],
                    "step_id": step["id"],
                    **({"operation_step_id": operation_step["id"]} if operation_step else {}),
                    **(
                        {"obligation_scope": sorted(atom["applicable_operations"])}
                        if entity_only and atom.get("applicable_operations")
                        else {}
                    ),
                    "target": "entity",
                    "role": reason,
                    "direction": step.get("direction"),
                    "sender": _clean(step["sender"]),
                    "receiver": _clean(step["receiver"]),
                    "source_refs": deepcopy(atom.get("source_refs") or []),
                }
    return {"version": VERSION, "units": list(units.values()), "pending": pending}


def _entity_locations(bundle):
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    bindings = bundle.get("command_bindings", {})
    by_id = {step["id"]: step for step in steps}
    associated = {}
    for step in steps:
        entities = set(step.get("entity_ids", []))
        entities.update(
            binding["entity_id"]
            for field in step.get("data", [])
            if (binding := field.get("entity_binding")) and binding.get("entity_id")
        )
        for cid, command in bindings.items():
            participants = [
                *command["occurrences"],
                *command.get("validation_step_ids", []),
                *command.get("response_step_ids", []),
            ]
            if step["id"] in participants:
                for entity in entities:
                    associated.setdefault(entity, set()).add(cid)
    result = {}
    for entity in bundle.get("entities", []):
        name = entity["id"]
        explicit = [step for step in steps if name in step.get("entity_ids", [])]
        if any("entity_ids" in link for link in bindings.values()):
            applicable = [link for link in bindings.values() if name in link.get("entity_ids", [])]
            if applicable:
                result[name] = sorted(
                    [
                        {
                            **by_id[link["primary_step_id"]],
                            "interface_owner": True,
                            "operation": {
                                **by_id[link["primary_step_id"]]["operation"],
                                "kinds": link.get("crud", []),
                            },
                        }
                        for link in applicable
                    ],
                    key=lambda step: step["order"],
                )
                continue
            result[name] = explicit
            continue
        primary_steps = [
            by_id[bindings[cid]["primary_step_id"]] for cid in associated.get(name, [])
        ]
        result[name] = sorted(primary_steps, key=lambda step: step["order"]) + explicit
    return result


def _first_entity_anchor(steps, atom):
    kinds = set(atom.get("applicable_operations") or [])
    if atom["operation"] in {"conditional_range", "state_equals"} and not kinds:
        kinds = {"create", "update"}
    step = next(
        (s for s in steps if not kinds or kinds.intersection(s["operation"]["kinds"])), None
    )
    if step is None:
        return None, "实体约束缺少明确出现或适用操作", None
    reason = (
        "首个相关接口调用"
        if step.get("interface_owner") or step["operation"].get("command_id")
        else "实体首次出现"
    )
    return step, reason, step if kinds else None


def _entity_anchor(steps, entity, attribute, atom):
    candidates = check_steps(steps, entity)
    relevant = []
    general = []
    name = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(attribute) + r"(?![A-Za-z0-9_])", re.I)
    data_terms = re.compile(r"参数|字段|格式|有效|完整|约束|必填|入参|input|field|attribute", re.I)
    for step in candidates:
        text = step["operation"]["name"] + " " + step.get("description", "")
        declared = {
            f.rsplit(".", 1)[-1]
            for ref in step.get("entity_refs", [])
            if ref["entity"] == entity
            for f in ref["fields"]
            if isinstance(f, str)
        }
        if name.search(text) or attribute in declared:
            relevant.append(step)
        elif not declared and data_terms.search(text):
            general.append(step)
    applicable = set(atom.get("applicable_operations") or [])
    if atom["operation"] in {"conditional_range", "state_equals"} and not applicable:
        applicable = {"create", "update"}
    operation_step = (
        next(
            (
                s
                for s in entity_steps(steps, entity)
                if applicable.intersection(s["operation"]["kinds"])
            ),
            None,
        )
        if applicable
        else None
    )
    if applicable and not operation_step:
        return None, "实体约束没有已确认的适用操作", None
    entry = entry_step(steps)
    validation = (relevant or general or [None])[0]
    if validation:
        return validation, "明确校验步骤", operation_step
    return entry, "用例首个业务请求", operation_step


def validate(value, inputs):
    """Every unit must name a real step and a registered concern."""
    from scene_completion.domain.concern_registry import registry

    definitions = registry()["definitions"]
    steps = {s["id"] for s in inputs.get("steps") or []}
    seen = set()
    for row in value.get("units") or []:
        if row["step_id"] not in steps:
            raise ValueError("约束挂载引用了不存在的步骤：" + row["step_id"])
        if row["concern_key"] not in definitions:
            raise ValueError("约束挂载引用了未知关注点：" + row["concern_key"])
        if row["unit_id"] in seen:
            raise ValueError("同一实体约束被重复挂载：" + row["unit_id"])
        seen.add(row["unit_id"])
    return value
