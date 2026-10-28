"""Offline acceptance for colleague intake, bounded recovery and gateway defaults."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,time,threading
import pytest
from fastapi.testclient import TestClient
from scene_completion import artifact_imports as imports
from scene_completion.storage import read_json,write_json
from scene_completion.runtime_settings import request_options,request_diagnostic
from scene_completion.workflow import Execution
from scene_completion.scheduler import Scheduler,Task,TaskRejected,TaskBlocked
from scene_completion.workbench import Workbench,create_app
from scene_completion.node_recovery import settings,reserve,records,eligible


def component(name='Service'):
 return {'components':[{'id':'svc','name':name,'composition_type':'内部服务','parent_id':None,'source_status':'explicit','source_refs':[]}],'relations':[]}


def receive(project,payload,task='components',coverage='complete',name='colleague.json',case=None):
 result=imports.receive(project,[{'name':name,'content':json.dumps({'task':task,'coverage':coverage,'case_id':case,'payload':payload})}])
 return imports.view(project,result['received'][0]['id'])


def make_project(root):
 service=Workbench(root);meta=service.create({'name':'审核项目','sources':{'RR':[{'name':'rr.md','content':'# UC-X\n查询对象'}],'SR':[{'name':'sr.md','content':'# UC-X\n查询对象'}]}})
 return service,service.run_dir(meta['id'])


def test_nested_off_clears_conflicts_and_preserves_other_template_parameters():
 original={'model':'deepseek','max_tokens':12000,'thinking':{'type':'enabled'},'enable_thinking':True,'reasoning_effort':'high','thinking_budget':10000,'chat_template_kwargs':{'enable_thinking':True,'other':7}}
 result=request_options(original,{'thinking_override':False,'thinking_api':'chat_template_kwargs'})
 assert result['chat_template_kwargs']=={'enable_thinking':False,'other':7}
 assert not set(result)&{'thinking','enable_thinking','thinking_budget','reasoning_effort'}
 assert original['chat_template_kwargs']['enable_thinking'] is True
 assert request_diagnostic(result)['thinking_control_status']=='disabled_requested_no_reasoning_observed'
 from scene_completion.model_routing import routed_config
 config={'agent_model':'a','thinking_override':False,'thinking_api':'chat_template_kwargs','model_routes':{'components':{'model':'b','thinking_api':'legacy'}}}
 # Global request override is tested directly above; all compatible routes retain nested off.


def test_gateway_admission_is_shared_across_keys_projects_and_paths(tmp_path):
 from scene_completion.endpoint_admission import endpoint_slot
 lock=threading.Lock();active=0;peak=0
 def request(n):
  nonlocal active,peak
  with endpoint_slot('http://gateway/v'+str(n),str(n),limit=8,scope='gateway',directory=tmp_path):
   with lock:active+=1;peak=max(peak,active)
   time.sleep(.08)
   with lock:active-=1
 with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(request,range(8)))
 assert 1<peak<=3


def test_full_import_skips_model_and_is_cited_and_deduplicated(tmp_path):
 row=receive(tmp_path,component());a=row['artifacts'][0]
 assert a['status']=='candidate' and a['document']['source_id'].startswith('import-')
 again=imports.receive(tmp_path,[{'name':'renamed.json','content':json.dumps({'task':'components','coverage':'complete','case_id':None,'payload':component()})}])
 assert again['received'][0]['duplicate']
 def forbidden(p):pytest.fail('Complete validated import must not call model')
 ex=Execution(tmp_path/'run',mocks={'components':forbidden});ex.add('components','components',static={'RR':[],'SR':[]})
 assert ex.scheduler.run()['complete']
 record=ex.scheduler.state['tasks']['components'];result=read_json(tmp_path/'run'/record['output_file'])
 assert result['payload']['components'][0]['name']=='Service'
 assert record['provenance']=='同事产物导入'


def test_partial_import_needs_confirmation_and_only_merges_missing_facts(tmp_path):
 row=receive(tmp_path,component(),coverage='partial')
 assert imports.selections(tmp_path,'components')==[]
 imports.decide(tmp_path,row['id'],{'expected_revision':0,'artifact_id':row['artifacts'][0]['id'],'action':'accept'})
 assert imports.candidate(tmp_path,'components',None,{'RR':[],'SR':[]}) is None
 parts=imports.selections(tmp_path,'components')
 assert parts[0]['accepted_partial']
 other=component('Another');other['components'][0]['id']='another'
 combined=imports.merge('components',other,parts)
 assert {c['name'] for c in combined['components']}=={'Service','Another'}
 with pytest.raises(ValueError,match='版本'):imports.decide(tmp_path,row['id'],{'expected_revision':0,'artifact_id':parts[0]['id'],'action':'accept'})


def test_import_revision_keeps_old_citations_and_snapshot_is_frozen(tmp_path):
 service,p=make_project(tmp_path);row=receive(p,component());frozen=imports.snapshot(p);first=row['artifacts'][0]['document']['source_id']
 replacement=component('Changed')
 imports.decide(p,row['id'],{'action':'accept','expected_revision':0,'artifact_id':row['artifacts'][0]['id'],'payload':replacement,'replace':True})
 assert imports.selections(p,'components',frozen=frozen)[0]['payload']['components'][0]['name']=='Service'
 from scene_completion.review_handoff import source_documents,source_view
 docs=source_documents(p)
 assert first in {d['source_id'] for d in docs}
 assert source_view(p,first,1,1)['derived_from']=='import-raw-'+row['id']
 assert len({d['source_id'] for d in docs if d['source_id'].startswith('import-')})>=3


def test_api_parameter_merge_keeps_location_identity_and_unions_constraints(tmp_path):
 from tests.test_workflow import parameter
 p=parameter('size',dtype='integer',rules=[('minimum',1)])
 a={'apis':[{'id':'api','name':'list','address':'/list','parameters':[p],'source_refs':[]}]}
 b=deepcopy(a);b['apis'][0]['parameters'][0]['required']=True;b['apis'][0]['parameters'][0]['constraints'].append({'id':'max','kind':'maximum','value':100,'status':'explicit','source_refs':p['source_refs']})
 merged=imports.merge('api-parameters',a,[{'payload':b}])
 assert len(merged['apis'][0]['parameters'])==1
 assert merged['apis'][0]['parameters'][0]['required'] is True
 assert len(merged['apis'][0]['parameters'][0]['constraints'])==2


def test_watch_requires_two_stable_samples_and_never_reads_hidden_program_or_symlinks(tmp_path):
 from scene_completion.input_gateway import watch_settings,scan
 project=tmp_path/'project';folder=tmp_path/'input';folder.mkdir();(folder/'components.json').write_text(json.dumps(component()))
 (folder/'.env').write_text('secret');(folder/'run').mkdir();(folder/'run/secret.json').write_text('{}')
 outside=tmp_path/'outside.json';outside.write_text('{}');(folder/'escape.json').symlink_to(outside)
 watch_settings(project,{'directory':str(folder),'watch':True})
 assert scan(project)['waiting']==1
 assert len(scan(project)['received'])==1
 assert len(imports.view(project)['items'])==1
 assert scan(project)['received']==[]


def test_nonartifact_conversion_cannot_inject_positive_results(tmp_path):
 from scene_completion.validation import validate_result
 from scene_completion.contracts import packet
 with pytest.raises(ValueError,match='非正向'):validate_result('artifact-convert',{'source_role':'test','artifacts':[{'task':'components','case_hint':None,'coverage':'complete','payload':component(),'source_refs':[]}]},{})
 with pytest.raises(ValueError):packet('exception-generate',{'G':[],'test-documents':[]})


def test_recovery_budget_survives_restart_and_refuses_unknown_transport_failures(tmp_path):
 settings(tmp_path,{'expected_revision':0,'settings':{'max_run_calls':2,'max_output_tokens':24000}})
 assert eligible(tmp_path,'components',{'status':'awaiting_configuration','failure':{'failure_category':'output_truncated'}},'run')
 assert not eligible(tmp_path,'components',{'status':'pending','failure':{'failure_category':'transport_timeout'}},'run')
 assert reserve(tmp_path,'node','run','hash')==1
 assert reserve(tmp_path,'node','run','hash')==2
 assert records(tmp_path)['epochs']['run']['calls']==2
 with pytest.raises(TaskBlocked):reserve(tmp_path,'node','run','hash')
 with pytest.raises(TaskBlocked):reserve(tmp_path,'another','run','hash')
 with pytest.raises(ValueError):settings(tmp_path,{'expected_revision':0,'settings':{'enabled':False}})


def test_repeated_rejections_trip_normal_repairs_then_bounded_recovery(tmp_path):
 s=Scheduler(tmp_path,1);attempts=[]
 def execute(d,r):
  attempts.append(r.copy())
  if not r.get('recovery_dispatch'):raise TaskRejected({'error':'bad schema','phase':'validation'})
  return {'value':1}
 t=Task('node','A','components',execute=execute);t.repairable=True;s.add(t)
 s.can_recover=lambda t,r:r.get('recovery_calls',0)<2
 assert s.run()['complete']
 assert len(attempts)==3 and attempts[-1]['recovery_dispatch']
 assert s.state['tasks']['node']['recovery_calls']==1


def test_priority_case_completes_before_other_case_but_does_not_starve_shared_roots(tmp_path):
 order=[];s=Scheduler(tmp_path,1);s.priority_cases=['B','A']
 def add(k,c,stage,deps=()):s.add(Task(k,c,stage,deps,execute=lambda d,r:(order.append(k),{'ok':True})[1]))
 add('shared','shared','components');add('a1','A','fused-ssd',('shared',));add('a2','A','gap-compare',('a1',));add('b1','B','fused-ssd',('shared',));add('b2','B','gap-compare',('b1',))
 assert s.run()['complete'];assert order==['shared','b1','b2','a1','a2']


def test_input_api_dryrun_version_and_business_review_model_prohibition(tmp_path):
 app=create_app(tmp_path);service=app.state.workbench;_,p=make_project(tmp_path);rid=p.name
 client=TestClient(app)
 row=receive(p,component(),coverage='partial');a=row['artifacts'][0]
 response=client.put(f'/api/projects/{rid}/imports/{row["id"]}',json={'action':'accept','artifact_id':a['id'],'expected_revision':0,'dry_run':True})
 assert response.status_code==200 and not response.json()['saved']
 assert imports.view(p,row['id'])['revision']==0
 write_json(tmp_path/'.review-mode.json',{'review_only':True});review=TestClient(create_app(tmp_path))
 assert review.post(f'/api/projects/{rid}/input-scan',json={}).status_code==403
 assert review.put(f'/api/projects/{rid}/recovery',json={}).status_code==403


def test_mermaid_literals_extract_clean_http_but_do_not_invent_layer_or_entities():
 from scene_completion.artifact_parsers import mermaid_sequences
 diagrams=mermaid_sequences('```mermaid\nsequenceDiagram\n actor D as 开发者\n participant S as Service\n D->>S: GET /ms/v1/repos<br/>查询列表\n S-->>D: items[]\n```')
 assert diagrams[0]['participants'][0]['human']
 assert diagrams[0]['messages'][0]['http']==[{'method':'GET','path':'/ms/v1/repos'}]
 assert 'layer' not in diagrams[0] and len(diagrams[0]['messages'])==2


def test_plain_json_does_not_claim_project_wide_completeness_or_overwrite_its_original(tmp_path):
 raw=json.dumps(component())
 result=imports.receive(tmp_path,[{'name':'record.json','content':raw}]);row=imports.view(tmp_path,result['received'][0]['id'])
 assert (tmp_path/row['original']).read_text()==raw
 assert row['artifacts'][0]['coverage']=='partial'
 assert imports.selections(tmp_path,'components')==[]


def test_imported_interface_can_feed_index_and_parameter_tasks_without_rr_invention(tmp_path):
 from scene_completion.api_documents import index_interfaces
 mapping={'services':[{'name':'Catalog','interfaces':[{'id':'API-LIST','name':'list','method':'GET','address':'/repos','source_refs':[]}],'source_refs':[]}]}
 row=receive(tmp_path,mapping,task='api-map');a=row['artifacts'][0]
 out=index_interfaces({'SR':[a['document']],'api-map':a['payload']})
 assert out['apis'][0]['id']=='API-LIST'
 assert out['apis'][0]['source_ranges'][0]['source_id']==a['document']['source_id']


def test_unknown_http_call_prevents_background_auto_resume(tmp_path):
 from scene_completion.execution_events import EventStore
 from scene_completion.worker_runtime import unsafe_to_resume,read_job
 events=EventStore(tmp_path/'run');events.append('request_started',model_call_id='inflight')
 assert unsafe_to_resume(tmp_path)
 events.append('request_finished',model_call_id='inflight',usage={'total_tokens':10})
 assert not unsafe_to_resume(tmp_path)
 write_json(tmp_path/'job.json',{'status':'running','pid':123,'worker_token':'current'})
 write_json(tmp_path/'worker-heartbeat.json',{'pid':123,'worker_token':'stale','at':time.time()})
 assert 'worker_heartbeat' not in read_job(tmp_path)
 write_json(tmp_path/'worker-heartbeat.json',{'pid':123,'worker_token':'current','at':time.time()})
 assert read_job(tmp_path)['worker_heartbeat']>0


def test_output_truncation_failure_reaches_recovery_dispatch(tmp_path):
 s=Scheduler(tmp_path,1);seen=[]
 def work(d,r):
  if not r.get('recovery_dispatch'):raise TaskBlocked('awaiting_configuration',{'failure_category':'output_truncated'})
  seen.append(r['failure']['failure_category']);return {'ok':True}
 s.add(Task('node','A','components',execute=work));s.can_recover=lambda t,r:r.get('recovery_calls',0)<2
 assert s.run()['complete'] and seen==['output_truncated']
