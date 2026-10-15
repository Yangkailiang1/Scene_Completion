import json
import copy

import pytest

from scene_completion import model_benchmark as benchmark
from scene_completion import model_access
from scene_completion import role_cli
from scene_completion.token_budget import TokenBudget


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


def execution_result(client, batch, items=None):
    return {'batch_id': batch['batch_id'], 'input_hash': batch['input_hash'],
        'model': client.model('agent'), 'items': items or [],
        'execution_model_evidence': {'requested_model': client.model('agent'),
            'api_endpoint_hash': benchmark.fingerprint(client.base_url), 'thinking': False,
            'reasoning_effort': None, 'thinking_budget': None}}


def install_fakes(monkeypatch, specs, outcomes):
    client = FakeClient()
    calls = []
    preflights = []
    monkeypatch.setattr(benchmark, 'cases', lambda source: specs)
    def make_client(args, output):
        client.token_budget = TokenBudget({'token_budget_limit': 900_000,
            'token_budget_ledger': str(output / 'token_budget.json'), 'unknown_usage_policy': 'stop'})
        return client
    monkeypatch.setattr(role_cli, '_client', make_client)
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
    assert report['scope']['kind'] == 'stage_level_fixed_upstream'
    assert 'not an independently executed whole-chain pass' in report['scope']['claim_limit']
    assert task['whole_chain_independent_pass'] is False


def test_inherited_repair_context_is_never_labeled_independent(tmp_path, monkeypatch):
    assigned = packet({'bounded_repair': {'round': 1}, 'evidence': ['source line']})
    install_fakes(monkeypatch, [('repair', assigned, lambda *_: None)], [True])

    report = benchmark.run('unused-source', 'unused-config', tmp_path, supplements=0)

    task = report['tasks']['repair']
    assert task['context_kind'] == 'inherited_repair_context'
    assert task['independent_pass'] is False
    assert task['assisted_context_pass'] is True
    assert task['whole_chain_independent_pass'] is False


def test_completed_resume_skips_preflight_and_model_calls(tmp_path, monkeypatch):
    assigned = packet()
    client = FakeClient()
    assignment = benchmark._assignment_fingerprint(assigned)
    folder = tmp_path / 'batches' / 'normal-0' / 'attempt-000'
    manifest = benchmark.prepare_packets(folder, assigned['stage'], [assigned['input']],
        assigned['instructions'], assigned['output_contract'])
    batch = manifest['batches'][0]
    benchmark.write_json(folder / 'results' / (batch['batch_id'] + '.json'), execution_result(client, batch))
    report = {'model': client.model('agent'), 'execution_identity': benchmark._client_identity(client),
        'tasks': {'normal-0': {'passed': True, 'input_fingerprint': benchmark.fingerprint(assigned['input']),
            'assignment_fingerprint': assignment, 'attempts': [{'attempt': 0,
                'folder': 'batches/normal-0/attempt-000', 'result': {'complete': True}}]}}}
    assert benchmark._reported_success(tmp_path, report['tasks']['normal-0'], lambda *_: [],
        client) == (True, None)
    (tmp_path / 'screening.json').write_text(json.dumps(report), encoding='utf8')
    monkeypatch.setattr(benchmark, 'cases', lambda source: [('normal-0', assigned, lambda *_: [])])
    def make_client(args, output):
        client.token_budget = TokenBudget({'token_budget_limit': 900_000,
            'token_budget_ledger': str(output / 'token_budget.json'), 'unknown_usage_policy': 'stop'})
        return client
    monkeypatch.setattr(role_cli, '_client', make_client)
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
    benchmark.write_json(folder / 'results' / (batch['batch_id'] + '.json'), execution_result(client, batch))
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
    with pytest.raises(ValueError, match='scope cannot change'):
        benchmark.run('source', 'config', tmp_path, tasks=['normal-0'])


def test_legacy_assignment_requires_matching_saved_full_packet(tmp_path):
    assigned = packet()
    folder = tmp_path / 'batches' / 'task' / 'attempt-000'
    benchmark.prepare_packets(folder, assigned['stage'], [assigned['input']],
        assigned['instructions'], assigned['output_contract'])
    task = {'input_fingerprint': benchmark.fingerprint(assigned['input']),
        'attempts': [{'attempt': 0, 'folder': 'batches/task/attempt-000'}]}
    assert benchmark._task_is_current(task, assigned, tmp_path) is True
    assert task['assignment_fingerprint'] == benchmark._assignment_fingerprint(assigned)

    for changed in [
            {**assigned, 'stage': 'different-stage'},
            {**assigned, 'instructions': ['Different role instruction.']},
            {**assigned, 'output_contract': {'items': ['different']}}]:
        other_folder = tmp_path / ('changed-' + str(len(list(tmp_path.glob('changed-*'))))) / 'attempt-000'
        benchmark.prepare_packets(other_folder, changed['stage'], [changed['input']],
            changed['instructions'], changed['output_contract'])
        legacy = {'input_fingerprint': benchmark.fingerprint(assigned['input']),
            'attempts': [{'attempt': 0, 'folder': other_folder.relative_to(tmp_path).as_posix()}]}
        assert benchmark._task_is_current(legacy, assigned, tmp_path) is False
        assert 'assignment_fingerprint' not in legacy


def test_cached_success_requires_same_endpoint_thinking_and_model_identity(tmp_path):
    client = FakeClient()
    assigned = packet()
    folder = tmp_path / 'batches' / 'task' / 'attempt-000'
    manifest = benchmark.prepare_packets(folder, assigned['stage'], [assigned['input']],
        assigned['instructions'], assigned['output_contract'])
    batch = manifest['batches'][0]
    result = execution_result(client, batch)
    benchmark.write_json(folder / 'results' / (batch['batch_id'] + '.json'), result)
    task = {'attempts': [{'folder': 'batches/task/attempt-000'}]}
    assert benchmark._reported_success(tmp_path, task, lambda *_: [], client) == (True, None)

    mutations = [
        (lambda r: r.update(model='other-model'), 'model'),
        (lambda r: r['execution_model_evidence'].update(
            api_endpoint_hash=benchmark.fingerprint('https://other.invalid/v1')), 'endpoint'),
        (lambda r: r['execution_model_evidence'].update(thinking=True), 'identity'),
        (lambda r: r['execution_model_evidence'].update(reasoning_effort='high'), 'identity'),
        (lambda r: r['execution_model_evidence'].update(provider_model='other-served-model'), 'provider'),
    ]
    for mutate, message in mutations:
        mismatched = json.loads(json.dumps(execution_result(client, batch)))
        mutate(mismatched)
        benchmark.write_json(folder / 'results' / (batch['batch_id'] + '.json'), mismatched)
        valid, failure = benchmark._reported_success(tmp_path, task, lambda *_: [], client)
        assert valid is False
        assert message in failure['validation_error']


def test_incremental_budget_counts_unknown_usage_and_stops_before_over_cap_call(tmp_path):
    client = FakeClient()
    client.token_budget = TokenBudget({'token_budget_limit': 10_000,
        'token_budget_ledger': str(tmp_path / 'ledger.json'),
        'unknown_usage_policy': 'reserve_and_continue'})
    report = {}
    guard = benchmark._install_incremental_budget_guard(client, report,
        tmp_path / 'screening.json', 1_000)
    request_id = client.token_budget.reserve({'messages': [], 'max_tokens': 500})
    client.token_budget.settle(request_id, usage=None)
    guard.refresh()
    assert report['incremental_token_budget']['incremental_used_tokens'] == 500
    assert report['incremental_token_budget']['unknown_rows'] == 1
    assert report['incremental_token_budget']['baseline_used_tokens'] == 0

    with pytest.raises(benchmark._ScreeningBudgetBlocked) as blocked:
        client.token_budget.reserve({'messages': [], 'max_tokens': 600})
    assert blocked.value.response_diagnostic['budget_reason'] == 'screening_incremental_limit'
    ledger = benchmark.read_json(tmp_path / 'ledger.json')
    assert len(ledger['requests']) == 1


def test_incremental_budget_allows_normal_settlement_and_preserves_resume_history(tmp_path):
    client = FakeClient()
    client.token_budget = TokenBudget({'token_budget_limit': 10_000,
        'token_budget_ledger': str(tmp_path / 'ledger.json')})
    report = {}
    report_file = tmp_path / 'screening.json'
    guard = benchmark._install_incremental_budget_guard(client, report, report_file, 1_000)
    request = client.token_budget.reserve({'messages': [], 'max_tokens': 800, 'model': 'candidate'})
    client.token_budget.settle(request, usage={'total_tokens': 100})
    guard.refresh()
    assert report['incremental_token_budget']['incremental_used_tokens'] == 100
    assert report['incremental_token_budget']['remaining_incremental_tokens'] == 900
    resumed_client = FakeClient()
    resumed_client.token_budget = TokenBudget({'token_budget_limit': 10_000,
        'token_budget_ledger': str(tmp_path / 'ledger.json')})
    resumed = benchmark.read_json(report_file)
    resumed_guard = benchmark._install_incremental_budget_guard(resumed_client, resumed, report_file, 1_000)
    second = resumed_client.token_budget.reserve({'messages': [], 'max_tokens': 500, 'model': 'candidate'})
    resumed_client.token_budget.settle(second, usage={'total_tokens': 200})
    resumed_guard.refresh()
    assert resumed['incremental_token_budget']['incremental_used_tokens'] == 300
    ledger = benchmark.read_json(tmp_path/'ledger.json')
    ledger['requests'][request]['charged_tokens'] = 0
    benchmark.write_json(tmp_path/'ledger.json', ledger)
    with pytest.raises(benchmark._ScreeningBudgetBlocked, match='allowance') as error:
        resumed_guard.refresh()
    assert error.value.response_diagnostic['budget_reason'] == 'token_ledger_settled_request_changed'


def test_incremental_budget_rejects_request_deletion_and_unknown_release(tmp_path):
    client = FakeClient()
    client.token_budget = TokenBudget({'token_budget_limit': 10_000,
        'token_budget_ledger': str(tmp_path/'ledger.json'), 'unknown_usage_policy':'reserve_and_continue'})
    guard = benchmark._install_incremental_budget_guard(client, {}, tmp_path/'screening.json', 1_000)
    request = client.token_budget.reserve({'messages': [], 'max_tokens': 500})
    client.token_budget.settle(request, usage=None)
    guard.refresh()
    original = benchmark.read_json(tmp_path/'ledger.json')
    deleted = copy.deepcopy(original)
    deleted['requests'].pop(request)
    benchmark.write_json(tmp_path/'ledger.json', deleted)
    with pytest.raises(benchmark._ScreeningBudgetBlocked) as error:
        guard.refresh()
    assert error.value.response_diagnostic['budget_reason'] == 'token_ledger_request_removed'
    changed = copy.deepcopy(original)
    changed['requests'][request].update(status='complete', charged_tokens=1, reported_total_tokens=1)
    benchmark.write_json(tmp_path/'ledger.json', changed)
    with pytest.raises(benchmark._ScreeningBudgetBlocked) as error:
        guard.refresh()
    assert error.value.response_diagnostic['budget_reason'] == 'token_ledger_settled_request_changed'


def test_run_reports_incremental_limit_as_budget_blocked_before_preflight_call(tmp_path, monkeypatch):
    client = FakeClient()
    specs = [('normal-0', packet(), lambda *_: [])]
    monkeypatch.setattr(benchmark, 'cases', lambda source: specs)
    monkeypatch.setattr(role_cli, '_client', lambda args, output: _budgeted(client, output))
    calls = []
    def preflight(c):
        calls.append('preflight')
        c.token_budget.reserve({'messages': [], 'max_tokens': 700})
    monkeypatch.setattr(model_access, 'preflight', preflight)
    monkeypatch.setattr(benchmark, 'run_agent_packets', lambda *args, **kwargs: pytest.fail('budget guard must stop before semantic call'))

    report = benchmark.run('unused-source', 'unused-config', tmp_path,
        supplements=0, incremental_token_limit=600)

    assert report['status'] == 'budget_blocked'
    assert report['diagnostic']['budget_reason'] == 'screening_incremental_limit'
    assert calls == ['preflight']
    assert not (tmp_path / 'token_budget.json').exists()


def test_unrun_screening_tasks_order_by_conservative_request_size(tmp_path, monkeypatch):
    small = packet({'source': 'x'})
    large = packet({'source': 'large source context ' * 500})
    small['stage'] = 'small-stage'
    large['stage'] = 'large-stage'
    specs = [('small', small, lambda *_: []), ('large', large, lambda *_: [])]
    _, calls, _ = install_fakes(monkeypatch, specs, [True, True])
    # Exercise stage-specific output reserves in the same ordering estimate
    # used by screening; both tasks remain unrun at the start of this pass.
    client = role_cli._client(None, tmp_path)
    client.output_limit = lambda stage: {'small-stage': 8_000, 'large-stage': 3_000}[stage]
    monkeypatch.setattr(role_cli, '_client', lambda args, output: client)
    report = benchmark.run('unused-source', 'unused-config', tmp_path, supplements=0)
    assert report['execution_order'][0] == 'large'
    assert [call['packet']['stage'] for call in calls] == ['large-stage', 'small-stage']


def _budgeted(client, output):
    client.token_budget = TokenBudget({'token_budget_limit': 900_000,
        'token_budget_ledger': str(output / 'token_budget.json'), 'unknown_usage_policy': 'stop'})
    return client


def test_default_cases_include_real_stage_packet_types_and_explicit_fixed_upstream_scope(tmp_path, monkeypatch):
    from scene_completion import interaction_batches as ib
    from scene_completion import concern_gap_batches as gb
    from scene_completion import interaction_audit, interaction_participants
    from scene_completion import concern_gap_dag, concern_gap_normalize_diagnostics
    from scene_completion import concern_gap_repair, concern_gap_comparison

    source = tmp_path / 'source'
    source.mkdir()
    write = benchmark.write_json
    write(source / 'sources_index.json', {})
    write(source / 'test_sources_index.json', {})
    case = 'UC-1'
    write(source / 'run_manifest.json', {'scope': {'use_case_ids': [case]}})
    run_case = source / 'cases' / benchmark.fingerprint(case)[:16]
    batches = run_case / 'batches'
    task_records = {}
    base_stages = [('normal', 'interaction-model'), ('E-extract', 'interaction-checker'),
        ('E-audit', 'interaction-checker-audit'), ('T-extract', 'gap-test-extract')]
    all_stages = base_stages + [('G-generate', 'gap-generation'), ('diagnosis', 'gap-diagnosis'),
        ('graphs', 'gap-graph-check'), ('participants', 'interaction-participants'),
        ('features', 'gap-features'), ('normalize-G', 'gap-normalize-G'),
        ('reverse-G', 'gap-reverse-check-G'), ('compare-EG', 'gap-ambiguity-EG')]
    for name, stage in all_stages:
        folder_name = name if name != 'diagnosis' else 'G-generate-diagnosis-1'
        folder = batches / folder_name
        fixture_input = {'fixed_upstream_context': name, 'hard_case_payload': ['source'] * (len(name) + 1)}
        if name == 'E-audit':
            fixture_input['requirement_layer'] = 'SR'
        manifest = benchmark.prepare_packets(folder, stage,
            [fixture_input],
            ['Original role instructions.'], {'items': []})
        if name in {s for s, _ in base_stages}:
            output_file = source / 'task_outputs' / (name + '.json')
            write(output_file, {'folder': str(folder.resolve())})
            task_records[case + ':' + name] = {'status': 'passed',
                'output_file': output_file.relative_to(source).as_posix()}
    write(source / 'case_tasks.json', {'tasks': task_records})

    passthrough = lambda *_: []
    monkeypatch.setattr(ib, 'model_validator', lambda *_: passthrough)
    monkeypatch.setattr(ib, 'checker_validator', lambda *_: passthrough)
    monkeypatch.setattr(ib, 'test_validator', lambda *_: passthrough)
    monkeypatch.setattr(interaction_audit, 'checker_audit_validator', lambda *_: passthrough)
    monkeypatch.setattr(gb, 'generation_validator', lambda *_: passthrough)
    monkeypatch.setattr(gb, 'feature_validator', lambda *_: passthrough)
    monkeypatch.setattr(concern_gap_dag, 'diagnosis_validator', passthrough)
    monkeypatch.setattr(concern_gap_dag, 'verify_execution_output', lambda *_: None)
    monkeypatch.setattr(interaction_participants, 'participant_validator', lambda *_: passthrough)
    monkeypatch.setattr(concern_gap_normalize_diagnostics, 'validator', lambda *_: passthrough)
    monkeypatch.setattr(concern_gap_repair, 'reverse_validator', passthrough)
    monkeypatch.setattr(concern_gap_comparison, 'validator', passthrough)

    specs = benchmark.cases(source)
    by_name = {name: packet for name, packet, _ in specs}
    assert {name for name in ('graphs', 'participants', 'features', 'normalize-G', 'reverse-G', 'compare-EG')
        if name in by_name} == {'graphs', 'participants', 'features', 'normalize-G', 'reverse-G', 'compare-EG'}
    assert {by_name[name]['stage'] for name in by_name} >= {
        'gap-graph-check', 'interaction-participants', 'gap-features', 'gap-normalize-G',
        'gap-reverse-check-G', 'gap-ambiguity-EG'}
    for name in ('graphs', 'participants', 'features', 'normalize-G', 'reverse-G', 'compare-EG'):
        assert by_name[name]['input']['benchmark_scope']['kind'] == 'stage_fixed_upstream'
    assert by_name['E-audit-0']['input']['requirement_layer'] == 'SR'
    assert by_name['E-audit-0']['input']['benchmark_scope']['kind'] == 'stage_fixed_upstream'
    estimates = benchmark.estimate_inputs(specs)
    assert all(row['assignment_utf8_bytes'] > 0 for row in estimates)
    assert all(row['conservative_input_token_estimate'] == row['assignment_utf8_bytes'] for row in estimates)


def test_screening_packet_closures_are_bounded_and_complete():
    normalized = packet({'scenarios': [
        {'scenario_id': 's1', 'mount_id': 'm1', 'use_case_id': 'u1', 'exchange_id': 'e1', 'source_refs': ['r1']},
        {'scenario_id': 's2', 'mount_id': 'm1', 'use_case_id': 'u1', 'exchange_id': 'e1', 'source_refs': ['r2']},
        {'scenario_id': 's3', 'mount_id': 'm2', 'use_case_id': 'u2', 'exchange_id': 'e2', 'source_refs': ['r3']}],
        'original_evidence': [{'scenario_id': sid, 'source_ref': 'r', 'text': sid} for sid in ('s1','s2','s3')],
        'locations': [{'location_id': 'l1', 'use_case_id': 'u1'}, {'location_id': 'l2', 'use_case_id': 'u2'}],
        'exchange_details': [{'exchange_id': 'e1', 'use_case_id': 'u1'}, {'exchange_id': 'e2', 'use_case_id': 'u2'}],
        'nodes': [{'node_id': 'n1', 'use_case_id': 'u1'}, {'node_id': 'n2', 'use_case_id': 'u2'}]})
    normalize_input = benchmark._bounded_normalize(normalized)['input']
    selected = {row['scenario_id'] for row in normalize_input['scenarios']}
    assert len({row['mount_id'] for row in normalize_input['scenarios']}) == 2
    assert {row['scenario_id'] for row in normalize_input['original_evidence']} == selected
    assert {row['use_case_id'] for row in normalize_input['locations']} == {'u1', 'u2'}
    assert normalize_input['benchmark_scope']['kind'] == 'stage_fixed_upstream'

    reverse = packet({'original_scenarios': [{'scenario_id': f's{i}', 'mount_id': 'm1' if i < 2 else 'm2',
            'use_case_id': 'u'} for i in range(3)],
        'units': [{'source_scenario_id': f's{i}', 'unit_id': f'u{i}'} for i in range(3)],
        'original_evidence': [{'scenario_id': f's{i}', 'source_ref': f'r{i}'} for i in range(3)],
        'locations': []})
    reverse_input = benchmark._bounded_reverse(reverse)['input']
    selected = {row['scenario_id'] for row in reverse_input['original_scenarios']}
    assert len({row['mount_id'] for row in reverse_input['original_scenarios']}) == 2
    assert {row['source_scenario_id'] for row in reverse_input['units']} == selected
    assert {row['scenario_id'] for row in reverse_input['original_evidence']} == selected

    generation = packet({'mounts': [{'mount_id': f'm{i}', 'exchange_id': f'e{i}', 'source_refs': [f'r{i}']}
        for i in range(4)], 'exchanges': [{'exchange_id': f'e{i}', 'from_node': f'n{i}', 'to_node': f'n{i+1}'}
        for i in range(4)], 'checked_features': [{'exchange_id': f'e{i}'} for i in range(4)],
        'nodes': [{'node_id': f'n{i}'} for i in range(5)]})
    generation_input = benchmark._bounded_generation(generation)['input']
    exchanges = {row['exchange_id'] for row in generation_input['exchanges']}
    assert len(generation_input['mounts']) == 2
    assert exchanges == {row['exchange_id'] for row in generation_input['mounts']}
    assert exchanges == {row['exchange_id'] for row in generation_input['checked_features']}
    assert generation_input['benchmark_scope']['kind'] == 'stage_fixed_upstream'

    comparison = packet({'checker': [{'scenario_id': 'c1'}],
        'generated': [{'scenario_id': f'g{i}'} for i in range(4)],
        'canonical_metadata': {key: {} for key in ['c1', 'g0', 'g1', 'g2', 'g3']}})
    comparison_input = benchmark._bounded_comparison(comparison)['input']
    generated_ids = {row['scenario_id'] for row in comparison_input['generated']}
    assert len(generated_ids) == 2
    assert set(comparison_input['canonical_metadata']) == {'c1'} | generated_ids
    assert comparison_input['expected_pairs'] == [
        {'checker_scenario_id': 'c1', 'generated_scenario_id': generated_id}
        for generated_id in (row['scenario_id'] for row in comparison_input['generated'])]
