from types import SimpleNamespace
from pathlib import Path
import pytest
from scene_completion.diagnosis import validate,quote_catalog
from scene_completion.semantic_backend import prepare_packets,read_json,write_json,SemanticClient
from scene_completion.concern_gap_dag import Packets
from scene_completion.case_dag import CallGate,TaskBlocked,TaskRejected
import time


def test_literal_quotes_are_checked_against_original_strings_not_python_repr():
    source='第一行\n用户说"查询订单"，返回查询结果。'
    payload={'allowed_inputs':[{'original':source}]}
    packet={'input':payload}
    output={'action':'recheck','reason':'原文已有该返回','evidence_quotes':[source], 'targets':['return']}
    assert validate(packet,output)[0]['evidence_quotes']==[source]
    payload['evidence_catalog']=quote_catalog(payload['allowed_inputs'])
    output['evidence_quotes']=[];output['evidence_refs']=[payload['evidence_catalog'][0]['id']]
    assert validate(packet,output)[0]['evidence_quotes']==[payload['evidence_catalog'][0]['quote']]
    output['evidence_refs']=['invented']
    with pytest.raises(ValueError):validate(packet,output)


def test_bad_diagnosis_is_bounded_and_never_replaces_original_failure(tmp_path,monkeypatch):
    folder=tmp_path/'original'
    prepare_packets(folder,'gap-fixture',[{'source':'顾客查询订单'}],[],{})
    client=SimpleNamespace(config={},model=lambda kind:'fixture')
    packets=Packets(tmp_path,SimpleNamespace(agent_mode='external'),client,CallGate(1))
    calls=[]
    def reject(folder,validator):
        calls.append(str(folder));raise TaskRejected({'errors':{'bad':'quote is not literal'}})
    monkeypatch.setattr(packets,'execute',reject)
    original={'errors':{'one':'bad source field'},'output':{'folder':str(folder)}}
    for _ in range(2):
        with pytest.raises(TaskBlocked) as exc:packets.diagnose(tmp_path,'graphs',{'folder':str(folder)},original,1)
        assert exc.value.status=='diagnosis_blocked'
    assert len(calls)==2 and original['output']['folder']==str(folder)
    assert all('diagnosis' in path for path in calls)


def test_context_guard_stops_before_transport_and_does_not_truncate(monkeypatch):
    monkeypatch.setenv('CTX_KEY','private')
    calls=[]
    client=SemanticClient({'agent_model':'ecnu-plus','max_context_tokens':2000,'max_tokens':1000,
        'base_url':'https://fixture.invalid','api_key_env':'CTX_KEY'},lambda *args:calls.append(args))
    packet={'stage':'gap-fixture','input':{'source':'中文'*1000}}
    with pytest.raises(RuntimeError) as exc:client.agent(packet)
    assert exc.value.response_diagnostic['failure_category']=='context_budget_exceeded'
    assert not calls and len(packet['input']['source'])==2000


def test_429_cooldown_applies_even_when_parallelism_is_already_one():
    states=[];gate=CallGate(1,on_change=states.append)
    gate.observe({'failure_category':'rate_limited','retry_after_seconds':1})
    start=time.monotonic()
    assert gate.call(lambda:'next-ready-case')=='next-ready-case'
    assert time.monotonic()-start>=.9
    assert states[0]['effective_max']==1 and states[0]['not_before_unix']>0
