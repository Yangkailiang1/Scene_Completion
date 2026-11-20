"""Map the selected supplier function tree commands into SSD contracts."""

import json

from scene_completion.analysis.concerns.constraint_atoms import normalize_rules
from scene_completion.domain.current_scope import (
    COMMAND_OPERATION_PROFILE,
    COMMAND_PROFILES,
)
from scene_completion.domain.ssd.construction import (
    unique,
)
from scene_completion.inputs.provenance.ssd_sources import api_contracts
from scene_completion.inputs.structured.case_names import candidates as case_candidates
from scene_completion.workflow.ssd.shared.command_bindings import _HTTP

LOCATIONS = {
    "路径参数": "path",
    "查询参数": "query",
    "请求头": "header",
    "请求体": "body",
    "成功响应": "response",
}


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


def for_case(root, sources, shared_tree, tree_link, case, case_entity, active_profile):
    """Resolve the function-tree entry and command contracts for one case."""
    local_tree_path, local_tree, local_contracts = shared_tree
    if tree_link.get("path"):
        linked_path = (root / tree_link["path"]).resolve()
        if not linked_path.is_relative_to(root):
            raise ValueError("功能树路径超出输入目录")
        if linked_path != shared_tree[0] and linked_path.is_file():
            local_tree_path = linked_path
            local_tree = json.loads(linked_path.read_text(encoding="utf-8-sig"))
            local_contracts = api_contracts(sources, local_tree, local_tree_path)
    tree_case = tree_link.get("uc_id") or case["id"]
    tree_hits = []
    if active_profile == COMMAND_OPERATION_PROFILE:
        tree_hits = case_candidates(
            (local_tree or {}).get("functions", []),
            case["name"],
            case_entity,
            explicit_id=tree_link.get("uc_id"),
        )
        tree_case = (
            tree_hits[0][1].get("functionId") or tree_hits[0][1].get("ucId")
            if len(tree_hits) == 1
            else None
        )
    command_mode = active_profile in COMMAND_PROFILES
    if command_mode:
        local_contracts = catalogue(
            sources,
            local_tree,
            local_tree_path,
            tree_case,
            case["name"],
            selected=tree_hits if active_profile == COMMAND_OPERATION_PROFILE else None,
        )
    return local_tree_path, local_tree, local_contracts, tree_case, tree_hits


def operation_hints(local_tree, tree_case, case_name):
    """Keep the existing operation evidence used by the entity-only profile."""
    candidates = (local_tree or {}).get("functions", [])
    matches = [f for f in candidates if (f.get("functionId") or f.get("ucId")) == tree_case]
    matches = matches or [f for f in candidates if f.get("name") == case_name]
    return (
        [
            {k: row[k] for k in ("apiId", "name", "method") if row.get(k)}
            for layer in ("rrLayer", "srLayer")
            for row in matches[0].get(layer, {}).get("commands", [])
            if row.get("method")
        ]
        if len(matches) == 1
        else []
    )
