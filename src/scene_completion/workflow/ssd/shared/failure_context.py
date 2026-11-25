"""Separate the source's actual failure step from the canonical display anchor."""

import re
from collections.abc import Mapping

from scene_completion.domain.current_scope import AVAILABILITY
from scene_completion.domain.ssd import actor_security

AUTH_KEYS = {actor_security.AUTHENTICATION}


def explicit_failure(condition, expected):
    """Recognize a narrow set of explicitly worded failures without consulting G."""
    text = condition.strip().rstrip("。.!！")
    response = r"(?:\s*(?:->|→|[,，])\s*(?:返回\s*)?(?:HTTP\s*)?401(?:\s+Unauthorized)?)?"
    if re.fullmatch(
        r"(?:(?:请求头\s*)?Authorization\s*(?:缺失|缺少|未提供|未携带)|"
        r"(?:缺少|未提供|未携带)\s*(?:请求头\s*)?Authorization)" + response,
        text,
        re.I,
    ) and re.search(r"(?<!\d)401(?!\d)", f"{text} {expected}"):
        return "missing_credential", AUTH_KEYS
    if re.fullmatch(
        r"(?:数据库|GaussDB(?:4MySQL)?)\s*(?:不可用|不可达|连接失败|无法连接)", text, re.I
    ):
        return "database_unavailable", {AVAILABILITY}
    if re.fullmatch(r"(?:数据库|GaussDB(?:4MySQL)?)\s*访问异常", text, re.I):
        return "database_access", {AVAILABILITY}
    return None, set()


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

    resume = raw.get("resume_at_main") or context.get("resume_at_main")

    # A branch boundary or hint can point to a different step from the failure.
    declared_id = (
        declared.get("step_id") or declared.get("ref") or declared.get("id")
        if isinstance(declared, Mapping)
        else declared
    )
    actual = _lookup(bundle["steps"], declared_id)
    if legacy and not actual:
        anchor = extension.get("after") if isinstance(extension, Mapping) else None
        actual = _lookup(bundle["steps"], step_ref or anchor)
    return {
        "failure_step_id": actual,
        "failure_step_hint": (
            hint or (declared if not actual else None) or step_ref or extension or resume
        ),
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


def request_actor(step):
    return actor_security.request_actor(
        step["direction"],
        step["kind"],
        step["sender_id"],
        step["sender_kind"],
        step["receiver_id"],
        step["receiver_kind"],
    )


def request_actors(steps, step_id):
    step = steps.get(step_id)
    if not step:
        return {}
    if actor := request_actor(step):
        return {step_id: actor}
    related = [
        steps[ref] for ref in [step.get("parent_id"), *step.get("validates", [])] if ref in steps
    ]
    return {item["id"]: actor for item in related if (actor := request_actor(item))}


def auth_request(step):
    return actor_security.AUTHENTICATION if request_actor(step) == "human" else None


def auth_requests(steps, step_id):
    return {
        step_id: actor_security.AUTHENTICATION
        for step_id, actor in request_actors(steps, step_id).items()
        if actor == "human"
    }


def service_security(steps, step_id):
    return set(request_actors(steps, step_id).values()) == {"service"}


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
