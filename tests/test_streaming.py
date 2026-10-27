import json,time
import http.client
import pytest
from scene_completion.streaming import read_chat_stream


def rows(events,done=True):
    for e in events:
        yield ('data: '+json.dumps(e,ensure_ascii=False)+'\n').encode();yield b'\n'
    if done:yield b'data: [DONE]\n';yield b'\n'


def test_stream_assembles_json_and_discards_reasoning():
    result=read_chat_stream(rows([
        {'model':'actual','choices':[{'delta':{'reasoning_content':'private reasoning'}}]},
        {'choices':[{'delta':{'content':'{"ok":'}}]},
        {'choices':[{'delta':{'content':'true}'},'finish_reason':'stop'}]},
        {'choices':[],'usage':{'total_tokens':12}}
    ]),time.perf_counter(),60)
    assert json.loads(result['choices'][0]['message']['content'])=={'ok':True}
    assert result['usage']=={'total_tokens':12} and result['model']=='actual'
    assert 'private reasoning' not in json.dumps(result)


def test_complete_looking_json_without_done_is_still_incomplete():
    with pytest.raises(http.client.IncompleteRead):
        read_chat_stream(rows([{'choices':[{'delta':{'content':'{}'},'finish_reason':'stop'}]}],done=False),time.perf_counter(),60)


def test_incomplete_stream_reports_real_provider_finish_and_no_payload():
    with pytest.raises(http.client.IncompleteRead) as failure:
        read_chat_stream(rows([{'model':'actual','choices':[{'delta':{'role':'assistant'}}]}],done=False),time.perf_counter(),900)
    d=failure.value.response_diagnostic
    assert d['failure_category']=='stream_incomplete' and d['partial_content_bytes']==0
    assert d['provider_model']=='actual' and not d['done_received'] and d['finish_reason'] is None
    assert d['elapsed_seconds']>=0 and d['phase']=='stream_read'


def test_opt_in_reasoning_replay_is_transport_only_with_separate_byte_counts():
 result=read_chat_stream(rows([{'choices':[{'delta':{'reasoning_content':'private chunk'}}]},{'choices':[{'delta':{'content':'{}'},'finish_reason':'stop'}]}]),time.perf_counter(),60,capture_reasoning=True)
 assert result['choices'][0]['message']['reasoning_content']=='private chunk'
 assert result['_scene_completion_metrics']['reasoning_bytes']==len('private chunk')
 assert result['choices'][0]['message']['content']=='{}'


def test_display_reasoning_is_opt_in_separate_from_artifact_and_resumes_from_events(tmp_path):
 from scene_completion.execution_events import EventStore,bind
 store=EventStore(tmp_path)
 trace='provider-supplied thinking text'
 stream=lambda:rows([{'choices':[{'delta':{'reasoning_content':trace}}]},{'choices':[{'delta':{'content':'{"ok":true}'},'finish_reason':'stop'}]}])
 with bind(store,task_key='first'):
  result=read_chat_stream(stream(),time.perf_counter(),60)
 assert trace not in json.dumps(store.read()) and 'reasoning_content' not in result['choices'][0]['message']
 with bind(store,task_key='second'):
  result=read_chat_stream(stream(),time.perf_counter(),60,display_reasoning=True)
 events=store.read(task_key='second');reason=[e for e in events if e['kind']=='stream_delta' and e['data']['channel']=='reasoning']
 assert len(reason)==1 and reason[0]['data']['text']==trace and reason[0]['data']['not_artifact']
 assert json.loads(result['choices'][0]['message']['content'])=={'ok':True}
 assert 'reasoning_content' not in result['choices'][0]['message']
 assert EventStore(tmp_path).read(reason[0]['id']-1,task_key='second')[0]['id']==reason[0]['id']
