"""Canonical interaction/cause units and one-to-one concern-gap evaluation."""
from __future__ import annotations

import copy
from .schemas import stable_id
from .sources import fingerprint
from .interaction_protocol import baseline
from .interaction_assignment import assign_one_to_one

PROTOCOL = 'rr-sr-concern-gap-v2'
POLICY = {'version': PROTOCOL, 'unit': 'use_case_interaction_object_cause_conditions',
    'ground_truth': 'provisional_test_spec_including_marked_framework_derivations',
    'matching': 'one_to_one', 'miss_rate_threshold': None,
    'recommendation_false_positive_denominator': 'ground_truth', 'ar_analysis': False}


def locations(ssd):
    """Boundary RR/SR views share a location; actual nested calls stay distinct."""
    exchanges = {e['exchange_id']: e for e in ssd['exchanges']}
    nodes = {n['node_id']: n for n in ssd['nodes']}
    result = []
    for e in ssd['exchanges']:
        if e['requirement_layer'] not in {'RR', 'SR'}:
            continue
        parent = exchanges.get(e.get('parent_exchange_id'))
        boundary = (e['requirement_layer'] == 'SR' and not e.get('parent_sr_exchange_id')
            and nodes[e['from_node']].get('boundary_role'))
        lid = parent['exchange_id'] if boundary and parent else e['exchange_id']
        existing = next((r for r in result if r['location_id'] == lid), None)
        if existing:
            existing['exchange_ids'].append(e['exchange_id'])
            existing['source_refs'] += e['source_refs']
            existing['operations'].append(e['operation'])
        else:
            result.append({'location_id': lid, 'use_case_id': e['use_case_id'],
                'exchange_ids': [e['exchange_id']], 'operations': [e['operation']],
                'from_node': e['from_node'], 'to_node': e['to_node'],
                'source_refs': copy.deepcopy(e['source_refs'])})
    return result


def identity(unit):
    return (unit['use_case_id'], unit['location_id'], unit['object_code'], unit['cause_code'],
        tuple(sorted(set(unit['condition_codes']))))


def merge_units(units, prefix):
    """Merge only checked canonical identities, retaining every source member."""
    merged = {}
    for original in units:
        row = copy.deepcopy(original)
        key = identity(row) if row['mapping_status'] == 'mapped' else ('unmapped', row['unit_id'])
        if key not in merged:
            merged[key] = row
            merged[key]['scenario_id'] = stable_id(prefix, fingerprint(key))
            merged[key]['members'] = []
            merged[key]['source_layers'] = []
        target = merged[key]
        target['members'].append({'unit_id': row['unit_id'], 'source_scenario_id': row['source_scenario_id'],
            'requirement_layer': row['requirement_layer'], 'concern_keys': row['concern_keys'],
            'source_refs': row['source_refs'], 'source_basis': 'ssd_derived' if row.get('collection')=='G' else row.get('source_basis', 'explicit')})
        if row.get('collection')=='G':target['source_basis']='ssd_derived'
        target['source_layers'] = sorted(set(target['source_layers'] + [row['requirement_layer']]))
        target['concern_keys'] = sorted(set(target['concern_keys'] + row['concern_keys']))
        target['source_refs'] = list({fingerprint(r):r for r in target['source_refs']+row['source_refs']}.values())
        target['pending_details']=sorted(set(target.get('pending_details',[])+row.get('pending_details',[])))
    return sorted(merged.values(), key=lambda r: r['scenario_id'])


def eligible(left, right):
    return (left['mapping_status'] == right['mapping_status'] == 'mapped'
        and left['use_case_id'] == right['use_case_id']
        and left['location_id'] == right['location_id']
        and (bool(set(left['concern_keys']) & set(right['concern_keys']))
            or (left['object_code']==right['object_code'] and left['cause_code']==right['cause_code'])))


def relation(left, right, decisions):
    expected = {(l['scenario_id'], r['scenario_id']) for l in left for r in right if eligible(l, r)}
    actual = [(d['checker_scenario_id'], d['generated_scenario_id']) for d in decisions]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('missing, duplicate or unrelated canonical comparison')
    if any(d.get('status') not in {'full','partial','unmatched'} for d in decisions):
        raise ValueError('unknown canonical comparison status')
    return assign_one_to_one(decisions)


def metrics(g, e, t, recommended_ids, relations):
    collections = {'G': g, 'E': e, 'T': t}
    for key, values in collections.items():
        if len({u['scenario_id'] for u in values}) != len(values):
            raise ValueError('duplicate '+key+' unit')
    assignments = {name: relation(left, right, relations[name]) for name, left, right in
        [('EG', e, g), ('TG', t, g), ('TE', t, e)]}
    g_ids = {u['scenario_id'] for u in g}
    covered_g = {p['generated_scenario_id'] for p in assignments['EG']['selected_pairs']}
    missing_ids = g_ids - covered_g
    r_ids = set(recommended_ids)
    if len(r_ids) != len(recommended_ids) or not r_ids <= missing_ids:
        raise ValueError('recommendations must be unique missing G units')
    existing_t = {p['checker_scenario_id'] for p in assignments['TE']['selected_pairs']}
    missing_t = {u['scenario_id'] for u in t} - existing_t
    # Restrict eligibility BEFORE assigning: all-G allocation must not steal a
    # missing/recommended unit's only GT. Each metric gets its own one-to-one map.
    missing_match = assign_one_to_one([p for p in relations['TG']
        if p['checker_scenario_id'] in missing_t and p['generated_scenario_id'] in missing_ids])
    rec_match = assign_one_to_one([p for p in relations['TG'] if p['generated_scenario_id'] in r_ids])

    def stat(name, numerator, denominator, numerator_ids, denominator_ids, complement=False):
        value = numerator / denominator if denominator else None
        if complement and value is not None:
            value = 1-value
        return {'metric': name, 'numerator': denominator-numerator if complement else numerator,
            'denominator': denominator, 'value': value,
            'numerator_ids': sorted(set(denominator_ids)-set(numerator_ids)) if complement else sorted(numerator_ids),
            'denominator_ids': sorted(denominator_ids)}

    definitions = baseline()
    groups = sorted({v['group'] for v in definitions.values()})
    def bucket(kind, category):
        def belongs(u):
            if kind == 'overall': return True
            if kind == 'concern': return category in u['concern_keys']
            if kind == 'unclassified': return not u['concern_keys']
            return any(definitions[k]['group'] == category for k in u['concern_keys'])
        gs = {u['scenario_id'] for u in g if belongs(u)}
        ts = {u['scenario_id'] for u in t if belongs(u)}
        rs, mts = r_ids & gs, missing_t & ts
        detected = {p['checker_scenario_id'] for p in missing_match['selected_pairs'] if p['checker_scenario_id'] in mts}
        valid = {p['generated_scenario_id'] for p in assignments['TG']['selected_pairs'] if p['generated_scenario_id'] in gs}
        adopted = {p['generated_scenario_id'] for p in rec_match['selected_pairs'] if p['generated_scenario_id'] in rs}
        return {'kind': kind, 'category': category, 'metrics': [
            stat('miss_rate', len(detected), len(mts), detected, mts, True),
            stat('generation_validity', len(valid), len(gs), valid, gs),
            stat('adoption_rate', len(adopted), len(rs), adopted, rs),
            stat('recommendation_false_positive_rate', len(rs-adopted), len(ts), rs-adopted, ts)]}
    return {'protocol': PROTOCOL, 'policy': POLICY, 'complete': True,
        'overall': bucket('overall', 'all'),
        'concerns': [bucket('concern', k) for k in sorted(definitions)],
        'groups': [bucket('group', k) for k in groups], 'unclassified': bucket('unclassified', 'unclassified'),
        'missing_ids': sorted(missing_ids), 'missing_gt_ids': sorted(missing_t),
        'assignments': {**assignments, 'TM': missing_match, 'TR': rec_match},
        'set_sizes': {'G': len(g), 'E': len(e), 'T': len(t), 'M': len(missing_ids), 'R': len(r_ids)},
        'gt_basis_counts': {basis: sum(any(m['source_basis'] == basis for m in u['members']) for u in t)
            for basis in ('explicit', 'framework_derived')},
        'input_hash': fingerprint([g, e, t, recommended_ids, relations])}
