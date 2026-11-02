from copy import deepcopy
import json
import pytest
from scene_completion.evaluation_scope import interaction_layers,report_view,concern_view
from scene_completion.concern_alignment import compare
from scene_completion.exception_comparison import compare_report
from scene_completion.recommendation import evaluate
from scene_completion.storage import write_json,fingerprint
from tests.test_workflow import exchange,scenario,decision


def sample():
    # Deliberately reverse conventional path prefixes: source ownership wins.
    rr=exchange(sid='rr',layer='SR',api='RR::PUBLIC')
    rr['source_views']=[{'layer':'RR','id':'rr-old'}]
    sr=exchange(sid='sr',api='SR::INTERNAL')
    sr['sender']={'name':'Platform','position':'内部服务'}
    sr['receiver']={'name':'Worker','position':'内部服务'}
    ret=deepcopy(sr);ret.update(id='ret',direction='return',parent_id='sr',api_id=None)
    ret['sender'],ret['receiver']=ret['receiver'],ret['sender']
    unknown=exchange(sid='unknown',api=None)
    inputs={'enriched-interactions':{'interactions':[rr,sr,ret,unknown]},'api-map':{'services':[]},
            'api-parameters':{'apis':[{'id':'RR::PUBLIC','source_layer':'RR','address':'/ms/internal','parameters':[]},
                                      {'id':'SR::INTERNAL','source_layer':'SR','address':'/v1/public','parameters':[]}]}}
    def s(sid,iid,cause):return {**scenario(sid,cause),'interaction_id':iid}
    g=[s('grr','rr','rr_failure'),s('gsr','sr','bad_input'),s('gret','ret','bad_output'),s('gx','unknown','unknown_failure')]
    e=[s('esr','sr','bad_input')]
    gt=[s('trr','rr','rr_failure'),s('tsr','sr','bad_input'),s('tret','ret','bad_output')]
    report=compare_report(g,e,gt,[decision('gsr','esr')],[decision('trr','grr'),decision('tsr','gsr'),decision('tret','gret')],[decision('tsr','esr')])
    inputs['gap-recommend']={'enabled':True,'Q':[g[0],g[2],g[3]],'ranked':[]}
    report=evaluate(report,inputs['gap-recommend'])
    def b(iid):return {'binding_id':'binding-'+iid,'status':'applicable','interaction_id':iid,'case_id':'CASE-A','direction':'return' if iid=='ret' else 'request','target':'receiver','object':iid,'concern_key':'service.query_retrieval.resource_existence'}
    concerns=compare({'matches':[b(i) for i in ('rr','sr','ret','unknown')]},{'matches':[b('sr')]},{'matches':[b(i) for i in ('rr','sr','ret')]})
    return inputs,report,concerns


def test_layer_is_actual_api_ownership_not_projected_message_id_or_url_prefix():
    inputs,_,_=sample();layers=interaction_layers(inputs)
    assert layers['rr']['layer']=='RR' and layers['sr']['layer']=='SR'
    assert layers['ret']['layer']=='SR' and layers['ret']['api_id']=='SR::INTERNAL'
    assert layers['unknown']['layer'] is None
    call=deepcopy(inputs['enriched-interactions']['interactions'][1]);call.update(id='database',api_id=None)
    inputs['enriched-interactions']['interactions'].append(call)
    assert interaction_layers(inputs)['database']['layer']=='SR'
    call['source_views']=[{'layer':'RR','id':'actor-view'}]
    assert interaction_layers(inputs)['database']['layer'] is None


def test_scope_recomputes_both_layers_and_pre_post_recommendation_without_mutating_saved_result():
    inputs,report,concerns=sample();saved=deepcopy((inputs,report,concerns))
    result=report_view(report,concerns,inputs,'SR')
    assert [s['id'] for s in result['G']]==['gsr','gret']
    assert [s['id'] for s in result['M']]==['gret']
    assert [s['id'] for s in result['recommendation']['Q']]==['gret']
    assert result['metrics']['generation_validity']['numerator']==2
    assert result['metrics']['generation_validity']['denominator']==2
    assert result['metrics']['missing_exception_miss_rate']['numerator']==0
    assert result['metrics']['missing_exception_miss_rate']['denominator']==1
    baseline=result['recommendation_comparison']['baseline']
    after=result['recommendation_comparison']['recommended']
    assert baseline['candidate_count']==after['candidate_count']==1
    assert after['metrics']['recommendation_adoption']['denominator']==1
    assert after['metrics']['recommendation_false_positive']['denominator']==2
    assert result['evaluation_scope']['excluded_binding_counts']['G']==2
    assert result['evaluation_scope']['unresolved_interaction_ids']==['unknown']
    assert (inputs,report,concerns)==saved


def test_scope_missing_truth_is_unevaluated_and_empty_denominator_is_not_applicable():
    inputs,_,concerns=sample()
    partial=compare({'matches':concerns['G_c']},{'matches':concerns['E_c']})
    result=report_view({},partial,inputs,'SR')
    assert result['metrics']=={} and 'GT_c' not in result['concern_level']
    no_truth=compare({'matches':[]},{'matches':[]},{'matches':[]})
    empty=concern_view(no_truth,interaction_layers(inputs),'SR')
    assert empty['metrics']['generation_validity']['value'] is None
    assert empty['metrics']['generation_validity']['status']=='不适用'


def test_historical_original_and_expanded_truth_get_independent_scoped_counts():
    inputs,report,concerns=sample()
    report['original_evaluation']=deepcopy(report)
    report['original_evaluation']['concern_level']=deepcopy(concerns)
    result=report_view(report,concerns,inputs,'SR')
    assert len(result['original_evaluation']['G'])==2
    assert result['original_evaluation']['metrics']==result['metrics']


def put(project,key,stage,value):
    root=project/'run';statefile=root/'workflow_tasks.json'
    state=json.loads(statefile.read_text()) if statefile.exists() else {'tasks':{}}
    file='task_outputs/'+fingerprint(key)+'.json';write_json(root/file,{'payload':value})
    state['tasks'][key]={'stage':stage,'case':'CASE-A' if ':' in key else 'shared','status':'passed','output_file':file}
    write_json(statefile,state)
    write_json(root/'workflow_graph.json',{'nodes':[{'id':k} for k in state['tasks']]})


def save_sample(project):
    inputs,report,concerns=sample()
    for key,stage,value in [('api-map','api-map',inputs['api-map']),('api-parameters','api-parameters',inputs['api-parameters']),
                            ('CASE-A:enriched-view','enriched-view',inputs['enriched-interactions']),('CASE-A:fused-ssd','fused-ssd',inputs['enriched-interactions']),
                            ('CASE-A:concern-evaluation','concern-evaluation',concerns),('CASE-A:exception-evaluation','exception-evaluation',report),
                            ('CASE-A:gap-recommend','gap-recommend',inputs['gap-recommend'])]:put(project,key,stage,value)
    write_json(project/'run/run_manifest.json',{'complete':True,'analysis_by_case':{'CASE-A':True},'evaluation_by_case':{'CASE-A':True}})


def test_http_scope_can_switch_without_discarding_rr_display_or_rewriting_frozen_artifacts(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    app=create_app(tmp_path/'data');client=TestClient(app)
    rid=client.post('/api/projects',json={'name':'Scope','evaluation_scope':'SR','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}]}}).json()['id']
    project=app.state.workbench.run_dir(rid);save_sample(project)
    raw={p:p.read_bytes() for p in (project/'run/task_outputs').glob('*.json')}
    base='/api/projects/'+rid+'/results'
    metrics=client.get(base+'/metrics',params={'test_set':'original'}).json()
    assert metrics['cases'][0]['counts']['G']==2
    assert client.get(base+'/metrics',params={'scope':'all'}).json()['cases'][0]['counts']['G']==4
    result=client.get(base+'/CASE-A',params={'scope':'SR','test_set':'original'})
    assert result.status_code==200,result.text
    rows=result.json()['interactions']
    assert any(i['interaction']['id']=='rr' and not i['metric_in_scope'] for i in rows)
    assert client.get(base+'/metrics',params={'scope':'bad'}).status_code==400
    total=client.get(base+'/project-metrics',params={'scope':'SR','test_set':'original'}).json()
    assert total['complete'] and not total['metrics']['generation_effectiveness']['partial']
    assert total['metrics']['generation_effectiveness']['included_granularities']==['interaction']
    assert all(p.read_bytes()==v for p,v in raw.items())


def test_cli_can_read_sr_metrics_and_full_case_without_llm_calls(tmp_path,capsys):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    from scene_completion.workbench_cli import main,capabilities
    from tests.test_model_accounts_cli import FakeAPI
    app=create_app(tmp_path/'data');client=TestClient(app);api=FakeAPI(client)
    rr=tmp_path/'rr.md';sr=tmp_path/'sr.md';rr.write_text('RR');sr.write_text('SR')
    assert main(['create','--name','CLI scope','--rr',str(rr),'--sr',str(sr)],client=api)==0
    meta=json.loads(capsys.readouterr().out);assert meta['evaluation_scope']=='SR'
    rid=meta['id'];save_sample(app.state.workbench.run_dir(rid))
    assert main(['metrics','--project',rid],client=api)==0
    assert json.loads(capsys.readouterr().out)['cases'][0]['counts']['G']==2
    assert main(['metrics','--project',rid,'--case','CASE-A','--scope','all'],client=api)==0
    assert len(json.loads(capsys.readouterr().out)['interactions'])==4
    assert 'metrics' in capabilities()['commands']


def test_quality_diagnostic_snapshot_uses_project_sr_scope_and_leaves_saved_evidence_intact(tmp_path):
    from scene_completion.quality_diagnostics import freeze,build
    save_sample(tmp_path);write_json(tmp_path/'project.json',{'sources':{},'evaluation_scope':'SR'})
    before={p:p.read_bytes() for p in (tmp_path/'run/task_outputs').glob('*.json')}
    snap=freeze(tmp_path,test_set='original')
    assert snap['versions']['evaluation_scope']=='SR'
    assert {s['id'] for s in snap['outputs']['CASE-A:exception-evaluation']['G']}=={'gsr','gret'}
    assert len(snap['outputs']['CASE-A:concern-evaluation']['G_c'])==2
    report=build(tmp_path,snap,tool_only=True)
    assert not any(l['anchor'].get('interaction_id') in {'rr','unknown'} for l in report['losses'])
    assert all(p.read_bytes()==v for p,v in before.items())
