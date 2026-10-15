"""Offline, pair-scoped repair support for rejected comparison packets."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from .semantic_backend import read_json
from .sources import fingerprint


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_bound_source(source_packet_path, prior_attempt_path):
    packet_path = Path(source_packet_path).resolve()
    attempt_path = Path(prior_attempt_path).resolve()
    packet = read_json(packet_path)
    attempt = read_json(attempt_path)
    result = attempt.get('result')
    if not isinstance(result, dict):
        raise ValueError('prior comparison attempt has no semantic result')
    batch_id, input_hash = packet.get('batch_id'), packet.get('input_hash')
    expected_hash = fingerprint({k: v for k, v in packet.items() if k not in {'batch_id', 'input_hash'}})
    if not isinstance(batch_id, str) or not batch_id or input_hash != expected_hash:
        raise ValueError('source comparison packet identity is invalid')
    if result.get('batch_id') != batch_id or result.get('input_hash') != input_hash:
        raise ValueError('prior attempt result is not bound to the source packet')
    if not attempt_path.name.startswith(batch_id + '-') or attempt_path.parent.name != 'attempts':
        raise ValueError('prior attempt path does not belong to the source packet')
    from .interaction_execution_identity import validate_result_execution
    validate_result_execution(result)
    return packet, attempt, result, {
        'source_packet_path': str(packet_path), 'source_packet_sha256': _sha256(packet_path),
        'source_batch_id': batch_id, 'source_input_hash': input_hash,
        'prior_attempt_path': str(attempt_path), 'prior_attempt_sha256': _sha256(attempt_path),
    }


def _expected_pairs(packet):
    data = packet.get('input', {})
    checkers, generated = data.get('checker'), data.get('generated')
    if not isinstance(checkers, list) or not isinstance(generated, list) or not checkers or not generated:
        raise ValueError('comparison packet must contain checker and generated scenarios')
    return [(left['scenario_id'], right['scenario_id']) for left in checkers for right in generated]


def _single_pair_packet(packet, checker_id, generated_id):
    view = copy.deepcopy(packet)
    data = view['input']
    data['checker'] = [s for s in data['checker'] if s['scenario_id'] == checker_id]
    data['generated'] = [s for s in data['generated'] if s['scenario_id'] == generated_id]
    selected = {checker_id, generated_id}
    metadata = data.get('canonical_metadata', {})
    data['canonical_metadata'] = {key: value for key, value in metadata.items() if key in selected}
    return view


def _partition_prior(packet, result, validator):
    expected = _expected_pairs(packet)
    expected_set = set(expected)
    seen = set()
    existing = {}
    for row in result.get('pairs', []):
        if not isinstance(row, dict):
            raise ValueError('prior comparison pair must be an object')
        key = (row.get('checker_scenario_id'), row.get('generated_scenario_id'))
        if key not in expected_set:
            raise ValueError('prior comparison contains an unknown pair')
        if key in seen:
            raise ValueError('prior comparison contains a duplicate pair')
        seen.add(key)
        existing[key] = row
    valid, repair, errors = {}, [], {}
    for key in expected:
        row = existing.get(key)
        if row is None:
            repair.append(key)
            errors[key] = 'decision omitted by prior result'
            continue
        try:
            validator(_single_pair_packet(packet, *key), {'pairs': [copy.deepcopy(row)]})
            valid[key] = row
        except (ValueError, KeyError, TypeError) as exc:
            repair.append(key)
            errors[key] = str(exc)
    return expected, valid, repair, errors


def build_comparison_patch(source_packet_path, prior_attempt_path, validator):
    """Build one packet covering only invalid or omitted checker/generated pairs.

    The caller passes ``payload`` and ``instructions`` to the existing packet
    preparation path, then keeps the returned ``binding`` with that patch run.
    Returns None when all original pair decisions independently validate.
    """
    packet, _attempt, result, binding = _read_bound_source(source_packet_path, prior_attempt_path)
    expected, valid, repair, errors = _partition_prior(packet, result, validator)
    if not repair:
        return None
    checker_ids = {key[0] for key in repair}
    generated_ids = {key[1] for key in repair}
    if len(checker_ids) != 1:
        raise ValueError('pair-scoped comparison repair requires one checker scenario')
    payload = copy.deepcopy(packet['input'])
    payload['checker'] = [s for s in payload['checker'] if s['scenario_id'] in checker_ids]
    payload['generated'] = [s for s in payload['generated'] if s['scenario_id'] in generated_ids]
    selected_ids = checker_ids | generated_ids
    payload['canonical_metadata'] = {key: value for key, value in payload['canonical_metadata'].items()
                                     if key in selected_ids}
    payload['expected_pairs'] = [{'checker_scenario_id': c, 'generated_scenario_id': g}
                                  for c, g in repair]
    binding.update({
        'expected_pairs': payload['expected_pairs'],
        'preserved_pair_keys': [{'checker_scenario_id': c, 'generated_scenario_id': g}
                                for c, g in expected if (c, g) in valid],
    })
    payload['comparison_patch_binding'] = binding
    payload['repair_feedback'] = [
        {'checker_scenario_id': c, 'generated_scenario_id': g, 'validation_error': errors[(c, g)]}
        for c, g in repair]
    instructions = list(packet.get('instructions', [])) + [
        'This is a pair-scoped repair. Return exactly one decision for each pair in input.expected_pairs, and no other pairs.',
        'A prior decision is being repaired only because it was omitted or failed offline validation. Reassess the supplied original fields. Do not automatically flip any semantic flag to satisfy validation feedback.',
    ]
    return {'payload': payload, 'instructions': instructions,
            'expected_pairs': copy.deepcopy(payload['expected_pairs']), 'binding': binding}


def apply_comparison_patch(source_packet_path, prior_attempt_path, patch_packet_path,
                           patch_result, validator):
    """Validate a pair-scoped result, retain valid prior pairs, and return all pairs.

    The returned list follows the source packet's checker-major/generated-minor
    order. It is not a new execution record and must not inherit the prior
    result's model or execution evidence.
    """
    packet, _attempt, prior_result, binding = _read_bound_source(source_packet_path, prior_attempt_path)
    patch_packet = (copy.deepcopy(patch_packet_path) if isinstance(patch_packet_path, dict)
                    else read_json(Path(patch_packet_path).resolve()))
    if patch_packet.get('stage') != packet.get('stage'):
        raise ValueError('comparison patch stage differs from its source packet')
    patch_hash = fingerprint({k: v for k, v in patch_packet.items() if k not in {'batch_id', 'input_hash'}})
    if patch_packet.get('input_hash') != patch_hash:
        raise ValueError('comparison patch packet identity is invalid')
    if (patch_result.get('batch_id') != patch_packet.get('batch_id')
            or patch_result.get('input_hash') != patch_packet.get('input_hash')):
        raise ValueError('patch result is not bound to the patch packet')
    from .interaction_execution_identity import validate_result_execution
    validate_result_execution(patch_result)

    expected, valid, repair, _errors = _partition_prior(packet, prior_result, validator)
    patch_binding = patch_packet.get('input', {}).get('comparison_patch_binding')
    if not isinstance(patch_binding, dict):
        raise ValueError('comparison patch lacks its prior-execution binding')
    for key, value in binding.items():
        if patch_binding.get(key) != value:
            raise ValueError('comparison patch source/attempt binding changed')
    patch_data = patch_packet.get('input', {})
    expected_rows = [{'checker_scenario_id': c, 'generated_scenario_id': g} for c, g in repair]
    preserved_rows = [{'checker_scenario_id': c, 'generated_scenario_id': g}
                      for c, g in expected if (c, g) in valid]
    expected_binding = {**binding, 'expected_pairs': expected_rows,
                        'preserved_pair_keys': preserved_rows}
    if patch_binding != expected_binding or patch_data.get('expected_pairs') != expected_rows:
        raise ValueError('comparison patch expected-pair list changed')

    source_data = packet['input']
    checker_id = repair[0][0] if repair else None
    if not repair or any(c != checker_id for c, _ in repair):
        raise ValueError('source packet no longer has the same repairable pair set')
    expected_generated = {g for _, g in repair}
    if ([s.get('scenario_id') for s in patch_data.get('checker', [])] != [checker_id]
            or {s.get('scenario_id') for s in patch_data.get('generated', [])} != expected_generated):
        raise ValueError('comparison patch scenario subset differs from its expected pairs')
    source_meta = source_data.get('canonical_metadata', {})
    subset_ids = {checker_id} | expected_generated
    if patch_data.get('canonical_metadata') != {k: v for k, v in source_meta.items() if k in subset_ids}:
        raise ValueError('comparison patch canonical metadata differs from the source subset')
    expected_payload = copy.deepcopy(source_data)
    expected_payload['checker'] = [s for s in expected_payload['checker'] if s['scenario_id'] == checker_id]
    expected_payload['generated'] = [s for s in expected_payload['generated']
                                     if s['scenario_id'] in expected_generated]
    expected_payload['canonical_metadata'] = {k: v for k, v in source_meta.items() if k in subset_ids}
    expected_payload['expected_pairs'] = expected_rows
    expected_payload['comparison_patch_binding'] = patch_binding
    expected_payload['repair_feedback'] = [
        {'checker_scenario_id': c, 'generated_scenario_id': g, 'validation_error': _errors[(c, g)]}
        for c, g in repair]
    if patch_data != expected_payload or patch_packet.get('output_contract') != packet.get('output_contract'):
        raise ValueError('comparison patch input differs from the exact source subset')
    expected_instructions = list(packet.get('instructions', [])) + [
        'This is a pair-scoped repair. Return exactly one decision for each pair in input.expected_pairs, and no other pairs.',
        'A prior decision is being repaired only because it was omitted or failed offline validation. Reassess the supplied original fields. Do not automatically flip any semantic flag to satisfy validation feedback.',
    ]
    actual_instructions = patch_packet.get('instructions')
    if (not isinstance(actual_instructions, list)
            or actual_instructions[:len(expected_instructions)] != expected_instructions):
        raise ValueError('comparison patch instructions omit the scoped source requirements')

    patch_keys = []
    for row in patch_result.get('pairs', []):
        if not isinstance(row, dict):
            raise ValueError('patch comparison pair must be an object')
        key = (row.get('checker_scenario_id'), row.get('generated_scenario_id'))
        patch_keys.append(key)
    if len(patch_keys) != len(set(patch_keys)):
        raise ValueError('comparison patch contains a duplicate pair')
    if set(patch_keys) != set(repair):
        raise ValueError('comparison patch has unknown or missing expected pairs')
    validator(patch_packet, patch_result)

    replacements = {key: row for key, row in zip(patch_keys, patch_result['pairs'])}
    merged = [copy.deepcopy(valid[key] if key in valid else replacements[key]) for key in expected]
    return validator(packet, {'pairs': merged})
