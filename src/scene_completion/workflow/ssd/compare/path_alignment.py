"""Identify path validation obligations independently of scenario coverage."""

import re

from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd import interface_fields, name_inputs
from scene_completion.domain.ssd.path_inputs import (
    database_failure,
    declared_character_rule,
    failure_keys,
    injection_risk,
    path_keys,
)
from scene_completion.domain.ssd.path_resources import path_parameters


def field_character_candidates(bundle, source, part, scenarios, fields):
    """A verified input character rule can be checked later in the same flow."""
    if database_failure(part["condition"]):
        return set()
    explicit = interface_fields.command_id(source)
    actual = next(
        (step for step in bundle["steps"] if step["id"] == part.get("failure_step_id")), {}
    )
    if not explicit and not actual.get("receiver", {}).get("external"):
        explicit = actual.get("operation", {}).get("command_id")
    named_commands = _commands_mentioned(bundle, part)
    if explicit and named_commands and explicit not in named_commands:
        return set()
    scope = {explicit} if explicit else named_commands
    declarations = [
        (
            scene,
            fields.get(scene.get("field_id"), {}),
            scene.get("attribute"),
        )
        for scene in scenarios
        if scene.get("input_character_rule") and scene.get("status") == "active"
    ]
    possible = {}
    for scene, field, attribute in declarations:
        condition = part["condition"]
        declared, role = _field_identity(source, condition)
        names = {attribute} if attribute else name_inputs.names(field)
        if not any(
            name == interface_fields.legacy_name(declared) or _mentions(condition, name)
            for name in names
        ):
            continue
        if role and field and name_inputs.location(field) not in {None, role}:
            continue
        command_ids = {scene.get("command_id"), field.get("command_id")} - {None}
        if attribute:
            command_ids.update(
                fields[field_id]["command_id"]
                for field_id, aliases in bundle.get("command_aliases", {}).items()
                if field_id in fields
                and (alias := aliases.get(policy.FIELD))
                and (alias["entity_id"], alias["attribute"]) == (scene.get("entity_id"), attribute)
            )
            command_ids.update(scene.get("related_command_ids", []))
        if scope and not command_ids.intersection(scope):
            continue
        owner = scene.get("field_id") or (scene["entity_id"], attribute)
        possible.setdefault(owner, set()).add(scene["id"])
    return next(iter(possible.values())) if len(possible) == 1 else set()


def _mentions(text, token):
    return bool(
        re.search(r"(?<![A-Za-z0-9_-])" + re.escape(token) + r"(?![A-Za-z0-9_-])", text, re.I)
    )


def _commands_mentioned(bundle, part):
    evidence = [part["condition"], part.get("branch", {}).get("note"), *part["source_evidence"]]
    text = "\n".join(item for item in evidence if isinstance(item, str))
    return {
        command["id"]
        for command in bundle.get("commands", [])
        if _mentions(text, command["id"]) or command.get("path") and command["path"] in text
    }


def _field_identity(source, condition):
    parameter = source.get("parameter") or {}
    declared = parameter.get("name") or source.get("field_name") or source.get("attribute")
    location = parameter.get("location")
    prefix = (declared or "").partition(".")[0]
    if not location and prefix in {"path", "body", "query", "header"}:
        location = prefix
    if not location:
        if re.search(r"请求体|\bbody[.\s]", condition, re.I):
            location = "body"
        elif path_keys(condition) or re.search(r"路径参数|路径中的参数", condition):
            location = "path"
    return declared, location


def name_character_candidates(bundle, source, part, generated):
    """Restrict CREATE name evidence to the one identified input boundary."""
    condition = part["condition"]
    keys = set(part["keys"])
    attack = injection_risk(condition)
    rule = declared_character_rule(condition + part["expected"])
    if (
        not policy.name_characters(bundle)
        or database_failure(condition)
        or not (
            policy.PATH_CHARACTERS in keys or attack and keys & {policy.FIELD, "api.data.format"}
        )
    ):
        return None, None
    declared, location = _field_identity(source, condition)
    if location == "path" and not rule:
        return None, None

    explicit = interface_fields.command_id(source)
    named = _commands_mentioned(bundle, part)
    actual = next(
        (step for step in bundle["steps"] if step["id"] == part.get("failure_step_id")), {}
    )
    bindings = bundle.get("command_bindings", {})
    related = {
        cid
        for cid, link in bindings.items()
        if actual.get("id") in interface_fields.related_steps(link)
    }
    scope = {explicit} if explicit else related or named
    if named and scope:
        scope &= named
        if not scope:
            return [], "原文中的接口与 CREATE 名称参数的调用不一致"
    field_id = source.get("field_id")
    if field_id and not any(
        row["id"] == field_id for step in bundle["steps"] for row in step["data"]
    ):
        field_id = None
    matches = []
    for scene in generated.values():
        data = scene.get("name_character_input")
        if not data or scene.get("status") != "active":
            continue
        if scope and data["command_id"] not in scope:
            continue
        if location == "path" and not scene.get("path_input"):
            continue
        if location and data.get("location") not in {None, location}:
            continue
        if (
            not data["command_id"]
            and actual
            and (
                actual["id"] != scene["step_id"]
                and scene["step_id"] not in actual.get("validates", [])
            )
        ):
            continue
        if source.get("entity_id") and data.get("entity_id") != source["entity_id"]:
            continue
        if field_id:
            same_name = field_id == data.get("field_id")
        elif declared:
            same_name = interface_fields.legacy_name(declared) in data["names"]
        else:
            same_name = any(_mentions(condition, name) for name in data["names"])
        if same_name:
            matches.append(scene)
    if len(matches) > 1:
        return [], "无法唯一确定发生特殊字符异常的 CREATE 名称输入"
    if matches:
        # An explicit attack cue identifies the fixed risk. A distinct declared
        # constraint stays a candidate only when also identified in this excerpt.
        if rule and not attack:
            part["keys"] = sorted(keys - {policy.PATH_CHARACTERS} | {policy.FIELD})
            part["name_rule_only"] = True
            return None, None
        if attack and not rule:
            keys -= {policy.FIELD, "api.data.format"}
        part["keys"] = sorted(keys | {policy.PATH_CHARACTERS})
    return (matches, None) if matches else (None, None)


def candidates(bundle, source, part, generated):
    condition = part["condition"]
    keys = path_keys(condition)
    declared, location = _field_identity(source, condition)
    if location and location != "path":
        return None, None
    inferred = not keys and (
        policy.PATH_CHARACTERS not in part["keys"] or policy.name_characters(bundle)
    )
    if not keys:
        keys = set(part["keys"]) & {policy.COMPLETENESS, policy.PATH_CHARACTERS}
        if inferred:
            keys &= failure_keys(condition)
            if not keys or re.search(
                r"请求体|查询参数|请求头|\b(?:body|query|header)[.\s]", condition
            ):
                return None, None
    bindings = bundle.get("command_bindings", {})
    explicit = interface_fields.command_id(source)
    actual = part.get("failure_step_id")
    commands = interface_fields.commands_at(bindings, actual or source.get("step_ref"), explicit)
    named_commands = _commands_mentioned(bundle, part)
    if named_commands:
        commands &= named_commands
    routes = {
        command["id"]: path_parameters(command.get("path"))
        for command in bundle["commands"]
        if command["id"] in commands and not command.get("conflict")
    }
    routes = {command: names for command, names in routes.items() if names}
    tokens = set(path_parameters(condition))
    if declared:
        tokens.add(interface_fields.legacy_name(declared))
    named_routes = {
        command: {name for name in names if _mentions(condition, name) or name in tokens}
        for command, names in routes.items()
    }
    named_routes = {command: names for command, names in named_routes.items() if names}
    if inferred and not named_routes:
        return None, None
    if tokens:
        named_routes = {command: hits for command, hits in named_routes.items() if tokens <= hits}
        if not named_routes:
            return [], "测试指明的路径参数不存在于对应 SR 接口"
    selected = named_routes or routes
    if len(selected) != 1:
        return [], "无法唯一确认路径参数所属的 SR 接口"
    command, fields = next(iter(selected.items()))
    records = [
        scene
        for scene in generated.values()
        if scene["status"] == "active"
        and scene["key"] in keys
        and (identity := scene.get("path_input"))
        and identity["command_id"] == command
        and identity.get("parameter") in fields
    ]
    if not records:
        return [], "该接口没有已启用的对应路径参数关注点"
    return records, None
