"""Behavioral acceptance for inherited concerns and evidence-gated generation."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from tests.test_workflow import memory_inputs,exchange,parameter,R,scenario,decision,fake_pipeline
from scene_completion.contracts import registry,packet
from scene_completion.concern_registry import inheritance_paths,validate_registry
from scene_completion.concern_hierarchy import resolve_matches,applicability,match_is_applicable
from scene_completion.exception_generation import data_exceptions,query_exceptions,service_exceptions,storage_exceptions,deduplicate
from scene_completion.validation import validate_result
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.storage import fingerprint,read_json
from scene_completion.interaction_enrichment import bind_resource_services
from scene_completion.exception_comparison import compare_report


def guard(kind,value=True,condition='明确的正常规则',unit=None,**extra):
    return {'kind':kind,'condition':condition,'value':value,'unit':unit,'status':'explicit','source_refs':R,**extra}


def match(key,*,target='receiver',name='Platform',rules=(),**extra):
    return {'interaction_id':'req','target':target,'object':name,'concern_key':key,
      'basis':'本次实际交互和正常规则','concrete_rule':None,'source_refs':R,'activation_evidence':list(rules),**extra}


def resolved(x,raw=()):
    result=resolve_matches(x,list(raw));x['concern-match']=result;return result['matches']


def find(rows,key,**attrs):
    return next(m for m in rows if m['concern_key']==key and all(m.get(k)==v for k,v in attrs.items()))


def test_registry_is_a_valid_DAG_and_all_57_old_items_have_audit_mapping():
    r=registry();assert len(r['definitions'])!=57 and len(r['legacy_mapping'])==57
    assert 'internal_database.availability' not in r['definitions']
    assert r['legacy_mapping']['internal_database.availability']['targets']==['service.base.availability']
    assert len(r['legacy_mapping']['service.resource_mutation.concurrency_idempotency']['targets'])==2
    assert inheritance_paths('api.data.type')==[['service.base.request_data','api.data.type'],['service.base.response_contract','api.data.type']]
    broken=deepcopy(r);broken['definitions']['service.base.request_data']['parents']=['api.data.type']
    broken['hash']=fingerprint({k:v for k,v in broken.items() if k!='hash'})
    with pytest.raises(ValueError,match='cycle'):validate_registry(broken)


@pytest.mark.parametrize('position',['内部服务','外部Actor（系统）','内部数据库','外部数据库','AI模型'])
def test_every_service_position_inherits_the_same_base(position):
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['receiver']['position']=position
    if position=='AI模型':i['receiver']['name']='LLMService'
    rows=resolved(x)
    base=set(registry()['profiles']['base'])
    assert base<={m['concern_key'] for m in rows}
    assert find(rows,'service.base.availability')['status']=='applicable'
    assert find(rows,'human.authentication')['status']=='pending'
    assert find(rows,'human.authentication')['object']=='开发者'
    assert find(rows,'human.authentication')['service']==i['receiver']['name']
    assert len(service_exceptions(x))==1
    assert len(data_exceptions(x))==8


def test_actual_operation_selects_function_and_not_all_supported_capabilities():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['receiver']['position']='内部服务'
    x['object-operations']={'objects':[{'name':'Platform','supported_operations':[{'name':'delete all','source_refs':R}]}]}
    rows=resolved(x)
    assert find(rows,'service.query_retrieval.resource_existence')['status']=='applicable'
    assert not any(m['concern_key'].startswith('service.resource_mutation.') for m in rows)
    i['operation']['kinds']=['update'];i['operation']['name']='修改记录';rows=resolved(x)
    assert any(m['concern_key'].startswith('service.resource_mutation.') for m in rows)
    assert not any(m['concern_key'].startswith('service.query_retrieval.') for m in rows)


def test_LLM_retrieval_and_generation_can_combine_five_function_classes():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    i['receiver'].update(name='LLMService',position='外部Actor（系统）');i['operation']['kinds']=['read','process','external_call']
    rows=resolved(x)
    assert find(rows,'llm.grounding')['functional_types']==['query_retrieval','analysis_generation']
    assert find(rows,'llm.grounding')['technologies']==['llm']
    assert find(rows,'llm.grounding')['status']=='pending'
    assert 'llm.prompt_security' in {m['concern_key'] for m in rows}
    assert not any(m['concern_key'].startswith('service.resource_mutation.') for m in rows)


def test_explicit_technology_evidence_can_identify_a_non_LLM_named_provider():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['receiver'].update(name='InferenceEndpoint',position='内部服务')
    raw=match('llm.grounding',name='InferenceEndpoint',rules=[guard('technology','llm','该端点为大语言模型服务')])
    rows=resolved(x,[raw]);assert find(rows,'llm.output_stability')['technologies']==['llm']
    assert find(rows,'llm.output_stability')['status']=='pending'


def test_security_is_conditional_not_an_automatic_login_requirement():
    x=memory_inputs();rows=resolved(x)
    auth=find(rows,'human.authentication')
    assert auth['status']=='pending' and auth['concrete_rule'] is None
    rows=resolved(x,[match('human.authentication',rules=[guard('authentication',False,'该接口允许匿名调用')])])
    auth=find(rows,'human.authentication');assert auth['status']=='not_applicable'
    rows=resolved(x,[match('human.authentication',rules=[guard('authentication',True,'该接口需要认证')])])
    auth=find(rows,'human.authentication');assert auth['status']=='applicable' and auth['target']=='sender'
    assert len([m for m in rows if m['concern_key']=='human.authentication'])==1
    rows=resolved(x,[match('human.authentication',rules=[guard('authentication',True),guard('authentication',False)])])
    assert find(rows,'human.authentication')['status']=='pending'


def test_authentication_failure_cannot_be_generated_as_unavailability():
    x=memory_inputs();rows=resolved(x);s=service_exceptions(x)[0];s['cause']='authentication_failed'
    with pytest.raises(ValueError,match='not service availability'):
        validate_result('exception-generate',{'scenarios':[s],'pending':[]},x)


def test_unknown_deadline_is_pending_no_synthetic_five_seconds():
    x=memory_inputs();x['sr-ssd']['interactions'][0]['operation']['kinds']=['process'];rows=resolved(x)
    assert find(rows,'service.analysis_generation.execution_deadline')['status']=='not_applicable'
    raw=match('service.analysis_generation.execution_deadline',rules=[guard('timing',None,'要求实时响应但没有给定时限')])
    rows=resolved(x,[raw]);timing=find(rows,'service.analysis_generation.execution_deadline')
    assert timing['status']=='pending' and timing['concrete_rule'] is None
    bad=deepcopy(timing);bad.update(status='applicable',concrete_rule='必须5秒内完成')
    with pytest.raises(ValueError,match='lacks evidence'):
        validate_result('concern-match',{'matches':[bad],'pending':[]},x)
    rows=resolved(x,[match('service.analysis_generation.execution_deadline',rules=[guard('timing',500,'必须500毫秒内响应','ms')])])
    assert find(rows,'service.analysis_generation.execution_deadline')['status']=='applicable'
    rows=resolved(x,[match('service.analysis_generation.execution_deadline',rules=[guard('timing','必须在提交下一步前返回','必须在提交下一步前返回')])])
    assert find(rows,'service.analysis_generation.execution_deadline')['status']=='applicable'


def test_output_stability_needs_a_declared_allowed_variation_not_identical_text_by_default():
    x=memory_inputs();x['sr-ssd']['interactions'][0]['receiver'].update(name='LLMService',position='AI模型')
    rows=resolved(x,[match('llm.output_stability',name='LLMService',rules=[guard('stability',True)])])
    assert find(rows,'llm.output_stability')['status']=='pending'
    rows=resolved(x,[match('llm.output_stability',name='LLMService',rules=[guard('stability','关键判断必须一致','相同输入和配置下关键判断必须一致')])])
    assert find(rows,'llm.output_stability')['status']=='applicable'


@pytest.mark.parametrize('physical',['内部数据库','外部数据库'])
def test_database_uses_shared_query_base_and_only_relevant_extensions(physical):
    x=memory_inputs();x['components']['components']=[{'id':'db','name':'Database','composition_type':physical,'source_refs':R}]
    x['sr-ssd']['interactions'][0]['receiver'].update(name='Database',position=physical)
    x=bind_resource_services(x);rows=resolved(x)
    assert find(rows,'service.base.availability')['status']=='applicable'
    assert find(rows,'database.uniqueness')['status']=='not_applicable'
    assert find(rows,'database.query_performance')['status']=='not_applicable'
    assert 'database.transaction_atomicity' not in registry()['definitions']
    assert {s['concern_key'] for s in query_exceptions(x)}=={'service.query_retrieval.resource_existence'}
    x['sr-ssd']['interactions'][0]['operation'].update(name='创建记录',kinds=['create'])
    raw=match('database.uniqueness',name='Database资源服务',rules=[guard('unique',True,'名称必须唯一')])
    rows=resolved(x,[raw]);assert find(rows,'database.uniqueness')['status']=='applicable'
    assert find(rows,'database.referential_integrity')['status']=='pending'


def test_storage_schema_data_rules_reuse_seven_families_without_interface_collision():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['receiver']['position']='内部数据库';i['operation'].update(name='写入记录',kinds=['create'])
    raw=match('api.data.completeness',target='data',name='record.name',scope='storage',data_location='storage',
      rules=[guard('storage_field',True,'存储Schema中的name必填',field='record.name',constraint_kind='required')])
    rows=resolved(x,[raw]);m=find(rows,'api.data.completeness',object='record.name')
    assert m['status']=='applicable' and m['inheritance_paths']==[['service.base.request_data','api.data.completeness']]
    failures=storage_exceptions(x);assert len(failures)==1 and failures[0]['scope']=='storage'
    validate_result('exception-generate',{'scenarios':failures,'pending':[]},x)
    i['operation']['kinds']=['read'];rows=resolved(x,[raw])
    assert find(rows,'api.data.completeness',object='record.name')['status']=='not_applicable'
    assert not storage_exceptions(x)


def test_request_and_response_use_shared_definitions_but_separate_inheritance_and_units():
    x=memory_inputs();request=x['sr-ssd']['interactions'][0]
    returned=deepcopy(request);returned.update(id='returned',sequence=2,parent_id='req',direction='return');returned['sender'],returned['receiver']=returned['receiver'],returned['sender']
    x['sr-ssd']['interactions'].append(returned)
    x['api-parameters']['apis'][0]['parameters'].append(parameter('page','response',True,'integer'))
    rows=resolved(x)
    req=find(rows,'api.data.type',interaction_id='req',object='page')
    ret=find(rows,'api.data.type',interaction_id='returned',object='page')
    assert req['inheritance_paths']==[['service.base.request_data','api.data.type']]
    assert ret['inheritance_paths']==[['service.base.response_contract','api.data.type']]
    scenarios=data_exceptions(x)
    assert {'req','returned'}=={s['interaction_id'] for s in scenarios if s['field']=='page'}
    assert len([k for k in registry()['definitions'] if k.startswith('api.data.')])==7


def test_same_failure_does_not_duplicate_a_failure_or_its_score():
    first=scenario('root',cause='incorrect_result');first.update(object='LLMService',operation='生成摘要',concern_key='llm.grounding',conditions=['生成摘要与给定证据矛盾'])
    child=deepcopy(first);child['id']='leaf'
    merged=deduplicate([first,child]);assert len(merged)==1
    truth=deepcopy(child);truth.update(id='truth',source_status='explicit')
    report=compare_report([first,child],[],[truth],[],[decision('truth','root')],[])
    assert report['metrics']['generation_validity']['denominator']==1
    assert report['metrics']['generation_validity']['value']==100
    different=deepcopy(child);different.update(id='different',conditions=['生成摘要遗漏必须列出的结论'])
    assert len(deduplicate([first,different]))==2


def test_same_name_at_different_field_locations_never_collapses():
    x=memory_inputs();x['api-parameters']['apis'][0]['parameters']=[parameter('id','header',True),parameter('id','query',True)]
    resolved(x);scenarios=data_exceptions(x)
    assert len(scenarios)==2 and {s['data_location'] for s in scenarios}=={'header','query'}


def test_old_registry_or_existing_documents_cannot_be_supplied_as_positive_rules():
    x=memory_inputs();new=registry();old=deepcopy(new);old['version']='scene-workflow-v1'
    inputs={'components':x['components'],'rr-ssd':x['rr-ssd'],'sr-ssd':x['sr-ssd'],'api-map':x['api-map'],'api-parameters':x['api-parameters'],
      'object-operations':{'objects':[]},'enriched-interactions':{'interactions':[],'rr_sr_links':[],'pending':[],'resource_mappings':[]},'registry':old}
    with pytest.raises(ValueError,match='registry differs'):packet('concern-match',inputs)
    inputs['registry']=new;inputs['normal-documents']=[{'source_id':'bad','name':'rr.md','channel':'existing','lines':[]}]
    with pytest.raises(ValueError,match='positive documents'):packet('concern-match',inputs)


def test_pipeline_exports_applicability_and_passes_only_positive_rule_documents(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);seen=[]
    def collect(p):seen.append(p);return {'matches':[],'pending':[]}
    m['concern-match']=collect
    ex=Execution(tmp_path/'run',mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert seen and all(d['channel']=='normal' for d in seen[0]['input']['normal-documents'])
    assert 'existing empty result' not in json.dumps(seen[0])
    manifest=read_json(ex.root/'run_manifest.json');assert manifest['registry_version']=='interaction-concerns-v3'
    report=read_json(ex.root/'missing_report.json')['cases']['UC-X']
    assert {'applicable','pending','not_applicable'}<={m['status'] for m in report['concerns']}
    assert all(m['inheritance_paths'] for m in report['concerns'])


def test_numerical_and_qualitative_timing_rules_cannot_be_invented():
    x=memory_inputs();x['sr-ssd']['interactions'][0]['operation']['kinds']=['process'];bad=match('service.analysis_generation.execution_deadline',rules=[guard('timing',500,'响应要快','ms')],status='applicable')
    with pytest.raises(ValueError,match='numeric rule value|value/unit'):
        validate_result('concern-match',{'matches':[bad],'pending':[]},x)
    normal={'source_id':'timing-doc','name':'sr.md','channel':'normal','lines':[{'number':1,'text':'该服务必须在0.5秒内响应。'}]}
    x['normal-documents']=[normal]
    bad['activation_evidence'][0]['source_refs']=[{'source_id':'timing-doc','line_start':1,'line_end':1,'quote':normal['lines'][0]['text']}]
    validate_result('concern-match',{'matches':[bad],'pending':[]},x)
    bad['activation_evidence'][0]['unit']='seconds'
    with pytest.raises(ValueError,match='value/unit'):
        validate_result('concern-match',{'matches':[bad],'pending':[]},x)
    bad['activation_evidence'][0]['unit']='ms'
    bad['activation_evidence'][0]['value']='必须在提交下一步前返回'
    with pytest.raises(ValueError,match='exact normal wording'):
        validate_result('concern-match',{'matches':[bad],'pending':[]},x)


def test_interface_and_storage_scopes_cannot_cover_each_other():
    a=scenario('a');a.update(field='name',scope='storage',data_location='storage')
    b=deepcopy(a);b.update(id='b',scope='interface',data_location='body')
    with pytest.raises(ValueError,match='constraint scope'):
        validate_result('semantic-compare',{'decisions':[decision('a','b')]},{'left':[a],'right':[b],'purpose':'GT_G'})


def test_cancel_and_old_generic_timeout_are_not_registered_in_new_taxonomy():
    assert not {'service.workflow.interruption','common.timeout','service.base.result_correctness','service.contract.compatibility'}&set(registry()['definitions'])
    with pytest.raises(ValueError,match='unregistered concern'):
        validate_result('existing-extract',{'scenarios':[{**scenario('cancel',status='explicit'),'concern_key':'service.workflow.interruption'}]},{'evidence':R})


def test_report_distinguishes_applicable_pending_and_inapplicable(tmp_path):
    from scene_completion.artifact_exports import export_task
    x=memory_inputs();rows=resolved(x)
    export_task(tmp_path,'concern-match',{'matches':rows,'pending':x['concern-match']['pending']})
    text=(tmp_path/'concern-match.md').read_text()
    assert '适用' in text and '待确认' in text and '不适用' in text and '继承路径' in text
    assert '调用方身份认证' in text


@pytest.mark.parametrize('position',['内部服务','外部Actor（系统）','内部数据库','AI模型'])
@pytest.mark.parametrize('kinds,function',[(['display'],'display_interaction'),(['read'],'query_retrieval'),(['update'],'resource_mutation'),(['process'],'analysis_generation'),(['publish'],'release_activation')])
def test_all_five_functions_are_open_to_internal_external_and_technical_services(position,kinds,function):
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['receiver']['position']=position;i['operation']['kinds']=kinds
    if position=='AI模型':i['receiver']['name']='LLMService'
    rows=resolved(x)
    expected=set(registry()['profiles']['functional'][function])
    assert expected<={m['concern_key'] for m in rows}
    assert all(m['functional_types']==[function] for m in rows)


def test_callback_authentication_belongs_to_the_actual_caller_of_the_local_service():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    i['sender'].update(name='ExternalLLM',position='外部Actor（系统）')
    i['receiver'].update(name='LocalService',position='内部服务')
    rows=resolved(x,[match('service_relation.authentication',name='LocalService',rules=[guard('authentication',True,'该回调接口必须认证')])])
    auth=find(rows,'service_relation.authentication')
    assert auth['object']=='ExternalLLM' and auth['service']=='LocalService' and auth['status']=='applicable'
    assert not any(m['concern_key'].startswith('llm.') for m in rows)


def test_registry_rule_changes_invalidate_concern_analysis_without_reextracting_graphs(tmp_path,monkeypatch):
    import scene_completion.concern_registry as registry_module
    full=registry();file=tmp_path/'concern_registry.json';file.write_text(json.dumps(full,ensure_ascii=False))
    monkeypatch.setattr(registry_module,'Path',lambda _:tmp_path/'registry-module.py')
    rr,sr,t,m=fake_pipeline(tmp_path);calls=[]
    def capture(task,value):
        def invoke(packet):calls.append(task);return value(packet) if callable(value) else deepcopy(value)
        return invoke
    mocks={k:capture(k,v) for k,v in m.items()};root=tmp_path/'run'
    ex=Execution(root,mocks=mocks);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    calls.clear();full['definitions']['human.authentication']['description']='明确根据当前调用方和接口要求检查认证'
    full['hash']=fingerprint({k:v for k,v in full.items() if k!='hash'});file.write_text(json.dumps(full,ensure_ascii=False))
    ex=Execution(root,mocks=mocks);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert {'concern-match','exception-generate'}<=set(calls)
    assert not set(calls)&{'components','rr-ssd','sr-ssd','api-map','api-parameters','test-operation-project','interaction-align'}


def test_technical_refinement_paths_only_use_the_actual_function_not_dormant_classes():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    i['receiver'].update(name='LLMService',position='AI模型');i['operation']['kinds']=['process']
    rows=resolved(x)
    paths=find(rows,'llm.grounding')['inheritance_paths']
    assert paths==[['llm.grounding']]
    assert not any('service.query_retrieval.result_correctness' in path for path in paths)


def test_a_pending_same_name_field_does_not_borrow_another_locations_applicability():
    x=memory_inputs();x['api-parameters']['apis'][0]['parameters']=[parameter('id','header',True),parameter('id','query',True)]
    rows=resolved(x)
    for m in rows:
        if m['concern_key']=='api.data.completeness' and m['data_location']=='header':m['status']='pending';m['concrete_rule']=None
    out=data_exceptions(x)
    assert len(out)==1 and out[0]['data_location']=='query'


def test_RR_return_business_data_is_preserved_without_importing_request_fields():
    from scene_completion.interaction_enrichment import parameters_for
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i.update(id='business-return',direction='return',api_id=None)
    i['data']['sequence']=[parameter('分页结果','business',True,'object')]
    fields=parameters_for(i,x)
    assert [p['name'] for p in fields]==['分页结果']
    rows=resolved(x);out=data_exceptions(x)
    assert len(out)==2 and {s['field'] for s in out}=={'分页结果'}
