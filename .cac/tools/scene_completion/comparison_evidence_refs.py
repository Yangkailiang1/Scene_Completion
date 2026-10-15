"""Resolve explicit packet-local quote references in comparison evidence."""
from __future__ import annotations

from copy import deepcopy


_IDENTIFICATION_FIELDS = {
    "exception_object", "operation", "failure_mechanism", "trigger_condition",
}
_ALL_FIELDS = _IDENTIFICATION_FIELDS | {"necessary_conditions"}


def _scene_indexes(packet):
    data = packet.get("input")
    if not isinstance(data, dict):
        raise ValueError("comparison packet input must be an object")

    has_lr = "checker" in data or "generated" in data
    has_aliases = "left" in data or "right" in data
    if has_lr and has_aliases:
        raise ValueError("comparison packet has ambiguous checker/generated and left/right inputs")
    if has_lr:
        sides = {"checker": data.get("checker"), "generated": data.get("generated")}
    elif has_aliases:
        sides = {"checker": data.get("left"), "generated": data.get("right")}
    else:
        raise ValueError("comparison packet has no checker/generated inputs")

    indexes = {}
    for side, rows in sides.items():
        if not isinstance(rows, list):
            raise ValueError(f"comparison packet {side} input must be a list")
        by_id = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("scenario_id"), str):
                raise ValueError(f"comparison packet {side} rows need scenario_id")
            scenario_id = row["scenario_id"]
            if scenario_id in by_id:
                raise ValueError(f"duplicate {side} scenario_id: {scenario_id}")
            by_id[scenario_id] = row
        indexes[side] = by_id
    return indexes


def _quote(scenes, ref, *, required_side=None, allowed_fields=None,
        required_field=None, require_condition_index=False):
    if not isinstance(ref, dict) or set(ref) != {"quote_ref"}:
        raise ValueError("evidence reference must be exactly a quote_ref object")
    spec = ref["quote_ref"]
    if not isinstance(spec, dict):
        raise ValueError("quote_ref must contain an object")
    if set(spec) - {"side", "field", "index"}:
        raise ValueError("quote_ref contains an unknown key")
    if not {"side", "field"} <= set(spec):
        raise ValueError("quote_ref requires side and field")

    side, field = spec["side"], spec["field"]
    if side not in {"checker", "generated"}:
        raise ValueError("quote_ref side must be checker or generated")
    if required_side is not None and side != required_side:
        raise ValueError(f"quote_ref must use the {required_side} side here")
    if field not in _ALL_FIELDS:
        raise ValueError("quote_ref field is unknown")
    if required_field is not None and field != required_field:
        raise ValueError(f"quote_ref must use {required_field} here")
    if allowed_fields is not None and field not in allowed_fields:
        raise ValueError("quote_ref field is outside this evidence scope")

    has_index = "index" in spec
    if field == "necessary_conditions":
        if not has_index:
            raise ValueError("necessary_conditions quote_ref requires an index")
        index = spec["index"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("quote_ref index must be a nonnegative integer")
    else:
        if has_index:
            raise ValueError("quote_ref index is only valid for necessary_conditions")
        index = None

    if require_condition_index and field != "necessary_conditions":
        raise ValueError("this evidence location requires a necessary_conditions quote")
    scene = scenes[side]
    if field == "necessary_conditions":
        values = scene.get(field)
        if not isinstance(values, list) or index >= len(values):
            raise ValueError("quote_ref necessary_conditions index is out of range")
        value = values[index]
    else:
        value = scene.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError("quote_ref must resolve to a nonempty source string")
    return value


def _resolve_position(value, scenes, *, side=None, fields=None, field=None,
        condition_index=False):
    if value is None or isinstance(value, str):
        return value
    return _quote(scenes, value, required_side=side, allowed_fields=fields,
        required_field=field, require_condition_index=condition_index)


def _resolve_pair(pair, scenes):
    if not isinstance(pair, dict):
        raise ValueError("comparison pair must be an object")
    status = pair.get("status")
    if status not in {"full", "partial", "unmatched"}:
        raise ValueError("comparison pair has an invalid status")
    try:
        checker = scenes["checker"][pair["checker_scenario_id"]]
        generated = scenes["generated"][pair["generated_scenario_id"]]
    except (KeyError, TypeError) as exc:
        raise ValueError("comparison pair references an unknown scenario") from exc
    pair_scenes = {"checker": checker, "generated": generated}

    evidence_keys = (
        "generated_evidence", "checker_evidence", "identification_evidence",
        "causal_facet_evidence", "condition_evidence", "missing_condition_evidence",
    )
    if status == "unmatched":
        # These fields are accepted-pair evidence. Legacy text remains untouched,
        # but a reference here would assert accepted evidence for a rejected pair.
        for key in evidence_keys:
            if _contains_quote_ref(pair.get(key)):
                raise ValueError("quote_ref is not allowed on an unmatched pair")
        return pair

    for key, side in (("generated_evidence", "generated"), ("checker_evidence", "checker")):
        if key in pair:
            pair[key] = _resolve_position(pair[key], pair_scenes, side=side,
                fields=_IDENTIFICATION_FIELDS)

    identification = pair.get("identification_evidence")
    if identification is not None:
        if not isinstance(identification, dict):
            raise ValueError("identification_evidence must be an object")
        for field, sides in identification.items():
            if field not in _IDENTIFICATION_FIELDS:
                raise ValueError("identification_evidence has an unknown field")
            if not isinstance(sides, dict):
                raise ValueError("identification_evidence field must map sides")
            for side in ("generated", "checker"):
                if side in sides:
                    sides[side] = _resolve_position(sides[side], pair_scenes,
                        side=side, field=field)

    causal = pair.get("causal_facet_evidence")
    if causal is not None:
        if not isinstance(causal, dict):
            raise ValueError("causal_facet_evidence must be an object")
        for side in ("generated", "checker"):
            if side in causal:
                causal[side] = _resolve_position(causal[side], pair_scenes,
                    side=side, fields={"failure_mechanism", "trigger_condition"})

    conditions = pair.get("condition_evidence")
    if conditions is not None:
        if not isinstance(conditions, list):
            raise ValueError("condition_evidence must be a list")
        for row in conditions:
            if not isinstance(row, dict):
                raise ValueError("condition_evidence rows must be objects")
            if "checker_condition" in row:
                row["checker_condition"] = _resolve_position(row["checker_condition"],
                    pair_scenes, side="checker", fields={"necessary_conditions"},
                    condition_index=True)
            if "generated_quote" in row:
                row["generated_quote"] = _resolve_position(row["generated_quote"],
                    pair_scenes, side="generated",
                    fields={"trigger_condition", "failure_mechanism", "necessary_conditions"})

    missing = pair.get("missing_condition_evidence")
    if missing is not None:
        if not isinstance(missing, list):
            raise ValueError("missing_condition_evidence must be a list")
        for row in missing:
            if not isinstance(row, dict):
                raise ValueError("missing_condition_evidence rows must be objects")
            if "checker_quote" in row:
                if row.get("checker_field") != "necessary_conditions":
                    if _contains_quote_ref(row["checker_quote"]):
                        raise ValueError("missing-condition quote_ref requires checker_field=necessary_conditions")
                    continue
                row["checker_quote"] = _resolve_position(row["checker_quote"],
                    pair_scenes, side="checker", fields={"necessary_conditions"},
                    condition_index=True)
    if any(_contains_quote_ref(pair.get(key)) for key in evidence_keys):
        raise ValueError("quote_ref appears in an unsupported evidence position")
    return pair


def _contains_quote_ref(value):
    if isinstance(value, dict):
        return "quote_ref" in value or any(_contains_quote_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_quote_ref(item) for item in value)
    return False


def resolve_comparison_evidence(packet, raw):
    """Return a deep-copied result with packet-local quote references expanded.

    This resolves citations only. It never edits packet or raw and never changes
    a comparison decision, its status, booleans, or explanatory reasoning.
    """
    scenes = _scene_indexes(packet)
    result = deepcopy(raw)
    if not isinstance(result, dict) or not isinstance(result.get("pairs"), list):
        raise ValueError("raw comparison result must contain a pairs list")
    result["pairs"] = [_resolve_pair(pair, scenes) for pair in result["pairs"]]
    return result
