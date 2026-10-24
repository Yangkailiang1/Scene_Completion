"""Timeout phases remain distinct; a live long stream is not a 120-second deadline."""
import io,json,time
from unittest.mock import patch
from copy import deepcopy
import pytest
from scene_completion.streaming import read_chat_stream
from scene_completion.http_transport import _post_chat_completions_diagnostic
from scene_completion.deepagents_client import compact_input,task_message
from scene_completion.model_settings import resolve,public_settings

def event(row):return ('data: '+json.dumps(row)+'\n\n').encode()

def test_long_healthy_stream_uses_total_deadline_separate_from_idle_wait():
    clock=[0.0]
    def response():
        clock[0]=130
        yield event({'choices':[{'delta':{'content':'ok'},'finish_reason':'stop'}]})
        yield b'data: [DONE]\n\n'
    with patch('scene_completion.streaming.time.perf_counter',side_effect=lambda:clock[0]):
        result=read_chat_stream(io.BytesIO(b''.join(response())),0,900)
    assert result['choices'][0]['message']['content']=='ok'

def test_idle_timeout_preserves_phase_partial_bytes_and_pending_tool():
    def response():
        yield from event({'model':'actual','choices':[{'delta':{'tool_calls':[{'index':0,'id':'c','function':{'name':'submit_result','arguments':'{"payload":'}}]}}]}).splitlines(keepends=True)
        raise TimeoutError('socket idle')
    with pytest.raises(TimeoutError) as failure:read_chat_stream(response(),time.perf_counter(),900)
    d=failure.value.response_diagnostic
    assert d['phase']=='stream_read' and d['timeout_kind']=='idle_read' and d['partial_content_bytes']>0
    assert d['provider_model']=='actual' and d['incomplete_tools']==['submit_result']

def test_total_deadline_has_different_diagnostic():
    with patch('scene_completion.streaming.time.perf_counter',return_value=1000):
        with pytest.raises(TimeoutError) as failure:read_chat_stream(io.BytesIO(event({'choices':[]})),0,900)
    assert failure.value.response_diagnostic['timeout_kind']=='total_deadline'

def test_http_transport_sets_socket_idle_and_does_not_resend_on_timeout():
    class Socket:
        def settimeout(self,value):self.timeout=value
    class Response:
        headers={'Content-Type':'text/event-stream'};status=200
        def __init__(self):
            from types import SimpleNamespace
            self.sock=Socket();self.fp=SimpleNamespace(raw=SimpleNamespace(_sock=self.sock))
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def __iter__(self):return self
        def __next__(self):raise TimeoutError('no stream data')
    r=Response()
    with patch('scene_completion.http_transport.urllib.request.urlopen',return_value=r) as opened:
        with pytest.raises(RuntimeError) as failure:_post_chat_completions_diagnostic('http://test/v1/chat/completions','key',{'stream':True},60,2,idle_timeout=300,total_timeout=900)
    assert opened.call_count==1 and opened.call_args.kwargs['timeout']==60 and r.sock.timeout==300
    assert failure.value.response_diagnostic['timeout_kind']=='idle_read'
    assert failure.value.response_diagnostic['stream_total_timeout_seconds']==900

def test_compact_prompt_retains_all_source_lines_without_repeating_schema():
    d={'source_id':'source','channel':'normal','name':'SR.md','lines':[{'number':2,'text':'中文规则'},{'number':15,'text':'another rule'}]}
    p={'task':'api-map','case_ids':[],'input':{'SR':[d]},'output_schema':{'secret_schema':'not prompt content'},'skill_text':'skill'}
    original=deepcopy(p);message=task_message(p)
    assert '2 | 中文规则' in message and '15 | another rule' in message and 'source' in message
    assert 'secret_schema' not in message and p==original

def test_resolved_stream_timeouts_do_not_replace_explicit_connect_timeout(tmp_path):
    c=resolve({'timeout_seconds':120},tmp_path/'.env')
    assert c['timeout_seconds']==120 and c['stream_idle_timeout_seconds']==300 and c['stream_total_timeout_seconds']==900
    assert public_settings(c)['stream_total_timeout_seconds']==900
