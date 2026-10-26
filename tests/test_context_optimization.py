from copy import deepcopy
import pytest
from scene_completion.context_budget import check
from scene_completion.model_client import SemanticClient
from scene_completion.concern_presentation import paths
from scene_completion.concern_registry import default_registry
from scene_completion.contracts import schema
from scene_completion.indexed_context import EvidenceContext
from scene_completion.task_context import semantic_view
from scene_completion.task_partitions import split_task
from scene_completion.execution_events import EventStore
from scene_completion.usage_index import indexed_usage
from tests.test_workflow import memory_inputs,R,exchange,scenario


def inverse_packet():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['data']['sequence']=deepcopy(x['api-parameters']['apis'][0]['parameters'])
    other=exchange(sid='irrelevant');other['receiver']['name']='OtherService'
    rule=lambda rid,iid,field:{'id':rid,'interaction_id':iid,'owner_service':'Platform','concern_key':'api.data.range','condition':'page >= 1','violation':'page < 1','fields':[field],'functional_kinds':['read'],'resolution':'explicit','pending_details':[],'source_refs':R}
    m={'binding_id':'binding-page','status':'applicable','interaction_id':i['id'],'target':'data','object':'page','data_location':'query','scope':'interface','concern_key':'api.data.range','source_refs':R}
    inp={'fused-ssd':{'interactions':[i,other],'rr_sr_links':[],'pending':[]},'normal-constraints':x['api-parameters'],'normal-rules':{'rules':[rule('own',i['id'],'page'),rule('other',other['id'],'secret')],'pending':[]},'identified-concerns':{'matches':[m],'pending':[]},'test-documents':[{'source_id':'positive','channel':'test','name':'t.md','lines':[{'number':1,'text':R[0]['quote']}]}],'registry':x['registry']}
    return {'task':'test-ground-truth','input':inp,'output_schema':schema('test-ground-truth'),'instructions':'test','skill_text':'test','case_ids':['CASE-A'],'batch_id':'test'}


def test_request_context_bound_includes_tools_history_schema_and_output_before_transport():
    calls=[];client=SemanticClient({'api_key':'test','base_url':'https://example.invalid/v1','max_context_tokens':2000},transport=lambda *a:calls.append(a))
    body={'model':'m','max_tokens':100,'messages':[{'role':'system','content':'short'},{'role':'user','content':'short'}],'tools':[{'schema':'x'*3000}]}
    with pytest.raises(RuntimeError) as exc:client.post('/chat/completions',body)
    assert not calls and exc.value.response_diagnostic['not_sent']
    body.pop('tools');assert check(body,{'max_context_tokens':2000})['output_reserve']==100
    body['messages'].append({'role':'assistant','content':'x'*3000})
    with pytest.raises(RuntimeError):check(body,{'max_context_tokens':2000})


def test_presentation_paths_reference_shared_ids_and_preserve_definitions():
    defs=default_registry()['definitions'];before=deepcopy(defs)
    assert len(paths('api.data.range',defs))==2
    assert paths('api.data.range',defs,'return')[0][-1]=='输出数据'
    assert paths('service_relation.authentication',defs)[0][-1]=='Service之间'
    assert paths('unknown',defs)==[['待归类']] and defs==before


def test_inverse_context_retains_index_and_reads_only_allowed_deferred_evidence():
    p=inverse_packet();v=semantic_view(p['task'],p['input'])
    assert len(v['fused-ssd']['interactions'])==1 and len(v['interaction_index'])==2
    assert {r['id'] for r in v['normal-rules']['rules']}=={'own'}
    assert {x['name'] for a in v['normal-constraints']['apis'] for x in a['parameters']}=={'page'}
    assert 'api.data.legality' not in v['registry']['definitions']
    ctx=EvidenceContext(p);ids=list(ctx.pool);assert ctx.lookup(ids[:1])
    with pytest.raises(ValueError):ctx.lookup(['not-allowed'])
    with pytest.raises(ValueError):ctx.lookup(ids[:1]*9)
    assert 'violation' not in str(ctx.input)


def test_compact_refinement_roundtrip_restores_only_independent_anchor():
    p=inverse_packet();ctx=EvidenceContext(p);r=scenario();r.update(object='page',field='page',concern_key='api.data.range',scope='interface',data_location='query',cause='below minimum',conditions=['page < 1'],resolution='explicit',executable=True,pending_details=[],scenario_type='exception')
    row=ctx.encode_output({'scenarios':[r],'pending':[]})['scenarios'][0]
    assert row['binding_ref']=='binding-page' and 'interaction_id' not in row and 'steps' not in row
    result=ctx.expand({'scenarios':[row],'pending':[]})['scenarios'][0]
    assert result['interaction_id']=='req' and result['field']=='page' and result['conditions']==['page < 1']
    row['binding_ref']='foreign'
    with pytest.raises(ValueError):ctx.expand({'scenarios':[row]})


def test_object_partition_keeps_cross_field_conditions_intact():
    p=inverse_packet();inp=p['input'];m=deepcopy(inp['identified-concerns']['matches'][0]);m.update(binding_id='second',object='pageSize');inp['identified-concerns']['matches'].append(m)
    inp['branches']={'branches':[{'id':'source-branch','source_refs':R}]}
    units=split_task('existing-extract',inp)
    assert len(units)==2
    assert all(len(q['identified-concerns']['matches'])==1 for _,q in units)


def test_usage_peak_is_single_request_not_cumulative_and_unknown_is_not_zero(tmp_path):
    s=EventStore(tmp_path)
    for n,attempt in enumerate((1,2)):
        s.append('request_started',task_key='C:task',model_call_id=str(n),attempt=attempt,requested_model='m')
        s.append('request_finished',task_key='C:task',model_call_id=str(n),usage={'prompt_tokens':100+100*n,'completion_tokens':10,'total_tokens':110+100*n})
    s.append('request_started',task_key='C:task',model_call_id='bad',attempt=2,requested_model='m')
    s.append('request_failed',task_key='C:task',model_call_id='bad',diagnostic={'failure_category':'transport_timeout'})
    row=indexed_usage(tmp_path,view='tasks')['items'][0]
    assert row['input_tokens']==300 and row['max_input_tokens']==200 and row['reported_total_tokens']==320
    assert row['sent_calls']==3 and row['failed_calls']==1 and row['repair_calls']==2 and row['unknown_usage_calls']==1


def test_production_supplement_retains_test_preconditions_and_steps_after_regression():
    p=inverse_packet();p.update(task='test-supplement',output_schema=schema('test-supplement'))
    p['input']['normal-rules']['rules']=p['input']['normal-rules']['rules'][:1]
    p['input']['normal-rules']['rules'][0]['concern_key']='service.resource_mutation.business_constraint'
    ctx=EvidenceContext(p);required=ctx.packet['output_schema']['properties']['tests']['items']['required']
    assert 'preconditions' in required and 'steps' in required


def test_refinement_cannot_claim_unknown_format_as_executable():
    from scene_completion.refinement_context import expand
    p=inverse_packet();m=p['input']['identified-concerns']['matches'][0]
    m.update(concern_key='api.data.format',concrete_rule=None)
    row={'binding_ref':m['binding_id'],'cause':'格式错误','conditions':[], 'trigger':'违反约定格式','documented_follow_up':[], 'resolution':'explicit','executable':True}
    value=expand(row,p['input'],'test-ground-truth')
    assert value['resolution']=='conditional' and not value['executable'] and value['pending_details']
