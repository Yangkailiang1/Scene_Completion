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
