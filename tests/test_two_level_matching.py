"""Count actual recognition, then independent failures; never registry size."""
from copy import deepcopy
import pytest
from tests.test_workflow import memory_inputs as _memory_inputs, R, parameter, exchange, scenario, fake_pipeline
from scene_completion.concern_alignment import (recognize,compare,bind_scenarios,index_elements,
    supplemental_concerns,VERSION,attach_report)
from scene_completion.concern_hierarchy import resolve_matches
from scene_completion.scenario_patterns import applicability,generated
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.storage import read_json
from scene_completion.contracts import packet,registry


def memory_inputs():
    x=_memory_inputs()
    x['enriched-interactions']={'interactions':x['sr-ssd']['interactions']}
    x['normal-rules']={'rules':[],'pending':[]}
    return x


def raw(key='api.data.range',field='pageSize',target='data',**extra):
    return {'interaction_id':'req','target':target,'object':field,'concern_key':key,'basis':'本交互的明确规则',
            'concrete_rule':'1≤pageSize≤100','source_refs':R,'data_location':'query' if target=='data' else None,**extra}


def recognized(x,rows):return recognize(x,{'matches':rows,'pending':[]})


def test_empty_model_recognition_is_not_registry_or_mechanical_candidates():
    x=memory_inputs();assert resolve_matches(x,[])=={'matches':[],'pending':[]}
    x['concern-match']=resolve_matches(x,[])
    assert not generated(applicability(x))['scenarios']


def test_one_recognized_range_is_one_concern_but_two_failure_scenarios():
    x=memory_inputs();g=recognized(x,[raw()]);x['concern-match']=g
    scenes=generated(applicability(x))['scenarios']
    assert len(g['matches'])==1 and len(scenes)==2
    assert {s['failure_rule']['kind'] for s in scenes}=={'minimum','maximum'}
    assert {b for s in scenes for b in s['concern_binding_ids']}=={g['matches'][0]['binding_id']}
    e=recognize(x,{'matches':[raw()]},inverse=True)
    summary=compare(g,e,e)
    assert len(summary['G_c'])==1 and not summary['M_c']
    assert summary['metrics']['generation_validity']['value']==100
    assert summary['metrics']['missing_exception_miss_rate']['status']=='不适用'
    # A covered concern does not remove either concrete scene from generation.
    assert len(scenes)==2


def test_recognized_concern_survives_failed_or_empty_scene_generation():
    x=memory_inputs();g=recognized(x,[raw()]);report=compare(g,{'matches':[]},g)
    assert len(report['G_c'])==len(report['M_c'])==1
    assert report['metrics']['missing_exception_miss_rate']['value']==0
    assert bind_scenarios({'scenarios':[]},x,g,gate=True)['scenarios']==[]
    assert len(report['G_c'])==1


def test_direction_location_path_and_actual_occurrence_are_all_distinct():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    i['data']['sequence']=[parameter('skus[].stock','body',True,'integer'),parameter('skus[].stock','query',True,'integer')]
    a=recognize(x,{'matches':[raw('api.data.type','body.skus[].stock',data_location='body')]},inverse=True)
    b=recognize(x,{'matches':[raw('api.data.type','skus[].stock',data_location='query')]},inverse=True)
    assert a['matches'][0]['binding_id']!=b['matches'][0]['binding_id']
    second=deepcopy(i);second.update(id='req2',sequence=2);x['sr-ssd']['interactions'].append(second)
    c=recognize(x,{'matches':[{**raw('api.data.type','skus[].stock',data_location='body'),'interaction_id':'req2'}]},inverse=True)
    assert a['matches'][0]['binding_id']!=c['matches'][0]['binding_id']
    returned=deepcopy(i);returned.update(id='ret',direction='return',sequence=3,parent_id='req');returned['sender'],returned['receiver']=returned['receiver'],returned['sender'];returned['data']['sequence']=[parameter('skus[].stock','response',True,'integer')];x['sr-ssd']['interactions'].append(returned)
    ids=[e['element_id'] for e in index_elements(x) if e['target']=='data'];assert len(ids)==len(set(ids))


def test_relation_is_specific_operation_not_a_fifth_element():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['sender'].update(name='Caller',position='内部服务');i['receiver']['position']='内部服务'
    i['operation']['sequence']=['验证调用身份','读取列表']
    rows=recognize(x,{'matches':[raw('service_relation.authentication','验证调用身份',target='operation',operation_index=0)]},inverse=True)
    m=rows['matches'][0]
    assert m['target']=='operation' and m['caller']=='Caller' and m['callee']=='Platform' and m['operation_index']==0
    assert len({e['element_id'] for e in index_elements(x) if e['target']=='operation'})==3
    s=scenario('auth');s.update(interaction_id='req',operation='验证调用身份',concern_key='service_relation.authentication',field=None,object='Platform')
    value=bind_scenarios({'scenarios':[s]},x,rows,gate=True)
    assert value['scenarios'][0]['element_anchors'][0]['operation_index']==0


def test_service_function_class_has_same_provider_anchor_from_field_or_operation():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    a=recognize(x,{'matches':[raw('service.query_retrieval.resource_existence','memoryInstanceID',data_location='path')]},inverse=True)
    b=recognize(x,{'matches':[raw('service.query_retrieval.resource_existence',i['operation']['name'],target='operation')]},inverse=True)
    assert a['matches'][0]['binding_id']==b['matches'][0]['binding_id']
    assert a['matches'][0]['target']=='receiver'
    assert a['matches'][0]['element_origin']['object']=='memoryInstanceID'


def test_classification_normalizes_from_own_evidence_or_stays_pending():
    x=memory_inputs();m=raw('api.data.range','memoryType');m['activation_evidence']=[{'kind':'data','constraint_kind':'enum','status':'explicit','value':['PROFILE','SEMANTIC'],'condition':'枚举','source_refs':R}]
    v=recognize(x,{'matches':[m]},inverse=True)
    assert v['matches'][0]['concern_key']=='api.data.legality'
    unknown=recognize(x,{'matches':[raw(field='unknownField')]},inverse=True)
    assert not unknown['matches'] and unknown['pending']


def test_inverse_evidence_must_overlap_exception_not_just_same_document():
    x=memory_inputs();source=R[0]['source_id'];line=R[0]['line_start']+100
    x['existing-documents']=[{'source_id':source,'lines':[{'number':line,'text':'本条已有异常'}]}]
    v=recognize(x,{'matches':[raw()]},inverse=True)
    assert not v['matches'] and '本条异常来源' in v['pending'][0]['reason']
    own=raw(source_refs=[{**R[0],'line_start':line,'line_end':line,'quote':'本条已有异常'}])
    assert recognize(x,{'matches':[own]},inverse=True)['matches']


def test_exact_concern_sets_deduplicate_and_preserve_missed_truth():
    x=memory_inputs();g=recognized(x,[raw(),raw()]);e={'matches':[]};gt=recognize(x,{'matches':[raw(),raw('api.data.type','page')]},inverse=True)
    v=compare(g,e,gt)
    assert len(v['G_c'])==1 and len(v['GT_c'])==2
    assert v['metrics']['missing_exception_miss_rate']['value']==50
    assert v['metrics']['generation_validity']['value']==100
    assert compare({'matches':[]},e,e)['metrics']['generation_validity']['status']=='不适用'


def test_broad_E_only_covers_its_recognized_request_fields():
    x=memory_inputs();g=recognized(x,[raw()]);e=recognize(x,{'matches':[raw(source_branch_ids=['b'],coverage_kind='input_parameters')]},inverse=True)
    s=scenario('broad');s.update(interaction_id='req',object='Platform',field=None,original_branch_id='b',coverage_kind='input_parameters')
    v=bind_scenarios({'scenarios':[s]},x,e,gate=True)
    assert v['scenarios'][0]['concern_binding_ids']==[g['matches'][0]['binding_id']]
    s['original_branch_id']='other';assert not bind_scenarios({'scenarios':[s]},x,e,gate=True)['scenarios']


def test_inverse_task_packets_reject_G_E_and_unrelated_truth():
    with pytest.raises(ValueError):packet('test-concerns',{'test-documents':[],'registry':registry(),'G':[]})
    with pytest.raises(ValueError):packet('existing-concerns',{'existing-documents':[],'GT':[]})


def test_tool_only_schema_changes_do_not_require_paid_recognition_again():
    from scene_completion.semantic_reuse import identity
    from scene_completion.contracts import schema
    x=memory_inputs();x.pop('enriched-interactions');old=schema('concern-match');new=deepcopy(old)
    new['properties']['matches']['items']['properties'].pop('element_origin')
    args=('concern-match',x,'same Skill')
    assert identity(*args,old,'model','endpoint',0)==identity(*args,new,'model','endpoint',0)
    changed=deepcopy(x);changed['api-parameters']['apis'][0]['parameters'][-1]['constraints'][-1]['value']=200
    assert identity(*args,old,'model','endpoint',0)!=identity('concern-match',changed,'same Skill',new,'model','endpoint',0)


def test_recognition_explanation_does_not_invalidate_scene_semantics_but_field_does():
    from scene_completion.semantic_reuse import identity
    from scene_completion.contracts import schema
    x=memory_inputs();x['identified-concerns']=recognized(x,[raw()]);y=deepcopy(x)
    y['identified-concerns']['matches'][0]['basis']='同一依据的另一种说法'
    args=('existing-extract','same Skill',schema('existing-extract'),'model','endpoint',0)
    key=lambda v:identity(args[0],v,*args[1:])
    assert key(x)==key(y)
    y['identified-concerns']['matches'][0]['object']='page'
    assert key(x)!=key(y)


def test_single_test_partition_does_not_receive_other_test_concern_answers():
    from scene_completion.task_partitions import split_task
    doc={'source_id':'s','name':'test.md','channel':'test','lines':[
        {'number':1,'text':'| TEST-UC-A01 | 范围错误 | 异常 | - | page<1 | UC | - | 拒绝 | spec |'},
        {'number':2,'text':'| TEST-UC-A02 | 类型错误 | 异常 | - | page非整数 | UC | - | 拒绝 | spec |'}]}
    m1={'source_unit_ids':['TEST-UC-A01'],'source_refs':[]};m2={'source_unit_ids':['TEST-UC-A02'],'source_refs':[]}
    excluded={'original_id':'TEST-UC-A01','source_refs':[],'scenario_type':'normal','reason':'正常重放'}
    parts=split_task('test-ground-truth',{'test-documents':[doc],'identified-concerns':{'matches':[m1,m2],'pending':[],'excluded':[excluded]}})
    assert len(parts)==2
    assert parts[0][1]['identified-concerns']['matches']==[m1]
    assert parts[1][1]['identified-concerns']['matches']==[m2]
    assert parts[0][1]['identified-concerns']['excluded']==[excluded]
    assert parts[1][1]['identified-concerns']['excluded']==[]


def test_normal_idempotent_retry_is_excluded_before_GT_concern_identification():
    from scene_completion.scenario_types import normal_replay_record
    doc={'source_id':'t','name':'test.md','channel':'test','lines':[{'number':1,'text':
        '| TEST-UC-O01 | 幂等重放 | 异常 | 相同幂等键已创建订单 | 使用相同 idempotencyKey 重试 | UC | 验证幂等 | 返回已有订单，不重复创建 | spec |'}]}
    found=normal_replay_record({'test-documents':[doc]})
    assert found and found['id']=='TEST-UC-O01'
    bad=deepcopy(doc);bad['lines'][0]['text']=bad['lines'][0]['text'].replace('使用相同 idempotencyKey 重试','使用相同 idempotencyKey 重试却重复创建订单')
    assert normal_replay_record({'test-documents':[bad]}) is None


def test_timeout_with_operation_verb_and_propagation_has_one_actual_failure_owner():
    from scene_completion.failure_units import normalize_bindings,normalize_inverse_units
    req=exchange();req['receiver']['name']='OrderService'
    ret=deepcopy(req);ret.update(id='ret',sequence=2,parent_id='req',direction='return');ret['sender'],ret['receiver']=ret['receiver'],ret['sender']
    inp={'fused-ssd':{'interactions':[req,ret]},'branches':{'branches':[{'id':'b','description':'OrderService查询超时，系统向用户返回HTTP 504'}]}}
    bound=normalize_bindings({'bindings':[{'branch_id':'b','interaction_id':'ret','status':'confirmed','basis':'传播返回','source_refs':R}]},inp)
    assert bound['bindings'][0]['interaction_id']=='req'
    inp['branches']['branches'][0].update(description='系统向用户返回HTTP 504',case_hint='OrderService查询超时',source_refs=[{**R[0],'quote':'OrderService查询超时，系统向用户返回HTTP 504'}])
    assert normalize_bindings({'bindings':[{'branch_id':'b','interaction_id':'ret','status':'confirmed','basis':'传播返回','source_refs':R}]},inp)['bindings'][0]['interaction_id']=='req'
    s=scenario('timeout');s.update(interaction_id='ret',cause='OrderService查询超时')
    assert normalize_inverse_units({'scenarios':[s]},inp)['scenarios'][0]['interaction_id']=='req'


def test_unresolved_scene_classification_is_pending_without_dropping_test_source():
    x=memory_inputs();g=recognized(x,[raw()]);x['concern-match']=g
    s=deepcopy(generated(applicability(x))['scenarios'][0]);s['concern_key']='api.data.type';s['concern_origins']=[]
    value=bind_scenarios({'scenarios':[s]},{**x,'identified-concerns':g},g,gate=True)
    assert not value['scenarios'] and value['pending']
    assert value['pending'][0]['source_refs']==s['source_refs']


def test_official_metrics_replace_only_current_units_keep_legacy():
    c={'metrics':{'generation_validity':{'value':80}}}
    v=attach_report({'metrics':{'generation_validity':{'value':10},'recommendation_adoption':{'value':50}}},c)
    assert v['metrics']['generation_validity']['value']==80
    assert v['metrics']['recommendation_adoption']['value']==50
    assert v['legacy_scenario_metrics']['generation_validity']['value']==10
    assert v['metric_units']['generation_validity']=='关注点绑定'
    assert v['metric_units']['recommendation_adoption']=='独立异常场景'


def test_pipeline_declares_independent_recognition_then_scene_dependencies(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,t)
    manifest=ex.finish();assert manifest['complete']
    graph=read_json(tmp_path/'run/workflow_graph.json');nodes={n['id']:n for n in graph['nodes']}
    assert 'UC-X:existing-concerns' in nodes and 'UC-X:test-concerns' in nodes
    assert 'UC-X:existing-concerns' in nodes['UC-X:existing-extract']['deps']
    assert any('UC-X:test-concerns' in n['deps'] for k,n in nodes.items() if k.startswith('UC-X:test-ground-truth'))
    assert not any('exception-generate' in d or 'existing-extract' in d for d in nodes['UC-X:concern-evaluation']['deps'])
    assert manifest['matching_version']==VERSION
