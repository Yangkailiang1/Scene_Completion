"""Real event contracts, replay, concurrent attribution and bounded agent exit."""
import asyncio,io,json,time,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from scene_completion.execution_events import EventStore,bind,emit
from scene_completion.execution_graph import graph_snapshot
from scene_completion.streaming import read_chat_stream
from scene_completion.storage import write_json
from scene_completion.workbench import create_app

def sse(*rows,done=True):
    raw=''.join('data: '+json.dumps(r)+'\n\n' for r in rows)+('data: [DONE]\n\n' if done else '')
    return io.BytesIO(raw.encode())

def test_tool_deltas_nulls_multiple_calls_and_durable_replay(tmp_path):
    store=EventStore(tmp_path)
    chunks=[{'model':'actual-model','choices':[{'delta':None}]},{'choices':[{'delta':{'content':'正文','tool_calls':None}}]},
      {'choices':[{'delta':{'tool_calls':[{'index':0,'id':'a','function':{'name':'submit_','arguments':'{"payload":'}},{'index':1,'id':'b','function':{'name':'other','arguments':'{'}}]}}]},
      {'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'name':'result','arguments':'{}}'}},{'index':1,'function':{'arguments':'"ok":true}'}}]},'finish_reason':'tool_calls'}]},
      {'choices':[],'usage':{'total_tokens':7}}]
    with bind(store,task_key='case:task',role='modeler',case='case',attempt=2,model_call_id='request'):
        result=read_chat_stream(sse(*chunks),time.perf_counter(),10)
    message=result['choices'][0]['message'];assert message['content']=='正文'
    assert message['tool_calls'][0]['function']=={'name':'submit_result','arguments':'{"payload":{}}'}
    assert json.loads(message['tool_calls'][1]['function']['arguments'])=={'ok':True}
    assert result['model']=='actual-model' and result['usage']['total_tokens']==7
    rows=EventStore(tmp_path).read();assert all(r['attempt']==2 and r['task_key']=='case:task' for r in rows)
    assert store.read(rows[1]['id'])==rows[2:]
    assert rows[0]['data']['model_call_id']=='request'

def test_incomplete_stream_persists_diagnostics_but_cannot_be_result(tmp_path):
    store=EventStore(tmp_path)
    with bind(store,task_key='bad',role='modeler',case='x',attempt=1):
        with pytest.raises(Exception):read_chat_stream(sse({'choices':[{'delta':{'content':'partial'}}]},done=False),time.perf_counter(),10)
    assert store.read()[0]['data']['text']=='partial'
    assert not (tmp_path/'task_outputs').exists()

def test_concurrent_streams_keep_task_context_and_monotonic_ids(tmp_path):
    store=EventStore(tmp_path)
    def worker(k):
        with bind(store,task_key=k,case=k,role='modeler',attempt=1):
            for i in range(15):emit('stream_delta',text=f'{k}:{i}')
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(worker,['a','b','c']))
    rows=store.read();assert len(rows)==45 and len({r['id'] for r in rows})==45
    for k in ['a','b','c']:assert [r['data']['text'] for r in store.read(task_key=k)]==[f'{k}:{i}' for i in range(15)]

def test_graph_uses_real_dependencies_and_reports_review_blocking(tmp_path):
    write_json(tmp_path/'workflow_graph.json',{'nodes':[
      {'id':'components','stage':'components','case':'shared','role':'modeler','deps':[],'expected_files':['components.json']},
      {'id':'case:fused-ssd','stage':'fused-ssd','case':'case','role':'modeler','deps':['components'],'expected_files':['fused-ssd.json']},
      {'id':'gap-recommend','stage':'gap-recommend','case':'shared','role':'recommender','deps':[],'expected_files':[]}]})
    write_json(tmp_path/'workflow_tasks.json',{'tasks':{'components':{'status':'awaiting_review'}}})
    graph=graph_snapshot(tmp_path);nodes={n['id']:n for n in graph['nodes']}
    assert nodes['case:fused-ssd']['blocked_by']==['components']
    assert nodes['case:fused-ssd']['phase']=='dependency_wait'
    assert nodes['gap-recommend']['status']=='disabled'
    assert graph['edges']==[{'id':'components->case:fused-ssd','source':'components','target':'case:fused-ssd'}]

def test_event_api_replays_after_last_event_id_and_export_has_no_secret(tmp_path):
    env=tmp_path/'server.env';env.write_text('ECNU_BASE_URL=http://model.test/v1\nECNU_API_KEY=private-key\n')
    app=create_app(tmp_path/'projects',env_file=env);client=TestClient(app)
    project=client.post('/api/projects',json={'name':'stream','sources':{k:[{'name':k+'.md','content':'# 用例'}] for k in ['RR','SR']}}).json();rid=project['id']
    root=app.state.workbench.run_dir(rid);store=EventStore(root/'run')
    for i in range(3):store.append('stream_delta',task_key='task',role='modeler',case='shared',attempt=1,text=str(i))
    data=client.get(f'/api/projects/{rid}').json();assert data['config']['agent_model']=='ecnu-plus'
    assert data['config']['credential_configured'] and 'private-key' not in json.dumps(data)
    assert len(client.get(f'/api/projects/{rid}/events/history?after=1&task_key=task').json()['events'])==2
    endpoint=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/projects/{rid}/events')
    class Request:
        headers={'Last-Event-ID':'2'}
        async def is_disconnected(self):return False
    async def first():
        response=await endpoint(rid,Request(),after=1)
        try:return await anext(response.body_iterator)
        finally:await response.body_iterator.aclose()
    event=asyncio.run(first());assert event.startswith('id: 3\nevent: execution\n')
    archive=zipfile.ZipFile(io.BytesIO(client.get(f'/api/projects/{rid}/export').content))
    assert 'run/execution_events.jsonl' in archive.namelist()
    assert all('sqlite3' not in n and '.env' not in n for n in archive.namelist())
    assert b'private-key' not in b''.join(archive.read(n) for n in archive.namelist())

def test_settings_precedence_and_public_whitelist(tmp_path,monkeypatch):
    from scene_completion.model_settings import resolve,public_settings
    monkeypatch.delenv('SCENE_AGENT_MODEL',raising=False);monkeypatch.delenv('SCENE_API_KEY',raising=False)
    path=tmp_path/'.env';path.write_text('ECNU_API_KEY="secret"\nECNU_BASE_URL=https://env.test/v1\n')
    result=resolve({'agent_model':'explicit','base_url':'https://project.test/v1'},path)
    assert result['api_key']=='secret' and result['agent_model']=='explicit' and result['base_url']=='https://project.test/v1'
    assert 'secret' not in str(public_settings(result))

def test_new_global_stream_starts_at_tail_but_reconnect_replays_unseen_events(tmp_path):
    app=create_app(tmp_path/'projects');client=TestClient(app)
    rid=client.post('/api/projects',json={'name':'stream','sources':{k:[{'name':k+'.md','content':'# 用例'}] for k in ['RR','SR']}}).json()['id']
    store=EventStore(app.state.workbench.run_dir(rid)/'run')
    for n in range(5):store.append('stream_delta',task_key='a',text=str(n))
    assert store.latest_id()==5
    endpoint=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/projects/{rid}/events')
    class Request:
        headers={}
        async def is_disconnected(self):return False
    async def check():
        response=await endpoint(rid,Request(),tail=True)
        stream=response.body_iterator
        assert (await anext(stream)).startswith('id: 5\nevent: cursor\n')
        store.append('phase',task_key='a',phase='saved')
        assert (await anext(stream)).startswith('id: 6\nevent: execution\n')
        await stream.aclose()
        request=Request();request.headers={'Last-Event-ID':'4'}
        response=await endpoint(rid,request,tail=True)
        assert (await anext(response.body_iterator)).startswith('id: 5\nevent: execution\n')
        await response.body_iterator.aclose()
    asyncio.run(check())
    assert len(store.read(task_key='a'))==6  # history remains complete

def test_invalid_deepagent_submission_escapes_for_bounded_repair(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.contracts import packet
    from scene_completion.scheduler import TaskRejected
    sent=[]
    def transport(*args):
        sent.append(1)
        return {'choices':[{'message':{'content':None,'tool_calls':[{'id':'bad','type':'function','function':{'name':'submit_result','arguments':'{"payload":{"services":[{"wrong":true}]}}'}}]}}]}
    client=DeepAgentsClient({'base_url':'http://test/v1','agent_model':'test','api_key':'test','run_root':str(tmp_path)},transport=transport)
    p=packet('api-map',{'SR':[]});p['skill_text']='---\nname: scene-api-map\ndescription: API\n---\nSubmit data.'
    with pytest.raises(TaskRejected):client.agent(p)
    assert len(sent)==1
    trace=json.loads(next((tmp_path/'agent_traces').glob('*.json')).read_text());assert trace['status']=='failed'
    assert trace['error_type']=='TaskRejected' and trace['messages']

def test_deepagent_forces_submission_at_task_budget_instead_of_raising_recursion_limit(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.contracts import packet
    sent=[]
    def transport(url,key,body,*args):
        sent.append(body)
        final=len(sent)==2
        call={'id':str(len(sent)),'type':'function','function':{'name':'submit_result' if final else 'ls','arguments':'{"payload":{"services":[]}}' if final else '{"path":"/input"}'}}
        return {'model':'provider','choices':[{'message':{'content':None,'tool_calls':[call]}}]}
    client=DeepAgentsClient({'base_url':'http://test/v1','agent_model':'test','api_key':'test','run_root':str(tmp_path),'agent_max_model_calls':2},transport=transport)
    p=packet('api-map',{'SR':[]});p['skill_text']='---\nname: scene-api-map\ndescription: API\n---\nRead and submit.'
    result=client.agent(p)
    assert result['services']==[] and len(sent)==2
    assert sent[-1]['tool_choice']=='required'
    assert {t['function']['name'] for t in sent[-1]['tools']}=={'submit_result','ask_user'}
    assert result['execution_model_evidence']['observed_models']==['provider']

def test_task_virtual_sources_preserve_only_allowed_lines():
    from scene_completion.deepagents_client import task_files
    docs={'source_id':'customer/source.md','channel':'normal','lines':[{'number':3,'text':'normal request'},{'number':9,'text':'normal result'}]}
    files=task_files({'input':{'SR':[docs]}})
    assert len(files)==1 and next(iter(files)).startswith('/input/sources/')
    assert next(iter(files.values()))=='source_id=customer/source.md\n3 | normal request\n9 | normal result'

def test_stream_provider_error_is_classified_without_echoing_server_body():
    with pytest.raises(RuntimeError) as failure:read_chat_stream(sse({'error':{'message':'private upstream body','code':400}}),time.perf_counter(),10)
    assert failure.value.response_diagnostic['failure_category']=='request_invalid'
    assert 'private' not in str(failure.value)

def test_truncated_tool_result_is_rejected_for_repair_not_connection_failure():
    result=read_chat_stream(sse({'choices':[{'delta':{'tool_calls':[{'index':0,'id':'a','function':{'name':'submit_result','arguments':'{"partial":'}}]},'finish_reason':'length'}]}),time.perf_counter(),10)
    assert result['choices'][0]['finish_reason']=='length'
