import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from scene_completion.token_budget import TokenBudget, TokenBudgetBlocked, request_reservation
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


def test_structured_text_reservation_counts_decoded_content_not_transport_escaping(tmp_path):
    content = json.dumps({'source': '原文包含"引号"、反斜线\\和换行\n', 'items': ['"\\\n'] * 80}, ensure_ascii=False)
    request = {'model': 'fixture', 'messages': [{'role': 'user', 'content': content}], 'max_tokens': 500}
    estimate = request_reservation(request)
    old_estimate = len(json.dumps(request['messages'][0], ensure_ascii=False).encode('utf8')) + 256 + 500
    assert estimate >= len(content.encode('utf8')) + 256 + 500
    assert estimate < old_estimate
    budget = TokenBudget(settings(tmp_path, estimate))
    key = budget.reserve(request)
    budget.settle(key, usage=None)
    row = budget._read()['requests'][key]
    assert row['charged_tokens'] == estimate and row['status'] == 'usage_unknown'
    with pytest.raises(TokenBudgetBlocked): budget.reserve(request)


def test_non_text_reservation_keeps_serialized_fallback_and_reasoning():
    message = {'role': 'user', 'content': [{'type': 'text', 'text': '完整数据'}]}
    request = {'messages': [message], 'max_tokens': 400, 'enable_thinking': True}
    assert request_reservation(request, 300) == len(json.dumps(message, ensure_ascii=False).encode('utf8')) + 256 + 400 + 300


def test_incremental_and_original_reservation_estimators_agree():
    from scene_completion.model_benchmark import _reservation_for_body
    from types import SimpleNamespace
    request = {'messages': [{'role': 'user', 'content': '{"quoted":"\\n"}'}], 'max_tokens': 600}
    assert _reservation_for_body(request, SimpleNamespace(reasoning_reserve=0)) == request_reservation(request)


def test_pre_http_refusal_is_not_sent_as_semantic_repair_feedback(tmp_path):
    from scene_completion.semantic_backend import prepare_packets, write_json, run_agent_packets
    from types import SimpleNamespace
    manifest = prepare_packets(tmp_path, 'gap-fixture', [{'source': 'unchanged permitted input'}], [], {'items': []})
    batch = manifest['batches'][0]
    write_json(tmp_path/'attempts'/(batch['batch_id']+'-budget.json'), {'result': None,
        'validation_error': 'request was not admitted', 'response_diagnostic': {'failure_category': 'budget_exhausted'}})
    calls = []
    def agent(packet):
        calls.append(packet)
        return {'items': [], 'execution_model_evidence': {'requested_model': 'fixture'}}
    client = SimpleNamespace(config={'agent_model': 'fixture', 'semantic_max_attempts': 1},
        model=lambda kind: 'fixture', agent=agent)
    state = run_agent_packets(tmp_path, client, lambda p, r: r['items'])
    assert state['complete'] and len(calls) == 1
    assert 'validation_feedback' not in calls[0] and 'previous_output' not in calls[0]


def test_custom_stage_obeys_attempt_limit_and_preserves_rejected_result(tmp_path):
    from scene_completion.semantic_backend import prepare_packets, run_agent_packets
    from types import SimpleNamespace
    manifest = prepare_packets(tmp_path, 'independent-custom-review', [{'source': 'source text'}], [], {'checks': []})
    calls = []
    def agent(packet):
        calls.append(packet)
        return {'checks': [{'id': 'wrong-id'}], 'execution_model_evidence': {'requested_model': 'fixture'}}
    def reject(packet, result):
        raise ValueError('assigned ID missing')
    client = SimpleNamespace(config={'agent_model': 'fixture', 'semantic_max_attempts': 1},
        model=lambda kind: 'fixture', agent=agent)
    state = run_agent_packets(tmp_path, client, reject)
    assert not state['complete'] and len(calls) == 1
    attempts = list((tmp_path/'attempts').glob('*.json'))
    assert len(attempts) == 1
    retained = json.loads(attempts[0].read_text())
    assert retained['result']['checks'] == [{'id': 'wrong-id'}]
    assert retained['validation_error'] == 'assigned ID missing'
    assert retained['result']['batch_id'] == manifest['batches'][0]['batch_id']


def test_custom_stage_preserves_response_diagnostic_without_retry(tmp_path):
    from scene_completion.semantic_backend import prepare_packets, run_agent_packets
    from types import SimpleNamespace
    prepare_packets(tmp_path, 'independent-custom-review', [{}], [], {})
    calls = []
    def agent(packet):
        calls.append(packet)
        error = ValueError('invalid structured response')
        error.response_diagnostic = {'content': '{partial', 'finish_reason': 'length'}
        raise error
    client = SimpleNamespace(config={'agent_model': 'fixture', 'semantic_max_attempts': 1},
        model=lambda kind: 'fixture', agent=agent)
    state = run_agent_packets(tmp_path, client, lambda p, r: [])
    assert not state['complete'] and len(calls) == 1
    retained = json.loads(next((tmp_path/'attempts').glob('*.json')).read_text())
    assert retained['response_diagnostic']['content'] == '{partial'
