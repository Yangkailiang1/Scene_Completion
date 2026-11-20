"""Map behavior-model participants, order and interactions into SSD steps."""

import re
from copy import deepcopy

from scene_completion.domain.ssd.construction import (
    ident,
)
from scene_completion.workflow.ssd.shared.step_bindings import _enrich_fields, _field, _kinds


def _actor_reference(key, name, value):
    names = "|".join(re.escape(str(n)) for n in dict.fromkeys([name, key]) if n)
    actor = r"(?:human(?: actor)?|external_actor|actor|参与者|人类角色|用户角色)"
    label = rf"(?:[（(【「「]?(?:{names})[）)】」」]?)"
    patterns = (
        rf"(?<![\w]){actor}\s*[|：:=]\s*{label}(?![\w])",
        rf"(?<![\w]){label}\s*(?:[|：:=（(]|是|为|属于)\s*(?:外部)?{actor}(?![\w])",
    )
    return next(
        (
            ref
            for ref in value.get("source_refs") or []
            if isinstance(ref, dict)
            and any(re.search(pattern, str(ref.get("quote") or ""), re.I) for pattern in patterns)
        ),
        None,
    )


def _person(key, participants):
    value = participants.get(key, {})
    if isinstance(value, str):
        value = {"name": value}
    name = value.get("name") or key
    manual = value.get("kind_override")
    actor_ref = None if manual else _actor_reference(key, name, value)
    kind = manual or ("external_actor" if actor_ref else value.get("kind"))
    technology = value.get("technology")
    if not technology and re.search(r"database|数据库", name, re.I):
        technology = "database"
    if not technology and re.search(r"\bLLM\b|大语言模型|AI模型", name, re.I):
        technology = "llm"
    return {
        "id": str(key),
        "name": str(name),
        "type": "human"
        if kind in {"human", "external_actor"}
        or not manual
        and value.get("element_type") in {"human", "actor"}
        or kind == "external"
        and name in {"顾客", "客户", "消费者", "商家", "用户", "管理员"}
        else "service",
        "technology": technology,
        "external": kind in {"external", "external_actor", "external_service"},
        **(
            {"classification_source": "participant.source_refs", "source_refs": [actor_ref]}
            if actor_ref
            else {}
        ),
    }


def _step_refs(raw, node, sources, file_name, pointer, root):
    """Citation for one step: its own source file, or the case's documents.

    An authoring case is rendered from the documents listed in the supplied
    case file, so each step opens those originals at its own description. A
    description that no original contains is not guessed; the step keeps no
    invented line.
    """
    if file_name:
        return sources.refs(node, file_name, pointer)
    from scene_completion.inputs.provenance import source_origins

    wanted = None
    for group in ("system_event", "interaction", "action", "system_response"):
        for row in row_iter(raw, group):
            if row.get("id") == node.get("id"):
                wanted = row.get("description") or row.get("content")
    if not wanted:
        return []
    refs = []
    for declared in (raw.get("case") or {}).get("documents", []):
        document = source_origins.resolve_name(declared.get("name"), sources.origins)
        if document is None:
            continue
        found = source_origins.origin(document, wanted, None)
        if not found or found.get("match") == "pending":
            continue
        refs.append(
            {
                "document_id": document["id"],
                "start_line": found["start_line"],
                "end_line": found["end_line"],
                "quote": found["quote"],
                "kind": "origin",
                "origin": found,
            }
        )
    return refs


def row_iter(raw, group):
    for value in raw.get("operations", {}).values():
        yield from value.get(group, [])


def _declared_api(node, contracts):
    """Match a declared interface id by identity or by its method and path."""
    declared = node.get("api_id")
    if declared in contracts and not contracts[declared].get("path_conflicts"):
        return declared
    content = node.get("content") or node.get("message") or ""
    named = [
        key
        for key in contracts
        if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(key) + r"(?![A-Za-z0-9_-])", content)
    ]
    if len(named) == 1 and not contracts[named[0]].get("path_conflicts"):
        return named[0]
    operation = node.get("operation") or {}
    method, path = (operation.get("http_method") or "").upper(), operation.get("http_path")
    if not method or not path:
        return None
    candidates = [
        key
        for key, contract in contracts.items()
        if (contract.get("method") or "").upper() == method
        and contract.get("path") == path
        and not contract.get("path_conflicts")
    ]
    return candidates[0] if len(candidates) == 1 else None


def _steps(raw, sources, file_name, contracts, root=None, *, entity_only=False):
    from scene_completion.inputs.structured.ordered_behaviors import scenario_kind

    # Raw behaviour files may omit ``scenario_kind``; the shared resolver reads
    # the operation identity instead of guessing from file order.
    mains = [
        (key, value)
        for key, value in raw.get("operations", {}).items()
        if scenario_kind(value) in {"main", "normal"}
    ]
    if len(mains) != 1:
        raise ValueError("用例需要唯一主成功 SysOperation：" + str(raw.get("use_case")))
    operation_id, operation = mains[0]
    participants = operation.get("participant", raw.get("participant", {}))
    nodes = {}
    raw_ids = {}
    for group in ("system_event", "interaction", "action", "system_response"):
        for n, node in enumerate(operation.get(group, [])):
            key = node.get("id") or node.get("ID")
            if not key:
                continue
            pointer = (
                "/operations/"
                + operation_id.replace("~", "~0").replace("/", "~1")
                + f"/{group}/{n}"
            )
            raw_ids.setdefault(key, []).append((group, node, node.get("_pointer") or pointer))
    for key, entries in raw_ids.items():
        groups = set()
        for group, node, pointer in entries:
            if group in groups:
                raise ValueError(f"主成功节点 ID 在 {group} 中重复：{key}")
            groups.add(group)
            identity = key if len(entries) == 1 else ident("step", operation_id, group, key)
            nodes[identity] = (group, node, pointer)

    def resolve(ref, group=None):
        group = {"response": "system_response", "event": "system_event"}.get(group, group)
        hits = [
            key
            for key, (kind, node, _) in nodes.items()
            if (node.get("id") or node.get("ID")) == ref and (not group or kind == group)
        ]
        return hits[0] if len(hits) == 1 else None

    ordered = []
    for entry in operation.get("Order", []):
        ref = resolve(entry.get("ref"), entry.get("kind"))
        if not ref:
            raise ValueError("Order 引用缺失或有歧义：" + str(entry.get("ref")))
        ordered.append(ref)
    ordered = [
        key
        for key, (group, _, _) in nodes.items()
        if group == "system_event" and key not in ordered
    ] + ordered
    # An incomplete Order is surfaced instead of silently changing its sequence.
    missing = [key for key in nodes if key not in ordered]
    ordered += missing
    result = []
    for order, key in enumerate(dict.fromkeys(k for k in ordered if k in nodes), 1):
        group, node, pointer = nodes[key]
        action = group == "action"
        op = node.get("operation") or {}
        text = node.get("content") or node.get("message") or node.get("name") or key
        refs = _step_refs(raw, node, sources, file_name, pointer, root)
        executor = node.get("executor")
        sender = _person(executor if action else node.get("sender", "?"), participants)
        receiver = _person(executor if action else node.get("receiver", "?"), participants)
        direction = node.get("direction") or ("return" if group == "system_response" else "request")
        layer = node.get("source_layer") or (
            "RR"
            if group in {"system_event", "system_response"}
            or key.startswith("RR-")
            or key.startswith("A_R")
            else "SR"
        )
        aid = _declared_api(node, contracts)
        if entity_only and not aid and node.get("api_id") in contracts:
            aid = node["api_id"]
        declared = op.get("crud") or op.get("kinds")
        if not declared:
            declared = list(
                dict.fromkeys(
                    row["operation"]
                    for row in node.get("data_ref") or []
                    if row.get("operation") in {"create", "read", "update", "delete", "publish"}
                )
            )
        contract = contracts.get(aid, {})
        kinds = (
            list(declared or [])
            or _kinds(text, contract.get("method") or op.get("http_method"))
            or _kinds(raw.get("use_case", ""), contract.get("method"))
        )
        if (
            action
            and receiver["technology"] != "database"
            and not (
                aid
                or node.get("operation_kinds")
                or op.get("crud")
                or re.search(r"调用\s*API[-_][A-Za-z0-9-]+.*(?:查询|检索|读取)", text, re.I)
            )
        ):
            kinds = []
        if action and receiver["technology"] == "database" and not declared:
            kinds = _kinds(raw.get("use_case", "") + " " + text)
        data = []
        entities = []
        for row in node.get("data_ref") or []:
            if row.get("entity"):
                entities.append(row["entity"])
            if row.get("declared_fields"):
                # Supplied per-step fields keep their own declared text.
                data += [
                    _field(key, item["field"], refs, field=item.get("facts"))
                    for item in row["declared_fields"]
                    if isinstance(item, dict) and item.get("field")
                ]
            data += [_field(key, f, refs) for f in row.get("fields", []) if isinstance(f, str)]
        alias = re.match(r"^([RS]\d+)(?:[ab])?[.、:：]", text)
        step = {
            "id": key,
            "order": order,
            "kind": "action" if action else "interaction",
            "layer": layer,
            "direction": direction,
            "sender": sender,
            "receiver": receiver,
            "operation": {
                "name": op.get("name") or text,
                "kinds": node.get("operation_kinds") or kinds,
                "kinds_source": "declared"
                if node.get("operation_kinds") or declared
                else "inferred",
                **{part: op[part] for part in ("http_method", "http_path") if op.get(part)},
            },
            **({"description": node["description"]} if node.get("description") else {}),
            **(
                {
                    "entity_refs": [
                        {"entity": row["entity"], "fields": row.get("fields") or []}
                        for row in node.get("data_ref") or []
                        if row.get("entity")
                    ],
                    "validates": node.get("validates") or [],
                    "participant_gaps": [
                        party["id"]
                        for party in (sender, receiver)
                        if party["id"] not in participants
                    ],
                }
                if entity_only
                else {}
            ),
            "data": list({p["id"]: p for p in data}.values()),
            "api_id": aid,
            "entity_ids": list(dict.fromkeys(entities)),
            "source_refs": refs,
            "aliases": list(
                dict.fromkeys([*(node.get("aliases") or []), *([alias[1]] if alias else [])])
            ),
            "parent_id": None,
        }
        if direction == "return":
            calls = [
                s
                for s in result
                if s["direction"] == "request"
                and s["kind"] != "action"
                and s["sender"]["id"] == receiver["id"]
                and s["receiver"]["id"] == sender["id"]
                and (not aid or s["api_id"] == aid)
            ]
            parent_ref = (
                node.get("parent_id") or node.get("reply_to") or node.get("declared_parent")
            )
            if parent_ref:
                calls = [call for call in calls if parent_ref in [call["id"], *call["aliases"]]]
            if len(calls) == 1:
                step["parent_id"] = calls[0]["id"]
                step["operation"]["kinds"] = calls[0]["operation"]["kinds"]
            elif parent_ref or len(calls) > 1:
                step["parent_candidates"] = [call["id"] for call in calls]
        if action and receiver["technology"] == "database":
            calls = [
                s
                for s in result
                if s["receiver"]["id"] == receiver["id"]
                and s["kind"] != "action"
                and s["direction"] == "request"
            ]
            if calls:
                if not entities:
                    step["entity_ids"] = calls[-1]["entity_ids"]
                step["delegated_from"] = calls[-1]["id"]
                # Local storage execution belongs to its actual SSD call.
                # State names/preconditions in the action prose cannot change
                # compareAndDeleteProduct into update/publish, for example.
                if not node.get("operation_kinds") and calls[-1]["operation"]["kinds"]:
                    step["operation"]["kinds"] = deepcopy(calls[-1]["operation"]["kinds"])
        if entity_only:
            if node.get("api_id"):
                step["declared_command"] = node["api_id"]
            step["data"] = []
            step["entity_ids"] = list(dict.fromkeys(entities))
            step["operation"]["kinds"] = (
                list(op.get("crud", []))
                if op.get("crud_source") in {"declared", "manual"}
                or "crud" in op
                and not op.get("crud_source")
                else []
            )
            step["operation"]["kinds_source"] = (
                op.get("crud_source") or "declared"
                if "crud" in op and op.get("crud_source") != "pending"
                else "pending"
            )
            method = op.get("http_method") or contract.get("method")
            if not method:
                methods = {
                    str(api.get("method")).upper()
                    for api in contracts.values()
                    if api.get("method")
                    and api["id"] in text
                    and re.search(r"(?<![\w-])" + re.escape(api["id"]) + r"(?![\w-])", text)
                }
                method = next(iter(methods)) if len(methods) == 1 else None
            if method:
                step["operation"]["http_method"] = method
        elif not action or aid:
            _enrich_fields(step, contracts)
        result.append(step)
    return result, missing
