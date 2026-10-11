"""Identification metrics, with layer-isolated and C-oriented category totals."""
from __future__ import annotations

from .interaction_protocol import LAYERS, PROTOCOL, baseline, same_comparison_scope
from .sources import fingerprint

EVALUATION_POLICY = {'version': 'rr-sr-one-to-one-workflow-v5', 'acceptance_layers': ['RR', 'SR'],
    'reported_layers': ['RR', 'SR', 'combined'], 'miss_rate_threshold': None,
    'rr_status': '独立报告，服务职责映射至SR', 'combined_status': '两层合计报告',
    'cross_layer_matching': False, 'duplicate_sr_exception_in_rr': True,
    'matching_cardinality': 'one_to_one', 'test_granularity': 'interaction_concern_condition',
    'test_comparison_scope': 'test_all', 'adoption_denominator': 'unique_cross_layer_recommendation_units'}


def compare(generated, checked, decisions, *, complete=True, comparison_scope="layer_use_case"):
    if not complete:
        raise ValueError("incomplete comparison cannot publish metrics")
    g = {s["scenario_id"]: s for s in generated if s["scenario_type"] == "exception"}
    c = {s["scenario_id"]: s for s in checked if s["scenario_type"] == "exception"}
    if len(g) != sum(s["scenario_type"] == "exception" for s in generated) or len(c) != len(checked):
        raise ValueError("duplicate scenario IDs or non-exception checker input")
    expected = {(cid, gid) for cid, cs in c.items() for gid, gs in g.items()
                if same_comparison_scope(cs, gs, comparison_scope)}
    actual = [(p["checker_scenario_id"], p["generated_scenario_id"]) for p in decisions]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("incomplete/duplicate/unrelated pair universe")
    from .interaction_assignment import assign_one_to_one
    assignment = assign_one_to_one(decisions)
    links = assignment['selected_pairs']
    definitions = baseline()
    groups = sorted({d["group"] for d in definitions.values()})

    def belongs(scene, kind, value):
        keys = set(scene.get("concern_keys", []))
        if kind == "overall":
            return True
        if kind == "unclassified":
            return not keys
        if kind == "concern":
            return value in keys
        return any(definitions[k]["group"] == value for k in keys if k in definitions)

    def bucket(layer, kind="overall", category="exception_overall"):
        gs = {sid for sid, s in g.items() if (layer == "combined" or s["requirement_layer"] == layer) and belongs(s, kind, category)}
        cs = {sid for sid, s in c.items() if (layer == "combined" or s["requirement_layer"] == layer) and belongs(s, kind, category)}
        # Identification coverage depends on C's category only, not G's labels.
        cm = {p["checker_scenario_id"] for p in links if p["checker_scenario_id"] in cs}
        gm = {p["generated_scenario_id"] for p in links if p["generated_scenario_id"] in gs}
        same = [p for p in links if p["checker_scenario_id"] in cs and p["generated_scenario_id"] in gs]
        full_c = {p["checker_scenario_id"] for p in links if p["status"] == "full" and p["checker_scenario_id"] in cs}
        partial_only_c = {p["checker_scenario_id"] for p in links if p["status"] == "partial" and p["checker_scenario_id"] in cs} - full_c
        return {"requirement_layer": layer, "category_kind": kind, "category": category,
            "checker_count": len(cs), "miss_count": len(cs-cm), "miss_rate": len(cs-cm)/len(cs) if cs else None,
            "generated_count": len(gs), "overlap_count": len(gm), "completeness": len(gm)/len(gs) if gs else None,
            "full_checker_count": len(full_c), "partial_only_checker_count": len(partial_only_c),
            "checker_ids": sorted(cs), "generated_ids": sorted(gs), "missed_checker_ids": sorted(cs-cm),
            "unmatched_generated_ids": sorted(gs-gm), "matched_checker_ids": sorted(cm), "matched_generated_ids": sorted(gm),
            "same_category_checker_ids": sorted({p["checker_scenario_id"] for p in same}),
            "same_category_generated_ids": sorted({p["generated_scenario_id"] for p in same}),
            "checker_locations": {sid: c[sid].get("source_refs", []) for sid in sorted(cs)}}

    layers = {}
    for layer in (*LAYERS, "combined"):
        layers[layer] = {"overall": bucket(layer),
            "concerns": {k: bucket(layer, "concern", k) for k in sorted(definitions)},
            "groups": {k: bucket(layer, "group", k) for k in groups},
            "unclassified": bucket(layer, "unclassified", "unclassified_exception")}
    differences = [{**p, "checker_concerns": c[p["checker_scenario_id"]].get("concern_keys", []),
        "generated_concerns": g[p["generated_scenario_id"]].get("concern_keys", [])} for p in links
        if set(c[p["checker_scenario_id"]].get("concern_keys", [])) != set(g[p["generated_scenario_id"]].get("concern_keys", []))]
    return {"protocol": PROTOCOL, "complete": True, "formal": False, "layers": layers,
        'evaluation_policy': {**EVALUATION_POLICY},
        "threshold": None, "coverage_threshold_met": None, "classification_differences": differences,
        'assignment': assignment,
        "non_exception_counts": {layer: {kind: sum(s["scenario_type"] == kind and s["requirement_layer"] == layer for s in generated)
            for kind in ("main_success", "alternative")} for layer in LAYERS},
        "input_hash": fingerprint([generated, checked, decisions])}


def adoption(recommendations, test_conditions, decisions, complete=True, *, equivalence=None):
    if not complete:
        raise ValueError("incomplete adoption comparison")
    if any(s["requirement_layer"] not in {*LAYERS, 'RECOMMENDATION'} or s["scenario_type"] != "exception" for s in recommendations):
        raise ValueError("adoption denominator must contain recommended RR/SR exceptions only")
    # Reuse exhaustive-universe verification, never approximate all-G adoption.
    compared = compare(recommendations, test_conditions, decisions, comparison_scope='test_all')
    ids = {s["scenario_id"] for s in recommendations}
    accepted = {p["generated_scenario_id"] for p in compared['assignment']['selected_pairs']}
    tests = {s['scenario_id']: s for s in test_conditions}
    explicit = {p['generated_scenario_id'] for p in compared['assignment']['selected_pairs']
        if tests[p['checker_scenario_id']].get('source_basis') == 'explicit'}
    derived = accepted - explicit
    return {"requirement_layer": 'all', "recommended_count": len(ids), "adopted_count": len(accepted),
        "adoption_rate": len(accepted)/len(ids) if ids else None, "recommended_ids": sorted(ids),
        "adopted_ids": sorted(accepted), 'test_layer_partitioned': False,
        'recommendation_layers': {layer: {'recommended_ids': sorted(s['scenario_id'] for s in recommendations if layer in s.get('source_layers', [s['requirement_layer']])),
            'adopted_ids': sorted(s['scenario_id'] for s in recommendations if layer in s.get('source_layers', [s['requirement_layer']]) and s['scenario_id'] in accepted)} for layer in LAYERS},
        'explicit_adopted_count': len(explicit), 'derived_adopted_count': len(derived),
        'explicit_adopted_ids': sorted(explicit), 'derived_adopted_ids': sorted(derived),
        "comparison_scope": 'test_all', 'assignment': compared['assignment'],
        'equivalence': equivalence, 'granularity': 'interaction_concern_condition', "complete": True}
