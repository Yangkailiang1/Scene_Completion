"""Selected batch workers must block mutations just like a whole-stage worker."""
import os
import pytest

from scene_completion.interaction_worker_state import assert_stage_idle, stage_execution_snapshot
from scene_completion.semantic_backend import read_json, write_json


@pytest.mark.parametrize('name', ['worker-status-0-of-1-selection.json', 'worker-status-1-of-3.json'])
def test_selected_and_sharded_running_workers_block_retry_mutations(tmp_path, name):
    write_json(tmp_path/'worker-status-0-of-1.json', {'complete': False, 'batches': []})
    raw = {'complete': False, 'running': True, 'batches': []}
    write_json(tmp_path/name, raw)
    with pytest.raises(ValueError, match='stop or finish active stage workers') as rejected:
        assert_stage_idle(tmp_path, 'preparing retry feedback')
    assert name in str(rejected.value)
    assert read_json(tmp_path/name) == raw
    write_json(tmp_path/name, {'complete': False, 'batches': [{'status': 'failed'}]})
    assert_stage_idle(tmp_path, 'preparing retry feedback')


def test_partial_run_distinguishes_quota_failure_from_unexecuted_and_validated(tmp_path):
    write_json(tmp_path/'manifest.json', {'batches': [{'batch_id': k} for k in ('care', 'stock', 'invoice')]})
    write_json(tmp_path/'worker-status-0-of-1.json', {'complete': False, 'batches': [
        {'batch_id': 'care', 'status': 'complete'},
        {'batch_id': 'stock', 'status': 'failed', 'failure_category': 'quota_exhausted', 'error': 'private provider text'},
        {'batch_id': 'invoice', 'status': 'deferred', 'reason': 'quota_exhausted'}]})
    result = stage_execution_snapshot(tmp_path, {'pending': ['stock', 'invoice'], 'errors': {}})
    assert result['counts'] == {'validated_result': 1, 'invalid_result': 0, 'failed': 1, 'deferred': 1, 'pending': 0}
    assert all(r['failure_category'] == 'quota_exhausted' for r in result['batches'][1:])
    assert 'private provider text' not in str(result)
    assert result['informational_only']


def test_resume_ignores_resolved_quota_and_historical_batch_and_worker_success_claim(tmp_path):
    write_json(tmp_path/'manifest.json', {'batches': [{'batch_id': k} for k in ('read', 'write', 'return')]})
    old = tmp_path/'worker-status-0-of-1.json'
    newer = tmp_path/'worker-status-0-of-1-selected.json'
    write_json(old, {'complete': False, 'batches': [
        {'batch_id': 'read', 'status': 'failed', 'failure_category': 'quota_exhausted'},
        {'batch_id': 'write', 'status': 'deferred', 'reason': 'quota_exhausted'},
        {'batch_id': 'old-protocol', 'status': 'failed', 'failure_category': 'quota_exhausted'}]})
    write_json(newer, {'complete': True, 'batches': [
        {'batch_id': 'write', 'status': 'complete'}, {'batch_id': 'return', 'status': 'cached'}]})
    os.utime(old, ns=(1_000_000, 1_000_000))
    os.utime(newer, ns=(2_000_000, 2_000_000))
    result = stage_execution_snapshot(tmp_path, {'pending': ['write'], 'errors': {'return': 'invalid evidence'}})
    assert [r['status'] for r in result['batches']] == ['validated_result', 'pending', 'invalid_result']
    assert not any(r.get('failure_category') for r in result['batches'])
    assert not any(r['batch_id'] == 'old-protocol' for r in result['batches'])


def test_unreadable_worker_log_does_not_hide_pending_work(tmp_path):
    write_json(tmp_path/'manifest.json', {'batches': [{'batch_id': 'clinic-query'}]})
    (tmp_path/'worker-status-broken.json').write_text('{unfinished', encoding='utf-8')
    result = stage_execution_snapshot(tmp_path, {'pending': ['clinic-query'], 'errors': {}})
    assert result['counts']['pending'] == 1
    assert result['unreadable_worker_files'] == ['worker-status-broken.json']
