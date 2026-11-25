"""Generate CRUD resource checks and absorb equivalent path validity constraints."""

import re

from scene_completion.domain.concern_templates import scenario_metadata
from scene_completion.domain.ssd import path_resources as paths
from scene_completion.domain.ssd.construction import (
    add_concern,
    add_scenario,
    ident,
    pending,
    unique,
)
from scene_completion.workflow.ssd.resolve.operations import functional_owner


def _references(bundle, unit, kind, commands):
    for cid in unit.get("command_ids") or ([unit["command_id"]] if unit.get("command_id") else []):
        link = bundle["command_bindings"][cid]
        if kind not in link["crud"] or link.get("binding_source") == "step1_fallback":
            continue
        command = commands[cid]
        names = paths.path_parameters(command.get("path"))
        if kind == "create":
            roles = bundle.get("create_path_roles", {}).get(cid, {})
        else:
            roles = {
                name: {"role": role, "reason": "依据已挂载的接口路径层级"}
                for name, role in paths.route_roles(command.get("path")).items()
            }
        for name in names:
            role = roles.get(name) or {"role": "unknown", "reason": "创建路径角色尚未确认"}
            yield {"command_id": cid, "parameter_name": name, **role}


def _rows(bundle, unit, kind, refs):
    target_refs = [ref for ref in refs if ref["role"] == "target"]
    if kind == "create":
        yield target_refs[0] if len(target_refs) == 1 else None, "already_exists"
    if kind in {"update", "delete"} and not target_refs:
        yield None, "missing_resource"
    if kind == "read" and not refs:
        command = next((c for c in bundle["commands"] if c["id"] == unit.get("command_id")), {})
        context = " ".join(str(v or "") for v in (unit["name"], command.get("quote")))
        collection = re.search(r"列表|集合|分页|\blist\b|\bsearch\b", unit["name"], re.I)
        required_hit = re.search(r"至少返回一|不允许(?:返回)?空(?:列表|集合|结果)", context)
        lookup = re.search(r"指定|详情|按.{0,16}(?:ID|编号|标识)查询", context, re.I)
        if required_hit or lookup and not collection:
            yield None, "missing_resource"
    for ref in refs:
        if kind != "create" or ref["role"] not in {"target", "unknown"}:
            yield ref, "missing_resource"


def _atoms(bundle, checks, enabled_keys):
    # Match an entity attribute only via a declared field-to-entity binding.
    aliases, by_field = {}, {}
    for check in checks:
        if not check["resource_reference"] or check["key"] not in enabled_keys:
            continue
        ref = check["resource_reference"]
        by_field.setdefault((ref["command_id"], ref["parameter_name"]), []).append(check)
    moved = set()

    def absorb(atom, targets, key):
        variants = paths.atom_failures({**atom, "concern_key": key})
        eligible = [
            check
            for check in targets
            if not atom.get("applicable_operations")
            or check["crud"] in atom["applicable_operations"]
        ]
        for check in eligible:
            for variant in sorted(variants):
                if (check["default_failure"] == "already_exists") != (variant == "already_exists"):
                    continue
                check["variants"].setdefault(variant, []).extend(atom["source_refs"])
                moved.add(id(atom))

    for step in bundle["steps"]:
        for field in step["data"]:
            targets = by_field.get(
                (field.get("command_id"), field.get("wire_name") or field["name"])
            )
            if (
                not targets
                or field.get("conflicts")
                or field.get("direction") in {"response", "return"}
                or field.get("location") in {"query", "body", "header", "cookie"}
            ):
                continue
            for atom in field["atoms"]:
                absorb(atom, targets, atom["concern_key"])
            if explicit := field.get("entity_binding"):
                identity = (explicit["entity_id"], explicit["attribute"])
                aliases.setdefault(identity, []).append(targets)
    for unit in (bundle.get("field_anchors") or {}).get("units", []):
        candidates = aliases.get((unit["entity"], unit["attribute"]), [])
        if len(candidates) == 1:
            for atom in unit.get("atoms") or [unit]:
                absorb(atom, candidates[0], unit["concern_key"])
    return moved


def generate(bundle, output, enabled_keys):
    """Each row is a CRUD operation, with an optional proven path parameter identity."""
    if "operation_call_units" not in bundle:
        return set()
    commands = {c["id"]: c for c in bundle["commands"]}
    steps = {step["id"]: step for step in bundle["steps"]}
    checks = []
    for unit in bundle["operation_units"]:
        if not functional_owner(unit) or steps[unit["step_id"]]["receiver"]["type"] != "service":
            continue
        for kind in unit["crud"]:
            key = paths.KEYS[kind]
            if key not in enabled_keys:
                continue
            refs = list(_references(bundle, unit, kind, commands))
            for ref in refs:
                if kind == "create" and ref["role"] == "unknown":
                    output["pending"].append(
                        pending(
                            ident(
                                "create-path-role",
                                unit["id"],
                                paths.identity({"resource_reference": ref}),
                            ),
                            f"创建路径参数 {ref['parameter_name']} 的业务角色",
                            unit["source_refs"],
                            step_id=unit["step_id"],
                            reason=ref["reason"],
                        )
                    )
            for ref, variant in _rows(bundle, unit, kind, refs):
                checks.append(
                    {
                        "step_id": unit["step_id"],
                        "target": "receiver",
                        "key": key,
                        "operation_unit_id": unit["id"],
                        "command_id": ref["command_id"] if ref else unit.get("command_id"),
                        "crud": kind,
                        "resource_reference": ref,
                        "default_failure": variant,
                        "variants": {variant: []},
                    }
                )
    moved = _atoms(bundle, checks, enabled_keys)
    units = {unit["id"]: unit for unit in bundle["operation_units"]}
    for check in checks:
        unit = units[check["operation_unit_id"]]
        ref = check["resource_reference"]
        key = check["key"]
        noun = paths.label(ref) if ref else "操作目标"
        call_refs = (
            unique(
                commands[ref["command_id"]]["source_refs"]
                + [
                    r
                    for sid in bundle["command_bindings"][ref["command_id"]]["occurrences"]
                    for r in steps[sid]["source_refs"]
                ]
            )
            if ref
            else unit["source_refs"]
        )
        concern = add_concern(
            output,
            bundle,
            "G",
            steps[unit["step_id"]],
            key,
            "receiver",
            condition=noun + "的存在性",
            refs=unique(call_refs + [r for refs in check["variants"].values() for r in refs]),
            rule_id="crud-resource-v1:" + key,
            operation_unit_id=unit["id"],
            resource_reference=ref,
        )
        if concern is None:
            continue
        details = {
            "scope": "interaction",
            "applicable_operations": [check["crud"]],
            "related_call_step_ids": unit["occurrences"],
        }
        if check["command_id"]:
            details["command_id"] = check["command_id"]
        concern.update(details)
        for variant, evidence in check["variants"].items():
            condition = noun + paths.FAILURES[variant]
            expected = (
                "按约定处理创建目标已存在，避免重复创建"
                if variant == "already_exists"
                else "按约定处理" + condition
            )
            scene = add_scenario(
                output,
                concern,
                condition,
                expected,
                unique(call_refs + evidence),
                ident("scenario-resource", concern["id"], variant),
            )
            scene.update(details, resource_failure=variant)
            scene.update(scenario_metadata(key, variant, "reference_template"))
    bundle["path_resource_checks"] = [
        {**check, "variants": list(check["variants"])} for check in checks
    ]
    return moved
