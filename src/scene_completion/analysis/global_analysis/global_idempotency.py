"""User-confirmed C/U/D policy, anchored to business effects rather than calls.

Only G gets the explicit framework default. E and GT must independently find
their own exception evidence; neither the default nor generated scenes fill them.
"""

import re
from copy import deepcopy

from scene_completion.infrastructure.storage import fingerprint

KEY = "global.idempotency"
POLICY = "global-cud-idempotency-v2"
RULE = "同一用例对同一业务实体执行同一C/U/D操作时，重复执行不得产生超出一次执行的额外业务影响。"


def validate_explicit_modes(value, inputs):
    """Require an evidenced key-conflict mode, never infer it from C/U/D alone."""
    ops = inputs.get("business-operations", {}).get("operations", [])
    if len(ops) != 1:
        return
    op = ops[0]
    identified = inputs.get("identified-concerns", {}).get("matches", [])
    if not any(
        m.get("business_operation_id") == op["id"] and m["concern_key"] == KEY for m in identified
    ):
        return
    text = " ".join(
        row["text"]
        for doc in inputs.get("normal-documents", [])
        if doc.get("channel") == "normal"
        for row in doc["lines"]
    )
    if not re.search(
        r"同键不同内容|(?:相同|同一)[^。；\n]{0,30}(?:幂等键|Idempotency-Key)"
        r"[^。；\n]{0,60}(?:内容|指纹)[^。；\n]{0,30}(?:不同|不一致)",
        text,
        re.I,
    ):
        return
    for s in value.get("scenarios", []):
        cause = s["cause"] + " " + " ".join(s["conditions"])
        if (
            s.get("business_operation_id") == op["id"]
            and s["concern_key"] == KEY
            and re.search(r"同键|同一.*键|相同.*键|Idempotency-Key", cause, re.I)
            and re.search(r"(?:内容|指纹).*?(?:不同|不一致)|不同内容", cause)
        ):
            return
    raise ValueError(
        "global idempotency omitted evidenced same-key/different-content rejection; "
        "expand it separately from same-content replay or duplicate side effects; "
        "use only this operation's positive evidence"
    )


def operations(crud, entities, groups, cases):
    """Deduplicate delegated/direct effects without inferring CRUD from HTTP."""
    entity_map = {e["id"]: e for e in entities}
    group_map = {g["id"]: g for g in groups}
    case_map = {c["id"]: c["name"] for c in cases}
    result = {}
    for row in crud:
        if row["operation"] not in {"create", "update", "delete"}:
            continue
        if row["entity_id"] not in entity_map or row["case_id"] not in group_map:
            continue
        key = (row["case_id"], row["entity_id"], row["operation"])
        group = group_map[row["case_id"]]
        aliases = list(dict.fromkeys([row["case_id"], *group["rr_ids"], *group["sr_ids"]]))
        names = list(dict.fromkeys(case_map[i] for i in aliases if i in case_map))
        op = result.setdefault(
            key,
            {
                "id": "business-operation-" + fingerprint(key)[:24],
                "case_id": row["case_id"],
                "case_aliases": aliases,
                "case_names": names,
                "entity_id": row["entity_id"],
                "entity_name": entity_map[row["entity_id"]]["name"],
                "operation": row["operation"],
                "source_refs": [],
                "interaction_refs": [],
                "api_ids": [],
            },
        )
        op["source_refs"] = list(
            {fingerprint(x): deepcopy(x) for x in op["source_refs"] + row["source_refs"]}.values()
        )
        op["interaction_refs"] = sorted(set(op["interaction_refs"] + [row["interaction_id"]]))
        if row.get("api_id"):
            op["api_ids"] = sorted(set(op["api_ids"] + [row["api_id"]]))
    return list(result.values())


def recognized(operation):
    return {
        "matches": [
            {
                "id": "global-concern-" + fingerprint([operation["id"], KEY, POLICY])[:24],
                "dependency_id": None,
                "business_operation_id": operation["id"],
                "concern_key": KEY,
                "object": operation["entity_id"],
                "basis": "用户确认的全局C/U/D幂等策略；原文引用仅证明业务操作，不冒充原文明示幂等要求。"
                + RULE,
                "source_refs": deepcopy(operation["source_refs"]),
                "policy_id": POLICY,
            }
        ],
        "pending": [],
    }


def documents_for(documents, operation, channel, branches=()):
    """Scope each independent channel using case identities and exact citations."""
    from collections import defaultdict

    from scene_completion.analysis.interactions.domain_model import source_chunks

    aliases = set(operation["case_aliases"] + operation["case_names"])
    spans = defaultdict(set)
    if channel == "test":
        from scene_completion.inputs.provenance.test_sources import records

        for record in records(documents):
            if record["scenario_type"] == "exception" and (
                record.get("case_id") in aliases or record.get("case_name") in aliases
            ):
                spans[record["source_id"]].update([record["row"], *record.get("context_rows", [])])
                for ref in record.get("source_refs", []):
                    spans[ref["source_id"]].update(range(ref["line_start"], ref["line_end"] + 1))
    elif channel == "existing":
        for branch in branches:
            if branch.get("case_hint") in aliases or branch.get("operation_hint") in aliases:
                for ref in branch["source_refs"]:
                    spans[ref["source_id"]].update(range(ref["line_start"], ref["line_end"] + 1))
    else:
        for ref in operation["source_refs"]:
            spans[ref["source_id"]].update(range(ref["line_start"], ref["line_end"] + 1))
        for doc in documents:
            lines = doc["lines"]
            for n, row in enumerate(lines):
                # Positive common policies remain available. No E or GT is read.
                if any(term in row["text"] for term in ("幂等", "重复", *aliases)):
                    spans[doc["source_id"]].update(
                        x["number"] for x in lines[max(0, n - 1) : n + 2]
                    )
    selected = []
    for doc in documents:
        lines = [row for row in doc["lines"] if row["number"] in spans[doc["source_id"]]]
        if lines:
            selected.extend(source_chunks([{**doc, "lines": lines}], max_chars=9000))
    return selected
