import json

import pytest

from scene_completion import model_benchmark as benchmark
from scene_completion import model_access
from scene_completion import role_cli


class FakeClient:
    def __init__(self, model='fixture-model'):
        self._model = model
        self.config = {'thinking': False, 'reasoning_effort': 'low'}
        self.base_url = 'https://fixture.invalid/v1'
        self.profiler = None

    def model(self, kind):
        assert kind == 'agent'
        return self._model


def packet(data=None):
    return {'stage': 'normal', 'input': data or {'evidence': ['source line']},
        'instructions': ['Use only assigned evidence.'], 'output_contract': {'items': []}}


def install_fakes(monkeypatch, specs, outcomes):
    client = FakeClient()
    calls = []
    preflights = []
    monkeypatch.setattr(benchmark, 'cases', lambda source: specs)
    monkeypatch.setattr(role_cli, '_client', lambda args, output: client)
    monkeypatch.setattr(model_access, 'preflight', lambda c: preflights.append(c) or {'status': 'available'})

    def run_packets(folder, c, validator):
        packet_path = next((folder / 'packets').glob('*.json'))
        saved = json.loads(packet_path.read_text(encoding='utf8'))
        outcome = outcomes[len(calls)]
        calls.append({'folder': folder, 'packet': saved})
        raw = outcome.get('raw_output', {'items': []}) if isinstance(outcome, dict) else {'items': []}
        if outcome is True or isinstance(outcome, dict) and outcome.get('complete'):
            validator(saved, raw)
            complete = True
        else:
            try:
                validator(saved, raw)
            except (ValueError, KeyError, TypeError, RuntimeError):
                pass
            else:
                raise AssertionError('failed fixture outcome must be rejected by its validator')
            complete = False
        return {'complete': complete, 'batches': [{'batch_id': saved['batch_id'],
            'status': 'complete' if complete else 'failed'}]}

    monkeypatch.setattr(benchmark, 'run_agent_packets', run_packets)
    return client, calls, preflights


def test_supplements_are_directed_and_stop_after_same_error_makes_no_progress(tmp_path, monkeypatch):
    assigned = packet()
    def validator(p, result):
        if not p['input'].get('bounded_repair'):
            raise ValueError('missing required item')
        raise ValueError('missing required item')
    outcomes = [{'complete': False, 'raw_output': {'items': []}},
        {'complete': False, 'raw_output': {'items': []}}, {'complete': False, 'raw_output': {'items': []}}]
    _, calls, preflights = install_fakes(monkeypatch, [('normal-0', assigned, validator)], outcomes)

    report = benchmark.run('unused-source', 'unused-config', tmp_path, supplements=2)

    assert len(preflights) == 1
    assert len(calls) == 2
    assert len({call['folder'] for call in calls}) == 2
    assert calls[0]['packet']['input'] == assigned['input']
    assert calls[1]['packet']['input']['bounded_repair'] == {
        'attempt': 1, 'validation_error': 'missing required item', 'raw_output': {'items': []}}
    assert calls[0]['packet']['instructions'] == assigned['instructions']
    assert 'bounded_repair.validation_error' in calls[1]['packet']['instructions'][-1]
    assert report['tasks']['normal-0']['attempts'][1]['kind'] == 'bounded_self_repair'
    assert report['tasks']['normal-0']['no_progress'] is True


def test_successful_supplement_remains_independent_when_context_is_original(tmp_path, monkeypatch):
    def validator(p, result):
        if 'bounded_repair' not in p['input']:
            raise ValueError('missing required item')
    outcomes = [{'complete': False, 'raw_output': {'items': []}}, {'complete': True, 'raw_output': {'items': [{'id': 'ok'}]}}]
    _, calls, _ = install_fakes(monkeypatch, [('normal-0', packet(), validator)], outcomes)

    report = benchmark.run('unused-source', 'unused-config', tmp_path, supplements=2)

    task = report['tasks']['normal-0']
    assert len(calls) == 2
    assert task['passed'] is True
    assert task['initial_trial_pass'] is False
    assert task['independent_pass'] is False
    assert task['self_repaired_pass'] is True
    assert task['supplemental_pass'] is True
    assert task['assisted_context_pass'] is False


def test_inherited_repair_context_is_never_labeled_independent(tmp_path, monkeypatch):
    assigned = packet({'bounded_repair': {'round': 1}, 'evidence': ['source line']})
    install_fakes(monkeypatch, [('repair', assigned, lambda *_: None)], [True])

    report = benchmark.run('unused-source', 'unused-config', tmp_path, supplements=0)

    task = report['tasks']['repair']
    assert task['context_kind'] == 'inherited_repair_context'
    assert task['independent_pass'] is False
    assert task['assisted_context_pass'] is True


def test_completed_resume_skips_preflight_and_model_calls(tmp_path, monkeypatch):
    assigned = packet()
    client = FakeClient()
    assignment = benchmark._assignment_fingerprint(assigned)
    folder = tmp_path / 'batches' / 'normal-0' / 'attempt-000'
    manifest = benchmark.prepare_packets(folder, assigned['stage'], [assigned['input']],
        assigned['instructions'], assigned['output_contract'])
    batch = manifest['batches'][0]
    benchmark.write_json(folder / 'results' / (batch['batch_id'] + '.json'), {
        'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'], 'model': client.model('agent'), 'items': []})
    report = {'model': client.model('agent'), 'execution_identity': benchmark._client_identity(client),
        'tasks': {'normal-0': {'passed': True, 'input_fingerprint': benchmark.fingerprint(assigned['input']),
            'assignment_fingerprint': assignment, 'attempts': [{'attempt': 0,
                'folder': 'batches/normal-0/attempt-000', 'result': {'complete': True}}]}}}
    assert benchmark._reported_success(tmp_path, report['tasks']['normal-0'], lambda *_: [],
        client.model('agent')) == (True, None)
    (tmp_path / 'screening.json').write_text(json.dumps(report), encoding='utf8')
    monkeypatch.setattr(benchmark, 'cases', lambda source: [('normal-0', assigned, lambda *_: [])])
    monkeypatch.setattr(role_cli, '_client', lambda args, output: client)
    monkeypatch.setattr(model_access, 'preflight', lambda c: pytest.fail('resume should skip preflight'))
    monkeypatch.setattr(benchmark, 'run_agent_packets', lambda *args, **kwargs: pytest.fail('resume should reuse report'))

    resumed = benchmark.run('unused-source', 'unused-config', tmp_path)

    assert resumed['status'] == 'screening_passed'
    assert resumed['tasks']['normal-0']['passed'] is True


def test_resume_revalidates_saved_output_and_repairs_forged_pass(tmp_path, monkeypatch):
    assigned = packet()
    client = FakeClient()

    def validator(p, result):
        if 'bounded_repair' not in p['input']:
            raise ValueError('missing required item')

    folder = tmp_path / 'batches' / 'normal-0' / 'attempt-000'
    manifest = benchmark.prepare_packets(folder, assigned['stage'], [assigned['input']],
        assigned['instructions'], assigned['output_contract'])
    batch = manifest['batches'][0]
    benchmark.write_json(folder / 'results' / (batch['batch_id'] + '.json'), {
        'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'], 'model': client.model('agent'), 'items': []})
    report = {'model': client.model('agent'), 'execution_identity': benchmark._client_identity(client),
        'tasks': {'normal-0': {'passed': True, 'input_fingerprint': benchmark.fingerprint(assigned['input']),
            'assignment_fingerprint': benchmark._assignment_fingerprint(assigned),
            'attempts': [{'attempt': 0, 'folder': 'batches/normal-0/attempt-000', 'result': {'complete': True}}]}}}
    (tmp_path / 'screening.json').write_text(json.dumps(report), encoding='utf8')
    _, calls, preflights = install_fakes(monkeypatch, [('normal-0', assigned, validator)], [True])

    resumed = benchmark.run('unused-source', 'unused-config', tmp_path, supplements=1)

    task = resumed['tasks']['normal-0']
    assert len(preflights) == 1
    assert len(calls) == 1
    assert calls[0]['packet']['input']['bounded_repair']['validation_error'].endswith('missing required item')
    assert calls[0]['packet']['input']['bounded_repair']['raw_output']['items'] == []
    assert task['reported_pass_invalidated'] is True
    assert task['self_repaired_pass'] is True


def test_output_directory_cannot_be_reused_for_another_candidate(tmp_path, monkeypatch):
    (tmp_path / 'screening.json').write_text(json.dumps({'model': 'previous-model', 'tasks': {}}), encoding='utf8')
    monkeypatch.setattr(benchmark, 'cases', lambda source: [])
    monkeypatch.setattr(role_cli, '_client', lambda args, output: FakeClient('new-model'))

    with pytest.raises(ValueError, match='different model'):
        benchmark.run('unused-source', 'unused-config', tmp_path)


def test_selected_task_does_not_repeat_other_roles(tmp_path, monkeypatch):
    specs = [('normal-0', packet(), lambda *_: []), ('T-extract-0', packet(), lambda *_: [])]
    _, calls, _ = install_fakes(monkeypatch, specs, [True])
    report = benchmark.run('source', 'config', tmp_path, tasks=['T-extract-0'], supplements=0)
    assert len(calls) == 1
    assert report['task_scope'] == ['T-extract-0']
    assert set(report['tasks']) == {'T-extract-0'}
    with pytest.raises(ValueError, match='scope changed'):
        benchmark.run('source', 'config', tmp_path, tasks=['normal-0'])
