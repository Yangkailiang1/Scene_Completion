"""Source-backed decomposition, independent of sample numbering/cardinality."""
from __future__ import annotations

import copy

HIERARCHY_LAYERS = ("RR", "SR", "AR", "IMPLEMENTATION")


def validate_hierarchy(units):
    if not isinstance(units, list) or not units:
        raise ValueError("use-case hierarchy must contain source-backed units")
    by_id = {}
    source_ids = set()
    for raw in units:
        unit = copy.deepcopy(raw)
        for field in ("unit_id", "source_id", "name"):
            if not isinstance(unit.get(field), str) or not unit[field].strip():
                raise ValueError("hierarchy unit missing " + field)
        if unit["unit_id"] in by_id or unit.get("layer") not in HIERARCHY_LAYERS:
            raise ValueError("duplicate hierarchy unit or invalid layer")
        source_key = (unit["layer"], unit["source_id"])
        if source_key in source_ids:
            raise ValueError("duplicate source unit; reuse it through multiple parent_ids")
        source_ids.add(source_key)
        parents = unit.get("parent_ids")
        if not isinstance(parents, list) or any(not isinstance(p, str) or not p for p in parents) or len(set(parents)) != len(parents):
            raise ValueError("hierarchy parent_ids must be unique references")
        if not isinstance(unit.get("source_refs"), list) or not unit["source_refs"]:
            raise ValueError("hierarchy unit requires original source evidence")
        by_id[unit["unit_id"]] = unit
    for unit in by_id.values():
        depth = HIERARCHY_LAYERS.index(unit["layer"])
        if depth == 0:
            if unit["parent_ids"]:
                raise ValueError("RR cannot have a decomposition parent")
        elif not unit["parent_ids"] or any(p not in by_id or by_id[p]["layer"] != HIERARCHY_LAYERS[depth - 1] for p in unit["parent_ids"]):
            raise ValueError("hierarchy parent must belong to the immediately preceding layer")
    if not any(u["layer"] == "RR" for u in units) or not any(u["layer"] == "SR" for u in units):
        raise ValueError("hierarchy requires independent RR and SR units")
    return list(by_id.values())


def ancestor_ids(units, unit_id, layer):
    by_id = {u["unit_id"]: u for u in units}
    if unit_id not in by_id:
        raise ValueError("unknown hierarchy unit")
    unit = by_id[unit_id]
    if unit["layer"] == layer:
        return {unit_id}
    return {a for p in unit["parent_ids"] for a in ancestor_ids(units, p, layer)}


def bind_exchanges(units, exchanges):
    """Validate decomposition separately from message nesting/call order."""
    by_id = {u["unit_id"]: u for u in validate_hierarchy(units)}
    local = {e["local_id"]: e for e in exchanges}
    output = []
    for raw in exchanges:
        e = copy.deepcopy(raw)
        uid = e.get("hierarchy_unit_id")
        unit = by_id.get(uid)
        if unit is None or unit["layer"] != e["requirement_layer"] or unit["layer"] not in {"RR", "SR"}:
            raise ValueError("analyzed exchange must bind a real same-layer RR/SR unit")
        if unit["layer"] == "SR":
            parent = local.get(e.get("parent_rr_local_id"))
            if parent is None or parent.get("hierarchy_unit_id") not in ancestor_ids(units, uid, "RR"):
                raise ValueError("SR message parent disagrees with use-case decomposition")
        e["layer_use_case_id"] = unit["source_id"]
        output.append(e)
    return output
