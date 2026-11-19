"""Project only actual SR commands and their data obligations onto SSD steps."""

import re
from copy import deepcopy

from scene_completion.analysis.concerns.constraint_atoms import normalize_rules
from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, FIRST_CALL_PROFILES
from scene_completion.domain.ssd.construction import (
    add_concern,
    add_scenario,
    ident,
    pending,
    unique,
)
from scene_completion.infrastructure.identity import fingerprint

LOCATIONS = {
    "路径参数": "path",
    "查询参数": "query",
    "请求头": "header",
    "请求体": "body",
    "成功响应": "response",
}
_HTTP = re.compile(r"\b(GET|HEAD|POST|PUT|PATCH|DELETE)\s+(/[^\s`，。；]+)", re.I)


def _location(row):
    if row.get("location") in LOCATIONS.values():
        return row["location"]
    prefix, _, _ = row["name"].partition(".")
    if prefix in LOCATIONS.values():
        return prefix
    section = (row.get("source") or {}).get("section") or ""
    return next((loc for label, loc in LOCATIONS.items() if label in section), None)


def catalogue(sources, tree, path, case_id, case_name, *, selected=None):
    """Bind SR field declarations to their same-use-case command metadata."""
    functions = list(enumerate((tree or {}).get("functions", [])))
    hits = [(i, f) for i, f in functions if (f.get("functionId") or f.get("ucId")) == case_id]
    hits = hits or [(i, f) for i, f in functions if f.get("name") == case_name]
    if selected is not None:
        hits = selected
    if len(hits) != 1:
        return {}
    i, function = hits[0]
    source = sources.add(path)
    commands = {}
    rr = {}
    if selected is not None:
        for index, entry in enumerate((function.get("rrLayer") or {}).get("commands", [])):
            if entry.get("apiId"):
                rr.setdefault(entry["apiId"], []).append((index, entry))
    for j, raw in enumerate((function.get("srLayer") or {}).get("commands", [])):
        command_id = raw["apiId"]
        if command_id in commands:
            raise ValueError("SR 命令编号重复：" + command_id)
        pointer = f"/functions/{i}/srLayer/commands/{j}"
        declaration = raw.get("source") or {}
        original = sources.original([declaration])
        rr_refs, donors = [], rr.get(command_id, [])
        for index, item in donors:
            origin = item.get("source") or {}
            rr_refs.extend(
                [
                    sources.traced_ref(source, f"/functions/{i}/rrLayer/commands/{index}", origin),
                    *sources.original([origin]),
                ]
            )
        conflict = len(donors) > 1
        donor = donors[0][1] if len(donors) == 1 else {}
        for key in ("method", "path"):
            ours, theirs = raw.get(key), donor.get(key)
            if (
                ours
                and theirs
                and (ours.upper() != theirs.upper() if key == "method" else ours != theirs)
            ):
                conflict = True
        method = raw.get("method") or (donor.get("method") if not conflict else None)
        address = raw.get("path") or (donor.get("path") if not conflict else None)
        # A resolved SR reference can supply a literal method and path. RR is
        # useful as existing evidence and does not define an SR interface.
        facts = {
            match.groups()
            for ref in original
            if ref.get("origin", {}).get("role") == "SR"
            for match in _HTTP.finditer(ref["quote"])
        }
        interpreted = {
            (verb.upper(), route)
            for verb, route in facts
            if (not method or verb.upper() == method.upper()) and (not address or route == address)
        }
        if len(interpreted) == 1:
            found_method, found_path = next(iter(interpreted))
            method, address = method or found_method, address or found_path
        fields = []
        for k, row in enumerate(raw.get("attributes", [])):
            location = _location(row)
            name = row["name"].removeprefix(f"{location}.")
            origin = row.get("source") or {}
            attribute_pointer = f"{pointer}/attributes/{k}"
            rules = row.get("constraints") or []
            if selected is not None:
                refs, rule_refs, tags, tag_refs = sources.attribute_sources(
                    source, attribute_pointer, row
                )
                facts = normalize_rules(
                    rules,
                    name,
                    refs,
                    tags=tags,
                    data_type=row.get("type"),
                    entity_only=True,
                    rule_refs=rule_refs,
                    tag_refs=tag_refs,
                )
            else:
                tags = row.get("tags") or []
                refs = unique(
                    [
                        sources.traced_ref(source, attribute_pointer, origin),
                        *sources.original([origin]),
                    ]
                )
                facts = normalize_rules(
                    [], name, refs, tags=tags, data_type=row.get("type"), entity_only=True
                )
                for n, rule in enumerate(rules):
                    evidence = refs
                    if isinstance(rule, dict) and rule.get("source"):
                        evidence = unique(
                            [
                                sources.traced_ref(
                                    source, f"{attribute_pointer}/constraints/{n}", rule["source"]
                                ),
                                *sources.original([rule["source"]]),
                                *refs,
                            ]
                        )
                    inferred = normalize_rules([rule], name, evidence, entity_only=True)
                    for key in ("items", "unresolved"):
                        facts[key].extend(inferred[key])
            fields.append(
                {
                    "name": name,
                    "wire_name": row.get("wire_name") or name,
                    "location": location,
                    "type": row.get("type"),
                    "entity_binding": row.get("entity_binding"),
                    "required": True if "必填" in tags else None,
                    "constraints": [],
                    "rule_texts": [
                        rule.get("rule", "") if isinstance(rule, dict) else rule for rule in rules
                    ],
                    "atoms": facts["items"],
                    "unresolved": facts["unresolved"],
                    "source_refs": refs,
                }
            )
        if len({(f["location"], f["name"]) for f in fields}) != len(fields):
            raise ValueError("SR 接口字段位置与名称重复：" + command_id)
        commands[command_id] = {
            "id": command_id,
            "name": raw.get("name") or donor.get("name") or command_id,
            **({"conflict": "RR／SR 命令的唯一性、方法或路径有冲突"} if conflict else {}),
            "method": method.upper() if method else None,
            "path": address,
            "service": raw.get("service"),
            "quote": "\n".join(
                dict.fromkeys(
                    [ref["quote"] for ref in original if ref.get("origin", {}).get("role") == "SR"]
                    + ([str((donor.get("source") or {}).get("quote") or "")] if donor else [])
                )
            ).strip(),
            "authentication": raw.get("authentication"),
            "fields": fields,
            "source_refs": unique(
                [sources.traced_ref(source, pointer, declaration), *original, *rr_refs]
            ),
        }
    return commands


def _pick(step, commands):
    declared = step.get("api_id") or step.get("declared_command") or step.get("call_command_id")
    text = step["operation"]["name"]
    operation = step["operation"]
    observed = {(m.upper(), p) for m, p in _HTTP.findall(text)}
    if operation.get("http_method") and operation.get("http_path"):
        observed.add((operation["http_method"].upper(), operation["http_path"]))
    if declared:
        command = commands.get(declared)
        if not command:
            return None
        if command["service"] and command["service"] not in {
            step["receiver"]["id"],
            step["receiver"]["name"],
        }:
            return None
        if (
            command["method"]
            and command["path"]
            and observed
            and (command["method"], command["path"]) not in observed
        ):
            return None
        return declared
    direct = [
        cid
        for cid, row in commands.items()
        if (row["method"], row["path"]) in observed
        and (
            not row["service"]
            or row["service"] in {step["receiver"]["id"], step["receiver"]["name"]}
        )
    ]
    if not direct and not observed:
        evidence = " ".join(
            ref.get("quote", "") for ref in step["source_refs"] if ref.get("kind") == "origin"
        )
        direct = [
            cid
            for cid in commands
            if re.search(r"(?<![\w-])" + re.escape(cid) + r"(?![\w-])", evidence)
        ]
    return direct[0] if len(direct) == 1 else None


def attach(bundle, commands, placements=None):
    """Build one obligation owner per command, preserving every call occurrence."""
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    first_call = bundle.get("analysis_profile") in FIRST_CALL_PROFILES
    primary_only = bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
    bundle["pending"] = [p for p in bundle["pending"] if not p.get("command_gap")]
    calls = {cid: [] for cid in commands}
    for step in steps:
        step["data"] = []
        operation = step["operation"]
        operation.pop("command_id", None)
        operation.pop("command_ids", None)
        if step["direction"] != "request" or step["kind"] == "action":
            continue
        cid = _pick(step, commands)
        step["api_id"] = cid
        if primary_only:
            step.pop("call_command_id", None)
        if cid:
            calls[cid].append(step)
        elif step.get("declared_command"):
            _gap(
                bundle,
                step["declared_command"],
                "声明接口与 SR 命令或调用双方不一致",
                step["source_refs"],
            )
    bundle["commands"] = deepcopy(list(commands.values()))
    bundle["command_bindings"] = {}
    bundle["operation_hints"] = [
        {k: row[k] for k in ("id", "name", "method", "path", "quote")} for row in commands.values()
    ]
    for cid, command in commands.items():
        occurrences = calls[cid]
        placement = (placements or {}).get(cid)
        if command.get("conflict"):
            _gap(bundle, cid, command["conflict"], command["source_refs"])
        if not occurrences:
            if placement is None:
                _gap(bundle, cid, "功能树命令在主成功流缺少明确的调用步骤", command["source_refs"])
                continue
            occurrences = [next(step for step in steps if step["id"] == placement["step_id"])]
        primary = occurrences[0]
        for step in occurrences:
            if primary_only and step is not primary:
                step["call_command_id"] = cid
                step["api_id"] = None
                continue
            operation = step["operation"]
            if placement is None or placement["binding_source"] != "step1_fallback":
                operation.setdefault("command_id", cid)
                step["api_id"] = step.get("api_id") or cid
                if operation["command_id"] == cid:
                    for key in ("method", "path"):
                        if command[key]:
                            operation["http_" + key] = command[key]
            if placements is not None:
                operation.setdefault("command_ids", []).append(cid)
        fallback = bool(placement and placement["binding_source"] == "step1_fallback")
        validation = [s for s in steps if not fallback and primary["id"] in s.get("validates", [])]
        owner = validation[0] if len(validation) == 1 else primary
        if len(validation) > 1:
            _gap(bundle, cid, "参数校验步骤有歧义", command["source_refs"])
        returns = [
            s
            for s in steps
            if not fallback and s["direction"] == "return" and s.get("parent_id") == primary["id"]
        ]
        bundle["command_bindings"][cid] = {
            "primary_step_id": primary["id"],
            "occurrences": [s["id"] for s in occurrences],
            "validation_step_id": owner["id"] if owner is not primary else None,
            **(
                {k: placement[k] for k in ("binding_source", "reason")}
                if placement
                else {"binding_source": "evidence"}
                if placements is not None
                else {}
            ),
        }
        if first_call:
            occurrence_ids = {s["id"] for s in occurrences}
            validators = [
                s["id"]
                for s in steps
                if not fallback and occurrence_ids.intersection(s.get("validates", []))
            ]
            responses = [
                s["id"]
                for s in steps
                if not fallback
                and s["direction"] == "return"
                and s.get("parent_id") in occurrence_ids
            ]
            bundle["command_bindings"][cid].update(
                validation_step_ids=validators, response_step_ids=responses
            )
        for field in command["fields"]:
            location = field["location"]
            if not location or (
                location == "response" and len(returns) != 1 and placements is None
            ):
                _gap(bundle, cid, "未能唯一定位 SR 字段：" + field["name"], field["source_refs"])
                continue
            target = primary if first_call else returns[0] if location == "response" else owner
            target["data"].append(
                {
                    **deepcopy(field),
                    "id": ident(
                        "command-field", bundle["case"]["id"], cid, location, field["name"]
                    ),
                    "command_id": cid,
                    "call_step_id": primary["id"],
                    "direction": "response" if location == "response" else "request",
                    **(
                        {
                            "validation_step_ids": validators if location != "response" else [],
                            "response_step_ids": responses if location == "response" else [],
                        }
                        if first_call
                        else {}
                    ),
                }
            )


def associate_entities(bundle):
    """Connect commands to evidenced business entities without adding them to source steps."""
    steps = {s["id"]: s for s in bundle["steps"]}
    entities = {e["id"] for e in bundle.get("entities", [])}
    commands = {c["id"]: c for c in bundle["commands"]}
    for cid, link in bundle["command_bindings"].items():
        primary = steps[link["primary_step_id"]]
        related = [
            *link["occurrences"],
            *link.get("validation_step_ids", []),
            *link.get("response_step_ids", []),
        ]
        observed = {e for sid in related for e in steps[sid]["entity_ids"]}
        fields = {
            (f.get("entity_binding") or {}).get("entity_id")
            for f in primary["data"]
            if f["command_id"] == cid
        }
        selected = (observed | fields) & entities
        if not selected and len(commands) == len(entities) == 1:
            selected = entities
        link["entity_ids"] = sorted(selected)
        if not selected:
            choices = sorted(entities)
            _gap(
                bundle,
                cid,
                "接口的操作实体待确认" + (" · " + "、".join(choices) if choices else ""),
                commands[cid]["source_refs"],
            )


def _gap(bundle, cid, reason, refs):
    bundle["pending"].append(
        pending(
            ident("command-gap", cid, reason),
            reason,
            refs,
            command_id=cid,
            command_gap=True,
            reason=reason,
        )
    )


def signature(atom):
    return fingerprint(
        [
            atom["operation"],
            atom.get("value"),
            bool(atom.get("exclusive")),
            atom.get("failure_condition"),
            sorted(atom.get("applicable_operations") or []),
        ]
    )


def generate_fields(bundle, output):
    """Attach one concern per field/family and merge only fully equivalent atom sets."""
    from scene_completion.analysis.ssd.pipeline import _atom_condition
    from scene_completion.domain.concern_templates import scenario_metadata

    aliases = {}
    directions = {}
    precise_sources = bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
    for step in bundle["steps"]:
        for field in step["data"]:
            explicit = field.get("entity_binding") or {}
            for key in {a["concern_key"] for a in field["atoms"]}:
                atoms = frozenset(signature(a) for a in field["atoms"] if a["concern_key"] == key)
                identity = (explicit.get("entity_id"), explicit.get("attribute"), key, atoms)
                directions.setdefault(identity, set()).add(field["direction"])
    first_call = bundle.get("analysis_profile") in FIRST_CALL_PROFILES
    for step in bundle["steps"]:
        for field in step["data"]:
            obligations = {}
            binding = bundle["command_bindings"][field["command_id"]]
            for atom in field["atoms"]:
                operations = atom.get("applicable_operations") or []
                if (
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
                        len(directions[identity]) == 1
                        and not any(a.get("value_pending") for a in atoms)
                        if first_call
                        else u["step_id"] == step["id"] and not u.get("obligation_scope")
                    )
                    and atoms_identity == {signature(a) for a in u["atoms"]}
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
                                    == attribute
                                    + "："
                                    + _atom_condition({**atom, "attribute": attribute})
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
                    condition = _atom_condition({**atom, "attribute": field["wire_name"]})
                    scene = add_scenario(output, concern, condition, "", atom["source_refs"])
                    scene.update(
                        scenario_metadata(key, atom["operation"], "deterministic_constraint"),
                    )
                    _record_command_sources(scene, field)
    bundle["command_aliases"] = aliases


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
