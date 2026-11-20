"""Classify E and GT evidence independently before G alignment."""

import re

from scene_completion.domain.ssd.construction import unique
from scene_completion.infrastructure.execution_events import emit
from scene_completion.workflow.ssd.resolve import entity_semantics as evidence

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
            result = validate_result(CLASSIFY, semantic(CLASSIFY, inputs), inputs)
            records = {row["id"]: row for row in inputs["records"]}
            for decision in result["records"]:
                raw = originals[decision["record_id"]]
                parts, issues = _verified_parts(
                    decision["parts"], records[decision["record_id"]], inputs["definitions"]
                )
                audits[channel].append(
                    {
                        **decision,
                        "parts": parts,
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
    fragments = part.get(field + "_fragments")
    if fragments is None:
        text = part[field]
        if text and (not text.strip() or text not in source[field]):
            raise ValueError("异常条件和预期须保留来源原文")
        return text
    quotes = []
    for fragment in fragments:
        origin, index, quote = (fragment[key] for key in ("field", "index", "quote"))
        if origin == "evidence":
            items = source.get("evidence", [])
            text = items[index] if index is not None and 0 <= index < len(items) else None
        else:
            text = source[origin] if index is None else None
        if not isinstance(text, str) or not quote.strip() or quote not in text:
            raise ValueError("摘录片段未逐字出现在指定的本条来源")
        quotes.append(quote)
    if not quotes or part[field]:
        raise ValueError("提供摘录片段时，对应文本留空并至少提供一条逐字摘录")
    return "；".join(quotes)


def _verified_parts(parts, source, definitions):
    verified, issues = [], []
    seen = set()
    for part in parts:
        try:
            condition = _excerpt(part, source, "condition")
            expected = _excerpt(part, source, "expected")
            keys = sorted(set(part["keys"]))
            if not condition.strip() or not keys or not set(keys) <= definitions.keys():
                raise ValueError("异常需有失败原文并引用本轮关注点")
        except ValueError as error:
            issues.append(
                {"condition": part["condition"] or source["condition"], "reason": str(error)}
            )
            continue
        signature = (condition, expected, tuple(keys))
        if signature not in seen:
            seen.add(signature)
            verified.append({**part, "condition": condition, "expected": expected, "keys": keys})

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
