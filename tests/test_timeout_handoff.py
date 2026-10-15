from pathlib import Path
import pytest

from scene_completion.token_budget import TokenBudget, TokenBudgetBlocked
from scene_completion.case_dag import CallGate
from scene_completion.quota_profiles import BatchProfiles
from scene_completion.semantic_backend import read_json


def body():
    return {'model': 'test', 'messages': [{'role': 'user', 'content': 'short'}], 'max_tokens': 20}


def test_unknown_usage_can_remain_charged_while_other_profile_uses_shared_allowance(tmp_path):
    peers = [str(tmp_path/'a.json'), str(tmp_path/'b.json')]
    config = {'token_budget_limit': 2000, 'unknown_usage_policy': 'reserve_and_continue',
        'provider_token_budget_limit': 800, 'provider_token_budget_ledgers': peers,
        'provider_token_budget_lock': str(tmp_path/'provider')}
    a = TokenBudget({**config, 'token_budget_ledger': peers[0]})
    b = TokenBudget({**config, 'token_budget_ledger': peers[1]})
    first = a.reserve(body()); a.settle(first)
    original = a.path.read_bytes()
    second = b.reserve(body()); b.settle(second, usage={'total_tokens': 400})
    with pytest.raises(TokenBudgetBlocked, match='budget_exhausted'):
        b.reserve(body())
    assert a.path.read_bytes() == original
    assert read_json(a.path)['requests'][first]['status'] == 'usage_unknown'


def test_timeout_advances_once_and_ledger_cannot_be_replaced(tmp_path, monkeypatch):
    class Client:
        def __init__(self, name):
            self.name = name; self.base_url = 'https://fixture.invalid'
            self.config = {'thinking': False, 'timeout_handoff': True}
            self.token_budget = TokenBudget({'token_budget_limit': 2000,
                'token_budget_ledger': str(tmp_path/(name+'.json'))})
        def model(self, kind): return self.name
    clients = [Client('small'), Client('master')]
    monkeypatch.setattr('scene_completion.model_access.preflight', lambda c: None)
    calls = []
    def worker(folder, client, validator, **kw):
        calls.append(client.name)
        if client.name == 'small':
            return {'complete': False, 'batches': [{'failure_category': 'transport_timeout'}]}
        return {'complete': True, 'batches': []}
    monkeypatch.setattr('scene_completion.quota_profiles.run_agent_packets', worker)
    pool = BatchProfiles(tmp_path, clients, CallGate(1))
    assert pool.run_batch(tmp_path, None, 'batch')['complete']
    assert calls == ['small', 'master']
    clients[0].token_budget.path = tmp_path/'replacement.json'
    with pytest.raises(ValueError, match='ledger identity'):
        BatchProfiles(tmp_path, clients, CallGate(1))


def test_explicit_profile_selection_is_audited_forward_only_and_keeps_ledgers(tmp_path):
    class Client:
        def __init__(self, name):
            self.name = name; self.base_url = 'https://fixture.invalid'
            self.config = {'thinking': False}
            self.token_budget = TokenBudget({'token_budget_limit': 2000,
                'token_budget_ledger': str(tmp_path/(name+'.json'))})
        def model(self, kind): return self.name
    clients = [Client('old'), Client('new')]
    clients[0].config['batch_preferred_profile_index'] = 1
    with pytest.raises(ValueError, match='selection_reason'):
        BatchProfiles(tmp_path, clients, CallGate(1))
    clients[0].config['batch_profile_selection_reason'] = 'Measured reasoning exhaustion; use configured runtime'
    pool = BatchProfiles(tmp_path, clients, CallGate(1))
    assert pool.current()[0] == 1
    assert pool.state['transitions'][-1]['reason'] == 'configured_profile_selection'
    previous = read_json(tmp_path/'batch_budget_bindings.json')
    clients[0].config['batch_preferred_profile_index'] = 0
    resumed = BatchProfiles(tmp_path, clients, CallGate(1))
    assert resumed.current()[0] == 1
    assert len(resumed.state['transitions']) == 1
    assert read_json(tmp_path/'batch_budget_bindings.json') == previous
