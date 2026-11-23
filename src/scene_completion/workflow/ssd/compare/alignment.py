"""Align independently classified evidence to the final G snapshot."""

import re

from scene_completion.domain.coverage import GRAIN_POLICY, binary_status
from scene_completion.domain.current_scope import AVAILABILITY
from scene_completion.domain.scenario_conditions import disjoint
from scene_completion.domain.ssd import interface_fields, validation_scope
from scene_completion.domain.ssd.construction import add_concern, add_scenario, ident, unique
from scene_completion.infrastructure.execution_events import emit
from scene_completion.workflow.ssd.compare import independent_mount
from scene_completion.workflow.ssd.resolve import entity_semantics as evidence
from scene_completion.workflow.ssd.shared import binding_targets, failure_context

ALIGN = "ssd-ground-align"


def _keys(record):
    return set(record.get("concern_keys", [])) | {record["key"]}


def _uses_step(link, step_id):
    return step_id in (
        link["occurrences"]
        + link.get("validation_step_ids", [])
        + link.get("response_step_ids", [])
    )


def _summary_command(bundle, raw, actual):
    """Use only a uniquely identified inbound command for broad evidence."""
    bindings = bundle.get("command_bindings", {})
    step = next((s for s in bundle["steps"] if s["id"] == actual), {})
    receiver = step.get("receiver", {})
    named = bundle.get("interface_field_policy") == interface_fields.INPUT_FIELD_POLICY
    if not named and (raw.get("parameter") or {}).get("direction") in {"response", "return"}:
        return None
    if (
        receiver.get("external")
        and receiver.get("type") == "service"
        and step.get("kind") != "action"
    ):
        return None
    if named:
        related = interface_fields.commands_at(
            bindings, actual or raw.get("step_ref"), interface_fields.command_id(raw)
        )
        return next(iter(related)) if len(related) == 1 else None
    related = {cid for cid, link in bindings.items() if _uses_step(link, actual)}
    explicit = raw.get("api_id") or (raw.get("raw") or {}).get("api_id")
    if explicit:
        return explicit if explicit in bindings and (not related or explicit in related) else None
    if len(related) == 1:
        return next(iter(related))
    if not related and len(bindings) == 1 and (not step or step.get("kind") == "action"):
        return next(iter(bindings))
    return None


def _allowed_keys(part, steps, actual):
    keys = set(part["keys"])
    if keys & failure_context.AUTH_KEYS:
        requests = failure_context.auth_requests(steps, actual)
        keys = (keys - failure_context.AUTH_KEYS) | (
            set(requests.values()) if actual else failure_context.AUTH_KEYS
        )
    return keys


def _candidates(bundle, raw, part, step_facts):
    actual = part["failure_step_id"]
    bindings = bundle.get("command_bindings", {})
    steps = {s["id"]: s for s in bundle["steps"]}
    units = {u["id"]: u for u in bundle.get("operation_units", [])}
    fields = {f["id"]: f for s in bundle["steps"] for f in s["data"]}
    concerns = {c["id"]: c for c in bundle["channels"]["G"]["concerns"]}
    actual_step = steps.get(actual, {})
    actual_actor = actual_step.get("receiver", {})
    external = (
        actual_actor.get("id")
        if actual_actor.get("external")
        and actual_actor.get("type") == "service"
        and actual_step.get("direction") == "request"
        and actual_step.get("kind") != "action"
        else None
    )
    explicit = raw.get("api_id") or (raw.get("raw") or {}).get("api_id")
    source_commands = {cid for cid, link in bindings.items() if _uses_step(link, actual)}
    if explicit in bindings:
        source_commands = {explicit}
    named = bundle.get("interface_field_policy") == interface_fields.INPUT_FIELD_POLICY
    if named:
        source_commands = interface_fields.commands_at(
            bindings, actual or raw.get("step_ref"), interface_fields.command_id(raw)
        )
    keys = _allowed_keys(part, step_facts, actual)
    failure = part.get("explicit_failure")
    database_only = failure in {"database_access", "database_unavailable"}
    database_steps = (
        {
            (step["id"], role)
            for step, role in independent_mount.database_anchors(bundle, raw, actual).values()
        }
        if database_only
        else set()
    )
    scope = part.get("validation_summary")
    if scope:
        keys = validation_scope.keys_for(scope)
        command = _summary_command(bundle, raw, actual)
        if command is None:
            return
        source_commands = {command}
    auth_requests = failure_context.auth_requests(step_facts, actual)
    parameter = raw.get("parameter") or {}
    direction = "response" if parameter.get("direction") == "return" else parameter.get("direction")
    names = {
        f.get("wire_name") or f["name"]
        for f in fields.values()
        if f.get("command_id")
        and (not source_commands or f["command_id"] in source_commands)
        and re.search(
            r"(?<![A-Za-z0-9_])" + re.escape(f.get("wire_name") or f["name"]) + r"(?![A-Za-z0-9_])",
            part["condition"],
            re.IGNORECASE,
        )
    }
    declared_field = parameter.get("name") or raw.get("field_name")
    if declared_field:
        names = {declared_field}
    field_ids = (
        {
            f["id"]
            for _, f in interface_fields.candidates(bundle, actual or raw.get("step_ref"), raw)
        }
        if named and declared_field
        else set()
    )
    names = {name.casefold() for name in names}
    for scenario in bundle["channels"]["G"]["scenarios"]:
        if scenario["status"] != "active":
            continue
        if failure == "missing_credential" and scenario.get("variant_id") != failure:
            continue
        if database_only and (
            (scenario["step_id"], scenario["target"]) not in database_steps
            or scenario["key"] != AVAILABILITY
            or (
                failure == "database_access" and scenario.get("variant_id") == "service_unavailable"
            )
            or (
                failure == "database_unavailable"
                and scenario.get("variant_id") != "service_unavailable"
            )
        ):
            continue
        scenario_keys = _keys(scenario)
        if not scenario.get("concern_keys"):
            for cid in scenario["concern_ids"]:
                if cid in concerns:
                    scenario_keys.update(_keys(concerns[cid]))
        if not keys.intersection(scenario_keys) or disjoint(
            part["condition"], scenario["condition"]
        ):
            continue
        if (
            actual
            and scenario["key"] in failure_context.AUTH_KEYS
            and (
                auth_requests.get(scenario.get("call_step_id") or scenario["step_id"])
                != scenario["key"]
            )
        ):
            continue
        unit = units.get(scenario.get("operation_unit_id"), {})
        target = steps[scenario["step_id"]]
        receiver = target["receiver"]["id"]
        field = fields.get(scenario.get("field_id"))
        cmd = (
            scenario.get("command_id") or unit.get("command_id") or (field or {}).get("command_id")
        )
        if scope:
            if not cmd:
                primary_commands = {
                    cid
                    for cid, link in bindings.items()
                    if link.get("primary_step_id") == target["id"]
                }
                if len(primary_commands) == 1:
                    cmd = next(iter(primary_commands))
                elif scenario.get("entity_id") and scenario.get("attribute"):
                    cmd = next(iter(source_commands))
            if cmd not in source_commands or not validation_scope.applies(
                scope,
                scenario,
                field,
                fields,
                cmd,
                bundle.get("command_aliases", {}),
                field_policy=bundle.get("interface_field_policy"),
            ):
                continue
        elif (
            bundle.get("coverage_policy") == GRAIN_POLICY
            and validation_scope.summary_kind(scenario["condition"]) == "json_syntax"
        ):
            continue
        if external and not database_only and receiver != external:
            continue
        if cmd and source_commands and cmd not in source_commands:
            continue
        if raw.get("entity_id") and scenario.get("entity_id") not in {None, raw["entity_id"]}:
            continue
        if raw.get("attribute") and scenario.get("attribute") not in {None, raw["attribute"]}:
            continue
        if (
            not named
            and raw.get("field_id")
            and scenario.get("field_id") not in {None, raw["field_id"]}
        ):
            continue
        if field:
            if named:
                if (
                    field.get("conflicts")
                    or cmd not in source_commands
                    or declared_field
                    and field["id"] not in field_ids
                    or names
                    and not declared_field
                    and (field.get("wire_name") or field["name"]).casefold() not in names
                ):
                    continue
                if len(source_commands) > 1 and any(
                    other["id"] != field["id"]
                    and other.get("command_id") in source_commands
                    and other["name"] == field["name"]
                    for other in fields.values()
                ):
                    continue
            elif (
                (names and (field.get("wire_name") or field["name"]).casefold() not in names)
                or (parameter.get("location") and field["location"] != parameter["location"])
                or (direction and field.get("direction") != direction)
            ):
                continue
        elif named and declared_field and scenario.get("entity_id"):
            if not any(
                (alias := bundle.get("command_aliases", {}).get(fid, {}).get(scenario["key"]))
                and (alias["entity_id"], alias["attribute"])
                == (scenario["entity_id"], scenario.get("attribute"))
                for fid in field_ids
            ):
                continue
        yield {
            **{
                k: scenario[k]
                for k in (
                    "id",
                    "condition",
                    "expected",
                    "step_id",
                    "target",
                    "key",
                    "entity_id",
                    "attribute",
                    "field_id",
                    "applicable_operations",
                    "command_id",
                    "call_step_id",
                    "concern_keys",
                    "operation_unit_id",
                )
                if k in scenario
            },
            "receiver": target["receiver"]["name"],
            "sender": target["sender"]["name"],
            "sender_kind": step_facts[target["id"]]["sender_kind"],
            "concern_keys": sorted(scenario_keys),
            **(
                {
                    "field_name": field.get("wire_name") or field["name"],
                    **(
                        {
                            "field_location": field["location"],
                            "field_direction": field.get("direction"),
                        }
                        if not named
                        else {}
                    ),
                }
                if field
                else {}
            ),
        }


def _decision(bundle, channel, level, source, generated, status, reason):
    pair, left, right = (
        ("G_E", generated, source) if channel == "E" else ("GT_G", source, generated)
    )
    value = {
        "id": ident("grounded", pair, level, left, right),
        "level": level,
        "pair": pair,
        "left_id": left,
        "right_id": right,
        "status": status,
        "reason": reason,
        "origin": "auto",
    }
    existing = next(
        (
            d
            for d in bundle["decisions"]
            if (d["pair"], d["level"], d["left_id"], d["right_id"]) == (pair, level, left, right)
        ),
        None,
    )
    if existing is None:
        bundle["decisions"].append(value)
    elif existing["origin"] != "manual" and ("none", "partial", "full").index(status) > (
        "none",
        "partial",
        "full",
    ).index(existing["status"]):
        existing.update(value)


def _add_matches(bundle, channel, raw, part, selected, all_matches, location):
    output = bundle["channels"][channel]
    order = {s["id"]: s["order"] for s in bundle["steps"]}
    actual = location["failure_step_id"]
    primary = min(
        (scene for scene, _ in selected),
        key=lambda scene: (scene["step_id"] != actual, order[scene["step_id"]], scene["id"]),
    )
    step = next(s for s in bundle["steps"] if s["id"] == primary["step_id"])
    field = next((f for f in step["data"] if f["id"] == primary.get("field_id")), None)
    concern = add_concern(
        output,
        bundle,
        channel,
        step,
        primary["key"],
        primary["target"],
        field=field,
        entity=primary.get("entity_id"),
        attribute=primary.get("attribute"),
        obligation_scope=primary.get("obligation_scope"),
        operation_unit_id=primary.get("operation_unit_id"),
        condition=part["condition"],
        refs=raw["source_refs"],
    )
    scene = add_scenario(output, concern, part["condition"], part["expected"], raw["source_refs"])
    scene["source_record_ids"] = unique([*scene.get("source_record_ids", []), raw["id"]])
    scene["identification_reason"] = part["classification_reason"]
    if raw.get("verified_excerpts"):
        scene["verified_excerpts"] = unique(
            [
                *scene.get("verified_excerpts", []),
                *raw["verified_excerpts"],
            ]
        )
    if part.get("validation_summary"):
        scene["validation_summary"] = part["validation_summary"]
    failure_context.annotate(scene, location, location.get("failure_step_reason"))
    if raw.get("extension_id"):
        scene.setdefault("extension_id", raw["extension_id"])
        scene["extension_ids"] = unique([*scene.get("extension_ids", []), raw["extension_id"]])
    for key in (
        "command_id",
        "call_step_id",
        "validation_step_ids",
        "response_step_ids",
        "related_call_step_ids",
    ):
        if primary.get(key):
            scene[key] = primary[key]
    for generated, match in all_matches:
        _decision(
            bundle,
            channel,
            "scenario",
            scene["id"],
            generated["id"],
            match["status"],
            match["reason"],
        )
        if match["status"] in {"full", "partial"}:
            for concern_id in generated["concern_ids"]:
                _decision(
                    bundle,
                    channel,
                    "concern",
                    concern["id"],
                    concern_id,
                    match["status"],
                    match["reason"],
                )
                scene["aligned_concern_ids"] = unique(
                    [*scene.get("aligned_concern_ids", []), concern_id]
                )
    return scene["id"]


def align(bundle, semantic):
    if not semantic:
        return
    step_facts = {s["id"]: s for s in evidence._steps(bundle)}
    entities = evidence._catalogue(bundle)
    fields = evidence.interface_fields(bundle)
    generated = {s["id"]: s for s in bundle["channels"]["G"]["scenarios"]}
    units = [
        {k: v for k, v in u.items() if k != "source_refs"}
        for u in bundle.get("operation_units", [])
    ]
    for channel, audits in bundle.get("source_classifications", {}).items():
        output = bundle["channels"][channel]
        incoming = {r["id"]: r for r in output["pending"] if r.get("original")}
        parts, owners = [], {}
        exception_ids = set()
        for audit in audits:
            source_id = audit["record_id"]
            if audit["kind"] == "pending":
                incoming[source_id].update(reason=audit["reason"], needs_semantic=False)
                continue
            if audit["kind"] == "exception":
                exception_ids.add(source_id)
                audit.update(bindings=[], rejected_bindings=list(audit.get("pending_parts", [])))
            for index, detail in enumerate(audit["parts"]):
                original = incoming[source_id]["original"]
                context = evidence._record(bundle, incoming[source_id])
                part = {
                    **{k: v for k, v in detail.items() if k != "verified_excerpts"},
                    "id": ident("source-part", source_id, index, detail["condition"]),
                    "failure_step_id": context["failure_step_id"],
                    "failure_step_hint": context["failure_step_hint"],
                    "branch": context["branch"],
                    "source_evidence": context["evidence"],
                    "classification_reason": audit["reason"],
                }
                failure, keys = failure_context.explicit_failure(
                    part["condition"], part["expected"]
                )
                if failure and keys.intersection(part["keys"]):
                    part["explicit_failure"] = failure
                if bundle.get("coverage_policy") == GRAIN_POLICY:
                    scope = validation_scope.summary_kind(part["condition"])
                    if scope:
                        part["validation_summary"] = scope
                part["candidates"] = list(_candidates(bundle, original, part, step_facts))
                excerpts = detail.get("verified_excerpts") or []
                refs = unique(
                    [
                        *[ref for excerpt in excerpts for ref in excerpt.get("source_refs", [])],
                        *original["source_refs"],
                    ]
                )
                owners[part["id"]] = (
                    {**original, "source_refs": refs, "verified_excerpts": excerpts},
                    audit,
                    part,
                )
                parts.append(part)
        for offset in range(0, len(parts), 4):
            inputs = {
                "case": bundle["case"],
                "channel": channel,
                "steps": list(step_facts.values()),
                "entities": entities,
                "interface_fields": list(fields.values()),
                "operation_units": units,
                "parts": parts[offset : offset + 4],
                **(
                    {"coverage_policy": GRAIN_POLICY}
                    if bundle.get("coverage_policy") == GRAIN_POLICY
                    else {}
                ),
            }
            direct, model_parts = [], []
            options_by_id = {}

            def mount_options(part):
                part_id = part["id"]
                if part_id not in options_by_id:
                    options_by_id[part_id] = independent_mount.options(
                        bundle,
                        owners[part_id][0],
                        _allowed_keys(part, step_facts, part["failure_step_id"]),
                        part["failure_step_id"],
                        step_facts,
                        entities,
                        fields,
                        units,
                        failure=part.get("explicit_failure"),
                    )
                return options_by_id[part_id]

            for part in inputs["parts"]:
                if part.get("validation_summary") and not part["candidates"]:
                    raw = owners[part["id"]][0]
                    command = _summary_command(bundle, raw, part["failure_step_id"])
                    owner = (
                        bundle["command_bindings"][command]["primary_step_id"] if command else None
                    )
                    if not owner:
                        continue
                    direct.append(
                        {
                            "part_id": part["id"],
                            "reason": "有明确的请求校验异常，按原文的唯一接口挂载",
                            "matches": [],
                            "fallback": {
                                "step_id": owner,
                                "target": "receiver",
                                "key": "service.base.request_data",
                                "entity_id": None,
                                "attribute": None,
                                "field_id": None,
                                "operation_unit_id": None,
                                "command_id": command,
                            },
                        }
                    )
                elif part.get("validation_summary"):
                    reason = "来源总述与候选属于同一接口及请求校验范围"
                    direct.append(
                        {
                            "part_id": part["id"],
                            "reason": reason,
                            "fallback": None,
                            "matches": [
                                {"candidate_id": c["id"], "status": "full", "reason": reason}
                                for c in part["candidates"]
                            ],
                        }
                    )
                elif part["candidates"]:
                    candidate = part["candidates"][0]
                    literal = part.get("explicit_failure") in {
                        "missing_credential",
                        "database_unavailable",
                    }
                    options = (
                        mount_options(part) if literal and len(part["candidates"]) == 1 else []
                    )
                    if len(options) == 1 and all(
                        options[0][key] == candidate.get(key)
                        for key in ("key", "step_id", "target")
                    ):
                        reason = "原文与生成场景指向同一对象及同一失败条件"
                        direct.append(
                            {
                                "part_id": part["id"],
                                "reason": reason,
                                "fallback": None,
                                "matches": [
                                    {
                                        "candidate_id": candidate["id"],
                                        "status": "full",
                                        "reason": reason,
                                    }
                                ],
                            }
                        )
                    else:
                        model_parts.append(part)
            inputs["parts"] = model_parts
            model_rows = (
                validate_result(ALIGN, semantic(ALIGN, inputs), inputs)["parts"]
                if model_parts
                else []
            )
            results = {row["part_id"]: row for row in direct + model_rows}
            independent = []
            for part in parts[offset : offset + 4]:
                part_id = part["id"]
                previous = results.get(part_id, {})
                fallback = previous.get("fallback")
                if fallback and fallback.get("command_id"):
                    continue
                if any(match["status"] != "none" for match in previous.get("matches", [])):
                    continue
                raw = owners[part_id][0]
                options = mount_options(part)
                if (
                    fallback
                    and independent_mount.permitted(fallback, options, step_facts, units)[0]
                ):
                    continue
                if fallback := independent_mount.confirmed_binding(raw, part, options):
                    results[part_id] = {
                        "part_id": part_id,
                        "matches": previous.get("matches", []),
                        "fallback": fallback,
                        "reason": "原文的失败条件与主成功流中唯一适用的挂载对象一致",
                    }
                elif options:
                    independent.append({**part, "candidates": [], "mount_options": options})
                else:
                    results[part_id] = {
                        "part_id": part_id,
                        "matches": previous.get("matches", []),
                        "fallback": None,
                        "reason": {
                            "missing_credential": "无法核实 Authorization 所属的认证请求边界",
                            "database_access": "无法核实该访问异常对应的外部数据库",
                            "database_unavailable": "无法核实该不可用异常对应的外部数据库",
                        }.get(
                            part.get("explicit_failure"),
                            "主成功流中缺少与该关注点及原文一致的步骤、对象或字段",
                        ),
                    }
            if independent:
                mount_inputs = {
                    **inputs,
                    "phase": "independent_mount",
                    "definitions": evidence.definitions(bundle),
                    "parts": independent,
                }
                mounted = validate_result(ALIGN, semantic(ALIGN, mount_inputs), mount_inputs)
                for row in mounted["parts"]:
                    previous = results.get(row["part_id"], {})
                    results[row["part_id"]] = {**row, "matches": previous.get("matches", [])}
            for part_in_batch in parts[offset : offset + 4]:
                row = results[part_in_batch["id"]]
                raw, audit, part = owners[row["part_id"]]
                matches = [(generated[m["candidate_id"]], m) for m in row["matches"]]
                selected = [(g, m) for g, m in matches if m["status"] in {"full", "partial"}]
                location = {
                    "failure_step_id": part["failure_step_id"] or row.get("failure_step_id"),
                    "failure_step_hint": part["failure_step_hint"],
                    "failure_step_reason": row.get("failure_step_reason")
                    or (None if part["failure_step_id"] else row["reason"]),
                }
                if selected:
                    record_id = _add_matches(
                        bundle, channel, raw, part, selected, matches, location
                    )
                    audit["bindings"].append(
                        {"record_id": record_id, "matches": [m for _, m in selected], **location}
                    )
                    continue
                fallback = row.get("fallback")
                target_note = None
                if fallback:
                    fallback, target_note = binding_targets.resolve(fallback, step_facts, units)
                if fallback:
                    if target_note:
                        audit.setdefault("target_corrections", []).append(target_note)
                    binding = {
                        **fallback,
                        "condition": part["condition"],
                        "expected": part["expected"],
                    }
                    issue = evidence._binding_issue(binding, step_facts, entities, fields)
                    if (
                        not issue
                        and bundle.get("interface_field_policy")
                        == interface_fields.INPUT_FIELD_POLICY
                        and binding.get("field_id")
                    ):
                        actual = (
                            location["failure_step_id"] or raw.get("step_ref") or binding["step_id"]
                        )
                        commands = interface_fields.commands_at(
                            bundle["command_bindings"], actual, interface_fields.command_id(raw)
                        )
                        field_id = binding["field_id"]
                        if (
                            fields[field_id]["command_id"] not in commands
                            or ((raw.get("parameter") or {}).get("name") or raw.get("field_name"))
                            and field_id
                            not in {
                                f["id"] for _, f in interface_fields.candidates(bundle, actual, raw)
                            }
                        ):
                            issue = "字段与来源声明的 SR 接口或字段名不符"
                    if not issue:
                        issue = evidence._mount(
                            bundle, channel, output, raw, binding, row["reason"], location=location
                        )
                    if not issue:
                        audit["bindings"].append({**binding, **location})
                        for scene in output["scenarios"]:
                            if (
                                raw["id"] in scene.get("source_record_ids", [])
                                and scene["condition"] == part["condition"]
                            ):
                                if part.get("validation_summary"):
                                    scene["validation_summary"] = part["validation_summary"]
                                    scene["command_id"] = fallback["command_id"]
                                for target, match in matches:
                                    _decision(
                                        bundle,
                                        channel,
                                        "scenario",
                                        scene["id"],
                                        target["id"],
                                        "none",
                                        match["reason"],
                                    )
                        continue
                else:
                    issue = target_note["reason"] if target_note else row["reason"]
                audit["rejected_bindings"].append(
                    {
                        "reason": issue,
                        "condition": part["condition"],
                        **(
                            {"original_target": target_note["original_target"]}
                            if target_note
                            else {}
                        ),
                    }
                )
        resolved = {a["record_id"] for a in audits if a["kind"] != "pending"}
        output["pending"] = [r for r in output["pending"] if r["id"] not in resolved]
        for audit in (a for a in audits if a["record_id"] in exception_ids):
            failures = audit["rejected_bindings"]
            if failures:
                row = incoming[audit["record_id"]]
                row.update(
                    reason="；".join(dict.fromkeys(f["reason"] for f in failures)),
                    needs_semantic=False,
                )
                audit["reason"] = row["reason"]
                if audit["bindings"]:
                    row.update(condition="；".join(f["condition"] for f in failures), step_id=None)
                else:
                    audit["kind"] = "pending"
                output["pending"].append(row)
        if channel == "GT":
            bundle["gt_identification_run_complete"] = bool(bundle.get("gt_source_available"))


def strip_align_summary(result):
    if isinstance(result, dict) and isinstance(result.get("reason"), str):
        result.pop("reason")
        emit("ground_align_summary_discarded")


def _auth_alignment(row, part, steps, actual):
    """Check candidate and fallback against the same concrete request boundary."""
    if not set(part["keys"]) & failure_context.AUTH_KEYS:
        return row
    requests = failure_context.auth_requests(steps, actual)
    candidates = {candidate["id"]: candidate for candidate in part["candidates"]}
    chosen = [
        candidates[m["candidate_id"]]
        for m in row["matches"]
        if m["status"] != "none"
        and candidates[m["candidate_id"]]["key"] in failure_context.AUTH_KEYS
    ]
    calls = {g.get("call_step_id") or g.get("step_id") for g in chosen}
    conflict = len(calls) > 1 or any(
        (requests if actual else failure_context.auth_requests(steps, call)).get(call) != g["key"]
        for g in chosen
        for call in [g.get("call_step_id") or g.get("step_id")]
    )
    fallback = row.get("fallback")
    if fallback and fallback["key"] in failure_context.AUTH_KEYS:
        call = fallback["step_id"]
        key = (requests if actual else failure_context.auth_requests(steps, call)).get(call)
        target = "sender" if key == "human.authentication" else "receiver"
        role = "human" if target == "sender" else "service"
        if key and fallback["key"] == key and fallback["target"] in {target, role}:
            # Keep verified role aliases for the existing correction audit.
            return row
        if actual and key and not any(m["status"] != "none" for m in row["matches"]):
            return {
                **row,
                "fallback": {**fallback, "key": key, "target": target},
                "reason": f"{row['reason']}。按已定位请求 {call} 的调用角色统一认证键和挂载方向",
            }
        conflict = True
    if conflict:
        return {
            **row,
            "matches": [{**m, "status": "none"} for m in row["matches"]],
            "fallback": None,
            "reason": "认证异常的候选或挂载未对齐同一调用边界，待定位",
        }
    return row


def validate_result(task, result, inputs):
    parts = {p["id"]: p for p in inputs["parts"]}
    steps = {s["id"]: s for s in inputs["steps"]}
    evidence._exact(result["parts"], "part_id", parts)
    for index, row in enumerate(result["parts"]):
        part = parts[row["part_id"]]
        evidence._exact(row["matches"], "candidate_id", [g["id"] for g in part["candidates"]])
        if not row["reason"].strip():
            raise ValueError(f"parts[{index}].reason: {row['part_id']} 须说明该部分的对齐依据")
        for candidate_index, match in enumerate(row["matches"]):
            if not match["reason"].strip():
                raise ValueError(
                    f"parts[{index}].matches[{candidate_index}].reason: {match['candidate_id']} 须说明候选依据"
                )
            if inputs.get("coverage_policy") == GRAIN_POLICY:
                match["status"] = binary_status(match["status"])
        actual = row.get("failure_step_id")
        confirmed = part.get("failure_step_id")
        if actual and (
            actual not in steps
            or (confirmed and actual != confirmed)
            or (not confirmed and not (row.get("failure_step_reason") or "").strip())
        ):
            raise ValueError("实际失败步骤须引用本用例主成功流并保留证据")
        row = _auth_alignment(row, part, steps, confirmed or actual)
        result["parts"][index] = row
        if inputs.get("phase") == "independent_mount":
            fallback = row.get("fallback")
            usable, issue = (
                independent_mount.permitted(
                    fallback, part["mount_options"], steps, inputs.get("operation_units", [])
                )
                if fallback and fallback["step_id"] in steps
                else (False, None)
            )
            if not usable:
                row["fallback"] = None
                reason = row["reason"]
                if fallback:
                    row["reason"] = issue or "提交的步骤、对象、字段或关注点超出独立挂载候选"
                else:
                    row["reason"] = "证据尚不足以确认具体交互步骤或挂载对象" + (
                        f"。{reason}"
                        if "候选为空" not in reason and "无可判定候选" not in reason
                        else ""
                    )
            continue
        allowed = _allowed_keys(part, steps, confirmed or actual)
        if fallback := row.get("fallback"):
            if any(m["status"] != "none" for m in row["matches"]):
                raise ValueError("已有 G 匹配的记录不能同时独立挂载")
            if fallback["key"] not in allowed or fallback["step_id"] not in steps:
                raise ValueError("独立挂载超出本批关注点或步骤")
            fallback, _ = binding_targets.resolve(
                fallback, steps, inputs.get("operation_units", [])
            )
            if (
                fallback
                and fallback["key"] in failure_context.AUTH_KEYS
                and (
                    failure_context.auth_request(steps[fallback["step_id"]]) != fallback["key"]
                    or fallback["target"]
                    != ("sender" if fallback["key"] == "human.authentication" else "receiver")
                )
            ):
                raise ValueError("认证异常的挂载与调用角色不符")
    return result
