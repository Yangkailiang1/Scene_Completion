"""Stable SSD record identities and concern/scenario construction."""

from scene_completion.domain.concern_registry import default_registry
from scene_completion.infrastructure.identity import fingerprint


def unique(values):
    return list({fingerprint(v): v for v in values}.values())


def ident(prefix, *values):
    return prefix + "-" + fingerprint(values)[:24]


def channel():
    return {"concerns": [], "scenarios": [], "pending": []}


def pending(identity, condition, refs=(), **extra):
    return {
        "id": identity,
        "condition": condition,
        "status": "pending",
        "source_refs": list(refs),
        "needs_semantic": False,
        **extra,
    }


def add_concern(
    output,
    bundle,
    channel_name,
    step,
    key,
    target,
    *,
    field=None,
    entity=None,
    condition="",
    refs=(),
    rule_id=None,
):
    definitions = bundle.get("registry", default_registry())["definitions"]
    if (
        key not in definitions
        or not definitions[key].get("enabled", True)
        or key.startswith("global.")
    ):
        return None
    cid = ident(
        channel_name + "-concern",
        bundle["case"]["id"],
        step["id"],
        target,
        key,
        field and field["id"],
        entity,
    )
    previous = next((c for c in output["concerns"] if c["id"] == cid), None)
    if previous:
        previous["source_refs"] = unique(previous["source_refs"] + list(refs))
        return previous
    value = {
        "id": cid,
        "step_id": step["id"],
        "target": target,
        "key": key,
        "label": definitions[key]["label"],
        "field_id": field["id"] if field else None,
        "entity_id": entity,
        "condition": condition or definitions[key]["label"],
        "status": "active",
        "source_refs": list(refs),
    }
    if rule_id:
        value["rule_id"] = rule_id
    output["concerns"].append(value)
    return value


def add_scenario(output, concern, condition, expected, refs, identity=None):
    sid = identity or ident("scenario", concern["id"], condition, expected)
    old = next((s for s in output["scenarios"] if s["id"] == sid), None)
    if old:
        old["source_refs"] = unique(old["source_refs"] + list(refs))
        old["concern_ids"] = list(dict.fromkeys(old["concern_ids"] + [concern["id"]]))
        return old
    value = {
        "id": sid,
        "concern_ids": [concern["id"]],
        **{k: concern.get(k) for k in ("step_id", "target", "key", "field_id", "entity_id")},
        "condition": condition,
        "expected": expected,
        "source_refs": list(refs),
        "status": "active",
    }
    output["scenarios"].append(value)
    return value
