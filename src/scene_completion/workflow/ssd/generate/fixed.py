"""Generate the deterministic G concerns and reference scenarios from positive inputs."""

import json
import re

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
    unique,
)
from scene_completion.workflow.ssd.shared.step_bindings import RULE_VERSION

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
    from scene_completion.domain.ssd import external_databases

    registry = current_registry(bundle.get("registry") or default_registry())
    definitions, profiles = registry["definitions"], registry["profiles"]
    entity_only = bundle.get("analysis_profile") in STRUCTURED_PROFILES
    unit_profile = bundle.get("analysis_profile") == COMMAND_OPERATION_PROFILE
    from scene_completion.workflow.ssd.resolve.operations import functional_family

    owners = {}
    for unit in bundle.get("operation_units", []):
        owners.setdefault(unit["step_id"], []).append(unit)
    external_calls = {}
    database_anchors = {}
    for appearances in external_databases.occurrences(bundle["steps"]).values():
        first, target = appearances[0]
        database_anchors.setdefault(first["id"], []).append((target, appearances))
    if unit_profile and "operation_units" in bundle:
        for step in sorted(bundle["steps"], key=lambda step: step["order"]):
            receiver = step["receiver"]
            if (
                step["direction"] == "request"
                and step["kind"] != "action"
                and step["sender"]["id"] != receiver["id"]
                and receiver["type"] == "service"
                and receiver.get("external")
                and receiver.get("technology") != "database"
            ):
                external_calls.setdefault(receiver["id"], []).append(step)
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

        for target, appearances in database_anchors.get(step["id"], []):
            database_refs = unique(
                [ref for occurrence, _ in appearances for ref in occurrence.get("source_refs", [])]
            )
            related = [occurrence["id"] for occurrence, _ in appearances]
            attach(
                "service.base.availability",
                target,
                source_refs=database_refs,
                related_calls=related,
            )
            if "database.special_characters" in profiles["technology"].get("database", []):
                attach(
                    "database.special_characters",
                    target,
                    source_refs=database_refs,
                    related_calls=related,
                )

        if request and call and step["sender"]["type"] == "human":
            for key in profiles["human"]:
                attach(key, "sender")
        if request and call and receiver["type"] == "service":
            if (
                receiver.get("external")
                and receiver.get("technology") != "database"
                and (not unit_profile or "operation_units" not in bundle)
            ):
                attach("service.base.availability")
            calls = external_calls.get(receiver["id"], [])
            if calls and calls[0]["id"] == step["id"]:
                attach(
                    "service.base.availability",
                    source_refs=unique([ref for member in calls for ref in member["source_refs"]]),
                    related_calls=[member["id"] for member in calls],
                )
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
            if receiver.get("technology") == "database" and not receiver.get("external"):
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
        from scene_completion.workflow.ssd.generate.command_fields import generate_fields

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
