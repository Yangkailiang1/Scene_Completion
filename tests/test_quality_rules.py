from copy import deepcopy
import pytest
from scene_completion.normal_rules import normalize_scenarios,validate_rules,rule_matches,rule_exceptions
from scene_completion.concern_hierarchy import resolve_matches
from scene_completion.exception_generation import data_exceptions
from scene_completion.comparison_batches import compare_in_batches
from scene_completion.contracts import packet
from scene_completion.task_partitions import split_task
from tests.test_workflow import scenario,memory_inputs,R
from tests.test_comparison_batches import Client

def test_field_location_and_independent_fields_are_separate_units():
    s=scenario('test');s.update(field='skus[].salePrice / skus[].originalPrice',object='SKU',data_location='body.skus[].salePrice / body.skus[].originalPrice',concern_key='api.data.range',cause='salePrice/originalPrice 为负数')
    v=normalize_scenarios({'scenarios':[s]},{});rows=v['scenarios']
    assert len(rows)==2 and {s['data_location'] for s in rows}=={'body'}
    assert {s['field'] for s in rows}=={'skus[].salePrice','skus[].originalPrice'}
    assert all(s['normalization_origin']['object']=='SKU' for s in rows)
    assert normalize_scenarios(v,{})==v

def test_same_unavailable_failure_does_not_require_inventing_503(tmp_path):
    a=scenario('g',cause='service_unavailable');a.update(concern_key='service.base.availability',object='Catalog',conditions=['本次被调用服务无法执行当前操作'])
    b=deepcopy(a);b.update(id='gt',cause='目录服务不可用',conditions=['Catalog不可用']);b['steps']['documented_follow_up']=[{'action':'HTTP 503','source_refs':R}]
    p=packet('semantic-compare',{'left':[b],'right':[a],'purpose':'GT_G'});p['node_key']='compare';c=Client()
    assert compare_in_batches(p,c,tmp_path)['decisions'][0]['status']=='full' and not c.calls
    b['cause']='查询超时';b['conditions']=['Catalog查询超时'];p['input']['left']=[b];compare_in_batches(p,c,tmp_path)
    assert len(c.calls)==1

def test_negative_stock_has_same_normalized_failure_without_LLM(tmp_path):
    a=scenario('g',cause='minimum');a.update(object='skus[].stock',field='skus[].stock',data_location='body',scope='interface',concern_key='api.data.range',conditions=['skus[].stock已提供','违反minimum约束: 0'])
    b=deepcopy(a);b.update(id='gt',cause='库存为负数 stock<0',conditions=['商品存在','stock为负数'])
    p=packet('semantic-compare',{'left':[b],'right':[a],'purpose':'GT_G'});p['node_key']='stock';c=Client()
    assert compare_in_batches(p,c,tmp_path)['decisions'][0]['status']=='full' and not c.calls

def test_conditional_rule_needs_declared_check_never_invents_a_limit():
    from scene_completion.concern_matching import complete_data_matches
    x=memory_inputs();p=x['api-parameters']['apis'][0]['parameters'][2]
    p['constraints']=[{'id':'size','kind':'size','value':None,'status':'pending','source_refs':[{**R[0],'quote':'校验图片数量在允许范围内'}]}]
    x['concern-match']=resolve_matches(x,[])
    result=[s for s in data_exceptions(x) if s['cause']=='size']
    assert len(result)==1 and result[0]['resolution']=='conditional' and not result[0]['executable']
    assert result[0]['pending_details'] and not any('100' in c for c in result[0]['conditions'])
    p['constraints'][0]['source_refs']=[{**R[0],'quote':'图片信息'}]
    x['concern-match']=resolve_matches(x,[])
    assert not any(s['cause']=='size' for s in data_exceptions(x))

def test_descriptions_are_not_constraints():
    x=memory_inputs();p=x['api-parameters']['apis'][0]['parameters'][1]
    p['constraints']=[{'id':'desc','kind':'other','value':'商品唯一编号','status':'explicit','source_refs':R}]
    x['concern-match']=resolve_matches(x,[])
    assert not any(s['field']==p['name'] and s['cause']=='other' for s in data_exceptions(x))

def test_publishing_can_use_its_actual_update_and_release_rules():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['operation']['kinds']=['publish']
    ref={**R[0],'quote':'Platform校验 version 一致；状态为 DRAFT'}
    r={'id':'lock','interaction_id':i['id'],'owner_service':'Platform','concern_key':'service.resource_mutation.concurrency_consistency','condition':'version 一致','violation':'version 不一致','fields':['version'],'functional_kinds':['publish','update'],'resolution':'explicit','pending_details':[],'source_refs':[ref]}
    x['normal-rules']={'rules':[r],'pending':[]};x['concern-match']=resolve_matches(x,[])
    matches=[m for m in x['concern-match']['matches'] if m['concern_key']==r['concern_key']]
    assert any(m['status']=='applicable' for m in matches)
    assert len(rule_exceptions(x))==1
    doc={'source_id':'positive','name':'sr.md','channel':'normal','lines':[{'number':1,'text':ref['quote']}]}
    validate_rules(x['normal-rules'],{'normal-documents':[doc],'fused-ssd':{'interactions':[i],'rr_sr_links':[]}})
    bad=deepcopy(r);bad['fields']=['invented'];
    with pytest.raises(ValueError,match='field absent'):validate_rules({'rules':[bad]}, {'normal-documents':[doc],'fused-ssd':{'interactions':[i],'rr_sr_links':[]}})

def test_branch_parts_do_not_receive_other_exception_branches():
    branch=lambda n:{'id':str(n),'source_refs':[{**R[0],'line_start':n,'line_end':n,'quote':'branch '+str(n)}]}
    doc={'source_id':'positive','name':'rr.md','channel':'existing','lines':[{'number':n,'text':'branch '+str(n)} for n in (1,2)]}
    parts=split_task('existing-extract',{'branches':{'branches':[branch(1),branch(2)]},'bindings':{'bindings':[{'branch_id':str(n)} for n in (1,2)]},'existing-documents':[doc]})
    assert len(parts)==2
    assert all(len(p['branches']['branches'])==len(p['bindings']['bindings'])==len(p['existing-documents'][0]['lines'])==1 for _,p in parts)

def test_inverse_model_context_contains_positive_conditions_not_generated_negations():
    from scene_completion.task_context import semantic_view
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    inp={'fused-ssd':{'interactions':[i],'rr_sr_links':[]},'normal-rules':{'rules':[{'id':'r','condition':'normal','violation':'generated secret candidate'}]},'test-documents':[]}
    view=semantic_view('test-ground-truth',inp)
    assert view['normal-rules']['rules'][0]['condition']=='normal'
    assert 'generated secret candidate' not in str(view)
    assert inp['normal-rules']['rules'][0]['violation']=='generated secret candidate'

def test_partition_merge_namespaces_machine_ids_without_double_counting():
    from scene_completion.task_partitions import merge_parts
    a=scenario('model-id');b=deepcopy(a);b.update(cause='another cause',conditions=['another condition'])
    result=merge_parts('test-ground-truth',[{'scenarios':[a]},{'scenarios':[b]}])
    assert len({s['id'] for s in result['scenarios']})==2
    assert all(s['source_scenario_id']=='model-id' for s in result['scenarios'])

def test_local_validation_moves_into_owner_without_new_calls():
    from scene_completion.ssd_tools import complete_structure
    from tests.test_workflow import exchange
    root=exchange(sid='entry');local=deepcopy(root);local.update(id='local',parent_id='entry',api_id=None);local['sender']=deepcopy(local['receiver']);local['operation']['name']='校验请求参数'
    log=[];out=complete_structure({'interactions':[root,local],'rr_sr_links':[],'pending':[]},log)
    assert [i['id'] for i in out['interactions']]==['entry']
    assert '校验请求参数' in out['interactions'][0]['operation']['sequence'] and log

def test_rule_subject_keeps_physical_resource_mapping_and_human_caller():
    from scene_completion.normal_rules import rule_subject
    from tests.test_workflow import exchange
    i=exchange();r={'concern_key':'human.authentication'}
    assert rule_subject(r,i)==i['sender']['name']
    i['receiver'].update(name='records表',position='外部数据库');r['concern_key']='database.uniqueness'
    assert rule_subject(r,i)=='records表资源服务'

def test_authentication_taxonomy_follows_actual_caller_without_changing_trigger():
    from scene_completion.normal_rules import identity_concern
    from tests.test_workflow import exchange
    i=exchange()
    assert identity_concern('service_relation.authentication',i)=='human.authentication'
    i['sender'].update(name='OtherService',position='内部服务')
    assert identity_concern('human.authorization',i)=='service_relation.authorization'
    assert identity_concern('api.data.legality',i)=='api.data.legality'

def test_zero_is_an_explicit_boundary_not_an_unknown_constraint():
    from scene_completion.normal_rules import conditional_constraint
    rule={'kind':'minimum','status':'explicit','value':0,'source_refs':[{**R[0],'quote':'stock>=0，数量在允许范围内'}]}
    assert not conditional_constraint(rule)

def test_explicit_normal_tolerance_does_not_become_anomaly_truth():
    from scene_completion.normal_rules import documented_normal_tolerance
    d={'lines':[{'text':'| TEST-X | 非关键字段缺失 | 可选 | 验证部分详情容错 | 返回已有字段，缺失区域隐藏或使用缺省值 |'}]}
    assert documented_normal_tolerance({'test-documents':[d]})
    d['lines'][0]['text']='| TEST-X | 字段缺失 | 异常 | 必须拒绝 |'
    assert not documented_normal_tolerance({'test-documents':[d]})

def test_rule_id_cannot_silently_replace_child_field_with_parent_array():
    from tests.test_workflow import exchange
    i=exchange();s=scenario();s.update(concern_key='api.data.range',field='rows[].amount',object='rows[].amount',rule_id='parent',data_location='body')
    inputs={'fused-ssd':{'interactions':[i],'rr_sr_links':[]},'normal-rules':{'rules':[{'id':'parent','interaction_id':i['id'],'fields':['rows'],'concern_key':'api.data.completeness'}]}}
    out=normalize_scenarios({'scenarios':[s]},inputs,truth=True)['scenarios'][0]
    assert out['field']=='rows[].amount' and out['concern_key']=='api.data.range'
    assert out['rule_id'] is None and out['cause']==s['cause'] and out['interaction_id']==s['interaction_id']
    assert '索引对齐诊断' in out['derivation']

def test_missing_spec_threshold_is_pending_not_a_runtime_exception():
    from scene_completion.normal_rules import separate_unknown_criteria
    r={'id':'r','interaction_id':'req','resolution':'conditional','violation':'缺少具体阈值导致无法判定是否过期','pending_details':['文档没有阈值'],'source_refs':R}
    logs=[];v=separate_unknown_criteria({'rules':[r],'pending':[]},logs)
    assert not v['rules'] and len(v['pending'])==1 and logs[0]['rule_id']=='r'
    r['violation']='超过约定阈值后未刷新数据';r['source_refs']=[{**R[0],'quote':'校验缓存是否满足约定过期规则'}]
    assert separate_unknown_criteria({'rules':[r],'pending':[]})['rules']  # a conditional runtime failure is retained
    r['source_refs']=[{**R[0],'quote':'判断本地数据是否过期；若过期，获取新数据'}]
    assert separate_unknown_criteria({'rules':[r],'pending':[]})['pending']  # unsupported classification stays reviewable

def test_valid_service_rule_is_applied_before_parsing_irrelevant_field_path():
    from tests.test_workflow import exchange
    i=exchange();i['receiver'].update(name='account表',position='内部数据库')
    s=scenario();s.update(concern_key='service.query_retrieval.data_visibility',field='permission',data_location='account表.permission',rule_id='permission')
    r={'id':'permission','interaction_id':'req','concern_key':s['concern_key'],'fields':['permission']}
    v=normalize_scenarios({'scenarios':[s]},{'fused-ssd':{'interactions':[i]},'normal-rules':{'rules':[r]}})['scenarios'][0]
    assert v['object']=='account表资源服务' and v['field'] is None and v['data_location'] is None
