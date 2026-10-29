from pathlib import Path
import json,sys
import pytest
from fastapi.testclient import TestClient
from scene_completion.workbench import Workbench,create_app
from scene_completion.manager_store import Journal,settings
from scene_completion.manager_agent import execute_action,run_turn,model_config
from scene_completion.storage import write_json,fingerprint,read_json

def project(tmp_path):
 s=Workbench(tmp_path);p=s.create({'name':'项目','sources':{'RR':[{'name':'rr.md','content':'# UC-001 浏览商品\n顾客查询商品'}],'SR':[{'name':'sr.md','content':'# SR-01 浏览商品\nCatalog查询列表'}]}})
 return s,p['id'],s.run_dir(p['id'])

def test_recovered_colleague_formats_keep_all_types_and_file_trace(tmp_path):
 from scene_completion.test_sources import preview
 from scene_completion.artifact_imports import receive,view
 text='# 测试逆向恢复\n### UC-001：浏览商品列表\n2. 前置条件：\n 已进入页面\n5. 主成功路径：〔SC@SPEC-005〕\n ① 查询\n6. 扩展路径：\n - exception〔SC@SPEC-006〕非法分页：条件为page<1；HTTP 400。\n - alternative_success〔SC@SPEC-008〕无匹配：total=0。\n - undetermined〔SC@SPEC-011〕字段为空：处理待确认。'
 result=receive(tmp_path,[{'name':'unknown.md','content':text}]);row=view(tmp_path,result['received'][0]['id'])
 assert row['role']=='test' and row['test_preview']['counts']=={'exception':1,'normal':2,'pending':1,'optional':0}
 assert row['artifacts']==[] and 'test-case-align' in row['target_nodes']
 from scene_completion.input_gateway import accept_source
 s,rid,p=project(tmp_path/'work')
 result=receive(p,[{'name':'unknown.md','content':text}]);row=view(p,result['received'][0]['id'])
 accept_source(s,p,row,{'expected_revision':0})
 assert s.test_sources(rid)['preview']['counts']['exception']==1
 assert read_json(p/'project.json')['sources']['test'][0]['path']==row['original']


def test_actual_customer_file_if_available():
 from scene_completion.test_sources import preview
 file=Path('/Users/yangkailiang/Downloads/recovered_usecases.md')
 if not file.exists():pytest.skip('客户验收样本仅留本机，不随程序包上传')
 v=preview([{'source_id':'original','name':file.name,'channel':'test','lines':[{'number':n,'text':s} for n,s in enumerate(file.read_text(encoding='utf-8-sig').splitlines(),1)]}])
 assert v['valid'] and len(v['records'])==39 and len({r['id'] for r in v['records']})==39
 assert v['counts']=={'exception':13,'normal':12,'pending':14,'optional':0}


def test_journal_versions_and_new_session_do_not_erase_memory(tmp_path):
 j=Journal(tmp_path);j.append('user','查询进展');m=j.memory({'category':'decision','text':'只跑首例','expected_revision':0})
 j.new_session();assert j.messages()==[] and j.memory()[0]['text']=='只跑首例'
 j.memory({'id':m['id'] if 'id' in m else j.memory()[0]['id'],'expected_revision':1,'category':'decision','text':'暂停','active':False})
 assert len(j.objects('memory-history'))==1
 with pytest.raises(ValueError):settings(tmp_path,{'expected_revision':0,'settings':{'mode':'unknown'}})


def test_manager_actions_refuse_credentials_traversal_and_cross_project(tmp_path):
 s,rid,p=project(tmp_path)
 (p/'secret.local.json').write_text('{"api_key":"secret"}')
 with pytest.raises(ValueError):execute_action(s,rid,'read_file',{'path':'secret.local.json'})
 with pytest.raises(ValueError):execute_action(s,rid,'read_file',{'path':'../other.json'})
 with pytest.raises(ValueError):execute_action(s,rid,'configure_pipeline',{'api_key':'bad'})
 with pytest.raises(ValueError):execute_action(s,rid,'cli',{'command':'status','arguments':['--project','other']})
 with pytest.raises(ValueError):execute_action(s,rid,'start',{})
 assert execute_action(s,rid,'ask_user',{'question':'规则？'})['awaiting_user']
 settings(p,{'expected_revision':0,'settings':{'mode':'auto'}})
 assert execute_action(s,rid,'ask_user',{'question':'规则？'})['deferred']


def test_manager_deepagents_can_use_tools_and_persist_chat(tmp_path):
 from scene_completion.model_client import SemanticClient
 s,rid,p=project(tmp_path)
 calls=[]
 def transport(url,key,body,timeout,retries):
  calls.append(body)
  message={'role':'assistant','content':'当前0个节点，我已记录下一步。'}
  if len(calls)==1:message={'role':'assistant','content':'','tool_calls':[{'id':'op1','type':'function','function':{'name':'project_operation','arguments':json.dumps({'action':'plan','arguments':{'items':[{'task':'提取共享产物','status':'pending'}]}})}}]}
  return {'model':'test','choices':[{'message':message,'finish_reason':'tool_calls' if len(calls)==1 else 'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}}
 s.client_factory=lambda cfg,root:SemanticClient(cfg,transport)
 write_json(p/'model.local.json',{'agent_model':'test','base_url':'http://fake','api_key':'test-only','stream':False})
 Journal(p).append('user','请制定计划')
 run_turn(s,rid)
 j=Journal(p)
 assert j.get('plan')['items'][0]['status']=='pending'
 assert j.messages()[-1]['kind']=='assistant'
 assert j.get('checkpoint',j.session()['id'])['messages']
 assert j.objects('operation')[0]['status']=='completed'
 assert len(calls)==2 and 'project_operation' in str(calls[0]['tools'])


def test_trial_never_changes_formal_project_or_tests(tmp_path):
 s,rid,p=project(tmp_path);before=read_json(p/'project.json')
 v=execute_action(s,rid,'trial',{'node':'G-001:normal-rules','assumption':'page>=1','basis':'通用分页假设，待确认'})
 assert not v['formal'] and read_json(p/'project.json')==before
 trial=read_json(s.run_dir(v['project_id'])/'project.json')
 assert trial['manager_trial']['parent']==rid and trial['sources']['test']==[]
 assert execute_action(s,rid,'trial',{'node':'G-001:normal-rules','assumption':'page>=1','basis':'通用分页假设，待确认'})['project_id']==v['project_id']


def test_telemetry_does_not_export_prompt_or_reasoning(tmp_path):
 from scene_completion.execution_events import EventStore
 from scene_completion.throughput_view import series,csv_export
 store=EventStore(tmp_path/'run');store.append('throughput_sample',task_key='a',requested_model='model',output_bytes=40,tokens_per_second_estimate=2,api_key='SECRET',reasoning_content='private')
 v=series(tmp_path);assert len(v['points'])==1 and 'SECRET' not in json.dumps(v) and 'private' not in csv_export(v)


def test_patch_hash_frozen_tests_and_safe_apply(tmp_path,monkeypatch):
 from scene_completion import manager_patches as m
 program=tmp_path/'app';f=program/'.cac/tools/scene_completion/example.py';f.parent.mkdir(parents=True);f.write_text('value = 1\n');(program/'tests').mkdir();(program/'tests/test_x.py').write_text('def test_x(): assert True\n')
 p=tmp_path/'p';settings(p,{'expected_revision':0,'settings':{'mode':'auto'}})
 row=m.propose(p,program,{'reason':'修复边界','changes':[{'path':f.relative_to(program).as_posix(),'expected_hash':fingerprint(f.read_text()),'content':'value = 2\n'}]})
 def fake_run(*a,**kw):
  assert (Path(kw['cwd'])/'tests/test_x.py').read_text()=='def test_x(): assert True\n'
  return type('R',(),{'returncode':0,'stdout':'1 passed'})()
 monkeypatch.setattr(m.subprocess,'run',fake_run)
 assert m.test_patch(p,program,row['id'])['status']=='tested'
 assert m.apply(p,program,row['id'],[])['status']=='applied' and f.read_text()=='value = 2\n'
 assert m.apply(p,program,row['id'],[],rollback=True)['status']=='rolled_back' and f.read_text()=='value = 1\n'
 with pytest.raises(ValueError):m.allowed_program(program,'.cac/tools/scene_completion/token_budget.py')


def test_manager_api_review_mode_and_idempotent_actions(tmp_path):
 s,rid,p=project(tmp_path);client=TestClient(create_app(tmp_path))
 data=client.get(f'/api/projects/{rid}/manager').json();assert data['configuration']['settings']['mode']=='collaborative'
 args={'action':'memory','request_id':'once','arguments':{'text':'业务决定','category':'decision','expected_revision':0}}
 assert client.post(f'/api/projects/{rid}/manager/actions',json=args).status_code==200
 assert client.post(f'/api/projects/{rid}/manager/actions',json=args).status_code==200
 assert len(Journal(p).memory())==1
 write_json(tmp_path/'.review-mode.json',{})
 assert TestClient(create_app(tmp_path)).post(f'/api/projects/{rid}/manager/run',json={}).status_code==403


def test_normal_progress_does_not_trigger_another_model_turn(tmp_path):
 from scene_completion.manager_runtime import signature
 s,rid,p=project(tmp_path)
 before=signature(s,rid)
 # Counters change but normal successful work is handled by the program watcher.
 original=s.execution_status
 s.execution_status=lambda rid:{**original(rid),'completed':5,'total':20,'pending_nodes':[{'id':'next','status':'pending'}]}
 assert signature(s,rid)==before
 s.execution_status=lambda rid:{**original(rid),'pending_nodes':[{'id':'bad','status':'failed','failure':{'type':'TypeError'}}]}
 assert signature(s,rid)!=before


def test_recovered_number_collision_does_not_bypass_case_semantics():
 from scene_completion.test_alignment import exact_alignment
 value={'test-inventory':{'cases':[{'id':'t','association':'UC-001：支付订单','source_refs':[]}]},'case-groups':{'groups':[{'id':'g','rr_ids':['UC-001'],'sr_ids':['SR-1'],'status':'confirmed'}]},'rr-cases':{'cases':[{'id':'UC-001','name':'浏览商品'}]},'sr-cases':{'cases':[{'id':'SR-1','name':'浏览商品'}]}}
 assert exact_alignment(value) is None


def test_manager_context_compression_keeps_history_and_versions(tmp_path):
 from scene_completion.manager_agent import compact_history
 j=Journal(tmp_path)
 for i in range(14):j.append('user','消息'+str(i)+('汉字'*400))
 cfg={'max_context_tokens':6000,'max_tokens':256,'agent_model':'test','stream':False}
 class Client:
  def model(self,x):return 'test'
  def output_limit(self,x):return 256
  def post(self,endpoint,body):return {'choices':[{'message':{'content':'用户决定：仅首例；未完成：用例对应。文件引用保持。'}}],'usage':{'total_tokens':30}}
 # Reduce threshold without mutating messages; old chat remains saved.
 settings(tmp_path,{'expected_revision':0,'settings':{'compression_ratio':.2}})
 system,messages=compact_history(j,cfg,Client())
 assert len(j.messages())==14 and 1<=len(messages)<=6 and j.get('summary',j.session()['id'])['through']>0
 assert '仅首例' in system


def test_test_source_change_preserves_eligible_positive_seed(tmp_path):
 from scene_completion.workflow import Execution,build_pipeline
 from scene_completion.positive_reuse import prepare
 s,rid,old=project(tmp_path/'work')
 # The real source-change precondition, including a different independent test set.
 new=s.create({'name':'新测试','sources':{'RR':[{'name':'rr.md','content':'# UC-001 浏览商品\n顾客查询商品'}],'SR':[{'name':'sr.md','content':'# SR-01 浏览商品\nCatalog查询列表'}],'test':[{'name':'new.md','content':'# 独立测试'}]}})
 target=s.run_dir(new['id']);prepare(old,target)
 assert (target/'run/positive_reuse.json').exists()
 assert read_json(target/'run/positive_reuse.json')['policy'].startswith('unchanged')


def test_isolated_patch_runs_real_frozen_test_suite(tmp_path):
 from scene_completion.manager_patches import propose,test_patch
 app=tmp_path/'app';f=app/'.cac/tools/scene_completion/example.py';f.parent.mkdir(parents=True);f.write_text('value = 1\n');(f.parent/'__init__.py').write_text('')
 (app/'tests').mkdir();(app/'tests/test_example.py').write_text('from scene_completion.example import value\ndef test_value(): assert value == 2\n')
 row=propose(tmp_path/'project',app,{'reason':'修复示例边界','changes':[{'path':f.relative_to(app).as_posix(),'expected_hash':fingerprint(f.read_text()),'content':'value = 2\n'}]})
 result=test_patch(tmp_path/'project',app,row['id'])
 assert result['status']=='tested' and '1 passed' in result['test']['summary']
 assert f.read_text()=='value = 1\n'  # Validation never changes the live application.


def test_alignment_context_excludes_branches_and_preserves_case_identity():
 from scene_completion.test_alignment import alignment_context
 value={'rr-cases':{'cases':[{'id':'r','name':'浏览','goal':'列表','actors':['人'],'source_refs':[{'quote':'长步骤'*1000}]}]},'sr-cases':{'cases':[{'id':'s','name':'查询'}]},'case-groups':{'groups':[{'id':'g','rr_ids':['r'],'sr_ids':['s'],'status':'confirmed','source_refs':[{'quote':'长步骤'*1000}]}]},'test-inventory':{'cases':[{'id':'test','name':'浏览列表','source_refs':[{'quote':'测试自己的正常目标'}]}],'tests':[{'id':'exception-answer'}]}}
 compact=alignment_context(value)
 assert compact['rr-cases']['cases'][0]['name']=='浏览' and compact['test-inventory']['cases'][0]['source_refs']
 assert 'exception-answer' not in json.dumps(compact) and len(json.dumps(compact))<len(json.dumps(value))/10


def test_history_paginates_more_than_500_without_losing_decisions(tmp_path):
 j=Journal(tmp_path)
 for i in range(530):j.append('user','决定-'+str(i))
 assert len(list(j.history()))==530
 first=j.messages(limit=30,ascending=True)
 assert first[0]['content']=='决定-0' and j.messages(before=first[-1]['id'],limit=5)[-1]['id']==first[-1]['id']-1
 assert [r['id'] for r in j.history(after=500)]==list(range(501,531))


def test_pending_patch_reconciles_without_another_chat(tmp_path,monkeypatch):
 from scene_completion import manager_patches as patches,manager_runtime as runtime,manager_agent
 s,rid,p=project(tmp_path/'data');program=tmp_path/'program';f=program/'.cac/tools/scene_completion/business.py';f.parent.mkdir(parents=True);f.write_text('value=1\n')
 settings(p,{'expected_revision':0,'settings':{'mode':'auto'}})
 row=patches.propose(p,program,{'reason':'boundary fix','changes':[{'path':f.relative_to(program).as_posix(),'expected_hash':fingerprint(f.read_text()),'content':'value=2\n'}]})
 j=Journal(p);j.put('patch',{**row,'status':'tested','test':{'passed':True}},row['id'])
 write_json(p/'job.json',{'status':'running'})
 assert patches.apply(p,program,row['id'],[p])['status']=='waiting_safe_boundary'
 assert j.get('activation',row['id'])['status']=='waiting_safe_boundary' and f.read_text()=='value=1\n'
 write_json(p/'job.json',{'status':'completed'});called=[]
 monkeypatch.setattr(manager_agent,'PROGRAM',program)
 monkeypatch.setattr(runtime,'launch_restart',lambda *a,**kw:called.append(a))
 runtime.reconcile_activations(s,rid)
 assert f.read_text()=='value=2\n' and len(called)==1
 # Simulate durable handoff from restart launcher. It must not apply twice.
 j.put('activation',{'status':'restarting','patch_id':row['id']},row['id'])
 runtime.reconcile_activations(s,rid);assert len(called)==1


def test_restart_timeout_terminates_then_kills_child():
 from scene_completion.manager_restart import stop_child
 import subprocess
 class Process:
  def __init__(self):self.actions=[]
  def poll(self):return None
  def terminate(self):self.actions.append('terminate')
  def wait(self,timeout):
   self.actions.append('wait')
   if 'kill' not in self.actions:raise subprocess.TimeoutExpired('server',timeout)
  def kill(self):self.actions.append('kill')
 p=Process();stop_child(p);assert p.actions==['terminate','wait','kill','wait']


def test_auto_questions_persist_and_trial_assumption_is_not_a_source(tmp_path):
 s,rid,p=project(tmp_path);settings(p,{'expected_revision':0,'settings':{'mode':'auto'}})
 execute_action(s,rid,'ask_user',{'question':'categoryId如何校验？','scope':['G-001:normal-rules']})
 assert Journal(p).messages()[-1]['kind']=='question'
 v=execute_action(s,rid,'trial',{'node':'G-001:normal-rules','assumption':'page>=1','basis':'待确认'})
 trial=s.run_dir(v['project_id']);before=read_json(p/'project.json');after=read_json(trial/'project.json')
 assert [(x['name']) for x in before['sources']['RR']]==[x['name'] for x in after['sources']['RR']]
 from scene_completion.node_conversations import Conversations
 assert Conversations(trial/'run').revision('G-001:normal-rules')==1
 assert Conversations(trial/'run').list('G-001:test-concerns')==[]
 with pytest.raises(ValueError):execute_action(s,rid,'trial',{'node':'G-001:test-concerns','assumption':'答案','basis':'推测'})


def test_patch_removes_old_same_size_bytecode(tmp_path):
 from scene_completion.manager_patches import propose,apply
 import py_compile
 program=tmp_path/'app';f=program/'.cac/tools/scene_completion/business.py';f.parent.mkdir(parents=True);f.write_text('value=1\n')
 cached=Path(py_compile.compile(str(f),doraise=True));assert cached.exists()
 p=tmp_path/'project';settings(p,{'expected_revision':0,'settings':{'mode':'auto'}})
 row=propose(p,program,{'reason':'same size bytecode regression','changes':[{'path':f.relative_to(program).as_posix(),'expected_hash':fingerprint(f.read_text()),'content':'value=2\n'}]})
 Journal(p).put('patch',{**row,'status':'tested','test':{'passed':True}},row['id'])
 apply(p,program,row['id'],[]);assert not cached.exists()


def test_test_capability_context_does_not_include_recovered_exception_answers():
 from scene_completion.task_context import semantic_view
 from scene_completion.test_sources import records
 text='### UC-001：浏览列表\n5. 主成功路径：〔SC@SPEC-001〕\n ① 用户查询列表\n6. 扩展路径：\n - exception〔SC@SPEC-002〕字段缺失：HTTP 400 SECRET_ANSWER\n - alternative_success〔SC@SPEC-003〕空结果：返回空列表'
 doc={'source_id':'t','channel':'test','name':'test.md','lines':[{'number':i,'text':s} for i,s in enumerate(text.splitlines(),1)]}
 out=semantic_view('test-operation-project',{'test-operation-source':[doc]})
 assert 'SECRET_ANSWER' not in str(out) and '用户查询列表' in str(out)
 assert len(records([doc]))==3
