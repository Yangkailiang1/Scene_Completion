from copy import deepcopy
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from scene_completion.workbench import Workbench,create_app
from scene_completion.storage import read_json,write_json,fingerprint
from scene_completion.execution_control import control
from scene_completion.worker_runtime import read_job
from scene_completion.project_review import project_registry,registry_view
from scene_completion.concern_registry import default_registry,registry_scope
from scene_completion.concern_presentation import paths
from scene_completion.scenario_patterns import normalize_settings,default_library
from tests.test_workflow import memory_inputs


def make(root):
    s=Workbench(root);m=s.create({'name':'control','sources':{'RR':[{'name':'rr.md','content':'# RR'}],'SR':[{'name':'sr.md','content':'# SR'}]}})
    return s,m['id'],s.run_dir(m['id'])


def test_pause_waits_for_current_call_and_resume_is_explicit(tmp_path,monkeypatch):
    s,rid,p=make(tmp_path/'data');write_json(p/'job.json',{'status':'running','worker_token':'test'})
    saved=p/'run/artifacts/success.json';write_json(saved,{'keep':True})
    assert control(s,rid,{'action':'pause','dry_run':True})['saved'] is False
    assert not (p/'run/pause_requested.json').exists()
    control(s,rid,{'action':'pause'})
    assert read_job(p)['control_state']=='pausing'
    assert not (p/'worker-stop.json').exists()
    with pytest.raises(ValueError,match='已由用户'):s.start(rid)
    with pytest.raises(ValueError,match='等待当前请求'):control(s,rid,{'action':'resume'})
    write_json(p/'job.json',{'status':'paused','reason':'user_pause'})
    monkeypatch.setattr(s,'start',lambda rid:{'status':'running','project_id':rid})
    assert control(s,rid,{'action':'resume'})['status']=='running'
    assert not (p/'run/pause_requested.json').exists() and read_json(saved)=={'keep':True}
    s.pool.shutdown()


def test_stop_uses_only_this_workers_token_and_resume_failure_preserves_hold(tmp_path,monkeypatch):
    s,rid,p=make(tmp_path/'data');write_json(p/'job.json',{'status':'running','worker_token':'only-this-worker'})
    control(s,rid,{'action':'stop'})
    assert read_json(p/'worker-stop.json')['worker_token']=='only-this-worker'
    assert read_job(p)['control_state']=='stopping'
    write_json(p/'job.json',{'status':'interrupted','reason':'user_stop'})
    def fail(rid):raise ValueError('missing model')
    monkeypatch.setattr(s,'start',fail)
    with pytest.raises(ValueError):control(s,rid,{'action':'resume'})
    assert read_json(p/'run/pause_requested.json')['by']=='user'
    s.pool.shutdown()


def test_execution_control_api_and_cli_share_contract(tmp_path):
    from scene_completion.workbench_cli import main,capabilities
    with TestClient(create_app(tmp_path/'data')) as c:
        rid=c.post('/api/projects',json={'name':'x','sources':{'RR':[{'name':'r.md','content':'# RR'}],'SR':[{'name':'s.md','content':'# SR'}]}}).json()['id']
        r=c.post('/api/projects/'+rid+'/execution-control',json={'action':'pause'});assert r.status_code==200 and r.json()['status']=='paused'
    class Client:
        def call(self,path,body=None,method=None):assert path.endswith('/execution-control') and body=={'action':'stop','dry_run':True};return {'saved':False}
    assert main(['execution-control','--project',rid,'--action','stop','--dry-run'],Client())==0
    assert 'execution-control' in capabilities()['commands']


def test_new_taxonomy_paths_cover_crud_business_technology_and_global():
    defs=default_registry()['definitions']
    for group in ('create','update','delete'):
        assert '第二层' in '/'.join(paths('service.crud.'+group+'.idempotency',defs)[0])
    assert '第三层' in '/'.join(paths('service.analysis_generation.execution_deadline',defs)[0])
    assert '第四层' in '/'.join(paths('database.storage_validity',defs)[0])
    assert paths('global.cascade_operation',defs)[0][0]=='全局业务依赖级关注点'
    assert paths('api.data.validity',defs)[0][-1]=='输入数据' and len(paths('api.data.range',defs))==2
    assert not defs['api.data.legality']['enabled'] and not defs['service.analysis_generation.resource_consumption']['enabled']


def test_existing_project_migrates_once_with_history_and_pattern_support(tmp_path):
    p=tmp_path/'p';p.mkdir();old=default_registry();old.pop('framework_policies')['four_level_taxonomy_20261103']
    old['framework_policies']={}
    for key in ('api.data.validity','database.special_characters','database.storage_validity'):old['definitions'].pop(key)
    old['profiles']['technology']['database']=[k for k in old['profiles']['technology']['database'] if k in old['definitions']]
    old['definitions']['service.analysis_generation.resource_consumption']['enabled']=True
    old['profiles']['functional']['analysis_generation'].append('service.analysis_generation.resource_consumption')
    old['hash']=fingerprint({k:v for k,v in old.items() if k!='hash'});write_json(p/'run/registry_override.json',old)
    frozen=p/'run/report_versions/old/metrics.json';write_json(frozen,{'old':1})
    new=project_registry(p);count=len(list((p/'concern_versions').glob('*.json')))
    assert 'api.data.validity' in new['definitions'] and not new['definitions']['service.analysis_generation.resource_consumption']['enabled']
    project_registry(p);assert len(list((p/'concern_versions').glob('*.json')))==count and read_json(frozen)=={'old':1}
    with registry_scope(new):
        prior={'library':{'version':'scenario-patterns-v1','patterns':[]}}
        settings=normalize_settings(prior)
        assert 'rule.api.data.validity' in {p['id'] for p in settings['library']['patterns']}


def test_input_validity_requires_reference_evidence_and_is_not_output_validation():
    from scene_completion.concern_hierarchy import applicability
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];p=x['api-parameters']['apis'][0]['parameters'][0]
    match={'concern_key':'api.data.validity','object':p['name'],'scope':'interface','data_location':p['location'],'activation_evidence':[]}
    assert applicability(match,i,x)[0]=='pending'
    match['activation_evidence']=[{'kind':'resource_lookup','field':p['name'],'condition':'引用的记忆实例存在且有效','value':'必须存在','source_refs':p['source_refs'],'status':'explicit','unit':None,'constraint_kind':None}]
    assert applicability(match,i,x)[0]=='applicable'
