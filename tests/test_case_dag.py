from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from scene_completion.case_dag import Scheduler, Task, TaskRejected, TaskBlocked, CallGate
from scene_completion.semantic_backend import read_json


def test_compatible_version_reuses_verified_result_without_resetting_rounds(tmp_path):
    calls=[]
    first=Scheduler(tmp_path)
    first.add(Task('a','uc','normal',version=1,execute=lambda d,r:calls.append(1) or {'value':1}))
    assert first.run()['complete']
    first.state['tasks']['a']['rounds']=1;first.save()
    second=Scheduler(tmp_path)
    def compatible(deps,output):
        assert deps=={} and output=={'value':1}
    second.add(Task('a','uc','normal',version=2,execute=lambda d,r:pytest.fail('successful input must be reused'),compatible=compatible))
    assert second.run()['complete'] and calls==[1]
    assert second.state['tasks']['a']['rounds']==1
    assert any(e['event']=='compatible_version_reuse' for e in second.state['events'])
    third=Scheduler(tmp_path)
    def reject(deps,output):raise ValueError('semantic inputs differ')
    third.add(Task('a','uc','normal',version=3,execute=lambda d,r:calls.append(3) or {'value':3},compatible=reject))
    assert third.run()['complete'] and calls==[1,3]


def test_seventeen_cases_four_progress_while_other_cases_need_repair(tmp_path):
    scheduler = Scheduler(tmp_path, concurrency=3)
    reached = set()
    repairing = threading.Event()
    def success(deps, record):
        return {'checked': True}
    def reject(deps, record):
        raise TaskRejected({'findings': ['source citation is wrong']})
    def repair(deps, record):
        repairing.set()
        time.sleep(.02)
        return {'checked': True}
    for i in range(17):
        key = str(i)
        scheduler.add(Task(key + ':extract', key, 'extract', version=1, lane='discovery', execute=success))
        scheduler.add(Task(key + ':check', key, 'check', (key + ':extract',), version=1,
            execute=success if i < 4 else reject, repair=repair))
        scheduler.add(Task(key + ':generate', key, 'generate', (key + ':check',), version=1,
            execute=lambda d, r, key=key: reached.add(key) or {'generated': key}))
    assert scheduler.run()['complete']
    events = scheduler.state['events']
    first_four = [next(j for j, e in enumerate(events) if e['task'] == f'{i}:generate' and e['event'] == 'passed') for i in range(4)]
    last_repair = max(j for j, e in enumerate(events) if e['event'] == 'repairing')
    assert max(first_four) < last_repair
    assert reached == {str(i) for i in range(17)}


def test_deterministic_upstream_version_does_not_erase_proven_downstream_success(tmp_path):
    first = Scheduler(tmp_path)
    first.add(Task('mounts', 'uc', 'mounts', version=1, execute=lambda d, r: {'mount': 'same'}))
    first.add(Task('G', 'uc', 'G', ('mounts',), version=1,
                   execute=lambda d, r: {'candidate': 'already corrected'}))
    assert first.run()['complete']
    second = Scheduler(tmp_path)
    second.add(Task('mounts', 'uc', 'mounts', version=2, execute=lambda d, r: {'mount': 'same'}))
    def compatible(deps, output):
        assert deps == {'mounts': {'mount': 'same'}}
        assert output == {'candidate': 'already corrected'}
    second.add(Task('G', 'uc', 'G', ('mounts',), version=2,
                   execute=lambda d, r: pytest.fail('must retain directed successful output'),
                   compatible=compatible))
    assert second.run()['complete']
    assert any(e['event'] == 'compatible_retained_reuse' for e in second.state['events'])


def test_repair_budget_survives_resume_and_stops_identical_failure(tmp_path):
    calls = []
    def fail(d, r):
        calls.append(r['rounds'])
        raise TaskRejected({'findings': ['no supporting source']})
    for _ in range(3):
        scheduler = Scheduler(tmp_path)
        scheduler.add(Task('x', 'uc', 'check', version=1, execute=fail, repair=fail))
        assert not scheduler.run()['complete']
    assert calls == [0, 1]
    assert read_json(tmp_path / 'case_tasks.json')['tasks']['x']['rounds'] == 1


def test_different_failures_use_at_most_two_rounds(tmp_path):
    def fail(d, r):
        raise TaskRejected({'findings': [f'defect-{r["rounds"]}']})
    scheduler = Scheduler(tmp_path)
    scheduler.add(Task('x', 'uc', 'model', version=1, execute=fail, repair=fail))
    assert not scheduler.run()['complete']
    assert scheduler.state['tasks']['x']['rounds'] == 2
    assert scheduler.state['tasks']['x']['status'] == 'budget_exhausted'


def test_supervisor_takes_over_once_after_batch_exhaustion_and_resumes_downstream(tmp_path):
    calls = []
    def fail(d, r):
        calls.append(('batch', r['rounds']))
        raise TaskRejected({'findings': [f'defect-{r["rounds"]}']})
    for _ in range(2):
        scheduler = Scheduler(tmp_path)
        scheduler.add(Task('x', 'uc', 'normal', version=1, execute=fail, repair=fail,
            supervisor=lambda d, r: calls.append(('supervisor', r['supervisor_rounds'])) or {'checked': True}))
        scheduler.add(Task('y', 'uc', 'next', ('x',), version=1,
            execute=lambda d, r: calls.append(('next', 0)) or {'done': True}))
        assert scheduler.run()['complete']
    assert calls == [('batch', 0), ('batch', 1), ('batch', 2), ('supervisor', 1), ('next', 0)]
    assert scheduler.state['tasks']['x']['rounds'] == 2
    assert scheduler.state['tasks']['x']['supervisor_rounds'] == 1


def test_failed_supervisor_cannot_loop_or_override_confirmation(tmp_path):
    calls = []
    def fail(d, r): raise TaskRejected({'findings': ['same defect']})
    def supervisor(d, r):
        calls.append(1)
        raise TaskRejected({'findings': ['still unsupported']})
    for _ in range(3):
        scheduler = Scheduler(tmp_path)
        scheduler.add(Task('x', 'uc', 'normal', version=1, execute=fail, repair=fail, supervisor=supervisor))
        scheduler.add(Task('c', 'uc', 'confirmation', version=1,
            execute=lambda d,r: (_ for _ in ()).throw(TaskBlocked('awaiting_confirmation', 'new call')), supervisor=supervisor))
        assert not scheduler.run()['complete']
    assert calls == [1]
    assert scheduler.state['tasks']['c']['status'] == 'awaiting_confirmation'


def test_supervisor_quota_scope_shares_permits_but_not_provider_exhaustion():
    gate = CallGate(1)
    scope = gate.budget_scope()
    gate.quota.set()
    assert scope.call(lambda: 'supervisor response') == 'supervisor response'
    with pytest.raises(TaskBlocked): gate.call(lambda: 'not called')
    with scope.slot(): assert gate.active == 1
    assert gate.active == 0


def test_interrupted_supervisor_keeps_reserved_attempt(tmp_path):
    scheduler = Scheduler(tmp_path)
    scheduler.add(Task('x', 'uc', 'normal', version=1))
    scheduler.state['tasks']['x'].update(status='supervising', supervisor_rounds=1)
    scheduler.save()
    resumed = Scheduler(tmp_path)
    resumed.add(Task('x', 'uc', 'normal', version=1,
        supervisor=lambda d,r: pytest.fail('interruption cannot replenish supervisor attempt')))
    assert not resumed.run()['complete']
    assert resumed.state['tasks']['x']['supervisor_rounds'] == 1


def test_failed_context_revalidation_preserves_stopped_batch_and_rejects_new_sources(tmp_path):
    def fail(d,r): raise TaskRejected({'findings': ['same actual error']})
    first = Scheduler(tmp_path)
    first.add(Task('x','uc','normal',version=1,execute=fail,repair=fail))
    assert not first.run()['complete']
    old = first.state['tasks']['x']
    assert old['rounds'] == 1 and old['status'] == 'budget_exhausted'
    second = Scheduler(tmp_path)
    second.add(Task('x','uc','normal',version=2,execute=lambda d,r:pytest.fail('do not regenerate an exhausted batch'),
        compatible_failure=lambda d,r:None))
    assert not second.run()['complete']
    assert second.state['tasks']['x']['rounds'] == 1
    assert second.state['tasks']['x']['status'] == 'budget_exhausted'
    third = Scheduler(tmp_path)
    def changed(d,r): raise ValueError('actual original inputs changed')
    third.add(Task('x','uc','normal',version=3,execute=lambda d,r:{'new':True},compatible_failure=changed))
    assert third.run()['complete']


def test_confirmation_and_component_failure_only_block_real_dependents(tmp_path):
    scheduler = Scheduler(tmp_path, auto_repair='off')
    def pending(d, r):
        raise TaskBlocked('awaiting_confirmation', {'component': 'external payment'})
    scheduler.add(Task('payment', 'shared', 'component', version=1, execute=pending))
    scheduler.add(Task('catalog', 'shared', 'component', version=1, execute=lambda d, r: {'passed': True}))
    scheduler.add(Task('pay', 'payment-uc', 'generate', ('payment',), version=1, execute=lambda d, r: {'G': []}))
    scheduler.add(Task('browse', 'browse-uc', 'generate', ('catalog',), version=1, execute=lambda d, r: {'G': [1]}))
    assert not scheduler.run()['complete']
    assert scheduler.state['tasks']['browse']['status'] == 'passed'
    assert scheduler.state['tasks']['pay']['status'] != 'passed'


def test_local_revision_does_not_repeat_unrelated_successful_calls(tmp_path):
    calls = Counter()
    for revision in (1, 2, 2):
        scheduler = Scheduler(tmp_path)
        for case in ('a', 'b'):
            def run(d, r, case=case):
                calls[case] += 1
                return {'value': r['input_hash']}
            scheduler.add(Task(case, case, 'normal', version=revision if case == 'a' else 1, execute=run))
            scheduler.add(Task(case + '-G', case, 'G', (case,), version=1,
                execute=lambda d, r, case=case: {'normal': d[case]}))
        assert scheduler.run()['complete']
    assert calls == {'a': 2, 'b': 1}


def test_global_gate_caps_all_stages_including_embedding_and_quota(tmp_path):
    gate = CallGate(3)
    lock = threading.Lock()
    active = peak = 0
    def request():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(.015)
        with lock:
            active -= 1
        return 'done'
    with ThreadPoolExecutor(max_workers=17) as pool:
        assert list(pool.map(lambda i: gate.call(request), range(17))) == ['done'] * 17
    assert peak == 3
    gate.call(lambda: {'failure_category': 'quota_exhausted'})
    with pytest.raises(TaskBlocked, match='quota exhausted'):
        gate.call(request)


def test_crash_cannot_reset_reserved_repair_round(tmp_path):
    from scene_completion.semantic_backend import write_json
    write_json(tmp_path / 'case_tasks.json', {'schema': 'case-dag-v1', 'events': [],
        'tasks': {'x': {'case': 'uc', 'stage': 'check', 'status': 'repairing', 'rounds': 2, 'attempts': []}}})
    scheduler = Scheduler(tmp_path)
    scheduler.add(Task('x', 'uc', 'check', version=1, execute=lambda d, r: (_ for _ in ()).throw(TaskRejected('failed')),
        repair=lambda d, r: pytest.fail('repair budget reset')))
    assert not scheduler.run()['complete']
    assert scheduler.state['tasks']['x']['rounds'] == 2


@pytest.mark.parametrize('blocked_status', ['budget_exhausted', 'awaiting_configuration'])
def test_quota_during_repair_resumes_reserved_round_without_reset_or_extra_round(tmp_path, blocked_status):
    calls = []
    exhausted = True
    def fail(d, r):
        raise TaskRejected({'findings': ['bad citation']})
    def repair(d, r):
        calls.append(r['rounds'])
        if exhausted:
            raise TaskBlocked(blocked_status, 'external quota exhausted')
        return {'rechecked': True}
    for _ in range(2):
        scheduler = Scheduler(tmp_path)
        scheduler.add(Task('x', 'uc', 'check', version=1, execute=fail, repair=repair))
        scheduler.resume_external_budget()
        result = scheduler.run()
        exhausted = False
    assert result['complete'] and calls == [1, 1]
    assert scheduler.state['tasks']['x']['rounds'] == 1


def test_tool_failure_does_not_spend_model_repair_budget(tmp_path):
    scheduler = Scheduler(tmp_path)
    scheduler.add(Task('x', 'uc', 'check', version=1,
        execute=lambda d, r: (_ for _ in ()).throw(OSError('missing local input')),
        repair=lambda d, r: pytest.fail('tool failure sent to model')))
    assert not scheduler.run()['complete']
    assert scheduler.state['tasks']['x']['rounds'] == 0


def test_scope_change_retains_inactive_success_and_budget_for_later_resume(tmp_path):
    calls = Counter()
    for cases in (('a', 'b'), ('a',), ('a', 'b')):
        scheduler = Scheduler(tmp_path)
        for case in cases:
            def execute(d, r, case=case):
                calls[case] += 1
                return {'case': case}
            scheduler.add(Task(case, case, 'source', version=1, execute=execute))
        assert scheduler.run()['complete']
        if cases == ('a',):
            assert 'b' not in scheduler.state['tasks'] and scheduler.state['inactive_tasks']['b']['status'] == 'passed'
    assert calls == {'a': 1, 'b': 1}
