from copy import deepcopy
from scene_completion.result_alignment import align_rows,aggregate_metrics
from scene_completion.failure_units import normalize_inverse_units
from scene_completion.task_context import semantic_view
from tests.test_workflow import scenario,exchange


def test_rows_require_all_three_saved_edges_and_keep_broad_references_and_orphans():
    channels={k:[{'id':v,'conditions':['failure']} for v in vs] for k,vs in {'G':['g1','g2','g3'],'E':['e','alone'],'GT':['t1','t2','orphan']}.items()}
    p=lambda a,b:{'checker_scenario_id':a,'generated_scenario_id':b,'status':'full'}
    pairs={'G_E':[p('g1','e'),p('g2','e')],'GT_G':[p('t1','g1'),p('t2','g2')],'GT_E':[p('t1','e')]}
    rows=align_rows(channels,pairs)
    assert [r['status'] for r in rows]==['triple','conflict','single','single','single']
    assert sum('e' in r['shared_e_ids'] for r in rows)==2
    assert {s['id'] for r in rows for s in r['cells']['GT']}=={'t1','t2','orphan'}
    assert all(len(r['cells']['GT'])<=1 for r in rows)


def test_metrics_sum_counts_not_percentages_and_empty_stays_na():
    rows=[{'metrics':{'generation_validity':{'status':'适用','numerator':1,'denominator':2}}},{'metrics':{'generation_validity':{'status':'适用','numerator':1,'denominator':8}}}]
    v=aggregate_metrics(rows);assert v['generation_validity']['value']==20
    assert v['missing_exception_miss_rate']['value'] is None


def test_case_metrics_route_is_not_captured_as_a_case_id(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    app=create_app(tmp_path/'projects');client=TestClient(app)
    rid=client.post('/api/projects',json={'name':'A','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}]}}).json()['id']
    response=client.get('/api/projects/'+rid+'/results/metrics')
    assert response.status_code==200 and response.json()['cases']==[]
    assert response.json()['metrics']['generation_validity']['value'] is None


def test_named_transport_failure_moves_only_to_unique_actual_call_and_keeps_origin():
    request=exchange(sid='call');request['receiver']['name']='LookupService'
    response=deepcopy(request);response.update(id='outer',direction='return');response['receiver']['name']='Human';response['sender']['name']='Boundary'
    s=scenario('t');s.update(interaction_id='outer',object='Boundary',cause='LookupService 查询超时',field=None,data_location=None)
    inputs={'fused-ssd':{'interactions':[request,response]}}
    v=normalize_inverse_units({'scenarios':[s]},inputs)['scenarios'][0]
    assert v['interaction_id']=='call' and v['normalization_origin']['interaction_id']=='outer'
    assert v['cause']==s['cause'] and s['interaction_id']=='outer'
    another=deepcopy(request);another['id']='another';inputs['fused-ssd']['interactions'].append(another)
    assert normalize_inverse_units({'scenarios':[s]},inputs)['scenarios'][0]['interaction_id']=='outer'


def test_binding_and_refinement_use_the_same_unique_failure_owner():
    from scene_completion.failure_units import normalize_bindings
    request=exchange(sid='call');request['receiver']['name']='LookupService'
    result=normalize_bindings({'bindings':[{'branch_id':'B','interaction_id':'return','status':'confirmed','basis':'old'}]},
        {'branches':{'branches':[{'id':'B','description':'LookupService 查询超时，系统返回504'}]},'fused-ssd':{'interactions':[request]}})
    assert result['bindings'][0]['interaction_id']=='call' and '唯一' in result['bindings'][0]['basis']

def test_transport_owner_is_normalized_before_inverse_binding_validation():
    from scene_completion.inverse_alignment import expand_inverse
    request=exchange(sid='call');request['receiver']['name']='LookupService'
    reply=deepcopy(request);reply.update(id='reply',direction='return');reply['receiver']['name']='Boundary';reply['sender']['name']='LookupService'
    s=scenario('s');s.update(interaction_id='reply',object='Boundary',cause='LookupService查询超时',field=None,original_branch_id='B',coverage_kind='exact')
    result=expand_inverse({'scenarios':[s]},{'fused-ssd':{'interactions':[request,reply]},'branches':{'branches':[{'id':'B','description':'LookupService查询超时','source_refs':s['source_refs']}]},'bindings':{'bindings':[{'branch_id':'B','interaction_id':'call','status':'confirmed','basis':'named unique call'}]}})
    assert result['scenarios'][0]['interaction_id']=='call'


def test_same_test_tautological_duplicate_merges_but_different_fields_do_not():
    a=scenario('a');a.update(field='id',data_location='path',cause='标识格式错误',source_refs=[{'source_id':'test','line_start':1,'line_end':1,'quote':'| TEST-ID-A | 标识格式错误 |'}])
    b=deepcopy(a);b.update(id='b',cause='标识格式错误导致格式校验失败')
    c=deepcopy(b);c.update(id='c',field='other')
    out=normalize_inverse_units({'scenarios':[a,b,c]},{})['scenarios']
    assert len(out)==2 and out[0]['source_unit_ids']==['a','b'] and out[0]['quality_notes']


def test_semantic_comparison_cannot_be_biased_by_concern_or_response_but_keeps_failure_scope():
    s=scenario('s');s.update(scope='interface',field='id',data_location='path',concern_key='some.classification')
    out=semantic_view('semantic-compare',{'left':[s],'right':[deepcopy(s)],'purpose':'GT_G'})
    assert 'concern_key' not in out['left'][0] and 'steps' not in out['left'][0]
    assert out['left'][0]['scope']=='interface' and out['left'][0]['conditions']==s['conditions']


def test_foreign_local_check_is_evidence_bound_pending_not_a_database_rule():
    from scene_completion.normal_rules import separate_foreign_checks
    i=exchange();i['sender']['name']='Writer';i['receiver']['name']='Database'
    ref={'source_id':'normal','line_start':1,'line_end':1,'quote':'Writer按 requestKey 执行幂等校验。'}
    i['operation']['source_refs']=[ref];i['data']['sequence']=[]
    rule={'id':'r','interaction_id':i['id'],'fields':['requestKey'],'source_refs':[{'source_id':'normal','line_start':2,'line_end':2,'quote':'Writer写入记录。'}]}
    inputs={'fused-ssd':{'interactions':[i]},'normal-documents':[{'source_id':'normal','lines':[{'number':1,'text':ref['quote']},{'number':2,'text':'Writer写入记录。'}]}]}
    out=separate_foreign_checks({'rules':[rule],'pending':[]},inputs)
    assert out['rules']==[] and out['pending'][0]['source_refs']==[ref] and '发送方Writer' in out['pending'][0]['reason']
    i['operation']['source_refs']=[]
    assert separate_foreign_checks({'rules':[rule],'pending':[]},inputs)['rules']==[rule]  # no invented proof


def test_explicit_test_cannot_disappear_without_a_truth_or_pending_record():
    import pytest
    from scene_completion.validation import validate_result
    text='| TEST-Q-01 | 资源不存在 | 异常 | 服务可用 | 查询不存在资源 |'
    doc={'source_id':'test','name':'test.md','channel':'test','lines':[{'number':1,'text':text}]}
    with pytest.raises(ValueError,match='不能静默'):
        validate_result('test-ground-truth',{'scenarios':[],'pending':[]},{'test-documents':[doc]})
    pending={'interaction_id':'unknown','object':'资源','concern_key':'service.query_retrieval.resource_existence','reason':'无法确定执行服务','source_refs':[{'source_id':'test','line_start':1,'line_end':1,'quote':text}]}
    validate_result('test-ground-truth',{'scenarios':[],'pending':[pending]},{'test-documents':[doc]})


def test_broad_parent_is_canonical_once_per_original_branch():
    from tests.test_workbench_v3 import inverse_fixture
    from scene_completion.inverse_alignment import expand_inverse
    x,s,inputs=inverse_fixture();other=deepcopy(s);other.update(id='other',cause='仅某字段非法',field='page')
    result=expand_inverse({'scenarios':[s,other]},inputs)['scenarios']
    broad=[s for s in result if s.get('coverage_kind')=='input_parameters']
    assert len(broad)==1 and broad[0]['field'] is None and broad[0]['cause']=='输入参数非法'
    assert other['id'] in broad[0]['source_unit_ids']


def test_model_bookkeeping_is_not_part_of_failure_facts_or_model_schema():
    from scene_completion.failure_units import clean_model_scenarios,MODEL_METADATA_FIELDS
    from scene_completion.indexed_context import EvidenceContext
    from scene_completion.contracts import packet,registry
    s=scenario('source');s['normalization_origin']=None;s['quality_notes']=['model-made bookkeeping']
    out=clean_model_scenarios({'scenarios':[s]})['scenarios'][0]
    assert out['cause']==s['cause'] and out['conditions']==s['conditions'] and out['source_refs']==s['source_refs']
    assert all(k not in out for k in MODEL_METADATA_FIELDS) and s['normalization_origin'] is None
    context=EvidenceContext(packet('test-ground-truth',{'test-documents':[],'normal-constraints':{'apis':[]},'registry':registry()}))
    props=context.packet['output_schema']['properties']['scenarios']['items']['properties']
    assert not set(MODEL_METADATA_FIELDS)&set(props)


def test_expected_response_is_folded_into_own_test_failure_not_counted_again():
    from scene_completion.failure_units import normalize_test_assertions
    call=exchange(sid='call');reply=deepcopy(call);reply.update(id='reply',direction='return')
    ref={'source_id':'test','line_start':1,'line_end':1,'quote':'| TEST-A-01 | 规则失败 | 异常 | 草稿 | 缺少类目属性后发布 | API | 校验分流 | 返回409并进入审核队列 | spec |'}
    primary=scenario('failure');primary.update(interaction_id='call',cause='缺少类目属性',source_refs=[ref])
    handling=deepcopy(primary);handling.update(id='handling',interaction_id='reply',cause='规则失败时返回错误响应',field='status')
    out=normalize_test_assertions({'scenarios':[primary,handling]},{'fused-ssd':{'interactions':[call,reply]}})
    assert len(out['scenarios'])==1
    assert out['scenarios'][0]['cause']=='缺少类目属性'
    assert 'handling' in out['scenarios'][0]['source_unit_ids']
    assert out['scenarios'][0]['steps']['documented_follow_up'][-1]['action']=='返回409并进入审核队列'
    # Explicitly injecting an erroneous response is a genuine failure.
    ref['quote']='| TEST-A-01 | 返回错误 | 异常 | 草稿 | 模拟返回status字段错误 | API | 校验响应 | 拒绝错误结果 | spec |'
    assert len(normalize_test_assertions({'scenarios':[primary,handling]},{'fused-ssd':{'interactions':[call,reply]}})['scenarios'])==2


def test_recovery_only_unit_uses_explicit_trigger_and_unique_call_without_new_classification():
    from scene_completion.failure_units import normalize_test_assertions
    call=exchange(sid='call');call['receiver']['name']='IndexService'
    reply=deepcopy(call);reply.update(id='reply',direction='return');reply['receiver']['name']='Human'
    s=scenario('recovery');s.update(interaction_id='reply',cause='同步失败后状态更新并重试',field=None,concern_key='service.release_activation.failure_recovery',source_refs=[{'source_id':'test','line_start':1,'line_end':1,'quote':'| TEST-A-02 | 同步失败 | 异常 | 满足发布条件 | IndexService 同步失败 | API | 验证恢复 | 记录任务并重试 | spec |'}])
    out=normalize_test_assertions({'scenarios':[s]},{'fused-ssd':{'interactions':[call,reply]}})['scenarios'][0]
    assert out['interaction_id']=='call' and out['cause']=='IndexService 同步失败'
    assert out['concern_key']==s['concern_key'] and out['steps']['documented_follow_up'][0]['action']=='记录任务并重试'
    duplicate=deepcopy(call);duplicate['id']='another'
    unchanged=normalize_test_assertions({'scenarios':[s]},{'fused-ssd':{'interactions':[call,duplicate,reply]}})['scenarios'][0]
    assert unchanged['cause']==s['cause']  # ambiguous ownership is not guessed
