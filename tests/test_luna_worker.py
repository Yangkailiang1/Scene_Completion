"""Native resume must retain exact CLI data and cannot promote bad attempts."""
import json
import subprocess

import pytest

from scene_completion.luna_subprocess import LunaSubprocessClient
from scene_completion.semantic_backend import prepare_packets, read_json, write_json, run_agent_packets
from scene_completion.interaction_execution_identity import validate_result_execution


def setup(tmp_path, monkeypatch, stage='interaction-model', transport='auto', include_metadata=False, effort='max'):
    directory = tmp_path / 'batches' / stage
    manifest = prepare_packets(directory, stage, [{'value': 'source'}], [], {'items': []})
    batch = manifest['batches'][0]
    packet = read_json(directory / 'packets' / (batch['batch_id'] + '.json'))
    executable = tmp_path / 'codex.exe'
    executable.write_bytes(b'fixture')
    monkeypatch.setattr('scene_completion.luna_subprocess.shutil.which', lambda name: str(executable))
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        output = {'items': [{'value': 'source'}]}
        if include_metadata:
            output.update(batch_id=packet['batch_id'], input_hash=packet['input_hash'],
                model='self-reported-label', execution_model_evidence={'provider': 'untrusted'})
        text = json.dumps(output)
        with open(argv[argv.index('--output-last-message') + 1], 'w', encoding='utf-8') as stream:
            stream.write(text)
        events = [{'type': 'thread.started', 'thread_id': 'real-fixture-thread'},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': text}},
            {'type': 'turn.completed'}]
        return subprocess.CompletedProcess(argv, 0,
            ('\n'.join(json.dumps(e) for e in events) + '\n').encode(), b'')

    client = LunaSubprocessClient({'native_run_dir': str(tmp_path / 'native-runs'),
        'reasoning_effort': effort, 'native_transport': transport, 'max_concurrency': 1, 'semantic_max_attempts': 1}, runner=runner)
    return directory, packet, client, calls


def validator(packet, raw):
    if raw['items'][0]['value'] != 'source':
        raise ValueError('unsupported semantic value')
    raw['items'][0]['normalized'] = True
    return raw['items']


@pytest.mark.parametrize('transport', ['auto', 'http'])
@pytest.mark.parametrize('include_metadata', [False, True])
@pytest.mark.parametrize('effort', ['high', 'max'])
def test_native_worker_preserves_original_json_after_mutating_validation(tmp_path, monkeypatch, transport, include_metadata, effort):
    directory, packet, client, calls = setup(tmp_path, monkeypatch, transport=transport, include_metadata=include_metadata, effort=effort)
    assert run_agent_packets(directory, client, validator)['complete']
    result_path = directory / 'results' / (packet['batch_id'] + '.json')
    saved = read_json(result_path)
    assert saved['items'] == [{'value': 'source'}]
    assert saved['execution_model_evidence']['reasoning_effort'] == effort
    validate_result_execution(saved, result_path=result_path)
    assert run_agent_packets(directory, client, validator)['batches'][0]['status'] == 'cached'
    assert len(calls) == 1
    assert read_json(result_path) == saved


def test_http_transport_cannot_override_auth_endpoint_or_model(tmp_path, monkeypatch):
    directory, packet, client, _ = setup(tmp_path, monkeypatch, transport='http')
    raw = client.agent(packet)
    raw.update(batch_id=packet['batch_id'], input_hash=packet['input_hash'], model=client.model('agent'))
    evidence = raw['execution_model_evidence']['native_execution']
    evidence['argv'].insert(-1, '--dangerously-bypass-approvals-and-sandbox')
    with pytest.raises(ValueError, match='argv'):
        validate_result_execution(raw, result_path=directory / 'results' / 'new.json')


def test_authorized_max_cache_keeps_actual_effort_when_resuming_high(tmp_path, monkeypatch):
    directory, packet, client, calls = setup(tmp_path, monkeypatch)
    assert run_agent_packets(directory, client, validator)['complete']
    client.config.update(reasoning_effort='high', allowed_cached_reasoning_efforts=['high', 'max'])
    assert run_agent_packets(directory, client, validator)['batches'][0]['status'] == 'cached'
    saved = read_json(directory / 'results' / (packet['batch_id'] + '.json'))
    assert saved['execution_model_evidence']['reasoning_effort'] == 'max'
    assert len(calls) == 1


def test_quota_error_stops_retries_and_defers_unstarted_batches(tmp_path, monkeypatch):
    directory, _, client, _ = setup(tmp_path, monkeypatch)
    prepare_packets(directory, 'interaction-model', [{'value': str(i)} for i in range(5)], [], {'items': []})
    calls = []
    def exhausted(argv, **kwargs):
        calls.append(argv)
        events = [{'type': 'thread.started', 'thread_id': 'limited'},
            {'type': 'turn.failed', 'error': {'message': "You’ve hit your usage limit. Try again later."}}]
        return subprocess.CompletedProcess(argv, 1,
            ('\n'.join(json.dumps(e) for e in events) + '\n').encode(), b'')
    client.runner = exhausted
    client.config['semantic_max_attempts'] = 3
    state = run_agent_packets(directory, client, validator)
    assert state['complete'] is False
    assert len(calls) == 1
    assert state['batches'][0]['failure_category'] == 'quota_exhausted'
    assert all(b['status'] == 'deferred' for b in state['batches'][1:])
    assert not list((directory / 'results').glob('*.json'))


@pytest.mark.parametrize('failure', [None, 'tamper', 'wrong_batch', 'other_stage'])
def test_resume_rechecks_proof_semantics_and_role_before_recovering(tmp_path, monkeypatch, failure):
    directory, packet, client, calls = setup(tmp_path, monkeypatch,
        'interaction-generation' if failure == 'other_stage' else 'interaction-model')
    raw = client.agent(packet)
    raw.update(batch_id=packet['batch_id'], input_hash=packet['input_hash'], model=client.model('agent'))
    if failure == 'tamper':
        raw['items'][0]['value'] = 'unsupported'
    elif failure == 'wrong_batch':
        raw['batch_id'] = 'another-input'
    write_json(directory / 'attempts' / (packet['batch_id'] + '-prior.json'),
        {'result': raw, 'validation_error': 'old guard rejected', 'attempt': 1})
    state = run_agent_packets(directory, client, validator)
    assert state['complete']
    assert state['batches'][0]['status'] == ('recovered' if failure is None else 'complete')
    assert len(calls) == (1 if failure is None else 2)
    saved_path = directory / 'results' / (packet['batch_id'] + '.json')
    validate_result_execution(read_json(saved_path), result_path=saved_path)


@pytest.mark.parametrize('stage,feedback_field', [
    ('interaction-model', 'model_origin_feedback'),
    ('interaction-model-audit', 'source_only_review_feedback')])
def test_explicit_source_rejection_cannot_be_recovered_as_a_transport_retry(tmp_path, monkeypatch, stage, feedback_field):
    directory, packet, client, calls = setup(tmp_path, monkeypatch, stage=stage)
    raw = client.agent(packet)
    raw.update(batch_id=packet['batch_id'], input_hash=packet['input_hash'], model=client.model('agent'))
    write_json(directory / 'attempts' / (packet['batch_id'] + '-older.json'),
        {'result': raw, 'validation_error': 'old transport rejection', 'attempt': 1})
    write_json(directory / 'attempts' / (packet['batch_id'] + '-review.json'),
        {'result': raw, 'validation_error': 'independent source review rejected this decision',
         'attempt': 0, feedback_field: [{'problem': 'concrete source omission'}]})
    state = run_agent_packets(directory, client, validator)
    assert state['complete'] and state['batches'][0]['status'] == 'complete'
    assert len(calls) == 2  # Original execution plus actual re-extraction/rejudge.
