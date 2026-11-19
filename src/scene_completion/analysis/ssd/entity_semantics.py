"""Channel-isolated semantic inference and canonical entity obligation alignment."""

from copy import deepcopy

from scene_completion.domain.current_scope import COMMAND_OPERATION_PROFILE, COMMAND_PROFILES
from scene_completion.domain.ssd.construction import add_concern, add_scenario, ident, pending
from scene_completion.domain.ssd_contracts import CRUD

ENTITY_KEYS = {
    "api.data.completeness",
    "api.data.type",
    "api.data.format",
    "api.data.length",
    "api.data.size",
    "api.data.range",
    "api.data.validity",
    "service.business_attribute_constraint",
}


def definitions(bundle):
    return {
        key: definition["description"]
        for key, definition in bundle["registry"]["definitions"].items()
        if definition.get("enabled", True)
        and definition.get("kind") == "check"
        and definition.get("scope", "interaction") == "interaction"
        and (
            key in ENTITY_KEYS
            or key.startswith(("human.", "service_relation.", "service.crud."))
            or key
            in {
                "service.query_retrieval.resource_existence",
                "service.base.availability",
                "database.special_characters",
            }
        )
    }


def _steps(bundle):
    return [
        {
            "id": s["id"],
            "kind": s["kind"],
            "direction": s["direction"],
            "sender": s["sender"]["name"],
            "receiver": s["receiver"]["name"],
            "receiver_technology": s["receiver"].get("technology"),
            "sender_kind": "human" if s["sender"]["type"] == "human" else "service",
            "receiver_external": bool(s["receiver"].get("external")),
            "crud": s["operation"].get("kinds", []),
            "entities": s["entity_ids"],
            "operation": s["operation"]["name"],
            "description": s.get("description"),
            "http_method": s["operation"].get("http_method"),
            "command_id": s["operation"].get("command_id"),
        }
        for s in bundle["steps"]
    ]


def _catalogue(bundle):
    return {e["id"]: [a["name"] for a in e["attributes"]] for e in bundle.get("entities", [])}


def _unresolved(bundle):
    fields = [(e["id"], a) for e in bundle.get("entities", []) for a in e["attributes"]]
    fields.extend(
        (f["command_id"], f)
        for s in bundle["steps"]
        for f in s.get("data", [])
        if f.get("command_id")
    )
    return {
        ident("rule", owner, attr.get("id", attr["name"]), rule["text"]): (owner, attr, rule)
        for owner, attr in fields
        for rule in attr.get("unresolved", [])
    }


def infer(bundle, semantic):
    from scene_completion.analysis.interactions.field_anchors import anchors
    from scene_completion.analysis.ssd.pipeline import generate_g

    steps = {
        s["id"]: s
        for s in bundle["steps"]
        if bundle.get("analysis_profile") != COMMAND_OPERATION_PROFILE
        and s["operation"].get("kinds_source") not in {"declared", "manual"}
    }
    rules = _unresolved(bundle)
    keys = definitions(bundle)
    inputs = {
        "case": bundle["case"],
        "steps": _steps(bundle),
        "operation_hints": bundle.get("operation_hints", []),
        "entities": _catalogue(bundle),
        "definitions": {k: keys[k] for k in sorted(ENTITY_KEYS.intersection(keys))},
        "operations": list(steps),
        "constraints": [],
    }
    unresolved = []
    for offset in range(0, max(len(rules), 1), 12):
        batch = list(rules.items())[offset : offset + 12]
        inputs["constraints"] = [
            {"id": rid, "entity": entity, "attribute": attr["name"], "rule": rule["text"]}
            for rid, (entity, attr, rule) in batch
        ]
        if not (inputs["operations"] or inputs["constraints"]):
            continue
        if not semantic:
            unresolved.extend(
                {"step_id": sid, "reason": "实际 CRUD 待分析"} for sid in inputs["operations"]
            )
            unresolved.extend({"rule_id": key, "reason": "实体约束待分析"} for key, _ in batch)
            inputs["operations"] = []
            continue
        result = semantic("ssd-entity-inference", inputs)
        for row in result["operations"]:
            operation = steps[row["step_id"]]["operation"]
            operation.update(
                kinds=row["crud"],
                kinds_source="pending" if row["state"] == "pending" else "semantic",
                reason=row["reason"],
            )
            if row["state"] == "pending":
                unresolved.append({"step_id": row["step_id"], "reason": row["reason"]})
        for row in result["constraints"]:
            entity, attr, rule = rules[row["rule_id"]]
            if row["state"] == "pending":
                unresolved.append(
                    {
                        "rule_id": row["rule_id"],
                        "entity": entity,
                        "attribute": attr["name"],
                        "rule": rule["text"],
                        "reason": row["reason"],
                    }
                )
            attr["atoms"].extend(
                {
                    "id": ident("atom", row["rule_id"], binding),
                    "concern_key": binding["key"],
                    "operation": "semantic",
                    "failure_condition": binding["failure"],
                    "applicable_operations": binding["applies_to"],
                    "source_refs": deepcopy(rule["source_refs"]),
                }
                for binding in row["bindings"]
            )
        inputs["operations"] = []
    bundle["field_anchors"] = anchors(bundle)
    bundle["contract_binding_pending"] = unresolved + bundle["field_anchors"]["pending"]
    bundle["channels"]["G"] = generate_g(bundle)


def _occurrence(bundle, source):
    raw = source.get("raw") or {}
    label = source.get("failure_step_id") or source.get("step_ref")
    label = label or (raw.get("extend_at_main") or {}).get("after")
    found = [
        s["id"] for s in bundle["steps"] if label and label in [s["id"], *s.get("aliases", [])]
    ]
    return found[0] if len(found) == 1 else None


def _record(bundle, row):
    source = row["original"]
    raw = source.get("raw") or {}
    return {
        "id": row["id"],
        "name": source.get("original_id"),
        "source_kind": source.get("scenario_type"),
        "condition": source["condition"],
        "expected": source.get("expected", ""),
        "failure_step_id": _occurrence(bundle, source),
        "failure_step_hint": source.get("failure_step_id"),
        "note": raw.get("note"),
        "evidence": raw.get("evidence", []),
    }


def _binding_issue(binding, steps, entities, fields):
    step = steps[binding["step_id"]]
    key = binding["key"]
    entity = binding["entity_id"]
    attribute = binding["attribute"]
    field_id = binding.get("field_id")
    if binding["target"] == "interface":
        field = fields.get(field_id)
        if key not in ENTITY_KEYS or not field or entity is not None or attribute is not None:
            return "接口异常缺少有效的 SR 字段绑定"
        if binding["step_id"] not in field["related_steps"]:
            return "接口异常未定位到所属调用或其校验步骤"
    elif field_id is not None:
        return "实体或参与者异常含接口字段"
    elif key in ENTITY_KEYS:
        if binding["target"] != "entity" or attribute not in entities.get(entity, []):
            return "数据异常缺少功能树中明确的实体属性对应"
    elif binding["target"] == "entity" or entity is not None or attribute is not None:
        return "服务异常的挂载对象有歧义"
    if key == "database.special_characters" and step["receiver_technology"] != "database":
        return "异常无法定位到明确的数据库操作"
    if key == "service.base.availability" and (
        not step["receiver_external"] or step["direction"] != "request" or step["kind"] == "action"
    ):
        return "服务可用性异常无法定位到实际外部服务调用"
    return None


def classify(bundle, semantic):
    """Classify before consulting G, then align only confirmed bindings."""
    classifications = bundle.setdefault("source_classifications", {})
    command_mode = bundle.get("analysis_profile") in COMMAND_PROFILES
    step_facts = {s["id"]: s for s in _steps(bundle)}
    units = bundle.get("operation_units")
    fields = {
        f["id"]: {
            "id": f["id"],
            "name": f["wire_name"],
            "location": f["location"],
            "command_id": f["command_id"],
            "related_steps": list(
                dict.fromkeys(
                    [
                        s["id"],
                        *bundle["command_bindings"][f["command_id"]]["occurrences"],
                        *f.get("validation_step_ids", []),
                        *f.get("response_step_ids", []),
                    ]
                )
            ),
        }
        for s in bundle["steps"]
        for f in s.get("data", [])
        if f.get("command_id")
    }
    for channel in ("E", "GT"):
        output = bundle["channels"][channel]
        source_rows = [
            r for r in output["pending"] if r.get("needs_semantic") and r.get("original")
        ]
        if not semantic:
            continue
        output["pending"] = [r for r in output["pending"] if r not in source_rows]
        audited = []
        for offset in range(0, len(source_rows), 6):
            batch = source_rows[offset : offset + 6]
            by_id = {r["id"]: r["original"] for r in batch}
            inputs = {
                "case": bundle["case"],
                "channel": channel,
                "steps": list(step_facts.values()),
                **({"interface_fields": list(fields.values())} if command_mode else {}),
                "entities": _catalogue(bundle),
                "definitions": definitions(bundle),
                **(
                    {
                        "operation_units": [
                            {k: v for k, v in unit.items() if k != "source_refs"} for unit in units
                        ]
                    }
                    if units is not None
                    else {}
                ),
                "records": [_record(bundle, row) for row in batch],
            }
            for result in semantic(
                "ssd-command-classify" if command_mode else "ssd-entity-classify", inputs
            )["records"]:
                source = by_id[result["record_id"]]
                audit = {
                    **result,
                    "condition": source["condition"],
                    "expected": source.get("expected", ""),
                    "source_id": source.get("extension_id") or source.get("original_id"),
                    "source_refs": source["source_refs"],
                }
                accepted, rejected = [], []
                for binding in result["bindings"]:
                    issue = _binding_issue(binding, step_facts, inputs["entities"], fields)
                    if not issue:
                        issue = _mount(bundle, channel, output, source, binding, result["reason"])
                    if issue:
                        rejected.append({**binding, "reason": issue})
                    else:
                        accepted.append(binding)
                audit["bindings"] = accepted
                if rejected:
                    audit["rejected_bindings"] = rejected
                    audit["reason"] = "；".join(dict.fromkeys(r["reason"] for r in rejected))
                    if not accepted:
                        audit["kind"] = "pending"
                if audit["kind"] == "pending" or rejected:
                    output["pending"].append(
                        pending(
                            source["id"],
                            source["condition"],
                            source["source_refs"],
                            reason=audit["reason"],
                            original=source,
                        )
                    )
                audited.append(audit)
        classifications[channel] = audited
    bundle["gt_identification_run_complete"] = bool(bundle.get("gt_source_available") and semantic)


def _mount(bundle, channel, output, source, binding, reason):
    steps = {s["id"]: s for s in bundle["steps"]}
    actual = _occurrence(bundle, source) or binding["step_id"]
    entity, attribute, key = (binding[k] for k in ("entity_id", "attribute", "key"))
    field_id = binding.get("field_id")
    field = None
    mapped_step = binding["step_id"]
    if field_id:
        for step in steps.values():
            field = next((f for f in step["data"] if f["id"] == field_id), None)
            if field:
                mapped_step = step["id"]
                break
        alias = bundle.get("command_aliases", {}).get(field_id, {}).get(key)
        if alias:
            entity, attribute, field = alias["entity_id"], alias["attribute"], None
            field_id = None
    target = "data" if binding["target"] in {"entity", "interface"} else binding["target"]
    operation_unit_id = None
    if bundle.get("operation_units") is not None and target == "receiver":
        from scene_completion.analysis.ssd.operation_units import functional

        if functional(key):
            operations = set(bundle["registry"]["definitions"][key]["operation_kinds"])
            stated = binding.get("operation_unit_id")
            hits = [
                unit
                for unit in bundle["operation_units"]
                if (not stated or stated == unit["id"])
                and (actual in unit["related_steps"] or binding["step_id"] in unit["related_steps"])
                and operations.intersection(unit["crud"])
            ]
            if len(hits) != 1:
                return "无法唯一对齐到已挂载的接口或外部服务 CRUD"
            operation_unit_id = hits[0]["id"]
            mapped_step = hits[0]["step_id"]
    candidates = [
        c
        for c in bundle["channels"]["G"]["concerns"]
        if c["key"] == key
        and c["target"] == target
        and c.get("operation_unit_id") == operation_unit_id
        and c.get("field_id") == field_id
        and c.get("entity_id") == entity
        and c.get("attribute") == attribute
        and ((entity and attribute) or c["step_id"] == mapped_step)
        and (
            not c.get("obligation_scope")
            or any(
                set(c["obligation_scope"]).intersection(steps[sid]["operation"]["kinds"])
                for sid in [
                    actual,
                    *steps[actual].get("validates", []),
                    *([steps[actual]["parent_id"]] if steps[actual].get("parent_id") else []),
                ]
                if sid in steps
            )
        )
    ]
    if (entity and attribute and len(candidates) > 1) or (
        not candidates
        and entity
        and attribute
        and any(
            c["key"] == key and c.get("entity_id") == entity and c.get("attribute") == attribute
            for c in bundle["channels"]["G"]["concerns"]
        )
    ):
        return "无法唯一判定实体约束作用域"
    g = candidates[0] if len(candidates) == 1 else None
    step = steps[g["step_id"] if g else mapped_step]
    refs = source["source_refs"]
    concern = add_concern(
        output,
        bundle,
        channel,
        step,
        key,
        target,
        field=field,
        entity=entity,
        attribute=attribute,
        condition=binding["condition"],
        refs=refs,
        obligation_scope=g.get("obligation_scope") if g else None,
        operation_unit_id=operation_unit_id,
    )
    if concern is None:
        return "关注点在当前规则中未启用"
    scene = add_scenario(output, concern, binding["condition"], binding["expected"], refs)
    scene["failure_step_id"] = actual
    scene["failure_step_ids"] = list(dict.fromkeys([*scene.get("failure_step_ids", []), actual]))
    scene["identification_reason"] = reason
    if field:
        scene.update(command_id=field["command_id"], call_step_id=field["call_step_id"])
    if g:
        for key in ("validation_step_ids", "response_step_ids", "related_call_step_ids"):
            if g.get(key):
                scene[key] = g[key]
    elif field:
        for key in ("validation_step_ids", "response_step_ids"):
            if field.get(key):
                scene[key] = field[key]

    if source.get("extension_id"):
        scene["extension_id"] = source["extension_id"]
        scene["extension_ids"] = list(
            dict.fromkeys([*scene.get("extension_ids", []), source["extension_id"]])
        )


def _exact(rows, key, expected):
    names = [row[key] for row in rows]
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise ValueError("模型必须对本批每个来源恰好返回一条判定")


def validate_result(task, value, inputs):
    if task == "ssd-entity-inference":
        _exact(value["operations"], "step_id", inputs["operations"])
        _exact(value["constraints"], "rule_id", [r["id"] for r in inputs["constraints"]])
        for row in value["operations"]:
            if (row["state"] == "operation") != bool(row["crud"]) or len(row["crud"]) != len(
                set(row["crud"])
            ):
                raise ValueError("实际CRUD、判定状态或重复枚举不正确")
        for row in value["constraints"]:
            _validate_bindings(row, "state", "mapped")
            for b in row["bindings"]:
                if b["key"] not in inputs["definitions"] or not b["failure"].strip():
                    raise ValueError("实体规则绑定引用未知关注点或空失败条件")
                if not set(b["applies_to"]) <= set(CRUD):
                    raise ValueError("实体规则的CRUD作用域无效")
        return value
    _exact(value["records"], "record_id", [r["id"] for r in inputs["records"]])
    steps = {s["id"]: s for s in inputs["steps"]}
    for row in value["records"]:
        _validate_bindings(row, "kind", "exception")
        for b in row["bindings"]:
            if (
                b["step_id"] not in steps
                or b["key"] not in inputs["definitions"]
                or not b["condition"].strip()
            ):
                raise ValueError("逆向结果引用未知步骤、未知关注点或空失败条件")
    return value


def _validate_bindings(row, classification, expected):
    if (row[classification] == expected) != bool(row["bindings"]) or not row["reason"].strip():
        raise ValueError("分类与具体绑定数量不符或欠缺依据")
