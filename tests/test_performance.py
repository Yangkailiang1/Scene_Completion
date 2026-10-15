import json
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from scene_completion.performance import Profiler
from scene_completion.semantic_backend import SemanticClient,read_json
from scene_completion.case_dag import Scheduler,Task,TaskRejected


def test_profile_records_context_usage_repairs_and_zero_request_resume(tmp_path,monkeypatch):
    monkeypatch.setenv('PROFILE_KEY','private-secret')
    calls=[]
    def transport(url,key,body,*args):
        calls.append(body)
        return {'model':'provider-model','usage':{'prompt_tokens':8,'completion_tokens':3},
            '_scene_completion_metrics':{'transport_attempts':2},'choices':[{'message':{'content':'{"ok":true}'}}]}
    client=SemanticClient({'agent_model':'fixture','base_url':'https://fixture.invalid/v1','api_key_env':'PROFILE_KEY'},transport)
    def setup(profiler):
        client.profiler=profiler
        scheduler=Scheduler(tmp_path,profiler=profiler)
        scheduler.add(Task('x','UC','normal',execute=lambda d,r:(_ for _ in ()).throw(TaskRejected('bad format')),
            repair=lambda d,r:client.agent({'stage':'interaction-model','batch_id':'test','input':{}})))
        return scheduler
    first=Profiler(tmp_path)
    assert setup(first).run()['complete'];first.finish()
    payload=read_json(tmp_path/'performance.json')['sessions'][0]
    assert payload['request_count']==1 and payload['usage']=={'prompt_tokens':8,'completion_tokens':3}
    stage=payload['stages']['normal']
    assert stage['repairs']==1 and stage['transport_retries']==1 and stage['request_bytes']>0
    second=Profiler(tmp_path)
    assert setup(second).run()['complete'];second.finish()
    assert len(calls)==1
    assert read_json(tmp_path/'performance.json')['sessions'][1]['request_count']==0
    assert 'private-secret' not in (tmp_path/'performance_events.jsonl').read_text(encoding='utf8')


def test_concurrent_intervals_are_not_summed_as_wall_time(tmp_path):
    profile=Profiler(tmp_path)
    def work(n):
        with profile.span('task',stage='s',task_key=str(n),dependencies=[]):time.sleep(.03)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(work,[1,2]))
    profile.finish()
    session=read_json(tmp_path/'performance.json')['sessions'][0]
    assert session['task_overlap_seconds']>0
    assert session['task_seconds']>session['task_busy_seconds']
    assert session['dependency_path']['task_seconds']<session['task_seconds']


def test_failure_and_absent_usage_remain_unknown(tmp_path):
    profile=Profiler(tmp_path)
    with pytest.raises(RuntimeError):
        with profile.span('request',stage='model-availability'):raise RuntimeError('denied')
    profile.finish('pending')
    session=read_json(tmp_path/'performance.json')['sessions'][0]
    assert session['unknown_usage_requests']==1 and session['usage']=={}
    assert session['stages']['model-availability']['failures']==1


def test_unfinished_session_does_not_report_zero_wall_time(tmp_path):
    profile=Profiler(tmp_path)
    profile.emit('cache',stage='normal')
    profile.report()
    session=read_json(tmp_path/'performance.json')['sessions'][0]
    assert session['wall_seconds'] is None and session['status']=='incomplete_or_running'
    assert '未结束' in (tmp_path/'performance.md').read_text(encoding='utf8')


def test_profiling_flag_does_not_enter_packets_or_change_semantic_results(tmp_path,monkeypatch):
    monkeypatch.setenv('PROFILE_KEY','private-secret')
    client=SemanticClient({'agent_model':'fixture','base_url':'https://fixture.invalid/v1','api_key_env':'PROFILE_KEY'},
        lambda *args:{'choices':[{'message':{'content':'{"ok":true}'}}]})
    packet={'stage':'gap-fixture','batch_id':'b','input':{'x':1}}
    before=json.dumps(packet)
    result=client.agent(packet)
    client.profiler=Profiler(tmp_path)
    assert client.agent(packet)==result and json.dumps(packet)==before
