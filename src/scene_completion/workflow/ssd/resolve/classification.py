"""Classify E and GT evidence independently before G alignment."""

import re

from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.ssd import (
    actor_security,
    interface_fields,
    llm_responses,
    validation_scope,
)
from scene_completion.domain.ssd.construction import unique
from scene_completion.domain.ssd.path_resources import path_parameters
from scene_completion.infrastructure.execution_events import emit
from scene_completion.workflow.ssd.resolve import entity_semantics as evidence
from scene_completion.workflow.ssd.shared.failure_context import explicit_failure, service_security

CLASSIFY = "ssd-evidence-classify"


def classify(bundle, semantic):
    if not semantic:
        return
    audits = bundle.setdefault("source_classifications", {})
    for channel in ("E", "GT"):
        rows = [
            r
            for r in bundle["channels"][channel]["pending"]
            if r.get("needs_semantic") and r.get("original")
        ]
        originals = {row["id"]: row["original"] for row in rows}
        audits[channel] = []
        for offset in range(0, len(rows), 6):
            inputs = {
                "case": bundle["case"],
                "channel": channel,
                "definitions": evidence.definitions(bundle),
                "steps": evidence._steps(bundle),
                "records": [evidence._record(bundle, row) for row in rows[offset : offset + 6]],
            }
            named = bundle.get("interface_field_policy") == interface_fields.INPUT_FIELD_POLICY
            if named:
                inputs["interface_field_policy"] = interface_fields.INPUT_FIELD_POLICY
            if "path_resource_checks" in bundle:
                inputs["resource_routes"] = [
                    {
                        "command_id": command["id"],
                        "path": command["path"],
                        "parameters": names,
                        "crud": link["crud"],
                        "step_id": link["primary_step_id"],
                    }
                    for command in bundle["commands"]
                    if (names := path_parameters(command["path"]))
                    and (link := bundle["command_bindings"].get(command["id"]))
                    and link.get("binding_source") != "step1_fallback"
                ]
            records = {row["id"]: row for row in inputs["records"]}
            steps = {step["id"]: step for step in inputs["steps"]}
            direct, remaining = [], []
            g_aligned = bundle.get("coverage_policy") == GRAIN_POLICY

            def summary_part(condition, expected):
                scope = validation_scope.summary_kind(condition) if g_aligned else None
                keys = (
                    sorted(validation_scope.keys_for(scope) & inputs["definitions"].keys())
                    if scope
                    else []
                )
                return (
                    {"condition": condition, "expected": expected, "keys": keys} if keys else None
                )

            for source in records.values():
                condition = source["condition"]
                failure, keys = explicit_failure(condition, source["expected"])
                outside_security = source.get("declared_key") in actor_security.SERVICE_KEYS or (
                    keys & actor_security.HUMAN_KEYS
                    and service_security(steps, source["failure_step_id"])
                )
                response_context = llm_responses.KEY in inputs[
                    "definitions"
                ] and llm_responses.placements(
                    bundle, condition, source["failure_step_id"], context=source["evidence"]
                )
                llm_failure = llm_responses.failure_variant(condition) if response_context else None
                if outside_security or (
                    named
                    and (
                        source["source_kind"] == "out_of_scope"
                        or (not response_context and interface_fields.output_only(condition))
                    )
                ):
                    direct.append(
                        {
                            "record_id": source["id"],
                            "kind": "out_of_scope",
                            "reason": actor_security.OUT_OF_SCOPE
                            if outside_security
                            else "该来源已标记范围外"
                            if source["source_kind"] == "out_of_scope"
                            else "条件只涉及返回值异常",
                            "parts": [],
                        }
                    )
                    continue
                if llm_failure:
                    failure, keys = llm_failure, {llm_responses.KEY}
                keys = sorted(keys & inputs["definitions"].keys())
                part = (
                    {"condition": source["condition"], "expected": source["expected"], "keys": keys}
                    if failure and keys
                    else summary_part(source["condition"], source["expected"])
                )
                if not part:
                    remaining.append(source)
                    continue
                direct.append(
                    {
                        "record_id": source["id"],
                        "kind": "exception",
                        "reason": (
                            "依据原文中明确的失败条件归类"
                            if failure and keys
                            else "原文明确描述请求校验失败，按失败类型匹配"
                        ),
                        "parts": [part],
                    }
                )
            inputs["records"] = remaining
            classified = (
                validate_result(CLASSIFY, semantic(CLASSIFY, inputs), inputs)["records"]
                if remaining
                else []
            )
            by_source = {item["record_id"]: item for item in direct + classified}
            for decision in (by_source[key] for key in records):
                raw = originals[decision["record_id"]]
                parts, issues = _verified_parts(
                    decision["parts"],
                    records[decision["record_id"]],
                    inputs["definitions"] | dict.fromkeys(actor_security.SERVICE_KEYS),
                    evidence_items=evidence.evidence_items(raw),
                )
                source = records[decision["record_id"]]
                excluded = []
                outside_keys = actor_security.SERVICE_KEYS
                if service_security(steps, source["failure_step_id"]):
                    outside_keys = outside_keys | actor_security.HUMAN_KEYS
                kept = []
                for part in parts:
                    if outside := set(part["keys"]) & outside_keys:
                        excluded.append({**part, "keys": sorted(outside)})
                    if keys := sorted(set(part["keys"]) - outside):
                        kept.append({**part, "keys": keys})
                parts = kept
                if excluded and not parts and not issues:
                    decision = {
                        **decision,
                        "kind": "out_of_scope",
                        "reason": actor_security.OUT_OF_SCOPE,
                    }
                if g_aligned and decision["kind"] == "exception":
                    conditions = {part["condition"] for part in parts}
                    # A colon introduces a scope for the examples that follow. Only
                    # standalone clauses separated by semicolons/newlines are added.
                    for text in re.split(r"[；;\n]+", source["condition"]):
                        condition = text.strip()
                        part = summary_part(condition, source["expected"])
                        if (
                            part
                            and condition not in conditions
                            and not (
                                llm_responses.failure_variant(condition)
                                and llm_responses.placements(
                                    bundle,
                                    condition,
                                    source["failure_step_id"],
                                    context=source["evidence"],
                                )
                            )
                        ):
                            verified, _ = _verified_parts([part], source, inputs["definitions"])
                            parts.extend(verified)
                            conditions.add(condition)
                if named and parts:
                    inbound = [
                        part
                        for part in parts
                        if llm_responses.KEY in part["keys"]
                        or not interface_fields.output_only(part["condition"])
                    ]
                    if not inbound and not issues:
                        decision = {
                            **decision,
                            "kind": "out_of_scope",
                            "reason": "拆分后的失败条件只涉及返回值异常",
                        }
                    parts = inbound
                audits[channel].append(
                    {
                        **decision,
                        "parts": parts,
                        **({"scope_exclusions": excluded} if excluded else {}),
                        "pending_parts": issues,
                        **(
                            {"submitted_parts": decision["parts"]}
                            if parts != decision["parts"]
                            else {}
                        ),
                        **(
                            {
                                "kind": "pending",
                                "reason": "；".join(unique(p["reason"] for p in issues)),
                            }
                            if issues and not parts
                            else {}
                        ),
                        "condition": raw["condition"],
                        "expected": raw.get("expected", ""),
                        "source_id": raw.get("extension_id") or raw.get("original_id"),
                        "source_refs": raw["source_refs"],
                    }
                )


def _excerpt(part, source, field):
    submitted = part[field]
    fragments = part.get(field + "_fragments")
    if submitted.strip():
        if submitted in source[field]:
            return submitted, [{"field": field, "index": None, "quote": submitted}]
        matches = [
            {"field": "evidence", "index": index, "quote": submitted}
            for index, item in enumerate(source.get("evidence", []))
            if isinstance(item, str) and submitted in item
        ]
        if matches:
            return submitted, matches

    if not fragments:
        if not submitted.strip():
            return "", []
        raise ValueError("异常摘录须逐字出现在本条记录的原字段或证据中")

    for fragment in fragments:
        origin, index, quote = (fragment[key] for key in ("field", "index", "quote"))
        if origin == "evidence":
            items = source.get("evidence", [])
            text = items[index] if index is not None and 0 <= index < len(items) else None
        else:
            text = source[origin] if index is None else None
        if not isinstance(text, str) or not quote.strip() or quote not in text:
            raise ValueError("摘录片段未逐字出现在指定的本条来源")
    quotes = [fragment["quote"] for fragment in fragments]
    joined = "；".join(quotes)
    # Only the boundaries inserted by the model may differ; keep each quote literal.
    if submitted and not re.fullmatch(
        r"\s*[;；]?\s*".join(re.escape(quote) for quote in quotes), submitted
    ):
        raise ValueError("全文与已核验的摘录片段不一致")
    return joined, fragments


def _verified_parts(parts, source, definitions, *, evidence_items=()):
    verified, issues = [], []
    seen = {}
    for part in parts:
        try:
            condition, condition_fragments = _excerpt(part, source, "condition")
            expected, expected_fragments = _excerpt(part, source, "expected")
            keys = sorted(set(part["keys"]))
            if not condition.strip() or not keys or not set(keys) <= definitions.keys():
                raise ValueError("异常需有失败原文并引用本轮关注点")
        except ValueError as error:
            description = (
                part["condition"]
                or "；".join(fragment["quote"] for fragment in part.get("condition_fragments", []))
                or source["condition"]
            )
            issues.append({"condition": description, "reason": str(error)})
            continue
        excerpts = []
        for subject, fragments in (
            ("condition", condition_fragments),
            ("expected", expected_fragments),
        ):
            for fragment in fragments:
                proof = {"subject": subject, **fragment}
                if fragment["field"] == "evidence" and fragment["index"] < len(evidence_items):
                    item = evidence_items[fragment["index"]]
                    if item.get("evidence_id"):
                        proof["evidence_id"] = item["evidence_id"]
                    if item["source_refs"]:
                        proof["source_refs"] = item["source_refs"]
                excerpts.append(proof)
        signature = (condition, expected, tuple(keys))
        if signature in seen:
            saved = seen[signature]
            saved["verified_excerpts"] = unique(saved["verified_excerpts"] + excerpts)
            continue
        saved = {
            "condition": condition,
            "expected": expected,
            "keys": keys,
            "verified_excerpts": excerpts,
        }
        verified.append(saved)
        seen[signature] = saved

    # A verified, complete disjunction can be represented by its original children.
    def terms(text):
        return {token.strip() for token in re.split(r"或(?:者)?|\bor\b", text) if token.strip()}

    summaries = set()
    for i, parent in enumerate(verified):
        children = terms(parent["condition"])
        if len(children) > 1 and children <= {
            item["condition"]
            for n, item in enumerate(verified)
            if n != i and item["expected"] == parent["expected"] and item["keys"] == parent["keys"]
        }:
            summaries.add(i)
    conflicts = set()
    for i, parent in enumerate(verified):
        if i in summaries:
            continue
        for j, child in enumerate(verified):
            if (
                j not in summaries
                and child["condition"] != parent["condition"]
                and (
                    child["condition"] in parent["condition"]
                    and child["expected"] == parent["expected"]
                    and child["keys"] == parent["keys"]
                )
            ):
                conflicts.update((i, j))
    issues.extend(
        {"condition": verified[i]["condition"], "reason": "总述与子条件的独立失败范围待确认"}
        for i in sorted(conflicts)
    )
    return [row for i, row in enumerate(verified) if i not in summaries | conflicts], issues


def validate_result(task, result, inputs):
    evidence.validate_source_batch(task, result, inputs)
    classified = [
        evidence.pending_without_details(row, "parts", "可用于对齐的异常明细")
        for row in result["records"]
    ]
    for row in classified:
        parts = row["parts"]
        if not row["reason"].strip() or bool(parts) != (row["kind"] == "exception"):
            raise ValueError("来源须给出分类依据，只有异常可拆分")
        distinct = []
        for part in parts:
            if part not in distinct:
                distinct.append(part)
        if len(distinct) != len(parts):
            emit(
                "duplicate_source_parts_discarded",
                record_id=row["record_id"],
                count=len(parts) - len(distinct),
            )
            row["parts"] = distinct
    result["records"] = classified
    return result
