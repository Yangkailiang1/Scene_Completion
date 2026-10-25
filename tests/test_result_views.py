import pytest
from scene_completion.result_views import ResultView
from scene_completion.storage import write_json, fingerprint
from scene_completion.project_review import pending_view
from tests.test_project_review import pending_fixture


def fixture(project):
    root=project/'run';state={}
    def put(key,stage,payload,status='passed'):
        file='task_outputs/'+fingerprint(key)+'.json'
        write_json(root/file,{'payload':payload})
        state[key]={'stage':stage,'case':key.split(':')[0] if ':' in key else 'shared','status':status,'output_file':file}
    interaction={'id':'i1','sequence':1,'sender':{'name':'开发者'},'receiver':{'name':'平台'},'operation':{'name':'查询'},'data':{'sequence':[]}}
    put('rr-use-cases','use-case-extract',{'cases':[{'id':'RR1','name':'查询记忆库'}]})
    put('use-case-align','use-case-align',{'groups':[{'id':'C','rr_ids':['RR1'],'sr_ids':[]}]})
    put('C:enriched-view','enriched-view',{'interactions':[interaction]})
    def s(id,iid='i1'):return {'id':id,'interaction_id':iid,'concern_key':'key','cause':id}
    put('C:exception-generate','exception-generate',{'scenarios':[s('early')]})
    put('C:missing-report','missing-report',{'G':[s('g')],'E':[s('e')],'M':[s('g')]})
    put('C:exception-evaluation','exception-evaluation',{'G':[s('g')],'E':[s('e')],'GT':[s('gt'),s('unbound','unknown')],'metrics':{'generation_validity':{'value':100}}})
    put('C:fused-ssd','fused-ssd',{'interactions':[interaction]})
    put('C:fused-ssd--part-old','fused-ssd',{'interactions':[]})
    put('components','components',{})
    put('C:failed','rr-ssd',{},'failed')
    write_json(root/'workflow_tasks.json',{'tasks':state})
    write_json(root/'workflow_graph.json',{'nodes':[{'id':k} for k in state if '--part-' not in k]})
    write_json(root/'run_manifest.json',{'complete':True,'registry_hash':'frozen','analysis_by_case':{'C':True}})
    write_json(root/'registry_used/frozen.json',{'definitions':{'key':{'label':'执行时定义'}}})
    from scene_completion.concern_registry import default_registry
    write_json(root/'registry_override.json',default_registry())
    folder=root/'artifacts'/fingerprint('C')[:12];folder.mkdir(parents=True)
    (folder/'fused-ssd.svg').write_text('<svg/>')
    (folder/'fused-ssd--part-old.svg').write_text('<svg/>')
    (folder/'failed.svg').write_text('<svg/>')
    shared=root/'artifacts/shared';shared.mkdir();(shared/'components.svg').write_text('<svg/>')


def test_results_are_lazy_snapshot_based_and_do_not_reclassify_or_hide_unbound(tmp_path):
    fixture(tmp_path);view=ResultView(tmp_path);index=view.index()
    assert index['complete'] and index['cases'][0]['name']=='查询记忆库'
    assert 'interactions' not in index and 'definitions' not in index
    assert {a['key'] for a in index['artifacts']}=={'components','C:fused-ssd'}
    v=view.detail('C');row=v['interactions'][0]
    assert {k:[s['id'] for s in a] for k,a in row['channels'].items()}=={'G':['g'],'E':['e'],'GT':['gt']}
    assert row['missing_ids']==['g'] and v['unbound']['GT'][0]['id']=='unbound'
    assert v['definitions']['key']['label']=='执行时定义'
    assert row['channels']['G'][0]['lazy_detail'] and 'source_refs' not in row['channels']['G'][0]
    assert view.scenario('C','G','g')['id']=='g'
    with pytest.raises(ValueError,match='未知用例'):view.detail('../invalid')


def test_business_default_queue_keeps_diagnostics_without_counting_as_anomalies(tmp_path):
    state=pending_fixture(tmp_path);root=tmp_path/'run'
    for stage in ('concern-match','enriched-view'):
        key='C:'+stage;file='task_outputs/'+fingerprint(key)+'.json'
        value={'pending':[{'interaction_id':'i','reason':'内部规则未声明','source_refs':[]}]}
        write_json(root/file,{'payload':value});state[key]={'case':'C','stage':stage,'status':'passed','output_file':file,'output_hash':fingerprint(value)}
    write_json(root/'workflow_tasks.json',{'tasks':state});write_json(root/'workflow_graph.json',{'nodes':[{'id':k} for k in state]})
    v=pending_view(tmp_path)
    assert v['count']==2 and v['queue_counts']['rules']['unresolved']==1 and v['queue_counts']['structure']['unresolved']==1
    assert pending_view(tmp_path,queue='all')['count']==4
    assert pending_view(tmp_path,queue='rules')['items'][0]['origins']==['C:concern-match']


def test_results_http_returns_only_selected_case_and_real_downloads(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    app=create_app(tmp_path/'data');client=TestClient(app)
    rid=client.post('/api/projects',json={'name':'A','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}]}}).json()['id']
    fixture(app.state.workbench.run_dir(rid))
    base='/api/projects/'+rid
    index=client.get(base+'/results');assert index.status_code==200
    assert len(index.json()['cases'])==1
    d=client.get(base+'/results/C');assert d.status_code==200 and d.json()['interactions'][0]['channels']['G'][0]['id']=='g'
    image=next(a for a in index.json()['artifacts'] if a['stage']=='fused-ssd')['files'][0]
    assert client.get(base+'/file',params={'path':image['path']}).status_code==200
    assert client.get(base+'/results/unknown').status_code==400
