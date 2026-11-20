"""Separate the source's actual failure step from the canonical display anchor."""

from collections.abc import Mapping

AUTH_KEYS = {"human.authentication", "service_relation.authentication"}


def _lookup(steps, label):
    if not isinstance(label, str) or not label.strip():
        return None
    label = label.strip()
    if any(step["id"] == label for step in steps):
        return label
    aliases = [step["id"] for step in steps if label in step.get("aliases", [])]
    return aliases[0] if len(aliases) == 1 else None


def location(bundle, source, *, legacy=False):
    raw = source.get("raw") or {}
    context = source.get("evidence_context") or {}
    declared = source.get("failure_step_id") or raw.get("failure_step_id")
    hint = source.get("failure_step_hint") or raw.get("failure_step_hint")
    step_ref = source.get("step_ref") or raw.get("step_ref")
    extension = raw.get("extend_at_main") or context.get("extend_at_main")

    # An extension boundary locates a branch in the flow. It can be before or
    # after the failing operation and cannot by itself certify that operation.
    def explicit_id(value):
        if isinstance(value, Mapping):
            return value.get("step_id") or value.get("ref") or value.get("id")
        return value

    actual = _lookup(bundle["steps"], explicit_id(declared)) or _lookup(
        bundle["steps"], explicit_id(hint)
    )
    if legacy and not actual:
        anchor = extension.get("after") if isinstance(extension, Mapping) else None
        actual = _lookup(bundle["steps"], step_ref or anchor)
    return {
        "failure_step_id": actual,
        "failure_step_hint": hint or (declared if not actual else None) or step_ref or extension,
    }


def branch_context(source):
    supplied = source.get("evidence_context")
    if isinstance(supplied, Mapping):
        return dict(supplied)
    raw = source.get("raw") or {}
    context = {
        key: raw[key]
        for key in ("ID", "name", "scenario_kind", "extend_at_main", "resume_at_main", "note")
        if raw.get(key)
    }
    declared = [
        {key: ref[key] for key in ("document", "doc", "quote") if ref.get(key)}
        for ref in raw.get("source_refs") or []
        if isinstance(ref, Mapping) and ref.get("quote")
    ]
    if declared:
        context["declared_excerpts"] = declared
    participants = raw.get("participant")
    if isinstance(participants, Mapping):
        context["participants"] = {
            key: {k: value[k] for k in ("name", "kind", "type", "element_type") if k in value}
            for key, value in participants.items()
            if isinstance(value, Mapping)
        }
    for kind in ("system_event", "interaction", "action", "system_response"):
        nodes = raw.get(kind) or []
        if nodes:
            context[kind] = [
                {
                    key: node[key]
                    for key in (
                        "ID",
                        "id",
                        "sender",
                        "receiver",
                        "executor",
                        "direction",
                        "message",
                        "content",
                    )
                    if key in node
                }
                for node in (nodes if isinstance(nodes, list) else [nodes])
                if isinstance(node, Mapping)
            ]
    pointers = [
        {"document_id": ref["document_id"], "json_pointer": ref["json_pointer"]}
        for ref in source.get("source_refs", [])
        if ref.get("json_pointer")
    ]
    if pointers:
        context["source_pointers"] = pointers
    return context


def auth_request(step):
    if (
        step["direction"] != "request"
        or step["sender_id"] == step["receiver_id"]
        or step["receiver_kind"] != "service"
    ):
        return None
    if step["sender_kind"] == "human":
        return "human.authentication"
    return "service_relation.authentication"


def auth_requests(steps, step_id):
    step = steps.get(step_id)
    if not step:
        return {}
    if key := auth_request(step):
        return {step_id: key}
    related = [
        steps[ref] for ref in [step.get("parent_id"), *step.get("validates", [])] if ref in steps
    ]
    return {item["id"]: key for item in related if (key := auth_request(item))}


def annotate(scene, loc, reason=None):
    actual = loc["failure_step_id"]
    if actual:
        scene.setdefault("failure_step_id", actual)
        scene["failure_step_ids"] = list(
            dict.fromkeys([*scene.get("failure_step_ids", []), actual])
        )
    elif not scene.get("failure_step_id"):
        scene["failure_step_pending"] = True
    if scene.get("failure_step_id"):
        scene.pop("failure_step_pending", None)
    if hint := loc["failure_step_hint"]:
        scene.setdefault("failure_step_hint", hint)
    if reason and (actual or not scene.get("failure_step_id")):
        scene["failure_step_reason"] = reason
