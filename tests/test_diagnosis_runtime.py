from types import SimpleNamespace
from pathlib import Path
import pytest
from scene_completion.diagnosis import validate,quote_catalog
from scene_completion.semantic_backend import prepare_packets,read_json,write_json,SemanticClient
from scene_completion.concern_gap_dag import Packets
from scene_completion.case_dag import CallGate,TaskBlocked,TaskRejected
from scene_completion.rejected_task_revalidation import promote_offline,offline_ready
from scene_completion.sources import fingerprint
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


def test_diagnosis_may_quote_the_rejected_value_only_alongside_original_source():
    original='顾客下单后系统返回订单号'
    rejected='MOUNT-5FAFF836DF'
    packet={'input':{'allowed_inputs':[{'original':original}],
        'failed_outputs_from_same_channel':[{'items':[{'mount_id':rejected}]}]}}
    only_failed={'action':'repair','reason':'挂载点编号与原文不符','evidence_quotes':[rejected],
        'targets':['items[0].mount_id']}
    # The channel's own rejected value is quotable material, but a diagnosis
    # that rests on it alone would only judge the output against itself.
    with pytest.raises(ValueError) as exc:validate(packet,only_failed)
    assert 'original-source evidence' in str(exc.value)
    both=dict(only_failed,evidence_quotes=[rejected,original])
    assert validate(packet,both)[0]['evidence_quotes']==[rejected,original]


def test_preserved_attempt_is_readmitted_only_with_its_own_execution_proof(tmp_path):
    folder=tmp_path/'rejected'
    prepare_packets(folder,'gap-fixture',[{'original_source':'顾客查询订单'}],[],{'items':[]})
    batch=read_json(folder/'manifest.json')['batches'][0]
    def proven(**over):
        value={'batch_id':batch['batch_id'],'input_hash':batch['input_hash'],'model':'fixture',
            'execution_model_evidence':{'requested_model':'fixture'},'items':[]}
        value.update(over);return value
    def validator(packet,result):
        assert packet['input']['original_source']=='顾客查询订单'
        return result['items']
    def attempt(number,result):
        path=folder/'attempts'/(batch['batch_id']+f'-{number}.json')
        write_json(path,{'validation_error':'old validator bug','result':result})
        return path
    # Newest first: an attempt with no request evidence and one whose preserved
    # result belongs to another input are skipped rather than promoted.
    attempt(3,{'batch_id':batch['batch_id'],'input_hash':batch['input_hash'],'model':'fixture','items':[]})
    attempt(2,proven(input_hash='other'))
    assert promote_offline(folder,validator)==[] and not (folder/'results'/(batch['batch_id']+'.json')).exists()
    assert offline_ready(folder,validator) is False
    original=attempt(1,proven())
    proofs=promote_offline(folder,validator)
    assert proofs[0]['attempt']==str(original.resolve())
    assert proofs[0]['attempt_hash']==fingerprint(read_json(original))
    assert (proofs[0]['batch_id'],proofs[0]['input_hash'],proofs[0]['original_error'])==(
        batch['batch_id'],batch['input_hash'],'old validator bug')
    assert read_json(folder/'results'/(batch['batch_id']+'.json'))['items']==[]
    assert offline_ready(folder,validator) is True


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


def test_diagnosis_locates_original_packet_using_rejected_unit_source_id(tmp_path, monkeypatch):
    folder=tmp_path/'original'
    prepare_packets(folder, 'gap-normalize-G', [
        {'scenarios':[{'scenario_id':'G1','original':'original first clause'}]},
        {'scenarios':[{'scenario_id':'G2','original':'original second clause'}]}], [], {})
    client=SimpleNamespace(config={}, model=lambda _: 'fixture')
    packets=Packets(tmp_path, SimpleNamespace(agent_mode='external'), client, CallGate(1))
    captured=[]
    def execute(out, validator):
        batch=read_json(out/'manifest.json')['batches'][0]
        packet=read_json(out/'packets'/(batch['batch_id']+'.json'))
        captured.append(packet['input'])
        return {'values':[{'action':'repair','reason':'separate atomic condition','targets':['G2']}], 'folder':str(out)}
    monkeypatch.setattr(packets, 'execute', execute)
    target={'folder':str(folder),'values':[{'unit_id':'U2','source_scenario_id':'G2'}]}
    failure={'findings':[{'unit_id':'U2','atomic':False}], 'output':{'large_unrelated':'x'*300000}}
    packets.diagnose(tmp_path, 'reverse-G', target, failure, 1)
    assert len(captured[0]['allowed_inputs'])==1
    assert captured[0]['allowed_inputs'][0]['scenarios'][0]['scenario_id']=='G2'
    assert 'output' not in captured[0]['failure']
    assert len(failure['output']['large_unrelated'])==300000


def test_repair_failure_prompt_excludes_successful_full_stage_output():
    from scene_completion.diagnosis import failure_view, rejection_ids
    original={'findings':[{'unit_id':'U1'}], 'output':{'values':['successful']}}
    assert failure_view(original)=={'findings':[{'unit_id':'U1'}]}
    assert rejection_ids(original, {'values':[{'unit_id':'U1','source_scenario_id':'G1'}]})=={'U1','G1'}
    assert original['output']['values']==['successful']


def test_focused_diagnosis_retains_exact_rejected_sources_and_shares_common_context():
    from scene_completion.diagnosis import focus_input, share_allowed_inputs, strings
    original={'scenarios':[{'scenario_id':'G1','source':'first'}, {'scenario_id':'G2','source':'second'}],
        'original_evidence':[{'scenario_id':'G1','text':'original first'}, {'scenario_id':'G2','text':'original second'}],
        'concern_definitions':{'C':'exact taxonomy definition'}, 'nodes':[{'id':'N'}]}
    first=focus_input(original, {'G1'});second=focus_input(original, {'G2'})
    assert len(original['scenarios'])==2
    assert first['original_evidence']==[{'scenario_id':'G1','text':'original first'}]
    shared=share_allowed_inputs([first,second])
    assert shared[-1]['shared_stage_context']['concern_definitions']==original['concern_definitions']
    assert sum(s=='exact taxonomy definition' for s in strings(shared))==1
    assert {'original first','original second'} <= set(strings(shared))


def test_recheck_salts_only_new_packets_and_keeps_original_success_identity(tmp_path):
    from scene_completion.concern_gap_dag import Pipeline
    folder=tmp_path/'recheck'
    prepare_packets(folder, 'gap-reverse-check-G', [{'units':[{'unit_id':'U1'}]}, {'units':[{'unit_id':'U2'}]}], [], {})
    before=read_json(folder/'manifest.json'); first=before['batches'][0]
    Pipeline.salt(folder, {'action':'repair'}, 2, retained=[first['batch_id']])
    after=read_json(folder/'manifest.json')
    assert after['batches'][0]==first
    assert after['batches'][1]!=before['batches'][1]
    old=read_json(folder/'packets'/(first['batch_id']+'.json'))
    new=read_json(folder/'packets'/(after['batches'][1]['batch_id']+'.json'))
    assert 'fresh_recheck' not in old['input']
    assert new['input']['fresh_recheck']['round']==2


def test_repair_taxonomy_projection_retains_every_definition_and_source_input():
    from scene_completion.diagnosis import repair_input
    original={'scenarios':[{'scenario_id':'G1','trigger_condition':'exact original'}],
        'concern_definitions':{'C':{'key':'C','description':'full definition','atomic_exception_types':['reason'],
            'concern_subject':'request','layers':['SR'],'registry_version':'v1','evidence_types':['ssd']}}}
    result=repair_input(original)
    assert result['scenarios']==original['scenarios']
    assert set(result['concern_definitions'])=={'C'}
    assert result['concern_definitions']['C']['description']=='full definition'
    assert result['concern_definitions']['C']['atomic_exception_types']==['reason']
    assert result['concern_registry_hash']==fingerprint(original['concern_definitions'])
    assert 'registry_version' in original['concern_definitions']['C']
def test_failure_prompt_excludes_candidate_artifacts_and_preserves_actual_findings():
    from copy import deepcopy
    from scene_completion.diagnosis import failure_view
    failure = {'findings': [{'unit_id': 'failed', 'cause_correct': False}],
        'output': {'values': ['full review']},
        'candidate_replacements': {'G': ['all generated scenes'], 'normalize-G': ['all units']},
        'candidate_source_repair': {'hash': 'audit-only'},
        'source_obligation_findings': ['already repaired old source defects'],
        'recovered_from_journal': '/local/journal', 'normalization_folder': '/local/cache'}
    original = deepcopy(failure)
    assert failure_view(failure) == {'findings': original['findings']}
    assert failure == original
def test_diagnosis_budget_key_binds_instructions_contract_and_actual_model():
    from scene_completion.diagnosis import protocol_key
    payload = {'allowed_inputs': [{'clause': 'original evidence'}]}
    instructions = ['diagnose only']
    contract = {'action': 'repair|recheck|confirm'}
    execution = {'model': 'batch-a', 'endpoint': 'endpoint-a'}
    original = protocol_key(payload, instructions, contract, execution)
    assert original == protocol_key(payload, list(instructions), dict(contract), dict(execution))
    assert original != protocol_key(payload, ['diagnose only; no repaired rows'], contract, execution)
    assert original != protocol_key(payload, instructions, {'reason': 'short'}, execution)
    assert original != protocol_key(payload, instructions, contract, {**execution, 'model': 'batch-b'})


def test_diagnosis_accepts_original_scoped_ids_but_not_output_only_or_orphan_catalogs():
    from scene_completion.evidence_refs import prepare_packet
    from scene_completion.diagnosis import validate
    stage = prepare_packet({'stage': 'gap-normalize-G', 'input': {
        'scenarios': [{'scenario_id': 'G1', 'trigger_condition': 'required product name missing'}]},
        'instructions': [], 'output_contract': {}})
    entry = stage['input']['evidence_catalog'][0]
    packet = {'input': {'allowed_inputs': [stage['input']], 'evidence_catalog': []}}
    result = {'action': 'repair', 'reason': 'correct the rejected code',
        'evidence_refs': [entry['id']], 'evidence_quotes': [], 'targets': ['object_code']}
    assert validate(packet, result)[0]['evidence_quotes'] == [entry['quote']]
    from scene_completion.diagnosis import share_allowed_inputs
    shared = share_allowed_inputs([stage['input'], dict(stage['input'], extra='context')])
    assert validate({'input': {'allowed_inputs': shared}}, result)[0]['evidence_quotes'] == [entry['quote']]
    with pytest.raises(ValueError):
        validate({'input': {'allowed_inputs': [{}],
            'failed_outputs_from_same_channel': [stage['input']]}}, result)
    orphan = dict(stage['input'], scenarios=[])
    with pytest.raises(ValueError):
        validate({'input': {'allowed_inputs': [orphan]}}, result)
    corrupted = dict(entry, quote='an invented source')
    with pytest.raises(ValueError):
        validate({'input': {'allowed_inputs': [dict(stage['input'], evidence_catalog=[corrupted])]}}, result)

