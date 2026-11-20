"""Deterministic, per-use-case SSD preparation and concern attachment.

G is a pure function of positive steps, contracts and entity metadata. Reverse
channels are parsed separately and never used to decide which G rules apply.
"""

import json
import re
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.concern_templates import scenario_metadata, templates_for
from scene_completion.domain.current_scope import (
    COMMAND_OPERATION_PROFILE,
    COMMAND_PROFILES,
    STRUCTURED_PROFILES,
)
from scene_completion.domain.ssd.construction import (
    add_concern,
    add_scenario,
    channel,
    ident,
    pending,
    unique,
)
from scene_completion.infrastructure.storage import io_path
from scene_completion.inputs.provenance.ssd_sources import (
    Sources,
    api_contracts,
    entities_for,
)
from scene_completion.inputs.structured.case_names import candidates as case_candidates

VERSION = "ssd-case-v1"
RULE_VERSION = "ssd-three-scope-rules-v2"  # Existing rule/record identities stay stable.
DATA_KINDS = {
    "required": "completeness",
    "type": "type",
    "format": "format",
    "pattern": "format",
    "length": "length",
    "size": "size",
    "minimum": "range",
    "maximum": "range",
    "enum": "range",
    "range": "range",
}


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


def _constraint_failures(field, constraint):
    """Keep the actual operator in generated boundary conditions."""
    name, kind, value = field["name"], constraint["kind"], constraint["value"]
    literal = json.dumps(value, ensure_ascii=False)
    if kind == "minimum":
        return [name + " < " + literal]
    if kind == "maximum":
        return [name + " > " + literal]
    if kind == "enum":
        return [name + "不属于枚举集合" + literal]
    if kind == "length" and isinstance(value, str):
        match = re.search(r"(\d+)\s*[-~至到]\s*(\d+)", value)
        if match:
            failures = [name + "长度 > " + match[2]]
            if int(match[1]) > 0:
                failures.insert(0, name + "长度 < " + match[1])
            return failures
    return [name + "不满足" + str(value)]


def _business_conditions(name, text, kinds, *, response=False, enum_values=()):
    """Select individual lifecycle clauses, keeping predicates on their own operation.

    A publish operation is implemented as an update, but does not thereby inherit
    every rule for editing entity fields. State names come from the source clause,
    never from a use-case number or a dataset-specific entity name.
    """
    primary = (
        "publish"
        if "publish" in kinds
        else next((kind for kind in ("create", "update", "delete", "read") if kind in kinds), None)
    )

    def invalid_values(allowed, context):
        if enum_values:
            return [
                f"{name} = {value}（{context}；要求值 {allowed}）"
                for value in enum_values
                if str(value) != allowed
            ]
        return [f"{name} != {allowed}（{context}）"]

    output = []
    for clause in re.split(r"[；;]", str(text)):
        clause = clause.strip()
        if not clause:
            continue
        if re.search(r"幂等|唯一标识|由数据库.*生成|创建请求不传|不同商家可重名", clause):
            continue
        transition = re.search(
            r"由\s*([A-Za-z][A-Za-z0-9_-]*)\s*(?:改为|变为|转为)\s*([A-Za-z][A-Za-z0-9_-]*)",
            clause,
        )
        if transition:
            if primary == "publish":
                state = transition[2] if response else transition[1]
                output.extend(invalid_values(state, "发布成功响应" if response else "发布前置状态"))
            continue
        initial = re.search(r"创建后(?:为|设为)\s*([A-Za-z0-9_-]+)", clause)
        if initial:
            if response and primary == "create":
                output.extend(invalid_values(initial[1], "创建成功响应"))
            continue
        allowed = re.search(r"仅\s*([A-Za-z][A-Za-z0-9_-]*)\s*可(.+)", clause)
        if allowed:
            operations = {
                kind
                for word, kind in (
                    ("更新", "update"),
                    ("修改", "update"),
                    ("删除", "delete"),
                    ("发布", "publish"),
                )
                if word in allowed[2]
            }
            if operations:
                if not response and primary in operations:
                    output.extend(invalid_values(allowed[1], clause))
                continue
        increment = re.search(r"(?:更新|发布).*成功增加\s*(\d+)", clause)
        if increment:
            if response and primary in {"update", "publish"}:
                output.append(f"{name}未按成功操作增加{increment[1]}")
            continue
        if re.search(r"不可修改|不得改变|提供不同值", clause) and primary != "update":
            continue
        if "不可重名" in clause and primary not in {"create", "update"}:
            continue
        if re.search(r"\S+为\S+时\S+必须", clause) and primary not in {"create", "update"}:
            continue
        if not response and "访问" in clause and primary != "read":
            continue
        qualified = clause if name in clause else f"{name}：{clause}"
        output.append(("返回结果不满足：" if response else "不满足业务条件：") + qualified)
    return list(dict.fromkeys(output))


def _attribute_business_rules(attribute, kinds, *, response=False, fallback_refs=()):
    constraints = attribute.get("constraints", [])
    enums = [rule for rule in constraints if rule.get("kind") == "enum"]
    enum_values = list(
        dict.fromkeys(
            value
            for rule in enums
            if isinstance(rule.get("value"), (list, tuple))
            for value in rule["value"]
        )
    )
    enum_refs = [ref for rule in enums for ref in rule.get("source_refs", [])]
    for rule in constraints:
        if rule.get("kind") != "other":
            continue
        refs = rule.get("source_refs") or attribute.get("source_refs") or fallback_refs
        for condition in _business_conditions(
            attribute["name"],
            rule.get("value", ""),
            kinds,
            response=response,
            enum_values=enum_values,
        ):
            yield condition, unique(list(refs) + enum_refs)


def _business_rules(bundle, step, entity_id):
    """Choose existing entity conditions for the current operation and fields."""
    entity = next((e for e in bundle.get("entities", []) if e["id"] == entity_id), {})
    kinds = set(step["operation"].get("kinds", []))
    names = {p["name"] for p in step["data"]}
    database_action = step["kind"] == "action" and step["receiver"].get("technology") == "database"
    result = []
    for attribute in entity.get("attributes", []):
        if not database_action and attribute["name"] not in names:
            continue
        result.extend(_attribute_business_rules(attribute, kinds))
    return unique(result)


def generate_g(bundle):
    """Attach registry rules to positive facts only, without source-evidence gates."""
    output = channel()
    from scene_completion.domain.current_scope import current_registry

    registry = current_registry(bundle.get("registry") or default_registry())
    definitions, profiles = registry["definitions"], registry["profiles"]
    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    unit_profile = bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
    from scene_completion.analysis.ssd.operation_units import functional_family

    owners = {}
    for unit in bundle.get("operation_units", []):
        owners.setdefault(unit["step_id"], []).append(unit)
    for step in bundle["steps"]:
        refs = step.get("source_refs", [])
        kinds = set(step["operation"].get("kinds", []))
        request = step["direction"] == "request"
        call = step["kind"] != "action" and step["sender"]["id"] != step["receiver"]["id"]
        receiver = step["receiver"]

        def attach(
            key,
            target="receiver",
            field=None,
            entity=None,
            condition="",
            source_refs=None,
            variant_id=None,
            generation_origin="deterministic_constraint",
            on_step=None,
            operation_unit_id=None,
            functional_keys=(),
            related_calls=(),
        ):
            definition = definitions.get(key, {})
            if (
                not definition.get("enabled", True)
                or definition.get("scope", "interaction") != "interaction"
            ):
                return None
            # An anchored constraint may live on a step other than the one being
            # iterated; nothing else about the concern changes.
            concern = add_concern(
                output,
                bundle,
                "G",
                on_step if on_step is not None else step,
                key,
                target,
                field=field,
                entity=entity,
                condition=condition,
                refs=source_refs if source_refs is not None else refs,
                rule_id=RULE_VERSION + ":" + key,
                operation_unit_id=operation_unit_id,
            )
            if concern:
                concern["scope"] = "interaction"
                if related_calls:
                    concern["related_call_step_ids"] = list(related_calls)
                scenario_refs = source_refs if source_refs is not None else refs
                templates = templates_for(key)
                if functional_keys:
                    concern["concern_keys"] = list(functional_keys)
                    concern["applicable_operations"] = sorted(
                        {
                            kind
                            for k in functional_keys
                            for kind in definitions[k]["operation_kinds"]
                        }
                    )
                    variants = {}
                    for k in functional_keys:
                        for template in templates_for(k):
                            identity = (
                                template["variant_id"],
                                re.sub(r"创建|更新|删除", "操作", template["condition"], count=1),
                                template["expected"],
                            )
                            variants.setdefault(identity, {**template, "concern_keys": []})[
                                "concern_keys"
                            ].append(k)
                    templates = list(variants.values())
                if condition:
                    if not variant_id:
                        variant_id = (
                            "immutable_attribute"
                            if key == "service.business_attribute_constraint"
                            and re.search(r"不可修改|不可变|不得改变", condition)
                            else "duplicate_value"
                            if key == "service.business_attribute_constraint"
                            and re.search(r"重名|唯一|重复", condition)
                            else templates[
                                -1 if key == "service.business_attribute_constraint" else 0
                            ]["variant_id"]
                            if templates
                            else "derived_constraint"
                        )
                    scene = add_scenario(output, concern, condition, "", scenario_refs)
                    scene.update(
                        scenario_metadata(key, variant_id, generation_origin), scope="interaction"
                    )
                else:
                    for template in templates:
                        if (
                            bundle.get("analysis_profile") in COMMAND_PROFILES
                            and key == "human.authentication"
                            and template["variant_id"] == "missing_credential"
                            and any(
                                c["id"] == step["operation"].get("command_id")
                                and c.get("authentication") == "optional"
                                for c in bundle["commands"]
                            )
                        ):
                            continue
                        scene = add_scenario(
                            output,
                            concern,
                            template["condition"],
                            template["expected"],
                            scenario_refs,
                            ident("scenario-template", concern["id"], template["template_id"]),
                        )
                        scene.update(
                            {
                                k: template[k]
                                for k in (
                                    "template_id",
                                    "variant_id",
                                    "template_version",
                                    "generation_origin",
                                )
                            },
                            scope="interaction",
                        )
                        if functional_keys:
                            scene["concern_keys"] = template["concern_keys"]
                            scene["applicable_operations"] = sorted(
                                {
                                    kind
                                    for k in template["concern_keys"]
                                    for kind in definitions[k]["operation_kinds"]
                                }
                            )
                            if len(template["concern_keys"]) > 1:
                                scene["condition"] = re.sub(
                                    r"创建|更新|删除", "操作", scene["condition"], count=1
                                )
                        if related_calls:
                            scene["related_call_step_ids"] = list(related_calls)
            return concern

        if request and call and step["sender"]["type"] == "human":
            for key in profiles["human"]:
                attach(key, "sender")
        if request and call and receiver["type"] == "service":
            if receiver.get("external") and (not unit_profile or "operation_units" not in bundle):
                attach("service.base.availability")
            if step["sender"]["type"] == "service":
                for key in profiles["relation"]:
                    attach(key)
        if request and receiver["type"] == "service" and kinds:
            if not unit_profile:
                for group, keys in profiles["functional"].items():
                    if group in {
                        "display_interaction",
                        "analysis_generation",
                        "release_activation",
                    }:
                        continue
                    for key in keys:
                        definition = definitions[key]
                        if entity_only and key == "service.query_retrieval.data_visibility":
                            continue
                        if kinds.intersection(definition["operation_kinds"]):
                            attach(key)
            if receiver.get("technology") == "database" and (
                not unit_profile or not receiver.get("external")
            ):
                special = definitions["database.special_characters"]
                if "database.special_characters" in profiles["technology"].get("database", []) and (
                    not special["operation_kinds"] or kinds.intersection(special["operation_kinds"])
                ):
                    attach("database.special_characters")
            for entity in [] if entity_only else step.get("entity_ids", []):
                rules = _business_rules(bundle, step, entity)
                if rules:
                    for condition, source_refs in rules:
                        attach(
                            "service.business_attribute_constraint",
                            entity=entity,
                            condition=condition,
                            source_refs=source_refs,
                        )
        if unit_profile and receiver["type"] == "service":
            for unit in owners.get(step["id"], []):
                if unit.get("functional_owner_id"):
                    continue
                operations = set(unit["crud"])
                if unit["kind"] == "external":
                    attach(
                        "service.base.availability",
                        source_refs=unit["source_refs"],
                        related_calls=unit["occurrences"],
                    )
                    special = definitions["database.special_characters"]
                    if (
                        receiver.get("technology") == "database"
                        and "database.special_characters"
                        in profiles["technology"].get("database", [])
                        and (
                            not special["operation_kinds"]
                            or operations.intersection(special["operation_kinds"])
                        )
                    ):
                        attach(
                            "database.special_characters",
                            source_refs=unit["source_refs"],
                            related_calls=unit["occurrences"],
                        )
                checks = {}
                for group, keys in profiles["functional"].items():
                    if group in {
                        "display_interaction",
                        "analysis_generation",
                        "release_activation",
                    }:
                        continue
                    for key in keys:
                        if (
                            key != "service.query_retrieval.data_visibility"
                            and operations.intersection(definitions[key]["operation_kinds"])
                        ):
                            checks.setdefault(functional_family(key), []).append(key)
                for keys in checks.values():
                    attach(
                        keys[0],
                        operation_unit_id=unit["id"],
                        source_refs=unit["source_refs"],
                        functional_keys=keys,
                        related_calls=unit["occurrences"],
                    )
        for field in [] if bundle.get("analysis_profile") in COMMAND_PROFILES else step["data"]:
            field_refs = field.get("source_refs", [])
            checks = []
            if field.get("required") is True:
                checks.append(("completeness", field["name"] + "缺失", field_refs))
            if field.get("type"):
                checks.append(("type", field["name"] + "不是" + field["type"], field_refs))
            for constraint in field.get("constraints", []):
                kind = DATA_KINDS.get(constraint["kind"])
                if kind and constraint["kind"] != "required":
                    for condition in _constraint_failures(field, constraint):
                        checks.append(
                            (kind, condition, constraint.get("source_refs") or field_refs)
                        )
                if request and (
                    constraint["kind"] in {"reference", "resource_reference", "validity"}
                    or constraint["kind"] == "other"
                    and re.search(r"引用|指向|父资源|关联资源", str(constraint.get("value", "")))
                    and re.search(r"存在|有效|已删除", str(constraint.get("value", "")))
                ):
                    for template in templates_for("api.data.validity"):
                        attach(
                            "api.data.validity",
                            "data",
                            field=field,
                            condition=field["name"] + "：" + template["condition"],
                            source_refs=constraint.get("source_refs") or field_refs,
                            variant_id=template["variant_id"],
                            generation_origin="reference_template",
                        )
            for kind, condition, source_refs in checks:
                attach(
                    "api.data." + kind,
                    "data",
                    field=field,
                    condition=condition,
                    source_refs=source_refs,
                )
        if not request:
            business = [
                (condition, source_refs)
                for field in step["data"]
                for condition, source_refs in _attribute_business_rules(
                    field, kinds, response=True, fallback_refs=refs
                )
            ]
            if business:
                for entity in step.get("entity_ids") or [None]:
                    for condition, source_refs in business:
                        attach(
                            "service.business_attribute_constraint",
                            "sender",
                            entity=entity,
                            condition=condition,
                            source_refs=source_refs,
                        )
    _attach_entity_units(bundle, output, definitions)
    if bundle.get("analysis_profile") in COMMAND_PROFILES:
        from scene_completion.analysis.ssd.command_contract import generate_fields

        generate_fields(bundle, output)
    return output


def _attach_entity_units(bundle, output, definitions):
    """Mount each constrained entity attribute at its one anchored step.

    The concern belongs to the entity attribute, not to a message field: a query
    that merely carries one attribute of the entity does not narrow the entity's
    other constraints. The anchored step owns every constrained attribute of the
    entities it declares, and an attribute declared on several messages stays a
    single concern on the one anchored step.
    """
    for unit in (bundle.get("field_anchors") or {}).get("units", []):
        key = unit["concern_key"]
        definition = definitions.get(key, {})
        if (
            not definition.get("enabled", True)
            or definition.get("scope", "interaction") != "interaction"
        ):
            continue
        step = next((s for s in bundle["steps"] if s["id"] == unit["step_id"]), None)
        if step is None:
            continue
        context_step = next(
            (s for s in bundle["steps"] if s["id"] == unit.get("operation_step_id")), step
        )
        if not any(
            _unit_applies({**unit, **atom}, context_step) for atom in unit.get("atoms") or [unit]
        ):
            # A rule that only governs editing must not be re-checked by an
            # operation that merely touches the same entity.
            continue
        refs = unit.get("source_refs") or step.get("source_refs", [])
        if bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE:
            refs = (
                unique([ref for atom in unit.get("atoms") or [unit] for ref in atom["source_refs"]])
                or refs
            )
        concern = add_concern(
            output,
            bundle,
            "G",
            step,
            key,
            "data" if bundle.get("analysis_profile") in STRUCTURED_PROFILES else "receiver",
            field=None,
            entity=unit["entity"],
            attribute=unit["attribute"],
            obligation_scope=unit.get("obligation_scope"),
            condition=unit["attribute"] + "：" + _atom_condition(unit),
            refs=refs,
            rule_id=RULE_VERSION + ":" + key,
        )
        if concern is None:
            continue
        concern["scope"] = "interaction"
        concern["unit_id"] = unit["unit_id"]
        concern["attribute"] = unit["attribute"]
        templates = templates_for(key)
        template = (
            templates[-1 if key == "service.business_attribute_constraint" else 0]
            if templates
            else {}
        )
        for atom in unit.get("atoms") or [unit]:
            projected = {**unit, **atom, "atoms": []}
            if not _unit_applies(projected, context_step):
                continue
            variant = (
                next((t for t in templates if t["variant_id"] == "immutable_attribute"), template)
                if atom.get("operation") == "immutable"
                else template
            )
            condition = unit["attribute"] + "：" + _atom_condition(projected)
            scene = add_scenario(
                output,
                concern,
                condition,
                variant.get("expected", ""),
                atom.get("source_refs") or unit.get("source_refs") or step.get("source_refs", []),
            )
            scene.update(
                **{
                    k: variant[k]
                    for k in ("template_id", "variant_id", "template_version", "generation_origin")
                    if k in variant
                },
                scope="interaction",
            )


EDIT_ONLY_OPERATIONS = {"conditional_range", "state_equals"}
EDITING_KINDS = {"create", "update"}


def _unit_applies(unit, step):
    """Whether a declared rule governs this step's actual operation.

    A relationship stated as "when X is A, Y >= 1" describes what an editor must
    submit. A publish operation is implemented as an update but does not thereby
    inherit every rule for editing entity fields, so the primary operation
    decides - the same precedence ``_business_conditions`` already applies.
    Plain field checks (format, range, uniqueness, completeness) are storage
    properties and stay applicable everywhere the entity is reached.
    """
    if unit.get("operation") not in EDIT_ONLY_OPERATIONS:
        return True
    kinds = set((step.get("operation") or {}).get("kinds") or [])
    primary = (
        "publish"
        if "publish" in kinds
        else next((kind for kind in ("create", "update", "delete", "read") if kind in kinds), None)
    )
    return primary in EDITING_KINDS


def _atom_condition(unit):
    """Readable failure condition; a missing standard is named, never invented."""
    atoms = unit.get("atoms") or []
    if atoms:
        return "；".join(
            dict.fromkeys(_atom_condition({**unit, **atom, "atoms": []}) for atom in atoms)
        )
    name = unit["attribute"]
    operation = unit.get("operation")
    value = unit.get("value")
    pending = unit.get("value_pending")
    label = {
        "required": "缺失",
        "format": "不满足格式要求",
        "unique": "不满足唯一性要求",
        "validity": "引用的资源无效",
    }.get(operation)
    if operation == "minimum":
        return (
            name
            + (" <= " if unit.get("exclusive") else " < ")
            + json.dumps(value, ensure_ascii=False)
            if value is not None
            else (name + "低于下限（" + (pending or "具体标准待确认") + "）")
        )
    if operation == "maximum":
        return (
            name
            + (" >= " if unit.get("exclusive") else " > ")
            + json.dumps(value, ensure_ascii=False)
            if value is not None
            else (name + "超过上限（" + (pending or "具体标准待确认") + "）")
        )
    if operation == "max_length":
        return (
            name + "长度超出上限"
            if value is None
            else (name + "长度 > " + json.dumps(value, ensure_ascii=False))
        )
    if operation == "min_length":
        return (
            name + "长度不足下限"
            if value is None
            else (name + "长度 < " + json.dumps(value, ensure_ascii=False))
        )
    if operation == "max_size":
        return name + "大小超出上限"
    if operation == "enum":
        return name + "不属于枚举集合" + json.dumps(value, ensure_ascii=False)
    if operation in {"state_precondition", "state_equals"}:
        return name + "不满足状态前置条件" + json.dumps(value, ensure_ascii=False)
    if operation == "state_enum":
        return name + "不在允许状态集合" + json.dumps(value, ensure_ascii=False)
    if operation == "conditional_range" and isinstance(value, dict):
        # A relationship between two attributes stays one condition.
        then = value.get("then") or {}
        when = value.get("when") or {}
        return (
            name
            + "关系不满足：当"
            + str(when.get("field"))
            + "为"
            + str(when.get("equals"))
            + "时，"
            + str(then.get("field"))
            + str(then.get("operator"))
            + str(then.get("value"))
        )
    if unit.get("failure_condition"):
        return unit["failure_condition"]
    if operation == "type":
        return name + "不是 " + str(value)
    if label:
        return name + label
    return name + "不满足声明约束"


ORIGIN_SUFFIXES = (".md", ".markdown", ".xlsx")


def origin_documents(root):
    """Original requirement/design documents shipped beside structured inputs."""
    from scene_completion.inputs.provenance import source_origins

    root = io_path(root).resolve()
    manifest = root / "source-documents.json"
    declared = {}
    registered = manifest.is_file()
    if registered:
        for row in json.loads(manifest.read_text(encoding="utf-8-sig"))["documents"]:
            path = (root / row["path"]).resolve()
            role = row["role"]
            if (
                not path.is_relative_to(root)
                or path.suffix.lower() not in ORIGIN_SUFFIXES
                or role not in {"RR", "SR", "test"}
                or path in declared
            ):
                raise ValueError("source-documents.json 的原文路径或角色无效：" + row["path"])
            aliases = row.get("aliases", [])
            if not isinstance(aliases, list) or any(
                not isinstance(a, str) or not a.strip() for a in aliases
            ):
                raise ValueError("原文别名须为非空字符串列表")
            declared[path] = (role, aliases)
    found = []
    for path in sorted(declared if registered else root.rglob("*")):
        if (
            path.suffix.lower() not in ORIGIN_SUFFIXES
            or any(part.startswith(".") for part in path.relative_to(root).parts)
            or not path.is_file()
        ):
            continue
        role, aliases = declared.get(path, (None, []))
        role = role or (
            "RR"
            if "需求" in path.name or re.match(r"RR[._-]", path.name, re.I)
            else "SR"
            if "设计" in path.name or re.match(r"SR[._-]", path.name, re.I)
            else "test"
            if path.suffix.lower() == ".xlsx"
            or "测试" in path.name
            or re.match(r"test[._-]", path.name, re.I)
            else None
        )
        if role is None:
            continue
        try:
            relative = path.relative_to(root).as_posix()
            for doc in source_origins.read_origin_document(
                path, role, "test" if role == "test" else "existing"
            ):
                key = relative + ("#" + doc["sheet"] if doc.get("sheet") else "")
                found.append(
                    {
                        **doc,
                        "path": key,
                        "source_path": relative,
                        "id": ident("document", key),
                        "configured_aliases": aliases,
                        "registered": registered,
                    }
                )
        except (OSError, UnicodeError, ValueError):
            continue
    return source_origins.origin_index(found)


def cited_origins(bundle, origins):
    """Only the original documents a citation actually points at."""
    names = {
        (row.get("origin") or {}).get("document")
        for row in walk_refs(bundle)
        if (row.get("origin") or {}).get("match") in {"exact", "located"}
    }
    return [
        {"name": doc.get("path") or doc["name"], "role": doc.get("role"), "content": doc["content"]}
        for doc in origins
        if (doc.get("path") or doc["name"]) in names
    ]


def walk_refs(value):
    from scene_completion.inputs.documents.source_documents import walk_references

    return walk_references(value)


def _input_root(directory):
    root = io_path(directory).resolve()
    return root / "输入文件" if (root / "输入文件").is_dir() else root


def case_identity(file, directory, raw=None):
    """Shared scheduler/builder identity, independent of an absolute checkout path.

    Pass the already decoded raw object when discovering cases. Passing an empty
    mapping returns a stable fallback identity even for a malformed source file.
    """
    root = _input_root(directory)
    file = Path(file)
    if not file.is_absolute():
        file = root / file
    file = io_path(file).resolve()
    relative = file.parent.relative_to(root)
    if raw is None:
        raw = json.loads(file.read_text(encoding="utf-8-sig"))
    inferred = None
    if raw.get("use_case") and not raw.get("use_case_id") and (root / "功能树.json").is_file():
        tree = json.loads((root / "功能树.json").read_text(encoding="utf-8-sig"))
        ids = [
            row.get("functionId") or row.get("ucId")
            for _, row in case_candidates(
                tree.get("functions", []),
                raw["use_case"],
                raw.get("resource") or file.parent.parent.name,
            )
        ]
        if len(ids) == 1:
            inferred = ids[0]
    return {
        "id": raw.get("use_case_id") or inferred or ident("case", relative.as_posix()),
        "name": raw.get("use_case") or file.parent.name,
    }


def build_cases(directory, case_ids=None, *, case_files=None, generate=True, profile=None):
    """Build independent bundles; an explicit file list isolates worker failures.

    Shared API/entity documents are read once, but only the selected SysOperation
    files are decoded when ``case_files`` is supplied by a case worker.
    """
    from scene_completion.inputs.structured import authoring_cases

    root = _input_root(directory)
    if case_files is None:
        entries = list(authoring_cases.discover(root, case_identity))
    else:
        if isinstance(case_files, (str, Path)):
            case_files = [case_files]
        entries = []
        for value in case_files:
            file = Path(value)
            file = io_path(file if file.is_absolute() else root / file).resolve()
            if (
                not file.is_relative_to(root)
                or file.name not in authoring_cases.FILES
                or not file.is_file()
            ):
                raise ValueError("用例文件必须是输入目录内的 SysOperation.json：" + str(value))
            if file not in [entry[0] for entry in entries]:
                entries.append((file, None, None))
    if not entries:
        raise ValueError("目录中没有 SysOperation.json；原始输入须先转换为用例 SSD")
    origins = origin_documents(root)
    sources = Sources(root, origins)
    tree_path = root / "功能树.json"
    tree = json.loads(tree_path.read_text(encoding="utf-8-sig")) if tree_path.exists() else None
    contracts = api_contracts(sources, tree, tree_path)
    selections = {case_ids} if isinstance(case_ids, str) else set(case_ids or [])
    bundles = []
    from scene_completion.analysis.ssd.inverse import existing_channel, test_channel

    for file, discovered_case, error in entries:
        if discovered_case and selections and not selections.intersection(discovered_case.values()):
            continue
        if error:
            raise ValueError(error)
        value = authoring_cases.read(file, root)
        authored = authoring_cases.is_authoring(value)
        if authored:
            # Rendered in memory: literal values stay as supplied and only the
            # step references are re-pointed. The folder name is presentation.
            raw = authoring_cases.sys_operation(value)
            case = authoring_cases.case_identity(value)
        else:
            raw = value
            case = case_identity(file, root, raw)
        if selections and not selections.intersection(case.values()):
            continue
        name = sources.add(file) if Path(file).is_relative_to(root) else None
        tree_link = raw.get("function_tree") or {}
        local_tree_path, local_tree, local_contracts = tree_path, tree, contracts
        if tree_link.get("path"):
            linked_path = (root / tree_link["path"]).resolve()
            if not linked_path.is_relative_to(root):
                raise ValueError("功能树路径超出输入目录")
            if linked_path != tree_path and linked_path.is_file():
                local_tree_path = linked_path
                local_tree = json.loads(linked_path.read_text(encoding="utf-8-sig"))
                local_contracts = api_contracts(sources, local_tree, local_tree_path)
        active_profile = profile or raw.get("analysis_profile")
        entity_only = active_profile in STRUCTURED_PROFILES
        tree_case = tree_link.get("uc_id") or case["id"]
        case_entity = raw.get("resource") or (file.parent.parent.name if not authored else None)
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
            from scene_completion.analysis.ssd.command_contract import catalogue

            local_contracts = catalogue(
                sources,
                local_tree,
                local_tree_path,
                tree_case,
                case["name"],
                selected=tree_hits if active_profile == COMMAND_OPERATION_PROFILE else None,
            )
        steps, missing = _steps(
            raw, sources, name, local_contracts, root=root, entity_only=entity_only
        )
        bundle = {
            "version": VERSION,
            "coverage_policy": "coverage-any-confirmed-v2",
            "case": case,
            **({"analysis_profile": active_profile} if active_profile else {}),
            "function_tree_case_id": tree_case,
            **({"case_entity": case_entity} if case_entity else {}),
            "function_tree_path": local_tree_path.relative_to(root).as_posix()
            if local_tree
            else None,
            "steps": steps,
            "channels": {key: channel() for key in ("G", "E", "GT")},
            "documents": [],
            "decisions": [],
            "pending": [],
            "entities": entities_for(
                sources,
                local_tree,
                tree_case,
                case["name"],
                local_tree_path,
                entity_only=entity_only,
                selected=tree_hits if active_profile == COMMAND_OPERATION_PROFILE else None,
            ),
            # Retain the project catalogue so a reviewer can select another
            # declared API. G still uses only the actual step's bound fields.
            "apis": [] if entity_only else deepcopy(list(local_contracts.values())),
            "registry": default_registry(),
            "rule_version": RULE_VERSION,
        }
        if active_profile == COMMAND_OPERATION_PROFILE and len(tree_hits) != 1:
            bundle["pending"].append(
                pending(
                    ident("case-tree-gap", case["id"]),
                    "功能树用例无法唯一对应",
                    reason="功能树用例无法唯一对应",
                    case_match_gap=True,
                    candidates=[row.get("functionId") or row.get("ucId") for _, row in tree_hits],
                )
            )
        if command_mode:
            from scene_completion.analysis.ssd.command_contract import attach

            attach(bundle, local_contracts)
        if entity_only and not command_mode:
            candidates = (local_tree or {}).get("functions", [])
            matches = [f for f in candidates if (f.get("functionId") or f.get("ucId")) == tree_case]
            matches = matches or [f for f in candidates if f.get("name") == case["name"]]
            bundle["operation_hints"] = (
                [
                    {k: row[k] for k in ("apiId", "name", "method") if row.get(k)}
                    for layer in ("rrLayer", "srLayer")
                    for row in matches[0].get(layer, {}).get("commands", [])
                    if row.get("method")
                ]
                if len(matches) == 1
                else []
            )
        if missing:
            bundle["pending"].append(
                pending(
                    ident("pending", case["id"], "order"),
                    "Order 未引用的步骤已保留，请确认顺序：" + ", ".join(missing),
                    [sources.ref(name)] if name else [],
                )
            )
        from scene_completion.analysis.interactions.field_anchors import anchors

        bundle["field_anchors"] = anchors(bundle)
        for step in steps:
            if "parent_candidates" in step:
                bundle["pending"].append(
                    pending(
                        ident("pending", case["id"], "response", step["id"]),
                        "响应未能唯一关联到请求",
                        step["source_refs"],
                        step_id=step["id"],
                        candidate_step_ids=step["parent_candidates"],
                    )
                )
        if generate:
            bundle["channels"]["G"] = generate_g(bundle)
        bundle["channels"]["E"] = existing_channel(
            bundle,
            file.parent,
            sources,
            supplied=authoring_cases.supplied_exceptions(raw, sources, file, "E")
            if authored
            else (),
            raw=raw if not authored else None,
        )
        if authored:
            # The supplied extension mapping is the test case's own binding; keep
            # it visible for review instead of re-deriving it.
            bundle["extension_mapping"] = deepcopy(
                (raw.get("extension-mapping") or {}).get("items", [])
            )
        bundle["channels"]["GT"] = test_channel(
            bundle,
            sources,
            supplied=authoring_cases.supplied_exceptions(raw, sources, file, "GT")
            if authored
            else (),
            mapping=raw.get("extension-mapping") if authored else None,
            mapping_source=(
                (file.with_name("extension-mapping.json"), "")
                if file.name == authoring_cases.LEGACY_MAIN
                else (file, "/extension_mapping")
            )
            if authored and (raw.get("extension-mapping") or {}).get("items")
            else None,
        )
        bundle["documents"] = deepcopy(list(sources.documents.values()))
        bundle["origin_documents"] = cited_origins(bundle, origins)
        bundle["source_documents"] = unique(
            [
                {"path": d["source_path"], "role": d["role"], "aliases": d["configured_aliases"]}
                for d in origins
            ]
        )
        bundles.append(bundle)
    if selections:
        found = {value for bundle in bundles for value in bundle["case"].values()}
        unknown = selections - found
        if unknown:
            raise ValueError("未知用例：" + ", ".join(sorted(unknown)))
    return bundles


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
            from scene_completion.analysis.ssd.command_contract import attach

            if (
                result.get("analysis_profile") == COMMAND_OPERATION_PROFILE
                and result.get("operation_units") is not None
            ):
                from scene_completion.analysis.ssd.operation_units import rebind

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
