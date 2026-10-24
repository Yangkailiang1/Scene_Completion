"""Merged API table preserves drafts, identities, empty parameters and directions."""
from copy import deepcopy
import io,zipfile
from scene_completion.api_catalog import combine,saved_catalog
from scene_completion.contracts import PROTOCOL
from scene_completion.storage import write_json,fingerprint


def fixtures():
    mapping={'services':[{'name':'ServiceA','interfaces':[{'id':'API-A','name':'List','method':'GET','address':'/items','source_refs':[]}]}]}
    params={'apis':[{'id':'API-A','name':'List','address':'/items','parameters':[{'name':'page','location':'query','data_type':'integer','required':False,'default':1,'constraints':[],'source_refs':[]}]}]}
    return mapping,params


def test_combined_table_preserves_owner_metadata_directions_and_defaults():
    m,p=fixtures();p['apis'][0]['parameters'].append({**p['apis'][0]['parameters'][0],'name':'items','location':'response','required':True,'default':None})
    v=combine(m,p,mapping_status='已完成',parameters_complete=True)
    assert v['complete'] and v['identity_pending']==0
    assert [r['direction'] for r in v['rows']]==['输入','输出']
    assert v['rows'][0]['default']==1 and v['rows'][0]['service']=='ServiceA'
    assert v['rows'][0]['required']=='可选'


def test_unknown_and_empty_parameters_are_not_confused():
    m,p=fixtures();v=combine(m,{},mapping_status='已完成')
    assert not v['complete'] and v['rows'][0]['name']=='尚未取得参数结果'
    p['apis'][0]['parameters']=[]
    v=combine(m,p,mapping_status='已完成',parameters_complete=True)
    assert v['complete'] and len(v['rows'])==1 and v['rows'][0]['name']=='文档未列出参数'


def test_path_fallback_must_be_unique_in_both_directions():
    m,p=fixtures();p['apis'][0]['id']='different-id'
    assert combine(m,p)['identity_pending']==0
    m['services'][0]['interfaces'].append({**m['services'][0]['interfaces'][0],'id':'OTHER','method':'POST'})
    v=combine(m,p);assert v['identity_pending']==3 and len(v['rows'])==3
    assert v['rows'][-1]['service'] is None
    # Conflicting IDs must not join across different paths.
    m,p=fixtures();p['apis'][0]['address']='/wrong'
    assert combine(m,p)['identity_pending']==2


def test_saved_partial_children_and_api_endpoint_download(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    app=create_app(tmp_path);client=TestClient(app)
    meta=client.post('/api/projects',json={'name':'test','sources':{r:[{'name':r+'.md','content':'# document'}] for r in ('RR','SR')}}).json()
    rid=meta['id'];root=tmp_path/rid/'run';m,p=fixtures()
    write_json(root/'workflow_tasks.json',{'tasks':{'api-map':{'status':'awaiting_review'},'api-parameters-part-a':{'status':'passed','output_file':'task_outputs/a.json'}}})
    write_json(root/'reviews'/(fingerprint('api-map')+'.json'),{'status':'draft','payload':m})
    write_json(root/'task_outputs/a.json',{'protocol':PROTOCOL,'payload':p})
    v=client.get(f'/api/projects/{rid}/api-catalog').json()
    assert not v['complete'] and v['rows'][0]['mapping_status']=='待审核' and v['rows'][0]['parameter_status']=='已完成'
    assert v==saved_catalog(root)
    assert (root/'artifacts/shared/api-catalog.json').exists()
    md=client.get(f'/api/projects/{rid}/api-catalog?format=md')
    assert '中间结果' in md.text and '服务名称' in md.text and 'attachment' in md.headers['content-disposition']
    assert client.get(f'/api/projects/{rid}/api-catalog?format=bad').status_code==400
    archive=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{rid}/export').content))
    assert 'run/artifacts/shared/api-catalog.md' in archive.namelist()
    # Rejected/regenerated drafts cannot enter the visible merged table.
    write_json(root/'workflow_tasks.json',{'tasks':{'api-map':{'status':'rejected'}}})
    assert not client.get(f'/api/projects/{rid}/api-catalog').json()['rows']
