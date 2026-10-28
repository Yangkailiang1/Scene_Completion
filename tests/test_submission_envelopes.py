import json
import pytest
from scene_completion.contracts import packet
from scene_completion.deepagents_client import DeepAgentsClient
from scene_completion.scheduler import TaskRejected
from scene_completion.storage import read_json


@pytest.mark.parametrize('indexed', [False, True])
@pytest.mark.parametrize('mode', ['tool_calls', 'json_text'])
def test_string_question_is_rejected_with_path_and_preserved_for_repair(tmp_path, indexed, mode):
    bad = {'payload': {'services': []}, 'review_questions': ['接口所属服务尚未说明']}
    def transport(url, key, body, *args):
        msg = {'content': json.dumps({'result': bad['payload'], 'review_questions': bad['review_questions']})} if mode == 'json_text' else {'content': '', 'tool_calls': [{'id': 'submit', 'function': {'name': 'submit_result', 'arguments': json.dumps(bad)}}]}
        return {'choices': [{'message': msg, 'finish_reason': 'stop'}]}
    p = packet('api-map', {'SR': []}); p['skill_text'] = 'Extract and submit.'
    client = DeepAgentsClient({'api_key': 'fixture', 'base_url': 'http://offline/v1', 'agent_model': 'offline', 'run_root': str(tmp_path), 'indexed_context': indexed, 'submission_mode': mode}, transport=transport)
    with pytest.raises(TaskRejected, match=r'review_questions\[0\].*JSON object') as failure:
        client.agent(p)
    rejected = read_json(tmp_path / failure.value.details['rejected_output'])
    assert rejected['payload'] == {'services': []} and rejected['review_questions'] == bad['review_questions']
    assert not (tmp_path.parent / 'business_questions.json').exists()


@pytest.mark.parametrize('payload,path', [
    ('{"services":[]}', 'payload'),
    ({'services': 'bad'}, 'payload.services'),
    ({'services': ['bad']}, 'payload.services[0]'),
    ({'services': [{'name': 'svc', 'interfaces': ['GET /items'], 'source_refs': []}]}, 'payload.services[0].interfaces[0]'),
    ({'services': [{'name': 'svc', 'interfaces': [{'method': 123}], 'source_refs': []}]}, 'payload.services[0].interfaces[0].method'),
])
def test_nested_containers_cannot_reach_mapping_normalizer_as_strings(payload, path):
    from scene_completion.model_submission import containers
    from scene_completion.contracts import schema
    with pytest.raises(ValueError) as failure:
        containers(payload, schema('api-map'))
    assert path in str(failure.value)


def test_bounded_repair_keeps_good_payload_and_fixes_only_question_envelope(tmp_path):
    from scene_completion.workflow import Execution
    seen = []
    def transport(url, key, body, *args):
        seen.append(body)
        if len(seen) == 2:
            prompt = json.dumps(body, ensure_ascii=False)
            assert 'review_questions[0]' in prompt and '接口所属服务尚未说明' in prompt
        questions = ['接口所属服务尚未说明'] if len(seen) == 1 else [{'question': '接口所属服务尚未说明', 'required_answer': '请提供所属服务', 'source_refs': []}]
        return {'choices': [{'message': {'content': json.dumps({'result': {'services': []}, 'review_questions': questions})}, 'finish_reason': 'stop'}]}
    root = tmp_path / 'project' / 'run'
    config = {'api_key': 'fixture', 'base_url': 'http://offline/v1', 'agent_model': 'offline', 'run_root': str(root), 'submission_mode': 'json_text', 'indexed_context': True}
    ex = Execution(root, mode='external', client=DeepAgentsClient(config, transport=transport), config=config)
    ex.add('api-map', 'api-map', static={'SR': []})
    assert ex.finish()['complete'] and len(seen) == 2
    assert len(read_json(root.parent / 'business_questions.json')['items']) == 1
