"""Deterministic, per-use-case SSD preparation and concern attachment.

G is a pure function of positive steps, contracts and entity metadata. Reverse
channels are parsed separately and never used to decide which G rules apply.
"""

import json
import re
from copy import deepcopy
from pathlib import Path

from scene_completion.domain.concern_registry import default_registry
from scene_completion.domain.ssd.construction import (
    add_concern,
    add_scenario,
    channel,
    ident,
    pending,
    unique,
)
from scene_completion.inputs.provenance.ssd_sources import (
    Sources,
    api_contracts,
    entities_for,
)

VERSION = "ssd-case-v1"
RULE_VERSION = "ssd-object-rules-v1"
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


def _person(key, participants):
    value = participants.get(key, {})
    if isinstance(value, str):
        value = {"name": value}
    name = value.get("name") or key
    technology = value.get("technology")
    if not technology and re.search(r"database|数据库", name, re.I):
        technology = "database"
    if not technology and re.search(r"\bLLM\b|大语言模型|AI模型", name, re.I):
        technology = "llm"
    return {
        "id": str(key),
        "name": str(name),
        "type": "human"
        if value.get("element_type") in {"human", "actor"} or value.get("kind") == "human"
        else "service",
        "technology": technology,
        "external": value.get("kind") == "external",
    }


def _kinds(text, method=None):
    # HTTP reads/deletes stay reads/deletes even when payloads mention a state
    # such as PUBLISHED. Publishing itself may use POST or PUT.
    method = method.upper() if method else None
    if method in {"GET", "DELETE"}:
        return ["read" if method == "GET" else "delete"]
    if re.search(r"\bpublish\b|发布|激活", text, re.I) or re.search(r"[pP]ublish(?=[A-Z])", text):
        return ["update", "publish"]
    if method:
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


def _field(step_id, value, refs):
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
    return {
        "id": ident("field", step_id, location, name),
        "name": name,
        "location": location,
        "type": None,
        "required": None,
        "constraints": [],
        "source_refs": deepcopy(refs),
    }


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


def _steps(raw, sources, file_name, contracts):
    mains = [
        (key, value)
        for key, value in raw.get("operations", {}).items()
        if value.get("scenario_kind") in {"main", "normal"}
    ]
    if len(mains) != 1:
        raise ValueError("用例需要唯一主成功 SysOperation：" + str(raw.get("use_case")))
    operation_id, operation = mains[0]
    participants = operation.get("participant", raw.get("participant", {}))
    nodes = {}
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
            nodes[key] = (group, node, pointer)
    ordered = [n.get("id") for n in operation.get("system_event", [])]
    ordered += [n.get("ref") for n in operation.get("Order", [])]
    ordered += [n.get("id") for n in operation.get("system_response", [])]
    # An incomplete Order is surfaced instead of silently changing its sequence.
    missing = [key for key in nodes if key not in ordered]
    ordered += missing
    result = []
    for order, key in enumerate(dict.fromkeys(k for k in ordered if k in nodes), 1):
        group, node, pointer = nodes[key]
        action = group == "action"
        text = node.get("content") or node.get("message") or node.get("name") or key
        refs = sources.refs(node, file_name, pointer)
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
        aid = node.get("api_id")
        contract = contracts.get(aid, {})
        kinds = _kinds(text, contract.get("method"))
        if action and receiver["technology"] != "database" and not node.get("operation_kinds"):
            kinds = []
        if action and receiver["technology"] == "database":
            kinds = _kinds(raw.get("use_case", "") + " " + text)
        data = []
        entities = []
        for row in node.get("data_ref") or []:
            if row.get("entity"):
                entities.append(row["entity"])
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
            "operation": {"name": text, "kinds": node.get("operation_kinds") or kinds},
            "data": list({p["id"]: p for p in data}.values()),
            "api_id": aid,
            "entity_ids": list(dict.fromkeys(entities)),
            "source_refs": refs,
            "aliases": [alias[1]] if alias else [],
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
                and s["api_id"] == aid
            ]
            if calls:
                step["parent_id"] = calls[-1]["id"]
                step["operation"]["kinds"] = calls[-1]["operation"]["kinds"]
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
        if not action:
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
    registry = bundle.get("registry") or default_registry()
    definitions, profiles = registry["definitions"], registry["profiles"]
    for step in bundle["steps"]:
        refs = step.get("source_refs", [])
        kinds = set(step["operation"].get("kinds", []))
        request = step["direction"] == "request"
        call = step["kind"] != "action" and step["sender"]["id"] != step["receiver"]["id"]
        receiver = step["receiver"]

        def attach(key, target="receiver", field=None, entity=None, condition="", source_refs=None):
            concern = add_concern(
                output,
                bundle,
                "G",
                step,
                key,
                target,
                field=field,
                entity=entity,
                condition=condition,
                refs=source_refs if source_refs is not None else refs,
                rule_id=RULE_VERSION + ":" + key,
            )
            if concern:
                add_scenario(
                    output,
                    concern,
                    condition or f"{definitions[key]['label']}不满足",
                    "",
                    source_refs if source_refs is not None else refs,
                )
            return concern

        if request and call and step["sender"]["type"] == "human":
            for key in profiles["human"]:
                attach(key, "sender")
        if request and call and receiver["type"] == "service":
            if receiver.get("external"):
                attach("service.base.availability")
            if step["sender"]["type"] == "service":
                for key in profiles["relation"]:
                    attach(key)
        if request and receiver["type"] == "service" and kinds:
            for group, keys in profiles["functional"].items():
                for key in keys:
                    definition = definitions[key]
                    if "idempotency" not in key and kinds.intersection(
                        definition["operation_kinds"]
                    ):
                        attach(key)
            for key in profiles["technology"].get(receiver.get("technology"), []):
                definition = definitions[key]
                if not definition["operation_kinds"] or kinds.intersection(
                    definition["operation_kinds"]
                ):
                    attach(key)
            for entity in step.get("entity_ids", []):
                rules = _business_rules(bundle, step, entity)
                if rules:
                    for condition, source_refs in rules:
                        attach(
                            "service.business_attribute_constraint",
                            entity=entity,
                            condition=condition,
                            source_refs=source_refs,
                        )
                else:
                    attach("service.business_attribute_constraint", entity=entity)
        # Technology-only operations (e.g. LLM calls) need no invented CRUD kind.
        if request and receiver.get("technology") == "llm":
            for key in profiles["technology"].get("llm", []):
                attach(key)
        for field in step["data"]:
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
    return output


def _input_root(directory):
    root = Path(directory).resolve()
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
    file = file.resolve()
    relative = file.parent.relative_to(root)
    if raw is None:
        raw = json.loads(file.read_text(encoding="utf-8-sig"))
    return {
        "id": raw.get("use_case_id") or ident("case", relative.as_posix()),
        "name": raw.get("use_case") or file.parent.name,
    }


def build_cases(directory, case_ids=None, *, case_files=None):
    """Build independent bundles; an explicit file list isolates worker failures.

    Shared API/entity documents are read once, but only the selected SysOperation
    files are decoded when ``case_files`` is supplied by a case worker.
    """
    root = _input_root(directory)
    if case_files is None:
        files = sorted(root.rglob("SysOperation.json"))
    else:
        if isinstance(case_files, (str, Path)):
            case_files = [case_files]
        files = []
        for value in case_files:
            file = Path(value)
            file = (file if file.is_absolute() else root / file).resolve()
            if (
                not file.is_relative_to(root)
                or file.name != "SysOperation.json"
                or not file.is_file()
            ):
                raise ValueError("用例文件必须是输入目录内的 SysOperation.json：" + str(value))
            if file not in files:
                files.append(file)
    if not files:
        raise ValueError("目录中没有 SysOperation.json；原始输入须先转换为用例 SSD")
    sources = Sources(root)
    tree_path = root / "功能树.json"
    tree = json.loads(tree_path.read_text(encoding="utf-8-sig")) if tree_path.exists() else None
    contracts = api_contracts(sources, tree)
    selections = {case_ids} if isinstance(case_ids, str) else set(case_ids or [])
    bundles = []
    from scene_completion.analysis.ssd.inverse import existing_channel, test_channel

    for file in files:
        raw = json.loads(file.read_text(encoding="utf-8-sig"))
        case = case_identity(file, root, raw)
        if selections and not selections.intersection(case.values()):
            continue
        name = sources.add(file)
        steps, missing = _steps(raw, sources, name, contracts)
        bundle = {
            "version": VERSION,
            "case": case,
            "steps": steps,
            "channels": {key: channel() for key in ("G", "E", "GT")},
            "documents": [],
            "decisions": [],
            "pending": [],
            "entities": entities_for(sources, tree, case["id"], case["name"]),
            # Retain the project catalogue so a reviewer can select another
            # declared API. G still uses only the actual step's bound fields.
            "apis": deepcopy(list(contracts.values())),
            "registry": default_registry(),
            "rule_version": RULE_VERSION,
        }
        if missing:
            bundle["pending"].append(
                pending(
                    ident("pending", case["id"], "order"),
                    "Order 未引用的步骤已保留，请确认顺序：" + ", ".join(missing),
                    [sources.ref(name)],
                )
            )
        bundle["channels"]["G"] = generate_g(bundle)
        bundle["channels"]["E"] = existing_channel(bundle, file.parent, sources)
        bundle["channels"]["GT"] = test_channel(bundle, sources)
        bundle["documents"] = deepcopy(list(sources.documents.values()))
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
        old = old_steps.get(step["id"])
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
