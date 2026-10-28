"""Runtime routing never changes an already verified business artifact."""
from copy import deepcopy
import pytest
from scene_completion.throughput import Monitor,SlowStream
from scene_completion.model_resilience import validate,invoke,select,fresh,mark_degraded,cooling
from scene_completion.scheduler import TaskRejected,TaskBlocked,Scheduler,Task
from scene_completion.storage import read_json,write_json
from scene_completion.model_client import SemanticClient
from scene_completion.workflow import Execution


def test_rate_monitor_grace_reasoning_and_consecutive_windows():
 clock=[0.];policy=validate({'enabled':True,'grace_seconds':10,'window_seconds':5,'low_windows':2,'no_output_seconds':100})
 m=Monitor(lambda:policy,clock=lambda:clock[0]);total=0
 for t in range(1,11):clock[0]=t;total+=100;m.observe(total)
 # Generated reasoning bytes count as activity; heartbeats alone do not.
 for t in range(11,21):
  clock[0]=t
  if t<20:m.observe(total)
  else:
   with pytest.raises(SlowStream) as e:m.observe(total)
 assert e.value.response_diagnostic['reason']=='sustained_low_throughput'


def test_stall_threshold_can_be_changed_in_flight_and_disabled():
 clock=[0.];p=validate({'enabled':False,'no_output_seconds':10,'grace_seconds':0,'min_tokens_per_second':0})
 m=Monitor(lambda:p,clock=lambda:clock[0]);clock[0]=100;m.observe(0)
 p['enabled']=True
 with pytest.raises(SlowStream,match='cancelled'):m.timeout()


def test_fallback_is_explicit_bounded_and_preserves_packet_and_credentials(tmp_path):
 c=SemanticClient({'base_url':'http://offline.invalid','agent_model':'a','allowed_models':['a','b'],'run_root':str(tmp_path),'resilience':{'enabled':True,'candidates':[{'model':'b'}]}});c.api_key='test-only'
 seen=[];packet={'task':'components','input':{'RR':[],'SR':[]}}
 def call(child):
  seen.append(child.model('agent'));assert child.api_key=='test-only'
  if len(seen)==1:raise SlowStream({'output_bytes':0})
  return {'model':child.model('agent')}
 assert invoke(c,packet,call)=={'model':'b'} and seen==['a','b']
 assert packet=={'task':'components','input':{'RR':[],'SR':[]}}
 assert cooling({**c.config,'agent_model':'a'})
 assert not cooling({**c.config,'agent_model':'b'})


@pytest.mark.parametrize('category',['transport_timeout','stream_incomplete','authentication_failed','quota_exhausted'])
def test_unknown_post_and_auth_are_not_blindly_replayed(category):
 c=SemanticClient({'agent_model':'a','resilience':{'enabled':True,'candidates':[{'model':'b'}]}});seen=[]
 def call(child):
  seen.append(1);e=RuntimeError('failed');e.response_diagnostic={'failure_category':category};raise e
 with pytest.raises(RuntimeError):invoke(c,{'task':'components'},call)
 assert len(seen)==1


def test_model_switch_obeys_allowlist_and_independent_ledger():
 with pytest.raises(ValueError,match='allowed'):select({'agent_model':'a','allowed_models':['a']},{'model':'b'})
 with pytest.raises(ValueError,match='ledger'):select({'agent_model':'a','token_budget_limit':900000},{'model':'b'})


def test_future_calls_read_changed_project_config(tmp_path):
 project=tmp_path/'p';project.mkdir();env=tmp_path/'.env';env.write_text('SCENE_API_KEY=test')
 write_json(project/'model.local.json',{'agent_model':'b','base_url':'http://gateway'})
 old={'_live_project':str(project),'_live_env_file':str(env),'_live_accounts_root':str(tmp_path),'agent_model':'a','run_root':'fixed-run'}
 assert fresh(old)['agent_model']=='b' and fresh(old)['run_root']=='fixed-run'


def test_passed_artifact_reused_after_model_output_and_concurrency_changes(tmp_path):
 calls=[]
 def mock(p):calls.append(1);return {'components':[],'relations':[]}
 for config in ({'agent_model':'a','max_tokens':12000,'max_concurrency':1},{'agent_model':'b','max_tokens':32000,'max_concurrency':3}):
  ex=Execution(tmp_path/'run',mocks={'components':mock},config=config);ex.add('components','components',static={'RR':[],'SR':[]});assert ex.scheduler.run()['complete']
 assert len(calls)==1
 # Changed actual source data is still not reusable.
 ex=Execution(tmp_path/'run',mocks={'components':mock},config=config);ex.add('components','components',static={'RR':[{'source_id':'s','name':'r','channel':'normal','lines':[]}],'SR':[]})
 ex.scheduler.run();assert len(calls)>1
 assert ex.scheduler.state['tasks']['components']['status']=='rejected'  # Changed input cannot reuse empty old result.


def test_changed_provider_reopens_only_failed_attempt_window(tmp_path):
 s=Scheduler(tmp_path,max_rounds=0);t=Task('x','shared','components',(),version=1,execute=lambda d,r:(_ for _ in ()).throw(TaskRejected({'error':'bad'})))
 t.attempt_identity='a';s.add(t);s.run();assert s.state['tasks']['x']['status']=='rejected'
 s=Scheduler(tmp_path,max_rounds=0);t=Task('x','shared','components',(),version=1,execute=lambda d,r:{'ok':True});t.attempt_identity='b';s.add(t)
 assert s.run()['complete'];assert len(s.state['tasks']['x']['attempt_windows'])==1


def test_exact_previous_release_cache_can_be_rebound_but_not_unknown_logic(tmp_path):
 from scene_completion.storage import fingerprint
 calls=[]
 def mock(p):calls.append(1);return {'components':[],'relations':[]}
 run=tmp_path/'run';ex=Execution(run,mocks={'components':mock});ex.add('components','components',static={'RR':[],'SR':[]});assert ex.scheduler.run()['complete']
 task=ex.scheduler.tasks['components'];proof=read_json(__import__('pathlib').Path(__import__('scene_completion.workflow',fromlist=['x']).__file__).with_name('cache_migrations_2aee6cc.json'))['tasks']['components']
 manifest=read_json(run/'run_manifest.json');manifest.pop('artifact_cache_contract',None);manifest['execution_identity']={'mode':'mock','model':'legacy','config_hash':'old','endpoint_hash':'old'};write_json(run/'run_manifest.json',manifest)
 state=read_json(run/'workflow_tasks.json');record=state['tasks']['components'];old=deepcopy(task.version)
 for k in ('cache_contract','imports'):old.pop(k,None)
 old.update(code=proof['legacy_code'],identity=manifest['execution_identity'],cases=[])
 record.pop('version');record['identity']=fingerprint({'version':old,'dependencies':{}});write_json(run/'workflow_tasks.json',state)
 ex=Execution(run,mocks={'components':mock});ex.add('components','components',static={'RR':[],'SR':[]});assert ex.scheduler.run()['complete']
 assert calls==[1] and ex.scheduler.state['tasks']['components']['cache_migrations']
 # A forged/unknown implementation proof is not accepted as the old version.
 state=read_json(run/'workflow_tasks.json');state['tasks']['components'].pop('version');state['tasks']['components']['identity']='unknown';write_json(run/'workflow_tasks.json',state)
 ex=Execution(run,mocks={'components':mock});ex.add('components','components',static={'RR':[],'SR':[]});ex.scheduler.run()
 assert not ex.scheduler.state['tasks']['components'].get('cache_migrations')


def test_explicit_cross_account_selection_does_not_reuse_key_or_budget(tmp_path):
 from scene_completion.model_accounts import save_account
 save_account(tmp_path,{'expected_revision':0,'id':'b','name':'B','base_url':'http://b/v1','models':['model-b'],'api_key':'key-b'},tmp_path/'.env')
 cfg={'agent_model':'model-a','model_account_id':'a','api_key':'key-a','base_url':'http://a','_live_accounts_root':str(tmp_path),'_live_env_file':str(tmp_path/'.env')}
 value=select(cfg,{'account_id':'b','model':'model-b'})
 assert value['api_key']=='key-b' and value['base_url']=='http://b/v1' and value['allowed_models']==['model-b']
 with pytest.raises(ValueError,match='独立额度'):select({**cfg,'token_budget_limit':900000,'token_budget_ledger':'old'}, {'account_id':'b','model':'model-b'})


def test_live_edit_during_failed_call_changes_next_candidate(tmp_path):
 project=tmp_path/'p';project.mkdir();env=tmp_path/'.env';env.write_text('SCENE_API_KEY=test')
 cfg={'agent_model':'a','base_url':'http://offline','resilience':{'enabled':True,'candidates':[{'model':'b'}],'cooldown_seconds':0}}
 write_json(project/'model.local.json',cfg)
 c=SemanticClient({**cfg,'_live_project':str(project),'_live_env_file':str(env),'_live_accounts_root':str(tmp_path)})
 seen=[]
 def call(child):
  seen.append(child.model('agent'))
  if len(seen)==1:
   write_json(project/'model.local.json',{**cfg,'resilience':{'enabled':True,'candidates':[{'model':'c'}],'cooldown_seconds':0}})
   raise SlowStream({})
  return 'done'
 assert invoke(c,{'task':'components'},call)=='done' and seen==['a','c']


def test_live_primary_changes_still_obey_maximum_switch_count(tmp_path):
 project=tmp_path/'p';project.mkdir();env=tmp_path/'.env';env.write_text('SCENE_API_KEY=test')
 cfg={'agent_model':'a','base_url':'http://offline','resilience':{'enabled':True,'max_switches':1,'cooldown_seconds':0}}
 write_json(project/'model.local.json',cfg)
 c=SemanticClient({**cfg,'_live_project':str(project),'_live_env_file':str(env),'_live_accounts_root':str(tmp_path)})
 seen=[]
 def call(child):
  seen.append(child.model('agent'))
  write_json(project/'model.local.json',{**cfg,'agent_model':chr(ord('a')+len(seen))})
  raise SlowStream({})
 with pytest.raises(SlowStream):invoke(c,{'task':'components'},call)
 assert seen==['a','b']
