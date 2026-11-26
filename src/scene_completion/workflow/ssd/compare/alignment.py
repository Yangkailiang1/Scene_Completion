"""Align independently classified evidence to the final G snapshot."""

import re

from scene_completion.domain.coverage import GRAIN_POLICY, binary_status
from scene_completion.domain.current_scope import AVAILABILITY
from scene_completion.domain.scenario_conditions import disjoint
from scene_completion.domain.ssd import (
    actor_security,
    concern_policy,
    input_concerns,
    interface_fields,
    llm_responses,
    validation_scope,
)
from scene_completion.domain.ssd.construction import add_concern, add_scenario, ident, unique
from scene_completion.domain.ssd.matching import same_failure_text
from scene_completion.infrastructure.execution_events import emit
from scene_completion.workflow.ssd.compare import (
    decision_review,
    independent_mount,
    resource_alignment,
)
from scene_completion.workflow.ssd.resolve import entity_semantics as evidence
from scene_completion.workflow.ssd.resolve.operations import in_operation_scope
from scene_completion.workflow.ssd.shared import (
    authentication_evidence,
    binding_targets,
    failure_context,
)

ALIGN = "ssd-ground-align"


def _keys(record):
    return set(record.get("concern_keys", [])) | {record["key"]}


def _uses_step(link, step_id):
    return step_id in (
        link["occurrences"]
        + link.get("validation_step_ids", [])
        + link.get("response_step_ids", [])
    )


def _summary_command(bundle, raw, actual, *, allow_external=False):
    """Use only a uniquely identified inbound command for broad evidence."""
    bindings = bundle.get("command_bindings", {})
    step = next((s for s in bundle["steps"] if s["id"] == actual), {})
    receiver = step.get("receiver", {})
    named = bundle.get("interface_field_policy") == interface_fields.INPUT_FIELD_POLICY
    if not named and (raw.get("parameter") or {}).get("direction") in {"response", "return"}:
        return None
    if (
        not allow_external
        and receiver.get("external")
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
    keys = set(part["keys"]) - actor_security.SERVICE_KEYS
    if (
        actual
        and keys & actor_security.HUMAN_KEYS
        and not failure_context.auth_requests(steps, actual)
    ):
        keys -= actor_security.HUMAN_KEYS
    return keys


def _candidates(bundle, raw, part, step_facts, name_ids=()):
    from scene_completion.domain.ssd.path_inputs import character_failure
    from scene_completion.workflow.ssd.compare import path_alignment

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
    character_evidence = concern_policy.path_inputs(bundle) and bool(
        keys & {concern_policy.FIELD, "api.data.format"}
    )
    explicit_characters = character_evidence and character_failure(part["condition"])
    field_character_ids = (
        path_alignment.field_character_candidates(
            bundle, raw, part, bundle["channels"]["G"]["scenarios"], fields
        )
        if explicit_characters or character_evidence and "正则" in part["condition"]
        else set()
    )
    character_ids = set(field_character_ids) | set(name_ids)
    failure = part.get("explicit_failure")
    llm_variant = (
        llm_responses.failure_variant(part["condition"]) if llm_responses.KEY in keys else None
    )
    llm_anchors = (
        {
            (step["id"], role)
            for step, role in llm_responses.placements(
                bundle,
                part["condition"],
                actual,
                context=[raw["condition"], *part["source_evidence"]],
            )
        }
        if llm_variant
        else set()
    )
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
        command = _summary_command(bundle, raw, actual, allow_external=scope == "missing_body")
        if command is None:
            return
        source_commands = {command}
    auth_requests = failure_context.auth_requests(step_facts, actual)
    consolidated = concern_policy.applies(bundle)
    special_anchors = (
        {
            (step["id"], target)
            for step, target in independent_mount.special_character_anchors(
                bundle, {**raw, "condition": part["condition"]}, actual
            )
        }
        if consolidated and concern_policy.DATABASE in keys
        else set()
    )
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
        if scenario["status"] != "active" or (
            concern_policy.path_inputs(bundle)
            and (
                scenario.get("path_input")
                and scenario["id"] not in name_ids
                or scenario["key"] == concern_policy.DATABASE
            )
        ):
            continue
        if scenario.get("name_character_input") and scenario["id"] not in name_ids:
            continue
        character_cross_step = scenario["id"] in character_ids
        if (explicit_characters or character_ids) and not character_cross_step:
            continue
        if not resource_alignment.compatible(part, scenario):
            continue
        if not actor_security.in_scope(
            scenario["key"], scenario["target"], steps[scenario["step_id"]]
        ):
            continue
        if scenario["key"] == llm_responses.KEY:
            step_id, role = scenario["step_id"], scenario["target"]
            if (step_id, role) in llm_anchors and scenario.get("variant_id") == llm_variant:
                yield {
                    **{
                        key: scenario[key]
                        for key in ("id", "condition", "expected", "step_id", "target", "key")
                    },
                    "receiver": steps[step_id]["receiver"]["name"],
                    "sender": steps[step_id]["sender"]["name"],
                    "sender_kind": step_facts[step_id]["sender_kind"],
                    "concern_keys": [llm_responses.KEY],
                }
            continue
        if failure == "missing_credential" and (
            scenario.get("key") != concern_policy.AUTH
            or failure not in scenario.get("failure_variants", {})
            and scenario.get("variant_id") != failure
        ):
            continue
        if (
            consolidated
            and scenario["key"] == concern_policy.DATABASE
            and (scenario["step_id"], scenario["target"]) not in special_anchors
        ):
            continue
        if (
            consolidated
            and scenario["key"] == concern_policy.AUTH
            and "failure_variants" in scenario
            and (subtype := concern_policy.subtype(concern_policy.AUTH, part["condition"]))
            and subtype not in scenario.get("failure_variants", {})
        ):
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
        if (not character_cross_step and not keys.intersection(scenario_keys)) or disjoint(
            part["condition"], scenario["condition"]
        ):
            continue
        if (
            actual
            and scenario["key"] in actor_security.HUMAN_KEYS
            and (scenario.get("call_step_id") or scenario["step_id"]) not in auth_requests
        ):
            continue
        unit = units.get(scenario.get("operation_unit_id"), {})
        if not in_operation_scope(unit, actual, interface_fields.command_id(raw)):
            continue
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
        if (
            external
            and not database_only
            and not character_cross_step
            and scenario["key"] != concern_policy.DATABASE
            and receiver != external
        ):
            continue
        if not character_cross_step and cmd and source_commands and cmd not in source_commands:
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
                    or not character_cross_step
                    and cmd not in source_commands
                    or declared_field
                    and field["id"] not in field_ids
                    and scenario["id"] not in name_ids
                    or names
                    and not declared_field
                    and not character_cross_step
                    and (field.get("wire_name") or field["name"]).casefold() not in names
                ):
                    continue
                if (
                    not character_cross_step
                    and len(source_commands) > 1
                    and any(
                        other["id"] != field["id"]
                        and other.get("command_id") in source_commands
                        and other["name"] == field["name"]
                        for other in fields.values()
                    )
                ):
                    continue
            elif (
                (names and (field.get("wire_name") or field["name"]).casefold() not in names)
                or (parameter.get("location") and field["location"] != parameter["location"])
                or (direction and field.get("direction") != direction)
            ):
                continue
        elif (
            named
            and declared_field
            and scenario.get("entity_id")
            and scenario["id"] not in name_ids
        ):
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
                    "resource_reference",
                    "resource_failure",
                    "failure_variants",
                    "variant_id",
                    "input_character_rule",
                    "name_character_input",
                    "path_input",
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


def _source_concern(bundle, channel, raw, part, primary):
    step = next(s for s in bundle["steps"] if s["id"] == primary["step_id"])
    if primary.get("input_group"):
        return input_concerns.add_group(bundle, channel, step, primary["key"], raw["source_refs"])
    field = next((f for f in step["data"] if f["id"] == primary.get("field_id")), None)
    return add_concern(
        bundle["channels"][channel],
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
        resource_reference=primary.get("resource_reference"),
        path_input=primary.get("path_input"),
        condition=part["condition"],
        refs=raw["source_refs"],
    )


def _input_focus(bundle, channel, raw, part):
    keys = set(part["keys"])
    if len(keys) != 1 or not keys <= input_concerns.KEYS or part.get("resource_check"):
        return
    key = next(iter(keys))
    candidates = {
        row["step_id"]
        for row in part["candidates"]
        if row["key"] == key and row["target"] in {"data", "receiver"}
    }
    if not candidates:
        actual = part["failure_step_id"]
        hint = actual or raw.get("step_ref")
        command = (
            _summary_command(bundle, raw, hint, allow_external=True)
            if hint or interface_fields.command_id(raw)
            else None
        )
        if command:
            candidates = {bundle["command_bindings"][command]["primary_step_id"]}
        elif actual and not interface_fields.command_id(raw):
            # A local validator with several parent requests is still ambiguous.
            step = next(s for s in bundle["steps"] if s["id"] == actual)
            candidates = {
                s for s in (step.get("validates") or [actual]) if step["direction"] != "return"
            }
    if len(candidates) == 1:
        step = next(s for s in bundle["steps"] if s["id"] in candidates)
        input_concerns.add_group(bundle, channel, step, key, raw["source_refs"])


def _path_concerns(bundle, channel, raw, part, candidates):
    groups = {cid for scene in candidates for cid in scene["concern_ids"]}
    for generated in bundle["channels"]["G"]["concerns"]:
        if generated["id"] in groups:
            row = _source_concern(bundle, channel, raw, part, generated)
            _decision(
                bundle,
                channel,
                "concern",
                row["id"],
                generated["id"],
                "full",
                "测试来源涉及同一 SR 接口的路径参数及对应校验类别",
            )


def _add_matches(bundle, channel, raw, part, selected, all_matches, location):
    output = bundle["channels"][channel]
    order = {s["id"]: s["order"] for s in bundle["steps"]}
    actual = location["failure_step_id"]
    primary = min(
        (scene for scene, _ in selected),
        key=lambda scene: (scene["step_id"] != actual, order[scene["step_id"]], scene["id"]),
    )
    parent = primary
    if primary.get("path_input") and not input_concerns.applies(bundle):
        parent = next(
            c for c in bundle["channels"]["G"]["concerns"] if c["id"] in primary["concern_ids"]
        )
    concern = _source_concern(bundle, channel, raw, part, parent)
    identity = (
        ident(
            "path-source",
            channel,
            bundle["case"]["id"],
            primary["path_input"]["command_id"],
            part["condition"],
            part["expected"],
        )
        if primary.get("path_input")
        else None
    )
    scene = add_scenario(
        output, concern, part["condition"], part["expected"], raw["source_refs"], identity
    )
    if primary.get("path_input"):
        # One source row can link to several path obligations. Its binding must not
        # grant matches automatically when later comparing other source records.
        scene["path_input"] = {
            "command_id": primary["path_input"]["command_id"],
            **({"parameter": part["path_parameter"]} if part.get("path_parameter") else {}),
        }
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
    if primary.get("name_character_input"):
        scene["name_character_input"] = primary["name_character_input"]
    if primary["key"] == llm_responses.KEY and primary.get("variant_id"):
        scene["variant_id"] = primary["variant_id"]
    if primary.get("resource_failure"):
        scene["resource_failure"] = primary["resource_failure"]
    if concern_policy.applies(bundle) and (
        subtype := concern_policy.subtype(primary["key"], part["condition"])
    ):
        scene["failure_subtype"] = subtype
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
    parents = {row["id"]: row for row in bundle["channels"]["G"]["concerns"]}
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
                parent = parents[concern_id]
                if parent.get("input_group"):
                    source_parent = _source_concern(bundle, channel, raw, part, parent)
                    if scene["step_id"] == source_parent["step_id"]:
                        scene["concern_ids"] = unique([*scene["concern_ids"], source_parent["id"]])
                    scene["aligned_scenario_ids"] = unique(
                        [*scene.get("aligned_scenario_ids", []), generated["id"]]
                    )
                else:
                    source_parent = concern
                _decision(
                    bundle,
                    channel,
                    "concern",
                    source_parent["id"],
                    concern_id,
                    match["status"],
                    match["reason"],
                )
                scene["aligned_concern_ids"] = unique(
                    [*scene.get("aligned_concern_ids", []), concern_id]
                )
    return scene["id"]


def _fast_match(bundle, part, candidate, raw, steps):
    actual = part["failure_step_id"]
    explicit_command = interface_fields.command_id(raw)
    candidate_command = candidate.get("command_id")
    if explicit_command and (
        candidate_command
        and explicit_command != candidate_command
        or candidate.get("path_input")
        and explicit_command != candidate["path_input"]["command_id"]
    ):
        return None
    if candidate["key"] == actor_security.AUTHENTICATION:
        call = candidate.get("call_step_id") or candidate["step_id"]
        requests = failure_context.auth_requests(steps, actual)
        confirmed = set(requests) == {call}
        if not actual and not part.get("failure_step_hint"):
            if explicit_command:
                confirmed = bool(failure_context.auth_request(steps[call]))
            elif part.get("explicit_failure") == "missing_credential":
                # Preserve the existing narrow missing-header/401 inference in cases
                # with exactly one possible human request and no conflicting hint.
                confirmed = {
                    sid for sid, step in steps.items() if failure_context.auth_request(step)
                } == {call}
        if explicit_command:
            link = bundle.get("command_bindings", {}).get(explicit_command, {})
            confirmed = confirmed and link.get("primary_step_id") == call
        variants = authentication_evidence.generated_variants(candidate)
        if (
            confirmed
            and candidate["target"] == "sender"
            and actor_security.AUTHENTICATION in part["keys"]
            and variants
            and (
                explicit := authentication_evidence.explicit_variants(
                    part["condition"], part["expected"]
                )
            )
        ):
            if not explicit & variants:
                return "none", "同一人类请求，但生成场景不包含原文明确的凭证失败类型"
            if explicit <= variants and authentication_evidence.equivalent_outcome(
                part["condition"] + " " + part["expected"], candidate
            ):
                return "full", "同一人类 Actor 请求，凭证失败类型及拒绝认证的预期一致"
        return None
    # Exact text is sufficient only after fixing the obligation and actual boundary.
    if not actual or candidate["step_id"] != actual or candidate["key"] not in part["keys"]:
        return None
    if set(part["keys"]) & (actor_security.HUMAN_KEYS | actor_security.SERVICE_KEYS):
        return None
    if candidate.get("path_input") and (
        not part.get("path_parameter")
        or part["path_parameter"] != candidate["path_input"].get("parameter")
    ):
        return None
    if field := candidate.get("field_id"):
        declared_field = raw.get("field_id")
        if not declared_field and (
            (raw.get("parameter") or {}).get("name") or raw.get("field_name")
        ):
            available = {
                value["id"] for _, value in interface_fields.candidates(bundle, actual, raw)
            }
            if len(available) == 1:
                declared_field = next(iter(available))
        if field != declared_field:
            return None
    for key in (
        "entity_id",
        "attribute",
        "operation_unit_id",
        "resource_reference",
        "resource_failure",
    ):
        if candidate.get(key) and raw.get(key) != candidate[key]:
            return None
    if raw.get("target") and raw["target"] != candidate["target"]:
        return None
    if same_failure_text(part, candidate):
        return "full", "已确认同一挂载对象，原文失败条件和预期一致"
    return None


def _model_matches(semantic, inputs):
    def run(task, packet):
        return validate_result(task, semantic(task, packet), packet)

    first = run(ALIGN, inputs)["parts"]
    conflicts = {
        row["part_id"]: {
            m["candidate_id"] for m in row["matches"] if decision_review.contradictory(m)
        }
        for row in first
    }
    if not any(conflicts.values()):
        return first
    narrowed = [
        {
            **part,
            "candidates": [c for c in part["candidates"] if c["id"] in conflicts[part["id"]]],
        }
        for part in inputs["parts"]
        if conflicts[part["id"]]
    ]
    corrected = decision_review.retry(run, ALIGN, {**inputs, "parts": narrowed})
    repaired = {row["part_id"]: row for row in (corrected or {}).get("parts", [])}
    for row in first:
        conflict_ids = conflicts[row["part_id"]]
        if not conflict_ids:
            continue
        retry_row = repaired.get(row["part_id"], {})
        valid = {
            m["candidate_id"]: m
            for m in retry_row.get("matches", [])
            if not decision_review.contradictory(m)
        }
        # Keep the accepted explanation and location. A narrowed retry cannot
        # change which request the other, already judged candidates refer to.
        actual = row.get("failure_step_id")
        retry_actual = retry_row.get("failure_step_id")
        if actual and retry_actual and actual != retry_actual:
            valid = {}
        elif retry_actual and not any(
            m["status"] != "none" and m["candidate_id"] not in conflict_ids for m in row["matches"]
        ):
            row.update(
                failure_step_id=retry_actual,
                failure_step_reason=retry_row["failure_step_reason"],
            )
        if valid:
            row["reason"] = retry_row["reason"]
        row["matches"] = [
            valid.get(m["candidate_id"], m)
            for m in row["matches"]
            if m["candidate_id"] not in conflict_ids or m["candidate_id"] in valid
        ]
        if unresolved := sorted(conflict_ids - valid.keys()):
            row["conflicts"] = unresolved
        row["fallback"] = None
    return first


def align(bundle, semantic):
    from scene_completion.workflow.ssd.compare import path_alignment

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
                if llm_responses.KEY in part["keys"]:
                    if variant := llm_responses.failure_variant(part["condition"]):
                        part["explicit_failure"] = variant
                elif bundle.get("coverage_policy") == GRAIN_POLICY:
                    scope = validation_scope.summary_kind(part["condition"])
                    if scope:
                        part["validation_summary"] = scope
                name_candidates, name_issue = path_alignment.name_character_candidates(
                    bundle, original, part, generated
                )
                path_candidates, path_issue = (
                    path_alignment.candidates(bundle, original, part, generated)
                    if concern_policy.path_inputs(bundle)
                    and name_candidates is None
                    and not part.get("name_rule_only")
                    else (None, None)
                )
                if name_issue:
                    part.update(candidates=[], path_candidates=True, path_issue=name_issue)
                elif path_candidates is None:
                    resource_alignment.prepare(bundle, original, part)
                    part["candidates"] = list(
                        _candidates(
                            bundle,
                            original,
                            part,
                            step_facts,
                            name_ids={scene["id"] for scene in name_candidates or []},
                        )
                    )
                    if name_candidates:
                        [name_candidate] = name_candidates
                        part["name_candidate_id"] = name_candidate["id"]
                        if path_input := name_candidate.get("path_input"):
                            part["path_parameter"] = path_input["parameter"]
                else:
                    names = {scene["path_input"]["parameter"] for scene in path_candidates}
                    if len(names) == 1:
                        part["path_parameter"] = next(iter(names))
                    part["path_issue"] = path_issue
                    part["path_candidates"] = True
                    part["candidates"] = [
                        {
                            key: scene[key]
                            for key in (
                                "id",
                                "condition",
                                "expected",
                                "step_id",
                                "target",
                                "key",
                                "path_input",
                            )
                        }
                        for scene in path_candidates
                    ]
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
                if path_candidates:
                    _path_concerns(bundle, channel, owners[part["id"]][0], part, path_candidates)
                elif path_candidates is None and input_concerns.applies(bundle):
                    _input_focus(bundle, channel, owners[part["id"]][0], part)
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
                    {"name_character_policy": bundle["name_character_policy"]}
                    if concern_policy.name_characters(bundle)
                    else {}
                ),
                **(
                    {"coverage_policy": GRAIN_POLICY}
                    if bundle.get("coverage_policy") == GRAIN_POLICY
                    else {}
                ),
                **(
                    {"scenario_policy": bundle["scenario_policy"]}
                    if concern_policy.applies(bundle)
                    else {}
                ),
            }
            direct, model_parts = [], []
            deterministic = {}
            options_by_id = {}

            def mount_options(part):
                part_id = part["id"]
                actual = part["failure_step_id"]
                cache_key = (part_id, actual)
                if cache_key not in options_by_id:
                    options_by_id[cache_key] = independent_mount.options(
                        bundle,
                        owners[part_id][0],
                        _allowed_keys(part, step_facts, actual),
                        actual,
                        step_facts,
                        entities,
                        fields,
                        units,
                        failure=part.get("explicit_failure"),
                        condition=part["condition"],
                        context=part["source_evidence"],
                    )
                return options_by_id[cache_key]

            for part in inputs["parts"]:
                if bundle.get("coverage_policy") == GRAIN_POLICY and not part.get(
                    "validation_summary"
                ):
                    matches = [
                        {"candidate_id": candidate["id"], "status": result[0], "reason": result[1]}
                        for candidate in part["candidates"]
                        if (
                            result := _fast_match(
                                bundle, part, candidate, owners[part["id"]][0], step_facts
                            )
                        )
                    ]
                    if matches:
                        deterministic[part["id"]] = matches
                        decided = {m["candidate_id"] for m in matches}
                        remaining = [c for c in part["candidates"] if c["id"] not in decided]
                        if remaining:
                            model_parts.append(
                                {
                                    **part,
                                    "candidates": remaining,
                                    "has_confirmed_match": any(
                                        m["status"] == "full" for m in matches
                                    ),
                                }
                            )
                        else:
                            direct.append(
                                {
                                    "part_id": part["id"],
                                    "reason": matches[0]["reason"],
                                    "matches": [],
                                    "fallback": None,
                                }
                            )
                        continue
                if part.get("path_candidates"):
                    if part["candidates"]:
                        model_parts.append(part)
                    else:
                        direct.append(
                            {
                                "part_id": part["id"],
                                "reason": part["path_issue"],
                                "matches": [],
                                "fallback": None,
                            }
                        )
                elif part.get("validation_summary") and not part["candidates"]:
                    raw = owners[part["id"]][0]
                    command = _summary_command(
                        bundle,
                        raw,
                        part["failure_step_id"],
                        allow_external=part["validation_summary"] == "missing_body",
                    )
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
                    literal = part.get("explicit_failure") == "database_unavailable" or (
                        bundle.get("coverage_policy") != GRAIN_POLICY
                        and part.get("explicit_failure") == "missing_credential"
                    )
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
            model_rows = _model_matches(semantic, inputs) if model_parts else []
            results = {row["part_id"]: row for row in direct + model_rows}
            for part in parts[offset : offset + 4]:
                if part["id"] not in results:
                    continue
                row = results[part["id"]]
                if matches := deterministic.get(part["id"]):
                    row["matches"] = matches + row["matches"]
                    if any(m["status"] != "none" for m in matches):
                        row["fallback"] = None
                results[part["id"]] = _auth_alignment(
                    row, part, step_facts, part["failure_step_id"] or row.get("failure_step_id")
                )
            independent = []
            for part in parts[offset : offset + 4]:
                part_id = part["id"]
                previous = results.get(part_id, {})
                fallback = previous.get("fallback")
                if part.get("path_candidates") or previous.get("conflicts"):
                    continue
                if part.get("resource_issue"):
                    results[part_id] = {
                        "part_id": part_id,
                        "matches": [],
                        "fallback": None,
                        "reason": part["resource_issue"],
                    }
                    continue
                if any(match["status"] != "none" for match in previous.get("matches", [])):
                    continue
                if any(
                    match["candidate_id"] == part.get("name_candidate_id")
                    for match in previous.get("matches", [])
                ):
                    continue
                if check := part.get("resource_check"):
                    actual = part["failure_step_id"] or previous.get("failure_step_id")
                    usable = resource_alignment.in_scope(bundle, check, actual)
                    results[part_id] = {
                        **previous,
                        "part_id": part_id,
                        "matches": previous.get("matches", []),
                        "fallback": resource_alignment.fallback(check) if usable else None,
                        "reason": (
                            "原文已指明路径参数与失败条件，独立挂载到该接口的资源检查"
                            if usable
                            else "实际失败步骤与路径参数所属接口不一致"
                        ),
                    }
                    continue
                if fallback and fallback.get("command_id"):
                    continue
                raw = owners[part_id][0]
                if previous.get("failure_step_id") and not part["failure_step_id"]:
                    part = {**part, "failure_step_id": previous["failure_step_id"]}
                options = mount_options(part)
                if (
                    fallback
                    and independent_mount.permitted(fallback, options, step_facts, units)[0]
                ):
                    continue
                if fallback := independent_mount.confirmed_binding(raw, part, options):
                    results[part_id] = {
                        **previous,
                        "part_id": part_id,
                        "matches": previous.get("matches", []),
                        "fallback": fallback,
                        "reason": "原文的失败条件与主成功流中唯一适用的挂载对象一致",
                    }
                elif options:
                    independent.append({**part, "candidates": [], "mount_options": options})
                else:
                    results[part_id] = {
                        **previous,
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
                    results[row["part_id"]] = {
                        **previous,
                        **row,
                        "matches": previous.get("matches", []),
                        "failure_step_id": row.get("failure_step_id")
                        or previous.get("failure_step_id"),
                        "failure_step_reason": row.get("failure_step_reason")
                        or previous.get("failure_step_reason"),
                    }
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
                if set(
                    part["keys"]
                ) <= actor_security.HUMAN_KEYS and failure_context.service_security(
                    step_facts, location["failure_step_id"]
                ):
                    audit.setdefault("scope_exclusions", []).append(
                        {"condition": part["condition"], "keys": part["keys"], **location}
                    )
                    continue
                if row.get("conflicts"):
                    source_id = raw["id"]
                    if selected:
                        source_id = _add_matches(
                            bundle, channel, raw, part, selected, matches, location
                        )
                        audit["bindings"].append(
                            {
                                "record_id": source_id,
                                "matches": [m for _, m in selected],
                                **location,
                            }
                        )
                    else:
                        audit["rejected_bindings"].append(
                            {
                                "reason": decision_review.REASON,
                                "condition": part["condition"],
                                "matching_conflict": True,
                            }
                        )
                    for candidate_id in row["conflicts"]:
                        pair, left, right = (
                            ("G_E", candidate_id, source_id)
                            if channel == "E"
                            else ("GT_G", source_id, candidate_id)
                        )
                        decision_review.record_conflict(
                            bundle, pair, left, right, generated[candidate_id]["step_id"]
                        )
                    continue
                independent_candidates = (
                    matches
                    if part.get("path_candidates")
                    else [
                        pair for pair in matches if pair[0]["id"] == part.get("name_candidate_id")
                    ]
                )
                if independent_candidates and not selected:
                    record_id = _add_matches(
                        bundle, channel, raw, part, independent_candidates, matches, location
                    )
                    audit["bindings"].append({"record_id": record_id, "matches": [], **location})
                    continue
                if selected:
                    if part.get("resource_check") and not resource_alignment.in_scope(
                        bundle, part["resource_check"], location["failure_step_id"]
                    ):
                        audit["rejected_bindings"].append(
                            {
                                "reason": "实际失败步骤与路径参数所属接口不一致",
                                "condition": part["condition"],
                            }
                        )
                        continue
                    record_id = _add_matches(
                        bundle, channel, raw, part, selected, matches, location
                    )
                    audit["bindings"].append(
                        {"record_id": record_id, "matches": [m for _, m in selected], **location}
                    )
                    continue
                fallback = None if part.get("path_candidates") else row.get("fallback")
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
                        "resource_failure": part.get("resource_failure"),
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
                                if fallback["key"] == llm_responses.KEY:
                                    scene["variant_id"] = part["explicit_failure"]
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
            if audit.get("scope_exclusions") and not failures and not audit["bindings"]:
                audit.update(kind="out_of_scope", reason=actor_security.OUT_OF_SCOPE)
            if failures:
                row = incoming[audit["record_id"]]
                row.update(
                    reason="；".join(dict.fromkeys(f["reason"] for f in failures)),
                    needs_semantic=False,
                )
                audit["reason"] = row["reason"]
                if all(f.get("matching_conflict") for f in failures):
                    row["step_id"] = None  # The conflict already tracks its exact candidate IDs.
                if audit["bindings"]:
                    row.update(condition="；".join(f["condition"] for f in failures), step_id=None)
                else:
                    audit["kind"] = "pending"
                output["pending"].append(row)
        if channel == "GT":
            bundle["gt_identification_run_complete"] = bool(bundle.get("gt_source_available"))
    from scene_completion.domain.ssd.matching import PAIRS

    input_concerns.group_bundle(bundle, PAIRS)


def strip_align_summary(result):
    if isinstance(result, dict) and isinstance(result.get("reason"), str):
        result.pop("reason")
        emit("ground_align_summary_discarded")


def _auth_alignment(row, part, steps, actual):
    """Check candidate and fallback against the same concrete request boundary."""
    security_keys = actor_security.HUMAN_KEYS | actor_security.SERVICE_KEYS
    if (
        not set(part["keys"]) & security_keys
        and (row.get("fallback") or {}).get("key") not in security_keys
    ):
        return row
    requests = failure_context.auth_requests(steps, actual)
    candidates = {candidate["id"]: candidate for candidate in part["candidates"]}
    positive = [
        (match, candidates[match["candidate_id"]])
        for match in row["matches"]
        if match["status"] != "none" and candidates[match["candidate_id"]]["key"] in security_keys
    ]
    calls = {g.get("call_step_id") or g.get("step_id") for _, g in positive}
    boundary_issue = "身份或权限异常未核实属于同一人类 Actor 请求边界，待定位"
    rejected = set()
    for match, candidate in positive:
        call = candidate.get("call_step_id") or candidate.get("step_id")
        if (
            candidate["key"] in actor_security.SERVICE_KEYS
            or candidate["target"] != "sender"
            or (len(calls) > 1 and len(requests) != 1)
            or call not in (requests if actual else failure_context.auth_requests(steps, call))
        ):
            rejected.add(match["candidate_id"])
    fallback = row.get("fallback")
    invalid_fallback = False
    if fallback and fallback["key"] in security_keys:
        call = fallback["step_id"]
        invalid_fallback = (
            fallback["key"] not in set(part["keys"]) & actor_security.HUMAN_KEYS
            or fallback["target"] not in {"sender", "human"}
            or call not in (requests if actual else failure_context.auth_requests(steps, call))
        )
    if rejected or invalid_fallback:
        return {
            **row,
            "matches": [
                {**match, "status": "none", "reason": boundary_issue}
                if match["candidate_id"] in rejected
                else match
                for match in row["matches"]
            ],
            "fallback": None if invalid_fallback else fallback,
            "reason": boundary_issue,
        }
    return row


def validate_result(task, result, inputs):
    parts = {p["id"]: p for p in inputs["parts"]}
    steps = {s["id"]: s for s in inputs["steps"]}
    units = {unit["id"]: unit for unit in inputs.get("operation_units", [])}
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
        candidates = {candidate["id"]: candidate for candidate in part["candidates"]}
        for match in row["matches"]:
            unit = units.get(candidates[match["candidate_id"]].get("operation_unit_id"), {})
            if match["status"] != "none" and not in_operation_scope(unit, confirmed or actual):
                match.update(status="none", reason="实际失败步骤不属于该外部服务的同类 CRUD 调用")
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
            if part.get("has_confirmed_match"):
                row["fallback"] = None
                continue
            if any(m["status"] != "none" for m in row["matches"]):
                raise ValueError("已有 G 匹配的记录不能同时独立挂载")
            if fallback["key"] not in allowed or fallback["step_id"] not in steps:
                raise ValueError("独立挂载超出本批关注点或步骤")
            fallback, _ = binding_targets.resolve(
                fallback, steps, inputs.get("operation_units", [])
            )
            if (
                fallback
                and fallback["key"] in actor_security.HUMAN_KEYS
                and (
                    not failure_context.auth_request(steps[fallback["step_id"]])
                    or fallback["target"] != "sender"
                )
            ):
                raise ValueError("身份或权限异常的挂载与人类 Actor 请求边界不符")
    return result
