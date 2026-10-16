"""Definition closure for checks of already-mounted generated units."""
from copy import deepcopy


def concern_closure(payload, registry):
    """Keep every mounted/source label; never alter units, evidence or locations."""
    result = deepcopy(payload)
    if result.get('collection') != 'G':
        return result
    definitions = result.get('concern_definitions', {})
    if not isinstance(definitions, dict) or any(
            key not in registry or value != registry[key] for key, value in definitions.items()):
        raise ValueError('review definitions differ from the bound concern registry')
    keys = set()
    for row in [*result.get('units', []), *result.get('original_scenarios', [])]:
        if not isinstance(row, dict):
            continue
        if row.get('concern_key'):
            keys.add(row['concern_key'])
        for field in ('concern_keys', 'original_concern_keys'):
            keys.update(row.get(field, []))
    if not keys or not keys <= set(definitions):
        raise ValueError('review is missing an actual mounted/source concern definition')
    result['concern_definitions'] = {key: value for key, value in definitions.items() if key in keys}
    return result


def causal_scope(bundle):
    """Selected-case source closure, without altering the historical corpus.

    Unknown ownership stays visible. Explicit references and dedup edges pull
    related other-case records into the closure; use-case filtering alone is
    not sufficient for cross-layer or cross-case shared causes.
    """
    from .sources import fingerprint
    selected = set(bundle.get('scope', {}).get('use_case_ids', []))
    result = deepcopy(bundle)
    if not selected:
        return result, {}
    source_keys = ('source_generated', 'source_existing', 'source_tests')
    rows = [r for k in source_keys for r in bundle.get(k, []) if isinstance(r, dict)]
    rows += [r for k in ('source_units', 'base_source_units') for group in bundle.get(k, {}).values()
        for r in group if isinstance(r, dict)]
    outputs = [r for k in ('G', 'E', 'T') for r in bundle.get(k, []) if isinstance(r, dict)]
    universe = {str(r[k]) for r in rows + outputs for k in
        ('unit_id', 'scenario_id', 'source_scenario_id', 'test_scenario_id') if r.get(k)}
    def refs(value):
        if isinstance(value, str): return {value} & universe
        if isinstance(value, list): return set().union(*(refs(v) for v in value)) if value else set()
        if isinstance(value, dict): return refs(list(value.values()))
        return set()
    kept = set().union(*(refs(r) for r in outputs)) if outputs else set()
    kept |= set().union(*(refs(r) for r in rows if not r.get('use_case_id') or r['use_case_id'] in selected)) if rows else set()
    edges = [refs(r) for r in rows + outputs]
    dedup = bundle.get('dedup', {})
    def edge_rows(value):
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict): yield row
        elif isinstance(value, dict):
            for child in value.values(): yield from edge_rows(child)
    edges += [refs(r) for r in edge_rows(dedup)]
    while True:
        before = len(kept)
        for edge in edges:
            if edge & kept: kept |= edge
        if len(kept) == before: break
    omitted = {}
    def keep_rows(values, label):
        kept_rows = [r for r in values if not isinstance(r, dict) or not refs(r) or refs(r) & kept]
        outside = [r for r in values if r not in kept_rows]
        if outside: omitted[label] = {'count': len(outside), 'hash': fingerprint(outside)}
        return kept_rows
    for key in source_keys:
        if key in result: result[key] = keep_rows(result[key], key)
    for key in ('source_units', 'base_source_units'):
        for group, values in result.get(key, {}).items():
            result[key][group] = keep_rows(values, key + '.' + group)
    def filter_edges(value, label):
        if isinstance(value, list): return keep_rows(value, label)
        if isinstance(value, dict): return {k: filter_edges(v, label + '.' + k) for k, v in value.items()}
        return value
    if 'dedup' in result: result['dedup'] = filter_edges(result['dedup'], 'dedup')
    for group, value in result.get('reverse_checks', {}).items():
        if isinstance(value, dict) and 'reviews' in value:
            value['reviews'] = keep_rows(value['reviews'], 'reverse_checks.' + group)
    result['_causal_scope_source_ids'] = sorted(kept)
    return result, omitted
