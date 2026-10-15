import json

from scene_completion import controller_status as c


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf8')


def run_state(root, statuses, complete=False, accepted=False):
    write(root / 'run_manifest.json', {'complete': complete, 'accepted': accepted,
        'scope': {'kind': 'representative', 'use_case_ids': ['UC']}, 'model': 'configured-model'})
    write(root / 'case_tasks.json', {'tasks': {f'UC:{i}': {'stage': str(i), 'status': s} for i,s in enumerate(statuses)}})


def test_live_controller_does_not_start_duplicate_or_claim_delivery(tmp_path, monkeypatch):
    run_state(tmp_path, ['passed', 'running'])
    process = tmp_path / 'process.json'
    write(process, {'pid': 123, 'status': 'running'})
    monkeypatch.setattr(c.os, 'kill', lambda pid, sig: None)
    result = c.inspect_run(tmp_path, process_file=process)
    assert result['next_action'] == 'wait_for_state_change_do_not_start_second_pipeline'
    assert not result['ready_to_deliver'] and result['counts']['passed'] == 1


def test_stale_running_task_is_an_interrupted_pipeline(tmp_path, monkeypatch):
    run_state(tmp_path, ['running'])
    process = tmp_path / 'process.json'
    write(process, {'pid': 123, 'status': 'running'})
    def missing(*args): raise ProcessLookupError()
    monkeypatch.setattr(c.os, 'kill', missing)
    assert c.inspect_run(tmp_path, process_file=process)['next_action'] == 'inspect_exited_pipeline_with_unfinished_tasks'


def test_computation_and_accepted_flag_do_not_replace_verified_artifacts(tmp_path, monkeypatch):
    run_state(tmp_path, ['passed'], complete=True, accepted=True)
    plain = c.inspect_run(tmp_path)
    assert plain['pipeline_complete'] and plain['recorded_accepted'] and not plain['ready_to_deliver']
    calls = []
    monkeypatch.setattr(c, 'verified_acceptance', lambda *a: calls.append(1) or [])
    assert not c.inspect_run(tmp_path, verify=True)['ready_to_deliver']
    for name in c.ARTIFACTS:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists(): p.write_text('fixture artifact', encoding='utf8')
    (tmp_path/'final_snapshot.json').write_text('fixture snapshot', encoding='utf8')
    (tmp_path/'rebuilt').mkdir()
    for name in ('report.md', 'scene_assessment.xlsx'): (tmp_path/'rebuilt'/name).write_text('fixture artifact', encoding='utf8')
    ready = c.inspect_run(tmp_path, verify=True)
    assert ready['ready_to_deliver'] and ready['next_action'] == 'deliver_verified_artifact_paths_and_scope'
    monkeypatch.setattr(c, 'verified_acceptance', lambda *a: ['review invalid'])
    assert not c.inspect_run(tmp_path, verify=True)['ready_to_deliver']


def test_unknown_usage_prevents_delivery_and_exposes_no_raw_request(tmp_path):
    run_state(tmp_path, ['passed'], complete=True, accepted=True)
    ledger = tmp_path/'budget.json'
    write(ledger, {'limit': 1000, 'committed_tokens': 500, 'reserved_tokens': 200,
        'requests': {'private_request': {'status': 'usage_unknown', 'raw': 'do not expose'}}})
    result = c.inspect_run(tmp_path, budget_ledgers=[ledger])
    assert result['next_action'] == 'resolve_unknown_usage'
    assert 'private_request' not in json.dumps(result) and 'do not expose' not in json.dumps(result)


def test_explicit_retained_reservation_policy_keeps_usage_unknown_without_global_deadlock(tmp_path):
    run_state(tmp_path, ['pending'])
    manifest = c.read(tmp_path/'run_manifest.json');manifest['usage_accounting_policy'] = 'retained_reservations'
    write(tmp_path/'run_manifest.json', manifest)
    ledger = tmp_path/'budget.json'
    write(ledger, {'requests': {'request': {'status': 'usage_unknown', 'reservation': 200, 'charged_tokens': 200}}})
    result = c.inspect_run(tmp_path, budget_ledgers=[ledger])
    assert result['unknown_usage_retained'] and not result['usage_accounting_complete']
    assert result['next_action'] != 'resolve_unknown_usage'


def test_confirmation_is_visible_while_independent_work_runs(tmp_path):
    run_state(tmp_path, ['passed', 'awaiting_confirmation', 'running'])
    result = c.inspect_run(tmp_path)
    assert result['next_action'] == 'resolve_confirmation_keep_other_tasks_running'
    assert len(result['active']) == 1 and len(result['blocked']) == 1


def test_wait_returns_on_change_without_mutating_run(tmp_path, monkeypatch):
    run_state(tmp_path, ['passed', 'pending'])
    before = (tmp_path/'case_tasks.json').read_bytes()
    monkeypatch.setattr(c.time, 'sleep', lambda seconds: write(tmp_path/'case_tasks.json',
        {'tasks': {'UC:0': {'stage': '0', 'status': 'passed'}, 'UC:1': {'stage': '1', 'status': 'running'}}}))
    result = c.wait_for_change(tmp_path, wait_seconds=2)
    assert len(result['active']) == 1
    # The only mutation above is the simulated executor, never the observer.
    assert (tmp_path/'case_tasks.json').read_bytes() != before
