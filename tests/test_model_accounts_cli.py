from pathlib import Path
from copy import deepcopy
import json,os
import pytest
from fastapi.testclient import TestClient
from scene_completion.workbench import create_app
from scene_completion.model_accounts import save_account,public_accounts
from scene_completion.model_settings import resolve
from scene_completion.model_routing import routed_config
from scene_completion.model_client import SemanticClient
from scene_completion.workbench_cli import main,API

def source():return {'name':'CLI project','sources':{'RR':[{'name':'rr.md','content':'# RR'}],'SR':[{'name':'sr.md','content':'# SR'}]}}

def test_key_scoped_model_catalog_no_secret_response_no_fallback(tmp_path,monkeypatch):
    env=tmp_path/'.env';env.write_text('ONE=secret-one\nTWO=secret-two\nSCENE_API_KEY=unrelated-key\n')
    a=save_account(tmp_path,{'expected_revision':0,'id':'one','name':'账号A','base_url':'https://one.test/v1','models':['a','b'],'api_key_env':'ONE'},env)
    b=save_account(tmp_path,{'expected_revision':1,'id':'two','name':'账号B','base_url':'https://two.test/v1','models':['c'],'api_key_env':'TWO'},env)
    assert 'secret' not in json.dumps(b)
    x=resolve({'model_account_id':'one','agent_model':'b','api_key':'wrong'},env,tmp_path)
    assert x['api_key']=='secret-one' and x['base_url']=='https://one.test/v1'
    with pytest.raises(ValueError,match='允许模型'):resolve({'model_account_id':'one','agent_model':'c'},env,tmp_path)
    with pytest.raises(ValueError):resolve({'model_account_id':'one','agent_model':'a','role_models':{'checker':'c'}},env,tmp_path)
    env.write_text('SCENE_API_KEY=unrelated-key\n');monkeypatch.delenv('ONE',raising=False)
    assert resolve({'model_account_id':'one','agent_model':'a'},env,tmp_path)['api_key']==''
    if os.name!='nt':assert (tmp_path/'model-accounts.local.json').stat().st_mode&0o777==0o600

def test_account_edit_revision_and_blank_key_preserve(tmp_path):
    body={'expected_revision':0,'id':'one','name':'A','base_url':'http://local/v1','models':['a'],'api_key':'do-not-echo'};save_account(tmp_path,body,tmp_path/'.env')
    with pytest.raises(ValueError):save_account(tmp_path,body,tmp_path/'.env')
    save_account(tmp_path,{**body,'expected_revision':1,'api_key':'','models':['a','b']},tmp_path/'.env')
    assert resolve({'model_account_id':'one','agent_model':'b'},tmp_path/'.env',tmp_path)['api_key']=='do-not-echo'
    for patch in [{'models':[]},{'base_url':'https://secret:password@host/v1'},{'models':['bad\nmodel']}]:
        with pytest.raises(ValueError):save_account(tmp_path,{**body,'expected_revision':2,**patch},tmp_path/'.env')

def test_every_model_request_and_route_enforces_account_list(tmp_path):
    cfg={'agent_model':'a','api_key':'s','base_url':'http://test/v1','allowed_models':['a'],'role_models':{'checker':'b'}}
    with pytest.raises(ValueError):routed_config(cfg,'test-ground-truth','checker')
    sent=[];c=SemanticClient(cfg,transport=lambda *a:sent.append(a))
    with pytest.raises(ValueError):c.post('/chat/completions',{'model':'b'})
    assert not sent

def test_workbench_account_configuration_masks_secrets_and_keeps_old_reports(tmp_path):
    client=TestClient(create_app(tmp_path));rid=client.post('/api/projects',json=source()).json()['id'];body={'expected_revision':0,'id':'one','name':'A','base_url':'http://internal/v1','models':['model-a'],'api_key':'hidden-secret'}
    response=client.put('/api/model-accounts',json=body);assert response.status_code==200 and 'hidden-secret' not in response.text
    c=client.put(f'/api/projects/{rid}/config',json={'model_account_id':'one','agent_model':'model-a'});assert c.status_code==200 and c.json()['allowed_models']==['model-a']
    assert 'hidden-secret' not in client.get(f'/api/projects/{rid}').text
    assert client.put(f'/api/projects/{rid}/config',json={'model_account_id':'one','agent_model':'other'}).status_code==400
    assert client.get(f'/api/projects/{rid}/file',params={'path':'../model-accounts.local.json'}).status_code==404
    status=client.get(f'/api/projects/{rid}/execution-status').json();assert status['total']==0 and status['event_cursor']==0
    assert client.put('/api/model-accounts',json={**body,'expected_revision':1},headers={'origin':'http://evil.test'}).status_code==403

def test_execution_status_counts_real_graph_and_not_old_nodes(tmp_path):
    from scene_completion.storage import write_json
    client=TestClient(create_app(tmp_path));rid=client.post('/api/projects',json=source()).json()['id'];r=tmp_path/rid/'run'
    write_json(r/'workflow_graph.json',{'nodes':[{'id':'live','stage':'components','expected_files':['components.json']}]});write_json(r/'workflow_tasks.json',{'tasks':{'live':{'stage':'components','status':'passed'},'obsolete':{'stage':'old','status':'failed'}}})
    value=client.get(f'/api/projects/{rid}/execution-status').json();assert value['total']==value['completed']==1 and not value['pending_nodes']

class FakeAPI:
    server='http://127.0.0.1:8765'
    def __init__(self,client):self.client=client;self.requests=[]
    def call(self,path,body=None,method=None):
        self.requests.append((path,body,method));r=self.client.request(method or ('POST' if body is not None else 'GET'),'/api/'+path,json=body) if body is not None else self.client.get('/api/'+path)
        if r.status_code>=400:raise ValueError(r.text)
        return r.json()

def test_cli_creates_same_web_project_configures_account_and_reads_events(tmp_path,capsys):
    client=TestClient(create_app(tmp_path/'data'));api=FakeAPI(client);rr=tmp_path/'rr.md';sr=tmp_path/'sr.md';rr.write_text('# RR\n查询');sr.write_text('# SR\n查询')
    assert main(['create','--name','agent','--rr',str(rr),'--sr',str(sr),'--mode','auto'],client=api)==0
    rid=json.loads(capsys.readouterr().out)['id'];assert client.get('/api/projects').json()[0]['id']==rid
    assert main(['save-account','--name','内网','--base-url','http://model/v1','--model','a','--api-key-env','KEY'],client=api)==0
    account=json.loads(capsys.readouterr().out)['accounts'][0]['id']
    assert main(['configure','--project',rid,'--account',account,'--model','a'],client=api)==0;capsys.readouterr()
    assert main(['status','--project',rid],client=api)==0 and json.loads(capsys.readouterr().out)['project']==rid
    assert main(['events','--project',rid,'--after','0'],client=api)==0 and json.loads(capsys.readouterr().out)['events']==[]

def test_cli_wait_and_detach_use_web_execution_not_a_new_run(tmp_path,capsys,monkeypatch):
    rid='a'*32
    class RunAPI:
        server='http://127.0.0.1:8765'
        def __init__(self):self.calls=[];self.status=0
        def call(self,path,body=None,method=None):
            self.calls.append(path)
            if path.endswith('/run'):return {'status':'running','project_id':rid}
            if '/events/history?' in path:return {'events':[]}
            self.status+=1;return {'project':rid,'name':'test','job':{'status':'complete' if self.status>1 else 'ready'},'complete':self.status>1,'completed':2,'total':2,'event_cursor':12,'pending_nodes':[]}
    api=RunAPI();assert main(['run','--project',rid,'--wait'],client=api)==0
    rows=[json.loads(s) for s in capsys.readouterr().out.splitlines()];assert rows[-1]['kind']=='finished' and rows[-1]['complete']
    assert api.calls.count('projects/'+rid+'/run')==1 and not any('pipeline' in s for s in api.calls)
    with pytest.raises(ValueError):API('https://external.test')

def test_removed_allowed_model_does_not_hide_saved_project_reports(tmp_path):
    client=TestClient(create_app(tmp_path));rid=client.post('/api/projects',json=source()).json()['id'];body={'expected_revision':0,'id':'one','name':'A','base_url':'http://internal/v1','models':['a','b'],'api_key':'secret'}
    client.put('/api/model-accounts',json=body);client.put(f'/api/projects/{rid}/config',json={'model_account_id':'one','agent_model':'a'})
    assert client.put('/api/model-accounts',json={**body,'expected_revision':1,'models':['b'],'api_key':''}).status_code==200
    view=client.get(f'/api/projects/{rid}');assert view.status_code==200 and view.json()['config']['configuration_error']
    assert 'secret' not in view.text
    assert client.post(f'/api/projects/{rid}/run',json={}).status_code==400

def test_running_account_catalog_locked_but_future_project_routing_editable_without_budget_reset(tmp_path):
    from scene_completion.storage import write_json,read_json
    import time
    app=create_app(tmp_path);client=TestClient(app);rid=client.post('/api/projects',json=source()).json()['id'];body={'expected_revision':0,'id':'one','name':'A','base_url':'http://internal/v1','models':['a'],'api_key':'secret'}
    client.put('/api/model-accounts',json=body);client.put(f'/api/projects/{rid}/config',json={'model_account_id':'one','agent_model':'a'})
    write_json(tmp_path/rid/'job.json',{'status':'running','worker_heartbeat':time.time()})
    assert client.put('/api/model-accounts',json={**body,'expected_revision':1,'name':'changed'}).status_code==400
    assert client.put(f'/api/projects/{rid}/config',json={'model_account_id':'one','agent_model':'a'}).status_code==200
    write_json(tmp_path/rid/'job.json',{'status':'complete'})
    ledger=tmp_path/'historical-ledger.json';write_json(ledger,{'committed_tokens':1234})
    config=tmp_path/rid/'model.local.json';v=read_json(config);v.update(token_budget_limit=900000,token_budget_ledger=str(ledger));write_json(config,v)
    assert client.put(f'/api/projects/{rid}/config',json={'model_account_id':'one','agent_model':'a'}).status_code==200
    assert read_json(config)['token_budget_ledger']==str(ledger) and read_json(ledger)['committed_tokens']==1234

def test_cli_launches_real_workbench_worker_and_web_receives_node_events(tmp_path,capsys):
    from scene_completion.scheduler import TaskBlocked
    class OfflineClient:
        def __init__(self,cfg):self.config=cfg;self.base_url='http://offline';self.api_key='offline-test'
        def model(self,kind):return 'offline-test'
        def agent(self,packet):raise TaskBlocked('awaiting_configuration',{'reason':'offline fixture: model intentionally not called'})
    client=TestClient(create_app(tmp_path,client_factory=lambda cfg,root:OfflineClient(cfg)));api=FakeAPI(client)
    rid=client.post('/api/projects',json={**source(),'review_mode':'auto'}).json()['id']
    assert main(['run','--project',rid,'--wait','--poll','0.2','--timeout','30'],client=api)==2
    rows=[json.loads(row) for row in capsys.readouterr().out.splitlines()];assert rows[0]['kind']=='started' and rows[-1]['kind']=='finished'
    snapshot=client.get(f'/api/projects/{rid}/execution-status').json();assert snapshot['total'] and snapshot['pending_nodes'] and not snapshot['complete']
    events=client.get(f'/api/projects/{rid}/events/history').json()['events'];assert any(e['kind']=='task_status' for e in events)
    assert any(e['kind']=='execution_event' for e in rows)
