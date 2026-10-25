from copy import deepcopy
import json
import pytest
from scene_completion.indexed_context import EvidenceContext,markdown_index,select_indexed_sections,task_document_view
from scene_completion.source_documents import current_projection,case_projection
from scene_completion.contracts import packet
from tests.test_workflow import exchange,R


def fused_fixture():
    doc={'source_id':'positive','channel':'normal','name':'rr.md','lines':[{'number':1,'text':R[0]['quote']}]}
    comps={'components':[{'id':'human','name':'开发者','composition_type':'外部Actor（人类）','parent_id':None,'source_status':'explicit','source_refs':R},{'id':'svc','name':'Platform','composition_type':'系统边界','parent_id':None,'source_status':'explicit','source_refs':R}], 'relations':[]}
    inp={'RR':[doc],'SR':[doc],'components':comps,'case-group':{'id':'CASE-A','rr_ids':['RR1'],'sr_ids':['SR1'],'status':'confirmed','reason':'same','source_refs':R}}
    p=packet('fused-ssd',inp);p['skill_text']='test';return p


def test_indexed_ssd_round_trip_fills_only_trusted_identity_and_omitted_unknowns():
    p=fused_fixture();ctx=EvidenceContext(p)
    v={'interactions':[exchange(sid='rr',layer='RR'),exchange(sid='sr')],'rr_sr_links':[],'pending':[]}
    v['interactions'][0]['data']['sequence']=[{'name':'filter','location':'query','source_refs':R}]
    q=ctx.encode_output(v)
    assert q['interactions'][0]['sender']=={'component_id':'human'} and 'case_id' not in q['interactions'][0]
    assert isinstance(q['interactions'][0]['source_refs'][0],str)
    r=ctx.expand(q)
    assert r['interactions'][0]['sender']['name']=='开发者' and r['interactions'][0]['case_id']=='CASE-A'
    param=r['interactions'][0]['data']['sequence'][0];assert param['required'] is None and param['constraints']==[]
    assert r['interactions'][0]['source_refs']==R
    q['interactions'][0]['source_refs']=['e000000000000']
    with pytest.raises(ValueError,match='unknown evidence_id'):ctx.expand(q)


def test_index_keeps_excluded_sections_but_default_projection_omits_them():
    lines=['# Current','real','## V5 历史映射，非抽取权威章节','old','## 关联实现接口OpenAPI文件','AR','## Current again','new']
    d={'source_id':'s','channel':'existing','name':'sr.md','lines':[{'number':n,'text':s} for n,s in enumerate(lines,1)]}
    idx=markdown_index([d]);sections=idx['documents'][0]['sections']
    assert not sections[1]['default_input'] and not sections[2]['default_input']
    text=str(current_projection([d]));assert 'old' not in text and "'AR'" not in text and 'new' in text
    assert select_indexed_sections([d],idx,[sections[1]['id']])[0]['lines'][1]['text']=='old'
    with pytest.raises(ValueError):select_indexed_sections([d],idx,['missing'])


def test_test_table_selects_only_explicit_case_rows_without_prefix_collisions():
    rows=['# Tests','| 编号 | 关联需求 | 异常 |','|---|---|---|','| T1 | UC-1 | one |','| T2 | UC-10 | other |']
    d={'source_id':'test','name':'test.md','channel':'test','lines':[{'number':n,'text':t} for n,t in enumerate(rows,1)]}
    result=case_projection([d],'UC-1',['UC-1','UC-10'])
    assert [r['number'] for r in result[0]['lines']]==[1,2,3,4]
    assert case_projection([d],'UC-2',['UC-1','UC-2','UC-10'])==[]


def test_mapping_context_does_not_carry_parameter_bodies_and_catalog_keeps_metadata():
    rows=['# API list','## API-1','- API编号：A1','- 所属服务：ExampleService','- 方法：GET','- 资源路径：/items','- query:','  foo: very long type body'+'x'*5000,'## 用例详情','### UC-X','| 用例编号 | UC-X |','| 用例名称 | Query |','1. Actor：人类','5. 主成功路径：','a body that is not catalog metadata']
    d={'source_id':'s','name':'s.md','channel':'normal','lines':[{'number':n,'text':v} for n,v in enumerate(rows,1)]}
    api=str(task_document_view([d],'api-map'));cat=str(task_document_view([d],'catalogue'))
    assert 'ExampleService' in api and 'very long type body' not in api
    assert '用例编号' in cat and 'not catalog metadata' not in cat


def test_agent_decodes_compact_model_result_before_public_contract_validation(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    p=fused_fixture();ctx=EvidenceContext(p)
    full={'interactions':[exchange(sid='rr',layer='RR'),exchange(sid='sr')],'rr_sr_links':[],'pending':[]}
    compact=ctx.encode_output(full);sent=[]
    def transport(url,key,body,*args):
        sent.append(body)
        assert 'evidence_id' in body['messages'][0]['content']
        return {'model':'offline','usage':{'total_tokens':17},'choices':[{'message':{'content':json.dumps(compact)},'finish_reason':'stop'}]}
    client=DeepAgentsClient({'api_key':'test','base_url':'http://offline/v1','agent_model':'offline','run_root':str(tmp_path),'indexed_context':True,'submission_mode':'json_text'},transport=transport)
    result=client.agent(p)
    assert len(sent)==1 and result['interactions'][0]['sender']['source_refs']==R
    assert result['interactions'][0]['case_id']=='CASE-A'


def test_structure_tool_expands_only_existing_nested_messages_and_preserves_return_owner():
    from scene_completion.ssd_tools import complete_structure
    from tests.test_workflow import exchange
    rr=exchange(sid='rr',layer='RR');root=exchange(sid='root')
    down=deepcopy(root);down.update(id='down',sequence=2);down['sender']=deepcopy(root['receiver']);down['receiver']['name']='Database'
    back=deepcopy(down);back.update(id='back',sequence=3,direction='return',parent_id='down');back['sender'],back['receiver']=deepcopy(down['receiver']),deepcopy(down['sender'])
    ret=deepcopy(root);ret.update(id='ret',sequence=4,direction='return',parent_id='root');ret['sender'],ret['receiver']=deepcopy(root['receiver']),deepcopy(root['sender'])
    rrret=deepcopy(rr);rrret.update(id='rrret',sequence=2,direction='return',parent_id='rr');rrret['sender'],rrret['receiver']=deepcopy(rr['receiver']),deepcopy(rr['sender'])
    value={'interactions':[rr,root,down,back,ret,rrret],'rr_sr_links':[{'rr_id':'rr','sr_ids':['root'],'status':'confirmed'},{'rr_id':'rrret','sr_ids':['ret'],'status':'confirmed'}],'pending':[]}
    result=complete_structure(value)
    assert result['interactions'][2]['parent_id']=='root'
    assert result['rr_sr_links'][0]['sr_ids']==['root','down','back']
    assert result['rr_sr_links'][1]['sr_ids']==['ret']
    assert len(result['interactions'])==len(value['interactions']) and value['interactions'][2]['parent_id'] is None


def test_test_operation_reference_cannot_leak_the_rest_of_a_table_row():
    from scene_completion.validation import validate_result
    row='| Case | listJobs | 异常 | HTTP 503 missing service |'
    doc={'source_id':'test','channel':'test','name':'tests.md','lines':[{'number':9,'text':row}]}
    p=packet('test-operation-project',{'test-operation-source':[doc]});ctx=EvidenceContext(p)
    rid=next(iter(ctx.pool))
    result=ctx.expand({'objects':[{'name':'JobService','supported_operations':[{'name':'listJobs','source_refs':[rid]}]}]})
    assert result['objects'][0]['supported_operations'][0]['source_refs'][0]['quote']=='listJobs'
    validate_result('test-operation-project',result,p['input'])
    assert '503' not in json.dumps(result)


def test_repair_cannot_turn_foreign_channel_quotes_into_trusted_evidence_ids():
    p=fused_fixture();p['repair']={'candidate':{'interactions':[],'rr_sr_links':[],'pending':[{'interaction_id':'x','reason':'fix','source_refs':[{'source_id':'foreign-test','line_start':1,'line_end':1,'quote':'secret GT'}]}]}}
    ctx=EvidenceContext(p)
    assert ctx.packet['repair']['candidate']['pending'][0]['source_refs']==[]
    assert 'secret GT' not in json.dumps(ctx.input,ensure_ascii=False)


def test_ssd_identity_context_excludes_unrelated_services_but_retains_parent():
    from scene_completion.task_context import ssd_context
    p=fused_fixture()['input'];p['components']['components'][1]['parent_id']='boundary'
    p['components']['components'] += [
      {'id':'boundary','name':'整体系统','composition_type':'系统边界','parent_id':None,'source_refs':[]},
      {'id':'unused','name':'UnrelatedService','composition_type':'内部服务','parent_id':'boundary','source_refs':[]}]
    result=ssd_context(p)
    assert {c['id'] for c in result['components']['components']}=={'human','svc','boundary'}
    assert len(p['components']['components'])==4


def test_fused_evidence_ids_expose_layer_and_reject_foreign_layer():
    p=fused_fixture();p['input']['SR']=deepcopy(p['input']['SR']);p['input']['SR'][0]['source_id']='SR-source'
    ctx=EvidenceContext(p)
    assert any(k.startswith('RR-e') for k in ctx.pool) and any(k.startswith('SR-e') for k in ctx.pool)
    assert ctx.packet['output_schema']['properties']['interactions']['items']['properties']['source_refs']['items']['pattern'].startswith('^')


def test_concern_model_does_not_author_applicability_or_receive_duplicate_views():
    from scene_completion.contracts import registry
    from scene_completion.concern_hierarchy import resolve_matches
    from scene_completion.interaction_enrichment import enrich
    from tests.test_workflow import memory_inputs
    # Empty semantic extras remain valid: inheritance is owned by the tool.
    inp=memory_inputs();inp.pop('concern-match');inp['components']=fused_fixture()['input']['components'];inp['object-operations']={'objects':[]};inp['enriched-interactions']={'interactions':[],'rr_sr_links':[],'pending':[],'resource_mappings':[]}
    ctx=EvidenceContext(packet('concern-match',inp))
    props=ctx.packet['output_schema']['properties']['matches']['items']['properties']
    assert 'status' not in props and 'functional_types' not in props
    result=ctx.expand({'matches':[],'pending':[]})
    assert any(m['concern_key']=='service.base.availability' and m['status']=='applicable' for m in result['matches'])


def test_case_index_prefers_formal_details_over_duplicate_brief_summary():
    from scene_completion.indexed_context import catalogue_context
    from scene_completion.use_cases import validate_catalogue,select_documents
    rows=['# Design','## 设计用例','### UC-A Summary','API: /items','## 设计用例详情','### UC-A Query','#### 基本信息','| 用例编号 | UC-A |','| 用例名称 | Query |','#### 参与者','Developer, QueryService','#### 基本流程','查询列表并逐层返回','#### 备选流程','无结果','### UC-B other']
    d={'source_id':'s','name':'sr.md','channel':'normal','lines':[{'number':n,'text':t} for n,t in enumerate(rows,1)]}
    # Make it larger than small-document fallback so metadata view is exercised.
    d['lines'][3]['text']+='x'*5000
    v=catalogue_context([d]);sections=v['source-index']['documents'][0]['sections']
    assert len(sections)==1 and sections[0]['line_start']==6 and sections[0]['line_end']==15
    assert all(r['number']>=6 for r in v['documents'][0]['lines'])
    case={'id':'UC-A','layer':'SR','source_ranges':[{'source_id':'s','start':3,'end':4}]}
    with pytest.raises(ValueError,match='detailed section'):validate_catalogue('use-case-extract',{'cases':[case]},{**v,'layer':'SR'})
    case['source_ranges']=[{'source_id':'s','start':6,'end':15}]
    validate_catalogue('use-case-extract',{'cases':[case]},{**v,'layer':'SR'})
    assert '查询列表并逐层返回' in str(select_documents([d],[case]))


def test_chinese_alternative_flow_never_enters_positive_ssd_or_G():
    from scene_completion.source_documents import normal_projection
    rows=['# UC-A','## 基本流程','返回列表','## 备选流程','1.a 参数非法：返回400','1.b 无匹配：空列表','## UC-B','正常调用']
    d={'source_id':'s','name':'sr.md','channel':'existing','lines':[{'number':n,'text':t} for n,t in enumerate(rows,1)]}
    result=normal_projection([d])
    assert [r['number'] for r in result[0]['lines']]==[1,2,3,7,8]
    assert len(d['lines'])==8


def test_model_schema_disallows_response_fields_in_request_before_submission():
    from jsonschema import Draft202012Validator
    p=fused_fixture();ctx=EvidenceContext(p)
    i=exchange();i['data']['sequence']=[{'name':'resultColumn','location':'response','source_refs':R}]
    q=ctx.encode_output({'interactions':[i],'rr_sr_links':[],'pending':[]})
    errors=list(Draft202012Validator(ctx.packet['output_schema']).iter_errors(q))
    assert any('location' in list(e.path) for e in errors)
    q['interactions'][0]['data']['sequence'][0]['location']='query'
    assert not list(Draft202012Validator(ctx.packet['output_schema']).iter_errors(q))


def test_model_format_rejection_retains_targeted_repair_candidate(tmp_path):
    from scene_completion.deepagents_client import DeepAgentsClient
    from scene_completion.scheduler import TaskRejected
    p=fused_fixture();ctx=EvidenceContext(p)
    bad=ctx.encode_output({'interactions':[exchange(sid='rr',layer='RR'),exchange(sid='sr')],'rr_sr_links':[],'pending':[]})
    bad['interactions'][0]['sender']['component_id']='unknown-identity'
    def transport(*args):return {'model':'offline','choices':[{'message':{'content':json.dumps(bad)},'finish_reason':'stop'}]}
    client=DeepAgentsClient({'api_key':'test','base_url':'http://offline','agent_model':'test','run_root':str(tmp_path),'indexed_context':True,'submission_mode':'json_text'},transport=transport)
    with pytest.raises(TaskRejected) as caught:client.agent(p)
    saved=json.loads((tmp_path/caught.value.details['rejected_output']).read_text())
    assert saved['candidate_format']=='model' and saved['payload']==bad
    p['repair']={k:saved[k] for k in ('payload','candidate_format')};p['repair']['candidate']=p['repair'].pop('payload')
    repaired=EvidenceContext(p).packet['repair']['candidate']
    assert repaired['interactions'][0]['sender']['component_id']=='unknown-identity'
    assert repaired['interactions'][1]['sender']['component_id']=='human'


def test_generation_context_excludes_review_matrix_and_computed_inheritance():
    from scene_completion.task_context import semantic_view
    from tests.test_workflow import memory_inputs
    from scene_completion.concern_hierarchy import resolve_matches
    x=memory_inputs();x['concern-match']=resolve_matches(x,x['concern-match']['matches'])
    # A semantic business rule survives; a pending/inapplicable one does not.
    extra={'interaction_id':'req','target':'sender','object':'开发者','concern_key':'human.authentication','basis':'explicit','concrete_rule':'must own resource','status':'applicable','source_refs':R,'inheritance_paths':[['extra']],'activation_evidence':[{'kind':'authentication','value':'login required','condition':'authenticated caller required','unit':None,'status':'explicit','source_refs':R}]}
    x['concern-match']['matches'] += [extra,{**extra,'status':'pending','concrete_rule':None}]
    view=semantic_view('exception-generate',x)
    assert view['concern-match']['matches']==[{k:v for k,v in extra.items() if k not in {'status','inheritance_paths'}}]
    # Audit artifact remains intact; only the model view is projected.
    assert len(x['concern-match']['matches'])>len(view['concern-match']['matches'])
    x['enriched-interactions']={'interactions':[],'rr_sr_links':[],'pending':[],'resource_mappings':[]}
    ctx=EvidenceContext(packet('exception-generate',x))
    assert 'concern_paths' not in ctx.packet['output_schema']['properties']['scenarios']['items']['properties']


def test_generated_source_and_coverage_are_fixed_without_relabeling_original_branches():
    from jsonschema import Draft202012Validator
    from tests.test_workflow import memory_inputs,scenario
    x=memory_inputs();i=x['sr-ssd']['interactions'][0]
    x['enriched-interactions']={'interactions':[],'rr_sr_links':[],'pending':[],'resource_mappings':[]}
    x['concern-match']['matches']=[{'interaction_id':i['id'],'target':'sender','object':i['sender']['name'],
      'concern_key':'human.authentication','basis':'credential must be valid','concrete_rule':'credential must be valid',
      'source_refs':R,'activation_evidence':[{'kind':'authentication','condition':'credential must be valid','value':True,'unit':None,'status':'explicit','source_refs':R}]}]
    ctx=EvidenceContext(packet('exception-generate',x));s=scenario(status='explicit')
    s.update(object=i['sender']['name'],concern_key='human.authentication',derivation='Negation of the explicitly required valid credential',original_branch_id='wrong',coverage_kind='input_parameters')
    compact=ctx.encode_output({'scenarios':[s],'pending':[]})
    for k in ('source_status','original_branch_id','coverage_kind'):assert k not in compact['scenarios'][0]
    Draft202012Validator(ctx.packet['output_schema']).validate(compact)
    restored=ctx.expand(compact)['scenarios'][0]
    assert (restored['source_status'],restored['original_branch_id'],restored['coverage_kind'])==('framework_inferred',None,'exact')
    annotated=deepcopy(compact);annotated['scenarios'][0]['field']='Authorization'
    assert ctx.expand(annotated)['scenarios'][0]['field'] is None
    assert ctx.normalizations[-1]['original_value']=='Authorization'
    annotated['scenarios'][0].update(concern_key='database.referential_integrity',scope='storage',field='merchant_id')
    assert ctx.expand(annotated)['scenarios'][0]['field'] is None
    annotated['scenarios'][0]['concern_key']='api.data.legality'
    assert ctx.expand(annotated)['scenarios'][0]['field']=='merchant_id'
    compact['scenarios'][0]['derivation']=''
    assert list(Draft202012Validator(ctx.packet['output_schema']).iter_errors(compact))
    # Original E retains its own explicit/inferred status and broad coverage.
    existing=deepcopy(ctx.original);existing['task']='existing-extract'
    inverse=EvidenceContext(existing);row=inverse.expand(inverse.encode_output({'scenarios':[s],'pending':[]}))['scenarios'][0]
    assert row['source_status']=='explicit' and row['original_branch_id']=='wrong' and row['coverage_kind']=='input_parameters'


def test_deterministic_generation_does_not_call_model_for_matrix_only_rules(tmp_path):
    from scene_completion.workflow import Execution
    from scene_completion.concern_hierarchy import resolve_matches
    from tests.test_workflow import memory_inputs
    from scene_completion.storage import read_json
    x=memory_inputs();x['concern-match']=resolve_matches(x,x['concern-match']['matches'])
    x['enriched-interactions']={'interactions':[],'rr_sr_links':[],'pending':[],'resource_mappings':[]}
    class Client:
        config={}
        def model(self,kind):return 'offline'
        def agent(self,p):raise AssertionError('Mechanical rules must not trigger a model call')
    ex=Execution(tmp_path,mode='external',client=Client());ex.add('G','exception-generate',static=x)
    result=ex.finish();assert result['complete']
    output=read_json(tmp_path/ex.scheduler.state['tasks']['G']['output_file'])
    assert len([s for s in output['payload']['scenarios'] if s['field']])==8
    assert output['metadata']['execution']['provider']=='deterministic_rule_coverage'


def test_request_parent_transport_hint_does_not_define_business_relation():
    p=fused_fixture();ctx=EvidenceContext(p)
    v=ctx.encode_output({'interactions':[exchange(sid='rr',layer='RR'),exchange(sid='sr')],'rr_sr_links':[],'pending':[]})
    v['interactions'][1]['reply_to']='rr'
    result=ctx.expand(v)
    assert result['interactions'][1]['parent_id'] is None
    assert ctx.normalizations[0]['message_id']=='sr'
    assert result['interactions'][1]['sender']['name']=='开发者'


def test_structure_tool_assigns_duplicate_return_only_to_unique_direct_match():
    from scene_completion.ssd_tools import complete_structure
    rr=exchange(sid='rr',layer='RR');sr=exchange(sid='sr')
    def response(i,sid):
        r=deepcopy(i);r.update(id=sid,sequence=2,direction='return',parent_id=i['id']);r['sender'],r['receiver']=deepcopy(i['receiver']),deepcopy(i['sender']);return r
    rrret=response(rr,'rrret');srret=response(sr,'srret')
    value={'interactions':[rr,rrret,sr,srret],'rr_sr_links':[{'rr_id':'rr','sr_ids':['sr','srret'],'status':'confirmed','source_refs':R},{'rr_id':'rrret','sr_ids':['srret'],'status':'confirmed','source_refs':R}],'pending':[]}
    log=[];out=complete_structure(value,log)
    assert out['rr_sr_links'][0]['sr_ids']==['sr'] and out['rr_sr_links'][1]['sr_ids']==['srret']
    assert log[0]['rr_message_id']=='rrret' and len(out['interactions'])==4
    # Two equally direct RR messages are a business ambiguity, not a tool fix.
    rrret2=deepcopy(rrret);rrret2['id']='rrret2';value['interactions'].append(rrret2);value['rr_sr_links'].append({'rr_id':'rrret2','sr_ids':['srret'],'status':'confirmed','source_refs':R})
    out=complete_structure(value)
    assert sum('srret' in link['sr_ids'] for link in out['rr_sr_links'])==3


def test_case_identity_context_resolves_whitespace_table_names_and_chinese_service_suffix():
    from scene_completion.task_context import ssd_context
    p=fused_fixture()['input'];p['RR'][0]['lines']=[{'number':5,'text':'ProductService服务写入 product 表，不是product_item表。'}]
    # Identity evidence is from another case, so only the actual spelling in
    # this case may select these resources.
    base=p['components']['components'][1]
    p['components']['components']=[{**deepcopy(base),'id':'product','name':'product表'},
      {**deepcopy(base),'id':'service','name':'ProductService'},
      {**deepcopy(base),'id':'wrong','name':'product_items表'}]
    p['SR']=[]
    selected=ssd_context(p)['components']['components']
    assert {r['id'] for r in selected}=={'product','service'}


def test_unique_table_reference_rejects_wrong_resource_but_multitable_is_not_guessed():
    from scene_completion.ssd_tools import validate_explicit_resources
    row=exchange();row['receiver'].update(name='merchant表',position='内部数据库')
    row['operation']['source_refs']=[{**R[0],'quote':'Service写入 product 表，保存商品草稿。'}]
    with pytest.raises(ValueError,match='explicitly names product表'):validate_explicit_resources([row])
    row['receiver']['name']='product表';validate_explicit_resources([row])
    row['receiver']['name']='sku表';row['operation']['source_refs'][0]['quote']='查询 product 表和 sku 表'
    validate_explicit_resources([row])
