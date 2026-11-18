"""Project only actual SR commands and their data obligations onto SSD steps."""

import re
from copy import deepcopy

from scene_completion.analysis.concerns.constraint_atoms import normalize_rules
from scene_completion.domain.current_scope import COMMAND_PROFILE
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


def catalogue(sources, tree, path, case_id, case_name):
    """Read the selected function's SR catalogue alone. Source text may complete metadata."""
    functions = list(enumerate((tree or {}).get("functions", [])))
    hits = [(i, f) for i, f in functions if (f.get("functionId") or f.get("ucId")) == case_id]
    hits = hits or [(i, f) for i, f in functions if f.get("name") == case_name]
    if len(hits) != 1:
        return {}
    i, function = hits[0]
    source = sources.add(path)
    commands = {}
    for j, raw in enumerate((function.get("srLayer") or {}).get("commands", [])):
        command_id = raw["apiId"]
        if command_id in commands:
            raise ValueError("SR 命令编号重复：" + command_id)
        pointer = f"/functions/{i}/srLayer/commands/{j}"
        declaration = raw.get("source") or {}
        original = sources.original([declaration])
        method, address = raw.get("method"), raw.get("path")
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
            refs = unique(
                [
                    sources.traced_ref(source, f"{pointer}/attributes/{k}", origin),
                    *sources.original([origin]),
                ]
            )
            facts = normalize_rules(
                [], name, refs, tags=row.get("tags"), data_type=row.get("type"), entity_only=True
            )
            for n, rule in enumerate(row.get("constraints", [])):
                if isinstance(rule, dict) and rule.get("source"):
                    rule_refs = unique(
                        [
                            sources.traced_ref(
                                source, f"{pointer}/attributes/{k}/constraints/{n}", rule["source"]
                            ),
                            *sources.original([rule["source"]]),
                            *refs,
                        ]
                    )
                else:
                    rule_refs = refs
                result = normalize_rules([rule], name, rule_refs, entity_only=True)
                for key in ("items", "unresolved"):
                    facts[key].extend(result[key])
            fields.append(
                {
                    "name": name,
                    "wire_name": row.get("wire_name") or name,
                    "location": location,
                    "type": row.get("type"),
                    "entity_binding": row.get("entity_binding"),
                    "required": True if "必填" in row.get("tags", []) else None,
                    "constraints": [],
                    "rule_texts": [
                        rule.get("rule", "") if isinstance(rule, dict) else rule
                        for rule in row.get("constraints", [])
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
            "name": raw.get("name") or command_id,
            "method": method.upper() if method else None,
            "path": address,
            "service": raw.get("service"),
            "quote": "\n".join(
                ref["quote"] for ref in original if ref.get("origin", {}).get("role") == "SR"
            ),
            "authentication": raw.get("authentication"),
            "fields": fields,
            "source_refs": unique([sources.traced_ref(source, pointer, declaration), *original]),
        }
    return commands


def _pick(step, commands):
    declared = step.get("api_id") or step.get("declared_command")
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


def attach(bundle, commands):
    """Build one obligation owner per command, preserving every call occurrence."""
    steps = sorted(bundle["steps"], key=lambda step: step["order"])
    first_call = bundle.get("analysis_profile") == COMMAND_PROFILE
    bundle["pending"] = [p for p in bundle["pending"] if not p.get("command_gap")]
    calls = {cid: [] for cid in commands}
    for step in steps:
        step["data"] = []
        operation = step["operation"]
        operation.pop("command_id", None)
        if step["direction"] != "request" or step["kind"] == "action":
            continue
        cid = _pick(step, commands)
        step["api_id"] = cid
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
        if not occurrences:
            _gap(bundle, cid, "功能树命令在主成功流缺少明确的调用步骤", command["source_refs"])
            continue
        primary = occurrences[0]
        for step in occurrences:
            step["operation"]["command_id"] = cid
            if command["method"]:
                step["operation"]["http_method"] = command["method"]
            if command["path"]:
                step["operation"]["http_path"] = command["path"]
        validation = [s for s in steps if primary["id"] in s.get("validates", [])]
        owner = validation[0] if len(validation) == 1 else primary
        if len(validation) > 1:
            _gap(bundle, cid, "参数校验步骤有歧义", command["source_refs"])
        returns = [
            s for s in steps if s["direction"] == "return" and s.get("parent_id") == primary["id"]
        ]
        bundle["command_bindings"][cid] = {
            "primary_step_id": primary["id"],
            "occurrences": [s["id"] for s in occurrences],
            "validation_step_id": owner["id"] if owner is not primary else None,
        }
        if first_call:
            occurrence_ids = {s["id"] for s in occurrences}
            validators = [
                s["id"] for s in steps if occurrence_ids.intersection(s.get("validates", []))
            ]
            responses = [
                s["id"]
                for s in steps
                if s["direction"] == "return" and s.get("parent_id") in occurrence_ids
            ]
            bundle["command_bindings"][cid].update(
                validation_step_ids=validators, response_step_ids=responses
            )
        for field in command["fields"]:
            location = field["location"]
            if not location or (location == "response" and len(returns) != 1):
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
    for step in bundle["steps"]:
        for field in step["data"]:
            explicit = field.get("entity_binding") or {}
            for key in {a["concern_key"] for a in field["atoms"]}:
                atoms = frozenset(signature(a) for a in field["atoms"] if a["concern_key"] == key)
                identity = (explicit.get("entity_id"), explicit.get("attribute"), key, atoms)
                directions.setdefault(identity, set()).add(field["direction"])
    first_call = bundle.get("analysis_profile") == COMMAND_PROFILE
    for step in bundle["steps"]:
        for field in step["data"]:
            obligations = {}
            for atom in field["atoms"]:
                obligations.setdefault(atom["concern_key"], []).append(atom)
            for key, atoms in obligations.items():
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
                    merged_refs = unique(
                        field["source_refs"] + [ref for a in atoms for ref in a["source_refs"]]
                    )
                    mapped["source_refs"] = unique(mapped["source_refs"] + merged_refs)
                    if first_call:
                        _record_command_sources(mapped, field, include_primary=False)
                    for scene in output["scenarios"]:
                        if mapped["id"] in scene["concern_ids"]:
                            scene["source_refs"] = unique(scene["source_refs"] + merged_refs)
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
                    refs=field["source_refs"],
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
