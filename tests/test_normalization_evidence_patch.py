import copy
import json

import pytest

from scene_completion.normalization_evidence_patch import prepare, validate
from scene_completion.semantic_backend import compose_packet
from scene_completion.sources import fingerprint


ERROR = 'normalization needs exact original abnormal scenario evidence'
TRIGGER = 'The request times out after thirty seconds.'


def _proof(model):
    return {'model': model, 'execution_model_evidence': {
        'requested_model': model, 'provider': 'openai-compatible'}}


def _save_packet(path, packet):
    packet = copy.deepcopy(packet)
    packet['input_hash'] = fingerprint({key: value for key, value in packet.items()
        if key not in {'batch_id', 'input_hash'}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False), encoding='utf-8')
    return packet


def _setup(tmp_path, collection='T', bad_semantics=False):
    key = next(iter(__import__('scene_completion.interaction_protocol',
        fromlist=['baseline']).baseline()))
    source = {
        'scenario_id': 'S-1', 'use_case_id': 'UC-1', 'requirement_layer': 'RR',
        'scenario_type': 'exception', 'source_basis': 'explicit', 'concern_keys': [key],
        'name': 'Request timeout', 'exception_object': 'request', 'operation': 'submit request',
        'failure_mechanism': 'network timeout', 'trigger_condition': TRIGGER,
        'necessary_conditions': [], 'source_refs': [
            {'document': 'req.md', 'line_start': 1, 'line_end': 1}],
    }
    def unit(quote, object_code='request', location_id='LOC-1'):
        return {'mapping_status': 'mapped', 'location_id': location_id, 'concern_key': key,
            'object_code': object_code, 'cause_code': 'timeout', 'condition_codes': [],
            'name': 'Request timeout', 'exception_object': 'request', 'operation': 'submit request',
            'failure_mechanism': 'network timeout', 'trigger_condition': TRIGGER,
            'necessary_conditions': [], 'evidence_quote': quote,
            'source_refs': [{'document': 'req.md', 'line_start': 1, 'line_end': 1}],
            'reason': 'Explicit source condition', 'pending_details': []}
    raw = {**_proof('old-model'), 'items': [{'source_scenario_id': 'S-1',
        'units': [unit('DQ-8291 generated diagnostic'), unit('request times out')]}]}
    if bad_semantics:
        raw['items'][0]['units'][1]['object_code'] = 'not a canonical code!'
    payload = {'collection': collection, 'scenarios': [source], 'locations': [{
        'location_id': 'LOC-1', 'use_case_id': 'UC-1', 'exchange_ids': []}]}
    original = compose_packet('gap-normalize-' + collection, payload,
        ['Normalization instructions'], {'items': []})
    original['batch_id'] = 'gap-normalize-' + collection + '-0000-source'
    original_path = tmp_path / 'source' / 'packets' / (original['batch_id'] + '.json')
    original = _save_packet(original_path, original)
    raw.update(batch_id=original['batch_id'], input_hash=original['input_hash'])
    attempt_path = tmp_path / 'source' / 'attempts' / (original['batch_id'] + '-attempt-1.json')
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_path.write_text(json.dumps({'result': raw, 'validation_error': 'earlier unrelated first error',
        'attempt': 1}), encoding='utf-8')
    index = {'documents': [{'document': 'req.md', 'line_count': 1,
        'text': TRIGGER, 'format': 'md', 'chapters': [{
            'chapter_id': 'CH-1', 'document': 'req.md', 'title': 'Request',
            'heading_path': ['Request'], 'level': 1, 'line_start': 1, 'line_end': 1}]}]}
    return original, original_path, raw, attempt_path, index


def _patch_packet(tmp_path, built, collection='T'):
    packet = compose_packet('gap-normalize-' + collection, built['payload'],
        built['instructions'], built['contract'])
    packet['batch_id'] = 'gap-normalize-' + collection + '-0000-patch'
    return _save_packet(tmp_path / 'patch' / 'packets' / (packet['batch_id'] + '.json'), packet)


def test_prepare_and_validate_repairs_only_the_failed_quote(tmp_path):
    original, original_path, raw, attempt_path, index = _setup(tmp_path)
    built = prepare(original, raw, original_path, attempt_path, ERROR + ': source units [S-1/0]', index)
    assert built is not None
    patch_data = built['payload']['normalization_evidence_patch']
    assert [(row['source_scenario_id'], row['unit_index']) for row in patch_data['failed_units']] == [('S-1', 0)]
    assert len(json.dumps(built['payload'], ensure_ascii=False).encode('utf-8')) <= 8000
    patch_packet = _patch_packet(tmp_path, built)
    result = {**_proof('repair-model'), 'batch_id': patch_packet['batch_id'],
        'input_hash': patch_packet['input_hash'], 'evidence_quotes': [{
            'source_scenario_id': 'S-1', 'unit_index': 0, 'evidence_quote': TRIGGER}]}

    values = validate(patch_packet, result, index)
    assert len(values) == 2
    assert values[0]['evidence_quote'] == TRIGGER
    assert values[1]['evidence_quote'] == 'request times out'
    assert values[0]['object_code'] == 'request'


def test_prepare_stops_if_evidence_only_substitution_does_not_validate(tmp_path):
    original, original_path, raw, attempt_path, index = _setup(tmp_path, bad_semantics=True)
    assert prepare(original, raw, original_path, attempt_path, ERROR, index) is None


def test_validate_rejects_extra_fields_wrong_quote_and_stale_source(tmp_path):
    original, original_path, raw, attempt_path, index = _setup(tmp_path)
    built = prepare(original, raw, original_path, attempt_path, ERROR, index)
    patch_packet = _patch_packet(tmp_path, built)
    base = {'batch_id': patch_packet['batch_id'], 'input_hash': patch_packet['input_hash']}
    wrong_quote = {**_proof('repair-model'), **base, 'evidence_quotes': [{
        'source_scenario_id': 'S-1', 'unit_index': 0, 'evidence_quote': 'A paraphrase.'}]}
    with pytest.raises(ValueError, match='exact original trigger_condition'):
        validate(patch_packet, wrong_quote, index)
    extra = {**_proof('repair-model'), **base, 'evidence_quotes': [{
        'source_scenario_id': 'S-1', 'unit_index': 0, 'evidence_quote': TRIGGER}], 'items': []}
    with pytest.raises(ValueError, match='only evidence_quotes'):
        validate(patch_packet, extra, index)

    shell = json.loads(attempt_path.read_text(encoding='utf-8'))
    shell['attempt'] = 2
    attempt_path.write_text(json.dumps(shell), encoding='utf-8')
    correct = {**_proof('repair-model'), **base, 'evidence_quotes': [{
        'source_scenario_id': 'S-1', 'unit_index': 0, 'evidence_quote': TRIGGER}]}
    with pytest.raises(ValueError):
        validate(patch_packet, correct, index)


@pytest.mark.parametrize('collection', ['E', 'T'])
def test_only_e_and_t_normalization_are_supported(tmp_path, collection):
    original, original_path, raw, attempt_path, index = _setup(tmp_path, collection=collection)
    assert prepare(original, raw, original_path, attempt_path, ERROR, index) is not None
    g_packet = copy.deepcopy(original)
    g_packet['stage'] = 'gap-normalize-G'
    g_packet['input']['collection'] = 'G'
    assert prepare(g_packet, raw, original_path, attempt_path, ERROR, index) is None
