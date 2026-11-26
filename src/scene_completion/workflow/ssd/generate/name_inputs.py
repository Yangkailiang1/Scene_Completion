"""Add a fixed special-character scenario for each confirmed CREATE name input."""

from scene_completion.domain.concern_templates import scenario_metadata
from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd import name_inputs
from scene_completion.domain.ssd.construction import add_concern, add_scenario, ident, unique

VARIANT = "create_name_characters"
EXAMPLES = "SQL 注入特征、HTML 脚本内容或路径穿越特征"
EXPECTED = "按接口约定安全处理异常输入，避免将名称数据解释为指令或路径"


def _add(bundle, output, step, *, field=None, entity=None, command=None, operation_refs=()):
    name = (field.get("wire_name") or field["name"]) if field else "name"
    cid = command["id"] if command else None
    roles = name_inputs.names(field) if field else {"name"}
    if entity:
        roles.add("name")
    refs = unique(
        [
            *operation_refs,
            *step.get("source_refs", []),
            *(command or {}).get("source_refs", []),
            *(field or {}).get("source_refs", []),
            *(entity[1].get("source_refs", []) if entity else []),
        ]
    )
    path_parameter = name_inputs.path_name(field, command) if field and command else None
    path = {"command_id": cid, "parameter": path_parameter} if path_parameter else None
    existing = next(
        (
            scene
            for scene in output["scenarios"]
            if path and scene["key"] == policy.PATH_CHARACTERS and scene.get("path_input") == path
        ),
        None,
    )
    metadata = {"names": sorted(roles), "command_id": cid}
    if field:
        metadata["field_id"] = field["id"]
        if location := name_inputs.location(field):
            metadata["location"] = location
    if entity:
        metadata["entity_id"] = entity[0]
    if existing:
        existing["source_refs"] = unique(existing["source_refs"] + refs)
        for parent in output["concerns"]:
            if parent["id"] in existing["concern_ids"]:
                parent["source_refs"] = unique(parent["source_refs"] + refs)
        if previous := existing.get("name_character_input"):
            metadata["names"] = sorted(roles.union(previous["names"]))
        else:
            existing["condition"] += "（创建名称异常输入示例包括" + EXAMPLES + "）"
        existing["expected"] = EXPECTED
        existing["name_character_input"] = {**existing.get("name_character_input", {}), **metadata}
        existing["generation_rules"] = ["path_parameter", "create_name"]
        return
    parent = add_concern(
        output,
        bundle,
        "G",
        step,
        policy.PATH_CHARACTERS,
        "data",
        field=field,
        entity=entity[0] if entity and not field else None,
        attribute="name" if entity and not field else None,
        refs=refs,
    )
    if not parent:
        return
    scene = add_scenario(
        output,
        parent,
        f"创建操作的 {name} 输入含特殊字符（如{EXAMPLES}）",
        EXPECTED,
        refs,
        ident(
            "create-name-characters",
            bundle["case"]["id"],
            step["id"],
            cid,
            field["id"] if field else entity[0],
        ),
    )
    scene.update(
        scenario_metadata(policy.PATH_CHARACTERS, VARIANT, "deterministic_constraint"),
        name_character_input=metadata,
        generation_rules=["create_name"],
    )
    if cid:
        scene["command_id"] = cid


def _contract_names(bundle, output, step, command, link, refs):
    fields = [
        row
        for row in step["data"]
        if row.get("command_id") == command["id"] and name_inputs.name_field(row)
    ]
    calls = set(link.get("occurrences", [step["id"]]))
    entity_ids = {
        entity
        for call in bundle["steps"]
        if call["id"] in calls and call["direction"] == "request"
        for entity in call["entity_ids"]
    }
    entity_ids.update((field.get("entity_binding") or {}).get("entity_id") for field in fields)
    entities = name_inputs.entity_names(bundle, entity_ids)
    handled = set()
    for field in fields:
        binding = field.get("entity_binding") or {}
        linked = binding.get("entity_id") if binding.get("attribute") == "name" else None
        if not binding and len(entities) == 1:
            linked = next(iter(entities))
        entity = (linked, entities[linked]) if linked in entities else None
        if entity:
            handled.add(linked)
        _add(bundle, output, step, field=field, entity=entity, command=command, operation_refs=refs)
    for entity_id, attribute in entities.items():
        if entity_id not in handled:
            _add(
                bundle,
                output,
                step,
                entity=(entity_id, attribute),
                command=command,
                operation_refs=refs,
            )


def generate(bundle, output):
    steps = {row["id"]: row for row in bundle["steps"]}
    commands = {row["id"]: row for row in bundle.get("commands", [])}
    bindings = bundle.get("command_bindings", {})
    units = bundle.get("operation_call_units", [])
    for unit in units:
        step = steps.get(unit["step_id"])
        if not step or "create" not in unit["crud"] or step["direction"] != "request":
            continue
        if cid := unit.get("command_id"):
            link = bindings.get(cid, {})
            if (
                link
                and cid in commands
                and link.get("binding_source") != "step1_fallback"
                and not commands[cid].get("conflict")
            ):
                _contract_names(
                    bundle, output, step, commands[cid], link, unit.get("source_refs", [])
                )
        else:
            for entity in name_inputs.entity_names(bundle, step["entity_ids"]).items():
                _add(
                    bundle, output, step, entity=entity, operation_refs=unit.get("source_refs", [])
                )
    bound = {
        sid
        for link in bindings.values()
        if link.get("binding_source") != "step1_fallback"
        for sid in link["occurrences"] + link.get("validation_step_ids", [])
    } | {unit["step_id"] for unit in units}
    for sid, result in bundle.get("name_input_operations", {}).items():
        step = steps.get(sid)
        if (
            not step
            or sid in bound
            or step["direction"] != "request"
            or result["context"] != name_inputs.operation_context(step)
            or "create" not in result["crud"]
        ):
            continue
        for entity in name_inputs.entity_names(bundle, step["entity_ids"]).items():
            _add(bundle, output, step, entity=entity)
