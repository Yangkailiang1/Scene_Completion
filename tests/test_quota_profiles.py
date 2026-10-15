from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from scene_completion import quota_profiles as q
from scene_completion.case_dag import CallGate, TaskBlocked


class Client:
    def __init__(self, name):
        self.name = name
        self.base_url = 'https://' + name + '.invalid'
        self.config = {'thinking': False}
    def model(self, kind): return self.name


def test_quota_only_switches_in_configured_order_and_resume_does_not_restart_primary(tmp_path, monkeypatch):
    clients = [Client('first'), Client('second'), Client('third')]
    calls = []
    monkeypatch.setattr('scene_completion.model_access.preflight', lambda c: None)
    def run(folder, client, validator, **kwargs):
        calls.append(client.name)
        if client.name != 'third':
            return {'complete': False, 'batches': [{'failure_category': 'quota_exhausted'}]}
        return {'complete': True, 'batches': []}
    monkeypatch.setattr(q, 'run_agent_packets', run)
    pool = q.BatchProfiles(tmp_path, clients, CallGate(3))
    assert pool.run_batch(tmp_path, None, 'batch')['complete']
    assert calls == ['first', 'second', 'third']
    resumed = q.BatchProfiles(tmp_path, clients, CallGate(3))
    assert resumed.current()[1].name == 'third'
    assert len(resumed.state['transitions']) == 2


def test_semantic_or_rate_limit_failure_does_not_spend_another_model(tmp_path, monkeypatch):
    clients = [Client('first'), Client('second')]
    calls = []
    monkeypatch.setattr('scene_completion.model_access.preflight', lambda c: None)
    def run(folder, client, validator, **kwargs):
        calls.append(client.name)
        return {'complete': False, 'batches': [{'error': 'diagnosis must quote supplied evidence', 'failure_category': 'rate_limited'}]}
    monkeypatch.setattr(q, 'run_agent_packets', run)
    pool = q.BatchProfiles(tmp_path, clients, CallGate(1))
    assert not pool.run_batch(tmp_path, None, 'batch')['complete']
    assert calls == ['first'] and pool.current()[0] == 0


def test_unknown_usage_blocks_all_switching_and_parallel_failure_does_not_skip_profile(tmp_path):
    pool = q.BatchProfiles(tmp_path, [Client('first'), Client('second'), Client('third')], CallGate(3))
    with pytest.raises(TaskBlocked): pool.advance(0, 'usage_unresolved')
    assert pool.current()[0] == 0
    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(lambda n: pool.advance(0, 'quota_exhausted'), range(3)))
    assert pool.current()[0] == 1 and len(pool.state['transitions']) == 1
    pool.advance(1, 'insufficient_remaining_allowance')
    with pytest.raises(TaskBlocked): pool.advance(2, 'quota_exhausted')


def test_inaccessible_configured_fallback_is_not_retried_or_confused_with_authentication(tmp_path, monkeypatch):
    from scene_completion.model_access import ModelUnavailable
    clients = [Client('unavailable'), Client('available')]
    def probe(client):
        if client.name == 'unavailable':
            raise ModelUnavailable('access_denied', client.name)
    monkeypatch.setattr('scene_completion.model_access.preflight', probe)
    monkeypatch.setattr(q, 'run_agent_packets', lambda *a, **k: {'complete': True})
    pool = q.BatchProfiles(tmp_path, clients, CallGate(1))
    assert pool.run_batch(tmp_path, None, 'batch')['complete']
    assert pool.current()[0] == 1
    assert pool.state['transitions'][0]['reason'] == 'configured_profile_access_denied'
