"""Mount each declared entity's constrained attributes at the step that names it.

The behaviour model (``SysOperation.json``) already declares, per node, which
entity that node works on through ``data_ref``. The function tree declares, per
use case, the constrained attributes of each entity. This module joins the two:
an entity reached by a step brings all of its constrained attributes to that
step, and an entity never reached by any step falls back to the use case's first
business request.

A single field travelling through a message never narrows the entity: the
constraint belongs to the entity attribute, not to one field that happens to
appear with it.
"""

import re
from copy import deepcopy

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
        **({"exclusive": True} if atom.get("exclusive") else {}),
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
    units = []
    pending = []
    for entity in bundle.get("entities") or []:
        name = entity["id"]
        constrained = [
            (attribute, attribute.get("atoms") or [])
            for attribute in entity.get("attributes") or []
            if attribute.get("atoms")
        ]
        if not constrained:
            continue
        step, reason = resolve_step(bundle, name)
        if step is None:
            pending.append(
                {
                    "entity": name,
                    "reason": reason,
                    "attributes": [a["name"] for a, _ in constrained],
                }
            )
            continue
        for attribute, atoms in constrained:
            for atom in atoms:
                concern = atom["concern_key"]
                identity = unit_id(case_id, name, attribute["name"], concern)
                existing = next((u for u in units if u["unit_id"] == identity), None)
                if existing is not None:
                    existing["atoms"].append(_atom_row(atom))
                    continue
                units.append(
                    {
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
                        "target": "entity",
                        "role": reason,
                        "direction": step.get("direction"),
                        "sender": _clean(step["sender"]),
                        "receiver": _clean(step["receiver"]),
                        "source_refs": deepcopy(atom.get("source_refs") or []),
                    }
                )
    unique = {}
    for row in units:
        unique.setdefault(row["unit_id"], row)
    return {"version": VERSION, "units": list(unique.values()), "pending": pending}


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
