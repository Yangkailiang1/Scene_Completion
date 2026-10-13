"""Configured models reach transports, proof checks and isolated batch/vector caches."""
import argparse
import json
import subprocess
from types import SimpleNamespace

import pytest

from scene_completion.semantic_backend import SemanticClient,prepare_packets,run_agent_packets,read_json,write_json
from scene_completion.interaction_execution_identity import validate_result_execution,validate_client_execution_model
from scene_completion.role_cli import register_commands,_client,validate_execution_models
from scene_completion.luna_subprocess import LunaSubprocessClient
from tests.test_luna_subprocess import valid_events


def api(monkeypatch,tmp_path,model='qwen38-27b-vl',embedding='vector-A',endpoint='https://fixture.invalid/v1',calls=None):
    monkeypatch.setenv('MODEL_TEST_KEY','fixture-only')
    calls=[] if calls is None else calls
    def transport(url,key,body,*args):
        calls.append((url,body))
        if url.endswith('/embeddings'):
            vector=[1.,0.] if body['model']=='vector-A' and endpoint.endswith('/v1') else [0.,1.]
            return {'data':[{'index':i,'embedding':vector} for i in range(len(body['input']))]}
        return {'model':'observed-provider-model','choices':[{'message':{'content':'{"items":[]}'},'finish_reason':'stop'}]}
    return SemanticClient({'base_url':endpoint,'api_key_env':'MODEL_TEST_KEY','agent_model':model,
        'embedding_model':embedding,'cache_dir':str(tmp_path/'vectors'),'max_concurrency':1,
        'semantic_max_attempts':1},transport=transport),calls


@pytest.mark.parametrize('model',['ecnu-max','qwen38-27b-vl','project-specific-model'])
def test_dynamic_api_batch_request_proof_and_zero_call_resume(monkeypatch,tmp_path,model):
    c,calls=api(monkeypatch,tmp_path,model=model)
    folder=tmp_path/'stage'
    prepare_packets(folder,'gap-fixture',[{}],[],{'items':[]})
    validator=lambda p,r:r['items']
    assert run_agent_packets(folder,c,validator)['complete']
    result=read_json(next((folder/'results').glob('*.json')))
    assert calls[0][1]['model']==model
    assert validate_result_execution(result,expected_models=[model])['model']==model
    assert result['execution_model_evidence']['provider_model']=='observed-provider-model'
    assert run_agent_packets(folder,c,validator)['batches'][0]['status']=='cached'
    assert len(calls)==1
    with pytest.raises(ValueError,match='allowed'):validate_result_execution(result,expected_models=['different'])
    with pytest.raises(ValueError,match='request evidence'):validate_result_execution({'model':model})


def test_batch_switches_model_or_endpoint_without_retagging_old_execution(monkeypatch,tmp_path):
    c,calls=api(monkeypatch,tmp_path,model='ecnu-max')
    folder=tmp_path/'stage';prepare_packets(folder,'gap-fixture',[{}],[],{'items':[]})
    validator=lambda p,r:r['items']
    assert run_agent_packets(folder,c,validator)['complete']
    c,calls=api(monkeypatch,tmp_path,model='qwen38-27b-vl',calls=calls)
    assert run_agent_packets(folder,c,validator)['complete']
    c,calls=api(monkeypatch,tmp_path,endpoint='https://other.invalid/v1',calls=calls)
    assert run_agent_packets(folder,c,validator)['complete']
    assert [body['model'] for url,body in calls]==['ecnu-max','qwen38-27b-vl','qwen38-27b-vl']
    prior=[read_json(p)['result']['model'] for p in (folder/'attempts').glob('*-cache-*.json')]
    assert 'ecnu-max' in prior


def test_embedding_model_and_endpoint_each_have_their_own_cached_vectors(monkeypatch,tmp_path):
    c,calls=api(monkeypatch,tmp_path)
    assert c.embeddings(['same text'])==[[1.,0.]]
    assert c.embeddings(['same text'])==[[1.,0.]]
    changed,calls=api(monkeypatch,tmp_path,embedding='vector-B',calls=calls)
    assert changed.embeddings(['same text'])==[[0.,1.]]
    other,calls=api(monkeypatch,tmp_path,endpoint='https://fixture.invalid/v2',calls=calls)
    assert other.embeddings(['same text'])==[[0.,1.]]
    assert len(calls)==3
    assert c.embeddings(['same text'])==[[1.,0.]] and len(calls)==3


def test_cli_overrides_config_and_config_overrides_environment(monkeypatch,tmp_path):
    monkeypatch.setenv('SCENE_AGENT_MODEL','env-agent')
    monkeypatch.setenv('SCENE_EMBEDDING_MODEL','env-vector')
    config=tmp_path/'config.json';write_json(config,{'agent_model':'config-agent','embedding_model':'config-vector'})
    args=SimpleNamespace(config=str(config),env_file=None,agent_runtime=None,agent_model=None,embedding_model=None)
    c=_client(args,tmp_path)
    assert (c.model('agent'),c.model('embedding'))==('config-agent','config-vector')
    args.agent_model='qwen38-27b-vl';args.embedding_model='cli-vector'
    c=_client(args,tmp_path)
    assert (c.model('agent'),c.model('embedding'))==('qwen38-27b-vl','cli-vector')
    assert SemanticClient({}).model('agent')=='env-agent'
    parser=argparse.ArgumentParser();register_commands(parser.add_subparsers(dest='command'))
    parsed=parser.parse_args(['run-agent-batches','--stage-dir','stage','--sources-index','sources',
        '--agent-model','qwen38-27b-vl','--embedding-model','selected-vector','--agent-runtime','openai-compatible'])
    assert parsed.agent_model=='qwen38-27b-vl' and parsed.embedding_model=='selected-vector'


def test_model_environment_references_and_invalid_identifiers(monkeypatch):
    monkeypatch.setenv('CONFIG_AGENT','qwen38-27b-vl')
    assert SemanticClient({'agent_model':'${CONFIG_AGENT}'}).model('agent')=='qwen38-27b-vl'
    for value in ['',[],None,'${UNSET_MODEL_TEST_VARIABLE}','bad\nmodel']:
        with pytest.raises(ValueError):SemanticClient({'agent_model':value}).model('agent')


def test_native_cli_uses_configured_model_with_full_proof_and_rejects_relabeling(tmp_path,monkeypatch):
    exe=tmp_path/'codex.exe';exe.write_text('fixture executable',encoding='utf8')
    monkeypatch.setattr('scene_completion.luna_subprocess.shutil.which',lambda _:str(exe))
    def runner(argv,**kwargs):
        assert argv[argv.index('-m')+1]=='configured-native-model'
        path=argv[argv.index('--output-last-message')+1]
        open(path,'w',encoding='utf8').write('{"items":[]}')
        return subprocess.CompletedProcess(argv,0,valid_events(),b'')
    c=LunaSubprocessClient({'native_run_dir':str(tmp_path/'native'),
        'agent_model':'configured-native-model','reasoning_effort':'high'},runner=runner)
    assert validate_client_execution_model(c)=='configured-native-model'
    packet={'stage':'fixture','input':{},'instructions':[],'output_contract':{'items':[]},'batch_id':'B','input_hash':'a'*64}
    result=c.agent(packet);result.update(model=c.model('agent'),batch_id='B',input_hash='a'*64)
    assert validate_result_execution(result)['proof_kind']=='native_subprocess'
    result['model']='renamed';result['execution_model_evidence']['requested_model']='renamed'
    with pytest.raises(ValueError,match='expected model'):validate_result_execution(result)


def test_legacy_batch_acceptance_checks_the_selected_model(tmp_path):
    write_json(tmp_path/'manifest.json',{'batches':[{'batch_id':'B'}]})
    write_json(tmp_path/'results/B.json',{'model':'qwen38-27b-vl','semantic_verification':{'model':'qwen38-27b-vl'}})
    validate_execution_models(tmp_path,'qwen38-27b-vl')
    with pytest.raises(ValueError,match='configured execution model'):validate_execution_models(tmp_path,'ecnu-max')


def test_cli_env_file_loads_generic_and_explicit_custom_model_settings(tmp_path,monkeypatch):
    from scene_completion.review import load_ecnu_env_file
    for key in ['SCENE_AGENT_MODEL','SCENE_EMBEDDING_MODEL','CUSTOM_MODEL_URL','CUSTOM_MODEL_KEY','CUSTOM_EMBED_ID']:
        # Register an undo even if absent: the dotenv loader writes outside
        # monkeypatch and must not leak model selection into later tests.
        monkeypatch.setenv(key,'')
        monkeypatch.delenv(key,raising=False)
    env=tmp_path/'models.env'
    env.write_text('SCENE_AGENT_MODEL=qwen38-27b-vl\nSCENE_EMBEDDING_MODEL=vector-local\n'
        'CUSTOM_MODEL_URL=https://fixture.invalid/v1\nCUSTOM_MODEL_KEY=fixture-key\n'
        'CUSTOM_EMBED_ID=vector-custom\nUNRELATED_SETTING=ignore-this\n',encoding='utf8')
    config=tmp_path/'config.json'
    write_json(config,{'base_url':'${CUSTOM_MODEL_URL}','api_key_env':'CUSTOM_MODEL_KEY'})
    args=SimpleNamespace(config=str(config),env_file=str(env),agent_runtime=None)
    c=_client(args,tmp_path)
    assert (c.base_url,c.model('agent'),c.model('embedding'))==('https://fixture.invalid/v1','qwen38-27b-vl','vector-local')
    assert c.api_key=='fixture-key'
    assert load_ecnu_env_file(env,extra_keys={'CUSTOM_EMBED_ID'})[-1]=='CUSTOM_EMBED_ID'
