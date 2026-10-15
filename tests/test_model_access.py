import json
import time
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest

from scene_completion.semantic_backend import SemanticClient, read_json, write_json, prepare_packets, run_agent_packets
from scene_completion.model_access import probe, registry, configure_models, ModelUnavailable
from scene_completion.case_dag import CallGate, TaskBlocked
from scene_completion.model_configuration import config_overrides, matches_review_policy


def client(tmp_path, monkeypatch, calls, rejected=()):
    monkeypatch.setenv('CAPABILITY_KEY', 'local-private-key')
    def transport(url, key, body, *args):
        calls.append((url, body))
        if body['model'] in rejected:
            error = RuntimeError('HTTP 404')
            error.response_diagnostic = {'http_status':404, 'failure_category':'model_unavailable'}
            raise error
        if url.endswith('/embeddings'):
            return {'data':[{'index':i,'embedding':[1.,0.]} for i in range(len(body['input']))]}
        return {'model':'actual-provider-route', 'choices':[{'message':{'content':'{"ok":true}'}}]}
    return SemanticClient({'agent_model':'available-chat','embedding_model':'available-vector','base_url':'https://fixture.invalid/v1',
        'api_key_env':'CAPABILITY_KEY','cache_dir':str(tmp_path),'thinking':False,'max_concurrency':1}, transport)


def test_probes_are_cached_serialized_and_keep_embedding_capability_separate(tmp_path, monkeypatch):
    calls = []
    c = client(tmp_path, monkeypatch, calls)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: probe(c), range(3)))
    assert len(calls) == 1 and all(r['status']=='available' for r in results)
    assert probe(c,'embedding')['kind']=='embedding' and len(calls)==2
    assert probe(c,'embedding')['cached'] and len(calls)==2
    assert 'local-private-key' not in json.dumps(read_json(tmp_path/'model_access.json'))


def test_denied_model_stops_repeat_requests_until_refresh_or_configuration_changes(tmp_path, monkeypatch):
    calls=[]
    c=client(tmp_path, monkeypatch, calls, rejected={'denied'})
    c.config['agent_model']='denied'
    for _ in range(3):
        with pytest.raises(ModelUnavailable):probe(c)
    assert len(calls)==1
    with pytest.raises(ModelUnavailable):probe(c,force=True)
    assert len(calls)==2
    c.config['agent_model']='available-chat'
    assert probe(c)['status']=='available' and len(calls)==3
    c.api_key='rotated-private-key'
    assert not probe(c)['cached'] and len(calls)==4


def test_failed_preflight_is_not_repeated_by_every_ready_stage(tmp_path,monkeypatch):
    calls=[];c=client(tmp_path,monkeypatch,calls)
    def fail(*args):
        calls.append('500');error=RuntimeError('HTTP 500')
        error.response_diagnostic={'http_status':500,'failure_category':'transport_error'};raise error
    c.transport=fail
    for _ in range(3):
        with pytest.raises(ModelUnavailable) as exc:probe(c)
        assert exc.value.response_diagnostic['configuration_required']
    assert calls==['500']


def test_authentication_failure_blocks_other_models_on_same_endpoint(tmp_path, monkeypatch):
    calls=[]
    c=client(tmp_path,monkeypatch,calls)
    def fail(*args):
        calls.append('denied')
        exc=RuntimeError('HTTP 401')
        exc.response_diagnostic={'http_status':401,'failure_category':'authentication_failed'}
        raise exc
    c.transport=fail
    with pytest.raises(ModelUnavailable):probe(c)
    c.config['agent_model']='another-model'
    with pytest.raises(ModelUnavailable):probe(c)
    assert calls==['denied']


def test_endpoint_denial_overrides_a_previously_successful_model_probe(tmp_path, monkeypatch):
    calls=[]
    c=client(tmp_path,monkeypatch,calls)
    probe(c)
    registry(c).record('endpoint','*',available=False,category='authentication_failed')
    with pytest.raises(ModelUnavailable):probe(c)
    with pytest.raises(ModelUnavailable):c.agent({'stage':'fixture','input':{}})
    assert len(calls)==1


def test_cached_vectors_do_not_probe_even_after_availability_record_expires(tmp_path, monkeypatch):
    from scene_completion.model_access import with_embedding_preflight
    calls=[]
    c=client(tmp_path,monkeypatch,calls)
    assert with_embedding_preflight(c,['existing scene'],c.embeddings)==[[1.,0.]]
    assert len(calls)==2  # one capability probe, one actual vector
    access=registry(c)
    access.records=read_json(access.path)
    for row in access.records.values():row['expires_at']=0
    write_json(access.path,access.records)
    # New process, disk cache only; expired availability is irrelevant to reuse.
    resumed=client(tmp_path,monkeypatch,calls)
    assert with_embedding_preflight(resumed,['existing scene'],resumed.embeddings)==[[1.,0.]]
    assert len(calls)==2


def test_configurator_supports_an_independent_embedding_endpoint(tmp_path, monkeypatch):
    calls=[]
    agent=client(tmp_path/'agent',monkeypatch,calls)
    embedding=client(tmp_path/'embedding',monkeypatch,calls)
    embedding.base_url='https://vector.invalid/v1'
    embedding.config['base_url']=embedding.base_url
    report=tmp_path/'checked.json';write_json(report,{'models':[probe(agent),probe(embedding,'embedding')]})
    config=tmp_path/'agent.json';write_json(config,agent.config)
    embed_config=tmp_path/'embedding.json';write_json(embed_config,embedding.config)
    args=SimpleNamespace(config=str(config),checked_report=str(report),output_config=str(tmp_path/'runtime.json'),
        agent_model='available-chat',embedding_model='available-vector',review_model=None,max_concurrency=1,env_file=None,
        embedding_config=str(embed_config),output_embedding_config=str(tmp_path/'vectors.json'))
    assert configure_models(args)[0]['complete']
    assert read_json(args.output_embedding_config)['base_url']=='https://vector.invalid/v1'
    args.embedding_config=None
    with pytest.raises(ValueError,match='different endpoint'):configure_models(args)


def test_worker_treats_model_access_failure_as_configuration_not_semantic_retry(tmp_path, monkeypatch):
    calls=[]
    c=client(tmp_path/'cache',monkeypatch,calls,rejected={'denied'})
    c.config.update(agent_model='denied',semantic_max_attempts=4)
    folder=tmp_path/'batches'
    prepare_packets(folder,'gap-fixture',[{}, {}, {}],[],{'ok':True})
    result=run_agent_packets(folder,c,lambda p,r:[r['ok']])
    assert len(calls)==1 and not result['complete']
    assert result['batches'][0]['failure_category']=='model_unavailable'
    assert all(r.get('reason')=='model_unavailable' for r in result['batches'][1:])


def test_configurator_accepts_checked_choices_and_rejects_endpoint_mismatch(tmp_path, monkeypatch):
    calls=[]
    c=client(tmp_path/'cache',monkeypatch,calls)
    result=probe(c)
    report=tmp_path/'checked.json';write_json(report,{'models':[result]})
    config=tmp_path/'original.json';write_json(config,c.config)
    output=tmp_path/'configured.json'
    args=SimpleNamespace(config=str(config),checked_report=str(report),output_config=str(output),
        agent_model='available-chat',embedding_model=None,review_model='available-chat',max_concurrency=1,env_file=None)
    assert configure_models(args)[0]['complete']
    written=read_json(output)
    assert written['agent_model']=='available-chat' and written['max_concurrency']==1 and written['review_model']=='available-chat'
    assert 'local-private-key' not in output.read_text(encoding='utf8')
    args.agent_model='unchecked'
    with pytest.raises(ValueError,match='successful capability probe'):configure_models(args)
    args.agent_model='available-chat'
    altered=read_json(config);altered['base_url']='https://different.invalid/v1';write_json(config,altered)
    with pytest.raises(ValueError,match='different endpoint'):configure_models(args)


def test_adaptive_concurrency_respects_explicit_cap_and_halves_on_rate_limit():
    changes=[]
    gate=CallGate(4,on_change=changes.append)
    gate.call(lambda:{'batches':[{'failure_category':'rate_limited'}]})
    assert gate.limit==4 and gate.effective_limit==2
    gate.retry_not_before=0
    gate.call(lambda:{'batches':[{'failure_category':'rate_limited'}]})
    assert gate.effective_limit==1 and len(changes)==2
    gate.retry_not_before=0
    gate.call(lambda:{'complete':True})
    assert gate.effective_limit==1
    disabled=CallGate(2,adaptive=False)
    disabled.call(lambda:{'batches':[{'failure_category':'rate_limited'}]})
    assert disabled.effective_limit==2


@pytest.mark.parametrize('value',[0,-1,True,'bad'])
def test_invalid_concurrency_is_rejected(value):
    with pytest.raises(ValueError):CallGate(value)


def test_review_follows_declared_policy_and_cli_concurrency_overrides_config(tmp_path):
    write_json(tmp_path/'run_manifest.json',{'review_policy':{'model':'chosen-review-model','reasoning_effort':None}})
    assert matches_review_policy(tmp_path,{'model':'chosen-review-model','reasoning_effort':None})
    assert not matches_review_policy(tmp_path,{'model':'gpt-6-luna','reasoning_effort':'max'})
    values=config_overrides({'max_concurrency':3},SimpleNamespace(max_concurrency=1,review_model='chosen-review-model'))
    assert values['max_concurrency']==1 and values['review_model']=='chosen-review-model'


def test_active_prompts_do_not_pin_model_names_and_modeler_role_is_primary():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'.cac'
    for folder in ('skills','agents'):
        for path in (root/folder).rglob('*.md'):
            if path.name=='SKILL.md' and not path.exists():continue
            text=path.read_text(encoding='utf8')
            assert 'ecnu-max' not in text and 'gpt-6-luna' not in text
    assert (root/'agents/scene-modeler.md').is_file()
