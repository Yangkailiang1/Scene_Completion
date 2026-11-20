"""Field and operation bindings reused by conversion and revisions."""

import json
import re
from copy import deepcopy

from scene_completion.domain.current_scope import (
    COMMAND_OPERATION_PROFILE,
    COMMAND_PROFILES,
    STRUCTURED_PROFILES,
)
from scene_completion.domain.ssd.construction import (
    ident,
    unique,
)

VERSION = "ssd-case-v1"


RULE_VERSION = "ssd-three-scope-rules-v2"  # Existing rule/record identities stay stable.


def _kinds(text, method=None):
    # HTTP reads/deletes stay reads/deletes even when payloads mention a state
    # such as PUBLISHED. Publishing itself may use POST or PUT.
    declared = re.search(
        r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(?:/|https?://)", text, re.I
    )
    method = method.upper() if method else declared[1].upper() if declared else None
    if method in {"GET", "DELETE"}:
        return ["read" if method == "GET" else "delete"]
    if re.search(r"\bpublish\b|发布|激活", text, re.I) or re.search(r"[pP]ublish(?=[A-Z])", text):
        return ["update", "publish"]
    # POST is transport, not necessarily create (search/actions commonly use it).
    if method and method != "POST":
        return {
            "GET": ["read"],
            "POST": ["create"],
            "PUT": ["update"],
            "PATCH": ["update"],
            "DELETE": ["delete"],
        }.get(method, [])
    for pattern, kind in [
        (r"create|创建|新增", "create"),
        (r"compareAndUpdate|update|更新|修改", "update"),
        (r"delete|删除", "delete"),
        (r"listProducts|query|retrieve|查询|检索", "read"),
        (r"display|显示|展示", "display"),
        (r"generate|分析|生成|计算", "process"),
    ]:
        if re.search(pattern, text, re.I):
            return [kind]
    return []


def _field(step_id, value, refs, field=None):
    location, sep, name = value.partition(".")
    if not sep or location not in {
        "header",
        "path",
        "query",
        "body",
        "response",
        "business",
        "storage",
    }:
        location, name = "business", value
    row = {
        "id": ident("field", step_id, location, name),
        "name": name,
        "location": location,
        "type": None,
        "required": None,
        "constraints": [],
        "source_refs": deepcopy(refs),
    }
    if isinstance(field, dict):
        # A supplied per-step field keeps its own declared constraint text; the
        # interface contract below only fills what it actually declares.
        from scene_completion.inputs.structured.colleague_formats import constraints

        row["constraints"] = [
            {**constraint, "source_refs": refs}
            for constraint in field.get("normalized_constraints", [])
        ] or constraints(field.get("constraints") or [], name, refs, field.get("source"))
        if field.get("type"):
            row["type"] = field["type"]
        if field.get("required") is not None:
            row["required"] = field["required"]
    return row


def _enrich_fields(step, contracts):
    contract = contracts.get(step.get("api_id"))
    if not contract:
        return
    incoming = step["direction"] == "request"
    for prop in contract.get("fields", []):
        location = prop.get("location")
        matches = [p for p in step["data"] if p["name"] == prop["name"]]
        if not location and len(matches) == 1:
            location = matches[0]["location"]
        if not location or (location == "response") == incoming:
            continue
        old = next((p for p in matches if p["location"] == location), None)
        if old is None:
            old = _field(step["id"], location + "." + prop["name"], prop.get("source_refs", []))
            step["data"].append(old)
        old["type"] = prop.get("data_type") or prop.get("type") or old.get("type")
        if prop.get("required") is not None:
            old["required"] = prop["required"]
        old["source_refs"] = unique(old["source_refs"] + prop.get("source_refs", []))
        merged = {}
        for rule in old["constraints"] + prop.get("constraints", []):
            signature = ident("constraint", rule["kind"], rule["value"])
            value = merged.setdefault(signature, deepcopy(rule))
            value["source_refs"] = unique(
                value.get("source_refs", []) + rule.get("source_refs", [])
            )
        old["constraints"] = list(merged.values())


def rebind_steps(previous, updated):
    """Reapply API defaults only for changed bindings, retaining manual field edits.

    Both arguments are complete case bundles. The returned copy never mutates
    either input. Manual edits are computed against the old API's default
    contract, so deleted fields stay deleted and changed attributes win over
    the new contract. Unlinking removes defaults without restoring an old API.
    """
    result = deepcopy(updated)
    old_steps = {s["id"]: s for s in previous.get("steps", [])}

    if result.get("analysis_profile") in STRUCTURED_PROFILES:
        from scene_completion.analysis.interactions.field_anchors import anchors
        from scene_completion.domain.ssd_contracts import CRUD

        declared = {e["id"] for e in result.get("entities", [])}
        for step in result["steps"]:
            operation = step["operation"]
            old = (old_steps.get(step["id"]) or {}).get("operation", {})
            if set(step["entity_ids"]) - declared:
                raise ValueError("步骤引用了功能树中不存在的业务实体")
            if not set(operation.get("kinds", [])) <= set(CRUD):
                raise ValueError("步骤操作必须为 create/read/update/delete")
            if operation.get("kinds") != old.get("kinds"):
                operation["kinds_source"] = "manual"
                operation["reason"] = "人工修订"
            step["operation"]["kinds"] = list(dict.fromkeys(operation.get("kinds", [])))
            if result.get("analysis_profile") not in COMMAND_PROFILES:
                step["data"] = []
        if result.get("analysis_profile") in COMMAND_PROFILES:
            from scene_completion.workflow.ssd.shared.command_bindings import attach

            if (
                result.get("analysis_profile") == COMMAND_OPERATION_PROFILE
                and result.get("operation_units") is not None
            ):
                from scene_completion.workflow.ssd.resolve.operations import rebind

                rebind(result, previous)
            else:
                attach(result, {c["id"]: c for c in result["commands"]})
        result["field_anchors"] = anchors(result)
        return result

    def contracts(bundle):
        out = {}
        for api in bundle.get("apis", []):
            out[api["id"]] = api
            if api.get("declared_id"):
                out[api["declared_id"]] = api
        return out

    old_contracts, new_contracts = contracts(previous), contracts(result)

    def field_key(field):
        name = field["name"].casefold() if field["location"] == "header" else field["name"]
        return field["location"], name

    def defaults(step, catalog, observed):
        seed = deepcopy(step)
        # Name-only function-tree attributes use positions already declared by
        # the SSD; this is locating a declaration, not copying manual values.
        seed["data"] = [_field(step["id"], f["location"] + "." + f["name"], []) for f in observed]
        declared = catalog.get(step.get("api_id"), {}).get("fields", [])
        seed["data"] = [
            f
            for f in seed["data"]
            if any(
                p["name"] == f["name"] and (not p.get("location") or p["location"] == f["location"])
                for p in declared
            )
        ]
        _enrich_fields(seed, catalog)
        return {field_key(f): f for f in seed["data"]}

    def comparable(key, value):
        if key == "constraints":
            return sorted(
                (c.get("kind"), json.dumps(c.get("value"), ensure_ascii=False, sort_keys=True))
                for c in value or []
            )
        return value

    for step in result.get("steps", []):
        aliases = {"c": "create", "r": "read", "u": "update", "d": "delete"}
        op = step.setdefault("operation", {})
        submitted_kinds = list(op.get("kinds", []))
        op["kinds"] = list(
            dict.fromkeys(aliases.get(k.lower(), k.lower()) for k in op.get("kinds", []))
        )
        old = old_steps.get(step["id"])
        if old:
            operation = step.setdefault("operation", {})
            before = old.get("operation", {})
            if submitted_kinds != before.get("kinds"):
                operation["kinds_source"] = "manual"
            context_changed = any(
                step.get(k) != old.get(k) for k in ("api_id", "receiver")
            ) or operation.get("name") != before.get("name")
            if context_changed and operation.get("kinds_source") not in {"manual", "declared"}:
                method = new_contracts.get(step.get("api_id"), {}).get("method")
                operation["kinds"] = _kinds(operation.get("name", ""), method) or _kinds(
                    result.get("case", {}).get("name", ""), method
                )
                operation["kinds_source"] = "inferred"
        if old is None or old.get("api_id") == step.get("api_id"):
            continue
        base = defaults(old, old_contracts, old.get("data", []))
        current = {field_key(f): deepcopy(f) for f in step.get("data", [])}
        new = defaults(step, new_contracts, step.get("data", [])) if step.get("api_id") else {}
        # Missing old-default fields are explicit removals, even if the newly
        # selected API contains a field of the same name and position.
        for key in base.keys() - current.keys():
            new.pop(key, None)
        for key, field in current.items():
            prior = base.get(key)
            if prior is None:
                new[key] = field
                continue
            changes = {
                prop: deepcopy(field.get(prop))
                for prop in ("name", "location", "type", "required", "constraints", "default")
                if comparable(prop, field.get(prop)) != comparable(prop, prior.get(prop))
            }
            if changes:
                if key not in new:
                    new[key] = field
                else:
                    new[key].update(changes)
                    new[key]["source_refs"] = unique(
                        new[key].get("source_refs", []) + field.get("source_refs", [])
                    )
        step["data"] = list(new.values())
        for field in step["data"]:
            field["id"] = ident("field", step["id"], field["location"], field["name"])
    return result
