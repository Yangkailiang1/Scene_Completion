from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from scene_completion import quota_profiles as q
from scene_completion.case_dag import CallGate, TaskBlocked
from scene_completion.token_budget import TokenBudget


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


def _budgeted_client(tmp_path, name, *, endpoint='https://same.invalid', credential='ACCOUNT_KEY', **budget_config):
    client = Client(name)
    client.base_url = endpoint
    client.config.update(api_key_env=credential)
    client.config.update(budget_config)
    client.token_budget = TokenBudget({'token_budget_limit': 2000,
        'token_budget_ledger': str(tmp_path / (name + '.json')), **budget_config})
    return client


def _mark_usage_unknown(budget):
    request_id = budget.reserve({'model': 'fixture', 'messages': [{'role': 'user', 'content': 'x'}], 'max_tokens': 20})
    budget.settle(request_id)


def test_preferred_profile_cannot_escape_same_provider_unknown_usage(tmp_path, monkeypatch):
    clients = [_budgeted_client(tmp_path, 'old'), _budgeted_client(tmp_path, 'new')]
    _mark_usage_unknown(clients[0].token_budget)
    clients[0].config.update(batch_preferred_profile_index=1, batch_profile_selection_reason='Use configured fallback')
    calls = []
    monkeypatch.setattr('scene_completion.model_access.preflight', lambda c: calls.append('preflight'))
    monkeypatch.setattr(q, 'run_agent_packets', lambda *a, **k: calls.append('run'))
    pool = q.BatchProfiles(tmp_path, clients, CallGate(1))

    with pytest.raises(TaskBlocked, match='unresolved_previous_request'):
        pool.run_batch(tmp_path, None, 'batch')
    assert pool.current()[0] == 1
    assert calls == []


def test_unknown_usage_on_other_provider_does_not_freeze_fallback(tmp_path, monkeypatch):
    clients = [_budgeted_client(tmp_path, 'old'), _budgeted_client(tmp_path, 'new',
        endpoint='https://other.invalid', credential='OTHER_ACCOUNT_KEY')]
    _mark_usage_unknown(clients[0].token_budget)
    clients[0].config.update(batch_preferred_profile_index=1, batch_profile_selection_reason='Use independent provider')
    monkeypatch.setattr('scene_completion.model_access.preflight', lambda c: None)
    monkeypatch.setattr(q, 'run_agent_packets', lambda *a, **k: {'complete': True})
    pool = q.BatchProfiles(tmp_path, clients, CallGate(1))

    assert pool.run_batch(tmp_path, None, 'batch')['complete']
    assert pool.current()[0] == 1


def test_reserve_and_continue_requires_shared_provider_ledger_set(tmp_path):
    client = _budgeted_client(tmp_path, 'unsafe', unknown_usage_policy='reserve_and_continue')
    with pytest.raises(ValueError, match='shared provider token limit'):
        q.BatchProfiles(tmp_path, [client], CallGate(1))


def test_shared_provider_cap_allows_retained_unknown_reservation(tmp_path, monkeypatch):
    ledgers = [str(tmp_path / 'first.json'), str(tmp_path / 'second.json')]
    shared = {'unknown_usage_policy': 'reserve_and_continue', 'provider_token_budget_limit': 3000,
        'provider_token_budget_ledgers': ledgers, 'provider_token_budget_lock': str(tmp_path / 'provider.lock')}
    clients = [_budgeted_client(tmp_path, 'first', **shared), _budgeted_client(tmp_path, 'second', **shared)]
    _mark_usage_unknown(clients[0].token_budget)
    clients[0].config.update(batch_preferred_profile_index=1, batch_profile_selection_reason='Continue within shared cap')
    monkeypatch.setattr('scene_completion.model_access.preflight', lambda c: None)
    monkeypatch.setattr(q, 'run_agent_packets', lambda *a, **k: {'complete': True})
    pool = q.BatchProfiles(tmp_path, clients, CallGate(1))

    assert pool.run_batch(tmp_path, None, 'batch')['complete']
