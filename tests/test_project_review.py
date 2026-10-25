from copy import deepcopy
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from scene_completion.workbench import create_app
from scene_completion.concern_registry import registry,default_registry
from scene_completion.project_review import save_registry,registry_view,pending_view,decide_pending
from scene_completion.storage import write_json,read_json,fingerprint
from scene_completion.workflow import Execution,build_pipeline
from tests.test_workflow import fake_pipeline,memory_inputs
from scene_completion.concern_hierarchy import resolve_matches
from scene_completion.exception_generation import data_exceptions


def custom_definition():
    return {'key':'custom.query_quality','label':'自定义查询质量','description':'本项目明确的查询质量要求，必须有正向业务依据。','layer':'functional','group':'query_retrieval','parents':[],'kind':'check','guard':'business','failure_family':'custom.query_quality','operation_kinds':['read'],'technology':None,'enabled':True}


def test_project_registry_versions_are_isolated_and_used_by_pipeline(tmp_path):
    p=tmp_path/'one';other=tmp_path/'two';p.mkdir();other.mkdir();base=registry_view(p)
    edited=deepcopy(base['registry']);edited['definitions']['custom.query_quality']=custom_definition()
    edited['definitions']['api.data.range']['enabled']=False
    edited['definitions']['api.data.type']['label']='项目参数类型检查'
    result=save_registry(p,{'expected_hash':base['current_hash'],'registry':edited,'note':'项目审核定义'})
    assert result['revision']==1 and project_registry_hash(other)==base['current_hash']
    assert registry_view(p,base['current_hash'])['read_only']
    with pytest.raises(ValueError,match='版本已变化'):save_registry(p,{'expected_hash':base['current_hash'],'registry':edited})
    (tmp_path/'fixtures').mkdir();rr,sr,t,m=fake_pipeline(tmp_path/'fixtures');seen=[]
    m['normal-rules']=lambda packet:(seen.append(packet['input']['registry']['hash']) or {'rules':[],'pending':[]})
    ex=Execution(p/'run',mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert seen and set(seen)=={result['current_hash']} and ex.manifest['registry_hash']==result['current_hash']
    assert registry()['hash']==default_registry()['hash']  # no process-global leak
    from scene_completion.concern_registry import registry_scope
    with registry_scope(result['registry']):
        x=memory_inputs();x['registry']=result['registry'];x['concern-match']=resolve_matches(x,[])
        assert not any(s['concern_key']=='api.data.range' for s in data_exceptions(x))
    assert project_registry_hash(other)==base['current_hash']


def test_parallel_projects_keep_separate_registry_contexts(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier,Event
    barrier=Barrier(2)
    def execute(name,custom):
        folder=tmp_path/name;folder.mkdir();fixture=folder/'docs';fixture.mkdir()
        if custom:
            old=registry_view(folder);value=deepcopy(old['registry']);value['definitions']['custom.query_quality']=custom_definition()
            save_registry(folder,{'expected_hash':old['current_hash'],'registry':value})
        expected=project_registry_hash(folder);rr,sr,t,m=fake_pipeline(fixture);first=Event();seen=[]
        def capture(packet):
            if not first.is_set():first.set();barrier.wait(timeout=15)
            seen.append(registry()['hash']);return {'rules':[],'pending':[]}
        m['normal-rules']=capture;ex=Execution(folder/'run',mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
        assert set(seen)=={expected};return expected
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(execute,'A',True);b=pool.submit(execute,'B',False)
        assert a.result()!=b.result()


def test_definition_change_archives_report_with_its_original_registry(tmp_path):
    docs=tmp_path/'docs';docs.mkdir();project=tmp_path/'project';project.mkdir()
    rr,sr,t,m=fake_pipeline(docs);root=project/'run'
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    before=(root/'missing_report.md').read_bytes();old=registry_view(project)
    edited=deepcopy(old['registry']);edited['definitions']['api.data.type']['description']='项目级类型规则的新定义'
    save_registry(project,{'expected_hash':old['current_hash'],'registry':edited})
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    history=registry_view(project,old['current_hash'])
    assert history['read_only'] and len(history['reports'])==1
    assert (project/history['reports'][0]['path']).read_bytes()==before


def test_equal_pending_text_does_not_merge_generation_and_checker_channels(tmp_path):
    state=pending_fixture(tmp_path);root=tmp_path/'run'
    key='C:existing-bind--part-b';record=state[key];v=read_json(root/record['output_file'])
    v['payload']['bindings'][0].update(interaction_id='i',basis='缺少具体阈值')
    write_json(root/record['output_file'],v);record['output_hash']=fingerprint(v)
    write_json(root/'workflow_tasks.json',{'tasks':state})
    rows=pending_view(tmp_path)['items']
    assert len(rows)==2 and {r['source_channel'] for r in rows}=={'positive','existing_e'}
    assert all(len(r['origins'])==1 for r in rows)


def project_registry_hash(p):return registry_view(p)['current_hash']


def test_registry_rejects_cycles_and_retired_parent_of_active_child(tmp_path):
    b=registry_view(tmp_path);r=deepcopy(b['registry']);r['definitions']['service.base.request_data']['parents']=['api.data.type']
    with pytest.raises(ValueError,match='cycle'):save_registry(tmp_path,{'expected_hash':b['current_hash'],'registry':r})
    r=deepcopy(b['registry']);r['definitions']['service.base.request_data']['enabled']=False
    with pytest.raises(ValueError,match='子关注点'):save_registry(tmp_path,{'expected_hash':b['current_hash'],'registry':r})
    assert registry_view(tmp_path)['current_hash']==b['current_hash']


def pending_fixture(project):
    root=project/'run';ref=[{'source_id':'doc','line_start':2,'line_end':2,'quote':'明确的原文依据'}]
    state={};nodes=[]
    for key,case,stage in [('C:normal-rules--part-a','C','normal-rules'),('C:existing-bind--part-b','C','existing-bind')]:
        value={'pending':[{'interaction_id':'i','reason':'缺少具体阈值','source_refs':ref}]} if stage=='normal-rules' else {'bindings':[{'branch_id':'B','interaction_id':'j','status':'pending','basis':'已有异常尚未确定对应步骤','source_refs':ref}]}
        file='task_outputs/'+fingerprint(key)+'.json';v={'task':stage,'payload':value};write_json(root/file,v)
        state[key]={'status':'passed','case':case,'stage':stage,'output_file':file,'output_hash':fingerprint(v)};nodes.append({'id':key})
    write_json(root/'workflow_tasks.json',{'tasks':state});write_json(root/'workflow_graph.json',{'nodes':nodes});return state


def test_pending_decisions_keep_history_and_do_not_leak_checker_feedback(tmp_path):
    state=pending_fixture(tmp_path);before={k:(tmp_path/'run'/v['output_file']).read_bytes() for k,v in state.items()}
    rows=pending_view(tmp_path);assert rows['counts']['unresolved']==2
    a=next(i for i in rows['items'] if i['interaction_id']=='i')
    row=decide_pending(tmp_path,a['id'],{'choice':'not_anomaly','revision':0,'note':'用户确认不算异常'})
    assert row['choice']=='not_anomaly' and pending_view(tmp_path)['count']==1
    from scene_completion.node_conversations import Conversations
    store=Conversations(tmp_path/'run');assert store.list('C:normal-rules--part-a') and not store.list('C:existing-bind--part-b')
    e=pending_view(tmp_path)['items'][0]
    decide_pending(tmp_path,e['id'],{'choice':'anomaly','concern_key':'service.base.availability','revision':0})
    assert len(read_json(tmp_path/'pending_decisions.json')['history'])==2
    assert all((tmp_path/'run'/v['output_file']).read_bytes()==before[k] for k,v in state.items())
    with pytest.raises(ValueError,match='审核已变化'):decide_pending(tmp_path,a['id'],{'choice':'needs_info','revision':0})
    with pytest.raises(ValueError,match='具体关注点'):decide_pending(tmp_path,a['id'],{'choice':'anomaly','concern_key':'not.exists','revision':1})


def test_review_http_api_and_linked_project_download(tmp_path):
    app=create_app(tmp_path/'data');client=TestClient(app)
    a=client.post('/api/projects',json={'name':'A','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}]}}).json()['id']
    p=app.state.workbench.run_dir(a);pending_fixture(p)
    assert client.get(f'/api/projects/{a}/registry').status_code==200
    items=client.get(f'/api/projects/{a}/pending').json()['items']
    r=client.post(f'/api/projects/{a}/pending/{items[0]["id"]}',json={'choice':'not_anomaly','revision':0})
    assert r.status_code==200 and client.get(f'/api/projects/{a}/pending').json()['count']==1
    target=tmp_path/'linked';p.rename(target);p.symlink_to(target,target_is_directory=True)
    write_json(target/'run/artifacts/shared/example.json',{'ok':True})
    assert client.get(f'/api/projects/{a}/file?path=run/artifacts/shared/example.json').status_code==200
