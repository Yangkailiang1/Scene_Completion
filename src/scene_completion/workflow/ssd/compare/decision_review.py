"""Detect contradictory model judgments without treating prose as a scoring decision."""

import re
import unicodedata

from scene_completion.infrastructure.execution_events import emit
from scene_completion.workflow_core import TaskRejected

REASON = "匹配未完成：模型状态与判定理由矛盾，待复核"

# Only explicit verdicts or unqualified assertions about both condition and outcome
# contradict a negative result. Sharing a request or a responsibility is compatible.
_POSITIVE = re.compile(
    r"^(?:应(?:当)?|可|故|因此|最终)?(?:判(?:定|为)?|状态(?:为|是)?|结论(?:为|是)?)"
    r"[:：=]?\s*(?:full|partial)(?![A-Za-z0-9_])|^(?:full|partial)(?=[:：。；;]|$)|"
    r"^(?:两者|二者|双方)?(?:失败)?条件(?:和|及|与)(?:处理)?预期(?:均|完全|都)?"
    r"(?:等价|一致|相同|同义)(?=$|[。；;，,：:])",
    re.I,
)
_NEGATIVE = re.compile(
    r"^(?:应(?:当)?|故|因此|最终)?(?:判(?:定|为)?|状态(?:为|是)?|结论(?:为|是)?)"
    r"[:：=]?\s*none(?![A-Za-z0-9_])|^none(?=[:：。；;]|$)|"
    r"^(?:两者|二者|双方)?(?:失败)?条件(?:明确)?(?:互斥|不相交)(?=$|[。；;，,：:])",
    re.I,
)


def contradictory(row):
    reason = unicodedata.normalize("NFKC", row["reason"]).replace("`", "").strip()
    clauses = re.split(r"[。；;，,\n]|\s*[，,]?\s*(?:因此|所以|故应)\s*", reason)
    return any(
        (_POSITIVE if row["status"] == "none" else _NEGATIVE).search(clause.strip())
        for clause in clauses
    )


def retry(semantic, task, inputs):
    """Use a distinct packet containing the conflicting IDs; retain the first reply on rejection."""
    try:
        return semantic(task, {**inputs, "decision_recheck": True})
    except (TaskRejected, ValueError):
        emit("ssd_match_recheck_rejected", task=task)
        return None


def record_conflict(bundle, pair, left_id, right_id, step_id):
    value = {
        "pair": pair,
        "left_id": left_id,
        "right_id": right_id,
        "step_id": step_id,
        "reason": REASON,
        "conflict": True,
    }
    conflicts = bundle.setdefault("matching_conflicts", [])
    if value not in conflicts:
        conflicts.append(value)
        emit("ssd_match_conflict", pair=pair, left_id=left_id, right_id=right_id)


def compare_pairs(semantic, inputs, first):
    conflicts = {
        (row["left_id"], row["right_id"]) for row in first["decisions"] if contradictory(row)
    }
    if not conflicts:
        return first["decisions"], set()
    packet = {
        **inputs,
        "pairs": [
            row for row in inputs["pairs"] if (row["left"]["id"], row["right"]["id"]) in conflicts
        ],
    }
    corrected = retry(semantic, "ssd-semantic-compare", packet)
    valid = {
        (row["left_id"], row["right_id"]): row
        for row in (corrected or {}).get("decisions", [])
        if not contradictory(row)
    }
    return [
        valid.get(identity, row)
        for row in first["decisions"]
        if (identity := (row["left_id"], row["right_id"])) not in conflicts or identity in valid
    ], conflicts - valid.keys()
