import copy
import json

import pytest

from scene_completion import interaction_batches
from scene_completion.normal_item_patch import prepare, validate
from scene_completion.semantic_backend import compose_packet
from scene_completion.sources import fingerprint


ERROR = ('hierarchy source_id must occur in its cited original text/chapter or be its exact '
         'document:Lline anchor: unit=unit-SR-1; source_id=BAD-ID')


def _proof(model):
    return {'model': model, 'execution_model_evidence': {
        'requested_model': model, 'provider': 'openai-compatible'}}


def _save_packet(path, packet):
    packet = copy.deepcopy(packet)
    packet['input_hash'] = fingerprint({k: v for k, v in packet.items()
        if k not in {'batch_id', 'input_hash'}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False), encoding='utf-8')
    return packet


def _setup(tmp_path, monkeypatch):
    lines = [
        'Purchase flow',
        'UC-1 purchase order use case',
        'User submits an order.',
        'System creates the order.',
        'Order is complete.',
    ]
    original_row = {
        'unit_id': 'unit-SR-1', 'source_id': 'BAD-ID', 'name': 'purchase order',
        'layer': 'SR', 'parent_ids': ['unit-RR-1'],
        'source_refs': [{'document': 'req.md', 'line_start': 2, 'line_end': 2}],
    }
    payload = {
        'use_case_id': 'UC-1', 'use_case_name': 'purchase order',
        'sections': [{'document': 'req.md', 'requirement_layer': 'SR',
            'heading_path': ['Purchase flow'], 'numbered_text': '\n'.join(
                f'{number}: {line}' for number, line in enumerate(lines, 1))}],
        'context_sections': [],
    }
    instructions = ['Original normal extraction instructions.']
    contract = {'use_case_hierarchy': [original_row]}
    source_packet = compose_packet('interaction-model', payload, instructions, contract)
    source_packet['batch_id'] = 'interaction-model-0000-source'
    source_path = tmp_path / 'source' / 'packets' / (source_packet['batch_id'] + '.json')
    source_packet = _save_packet(source_path, source_packet)
    raw = {**_proof('old-model'), 'batch_id': source_packet['batch_id'],
        'input_hash': source_packet['input_hash'], 'use_case_hierarchy': [original_row],
        'components': [], 'exchanges': [], 'normal_scenarios': []}
    attempt_path = tmp_path / 'source' / 'attempts' / (source_packet['batch_id'] + '-attempt-1.json')
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    # The stored failure is an earlier error. The current validator has since
    # exposed the hierarchy source-ID error that this patch is scoped to.
    attempt_path.write_text(json.dumps({'result': raw,
        'validation_error': 'product table name was invalid', 'attempt': 1}), encoding='utf-8')

    def validator(_index):
        def validate_normal(packet, result):
            row = next(row for row in result['use_case_hierarchy'] if row['unit_id'] == 'unit-SR-1')
            if row['source_id'] == 'BAD-ID':
                raise ValueError(ERROR)
            return [{'use_case_hierarchy': copy.deepcopy(result['use_case_hierarchy'])}]
        return validate_normal

    monkeypatch.setattr(interaction_batches, 'model_validator', validator)
    index = {'documents': [{'document': 'req.md', 'line_count': len(lines),
        'text': '\n'.join(lines), 'format': 'md', 'chapters': [{
            'chapter_id': 'chapter-1', 'document': 'req.md', 'title': 'Purchase flow',
            'heading_path': ['Purchase flow'], 'level': 1, 'line_start': 1,
            'line_end': len(lines)}]}]}
    return source_packet, source_path, raw, attempt_path, index, original_row


def _patch_packet(tmp_path, built):
    packet = compose_packet('interaction-model', built['payload'], built['instructions'], built['contract'])
    packet['batch_id'] = 'interaction-model-0000-patch'
    path = tmp_path / 'patch' / 'packets' / (packet['batch_id'] + '.json')
    return _save_packet(path, packet)


def test_prepare_and_validate_one_replacement_even_when_attempt_shell_has_earlier_error(tmp_path, monkeypatch):
    source_packet, source_path, prior_raw, attempt_path, index, original_row = _setup(tmp_path, monkeypatch)
    built = prepare(source_packet, prior_raw, source_path, attempt_path, ERROR, index)
    assert built is not None
    assert built['payload']['normal_item_patch']['unit_id'] == 'unit-SR-1'
    assert built['payload']['normal_item_patch']['original_row'] == original_row
    assert 'visible_source_snippets' in built['payload']['normal_item_patch']
    patch_packet = _patch_packet(tmp_path, built)
    replacement = {**original_row, 'source_id': 'UC-1'}
    result = {**_proof('repair-model'), 'batch_id': patch_packet['batch_id'],
        'input_hash': patch_packet['input_hash'], 'replacement': replacement}

    values = validate(patch_packet, result, index)
    expected = {**original_row, 'source_id': 'UC-1', 'source_refs': [{
        'document': 'req.md', 'chapter_id': 'chapter-1', 'heading_path': ['Purchase flow'],
        'line_start': 2, 'line_end': 2}]}
    assert values == [{'use_case_hierarchy': [expected]}]


def test_prepare_rejects_other_failure_and_validate_rejects_immutable_edits(tmp_path, monkeypatch):
    source_packet, source_path, prior_raw, attempt_path, index, original_row = _setup(tmp_path, monkeypatch)
    assert prepare(source_packet, prior_raw, source_path, attempt_path,
        'some unrelated validator issue', index) is None
    built = prepare(source_packet, prior_raw, source_path, attempt_path, ERROR, index)
    patch_packet = _patch_packet(tmp_path, built)
    tampered = {**original_row, 'source_id': 'UC-1', 'parent_ids': []}
    result = {**_proof('repair-model'), 'batch_id': patch_packet['batch_id'],
        'input_hash': patch_packet['input_hash'], 'replacement': tampered}
    with pytest.raises(ValueError, match='immutable hierarchy field: parent_ids'):
        validate(patch_packet, result, index)


def test_prepare_rejects_stale_attempt_file_hash(tmp_path, monkeypatch):
    source_packet, source_path, prior_raw, attempt_path, index, _ = _setup(tmp_path, monkeypatch)
    built = prepare(source_packet, prior_raw, source_path, attempt_path, ERROR, index)
    patch_packet = _patch_packet(tmp_path, built)
    shell = json.loads(attempt_path.read_text(encoding='utf-8'))
    shell['attempt'] = 2
    attempt_path.write_text(json.dumps(shell), encoding='utf-8')
    result = {**_proof('repair-model'), 'batch_id': patch_packet['batch_id'],
        'input_hash': patch_packet['input_hash'], 'replacement': {**built['payload']['normal_item_patch']['original_row'],
            'source_id': 'UC-1'}}
    with pytest.raises(ValueError):
        validate(patch_packet, result, index)


def test_version_only_replay_keeps_original_source_sections(tmp_path, monkeypatch):
    from scene_completion.normal_item_patch import source_packet
    source, path, prior, attempt, index, original_row = _setup(tmp_path, monkeypatch)
    built = prepare(source, prior, path, attempt, ERROR, index)
    packet = _patch_packet(tmp_path, built)
    packet['input']['execution_versions'] = {'old_tool_revision': 'preserved'}
    packet['input_hash'] = fingerprint({k: v for k, v in packet.items()
        if k not in {'batch_id', 'input_hash'}})
    result = {**_proof('repair-model'), 'batch_id': packet['batch_id'],
        'input_hash': packet['input_hash'], 'replacement': {**original_row, 'source_id': 'UC-1'}}
    assert validate(packet, result, index)
    assert source_packet(packet, index)['input']['sections'] == source['input']['sections']
