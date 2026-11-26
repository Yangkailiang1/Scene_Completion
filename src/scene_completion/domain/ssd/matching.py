"""Deterministic SSD bindings, candidate discovery and match assignment."""

import re
import unicodedata

from scene_completion.domain.coverage import GRAIN_POLICY
from scene_completion.domain.scenario_conditions import disjoint
from scene_completion.domain.ssd import concern_policy, path_resources
from scene_completion.domain.ssd.llm_responses import different_failures
from scene_completion.domain.ssd.validation_scope import compatible

PAIRS = {"G_E": ("G", "E"), "GT_G": ("GT", "G"), "GT_E": ("GT", "E")}


def _records(bundle):
    for channel in ("G", "E", "GT"):
        for kind in ("concerns", "scenarios", "pending"):
            for row in bundle["channels"][channel].get(kind, []):
                yield channel, kind, row


def display_binding(row):
    return (
        row.get("step_id"),
        row.get("target"),
        row.get("field_id") or "",
        row.get("entity_id") or "",
        row.get("key"),
        row.get("attribute") or "",
        *row.get("obligation_scope", []),
        *([row["operation_unit_id"]] if row.get("operation_unit_id") else []),
        *path_resources.identity(row),
    )


def binding(row):
    if row.get("input_group"):
        return ("input_group", row["step_id"], row["key"])
    if path_input := row.get("path_input"):
        return ("path_input", path_input["command_id"], path_input.get("parameter"), row["key"])
    if row.get("operation_unit_id"):
        return (
            "operation",
            row["operation_unit_id"],
            row.get("target"),
            row.get("key"),
            *path_resources.identity(row),
        )
    if row.get("entity_id") and row.get("attribute") and not row.get("field_id"):
        return (
            "entity",
            row["entity_id"],
            row["attribute"],
            row.get("key"),
            *row.get("obligation_scope", []),
        )
    return display_binding(row)


def _different_path_inputs(left, right):
    a, b = left.get("path_input"), right.get("path_input")
    return (
        a
        and b
        and (
            a["command_id"] != b["command_id"]
            or a.get("parameter")
            and b.get("parameter")
            and a["parameter"] != b["parameter"]
        )
    )


def semantic_candidates(bundle):
    """Unreviewed wording differences within one concern anchor, without guesswork."""
    conflicts = conflicting_pairs(bundle)
    candidates = []
    groups = {row["id"] for row in bundle["channels"]["G"]["concerns"] if row.get("input_group")}

    def alignment(row):
        return set(row.get("aligned_concern_ids", [])) - groups | set(
            row.get("aligned_scenario_ids", [])
        )

    for pair, (a, b) in PAIRS.items():
        decided = {
            (d["left_id"], d["right_id"])
            for d in bundle.get("decisions", [])
            if d.get("pair") == pair and d.get("level") == "scenario"
        }
        for left in bundle["channels"][a]["scenarios"]:
            for right in bundle["channels"][b]["scenarios"]:
                left_condition, right_condition = left.get("condition"), right.get("condition")
                if (
                    left.get("status") == right.get("status") == "active"
                    and (
                        binding(left) == binding(right)
                        or pair == "GT_E"
                        and alignment(left).intersection(alignment(right))
                    )
                    and not _different_path_inputs(left, right)
                    and not disjoint(left_condition, right_condition)
                    and not different_failures(left, right)
                    and not path_resources.different_failures(left, right)
                    and not concern_policy.different_subtypes(left, right)
                    and (
                        bundle.get("coverage_policy") != GRAIN_POLICY
                        or compatible(left_condition, right_condition)
                    )
                    and (left["id"], right["id"]) not in decided
                    and (pair, left["id"], right["id"]) not in conflicts
                    and not same_failure_text(left, right, require_text=False)
                ):
                    candidates.append(
                        {
                            "pair": pair,
                            "left_id": left["id"],
                            "right_id": right["id"],
                            "step_id": left.get("step_id"),
                        }
                    )
    return [*candidates, *conflicts.values()]


def conflicting_pairs(bundle):
    conflicts = bundle.get("matching_conflicts", [])
    if not conflicts:
        return {}
    records = {
        channel: {r["id"] for r in data["scenarios"] if r["status"] == "active"}
        | {r["id"] for r in data.get("pending", [])}
        for channel, data in bundle["channels"].items()
    }
    decided = {
        (d["pair"], d["left_id"], d["right_id"])
        for d in bundle.get("decisions", [])
        if d["level"] == "scenario"
    }
    return {
        (item["pair"], item["left_id"], item["right_id"]): item
        for item in conflicts
        if (item["pair"], item["left_id"], item["right_id"]) not in decided
        and item["left_id"] in records[PAIRS[item["pair"]][0]]
        and item["right_id"] in records[PAIRS[item["pair"]][1]]
    }


def same_failure_text(left, right, *, require_text=True):
    condition = _text(left.get("condition") or "")
    expected = _text(left.get("expected") or "")
    return (
        (not require_text or bool(condition and expected))
        and condition == _text(right.get("condition") or "")
        and expected == _text(right.get("expected") or "")
    )


def _text(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(text))).casefold()


def _units(bundle, kind):
    units, aliases = {}, {}
    for channel in ("G", "E", "GT"):
        grouped = {}
        aliases[channel] = {}
        for row in bundle["channels"][channel][kind]:
            if row["status"] != "active":
                continue
            identity = binding(row)
            if kind == "scenarios":
                identity += (_text(row.get("condition")), _text(row.get("expected")))
            representative = grouped.setdefault(identity, row)
            aliases[channel][row["id"]] = representative["id"]
        units[channel] = {r["id"]: r for r in grouped.values()}
    return units, aliases


def _edges(bundle, kind, units, aliases):
    edges = {}
    level = "concern" if kind == "concerns" else "scenario"
    deferred = (
        {
            (pair, aliases[PAIRS[pair][0]].get(left), aliases[PAIRS[pair][1]].get(right))
            for pair, left, right in conflicting_pairs(bundle)
        }
        if level == "scenario"
        else set()
    )
    for pair, (a, b) in PAIRS.items():
        matches = {}
        for x in units[a].values():
            for y in units[b].values():
                if binding(x) != binding(y) or (pair, x["id"], y["id"]) in deferred:
                    continue
                exact = kind == "concerns" or (
                    not _different_path_inputs(x, y)
                    and not different_failures(x, y)
                    and not path_resources.different_failures(x, y)
                    and not concern_policy.different_subtypes(x, y)
                    and same_failure_text(x, y, require_text=False)
                )
                if exact:
                    matches[(x["id"], y["id"])] = "full"
                elif disjoint(x.get("condition"), y.get("condition")):
                    matches[(x["id"], y["id"])] = "none"
        for d in sorted(bundle.get("decisions", []), key=lambda d: d.get("origin") == "manual"):
            if d["level"] != level or d["pair"] != pair:
                continue
            left, right = aliases[a].get(d["left_id"]), aliases[b].get(d["right_id"])
            if left and right:
                matches[(left, right)] = d["status"]
        edges[pair] = matches
    return edges


def _assignment(edges, left, right):
    """Maximum one-to-one assignment; one truth cannot count repeatedly."""
    assigned = {}

    def visit(x, seen):
        for y in sorted(y for (a, y), status in edges.items() if a == x and status == "full"):
            if y not in right or y in seen:
                continue
            seen.add(y)
            if y not in assigned or visit(assigned[y], seen):
                assigned[y] = x
                return True
        return False

    for x in sorted(left):
        visit(x, set())
    return {(x, y) for y, x in assigned.items()}
