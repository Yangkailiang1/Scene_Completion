from copy import deepcopy
import json,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from scene_completion.workbench import create_app
from scene_completion.workbench_cli import main
from scene_completion.runtime_settings import validate_options,request_options
from scene_completion.deepagents_client import DeepAgentsClient,_transport_model
from scene_completion.storage import write_json,read_json,windows_extended_path
from tests.test_model_accounts_cli import source,FakeAPI


def setup(tmp_path):
 c=TestClient(create_app(tmp_path));rid=c.post('/api/projects',json=source()).json()['id']
 c.put('/api/model-accounts',json={'expected_revision':0,'id':'customer','name':'客户内网','base_url':'http://internal/v1','models':['deepseek-v4.1-1017','other'],'api_key':'secret-fixture-key'})
 assert c.put(f'/api/projects/{rid}/config',json={'model_account_id':'customer','agent_model':'deepseek-v4.1-1017'}).status_code==200
 return c,rid


def test_cli_sets_and_reads_effective_config_without_resetting_fields_or_quota(tmp_path,capsys):
 c,rid=setup(tmp_path);api=FakeAPI(c)
 cfg=tmp_path/rid/'model.local.json';raw=read_json(cfg);raw.update(token_budget_ledger='unchanged.json',token_budget_limit=900000);write_json(cfg,raw)
 assert main(['configure','--project',rid,'--preset','deepseek-thinking','--max-output-tokens','65536','--stage-output','fused-ssd=90000','--total-timeout','3600','--concurrency','1'],client=api)==0
 settings=json.loads(capsys.readouterr().out);assert settings['max_tokens']==65536 and settings['reasoning_replay']
 assert main(['config','--project',rid,'--task','fused-ssd'],client=api)==0
 result=json.loads(capsys.readouterr().out);assert result['request_parameters']['max_tokens']==90000 and result['request_parameters']['thinking']=={'type':'enabled'}
 assert 'secret-fixture-key' not in json.dumps(result) and read_json(cfg)['token_budget_ledger']=='unchanged.json'
 assert main(['configure','--project',rid,'--idle-timeout','600'],client=api)==0;capsys.readouterr()
 assert read_json(cfg)['max_tokens']==65536 and read_json(cfg)['max_concurrency']==1
 before=cfg.read_bytes()
 assert main(['configure','--project',rid,'--max-output-tokens','70000','--dry-run'],client=api)==0;capsys.readouterr();assert cfg.read_bytes()==before
 assert c.put(f'/api/projects/{rid}/config',json={'max_tokens':210000}).status_code==400
 assert cfg.read_bytes()==before
 assert c.put(f'/api/projects/{rid}/config',json={'extra_body':{'messages':[]}}).status_code==400
 assert c.put(f'/api/projects/{rid}/config',json={'model_profiles':{'other':{'api_key':'x'}}}).status_code==400
 assert c.put(f'/api/projects/{rid}/config',json={'model_profiles':{'other':{'token_budget_ledger':'fresh'}}}).status_code==400


def test_model_profile_thinking_and_effective_task_overrides_are_visible(tmp_path):
 c,rid=setup(tmp_path)
 result=c.put(f'/api/projects/{rid}/config',json={'task_models':{'fused-ssd':'other'},'model_profiles':{'other':{'max_tokens':80000,'thinking':False,'thinking_api':'enable_thinking','max_tokens_parameter':'max_completion_tokens','supports_tool_choice':False}}})
 assert result.status_code==200,result.text
 v=c.get(f'/api/projects/{rid}/config?task=fused-ssd').json();assert v['model']=='other'
 assert v['request_parameters']['max_completion_tokens']==80000 and not v['request_parameters']['enable_thinking']
 assert c.get(f'/api/projects/{rid}/config?task_key=unknown').status_code==400


def test_diagnostics_keeps_original_failure_and_validation_reason_without_secret(tmp_path,capsys):
 c,rid=setup(tmp_path);root=tmp_path/rid/'run'
 write_json(root/'workflow_tasks.json',{'tasks':{'x':{'stage':'api-map','status':'awaiting_configuration','failure':{'failure_category':'output_truncated','finish_reason':'length','usage':{'completion_tokens':12000}}}}})
 from scene_completion.execution_events import EventStore
 EventStore(root).append('artifact_io_failed',task_key='x',diagnostic={'failure_category':'artifact_io_error','path':'very-long-path.tmp'})
 write_json(root/'agent_rejections/a.json',{'node_key':'x','error':'payload schema failed; secret-fixture-key','payload':{'private':'not returned'}})
 assert main(['diagnose','--project',rid,'--node','x'],client=FakeAPI(c))==0
 v=capsys.readouterr().out;assert 'output_truncated' in v and 'artifact_io_error' in v and 'secret-fixture-key' not in v and 'not returned' not in v
 assert json.loads(v)['llm_called'] is False


def test_thinking_tools_replay_only_in_memory_and_omit_unsupported_tool_choice(tmp_path):
 from scene_completion.contracts import packet
 calls=[]
 def transport(url,key,body,*args):
  calls.append(deepcopy(body));assert 'tool_choice' not in body and 'parallel_tool_calls' not in body
  if len(calls)==1:
   return {'model':'actual','choices':[{'finish_reason':'tool_calls','message':{'content':'','reasoning_content':'PRIVATE_EPHEMERAL_THOUGHT','tool_calls':[{'id':'one','type':'function','function':{'name':'write_todos','arguments':'{"todos":[]}'}}]}}],'usage':{'total_tokens':20}}
  assert any(m.get('reasoning_content')=='PRIVATE_EPHEMERAL_THOUGHT' for m in body['messages'])
  return {'model':'actual','choices':[{'finish_reason':'tool_calls','message':{'content':'','reasoning_content':'PRIVATE_SECOND','tool_calls':[{'id':'two','type':'function','function':{'name':'submit_result','arguments':'{"payload":{"services":[]}}'}}]}}],'usage':{'total_tokens':22}}
 config={'base_url':'http://fixture/v1','api_key':'test','agent_model':'thinking','run_root':str(tmp_path),'thinking':True,'send_reasoning_effort':False,'reasoning_replay':True,'supports_tool_choice':False,'supports_parallel_tool_calls':False,'submission_mode':'tool_calls'}
 p=packet('api-map',{'SR':[]});p['skill_text']='Use supplied task.'
 out=DeepAgentsClient(config,transport=transport).agent(p)
 assert out['services']==[] and len(calls)==2
 assert 'PRIVATE_EPHEMERAL_THOUGHT' not in ''.join(f.read_text() for f in tmp_path.rglob('*.json'))


def test_invalid_json_is_distinct_from_truncation_and_usage_is_retained(tmp_path):
 from langchain_core.messages import HumanMessage
 from scene_completion.scheduler import TaskBlocked
 def response(reason):
  return lambda *args:{'model':'actual','choices':[{'finish_reason':reason,'message':{'content':'{bad','reasoning_content':'not persisted'}}],'usage':{'completion_tokens':123,'completion_tokens_details':{'reasoning_tokens':120}}}
 c=DeepAgentsClient({'base_url':'http://fixture/v1','api_key':'x','agent_model':'x','max_tokens':1000,'submission_mode':'json_text','run_root':str(tmp_path)},transport=response('length'))
 m=_transport_model(c,'api-map');tools=[{'type':'function','function':{'name':'submit_result','parameters':{'type':'object','properties':{'payload':{'type':'object'}}}}}]
 with pytest.raises(TaskBlocked) as failure:m._generate([HumanMessage(content='json')],tools=tools)
 assert failure.value.details['finish_reason']=='length' and failure.value.details['usage']['completion_tokens_details']['reasoning_tokens']==120
 c.transport=response('stop')
 with pytest.raises(ValueError) as invalid:_transport_model(c,'api-map')._generate([HumanMessage(content='json')],tools=tools)
 assert invalid.value.response_diagnostic['failure_category']=='invalid_result_json' and invalid.value.response_diagnostic['json_line']==1


def test_short_atomic_temporary_names_and_windows_path_forms(tmp_path,monkeypatch):
 import scene_completion.storage as storage
 names=[];original=storage.os.replace
 def replace(src,dst):names.append(Path(src).name);return original(src,dst)
 monkeypatch.setattr(storage.os,'replace',replace)
 p=tmp_path/('a'*110)/('b'*110)/('c'*100+'.json');write_json(p,{'ok':1});assert read_json(p)=={'ok':1}
 assert len(names[0])<30 and not list(p.parent.glob('*.tmp'))
 assert windows_extended_path('C:\\long\\file.json')=='\\\\?\\C:\\long\\file.json'
 assert windows_extended_path('\\\\host\\share\\file.json')=='\\\\?\\UNC\\host\\share\\file.json'


def test_audit_write_failure_does_not_hide_original_model_error(tmp_path,monkeypatch):
 from scene_completion.contracts import packet
 import scene_completion.deepagents_client as module
 old=module.write_json
 def fail_history(path,value):
  if Path(path).parent.name=='agent_trace_history':raise FileNotFoundError('audit path fixture')
  return old(path,value)
 monkeypatch.setattr(module,'write_json',fail_history)
 def transport(*args):raise RuntimeError('ORIGINAL_MODEL_ERROR')
 c=DeepAgentsClient({'base_url':'http://fixture/v1','api_key':'x','agent_model':'x','run_root':str(tmp_path)},transport=transport)
 p=packet('api-map',{'SR':[]});p['skill_text']='fixture'
 with pytest.raises(RuntimeError,match='ORIGINAL_MODEL_ERROR'):c.agent(p)


def test_routed_model_uses_own_transport_runtime_options(tmp_path,monkeypatch):
 import scene_completion.model_client as module
 from scene_completion.contracts import packet
 requests=[]
 def post(url,key,body,timeout,retries,**options):
  requests.append((body,options))
  return {'model':'other','usage':{'total_tokens':5},'choices':[{'finish_reason':'tool_calls','message':{'content':'','tool_calls':[{'id':'x','type':'function','function':{'name':'submit_result','arguments':'{"payload":{"services":[]}}'}}]}}]}
 monkeypatch.setattr(module,'_post_chat_completions',post)
 config={'base_url':'http://fixture/v1','api_key':'x','agent_model':'base','run_root':str(tmp_path),'task_models':{'api-map':'other'},'model_profiles':{'other':{'reasoning_replay':True,'stream_total_timeout_seconds':1800,'stream':True}}}
 p=packet('api-map',{'SR':[]});p['skill_text']='fixture'
 assert DeepAgentsClient(config).agent(p)['services']==[]
 assert requests[0][1]['capture_reasoning'] is True and requests[0][1]['total_timeout']==1800


def test_output_parameter_alias_is_used_by_context_and_quota_bounds():
 from scene_completion.context_budget import check
 from scene_completion.token_budget import request_reservation
 body=request_options({'messages':[{'role':'user','content':'json'}],'max_tokens':400}, {'max_tokens_parameter':'max_completion_tokens'})
 assert 'max_tokens' not in body and body['max_completion_tokens']==400
 assert check(body,{'max_context_tokens':2000})['output_reserve']==400 and request_reservation(body)>=400
