"""Semantic RR/SR recommendation deduplication at interaction/concern granularity."""
from pathlib import Path
import copy

from .interaction_protocol import identification, validate_identification
from .semantic_backend import prepare_packets
from .sources import fingerprint
from .schemas import stable_id


def eligible_pairs(candidates, ssd):
    exchanges = {e['exchange_id']: e for e in ssd['exchanges']}
    pairs = []
    for rr in sorted((s for s in candidates if s['requirement_layer'] == 'RR'), key=lambda s: s['scenario_id']):
        for sr in sorted((s for s in candidates if s['requirement_layer'] == 'SR'), key=lambda s: s['scenario_id']):
            if (rr['use_case_id'] == sr['use_case_id']
                    and exchanges[sr['exchange_id']].get('parent_exchange_id') == rr['exchange_id']):
                pairs.append((rr, sr))
    return pairs


def equivalence_packets(candidates, ssd, directory):
    from .interaction_batches import role_skill
    payloads = [{'left': identification(rr), 'right': identification(sr),
        'left_concerns': rr['concern_keys'], 'right_concerns': sr['concern_keys'],
        'rr_exchange_id': rr['exchange_id'], 'sr_exchange_id': sr['exchange_id'],
        'rule_hash': fingerprint(Path(__file__).read_text(encoding='utf-8')), 'matching_skill': role_skill('scenario-match')}
        for rr, sr in eligible_pairs(candidates, ssd)]
    # Batch independent decisions without dropping any source-mapped pair.
    # Native process startup per pair is especially costly for full projects.
    groups = [{'pairs': payloads[i:i + 16]} for i in range(0, len(payloads), 16)]
    return prepare_packets(directory, 'interaction-equivalence', groups, [
        'Decide semantic equivalence of EVERY supplied source-mapped RR/SR pair. Return each left_id/right_id exactly once in decisions. This is deduplication, not exception generation or coverage. No original checker or test is provided.',
        'Equivalent means the SAME actual cause: concrete abnormal object, operation, mechanism and necessary trigger conditions. Business wording AND concern labels may differ by layer (service resource existence versus database resource existence). Such viewpoint labels do not create two causes. General topic, category, ordinary operation or partial overlap is NOT equivalence. Distinct actual causes remain separate.',
        'Responses, error codes, handling and recovery cannot affect equivalence. Return concrete exact identification excerpts for both sides. For equivalent=true, condition_equivalence must map EVERY necessary_conditions item from BOTH sides using complete exact condition strings and explain semantic equivalence; empty lists need []. A condition present only on one side or a contradictory condition blocks equivalence. Keep all original members and SSD anchors; do not delete generated scenarios.',
    ], {'decisions': [{'left_id': 'supplied left scenario_id', 'right_id': 'supplied right scenario_id',
        'equivalent': False, 'same_necessary_conditions': False, 'same_actual_cause': False, 'reason': 'concrete identity/difference',
        'condition_equivalence': [{'left_condition': 'complete left necessary condition', 'right_condition': 'complete right necessary condition',
            'same_condition': True, 'reason': 'same actual necessary condition'}],
        'evidence': {field: {'left': 'exact field excerpt', 'right': 'exact field excerpt'}
            for field in ('exception_object', 'operation', 'failure_mechanism', 'trigger_condition')}}]})


def equivalence_validator(packet, result):
    data = packet['input']
    if 'pairs' in data:
        expected = {(p['left']['scenario_id'], p['right']['scenario_id']): p for p in data['pairs']}
        rows = result.get('decisions')
        if (not isinstance(rows, list) or len(rows) != len(expected)
                or {(r.get('left_id'), r.get('right_id')) for r in rows} != set(expected)):
            raise ValueError('equivalence batch must decide every source-mapped pair exactly once')
        by_pair = {(r['left_id'], r['right_id']): r for r in rows}
        return [row for key, pair in expected.items()
            for row in equivalence_validator({'input': pair}, by_pair[key])]
    if type(result.get('equivalent')) is not bool or type(result.get('same_necessary_conditions')) is not bool or not result.get('reason'):
        raise ValueError('recommendation equivalence requires explicit complete semantic decision')
    if result['equivalent'] and (not result['same_necessary_conditions'] or result.get('same_actual_cause') is not True):
        raise ValueError('partial conditions are not equivalent recommendations')
    if result['equivalent']:
        rows = result.get('condition_equivalence', [])
        required = {side: set(data[side].get('necessary_conditions', [])) for side in ('left', 'right')}
        if not isinstance(rows, list):
            raise ValueError('equivalent recommendations need complete necessary condition mapping')
        if any({r.get(side + '_condition') for r in rows} != required[side] for side in ('left', 'right')):
            raise ValueError('equivalent recommendations must account for every necessary condition on both sides')
        if any(len(rows) != len(required[side]) for side in ('left', 'right')):
            raise ValueError('necessary condition equivalence must use one-to-one atomic condition mappings')
        if len({(r.get('left_condition'), r.get('right_condition')) for r in rows}) != len(rows):
            raise ValueError('duplicate recommendation necessary-condition mapping')
        if any(r.get('same_condition') is not True or not isinstance(r.get('reason'), str) or not r['reason'].strip() for r in rows):
            raise ValueError('contradictory/unexplained necessary conditions cannot be merged')
    for field in ('exception_object', 'operation', 'failure_mechanism', 'trigger_condition'):
        for side in ('left', 'right'):
            quote = result.get('evidence', {}).get(field, {}).get(side)
            if not isinstance(quote, str) or not quote.strip() or quote not in data[side][field]:
                raise ValueError('equivalence needs exact abnormal identification evidence on both sides')
    return [{'left_id': data['left']['scenario_id'], 'right_id': data['right']['scenario_id'],
        'left_concerns': data['left_concerns'], 'right_concerns': data['right_concerns'], **copy.deepcopy(result)}]


def recommendation_units(candidates, ssd, decisions):
    scenes = {s['scenario_id']: s for s in candidates}
    if len(scenes) != len(candidates) or any(s['scenario_type'] != 'exception' or len(s['concern_keys']) != 1 for s in candidates):
        raise ValueError('recommendation units require unique atomic concern candidates')
    expected = {(a['scenario_id'], b['scenario_id']) for a, b in eligible_pairs(candidates, ssd)}
    keys = [(d['left_id'], d['right_id']) for d in decisions]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('incomplete/stale RR/SR recommendation equivalence universe')
    parent = {sid: sid for sid in scenes}
    def root(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid
    for d in decisions:
        if d['equivalent']:
            a, b = root(d['left_id']), root(d['right_id'])
            parent[max(a, b)] = min(a, b)
    # An equivalence class cannot contain a known contrary cross-layer decision.
    for d in decisions:
        if not d['equivalent'] and root(d['left_id']) == root(d['right_id']):
            raise ValueError('non-transitive recommendation equivalence requires independent review')
    groups = {}
    for sid in sorted(scenes):
        groups.setdefault(root(sid), []).append(sid)
    units = []
    for members in groups.values():
        representative = min(members, key=lambda sid: (scenes[sid]['requirement_layer'] != 'SR', sid))
        unit = copy.deepcopy(scenes[representative])
        unit.update(scenario_id=stable_id('R-UNIT', fingerprint(members)),
            representative_scenario_id=representative, member_scenario_ids=members,
            source_layers=sorted({scenes[s]['requirement_layer'] for s in members}),
            member_exchange_ids=sorted({scenes[s]['exchange_id'] for s in members}),
            member_source_refs={s: scenes[s].get('source_refs', []) for s in members},
            concern_keys=sorted({key for sid in members for key in scenes[sid]['concern_keys']}),
            member_concerns={sid: scenes[sid]['concern_keys'] for sid in members}, causal_unit_count=1)
        validate_identification(unit)
        units.append(unit)
    return {'complete': True, 'granularity': 'interaction_concern_condition',
        'original_recommendation_count': len(candidates), 'unique_unit_count': len(units),
        'decisions_hash': fingerprint(decisions), 'units': sorted(units, key=lambda s: s['scenario_id'])}
