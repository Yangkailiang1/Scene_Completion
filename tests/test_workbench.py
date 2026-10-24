"""Business review and real Deep Agents execution tested without paid model calls."""
from copy import deepcopy
from pathlib import Path
import json,time,io,zipfile
import pytest
from scene_completion.contracts import packet,registry,PROTOCOL
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.reviews import Reviews
from scene_completion.validation import validate_result
from scene_completion.use_cases import select_documents
from scene_completion.interaction_types import classify
from scene_completion.storage import read_json
from tests.test_workflow import fake_pipeline,exchange,R


def test_manual_confirmation_blocks_downstream_and_survives_process_restarts(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);root=tmp_path/'run';calls=[]
    mocks={k:(lambda p,v=v:(calls.append(p['task']),v(p) if callable(v) else deepcopy(v))[1]) for k,v in m.items()}
    ex=Execution(root,mocks=mocks,config={'review_mode':'manual'});build_pipeline(ex,rr,sr,t)
    result=ex.finish();assert not result['complete']
    assert 'exception-generate' not in calls and 'fused-ssd' not in calls
    assert ex.scheduler.state['tasks']['components']['status']=='awaiting_review'
    for _ in range(12):
        store=Reviews(root,'manual')
        for file in store.root.glob('*.json'):
            draft=read_json(file)
            if draft['status']=='draft':store.decide(draft['key'],'approve',expected_revision=draft['revision'],expected_input_hash=draft['input_hash'])
        ex=Execution(root,mocks=mocks,config={'review_mode':'manual'});build_pipeline(ex,rr,sr,t);result=ex.finish()
        if result['complete']:break
    assert result['analysis_complete'] and result['complete']
    assert calls.count('fused-ssd')==1
    assert (root/'missing_report.json').exists()


def test_review_edits_are_input_bound_and_revalidate_sources(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);root=tmp_path/'run'
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    store=Reviews(root);v=store.read('components');edited=deepcopy(v['payload'])
    edited['components'][0]['source_refs'][0]['quote']='fabricated source text'
    with pytest.raises(ValueError):store.decide('components','approve',expected_revision=v['revision'],expected_input_hash=v['input_hash'],value=edited)
    good=deepcopy(v['payload']);good['components'][0]['source_status']='inferred'
    store.decide('components','approve',expected_revision=v['revision'],expected_input_hash=v['input_hash'],value=good)
    with pytest.raises(ValueError,match='changed'):store.decide('components','approve',expected_revision=v['revision'],expected_input_hash=v['input_hash'])
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert ex.reviews.read('components')['payload']['components'][0]['source_status']=='inferred'
    assert len(list((root/'reviews/versions').glob('*.json')))>1


def test_pending_case_correspondence_is_visible_not_falsely_complete(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path)
    m['use-case-align']={'groups':[{'id':'UC-X','rr_ids':['UC-X'],'sr_ids':['UC-X'],'status':'pending','reason':'需要业务确认目标是否一致','source_refs':[{'source_id':rr[0]['source_id'],'line_start':1,'line_end':1,'quote':rr[0]['lines'][0]['text']}]}]}
    ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,t);result=ex.finish()
    assert not result['complete'] and result['case_correspondence'][0]['status']=='pending'
    assert 'UC-X:fused-ssd' not in result['tasks']


def test_mismatched_ids_can_have_one_to_many_correspondence():
    from scene_completion.use_cases import validate_catalogue
    inputs={'rr-cases':{'cases':[{'id':'BUY'}]},'sr-cases':{'cases':[{'id':'ORDER'},{'id':'PAY'}]}}
    value={'groups':[{'id':'purchase','rr_ids':['BUY'],'sr_ids':['ORDER','PAY'],'status':'confirmed','reason':'explicit refinement','source_refs':R}]}
    validate_catalogue('use-case-align',value,inputs)
    value['groups'][0]['sr_ids'].pop()
    with pytest.raises(ValueError,match='catalogue'):validate_catalogue('use-case-align',value,inputs)


def test_source_case_selection_keeps_E_but_positive_projection_hides_it():
    from scene_completion.source_documents import normal_projection
    doc={'source_id':'d','channel':'existing','name':'rr.md','lines':[{'number':1,'text':'# A'},{'number':2,'text':'查询'},{'number':3,'text':'## 异常'},{'number':4,'text':'不存在'},{'number':5,'text':'# B'},{'number':6,'text':'新增'}]}
    a={'source_ranges':[{'source_id':'d','start':1,'end':2}]};b={'source_ranges':[{'source_id':'d','start':5,'end':6}]}
    selected=select_documents([doc],[a],[a,b])
    assert selected[0]['lines'][-1]['number']==4
    assert '不存在' not in str(normal_projection(selected)) and '新增' not in str(selected)


def test_return_preserves_original_caller_and_boundary_identity():
    req=exchange(layer='RR');ret=deepcopy(req);ret.update(id='ret',parent_id=req['id'],direction='return',sequence=2);ret['sender'],ret['receiver']=ret['receiver'],ret['sender']
    assert classify(req,[req,ret])==classify(ret,[req,ret])
    assert classify(req,[req])['kind']=='actor_system'
    req['sender'].update(name='LocalService',position='内部服务');req['receiver'].update(name='RemoteLLM',position='外部Actor（系统）')
    assert classify(req,[req])=={'kind':'service_service','caller':'LocalService','provider':'RemoteLLM','caller_location':'internal','provider_location':'external'}


def test_fused_ssd_rejects_invented_return_and_wrong_layer(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path)
    p={'task':'fused-ssd','input':{'RR':rr,'SR':sr,'case-group':{'id':'UC-X'}}}
    value=m['fused-ssd'](p);inputs={'RR':rr,'SR':sr,'case-group':{'id':'UC-X'},'components':m['components']}
    validate_result('fused-ssd',value,inputs)
    bad=deepcopy(value['interactions'][1]);bad.update(id='bad-return',sequence=2,direction='return',parent_id='rr-call')
    value['interactions'].append(bad)
    with pytest.raises(ValueError,match='within its layer'):validate_result('fused-ssd',value,inputs)


def test_real_deepagents_tools_submit_using_existing_transport_and_no_host_access(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient,role_for
    sent=[]
    def transport(url,key,body,timeout,retries):
        sent.append(body)
        if len(sent)==1:
            message={'content':'','tool_calls':[{'id':'one','type':'function','function':{'name':'read_file','arguments':json.dumps({'file_path':'/etc/passwd'})}}]}
        elif len(sent)==2:
            message={'content':'','tool_calls':[{'id':'two','type':'function','function':{'name':'submit_result','arguments':json.dumps({'payload':{'services':[]}})}}]}
        else:message={'content':'完成'}
        return {'choices':[{'message':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}],'usage':{'total_tokens':30}}
    client=DeepAgentsClient({'base_url':'http://offline.test/v1','agent_model':'customer-qwen38','api_key':'offline-test','max_tokens':1000,'run_root':str(tmp_path)},transport=transport)
    p=packet('api-map',{'SR':[]});p['skill_text']='---\nname: scene-api-map\ndescription: API mapping\n---\nExtract declared services.'
    result=client.agent(p)
    assert result['services']==[] and len(sent)==3
    assert result['execution_model_evidence']['requested_model']=='customer-qwen38'
    assert all(b['model']=='customer-qwen38' for b in sent)
    assert 'root:' not in json.dumps(sent[-1])
    assert role_for('existing-extract')=='checker' and role_for('fused-ssd')=='modeler'
    assert list((tmp_path/'agent_traces').glob('*.json'))


def test_frontend_api_persists_projects_masks_credentials_and_exports_sources(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    client=TestClient(create_app(tmp_path))
    assert client.get('/').status_code==200
    body={'name':'审核示例','review_mode':'manual','sources':{'RR':[{'name':'rr.md','content':'# RR\n查询'}],'SR':[{'name':'sr.md','content':'# SR\n查询'}]}}
    p=client.post('/api/projects',json=body).json();rid=p['id']
    response=client.put(f'/api/projects/{rid}/config',json={'base_url':'http://model.internal/v1','agent_model':'customer-model','api_key':'test-secret'})
    assert response.status_code==200 and 'test-secret' not in response.text
    assert 'test-secret' not in client.get(f'/api/projects/{rid}').text
    assert client.get(f'/api/projects/{rid}/file',params={'path':'model.local.json'}).status_code==404
    assert client.get(f'/api/projects/{rid}/file',params={'path':'../../etc/passwd'}).status_code==404
    archive=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{rid}/export').content))
    assert 'sources/RR-0.md' in archive.namelist() and 'model.local.json' not in archive.namelist()
    assert client.post(f'/api/projects/{rid}/run',json={},headers={'origin':'http://other-site.test'}).status_code==403
    reopened=TestClient(create_app(tmp_path));assert reopened.get('/api/projects').json()[0]['name']=='审核示例'


def test_changed_execution_identity_does_not_reuse_auto_review_drafts(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);calls=[]
    mocks={k:(lambda p,v=v:(calls.append(p['task']),v(p) if callable(v) else deepcopy(v))[1]) for k,v in m.items()}
    root=tmp_path/'run'
    ex=Execution(root,mocks=mocks,config={'max_tokens':1000});build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    calls.clear()
    ex=Execution(root,mocks=mocks,config={'max_tokens':2000});build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert 'components' in calls and 'fused-ssd' in calls


def test_review_is_excluded_while_execution_owns_run_lock(tmp_path):
    from scene_completion.scheduler import run_lock
    rr,sr,t,m=fake_pipeline(tmp_path);root=tmp_path/'run'
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);ex.finish();store=Reviews(root);v=store.read('components')
    with run_lock(root):
        with pytest.raises(ValueError,match='active'):store.decide('components','approve',expected_revision=v['revision'],expected_input_hash=v['input_hash'])


def test_artifact_links_identify_their_case_and_drafts_have_editable_diagrams(tmp_path):
    from scene_completion.workbench import Workbench
    wb=Workbench(tmp_path/'data')
    p=wb.create({'name':'draft diagrams','sources':{'RR':[{'name':'rr.md','content':'# UC-X\nnormal request'}],'SR':[{'name':'sr.md','content':'# UC-X\nnormal call'}]}})
    project=wb.run_dir(p['id']);rr,sr,t,m=fake_pipeline(tmp_path)
    ex=Execution(project/'run',mocks=m,config={'review_mode':'manual'});build_pipeline(ex,rr,sr,t);ex.finish()
    items=wb.snapshot(p['id'])['artifacts']
    assert any(a['task_key']=='components' and a['name']=='components.svg' and '/reviews/previews/' in a['path'] for a in items)
    assert all(a['task_key']=='components' for a in items if a['name']=='components.svg')
