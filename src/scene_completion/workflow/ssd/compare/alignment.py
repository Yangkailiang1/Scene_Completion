"""Align independently classified evidence to the final G snapshot."""

import re

from scene_completion.domain.scenario_conditions import disjoint
from scene_completion.domain.ssd.construction import add_concern, add_scenario, ident, unique
from scene_completion.infrastructure.execution_events import emit
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
    keys = _allowed_keys(part, step_facts, actual)
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
    if parameter.get("name"):
        names = {parameter["name"]}
    names = {name.casefold() for name in names}
    for scenario in bundle["channels"]["G"]["scenarios"]:
        if scenario["status"] != "active":
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
        if external and receiver != external:
            continue
        if cmd and source_commands and cmd not in source_commands:
            continue
        if raw.get("entity_id") and scenario.get("entity_id") not in {None, raw["entity_id"]}:
            continue
        if raw.get("attribute") and scenario.get("attribute") not in {None, raw["attribute"]}:
            continue
        if raw.get("field_id") and scenario.get("field_id") not in {None, raw["field_id"]}:
            continue
        if field and (
            (names and (field.get("wire_name") or field["name"]).casefold() not in names)
            or (parameter.get("location") and field["location"] != parameter["location"])
            or (direction and field.get("direction") != direction)
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
                    "field_location": field["location"],
                    "field_direction": field.get("direction"),
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
                    **detail,
                    "id": ident("source-part", source_id, index, detail["condition"]),
                    "failure_step_id": context["failure_step_id"],
                    "failure_step_hint": context["failure_step_hint"],
                    "branch": context["branch"],
                    "source_evidence": context["evidence"],
                    "classification_reason": audit["reason"],
                }
                part["candidates"] = list(_candidates(bundle, original, part, step_facts))
                owners[part["id"]] = (original, audit, part)
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
            }
            result = validate_result(ALIGN, semantic(ALIGN, inputs), inputs)
            for row in result["parts"]:
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
