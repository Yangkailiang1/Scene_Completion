from copy import deepcopy
import json
from types import SimpleNamespace
import pytest
from scene_completion.storage import write_json,read_json,fingerprint
from scene_completion import quality_diagnostics as q
from scene_completion.quality_runtime import enqueue,accept_analysis,evidence_packet,run_job,notify_completed
from scene_completion.quality_actions import impact,apply
from scene_completion.concern_registry import default_registry
from scene_completion.pattern_settings import settings
from tests.test_result_views import fixture


def project(p):
 fixture(p);registry=default_registry();write_json(p/'project.json',{'id':'a'*32,'sources':{},'name':'demo','created_at':0})
 write_json(p/'run/registry_override.json',registry);settings(p)
 state=read_json(p/'run/workflow_tasks.json')['tasks']
 def put(key,payload):
  f='task_outputs/'+fingerprint(key)+'.json';write_json(p/'run'/f,{'payload':payload});state[key]={'case':'C','stage':key.split(':')[1],'status':'passed','output_file':f}
 key='api.data.range';bindings={x:{'binding_id':x,'interaction_id':'i1','direction':'request','target':'data','object':'page','concern_key':key,'source_refs':[]} for x in ('a','b','c')}
 from scene_completion.concern_alignment import compare
 co=compare({'matches':[{**bindings[x],'status':'applicable'} for x in ('a','b')]},{'matches':[{**bindings['a'],'status':'applicable'}]},{'matches':[{**bindings[x],'status':'applicable'} for x in ('a','c')]})
 put('C:concern-evaluation',co)
 def s(id):return {'id':id,'interaction_id':'i1','object':'page','concern_key':key,'cause':id,'scenario_type':'exception','risk':{'level':'critical'}}
 ev={'concern_level':co,'G':[s('g1'),s('g2')],'E':[s('e')],'GT':[s('t1'),s('t2')],'M':[s('g1'),s('g2')],
 'full_matches':{'GT_G':[{'checker_scenario_id':'t1','generated_scenario_id':'g1'}],'GT_E':[],'GT_Q':[]},'metrics':deepcopy(co['metrics'])}
 from scene_completion.recommendation import evaluate
 rec={'enabled':True,'Q':[s('g2')],'run_id':'r','ranked':[]}
 ev=evaluate(ev,rec)
 put('C:exception-evaluation',ev);put('C:gap-recommend',rec);put('C:missing-report',ev)
 write_json(p/'run/workflow_tasks.json',{'tasks':state})
 write_json(p/'run/workflow_graph.json',{'nodes':[{'id':k,'case':r.get('case'),'stage':r.get('stage'),'deps':['C:gap-recommend'] if k=='C:exception-evaluation' else []} for k,r in state.items()]})
 manifest=read_json(p/'run/run_manifest.json');manifest.update(registry_hash=registry['hash'],matching_version=co['version'],evaluation_by_case={'C':True},execution_complete=True);write_json(p/'run/run_manifest.json',manifest)
 write_json(p/'run/registry_used'/(registry['hash']+'.json'),registry)
 return co


def test_frozen_losses_conserve_saved_counts_and_sources(tmp_path):
 co=project(tmp_path);before={p: p.read_bytes() for p in (tmp_path/'run').rglob('*.json')}
 v=enqueue(tmp_path,'original');assert v['test_set']=='original'
 assert not v['integrity']
 cards={c['metric']+':'+c['scope']:c for c in v['cards']}
 assert cards['generation_validity:current']['loss_count']==1
 assert cards['missing_exception_miss_rate:current']['loss_count']==1
 assert cards['recommendation_adoption:recommended']['loss_count']==1
 assert cards['recommendation_false_positive:recommended']['denominator']==2
 l=next(x for x in v['losses'] if x['metric']=='generation_validity')
 assert l['primary_cause']=='unverified' and '不能' in l['reason']
 assert all(p.read_bytes()==content for p,content in before.items())
 assert enqueue(tmp_path,'original')['id']==v['id']
 assert enqueue(tmp_path,'expanded')['id']!=v['id']
 assert '当前冻结GT' in q.markdown(v)


def test_normal_optional_do_not_enter_definite_loss_units(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original')
 assert all(l['anchor'].get('scenario_type','exception')=='exception' for l in v['losses'])
 assert any(c['status']=='待审核' and c['value'] is None for c in v['cards'])


def test_model_findings_strict_ids_evidence_and_gt_only_proposal_not_applicable(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original');snap=read_json(q.store(tmp_path)/v['id']/'snapshot.json')
 l=v['losses'][0];packet=evidence_packet(snap,[l]);eid=packet['evidence'][0]['id']
 finding={'loss_id':l['id'],'primary_cause':'recognition','certainty':'疑似','reason':'需核对适用条件','evidence_ids':[eid]}
 accept_analysis(v,{'findings':[finding],'proposals':[]},packet)
 assert v['coverage']['evidence_reviewed']==1
 with pytest.raises(ValueError):accept_analysis(v,{'findings':[{**finding,'loss_id':'bogus'}]},packet)
 with pytest.raises(ValueError):accept_analysis(v,{'findings':[{**finding,'certainty':'已核实','evidence_ids':[]}]},packet)
 packet['evidence']=[{'id':'test','channel':'GT'}]
 proposal={'kind':'concern','target':'api.data.range','patch':{'description':'bad'},'evidence_ids':['test'],'loss_ids':[l['id']]}
 accept_analysis(v,{'findings':[],'proposals':[proposal]},packet)
 assert not v['proposals'][0]['applicable']


def test_application_requires_human_snapshot_and_targeted_rank_impact(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original')
 v['proposals']=[{'id':'p','kind':'recommendation','target':'ranking','patch':{'top_k':11},'applicable':True,'loss_ids':[],'evidence':[]}];q.save(tmp_path,v)
 body={'snapshot_hash':v['snapshot_hash'],'reviewer':'Human','approvals':['p']}
 plan=impact(tmp_path,v['id'],body)
 assert plan['ranking_only'] and 'components' not in plan['affected']
 assert plan['roots']==['C:gap-recommend']
 for bad in ({**body,'reviewer':''},{**body,'snapshot_hash':'old'},{**body,'approvals':['notexist']}):
  with pytest.raises(ValueError):impact(tmp_path,v['id'],bad)
 service=SimpleNamespace(run_dir=lambda rid:tmp_path,review_only=False,active=set())
 old=settings(tmp_path)['version']
 assert not apply(service,'a'*32,v['id'],{**body,'dry_run':True})['saved']
 assert settings(tmp_path)['version']==old
 assert apply(service,'a'*32,v['id'],body)['saved']
 assert settings(tmp_path)['settings']['top_k']==11
 with pytest.raises(ValueError):apply(service,'a'*32,v['id'],body)


def test_ranking_identity_is_not_semantic_identity():
 from scene_completion.workflow import analysis_settings
 from scene_completion.scenario_patterns import normalize_settings
 a=normalize_settings();b=normalize_settings({**a,'top_k':50,'risk_weight':.5,'history_weight':.5})
 assert a['hash']!=b['hash']
 assert analysis_settings(a)['hash']==analysis_settings(b)['hash']
 b['threshold']=.9
 assert analysis_settings(a)['hash']!=analysis_settings(b)['hash']


def test_old_completed_project_not_enqueued_by_host_scan(tmp_path):
 project(tmp_path)
 from scene_completion.quality_runtime import QualityHost
 host=object.__new__(QualityHost);host.service=SimpleNamespace(root=tmp_path.parent)
 host.tick();assert q.listing(tmp_path)==[]
 notify_completed(tmp_path);assert len(q.listing(tmp_path))==1
 notify_completed(tmp_path);assert len(q.listing(tmp_path))==1


def test_budgeted_model_execution_and_unresolved_post_not_repeated(tmp_path,monkeypatch):
 project(tmp_path);v=enqueue(tmp_path,'original');calls=[]
 import scene_completion.manager_agent as manager
 monkeypatch.setattr(manager,'resolved',lambda *args:{'stream':False})
 class Client:
  def model(self,kind):return 'fake'
  def output_limit(self,stage):return 2000
  def post(self,endpoint,body):
   calls.append(body)
   packet=json.loads(body['messages'][1]['content']);eid=packet['evidence'][0]['id'] if packet['evidence'] else None
   result={'findings':[{'loss_id':l['id'],'primary_cause':'unknown','certainty':'待确认','reason':'需业务核对','evidence_ids':[eid] if eid else []} for l in packet['losses']]}
   return {'usage':{'total_tokens':300},'choices':[{'message':{'content':json.dumps(result)}}]}
 service=SimpleNamespace(run_dir=lambda rid:tmp_path)
 done=run_job(service,'a'*32,v['id'],Client())
 assert done['status']=='complete' and done['budget']['charged_tokens']==300*len(calls)
 assert done['coverage']['evidence_reviewed']==len(done['losses'])
 assert len(json.dumps(calls,ensure_ascii=False))<100000
 calls.clear();run_job(service,'a'*32,v['id'],Client());assert not calls
 done.update(status='partial');done['batches']['unknown']={'status':'sending'};q.save(tmp_path,done)
 stopped=run_job(service,'a'*32,v['id'],Client());assert stopped['status']=='partial' and not calls


def test_cli_quality_parser_and_review_only(tmp_path):
 from scene_completion.workbench_cli import parser,main
 args=parser().parse_args(['quality','diagnose','--project','a'*32,'--case','C','--test-set','original','--tool-only'])
 assert args.case=='C'
 class API:
  def call(self,*args):self.args=args;return {'status':'partial','id':'x'}
 client=API();assert main(['quality','diagnose','--project','a'*32,'--tool-only'],client)==0
 assert client.args[0].endswith('/quality-diagnostics')
 from scene_completion.workbench import create_app
 from fastapi.testclient import TestClient
 app=create_app(tmp_path/'data');api=TestClient(app)
 rid=api.post('/api/projects',json={'name':'A','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}]}}).json()['id']
 project(app.state.workbench.run_dir(rid));base='/api/projects/'+rid+'/quality-diagnostics'
 r=api.post(base,json={'test_set':'original','tool_only':True});assert r.status_code==200,r.text
 did=r.json()['id'];assert api.get(base+'/'+did+'?format=md').status_code==200
 app.state.workbench.review_only=True
 assert api.get(base).status_code==200 and api.post(base,json={}).status_code==403


def test_budget_block_and_unknown_transport_do_not_retry_or_reset(tmp_path,monkeypatch):
 project(tmp_path);v=enqueue(tmp_path,'original')
 import scene_completion.manager_agent as manager
 monkeypatch.setattr(manager,'resolved',lambda *args:{'stream':False})
 class Big:
  def model(self,k):return 'fake'
  def output_limit(self,s):return 100001
  def post(self,*args):raise AssertionError('over-budget request sent')
 service=SimpleNamespace(run_dir=lambda rid:tmp_path)
 stopped=run_job(service,'a'*32,v['id'],Big());assert stopped['status']=='partial' and stopped['budget']['requests']==0
 class Unknown(Big):
  def output_limit(self,s):return 1000
  def post(self,*args):raise TimeoutError('unknown POST')
 stopped=run_job(service,'a'*32,v['id'],Unknown());assert stopped['budget']['unknown']==1
 after=run_job(service,'a'*32,v['id'],Big());assert after['budget']['requests']==1


def test_crashed_apply_recovers_only_without_newer_configuration(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original');folder=q.store(tmp_path)/v['id']
 original=(tmp_path/'pattern-settings.json').read_text()
 write_json(folder/'application.json',{'status':'applying','before':{'pattern-settings.json':original},'intended':{'patterns':'new'}})
 write_json(tmp_path/'pattern-settings.json',{'version':'new','history':[]})
 from scene_completion.quality_actions import recover_application
 recover_application(tmp_path,v['id'])
 assert read_json(tmp_path/'pattern-settings.json')==json.loads(original)
 assert read_json(folder/'application.json')['status']=='rolled_back_after_restart'
 write_json(folder/'application.json',{'status':'applying','before':{'pattern-settings.json':original},'intended':{'patterns':'new'}})
 write_json(tmp_path/'pattern-settings.json',{'version':'someone-else','history':[]})
 recover_application(tmp_path,v['id'])
 assert read_json(tmp_path/'pattern-settings.json')['version']=='someone-else'
 assert read_json(folder/'application.json')['status']=='conflict'


def test_extraction_acc_has_auditable_individual_losses(tmp_path):
 project(tmp_path)
 from scene_completion.evaluation import accuracy
 extracted={'components':[{'name':'A','composition_type':'internal_service'}]}
 truth={'components':extracted['components']+[{'name':'B','composition_type':'internal_service'}]}
 scored=accuracy('components',extracted,truth)
 assert scored['H']==1 and scored['N']==2 and len(scored['unmatched_truth_ids'])==1
 state=read_json(tmp_path/'run/workflow_tasks.json');file='task_outputs/acc.json';write_json(tmp_path/'run'/file,{'payload':scored})
 state['tasks']['components:accuracy']={'stage':'extraction-evaluation','case':'shared','status':'passed','output_file':file};write_json(tmp_path/'run/workflow_tasks.json',state)
 graph=read_json(tmp_path/'run/workflow_graph.json');graph['nodes'].append({'id':'components:accuracy'});write_json(tmp_path/'run/workflow_graph.json',graph)
 v=enqueue(tmp_path,'original');card=next(c for c in v['cards'] if c['metric']=='Acc')
 assert card['loss_count']==card['expected_loss_count']==1
 assert not v['integrity']


def test_compact_case_pagination_and_business_handoff_excludes_context(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original')
 compact=q.compact_report(v,'C',offset=0,limit=2)
 assert len(compact['losses'])==2 and compact['pagination']['total']==len(v['losses'])
 assert 'output_hashes' not in compact['versions'] and 'batches' not in compact
 assert q.compact_report(v,'other')['losses']==[]
 from scene_completion.review_handoff import project_archive
 import zipfile,io
 write_json(q.store(tmp_path)/v['id']/'responses/secret.json',{'choices':[]})
 raw,_=project_archive(tmp_path)
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  names=archive.namelist()
  assert any(n.startswith('quality-diagnostics/') and n.endswith('/report.json') for n in names)
  assert not any(n.startswith('quality-diagnostics/') and not n.endswith('/report.json') for n in names)


def test_invalid_model_claim_is_not_allowed_to_change_formal_metric(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original');before=deepcopy(v['summary'])
 snap=read_json(q.store(tmp_path)/v['id']/'snapshot.json');packet=evidence_packet(snap,v['losses'][:1])
 with pytest.raises(ValueError):accept_analysis(v,{'findings':[{'loss_id':'unknown','primary_cause':'recognition','certainty':'已核实','evidence_ids':[]}]},packet)
 assert v['summary']==before


def test_scope_of_gt_claim_checked_against_frozen_set_size(tmp_path):
 project(tmp_path);v=enqueue(tmp_path,'original');snap=read_json(q.store(tmp_path)/v['id']/'snapshot.json');packet=evidence_packet(snap,v['losses'][:1])
 assert packet['set_sizes']['GT_c']==2
 finding={'loss_id':packet['losses'][0]['id'],'primary_cause':'unverified','certainty':'疑似','reason':'当前冻结GT为空','evidence_ids':[]}
 with pytest.raises(ValueError,match='GT集合非空'):accept_analysis(v,{'findings':[finding]},packet)
