from copy import deepcopy
from pathlib import Path
import json,time
import pytest
from scene_completion.contracts import PROTOCOL,packet,registry
from scene_completion.execution_events import EventStore,bind
from scene_completion.node_conversations import Conversations
from scene_completion.scheduler import CallGate,TaskBlocked,Scheduler,Task
from scene_completion.exception_comparison import missing_report,compare_report,broad_covers
from scene_completion.inverse_alignment import expand_inverse,expand_truth,canonical_fused
from scene_completion.validation import validate_result
from tests.test_workflow import memory_inputs,data_exceptions,exchange,R,scenario,decision,fake_pipeline

def inverse_fixture():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    s=scenario('parameter-branch',status='explicit');s.update(interaction_id=i['id'],object=i['receiver']['name'],operation=i['operation']['name'],cause='invalid_parameters',conditions=['请求参数非法'],concern_key='api.data.legality',scope='interface',data_location=None,original_branch_id='b',coverage_kind='input_parameters')
    inputs={'fused-ssd':{'interactions':[i],'rr_sr_links':[]},'normal-constraints':x['api-parameters'],'branches':{'branches':[{'id':'b','description':'参数非法','source_refs':R}]},'bindings':{'bindings':[{'branch_id':'b','interaction_id':i['id'],'status':'confirmed'}]}}
    return x,s,inputs

def test_broad_input_branch_covers_eight_rules_but_never_other_interactions_or_response():
    x,s,inputs=inverse_fixture();g=data_exceptions(x);e=expand_inverse({'scenarios':[s]},inputs)['scenarios']
    assert len([a for a in e if a.get('coverage_kind')=='exact'])==8
    m=missing_report(g,e,[]);assert m['M']==[] and len({p['checker_scenario_id'] for p in m['full_matches']})==8
    response=deepcopy(g[0]);response.update(id='response',interaction_id='response',data_location='response')
    other=deepcopy(g[0]);other.update(id='other',interaction_id='other')
    report=missing_report(g+[response,other],e,[])
    assert {a['id'] for a in report['M']}=={'response','other'}
    assert not broad_covers(response,s)

def test_GT_is_split_using_test_description_and_normal_contract_not_G():
    x,s,inputs=inverse_fixture();s['source_refs']=[{**R[0],'source_id':'test','quote':'查询接口参数非法'}]
    inputs={'fused-ssd':inputs['fused-ssd'],'normal-constraints':x['api-parameters'],'test-documents':[{'source_id':'test','channel':'test','name':'test.md','lines':[{'number':1,'text':'查询接口参数非法'}]}]}
    gt=expand_truth({'scenarios':[s]},inputs)['scenarios']
    assert len(gt)==8 and all(a['id'].startswith('GT-') and a['coverage_kind']=='exact' for a in gt)
    assert all(any(r['source_id']=='test' for r in a['source_refs']) for a in gt)
    assert set(inputs)=={'fused-ssd','normal-constraints','test-documents'}

def test_cross_layer_duplicate_view_collapses_but_downstream_call_remains():
    rr=exchange(sid='rr',layer='RR');sr=deepcopy(rr);sr.update(id='sr',layer='SR')
    downstream=deepcopy(sr);downstream.update(id='down');downstream['sender']=deepcopy(sr['receiver']);downstream['receiver']['name']='DatabaseService'
    value={'interactions':[rr,sr,downstream],'rr_sr_links':[{'rr_id':'rr','sr_ids':['sr','down'],'status':'confirmed'}]}
    canonical=canonical_fused(value)
    assert {i['id'] for i in canonical['interactions']}=={'sr','down'}
    assert canonical['aliases']==[{'source_id':'rr','interaction_id':'sr'}]


def test_repeated_actual_calls_keep_separate_chains_and_exception_units():
    from scene_completion.ssd_tools import complete_structure
    from scene_completion.exception_generation import deduplicate
    rows=[];links=[]
    for n in (1,2):
        rr=exchange(sid=f'rr{n}',layer='RR');sr=exchange(sid=f'sr{n}')
        downstream=deepcopy(sr);downstream.update(id=f'down{n}',parent_id=sr['id'])
        downstream['sender']=deepcopy(sr['receiver']);downstream['receiver']['name']='DatabaseService'
        for req in (rr,sr,downstream):
            ret=deepcopy(req);ret.update(id=req['id']+'-return',direction='return',parent_id=req['id'])
            ret['sender'],ret['receiver']=deepcopy(req['receiver']),deepcopy(req['sender'])
            if req is rr:rr_return=ret
            elif req is sr:sr_return=ret
            else:down_return=ret
        # Identical endpoint/operation/evidence across occurrences is intentional.
        rows.extend([rr,rr_return,sr,downstream,down_return,sr_return])
        links.extend([{'rr_id':rr['id'],'sr_ids':[sr['id'],downstream['id'],down_return['id']],'status':'confirmed'},
                      {'rr_id':rr_return['id'],'sr_ids':[sr_return['id']],'status':'confirmed'}])
    out=complete_structure({'interactions':rows,'rr_sr_links':links,'pending':[]})
    result=canonical_fused(out)
    assert len(out['interactions'])==12 and len(result['interactions'])==8
    assert {i['parent_id'] for i in result['interactions'] if i['id'].startswith('down') and i['direction']=='request'}=={'sr1','sr2'}
    assert {i['parent_id'] for i in result['interactions'] if i['id'].startswith('sr') and i['direction']=='return'}=={'sr1','sr2'}
    assert {a['source_id']:a['interaction_id'] for a in result['aliases']}=={
        'rr1':'sr1','rr1-return':'sr1-return','rr2':'sr2','rr2-return':'sr2-return'}
    first=scenario('first');first.update(interaction_id='sr1',canonical_interaction_id='sr1')
    second=deepcopy(first);second.update(id='second',interaction_id='sr2',canonical_interaction_id='sr2')
    assert len(deduplicate([first,deepcopy(first),second]))==2

def test_node_messages_questions_and_applied_status_survive_reload(tmp_path):
    store=Conversations(tmp_path);store.append('G','guidance','只分析本次查询')
    q=store.question('G','实例ID格式是什么？','文档只有必填','给出格式或确认待定')
    assert Conversations(tmp_path).pending('G')['id']==q['id']
    store.answer('G',q['detail']['question_id'],'仍待确认，不生成格式异常')
    assert not store.pending('G') and len(store.apply('G'))==2
    assert all(m['applied'] for m in store.list('G') if m['kind'] in {'guidance','answer'})
    assert store.list('E')==[]
    with pytest.raises(ValueError):store.answer('G',q['detail']['question_id'],'duplicate')

def test_429_retries_have_shared_cooldown_do_not_consume_semantic_repairs(tmp_path,monkeypatch):
    gate=CallGate(3);calls=[];observed=[]
    original=gate.observe
    def observe(d):observed.append(d);original(d);gate.retry_not_before=0
    monkeypatch.setattr(gate,'observe',observe)
    def call():
        calls.append(1)
        if len(calls)<=2:
            e=RuntimeError('429');e.response_diagnostic={'failure_category':'rate_limited','retry_after_seconds':2,'http_status':429};raise e
        return 'ok'
    store=EventStore(tmp_path)
    with bind(store,task_key='node',role='modeler',case='shared',attempt=1):assert gate.call(call)=='ok'
    assert len(calls)==3 and gate.effective_limit==1
    events=[e for e in store.read() if e['kind']=='rate_limit_wait'];assert len(events)==2 and events[0]['data']['retry_count']==1
    assert all(e['attempt']==1 for e in events)
    calls.clear()
    def always():
        calls.append(1);e=RuntimeError('429');e.response_diagnostic={'failure_category':'rate_limited'};raise e
    with pytest.raises(TaskBlocked) as failure:gate.call(always)
    assert len(calls)==4 and failure.value.status=='rate_limited'

def test_timeout_is_not_retried(tmp_path):
    gate=CallGate();calls=[]
    def call():
        calls.append(1);e=TimeoutError();e.response_diagnostic={'failure_category':'transport_timeout'};raise e
    with pytest.raises(TaskBlocked):gate.call(call)
    assert len(calls)==1

def test_ask_user_resumes_same_agent_history_without_resetting_model_count(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    sent=[]
    def transport(url,key,body,*args):
        sent.append(body)
        if len(sent)==1:fun={'name':'ask_user','arguments':json.dumps({'question':'服务身份待确认','basis':'材料未明确','decision':'请确认服务'})}
        else:fun={'name':'submit_result','arguments':'{"payload":{"services":[]}}'}
        return {'model':'actual','choices':[{'message':{'content':None,'tool_calls':[{'id':'c'+str(len(sent)),'type':'function','function':fun}]}}]}
    client=DeepAgentsClient({'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(tmp_path),'agent_max_model_calls':1},transport=transport)
    p=packet('api-map',{'SR':[]});p['skill_text']='---\nname: scene-api-map\ndescription: API\n---\nRead and submit.'
    store=EventStore(tmp_path)
    with bind(store,task_key='api-map',case='shared',role='modeler',attempt=1):
        with pytest.raises(TaskBlocked) as failure:client.agent(p)
    assert failure.value.status=='awaiting_answer'
    conversation=Conversations(tmp_path);q=conversation.pending('api-map');conversation.answer('api-map',q['detail']['question_id'],'保持未知')
    with bind(store,task_key='api-map',case='shared',role='modeler',attempt=1):assert client.agent(p)['services']==[]
    assert len(sent)==2
    checkpoint=next(iter(__import__('sqlite3').connect(tmp_path/'execution_events.sqlite3').execute('SELECT state FROM checkpoints')))[0]
    assert json.loads(checkpoint)['model_calls']==2
    assert any(m['role']=='tool' and m.get('tool_call_id')=='c1' for m in sent[1]['messages'])
    assert any('保持未知' in str(m['content']) for m in sent[1]['messages'])

def test_new_protocol_upgrade_keeps_original_project_and_records(tmp_path):
    from scene_completion.workbench import Workbench
    from scene_completion.storage import write_json,read_json
    w=Workbench(tmp_path);meta=w.create({'name':'old','sources':{r:[{'name':r+'.md','content':'# example'}] for r in ('RR','SR')}})
    p=w.run_dir(meta['id']);meta['protocol']='scene-workflow-v2';write_json(p/'project.json',meta);(p/'old-result.txt').write_text('history')
    rid=w.upgrade(meta['id']);assert rid!=meta['id']
    assert (p/'old-result.txt').read_text()=='history' and read_json(p/'project.json')['protocol']=='scene-workflow-v2'
    assert read_json(w.run_dir(rid)/'project.json')['protocol']==PROTOCOL

def test_dynamic_case_work_starts_while_independent_api_task_is_still_running(tmp_path):
    from scene_completion.workflow import Execution,build_pipeline
    import threading
    rr,sr,t,m=fake_pipeline(tmp_path);base=m['api-map'];slow_started=threading.Event();fused_started=threading.Event()
    def slow(p):
        slow_started.set()
        assert fused_started.wait(6),'fused SSD was incorrectly held behind unrelated API map'
        return base
    fused=m['fused-ssd']
    def fast(p):fused_started.set();return fused(p)
    m['api-map']=slow;m['fused-ssd']=fast
    ex=Execution(tmp_path/'run',mocks=m,config={'max_concurrency':3});build_pipeline(ex,rr,sr,[])
    assert ex.finish()['complete'] and slow_started.is_set() and fused_started.is_set()

def test_API_children_reuse_success_and_merge_only_after_all_children_pass(tmp_path):
    from scene_completion.workflow import Execution,build_pipeline
    rr,sr,t,m=fake_pipeline(tmp_path);ref=[{'source_id':sr[0]['source_id'],'line_start':2,'line_end':2,'quote':sr[0]['lines'][1]['text']}]
    m['api-map']={'services':[{'name':'Service','interfaces':[{'id':name,'name':name,'address':None,'method':None,'source_refs':ref} for name in ['a','b']],'source_refs':ref}]}
    calls=[]
    def part(p):
        key=p['node_key'];calls.append(key)
        if len(calls)==1:return {'wrong':True}
        target=p['input']['interface']
        return {'apis':[{'id':target['id'],'name':target['name'],'address':None,'parameters':[],'source_refs':ref}]}
    m['api-parameters']=part
    ex=Execution(tmp_path/'run',mocks=m,config={'max_concurrency':2});build_pipeline(ex,rr,sr,[]);ex.finish()
    # The first invalid response is repaired locally; the sibling result stays cached.
    states=ex.scheduler.state['tasks'];parts=[k for k in states if k.startswith('api-parameters-part-')]
    assert len(parts)==2 and all(states[k]['status']=='passed' for k in parts)
    assert states['api-parameters']['status']=='passed'
    assert (tmp_path/'run/artifacts/shared/api-parameters.json').exists()

def test_success_artifact_is_available_before_slow_sibling_finishes(tmp_path):
    import threading
    from scene_completion.contracts import PROTOCOL
    from scene_completion.scheduler import Scheduler,Task
    saved=threading.Event()
    def fast(d,r):return {'protocol':PROTOCOL,'task':'api-map','payload':{'services':[]}}
    def slow(d,r):
        deadline=time.time()+3
        while time.time()<deadline:
            if (tmp_path/'artifacts/shared/a.json').exists():saved.set();return {'ok':True}
            time.sleep(.02)
        pytest.fail('successful artifact withheld until entire execution completed')
    s=Scheduler(tmp_path,concurrency=2);s.add(Task('a','shared','api-map',execute=fast));s.add(Task('b','shared','other',execute=slow))
    assert s.run()['complete'] and saved.is_set()

def test_node_feedback_invalidates_only_target_and_downstream(tmp_path):
    from scene_completion.workflow import Execution,build_pipeline
    rr,sr,t,m=fake_pipeline(tmp_path);calls=[]
    mocks={k:(lambda p,v=v:(calls.append(p['node_key']),v(p) if callable(v) else deepcopy(v))[1]) for k,v in m.items()}
    root=tmp_path/'run';ex=Execution(root,mocks=mocks);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    calls.clear();Conversations(root).append('UC-X:exception-generate','guidance','仍按只读操作分析，重新核对')
    ex=Execution(root,mocks=mocks);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert any(k.startswith('UC-X:exception-generate--part-') for k in calls)
    assert not set(calls)&{'components','api-map','api-index','rr-use-cases','sr-use-cases','existing-branches','UC-X:fused-ssd','UC-X:existing-extract'}

def test_conversation_api_is_task_scoped_and_export_keeps_history(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    from scene_completion.storage import write_json
    app=create_app(tmp_path,client_factory=lambda *_:None);client=TestClient(app)
    p=client.post('/api/projects',json={'name':'review','sources':{r:[{'name':r+'.md','content':'# content'}] for r in ['RR','SR']}}).json();rid=p['id']
    root=app.state.workbench.run_dir(rid)/'run'
    write_json(root/'workflow_graph.json',{'nodes':[{'id':'G'},{'id':'E'}]})
    write_json(root/'workflow_tasks.json',{'tasks':{'G':{'status':'running'}}})
    assert client.post(f'/api/projects/{rid}/conversation',json={'task_key':'G','text':'核对当前查询'}).status_code==200
    assert len(client.get(f'/api/projects/{rid}/conversation?task_key=G').json()['messages'])==1
    assert client.get(f'/api/projects/{rid}/conversation?task_key=E').json()['messages']==[]
    assert client.get(f'/api/projects/{rid}/conversation?task_key=unknown').status_code==400
    import io,zipfile
    archive=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{rid}/export').content))
    assert json.loads(archive.read('run/node_conversations.json'))['G'][0]['text']=='核对当前查询'

def test_question_does_not_stop_independent_work_or_reset_repair_round(tmp_path):
    calls=[]
    s=Scheduler(tmp_path,concurrency=2)
    def question(d,r):calls.append(r['rounds']);raise TaskBlocked('awaiting_answer',{'question':'which rule?'})
    s.add(Task('ask','shared','task',version=1,execute=question));s.add(Task('other','shared','task',execute=lambda d,r:{'done':True}))
    assert not s.run()['complete'] and s.state['tasks']['other']['status']=='passed'
    s.state['tasks']['ask']['rounds']=1;s.save()
    s2=Scheduler(tmp_path);s2.add(Task('ask','shared','task',version=2,execute=lambda d,r:None,repair=lambda d,r:({'rounds':r['rounds']})))
    assert s2.run()['complete'] and s2.state['tasks']['ask']['rounds']==1

def test_duplicate_return_views_use_the_same_canonical_request_and_return():
    rr=exchange(sid='rr',layer='RR');sr=deepcopy(rr);sr.update(id='sr',layer='SR')
    returns=[]
    for request in [rr,sr]:
        ret=deepcopy(request);ret.update(id=request['id']+'-ret',parent_id=request['id'],sequence=2,direction='return');ret['sender'],ret['receiver']=ret['receiver'],ret['sender'];returns.append(ret)
    result=canonical_fused({'interactions':[rr,sr]+returns,'rr_sr_links':[{'rr_id':'rr','sr_ids':['sr'],'status':'confirmed'}]})
    assert {i['id'] for i in result['interactions']}=={'sr','sr-ret'}
    assert next(i for i in result['interactions'] if i['direction']=='return')['parent_id']=='sr'

def test_provider_SSE_429_is_rate_limited_instead_of_a_connection_error():
    from tests.test_execution_monitor import sse
    from scene_completion.streaming import read_chat_stream
    with pytest.raises(RuntimeError) as error:read_chat_stream(sse({'error':{'code':429,'retry_after_seconds':2,'message':'untrusted upstream'}}),time.perf_counter(),10)
    d=error.value.response_diagnostic
    assert d['failure_category']=='rate_limited' and d['retry_after_seconds']==2
    assert not d['configuration_required'] and 'untrusted' not in str(error.value)


def test_composition_uses_complete_input_without_repeated_filesystem_calls(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    rr,sr,_,m=fake_pipeline(tmp_path);sent=[]
    def transport(url,key,body,*args):
        sent.append(body)
        assert {t['function']['name'] for t in body['tools']}=={'ask_user','submit_result'}
        assert body['tool_choice']=='required' and body['parallel_tool_calls'] is False
        assert 'read_file' not in {t['function']['name'] for t in body['tools']}
        return {'model':'actual','choices':[{'message':{'content':None,'tool_calls':[{'id':'c','type':'function','function':{'name':'submit_result','arguments':json.dumps({'payload':m['components']})}}]}}]}
    from scene_completion.source_documents import normal_projection
    p=packet('components',{'RR':normal_projection(rr),'SR':normal_projection(sr)});p['skill_text']='---\nname: scene-components\ndescription: extract\n---\nExtract components.'
    c=DeepAgentsClient({'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(tmp_path),'component_submission_mode':'tool_calls'},transport=transport)
    assert c.agent(p)['components']==m['components']['components'] and len(sent)==1


def test_composition_json_stream_adapter_validates_and_finishes_in_one_request(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.source_documents import normal_projection
    rr,sr,_,m=fake_pipeline(tmp_path);sent=[]
    def transport(url,key,body,*args):
        sent.append(body)
        assert 'tools' not in body and 'tool_choice' not in body
        assert body['response_format']=={'type':'json_object'} and body['stream']
        return {'model':'actual','choices':[{'message':{'content':json.dumps(m['components'])},'finish_reason':'stop'}]}
    p=packet('components',{'RR':normal_projection(rr),'SR':normal_projection(sr)});p['skill_text']='---\nname: scene-components\ndescription: extract\n---\nExtract components.'
    c=DeepAgentsClient({'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(tmp_path)},transport=transport)
    store=EventStore(tmp_path)
    with bind(store,task_key='components',case='shared',role='modeler',attempt=1):assert c.agent(p)['components']==m['components']['components']
    assert len(sent)==1 and any(e['kind']=='structured_text_submission' for e in store.read())


def test_composition_json_adapter_preserves_blocking_questions_and_validation(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.source_documents import normal_projection
    rr,sr,_,m=fake_pipeline(tmp_path)
    p=packet('components',{'RR':normal_projection(rr),'SR':normal_projection(sr)});p['skill_text']='---\nname: scene-components\ndescription: extract\n---\nExtract.'
    response={'clarification':{'question':'服务内外边界？','basis':'原文缺少边界','decision':'请确认'}}
    def transport(*args):return {'choices':[{'message':{'content':json.dumps(response)},'finish_reason':'stop'}]}
    c=DeepAgentsClient({'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(tmp_path/'question')},transport=transport)
    with pytest.raises(TaskBlocked) as failure:c.agent(p)
    assert failure.value.status=='awaiting_answer'
    assert Conversations(tmp_path/'question').pending('components')['text']=='服务内外边界？'
    response.clear();response.update({'components':[{'name':'fabricated'}],'relations':[]})
    c=DeepAgentsClient({'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(tmp_path/'invalid')},transport=transport)
    from scene_completion.scheduler import TaskRejected
    with pytest.raises(TaskRejected):c.agent(p)


def test_runtime_cache_aliases_preserve_only_exact_reviewed_implementations(tmp_path,monkeypatch):
    from pathlib import Path
    import scene_completion.workflow as workflow
    from scene_completion.storage import fingerprint,read_json
    before=workflow.code_version('api-map')
    assert not Path(workflow.__file__).with_name('cache_code_aliases.json').exists()
    actual=Path.read_text
    def changed(path,*args,**kwargs):
        text=actual(path,*args,**kwargs)
        return text+'\n# semantic change' if path.name=='deepagents_client.py' else text
    monkeypatch.setattr(Path,'read_text',changed)
    assert workflow.code_version('api-map')!=before


def test_ecnu_all_tasks_use_json_text_and_do_not_buffer_tool_arguments(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    sent=[]
    def transport(url,key,body,*args):
        sent.append(body);assert body['response_format']=={'type':'json_object'} and 'tools' not in body
        return {'model':'qwen3.8-flash','choices':[{'message':{'content':'{"branches":[]}'},'finish_reason':'stop'}]}
    p=packet('existing-branches',{'existing-documents':[]});p['skill_text']='---\nname: scene-existing-branches\ndescription: extract\n---\nExtract.'
    c=DeepAgentsClient({'base_url':'http://offline/v1','api_key':'test','agent_model':'ecnu-plus','run_root':str(tmp_path)},transport=transport)
    assert c.agent(p)['branches']==[] and len(sent)==1


def test_scheduler_prioritizes_catalog_before_api_fanout(tmp_path):
    from scene_completion.scheduler import Scheduler,Task
    order=[];s=Scheduler(tmp_path,concurrency=1)
    def work(name):return lambda d,r:(order.append(name),{'value':name})[1]
    s.add(Task('api-part-a','shared','api-parameters',execute=work('api1')))
    s.add(Task('api-part-b','shared','api-parameters',execute=work('api2')))
    s.add(Task('rr-use-cases','shared','use-case-extract',execute=work('catalog')))
    s.add(Task('UC:fused-ssd','UC','fused-ssd',execute=work('fused')))
    assert s.run()['complete']
    assert order[0]=='catalog' and order.index('fused')<order.index('api2')


def test_repair_receives_only_this_node_rejected_candidate_and_specific_evidence_error(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.workflow import Execution
    from scene_completion.source_documents import normal_projection
    from copy import deepcopy
    rr,sr,_,m=fake_pipeline(tmp_path);root=tmp_path/'repair';sent=[]
    def transport(url,key,body,*args):
        sent.append(body);value=deepcopy(m['components'])
        if len(sent)==1:value['components'][0]['source_refs'][0]['quote']='wrong quotation'
        else:
            text=body['messages'][-1]['content']
            assert 'candidate' in text and 'wrong quotation' in text and 'allowed_text=' in text
        return {'choices':[{'message':{'content':json.dumps(value)},'finish_reason':'stop'}]}
    config={'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(root),'submission_mode':'json_text'}
    client=DeepAgentsClient(config,transport=transport);ex=Execution(root,mode='external',client=client,config=config)
    ex.add('components','components',static={'RR':normal_projection(rr),'SR':normal_projection(sr)})
    assert ex.finish()['complete'] and len(sent)==2
    assert len(list((root/'agent_rejections').glob('*.json')))==1


def test_mixed_case_provider_keys_and_missing_explicit_credential_fail_closed(tmp_path):
    from scene_completion.model_settings import read_env,resolve
    f=tmp_path/'.env';f.write_text('ECNU_API_KEY=ecnu-secret\nECNU_BASE_URL=http://ecnu/v1\nBailian_API_Key=bailian-secret\nBailian_API_URL=http://bailian/v1\n')
    assert read_env(f)['Bailian_API_Key']=='bailian-secret'
    c=resolve({'base_url':'${Bailian_API_URL}','api_key_env':'Bailian_API_Key'},f)
    assert c['base_url']=='http://bailian/v1' and c['api_key']=='bailian-secret'
    assert resolve({'api_key_env':'Missing_Provider_Key'},f)['api_key']==''


def test_catalog_cannot_replace_explicit_use_cases_with_a_group_header():
    from scene_completion.use_cases import validate_catalogue
    docs=[{'source_id':'s','lines':[{'number':1,'text':'| 用例编号 | unusual.id.one |'},{'number':2,'text':'| 用例编号 | another-id |'}]}]
    value={'cases':[{'id':'MODULE','layer':'SR','source_ranges':[{'source_id':'s','start':1,'end':2}]}]}
    with pytest.raises(ValueError,match='遗漏'):validate_catalogue('use-case-extract',value,{'documents':docs,'layer':'SR'})


def test_alignment_does_not_merge_distinct_rr_use_cases():
    from scene_completion.use_cases import validate_catalogue
    inputs={'rr-cases':{'cases':[{'id':'a'},{'id':'b'}]},'sr-cases':{'cases':[{'id':'s'}]}}
    value={'groups':[{'id':'g','rr_ids':['a','b'],'sr_ids':['s'],'status':'confirmed'}]}
    with pytest.raises(ValueError,match='一个RR'):validate_catalogue('use-case-align',value,inputs)


def test_markdown_indent_is_not_an_evidence_error_but_words_and_internal_spaces_are():
    from scene_completion.source_documents import validate_evidence
    docs=[{'source_id':'s','lines':[{'number':1,'text':'   failure condition'},{'number':2,'text':'   → return empty list'}]}]
    ref={'source_id':'s','line_start':1,'line_end':2,'quote':'failure condition\n    → return empty list'}
    validate_evidence(ref,docs)
    for quote in ['failure changed\n→ return empty list','failure condition\n→ return  empty list','   ']:
        with pytest.raises(ValueError):validate_evidence({**ref,'quote':quote},docs)


def test_truncated_output_is_settled_and_repair_increases_only_to_configured_ceiling(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.workflow import Execution
    from scene_completion.storage import read_json
    calls=[];root=tmp_path/'truncated';ledger=tmp_path/'tokens.json'
    def transport(url,key,body,*args):
        calls.append(body['max_tokens'])
        return {'model':'actual','usage':{'total_tokens':17},'choices':[{'message':{'content':'{"services":[' if len(calls)==1 else '{"services":[]}'},'finish_reason':'length' if len(calls)==1 else 'stop'}]}
    config={'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(root),'submission_mode':'json_text','max_tokens':4000,'stage_max_tokens':{'api-map':1000},'token_budget_limit':100000,'token_budget_ledger':str(ledger)}
    ex=Execution(root,mode='external',client=DeepAgentsClient(config,transport=transport),config=config);ex.add('api-map','api-map',static={'SR':[]})
    assert ex.finish()['complete'] and calls==[1000,2000]
    book=read_json(ledger);assert book['committed_tokens']==34 and all(r['status']=='complete' for r in book['requests'].values())


def test_truncation_at_output_ceiling_waits_for_configuration_without_paid_retry(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.workflow import Execution
    calls=[]
    def transport(url,key,body,*args):
        calls.append(body['max_tokens'])
        return {'model':'actual','usage':{'total_tokens':17},'choices':[{'message':{'content':'{"services":['},'finish_reason':'length'}]}
    config={'base_url':'http://offline/v1','api_key':'test','agent_model':'test','run_root':str(tmp_path),'submission_mode':'json_text','max_tokens':1000}
    ex=Execution(tmp_path,mode='external',client=DeepAgentsClient(config,transport=transport),config=config);ex.add('api-map','api-map',static={'SR':[]})
    assert not ex.finish()['complete'] and calls==[1000]
    assert ex.scheduler.tasks['api-map'].key=='api-map'
    from scene_completion.storage import read_json
    assert read_json(tmp_path/'workflow_tasks.json')['tasks']['api-map']['status']=='awaiting_configuration'


def test_fused_case_identifier_normalization_is_exact_layer_scoped_and_nonmutating():
    from scene_completion.use_cases import canonical_case_ids
    source={'interactions':[{'case_id':'RR-1','layer':'RR'},{'case_id':'SR-1','layer':'SR'},{'case_id':'RR-2','layer':'RR'},{'case_id':'RR-1','layer':'SR'}]}
    group={'case-group':{'id':'group-1','rr_ids':['RR-1'],'sr_ids':['SR-1'],'status':'confirmed'}}
    value=canonical_case_ids(source,group)
    assert [i['case_id'] for i in value['interactions']]==['group-1','group-1','RR-2','RR-1']
    assert source['interactions'][0]['case_id']=='RR-1'
    assert canonical_case_ids(source,{'case-group':{**group['case-group'],'status':'pending'}})==source


def test_busy_worker_pool_does_not_spend_repairs_before_retry_is_dispatched(tmp_path):
    from scene_completion.scheduler import TaskRejected
    calls=[]
    def first(deps,record):
        calls.append(record['rounds'])
        if len(calls)==1:raise TaskRejected({'error':'fix me'})
        assert record['failure']=={'error':'fix me'}
        return {'ok':True}
    def slow(deps,record):time.sleep(.18);return {'ok':True}
    def short(deps,record):time.sleep(.025);return {'ok':True}
    s=Scheduler(tmp_path,concurrency=2)
    s.add(Task('a','shared','components',execute=first,repair=first))
    s.add(Task('b','shared','api-map',execute=slow))
    s.add(Task('c','shared','use-case-extract',execute=short))
    s.add(Task('d','shared','use-case-align',execute=short))
    assert s.run()['complete'] and calls==[0,1]
    assert s.state['tasks']['a']['rounds']==1


def test_local_model_budget_does_not_block_other_models():
    gate=CallGate(3);calls=[]
    def post(endpoint,body):
        calls.append(body['model'])
        if body['model']=='exhausted' and body.get('max_tokens',1000)>100:
            e=RuntimeError();e.response_diagnostic={'failure_category':'budget_exhausted','budget_kind':'tokens','budget_reason':'insufficient_remaining_allowance'};raise e
        return 'ok'
    with pytest.raises(TaskBlocked):gate.call(post,'/chat/completions',{'model':'exhausted'})
    assert gate.call(post,'/chat/completions',{'model':'available'})=='ok'
    assert gate.call(post,'/chat/completions',{'model':'exhausted','max_tokens':50})=='ok'
    assert calls==['exhausted','available','exhausted'] and not gate.quota.is_set()
