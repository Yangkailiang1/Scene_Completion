"""Resolve a path resource from independent E/GT evidence before matching."""

import re

from scene_completion.domain.ssd import interface_fields
from scene_completion.domain.ssd import path_resources as paths


def _same_parameter(name, field, condition):
    return name.casefold() == field.casefold() if field else bool(paths.mentions(name, condition))


def prepare(bundle, raw, part):
    kind = paths.failure(part["condition"])
    if (
        not kind
        or "path_resource_checks" not in bundle
        or not ({paths.VALIDITY, *paths.KEYS.values()} & set(part["keys"]))
    ):
        return
    actual = part["failure_step_id"]
    scope = paths.source_scope(bundle, raw, actual)
    parameter = raw.get("parameter") or {}
    field = interface_fields.legacy_name(parameter.get("name") or raw.get("field_name"))
    non_path = parameter.get("location") in {"query", "body", "header", "cookie"}
    named_routes = {
        (command["id"], name)
        for command in bundle["commands"]
        if not non_path and command["id"] in scope
        for name in paths.path_parameters(command["path"])
        if _same_parameter(name, field, part["condition"])
    }
    if not named_routes and not field and raw.get("entity_id") and raw.get("attribute"):
        aliases = {
            (record["command_id"], record.get("wire_name") or record["name"])
            for step in bundle["steps"]
            for record in step["data"]
            if record.get("command_id") in scope
            and not record.get("conflicts")
            and (entity := record.get("entity_binding"))
            and (entity.get("entity_id"), entity.get("attribute"))
            == (raw["entity_id"], raw["attribute"])
        }
        named_routes = {
            (command["id"], name)
            for command in bundle["commands"]
            for name in paths.path_parameters(command["path"])
            if (command["id"], name) in aliases
        }
    role = None
    if not field and not named_routes:
        label = part["condition"]
        if re.search(r"祖先(?:对象|资源)|上级的上级|父级的父级", label):
            role = "ancestor"
        elif re.search(r"父(?:对象|资源|级)|直接上级", label):
            role = "parent"
        elif re.search(r"目标|要(?:删除|更新|创建|查询)的对象|指定的(?:资源|对象)|重复创建", label):
            role = "target"
    if not named_routes and not role:
        if field:
            part["keys"] = [key for key in part["keys"] if not paths.is_existence(key)]
            definition = bundle["registry"]["definitions"].get(paths.VALIDITY, {})
            if (
                definition.get("enabled")
                and paths.VALIDITY not in part["keys"]
                and len(interface_fields.candidates(bundle, actual, raw)) == 1
            ):
                part["keys"].append(paths.VALIDITY)
        elif any(
            check["resource_reference"]
            and check["key"] in part["keys"]
            and check["command_id"] in scope
            for check in bundle["path_resource_checks"]
        ):
            part["resource_issue"] = "原文尚未区分该接口的操作目标与路径依赖对象"
        return
    choices = []
    for check in bundle["path_resource_checks"]:
        ref = check["resource_reference"]
        if not ref:
            continue
        if (
            (ref["command_id"], ref["parameter_name"]) in named_routes
            or role == ref["role"]
            and ref["command_id"] in scope
        ) and (
            (kind == "already_exists") == (check["crud"] == "create" and ref["role"] == "target")
        ):
            choices.append(check)
    keyed = [check for check in choices if check["key"] in part["keys"]]
    choices = keyed or choices
    if len(choices) == 1 and len(named_routes) <= 1:
        part.update(keys=[choices[0]["key"]], resource_check=choices[0], resource_failure=kind)
    elif named_routes or choices or role in {"parent", "ancestor"}:
        part["resource_issue"] = "无法唯一判定路径参数对应的接口、CRUD 或资源角色"


def compatible(part, scenario):
    ref = scenario.get("resource_reference")
    check = part.get("resource_check")
    if check:
        return (
            paths.identity(scenario) == paths.identity(check)
            and scenario.get("operation_unit_id") == check["operation_unit_id"]
            and scenario["key"] == check["key"]
            and scenario.get("resource_failure") == part["resource_failure"]
        )
    key = next((key for key in part["keys"] if paths.is_existence(key)), "")
    return (
        not ref
        and not part.get("resource_issue")
        and not paths.different_failures({"key": key, "condition": part["condition"]}, scenario)
    )


def fallback(check):
    return {
        "step_id": check["step_id"],
        "target": "receiver",
        "key": check["key"],
        "entity_id": None,
        "attribute": None,
        "field_id": None,
        "operation_unit_id": check["operation_unit_id"],
        "resource_reference": check["resource_reference"],
    }


def in_scope(bundle, check, actual):
    if not actual:
        return True
    cid = check["resource_reference"]["command_id"]
    return cid in paths.source_scope(bundle, {}, actual)
