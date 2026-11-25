"""Generate and deduplicate positive command field obligations."""

import re

from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, FIRST_CALL_PROFILES
from scene_completion.domain.ssd import concern_policy
from scene_completion.domain.ssd.construction import (
    add_concern,
    add_scenario,
    ident,
    unique,
)
from scene_completion.domain.ssd.interface_fields import INPUT_FIELD_POLICY
from scene_completion.infrastructure.identity import fingerprint


def signature(atom):
    return fingerprint(
        [
            atom["operation"],
            atom.get("value"),
            bool(atom.get("exclusive")),
            atom.get("failure_condition"),
            atom.get("unit"),
            bool(atom.get("nonempty")),
            sorted(atom.get("applicable_operations") or []),
        ]
    )


def generate_fields(bundle, output, moved_atoms):
    """Attach one concern per field/family and merge only fully equivalent atom sets."""
    from scene_completion.domain.concern_templates import scenario_metadata
    from scene_completion.workflow.ssd.generate.fixed import _atom_conditions

    aliases = {}
    directions = {}
    input_fields = bundle.get("interface_field_policy") == INPUT_FIELD_POLICY
    precise_sources = bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
    consolidated = concern_policy.applies(bundle)
    if consolidated:
        _required_bodies(bundle, output)
    for step in bundle["steps"]:
        for field in step["data"]:
            explicit = field.get("entity_binding") or {}
            for key in {a["concern_key"] for a in field["atoms"]}:
                atoms = frozenset(signature(a) for a in field["atoms"] if a["concern_key"] == key)
                identity = (explicit.get("entity_id"), explicit.get("attribute"), key, atoms)
                directions.setdefault(identity, set()).add(field.get("direction"))
    first_call = bundle.get("analysis_profile") in FIRST_CALL_PROFILES
    for step in bundle["steps"]:
        for field in step["data"]:
            if field.get("conflicts"):
                continue
            obligations = {}
            binding = bundle["command_bindings"][field["command_id"]]
            for atom in field["atoms"]:
                if (
                    consolidated
                    and atom["operation"] == "required"
                    and field.get("wire_name") in _BODY_NAMES
                ):
                    continue
                operations = atom.get("applicable_operations") or []
                if id(atom) in moved_atoms or (
                    precise_sources
                    and operations
                    and not set(operations).intersection(binding.get("crud", []))
                ):
                    continue
                obligations.setdefault(atom["concern_key"], []).append(atom)
            for key, atoms in obligations.items():
                atom_refs = unique([ref for atom in atoms for ref in atom["source_refs"]])
                explicit = field.get("entity_binding") or {}
                atoms_identity = frozenset(signature(a) for a in atoms)
                identity = (
                    explicit.get("entity_id"),
                    explicit.get("attribute"),
                    key,
                    atoms_identity,
                )
                candidates = [
                    u
                    for u in bundle["field_anchors"]["units"]
                    if explicit.get("entity_id")
                    and u["entity"] == explicit["entity_id"]
                    and u["attribute"] == explicit.get("attribute")
                    and u["concern_key"] == key
                    and (
                        (input_fields or len(directions[identity]) == 1)
                        and not any(a.get("value_pending") for a in atoms)
                        if first_call
                        else u["step_id"] == step["id"] and not u.get("obligation_scope")
                    )
                    and atoms_identity
                    == {signature(a) for a in u["atoms"] if id(a) not in moved_atoms}
                ]
                mapped = next(
                    (
                        c
                        for c in output["concerns"]
                        if len(candidates) == 1 and c.get("unit_id") == candidates[0]["unit_id"]
                    ),
                    None,
                )
                if mapped:
                    aliases.setdefault(field["id"], {})[key] = {
                        "entity_id": mapped["entity_id"],
                        "attribute": mapped["attribute"],
                    }
                    merged_refs = (
                        atom_refs if precise_sources else unique(field["source_refs"] + atom_refs)
                    )
                    mapped["source_refs"] = unique(mapped["source_refs"] + merged_refs)
                    if first_call:
                        _record_command_sources(mapped, field, include_primary=False)
                    for scene in output["scenarios"]:
                        if mapped["id"] in scene["concern_ids"]:
                            attribute = mapped["attribute"]
                            evidence = (
                                [
                                    ref
                                    for atom in atoms
                                    if scene["condition"]
                                    in {
                                        attribute + "：" + condition
                                        for condition in _atom_conditions(
                                            {**atom, "attribute": attribute}, consolidated
                                        )
                                    }
                                    for ref in atom["source_refs"]
                                ]
                                if precise_sources
                                else merged_refs
                            )
                            scene["source_refs"] = unique(scene["source_refs"] + evidence)
                            if first_call:
                                _record_command_sources(scene, field, include_primary=False)
                    continue
                concern = add_concern(
                    output,
                    bundle,
                    "G",
                    step,
                    key,
                    "data",
                    field=field,
                    refs=atom_refs if precise_sources else field["source_refs"],
                    rule_id="sr-command:" + key,
                )
                if not concern:
                    continue
                _record_command_sources(concern, field)
                for atom in atoms:
                    for condition in _atom_conditions(
                        {**atom, "attribute": field["wire_name"]}, consolidated
                    ):
                        scene = add_scenario(output, concern, condition, "", atom["source_refs"])
                        scene.update(
                            scenario_metadata(key, atom["operation"], "deterministic_constraint"),
                        )
                        _record_command_sources(scene, field)
    bundle["command_aliases"] = aliases


_BODY_NAMES = {"body", "$body", "requestBody", "请求体", "请求报文"}
_BODY_REQUIRED = re.compile(
    r"(?:必须(?:提供|传入|包含)|不可缺少|不得省略)(?:非空)?(?:请求体|请求报文)"
    r"|(?:请求体|请求报文)(?:为必填|必填|不得为空|不能为空|不可为空|不允许为空)"
)


def _required_bodies(bundle, output):
    """An explicit whole-body obligation owns one scenario per command."""
    from scene_completion.domain.concern_templates import scenario_metadata

    steps = {step["id"]: step for step in bundle["steps"]}
    for command in bundle["commands"]:
        command_id = command["id"]
        binding = bundle["command_bindings"].get(command_id)
        if not binding or binding.get("binding_source") == "step1_fallback":
            continue
        step = steps.get(binding["primary_step_id"])
        if not step or step["direction"] != "request":
            continue
        refs = unique(command["source_refs"] + step["source_refs"])
        body_atoms = [
            atom
            for field in step["data"]
            if field.get("command_id") == command_id
            and field["wire_name"] in _BODY_NAMES
            and not field.get("conflicts")
            for atom in field["atoms"]
            if atom["operation"] == "required"
        ]
        text = [str(command.get("quote") or ""), *(r.get("quote") or "" for r in refs)]
        if not (body_atoms or any(_BODY_REQUIRED.search(quote) for quote in text)):
            continue
        body_refs = [ref for atom in body_atoms for ref in atom["source_refs"]]
        concern = add_concern(
            output,
            bundle,
            "G",
            step,
            concern_policy.COMPLETENESS,
            "receiver",
            condition="请求体完整性",
            refs=unique(body_refs + refs),
            operation_unit_id=ident("operation-unit", bundle["case"]["id"], "command", command_id),
        )
        if concern:
            concern["command_id"] = command_id
            scene = add_scenario(
                output,
                concern,
                "必填请求体未提供或为空",
                "按接口约定处理缺少请求体的输入",
                concern["source_refs"],
            )
            scene.update(
                command_id=command_id,
                **scenario_metadata(concern_policy.COMPLETENESS, "empty_body"),
            )


def _record_command_sources(record, field, *, include_primary=True):
    if include_primary:
        record.update(command_id=field["command_id"], call_step_id=field["call_step_id"])
    for key in ("validation_step_ids", "response_step_ids"):
        related = field.get(key)
        if related:
            record[key] = list(dict.fromkeys([*record.get(key, []), *related]))
    if not include_primary:
        record["related_call_step_ids"] = list(
            dict.fromkeys([*record.get("related_call_step_ids", []), field["call_step_id"]])
        )
