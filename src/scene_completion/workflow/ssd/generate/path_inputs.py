"""Generate fixed path input checks from the bound SR route."""

from scene_completion.domain.concern_templates import scenario_metadata
from scene_completion.domain.ssd import concern_policy as policy
from scene_completion.domain.ssd import name_inputs
from scene_completion.domain.ssd.construction import add_concern, add_scenario, ident, unique
from scene_completion.domain.ssd.path_resources import path_parameters


def _field_concerns(bundle, output, step, field, key):
    if not field:
        return []
    field_id = field["id"]
    aliases = bundle.get("command_aliases", {})
    alias = aliases.get(field_id, {}).get(key)
    if alias and sum(entry.get(key) == alias for entry in aliases.values()) != 1:
        alias = None
    return [
        row
        for row in output["concerns"]
        if row["key"] == key
        and (
            row.get("field_id") == field_id
            or alias
            and row["step_id"] == step["id"]
            and (row.get("entity_id"), row.get("attribute"))
            == (alias["entity_id"], alias["attribute"])
        )
    ]


def _merge(output, concerns, predicate):
    ids = {row["id"] for row in concerns}
    removed = [
        row
        for row in output["scenarios"]
        if ids.intersection(row["concern_ids"]) and predicate(row)
    ]
    remove_ids = {row["id"] for row in removed}
    output["scenarios"] = [row for row in output["scenarios"] if row["id"] not in remove_ids]
    return removed


def _complete(bundle, output, step, field, identity, refs):
    existing = _field_concerns(bundle, output, step, field, policy.COMPLETENESS)
    alternatives = _merge(output, existing, lambda row: True)
    refs = unique(refs + [ref for row in alternatives for ref in row["source_refs"]])
    parameter = identity["parameter"]
    condition = f"路径参数 {{{parameter}}} 缺失或为空"
    concern = (
        existing[0]
        if existing
        else add_concern(
            output,
            bundle,
            "G",
            step,
            policy.COMPLETENESS,
            "data",
            field=field,
            path_input=identity,
            condition=condition,
            refs=refs,
        )
    )
    if concern is None:
        return
    concern.update(path_input=identity, source_refs=refs, condition=condition)
    scene = add_scenario(
        output,
        concern,
        condition,
        "",
        refs,
        ident("path-input", bundle["case"]["id"], identity, policy.COMPLETENESS),
    )
    scene.update(scenario_metadata(policy.COMPLETENESS, "path_missing", "deterministic_constraint"))


def generate(bundle, output):
    steps = {row["id"]: row for row in bundle["steps"]}
    for command in bundle.get("commands", []):
        names = path_parameters(command.get("path"))
        link = bundle.get("command_bindings", {}).get(command["id"])
        if not names or not link or command.get("conflict"):
            continue
        step = steps[link["primary_step_id"]]
        refs = unique(command.get("source_refs", []) + step.get("source_refs", []))
        identity = {"command_id": command["id"]}
        special = add_concern(
            output,
            bundle,
            "G",
            step,
            policy.PATH_CHARACTERS,
            "data",
            path_input=identity,
            refs=refs,
        )
        for name in names:
            fields = [
                row
                for row in step["data"]
                if row.get("command_id") == command["id"]
                and not row.get("conflicts")
                and name in {row["name"], row.get("wire_name")}
            ]
            explicit_path = [
                row
                for row in step["data"]
                if row.get("command_id") == command["id"]
                and not row.get("conflicts")
                and name_inputs.path_name(row, command) == name
            ]
            if policy.name_characters(bundle) and len(explicit_path) == 1:
                field = explicit_path[0]
            else:
                field = fields[0] if len(fields) == 1 else None
                if (
                    policy.name_characters(bundle)
                    and field
                    and name_inputs.location(field) not in {"path", None}
                ):
                    field = None
            parameter = {**identity, "parameter": name}
            _complete(bundle, output, step, field, parameter, refs)
            if special is None:
                continue
            constraints = _field_concerns(bundle, output, step, field, policy.FIELD)
            keep_declared = (
                policy.name_characters(bundle)
                and "create" in link.get("crud", [])
                and field is not None
                and name_inputs.name_field(field)
            )
            replaced = (
                []
                if keep_declared
                else _merge(output, constraints, lambda row: row.get("input_character_rule"))
            )
            referenced = {cid for row in output["scenarios"] for cid in row["concern_ids"]}
            inactive = {row["id"] for row in constraints} - referenced
            output["concerns"] = [row for row in output["concerns"] if row["id"] not in inactive]
            source = unique(refs + [ref for row in replaced for ref in row["source_refs"]])
            special["source_refs"] = unique(special["source_refs"] + source)
            rules = list(dict.fromkeys(row["input_character_rule"] for row in replaced))
            text = f"路径参数 {{{name}}} 含不符合约定的特殊字符"
            if rules:
                text += "（" + "；".join(rules) + "）"
            scene = add_scenario(
                output,
                special,
                text,
                "",
                source,
                ident("path-input", bundle["case"]["id"], parameter, policy.PATH_CHARACTERS),
            )
            scene.update(
                scenario_metadata(
                    policy.PATH_CHARACTERS, "path_special_characters", "deterministic_constraint"
                ),
                path_input=parameter,
            )
