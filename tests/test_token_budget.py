import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from scene_completion.token_budget import TokenBudget, TokenBudgetBlocked
from scene_completion.semantic_backend import SemanticClient


def settings(tmp_path, limit=10000):
    return {'token_budget_limit': limit, 'token_budget_ledger': str(tmp_path/'budget.json')}


def body():
    return {'model': 'fixture-model', 'messages': [{'role': 'user', 'content': 'hello'}], 'max_tokens': 50}


def test_accounting_resume_and_no_prompt_storage(tmp_path):
    b = TokenBudget(settings(tmp_path))
    key = b.reserve(body())
    b.settle(key, usage={'prompt_tokens': 10, 'completion_tokens': 7, 'total_tokens': 17})
    data = json.loads(b.path.read_text())
    assert data['committed_tokens'] == 17 and data['reserved_tokens'] == 0
    assert data['remaining_tokens'] == 9983
    assert 'hello' not in b.path.read_text()
    assert TokenBudget(settings(tmp_path))._read()['requests'][key]['reported_total_tokens'] == 17


def test_parallel_reservations_cannot_spend_same_allowance(tmp_path):
    b = TokenBudget(settings(tmp_path, 500))
    def attempt(_):
        try: return b.reserve(body())
        except TokenBudgetBlocked: return None
    with ThreadPoolExecutor(max_workers=3) as pool:
        values = list(pool.map(attempt, range(3)))
    assert sum(v is not None for v in values) == 1
    assert json.loads(b.path.read_text())['remaining_tokens'] >= 0


@pytest.mark.parametrize('usage', [None, {}, {'total_tokens': 0}, {'total_tokens': '10'}, {'total_tokens': -1}])
def test_missing_or_invalid_usage_keeps_reservation_and_stops_calls(tmp_path, usage):
    b = TokenBudget(settings(tmp_path)); key = b.reserve(body()); b.settle(key, usage=usage)
    data = b._read(); row = data['requests'][key]
    assert row['status'] == 'usage_unknown' and row['charged_tokens'] == row['reservation']
    with pytest.raises(TokenBudgetBlocked): TokenBudget(settings(tmp_path)).reserve(body())


def test_explicit_http_rejection_releases_reservation(tmp_path):
    b = TokenBudget(settings(tmp_path)); key = b.reserve(body()); b.settle(key, refused=True)
    assert b._read()['remaining_tokens'] == 10000
    with pytest.raises(ValueError): b.settle(key, refused=True)


def test_ledger_limit_cannot_be_reset_on_resume(tmp_path):
    b = TokenBudget(settings(tmp_path)); b.reserve(body())
    with pytest.raises(ValueError): TokenBudget(settings(tmp_path, 20000)).reserve(body())


def test_separate_reasoning_allowance_is_reserved(tmp_path):
    b = TokenBudget({**settings(tmp_path), 'token_budget_reasoning_reserve': 4096})
    request = {**body(), 'enable_thinking': True}
    key = b.reserve(request)
    assert b._read()['requests'][key]['reservation'] > 4096 + request['max_tokens']


def test_transport_failure_blocks_new_calls_and_has_no_blind_retry(tmp_path, monkeypatch):
    monkeypatch.setenv('FIXTURE_KEY', 'private-key')
    calls = []
    def transport(url, key, request, timeout, retries):
        calls.append(retries); raise TimeoutError('timed out')
    client = SemanticClient({**settings(tmp_path), 'base_url': 'https://fixture.invalid/v1',
        'api_key_env': 'FIXTURE_KEY', 'agent_model': 'fixture', 'max_retries': 6}, transport)
    with pytest.raises(TimeoutError): client.post('/chat/completions', body())
    with pytest.raises(TokenBudgetBlocked): client.post('/chat/completions', body())
    assert calls == [0]
    assert 'private-key' not in (tmp_path/'budget.json').read_text()


@pytest.mark.parametrize('thinking', [True, False])
def test_configurable_bailian_style_and_stream_usage(monkeypatch, thinking):
    monkeypatch.setenv('FIXTURE_KEY', 'private-key'); calls = []
    def transport(url, key, request, timeout, retries):
        calls.append(request)
        return {'model': 'fixture', 'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]}
    client = SemanticClient({'base_url': 'https://fixture.invalid/v1', 'api_key_env': 'FIXTURE_KEY',
        'agent_model': 'fixture', 'thinking_api': 'enable_thinking', 'thinking': thinking,
        'reasoning_effort': 'medium', 'stream': True, 'include_usage': True}, transport)
    result = client.agent({'stage': 'fixture', 'input': {}})
    assert result['ok'] and calls[0]['enable_thinking'] == thinking
    assert 'thinking' not in calls[0]
    assert calls[0]['stream_options'] == {'include_usage': True}
    assert ('reasoning_effort' in calls[0]) == thinking


def test_embedding_not_charged_to_semantic_allowance(tmp_path, monkeypatch):
    monkeypatch.setenv('FIXTURE_KEY', 'private-key')
    client = SemanticClient({**settings(tmp_path), 'base_url': 'https://fixture.invalid/v1',
        'api_key_env': 'FIXTURE_KEY'}, lambda *a: {'data': []})
    client.post('/embeddings', {'model': 'embedding', 'input': ['hello']})
    assert not (tmp_path/'budget.json').exists()
