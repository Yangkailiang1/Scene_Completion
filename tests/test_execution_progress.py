"""Live telemetry never conflates billing, orphan requests, or human wait with ETA."""
import json
import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from scene_completion.execution_progress import estimate,snapshot
from scene_completion.execution_events import EventStore,bind
from scene_completion.storage import write_json
from scene_completion.workbench import create_app
from scene_completion.throughput import Monitor,SlowStream
from scene_completion.model_resilience import invoke
from scene_completion.model_client import SemanticClient
from scene_completion.throughput_view import series


def graph():
 return [{'id':'done-a','stage':'a','deps':[]},{'id':'done-b','stage':'b','deps':[]},
         {'id':'a','stage':'a','deps':[]},{'id':'b','stage':'a','deps':[]},{'id':'c','stage':'b','deps':['a','b']}]


def records():
 return {'done-a':{'stage':'a','status':'passed','started_at':100,'finished_at':110},'done-b':{'stage':'b','status':'passed','started_at':100,'finished_at':120}}


def test_eta_schedules_actual_parallel_dependencies_instead_of_percentage():
 e=estimate(graph(),records(),now=200,concurrency=2,running=True)
 assert e['seconds']==30 and e['finish_at']==230 and e['remaining_nodes']==3
 assert e['sample_count']==2 and e['confidence']=='low'
 assert estimate(graph(),records(),now=200,concurrency=1,running=True)['seconds']==40
 # Planned future nodes do not become measured work.
 assert estimate(graph()+[{'id':'fake','stage':'new','planned':True}],records(),now=200,concurrency=2,running=True)['seconds']==30


def test_eta_unknown_stage_blocking_and_discovery_never_fabricate_a_deadline():
 n=graph()+[{'id':'new','stage':'unseen','deps':[]}]
 e=estimate(n,records(),now=200,running=True);assert e['status']=='insufficient' and e['finish_at'] is None and e['unknown_nodes'][0]['id']=='new'
 r=records();r['a']={'status':'awaiting_review','stage':'a'}
 e=estimate(graph(),r,now=200,running=True)
 assert e['status']=='blocked' and e['finish_at'] is None and e['seconds'] is not None
 assert estimate(graph(),records(),now=200,running=False)['status']=='paused'
 r={k:{'status':'passed'} for k in ['a','b','c','done-a','done-b']}
 assert estimate(graph(),r,now=200,running=True)['status']=='discovering'
 assert estimate(graph(),r,now=200,complete=True)['seconds']==0


def test_eta_late_task_and_cycle_do_not_report_negative_or_completed():
 r=records();r['a']={'stage':'a','status':'running','started_at':150}
 e=estimate(graph(),r,now=200,concurrency=2,running=True)
 assert 'a' in e['late_nodes'] and e['seconds']>0
 n=graph();n[2]['deps']=['c']
 assert estimate(n,records(),now=200,running=True)['status']=='insufficient'
 n=graph();n[2]['deps']=['missing']
 assert estimate(n,records(),now=200,running=True)['finish_at'] is None


def setup_project(tmp_path):
 p=tmp_path/'p';run=p/'run';run.mkdir(parents=True)
 write_json(run/'workflow_graph.json',{'nodes':graph()})
 r=records();r['a']={'stage':'a','status':'running','started_at':190}
 write_json(run/'workflow_tasks.json',{'tasks':r})
 write_json(p/'job.json',{'status':'running','worker_heartbeat':200,'started_at':180})
 write_json(run/'execution_sessions.json',[{'started_at':180}])
 return p,EventStore(run)


def test_monitor_only_reports_current_active_request_and_never_exposes_prompt(tmp_path):
 p,store=setup_project(tmp_path)
 start=store.append('request_started',task_key='a',model_call_id='live',requested_model='fast',account_id='account',api_key='SECRET',request_parameters={'private':'prompt'})
 store.append('throughput_sample',task_key='a',model_call_id='live',tokens_per_second_estimate=1.5,output_bytes=600,content_bytes=400,tool_argument_bytes=200,reasoning_bytes=0,last_output_age_seconds=2)
 # Explicit times keep the exact stale/unknown boundary deterministic.
 with store.connect() as db:
  for row in db.execute('SELECT id,payload FROM events').fetchall():
   event=json.loads(row[1]);event['at']=190 if event['kind']=='request_started' else 198
   db.execute('UPDATE events SET at=?,payload=? WHERE id=?',(event['at'],json.dumps(event),row[0]))
 cfg={'max_concurrency':2,'resilience':{'enabled':True,'candidates':[{'model':'backup'}]}}
 value=snapshot(p,cfg,now=200)
 assert value['requests'][0]['status']=='low' and value['measurable_tokens_per_second_estimate']==1.5
 assert value['requests'][0]['last_output_age_seconds']==4 and value['session_started_at']==180
 assert 'SECRET' not in json.dumps(value) and 'prompt' not in json.dumps(value)
 stale=snapshot(p,cfg,now=218)
 assert stale['requests'][0]['status']=='stale' and stale['requests'][0]['tokens_per_second_estimate'] is None
 store.append('request_finished',task_key='a',model_call_id='live')
 assert snapshot(p,cfg,now=200)['requests']==[]
 # Failed worker/orphan starts cannot look like a still-active provider call.
 assert snapshot(p,cfg,now=500)['requests']==[]


def test_monitor_no_content_is_unknown_not_zero_and_telemetry_api_is_read_only(tmp_path):
 p,store=setup_project(tmp_path);store.append('request_started',task_key='a',requested_model='thinking')
 cfg={'resilience':{'enabled':False}}
 assert snapshot(p,cfg,now=200)['requests'][0]['tokens_per_second_estimate'] is None
 app=create_app(tmp_path/'projects');client=TestClient(app)
 rid=client.post('/api/projects',json={'name':'test','sources':{role:[{'name':role+'.md','content':'# 用例'}] for role in ('RR','SR')}}).json()['id']
 path=app.state.workbench.run_dir(rid);before=(path/'project.json').read_bytes()
 response=client.get(f'/api/projects/{rid}/execution-monitor');assert response.status_code==200,response.text
 assert response.json()['estimate']['status']=='discovering' and not (path/'model.local.json').exists()
 assert (path/'project.json').read_bytes()==before


def test_low_stream_switch_keeps_counts_and_records_previous_model(tmp_path):
 clock=[0.];client=SemanticClient({'base_url':'http://local.invalid','api_key':'test-only','agent_model':'slow','allowed_models':['slow','fast'],'run_root':str(tmp_path),'resilience':{'enabled':True,'candidates':[{'model':'fast'}],'grace_seconds':0,'window_seconds':5,'low_windows':1,'no_output_seconds':30}})
 store=EventStore(tmp_path);seen=[]
 def call(child):
  seen.append(child.model('agent'))
  if len(seen)>1:return {'valid':True}
  monitor=Monitor(lambda:child.config['resilience'],clock=lambda:clock[0],model='slow')
  monitor.observe(4,content_bytes=4,tool_argument_bytes=0,reasoning_bytes=0)
  clock[0]=6;monitor.observe(8,content_bytes=8)
 with bind(store,task_key='a',model_call_id='r'):
  assert invoke(client,{'task':'components'},call)=={'valid':True}
 assert seen==['slow','fast']
 event=next(e for e in store.read() if e['kind']=='model_switched');assert event['data']['previous_model']=='slow'
 monitor=Monitor(lambda:{'enabled':False},clock=lambda:clock[0]);monitor.observe(10,content_bytes=10,reasoning_bytes=4);clock[0]=12
 assert monitor.timeout() is None
 assert monitor.channels=={'content_bytes':10,'reasoning_bytes':4}


def test_series_supports_current_run_range_and_omits_sensitive_event_details(tmp_path):
 p,store=setup_project(tmp_path);store.append('request_started',task_key='a',requested_model='m',model_call_id='r',api_key='SECRET')
 store.append('model_switched',task_key='a',requested_model='m2',previous_model='m',previous_failure={'private':'TEXT'})
 value=series(p,since=time.time()-60)
 assert len(value['points'])==2 and value['points'][-1]['previous_model']=='m'
 assert 'SECRET' not in json.dumps(value) and 'TEXT' not in json.dumps(value)
 assert series(p,since=time.time()+60)['points']==[]
 with pytest.raises(ValueError):series(p,since=float('nan'))


def test_empty_failover_candidates_do_not_cancel_a_useful_request():
 from scene_completion.model_resilience import live_policy
 for policy in ({'enabled':True},{'enabled':True,'max_switches':0,'candidates':[{'model':'b'}]}):
  value=live_policy({'resilience':policy})()
  assert value['enabled'] is False and value['min_tokens_per_second']==2


def test_eta_uses_current_adaptive_limit_not_original_parallelism(tmp_path):
 p,_=setup_project(tmp_path);write_json(p/'run/concurrency_status.json',{'configured_max':3,'effective_max':1})
 value=snapshot(p,{'max_concurrency':3},now=200)
 assert value['effective_concurrency']==1 and value['estimate']['concurrency']==1


def test_short_successful_stream_still_records_a_final_rate_without_switching(tmp_path):
 import io
 from scene_completion.streaming import read_chat_stream
 store=EventStore(tmp_path)
 stream=io.BytesIO(('data: '+json.dumps({'choices':[{'delta':{'content':'ok'},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode())
 with bind(store,task_key='a',model_call_id='short'):
  result=read_chat_stream(stream,time.perf_counter(),10,throughput_policy=lambda:{'enabled':True,'grace_seconds':0,'min_tokens_per_second':1000000,'low_windows':1,'window_seconds':5})
 assert result['choices'][0]['message']['content']=='ok'
 samples=[r for r in store.read() if r['kind']=='throughput_sample']
 assert len(samples)==1 and samples[0]['data']['content_bytes']==2
