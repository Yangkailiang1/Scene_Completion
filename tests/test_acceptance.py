"""Regression cases for the new workflow boundaries; all inference is mocked."""
from copy import deepcopy
import json,threading,time
from pathlib import Path
import pytest
from tests.test_workflow import memory_inputs,exchange,parameter,scenario,decision,fake_pipeline,R
from scene_completion.contracts import registry,packet,PROTOCOL,TASKS
from scene_completion.storage import fingerprint,read_json,write_json
from scene_completion.exception_generation import data_exceptions,query_exceptions,query_matches,pending_rules
from scene_completion.concern_matching import complete_data_matches
from scene_completion.interaction_enrichment import enrich,capability_union,bind_resource_services,actual_context,with_concerns
from scene_completion.exception_comparison import missing_report
from scene_completion.validation import validate_result
from scene_completion.evaluation import accuracy,not_evaluated
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.scheduler import Scheduler,Task,TaskRejected,TaskBlocked,CallGate
from scene_completion.run_inspection import inspect_run


def test_request_and_response_rules_are_separate_and_parent_resolves_api():
    x=memory_inputs();req=x['sr-ssd']['interactions'][0]
    ret=deepcopy(req);ret.update(id='ret',sequence=2,direction='return',parent_id=req['id'],api_id=None)
    ret['data']['sequence']=[];ret['sender'],ret['receiver']=ret['receiver'],ret['sender']
    x['sr-ssd']['interactions'].append(ret)
    x['api-parameters']['apis'][0]['parameters'].append(parameter('total','response',True,'integer',rules=[('minimum',0)]))
    x['concern-match']['matches']=complete_data_matches(x,[])
    out=data_exceptions(x);requests=[s for s in out if s['interaction_id']=='req'];returns=[s for s in out if s['interaction_id']=='ret']
    assert len(requests)==8 and len(returns)==3
    assert {s['field'] for s in returns}=={'total'} and not any(s['field']=='total' for s in requests)
    assert all(s['steps']['trigger'] and not s['steps']['documented_follow_up'] for s in out)
    ret['data']['sequence']=[parameter('page','query')]
    with pytest.raises(ValueError,match='request fields'):validate_result('sr-ssd',x['sr-ssd'],x)


@pytest.mark.parametrize('origin',['内部数据库','外部数据库'])
def test_database_facade_has_database_resource_concern_for_either_origin(origin):
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    x['components']['components']=[{'id':'db','name':'PhysicalDB','composition_type':origin,'source_refs':R}]
    i['receiver'].update(name='PhysicalDB',position=origin)
    x=bind_resource_services(x)
    x['enriched-interactions']={'interactions':x['sr-ssd']['interactions']}
    out=query_exceptions(x)
    assert len(out)==2 and all(s['concern_key']=='internal_database.resource_existence' for s in out)
    assert {s['cause'] for s in out}=={'no_matching_records','requested_resource_not_found'}
    assert out[0]['cause']=='no_matching_records' and out[0]['object']=='PhysicalDB资源服务'
    bad=query_matches(x)[0];bad['concern_key']='service.query_retrieval.resource_existence'
    with pytest.raises(ValueError,match='wrong query'):validate_result('concern-match',{'matches':[bad],'pending':[]},x)


def test_generic_query_and_missing_instance_do_not_cover_each_other():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['operation']['name']='list workspaces';i['receiver']['position']='内部服务'
    candidates=query_exceptions(x)
    assert {s['cause'] for s in candidates}=={'no_matching_records','requested_resource_not_found'}
    assert all(not s['steps']['documented_follow_up'] for s in candidates)
    no_match=candidates[0]
    assert no_match['concern_key']=='service.query_retrieval.resource_existence'
    other=deepcopy(no_match);other.update(id='existing',cause='instance_missing',source_status='explicit')
    with pytest.raises(ValueError,match='cannot cover'):
        validate_result('semantic-compare',{'decisions':[decision(no_match['id'],'existing')]},{'left':[no_match],'right':[other],'purpose':'G_E'})
    result=missing_report([no_match],[other],[decision(no_match['id'],'existing','partial')])
    assert result['M']==[no_match]
    i['operation']['name']='read single workspace';assert not query_exceptions(x)


def test_enrichment_uses_composition_capabilities_api_and_evidenced_expansion():
    x=memory_inputs();rr=exchange(sid='rr1',layer='RR',api=None);sr=x['sr-ssd']['interactions'][0]
    sr['receiver']['name']='query service';sr['receiver']['position']='内部服务'
    x['rr-ssd']['interactions']=[rr]
    x['components']['components']=[{'id':'actor','name':'开发者','composition_type':'外部Actor（人类）','source_refs':R},
       {'id':'platform','name':'Platform','composition_type':'系统边界','source_refs':R},
       {'id':'query','name':'QueryService','composition_type':'内部服务','source_refs':R}]
    x['api-map']={'services':[{'name':'QueryService','interfaces':[{'id':'API-M-IF2','name':sr['operation']['name'],'method':None,'address':None,'source_refs':R}],'source_refs':R}]}
    x['object-operations']=capability_union({'components':x['components'],'rr-ssd':x['rr-ssd'],'test-operations':{'objects':[]}})
    x['object-operations']['objects'][0]['supported_operations'].append({'name':'write','source_refs':R})
    alignment={'aliases':[{'name':'query service','component_id':'query','source_refs':R}],
       'links':[{'rr_id':'rr1','sr_ids':[sr['id']],'status':'confirmed','basis':'explicit expansion','source_refs':R}]}
    validate_result('interaction-align',alignment,x)
    out=enrich(x,alignment);req=out['interactions'][0];inner=out['interactions'][1]
    assert req['receiver']['component_id']=='platform' and len(req['receiver']['supported_operations'])==2
    assert inner['receiver']['name']=='QueryService' and inner['receiver']['supported_operations']
    assert inner['associated_api']=='API-M-IF2' and len(inner['data']['sequence'])==5
    assert out['rr_sr_links'][0]['status']=='confirmed'
    safe=actual_context(out)
    assert all('write' not in [o['name'] for o in i['receiver']['supported_operations']] for i in safe['interactions'])
    assert req['operation']['kinds']==['read']
    populated=with_concerns(out,{'matches':x['concern-match']['matches']})
    assert populated['interactions'][1]['data']['concerns']
    unknown=enrich(x,{'aliases':[],'links':[]})
    assert any('RR步骤' in p['reason'] for p in unknown['pending'])


def test_gap_skill_returns_M_and_rejects_wrong_M():
    g=scenario('g');e=scenario('e',cause='different',status='explicit');inputs={'left':[g],'right':[e],'purpose':'G_E'}
    decisions=[decision('g','e','partial')]
    packet('gap-compare',inputs)
    validate_result('gap-compare',{'decisions':decisions,'missing':[g]},inputs)
    with pytest.raises(ValueError,match='missing must'):
        validate_result('gap-compare',{'decisions':decisions,'missing':[]},inputs)


def test_missing_report_survives_GT_failure_and_internal_prompts_differ(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path)
    m['test-ground-truth']={'invalid':'not a GT result'}
    ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,t)
    state=ex.finish()
    assert not state['complete'] and state['analysis_complete']
    report=read_json(tmp_path/'run/missing_report.json')
    assert 'UC-X' in report['cases'] and report['evaluation_status']['UC-X']=='未评测或任务未完成'
    assert (tmp_path/'run/missing_report.md').exists()
    assert ex.skill_text('test-operation-project')!=ex.skill_text('existing-extract')!=ex.skill_text('test-ground-truth')
    assert 'source_refs.quote' in ex.skill_text('test-operation-project')
    assert inspect_run(tmp_path/'run')['valid']


def test_two_cases_one_failure_does_not_block_other_case(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);rr2=deepcopy(rr[0]);sr2=deepcopy(sr[0])
    rr2['source_id']='rr-two';sr2['source_id']='sr-two'
    for d in (rr2,sr2):d['lines'][0]['text']='# UC-Y'
    rr+= [rr2];sr+=[sr2]
    base_rr=m['rr-ssd'];base_sr=m['sr-ssd']
    def ssd(base):
        def call(p):
            cid=p['case_ids'][0]
            if cid=='UC-X':return {'invalid':True}
            v=deepcopy(base)
            for i in v['interactions']:i['case_id']=cid
            for i in v['interactions']:
                doc=p['input']['RR' if i['layer']=='RR' else 'SR'][0]
                def patch(node):
                    if isinstance(node,dict):
                        for k,val in node.items():
                            if k=='source_refs':node[k]=[{'source_id':doc['source_id'],'line_start':2,'line_end':2,'quote':doc['lines'][1]['text']}]
                            else:patch(val)
                    elif isinstance(node,list):
                        for val in node:patch(val)
                patch(i)
            return v
        return call
    m['rr-ssd']=ssd(base_rr);m['sr-ssd']=ssd(base_sr)
    ex=Execution(tmp_path/'multi',mocks=m,config={'max_concurrency':3},case_ids=['UC-X','UC-Y']);build_pipeline(ex,rr,sr,[])
    result=ex.finish()
    assert not result['analysis_by_case']['UC-X'] and result['analysis_by_case']['UC-Y']
    assert 'UC-Y' in read_json(tmp_path/'multi/missing_report.json')['cases']


def test_six_manual_GTs_pipeline_status_and_bound_semantic_decisions(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);truth={'components':m['components'],'api-map':{'services':[]},
      'api-parameters':{'apis':[]},'UC-X:rr-ssd':m['rr-ssd'],'UC-X:sr-ssd':m['sr-ssd'],
      'UC-X:object-operations':{'objects':[]}}
    ex=Execution(tmp_path/'score',mocks=m);build_pipeline(ex,rr,sr,[],truth);assert ex.finish()['complete']
    outputs={k:read_json(ex.root/r['output_file'])['payload'] for k,r in ex.scheduler.state['tasks'].items() if k.endswith(':accuracy')}
    assert len(outputs)==6 and outputs['UC-X:rr-ssd:accuracy']['Acc']==100
    assert len(list((ex.root/'artifacts/shared').glob('*--accuracy.json')))==3
    assert len(list((ex.root/'artifacts').glob('*/rr-ssd--accuracy.json')))==1
    assert outputs['api-map:accuracy']['status']=='不适用'
    assert not_evaluated('api-map')['status']=='未评测'
    original=truth['components'];other=deepcopy(original);other['components'][0]['name']='developer'
    units=accuracy('components',other,original)
    decisions=[decision(units['truth_units'][0]['id'],units['extracted_units'][0]['id'])]
    bound={'protocol':PROTOCOL,'task':'components','extracted_hash':fingerprint(other),'truth_hash':fingerprint(original),'decisions':decisions}
    assert accuracy('components',other,original,bound)['H']==1
    other['components'][0]['name']='another'
    with pytest.raises(ValueError,match='not bound'):accuracy('components',other,original,bound)


def test_ssd_semantic_adjudication_cannot_change_order():
    a={'interactions':[exchange()]};t=deepcopy(a);t['interactions'][0]['sequence']=2
    units=accuracy('rr-ssd',a,t)
    with pytest.raises(ValueError,match='preserve case'):
        accuracy('rr-ssd',a,t,[decision(units['truth_units'][0]['id'],units['extracted_units'][0]['id'])])


def test_scheduler_shared_concurrency_local_repair_resume_and_content_invalidation(tmp_path):
    calls=[];lock=threading.Lock();active=0;peak=0
    def execute(deps,r):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active);calls.append((r['case'],r['rounds']))
        time.sleep(.01)
        with lock:active-=1
        if r['case']=='bad' and r['rounds']<1:raise TaskRejected({'schema':'bad'})
        return {'payload':{'value':1},'metadata':{'attempt':r['rounds']}}
    def build(version=1):
        s=Scheduler(tmp_path,concurrency=2)
        for cid in ('bad','good','other'):s.add(Task(cid,cid,'read',version=version,execute=execute,repair=execute))
        return s
    s=build();assert s.run()['complete'];assert 1<peak<=2 and ('bad',1) in calls
    n=len(calls);assert build().run()['complete'] and len(calls)==n
    s=build(2);assert s.run()['complete'] and len(calls)>n


def test_scheduler_output_same_after_upstream_change_reuses_downstream(tmp_path):
    def build(version):
        s=Scheduler(tmp_path);s.add(Task('a','case','project',version=version,execute=lambda d,r:{'payload':{'same':1},'metadata':{'changed':version}}))
        s.add(Task('b','case','G',('a',),version=1,execute=lambda d,r: {'result':1} if version==1 else pytest.fail('must reuse')))
        return s
    assert build(1).run()['complete'] and build(2).run()['complete']


def test_gate_halves_limit_and_applies_global_cooldown():
    g=CallGate(4);g.observe({'failure_category':'rate_limited','retry_after_seconds':1})
    assert g.effective_limit==2 and g.retry_not_before>time.monotonic()


def test_report_markdown_contains_steps_sources_pending_and_no_Q(tmp_path):
    from scene_completion.artifact_exports import export_missing_report
    x=memory_inputs();g=data_exceptions(x);report=missing_report(g,[],[])
    report.update(interactions={'interactions':x['sr-ssd']['interactions']},concerns=x['concern-match']['matches'],pending=pending_rules(x))
    export_missing_report(tmp_path,{'protocol':PROTOCOL,'cases':{'case':report},'evaluation_status':{'case':'未评测'},'recommendation':{'enabled':False}})
    text=(tmp_path/'missing_report.md').read_text()
    assert '正常交互' in text and '异常触发' in text and '缺失原因' in text and '待确认' in text and '来源' in text
    assert 'Q' not in read_json(tmp_path/'missing_report.json')

def test_positive_projection_excludes_before_change_and_negative_responses(tmp_path):
    from scene_completion.source_documents import read_documents,normal_projection,current_projection
    path=tmp_path/'api.md';path.write_text('# API\n## 变更前\nold parameter\n- 错误响应：OLD_ERROR\n## 变更后\nnew parameter\n- 成功响应：items[]\n- 错误响应：INVALID_INPUT\n返回400\n# next API\nnormal response\n')
    raw=read_documents([path],'existing');normal=normal_projection(raw)
    text=json.dumps(normal,ensure_ascii=False)
    assert 'new parameter' in text and 'items[]' in text and 'normal response' in text
    assert 'old parameter' not in text and 'INVALID_INPUT' not in text and '返回400' not in text
    existing=json.dumps(current_projection(raw),ensure_ascii=False)
    assert 'INVALID_INPUT' in existing and 'OLD_ERROR' not in existing


def test_object_capabilities_reject_unsanitized_test_projection():
    rr=exchange(layer='RR');bad={'components':{'components':[],'relations':[]},'rr-ssd':{'interactions':[rr]},
      'test-operations':{'objects':[{'name':'Platform','supported_operations':[{'name':'read','source_refs':[{**R[0],'quote':'read fails with 404'}]}]}]}}
    with pytest.raises(ValueError,match='only'):
        validate_result('object-operations',capability_union(bad),bad)


def test_malformed_provider_JSON_is_bounded_and_kept_for_diagnosis(tmp_path):
    from scene_completion.model_client import SemanticClient
    calls=[]
    def transport(*args):
        calls.append(1);return {'model':'configured','choices':[{'finish_reason':'stop','message':{'content':'{broken'}}]}
    client=SemanticClient({'base_url':'http://offline.invalid','agent_model':'configured','max_tokens':2000},transport=transport);client.api_key='offline-only'
    ex=Execution(tmp_path,mode='external',client=client);ex.add('rr-ssd','rr-ssd',static={'RR':[]})
    assert not ex.finish()['complete'] and len(calls)==3
    assert ex.scheduler.state['tasks']['rr-ssd']['rounds']==2
    assert len(list((tmp_path/'attempts').rglob('*.json')))==3

def test_complete_offline_memory_example_is_executable_and_has_no_fake_metrics(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run([sys.executable,str(root/'examples/memory_demo.py'),'--output-dir',str(tmp_path)],capture_output=True,text=True)
    assert p.returncode==0,p.stdout+p.stderr
    manifest=read_json(tmp_path/'run/run_manifest.json');assert manifest['analysis_complete']
    assert manifest['execution_identity']['mode']=='mock'
    report=read_json(tmp_path/'run/missing_report.json')
    assert report['evaluation_status']['SC002-UC002']=='未评测或任务未完成'
    g=report['cases']['SC002-UC002']['G']
    assert len([s for s in g if s['layer']=='SR' and s['field'] is not None])==8
    assert {'no_matching_records','requested_resource_not_found'}<={s['cause'] for s in g}
