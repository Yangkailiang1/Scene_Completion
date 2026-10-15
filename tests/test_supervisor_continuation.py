import pytest

from scene_completion.case_dag import Scheduler, Task, TaskRejected, TaskBlocked, CallGate
from scene_completion.semantic_backend import read_json, write_json
from scene_completion.supervisor_continuation import request, validate_history


def setup_failed(root):
    calls = []
    def fail(d, r):
        calls.append(('batch', r['rounds']))
        raise TaskRejected({'findings': ['original defect']})
    def supervise(d, r):
        calls.append(('master', r['supervisor_rounds']))
        if r['supervisor_rounds'] == 1:
            raise TaskRejected({'findings': ['remaining structure defect']})
        return {'validated': True}
    def build():
        scheduler = Scheduler(root)
        scheduler.add(Task('a', 'uc', 'normal', version=1, execute=fail, repair=fail, supervisor=supervise))
        scheduler.add(Task('b', 'uc', 'next', ('a',), version=1,
            execute=lambda d, r: {'downstream': True}))
        scheduler.add(Task('success', 'other', 'normal', version=1,
            execute=lambda d, r: calls.append(('success', 0)) or {'preserved': True}))
        return scheduler
    scheduler = build()
    assert not scheduler.run()['complete']
    return calls, build


def correction(root, repository, name='repair.json'):
    tool = repository / '.cac/tools/checker.py'
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text('fixed = True\n')
    record = read_json(root / 'case_tasks.json')['tasks']['a']
    path = repository / name
    write_json(path, {'input_hash': record['input_hash'], 'failure_hash': record['failure_hash'],
        'kind': 'tool_fix', 'diagnosis': 'validator looked under the wrong envelope',
        'correction': 'read the unambiguous root view, preserving raw output',
        'validation': 'focused regression passes; run original validator again',
        'changed_files': ['.cac/tools/checker.py']})
    return path


def test_smaller_correction_after_local_reservation_refusal_preserves_budget(tmp_path):
    root = tmp_path / 'run'
    setup_failed(root)
    state = read_json(root / 'case_tasks.json')
    state['tasks']['a'].update(status='budget_exhausted', reason='external quota exhausted')
    write_json(root / 'case_tasks.json', state)
    case = root / 'cases' / 'case'
    write_json(case / 'case_identity.json', {'use_case_id': 'uc'})
    rejected = case / 'batches' / 'normal-supervisor-repair-1' / 'attempts' / 'batch-1.json'
    write_json(rejected, {'response_diagnostic': {'failure_category': 'budget_exhausted',
        'budget_kind': 'tokens', 'budget_reason': 'insufficient_provider_allowance'}})
    ledger = root / 'token_budget.json'
    write_json(ledger, {'limit': 900000, 'unknown_reservation': 12345})
    original = ledger.read_bytes()
    result = request(root, 'a', correction(root, tmp_path), repository=tmp_path)
    assert result['supervisor_rounds'] == 1 and result['model_calls'] == 0
    assert ledger.read_bytes() == original
    pending = read_json(root / 'case_tasks.json')['tasks']['a']['supervisor_continuations'][-1]
    assert pending['prior_local_reservation_refusal']


def test_unknown_request_never_qualifies_as_local_reservation_refusal(tmp_path):
    from scene_completion.supervisor_continuation import _local_reservation_refusal
    case = tmp_path / 'cases' / 'case'
    write_json(case / 'case_identity.json', {'use_case_id': 'uc'})
    write_json(case / 'batches' / 'normal-supervisor-repair-1' / 'attempts' / 'batch-1.json',
        {'response_diagnostic': {'budget_kind': 'tokens', 'budget_reason': 'unresolved_previous_request'}})
    assert not _local_reservation_refusal(tmp_path, {'case': 'uc', 'stage': 'normal', 'supervisor_rounds': 1})


def test_quota_resume_keeps_diagnosed_supervisor_route_and_counters(tmp_path):
    scheduler = Scheduler(tmp_path)
    scheduler.state['tasks'] = {
        'correction': {'status': 'pending', 'reason': 'external quota exhausted',
            'supervisor_revision_pending': 'bound-plan', 'supervisor_rounds': 1, 'rounds': 2},
        'stopped': {'status': 'budget_exhausted', 'reason': 'external quota exhausted',
            'supervisor_rounds': 1, 'rounds': 2},
        'batch': {'status': 'budget_exhausted', 'reason': 'external quota exhausted', 'rounds': 0}}
    scheduler.resume_external_budget()
    assert scheduler.state['tasks']['correction']['status'] == 'budget_exhausted'
    assert scheduler.state['tasks']['stopped']['status'] == 'budget_exhausted'
    assert scheduler.state['tasks']['batch']['status'] == 'pending'
    assert scheduler.state['tasks']['correction']['supervisor_rounds'] == 1
    assert scheduler.state['tasks']['correction']['rounds'] == 2


def test_controller_continues_after_initial_supervisor_failure_without_reset(tmp_path):
    root = tmp_path / 'run'
    calls, build = setup_failed(root)
    request(root, 'a', correction(root, tmp_path), repository=tmp_path)
    scheduler = build()
    assert scheduler.run()['complete']
    record = scheduler.state['tasks']['a']
    assert record['rounds'] == 1 and record['supervisor_rounds'] == 2
    assert [row for row in calls if row[0] != 'success'] == [('batch', 0), ('batch', 1), ('master', 1), ('master', 2)]
    assert calls.count(('success', 0)) == 1
    validate_history(record)
    assert scheduler.state['tasks']['success']['status'] == 'passed'
    assert build().run()['complete']
    assert len(calls) == 5


def test_continuation_rejects_changed_input_unchanged_plan_and_missing_proof(tmp_path):
    root = tmp_path / 'run'
    setup_failed(root)
    path = correction(root, tmp_path)
    request(root, 'a', path, repository=tmp_path)
    with pytest.raises(ValueError, match='already pending'):
        request(root, 'a', path, repository=tmp_path)
    state = read_json(root / 'case_tasks.json')
    record = state['tasks']['a']
    record.pop('supervisor_revision_pending')
    write_json(root / 'case_tasks.json', state)
    with pytest.raises(ValueError, match='unchanged correction'):
        request(root, 'a', path, repository=tmp_path)
    renamed = read_json(path)
    renamed['diagnosis'] += ' (renamed without changing the fix)'
    write_json(path, renamed)
    with pytest.raises(ValueError, match='rewording'):
        request(root, 'a', path, repository=tmp_path)
    record['supervisor_rounds'] = 2
    with pytest.raises(ValueError, match='distinct controller'):
        validate_history(record)
    plan = read_json(path)
    plan['failure_hash'] = 'different failure'
    write_json(path, plan)
    with pytest.raises(ValueError, match='current input and failure'):
        request(root, 'a', path, repository=tmp_path)


def test_continuation_never_overrides_confirmation_or_quota(tmp_path):
    root = tmp_path / 'run'
    setup_failed(root)
    path = correction(root, tmp_path)
    state = read_json(root / 'case_tasks.json')
    state['tasks']['a']['status'] = 'awaiting_confirmation'
    write_json(root / 'case_tasks.json', state)
    with pytest.raises(ValueError, match='stopped failed'):
        request(root, 'a', path, repository=tmp_path)
    state['tasks']['a'].update(status='budget_exhausted', reason={'budget_reason': 'unresolved_previous_request'})
    write_json(root / 'case_tasks.json', state)
    with pytest.raises(ValueError, match='unknown usage'):
        request(root, 'a', path, repository=tmp_path)


def test_admission_pause_prevents_paid_calls_and_resumes_same_supervisor_round(tmp_path):
    calls, build = setup_failed(tmp_path)
    request(tmp_path, 'a', correction(tmp_path, tmp_path), repository=tmp_path)
    marker = tmp_path / 'pause_requested.json'
    marker.write_text('{}')
    scheduler = build()
    assert not scheduler.run()['complete']
    assert scheduler.state['tasks']['a']['supervisor_rounds'] == 1
    gate = CallGate(1, pause_file=marker)
    with pytest.raises(TaskBlocked) as error:
        gate.call(lambda: pytest.fail('paused call'))
    assert error.value.details['semantic_round_not_consumed'] is True
    marker.unlink()
    assert build().run()['complete']
    assert len(calls) == 5


def test_changed_correction_file_requires_controller_reassessment(tmp_path):
    root = tmp_path / 'run'
    _, build = setup_failed(root)
    request(root, 'a', correction(root, tmp_path), repository=tmp_path)
    (tmp_path / '.cac/tools/checker.py').write_text('unreviewed = True')
    with pytest.raises(ValueError, match='files changed'):
        build().run()


def test_unstarted_plan_can_be_cancelled_without_refunding_attempts(tmp_path):
    from scene_completion.supervisor_continuation import cancel_pending
    root=tmp_path/'run';setup_failed(root)
    request(root,'a',correction(root,tmp_path),repository=tmp_path)
    before=read_json(root/'case_tasks.json')['tasks']['a']
    result=cancel_pending(root,'a','dependency changed before execution')
    after=read_json(root/'case_tasks.json')['tasks']['a']
    assert result['model_calls']==0
    assert after['rounds']==before['rounds'] and after['supervisor_rounds']==before['supervisor_rounds']
    assert after['supervisor_continuations'][-1]['status']=='cancelled_unstarted'
    assert 'supervisor_revision_pending' not in after
    with pytest.raises(ValueError,match='unstarted'):
        cancel_pending(root,'a','again')


def test_refresh_pending_requires_unchanged_failure_and_dependency_hashes(tmp_path):
    from scene_completion.supervisor_continuation import refresh_pending
    from scene_completion.sources import fingerprint
    root=tmp_path/'run';setup_failed(root)
    request(root,'a',correction(root,tmp_path),repository=tmp_path)
    state=read_json(root/'case_tasks.json');r=state['tasks']['a']
    deps={key:state['tasks'][key].get('output_hash') for key in r.get('dependencies',[])}
    r['previous_version']={'checker':'old'}
    r['supervisor_continuations'][-1]['input_hash']=fingerprint({'version':r['previous_version'],'dependencies':deps})
    r['input_hash']='new-version-input';write_json(root/'case_tasks.json',state)
    assert refresh_pending(root,'a')['model_calls']==0
    updated=read_json(root/'case_tasks.json')['tasks']['a']
    assert updated['supervisor_continuations'][-1]['input_hash']=='new-version-input'
    assert updated['supervisor_continuations'][-1]['input_rebindings'][0]['basis']=='tool_version_only_reconciliation'
    state=read_json(root/'case_tasks.json');state['tasks']['a']['failure_hash']='changed'
    write_json(root/'case_tasks.json',state)
    with pytest.raises(ValueError,match='fresh diagnosis'):
        refresh_pending(root,'a')
