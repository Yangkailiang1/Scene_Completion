import copy
import json

import pytest

from scene_completion.comparison_patch import build_comparison_patch, apply_comparison_patch
from scene_completion.sources import fingerprint


def _validator(packet, result):
    checkers = packet['input']['checker']
    generated = packet['input']['generated']
    expected = {(c['scenario_id'], g['scenario_id']) for c in checkers for g in generated}
    rows = result.get('pairs')
    if not isinstance(rows, list):
        raise ValueError('missing pair decisions')
    seen = set()
    for row in rows:
        key = (row.get('checker_scenario_id'), row.get('generated_scenario_id'))
        if key not in expected or key in seen:
            raise ValueError('unknown or duplicate pair')
        seen.add(key)
        if row.get('decision') != 'valid':
            raise ValueError('invalid pair decision')
    if seen != expected:
        raise ValueError('missing decisions cannot be treated as unmatched')
    return rows


def _proof(model='fixture-model'):
    return {'model': model, 'execution_model_evidence': {'requested_model': model,
        'api_endpoint_hash': 'a' * 64, 'thinking': False, 'reasoning_effort': None}}


def _save_packet(path, packet):
    packet = copy.deepcopy(packet)
    packet['input_hash'] = fingerprint({k: v for k, v in packet.items() if k not in {'batch_id', 'input_hash'}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False), encoding='utf-8')
    return packet


def _setup(tmp_path):
    checker = {'scenario_id': 'C1'}
    generated = [{'scenario_id': f'G{i}'} for i in (1, 2, 3)]
    packet = {'stage': 'gap-ambiguity-EG', 'input': {
        'checker': [checker], 'generated': generated,
        'canonical_metadata': {'C1': {'scope': 'c'}, 'G1': {'scope': 'g'},
                               'G2': {'scope': 'g'}, 'G3': {'scope': 'g'}},
        'protocol': 'fixture', 'skill': {}, 'execution_versions': {}},
        'instructions': ['Resolve all comparisons.'], 'output_contract': {'pairs': []},
        'batch_id': 'gap-ambiguity-EG-fixture'}
    packet_path = tmp_path / 'source' / 'packets' / (packet['batch_id'] + '.json')
    packet = _save_packet(packet_path, packet)
    pairs = [
        {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G1', 'decision': 'valid', 'note': 'keep byte-for-byte content'},
        {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'invalid'},
    ]
    result = {**_proof(), 'batch_id': packet['batch_id'], 'input_hash': packet['input_hash'], 'pairs': pairs}
    attempt_path = tmp_path / 'source' / 'attempts' / (packet['batch_id'] + '-prior.json')
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_path.write_text(json.dumps({'result': result, 'validation_error': 'prior packet rejected'},
                                       ensure_ascii=False), encoding='utf-8')
    return packet_path, attempt_path, pairs


def _finalize_patch(tmp_path, built):
    packet = {'stage': 'gap-ambiguity-EG', 'input': built['payload'],
        'instructions': built['instructions'], 'output_contract': {'pairs': []},
        'batch_id': 'gap-ambiguity-EG-repair-fixture'}
    path = tmp_path / 'patch' / 'packets' / (packet['batch_id'] + '.json')
    return path, _save_packet(path, packet)


def _patch_result(patch_packet, rows):
    return {**_proof(), 'batch_id': patch_packet['batch_id'],
        'input_hash': patch_packet['input_hash'], 'pairs': rows}


def test_build_and_apply_repair_only_invalid_and_missing_pairs(tmp_path):
    source, attempt, original_pairs = _setup(tmp_path)
    built = build_comparison_patch(source, attempt, _validator)
    assert [r['generated_scenario_id'] for r in built['expected_pairs']] == ['G2', 'G3']
    assert [s['scenario_id'] for s in built['payload']['generated']] == ['G2', 'G3']
    assert built['payload']['expected_pairs'] == built['expected_pairs']

    patch_path, patch_packet = _finalize_patch(tmp_path, built)
    patched = _patch_result(patch_packet, [
        {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'valid'},
        {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G3', 'decision': 'valid'},
    ])
    merged = apply_comparison_patch(source, attempt, patch_path, patched, _validator)
    assert merged[0] == original_pairs[0]
    assert [(r['checker_scenario_id'], r['generated_scenario_id']) for r in merged] == [
        ('C1', 'G1'), ('C1', 'G2'), ('C1', 'G3')]


@pytest.mark.parametrize('rows', [
    [{'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'valid'}],
    [{'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'valid'},
     {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'valid'},
     {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G3', 'decision': 'valid'}],
    [{'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'valid'},
     {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G3', 'decision': 'valid'},
     {'checker_scenario_id': 'C1', 'generated_scenario_id': 'UNKNOWN', 'decision': 'valid'}],
])
def test_apply_rejects_missing_duplicate_and_unknown_pairs(tmp_path, rows):
    source, attempt, _ = _setup(tmp_path)
    built = build_comparison_patch(source, attempt, _validator)
    patch_path, patch_packet = _finalize_patch(tmp_path, built)
    with pytest.raises(ValueError):
        apply_comparison_patch(source, attempt, patch_path, _patch_result(patch_packet, rows), _validator)


def test_apply_rejects_changed_prior_attempt_or_packet(tmp_path):
    source, attempt, _ = _setup(tmp_path)
    built = build_comparison_patch(source, attempt, _validator)
    patch_path, patch_packet = _finalize_patch(tmp_path, built)
    patched = _patch_result(patch_packet, [
        {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G2', 'decision': 'valid'},
        {'checker_scenario_id': 'C1', 'generated_scenario_id': 'G3', 'decision': 'valid'}])
    attempt.write_text(attempt.read_text(encoding='utf-8') + ' ', encoding='utf-8')
    with pytest.raises(ValueError, match='binding changed'):
        apply_comparison_patch(source, attempt, patch_path, patched, _validator)


def test_real_comparison_validator_replays_pair_patch_and_preserves_prior_decision(tmp_path):
    from scene_completion.concern_gap_comparison import validator
    from tests.test_concern_gap_comparison import packet as real_packet
    packet = real_packet()
    other = copy.deepcopy(packet['input']['generated'][0])
    other['scenario_id'] = 'G2'
    packet['input']['generated'].append(other)
    packet['input']['canonical_metadata']['G2'] = copy.deepcopy(packet['input']['canonical_metadata']['G'])
    packet.update(batch_id='gap-ambiguity-EG-real', instructions=['Inspect actual source conditions.'],
                  output_contract={'pairs': []})
    path = tmp_path/'source/packets/gap-ambiguity-EG-real.json'
    packet = _save_packet(path, packet)
    prior_row = {'checker_scenario_id': 'C', 'generated_scenario_id': 'G',
                 'status': 'unmatched', 'reason': 'distinct actual causes'}
    prior = {**_proof(), 'batch_id': packet['batch_id'], 'input_hash': packet['input_hash'], 'pairs': [prior_row]}
    attempt = tmp_path/'source/attempts/gap-ambiguity-EG-real-original.json'
    attempt.parent.mkdir(parents=True)
    attempt.write_text(json.dumps({'result': prior}), encoding='utf8')
    built = build_comparison_patch(path, attempt, validator)
    patch = {'stage': packet['stage'], 'batch_id': 'gap-ambiguity-EG-patch',
             'input': built['payload'], 'instructions': built['instructions'], 'output_contract': {'pairs': []}}
    patch = _save_packet(tmp_path/'patch.json', patch)
    raw = _patch_result(patch, [{'checker_scenario_id': 'C', 'generated_scenario_id': 'G2',
                               'status': 'unmatched', 'reason': 'different failure object'}])
    original = copy.deepcopy(raw)
    merged = validator(patch, raw)
    assert merged[0] == prior_row
    assert [r['generated_scenario_id'] for r in merged] == ['G', 'G2']
    assert raw == original
