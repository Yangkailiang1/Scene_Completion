"""Repair only invalid normalization items, bound to the prior real execution."""
from copy import deepcopy
from pathlib import Path

from .sources import fingerprint
from .semantic_backend import read_json
from .interaction_execution_identity import validate_result_execution
from .response_contract import contract_view


def prepare(packet, raw, packet_path, result_path, index):
    if packet['input'].get('normalization_item_patch') or packet['input'].get('normalization_evidence_patch'):
        return None
    from .concern_gap_batches import normalize_validator
    check = normalize_validator(index)
    candidate = contract_view(packet, raw)
    sources = packet['input'].get('scenarios', [])
    items = candidate.get('items', [])
    if (not isinstance(items, list) or len(items) != len(sources)
            or {r.get('source_scenario_id') for r in items} != {s['scenario_id'] for s in sources}):
        return None
    failed, targets = [], []
    for source in sources:
        one = deepcopy(packet); one['input']['scenarios'] = [source]
        item = next(r for r in items if r['source_scenario_id'] == source['scenario_id'])
        try: check(one, {'items': [item]})
        except (ValueError, KeyError, TypeError) as exc:
            failed.append(source['scenario_id'])
            from .validation_issues import normalization_issue
            issue = normalization_issue(source, exc)
            if packet['input'].get('collection') == 'G' and len(item.get('units', [])) == 1 and issue['directed_repair_safe']:
                targets.append({'source_scenario_id': source['scenario_id'], 'unit_index': 0,
                    'fields': issue['fields'], 'validation_error': str(exc)})
    if not failed or len(failed) == len(sources): return None
    saved_packet, saved = read_json(packet_path), read_json(result_path)
    prior = saved.get('result', saved)
    if (saved_packet != packet or prior != raw or raw.get('batch_id') != packet.get('batch_id')
            or raw.get('input_hash') != packet.get('input_hash')
            or fingerprint({k:v for k,v in packet.items() if k not in ('batch_id', 'input_hash')}) != packet['input_hash']):
        raise ValueError('normalization item patch source identity changed')
    validate_result_execution(raw, result_path=result_path)
    data = deepcopy(packet['input'])
    data['scenarios'] = [s for s in sources if s['scenario_id'] in failed]
    data['original_evidence'] = [e for e in data.get('original_evidence', []) if e.get('scenario_id') in failed]
    data.pop('evidence_catalog', None); data.pop('evidence_catalog_format', None)
    data['normalization_item_patch'] = {'version': 'normalization-items-v1', 'failed_ids': failed,
        'packet_path': str(Path(packet_path).resolve()), 'packet_hash': fingerprint(packet),
        'result_path': str(Path(result_path).resolve()), 'result_file_hash': fingerprint(saved),
        'prior_result_hash': fingerprint(raw)}
    if len(targets) == len(failed):
        data['normalization_item_patch']['field_targets'] = targets
        return {'payload': data, 'instructions': [
            'Repair only field_targets in normalization_item_patch. Return edits, not items/units. Each edit has source_scenario_id, unit_index and values containing EXACTLY its listed fields. Tools retain all other fields and successful units unchanged.',
            'Use only each supplied source scenario and its normal interaction evidence. Never read another G/E/T channel or invent a limit, operation or necessary condition.',
            'Canonical codes are concrete semantic snake_case identities. Represent every original necessary condition separately in source order; do not collapse causes, fields or time conditions. Responses/recovery are not identity.',
        ], 'contract': {'edits': [{'source_scenario_id': 'listed ID', 'unit_index': 0,
            'values': {'listed_field': 'correct value (condition_codes is an array)'}}]}}
    return {'payload': data, 'instructions': packet['instructions'] + [
        'Repair ONLY assigned failed source IDs. Tools retain every successful prior item unchanged; return no other source IDs.'],
        'contract': packet['output_contract']}


def validate(packet, result, index):
    from .concern_gap_batches import normalize_validator
    from .semantic_backend import compose_packet
    from .partial_packet_reuse import semantic_packet
    meta = packet['input']['normalization_item_patch']
    original = read_json(meta['packet_path']); saved = read_json(meta['result_path'])
    raw = saved.get('result', saved)
    if (fingerprint(original) != meta['packet_hash'] or fingerprint(saved) != meta['result_file_hash']
            or fingerprint(raw) != meta['prior_result_hash']):
        raise ValueError('normalization item patch source was modified')
    rebuilt = prepare(original, raw, meta['packet_path'], meta['result_path'], index)
    if rebuilt is None: raise ValueError('normalization item patch no longer has the original failed items')
    expected = compose_packet(original['stage'], rebuilt['payload'], rebuilt['instructions'], rebuilt['contract'],
        context_policy=packet.get('context_policy', {}))
    if semantic_packet(expected) != semantic_packet(packet):
        raise ValueError('normalization item patch widened its permitted scope')
    prior = contract_view(original, raw)
    targets = meta.get('field_targets')
    if targets:
        expected_targets = {(t['source_scenario_id'], t['unit_index']): t for t in targets}
        edits = result.get('edits')
        if not isinstance(edits, list) or len(edits) != len(expected_targets):
            raise ValueError('normalization field patch must cover every failed field exactly once')
        merged = deepcopy(prior); seen = set()
        for edit in edits:
            key = (edit.get('source_scenario_id'), edit.get('unit_index'))
            target = expected_targets.get(key)
            values = edit.get('values')
            if (key in seen or not target or not isinstance(values, dict)
                    or set(edit) != {'source_scenario_id', 'unit_index', 'values'} or set(values) != set(target['fields'])):
                raise ValueError('normalization field patch changed unassigned fields')
            seen.add(key)
            item = next(r for r in merged['items'] if r['source_scenario_id'] == key[0])
            item['units'][key[1]].update(deepcopy(values))
        return normalize_validator(index)(original, merged)
    data = deepcopy(packet); data['input'].pop('normalization_item_patch')
    normalize_validator(index)(data, result)
    changed = {r['source_scenario_id']: r for r in result['items']}
    merged = {**prior, 'items': [deepcopy(changed.get(r['source_scenario_id'], r)) for r in prior['items']]}
    return normalize_validator(index)(original, merged)
