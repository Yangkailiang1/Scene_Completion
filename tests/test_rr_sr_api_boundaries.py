"""RR/SR namespace, duplicate-view preservation and independent inverse anchors."""
from copy import deepcopy
import pytest
from tests.test_workflow import exchange,parameter,memory_inputs,R,fake_pipeline
from scene_completion.api_layers import qualify_mapping,merge_mappings
from scene_completion.interaction_enrichment import resolved_api_id,parameters_for
from scene_completion.interaction_identity import canonical_fused
from scene_completion.concern_alignment import recognize,compare


def sample():
    rr=exchange(sid='rr',layer='RR',api='API-1');rr['receiver']['name']='PlatformService';rr['operation']['name']='POST /v1/memory-instances'
    rr['data']['sequence']=[parameter('name','body',True,'string',rules=[('length','1-30')])]
    sr=deepcopy(rr);sr.update(id='sr',layer='SR',api_id=None);sr['data']['sequence']=[]
    internal=deepcopy(sr);internal.update(id='internal',parent_id='sr',api_id='API-1',sequence=2)
    internal['sender']=deepcopy(sr['receiver']);internal['receiver']['name']='AdminService';internal['operation']['name']='POST /mx/v1/memory-instances'
    internal['operation']['sequence']=['检查实例名称唯一性']
    fused={'interactions':[rr,sr,internal],'rr_sr_links':[{'rr_id':'rr','sr_ids':['sr','internal'],'status':'confirmed','basis':'同一次外部调用及其内部展开','source_refs':R}],'pending':[]}
    def mapping(owner,path):return {'services':[{'name':owner,'interfaces':[{'id':'API-1','name':'创建记忆实例','method':'POST','address':path,'source_refs':R}],'source_refs':R}]}
    maps=merge_mappings([('RR',mapping('PlatformService','/v1/memory-instances')),('SR',mapping('AdminService','/mx/v1/memory-instances'))])
    apis={'apis':[{'id':'RR::API-1','declared_id':'API-1','source_layer':'RR','name':'创建记忆实例','address':'/v1/memory-instances','parameters':[parameter('name','body',True,'string',rules=[('length','1-30')])],'source_refs':R},
      {'id':'SR::API-1','declared_id':'API-1','source_layer':'SR','name':'创建记忆实例','address':'/mx/v1/memory-instances','parameters':[parameter('name','body',False,'string',rules=[('length','1-100')])],'source_refs':R}]}
    return {'fused-ssd':fused,'api-map':maps,'api-parameters':apis,'normal-constraints':apis,'registry':memory_inputs()['registry'],'components':{'components':[]},'normal-rules':{'rules':[],'pending':[]}}


def test_confirmed_duplicate_preserves_RR_api_and_constraints_but_not_downstream_contract():
    x=sample();before=deepcopy(x);v=canonical_fused(x['fused-ssd'],x)
    assert [i['id'] for i in v['interactions']]==['sr','internal']
    assert v['aliases']==[{'source_id':'rr','interaction_id':'sr'}]
    outer,inner=v['interactions'];assert outer['api_id']=='RR::API-1' and inner['api_id']=='SR::API-1'
    material={**x,'rr-ssd':{'interactions':[]},'sr-ssd':{'interactions':v['interactions']}}
    outer_name=parameters_for(outer,material)[0];inner_name=parameters_for(inner,material)[0]
    assert outer_name['required'] is True and {r['value'] for r in outer_name['constraints']}=={'1-30'}
    assert inner_name['required'] is False and {r['value'] for r in inner_name['constraints']}=={'1-100'}
    assert len(v['source_views']['sr'])==2 and x==before


def test_missing_public_constraints_are_not_inherited_from_internal_API():
    x=sample();rr=x['fused-ssd']['interactions'][0];rr['data']['sequence']=[parameter('name','body',None,None)]
    x['api-parameters']['apis'][0]['parameters']=[parameter('name','body',None,None)]
    rows=canonical_fused(x['fused-ssd'],x)['interactions'];outer=rows[0]
    m={**x,'rr-ssd':{'interactions':[]},'sr-ssd':{'interactions':rows}}
    p=parameters_for(outer,m)[0]
    assert p['data_type'] is None and p['required'] is None and p['constraints']==[]
    assert parameters_for(rows[1],m)[0]['constraints']


def test_same_raw_identifier_resolves_only_with_its_layer_or_an_explicit_wire_path():
    x=sample();rr,sr,internal=x['fused-ssd']['interactions']
    assert resolved_api_id(rr,x)=='RR::API-1'
    assert resolved_api_id(internal,x)=='SR::API-1'
    assert resolved_api_id(sr,x)=='RR::API-1'  # exact /v1 path even in SR narrative
    ambiguous=deepcopy(sr);ambiguous['operation']['name']='创建';ambiguous['receiver']['name']='Unknown'
    assert resolved_api_id(ambiguous,x) is None


def test_E_G_GT_duplicate_view_bindings_count_once_and_internal_call_remains_distinct():
    x=sample()
    def match(iid):return {'interaction_id':iid,'target':'data','object':'name','data_location':'body','concern_key':'api.data.length','basis':'明示长度约束','concrete_rule':'长度符合要求','source_refs':R}
    g=recognize(x,{'matches':[match('rr'),match('sr')]});g['matches']=[m for m in g['matches'] if not m.get('policy_id')];e=recognize(x,{'matches':[match('rr')]},inverse=True);gt=recognize(x,{'matches':[match('sr')]},inverse=True)
    assert len(g['matches'])==len(e['matches'])==len(gt['matches'])==1
    assert g['matches'][0]['binding_id']==e['matches'][0]['binding_id']==gt['matches'][0]['binding_id']
    assert g['matches'][0]['api_id']=='RR::API-1' and g['matches'][0]['api_source_layer']=='RR'
    internal=recognize(x,{'matches':[match('internal')]},inverse=True)
    assert internal['matches'][0]['binding_id']!=gt['matches'][0]['binding_id']
    evaluated=compare(g,e,gt);assert len(evaluated['G_c'])==len(evaluated['GT_c'])==1


def test_inverse_literal_internal_path_does_not_bind_to_the_public_interface():
    x=sample();quote='测试 POST /mx/v1/memory-instances，name长度超过限制'
    ref={'source_id':'test','line_start':1,'line_end':1,'quote':quote}
    x['test-documents']=[{'source_id':'test','name':'test.md','channel':'test','lines':[{'number':1,'text':quote}]}]
    m={'interaction_id':'rr','target':'data','object':'name','data_location':'body','concern_key':'api.data.length','basis':'测试接口','concrete_rule':'长度限制','source_refs':[ref]}
    value=recognize(x,{'matches':[m]},inverse=True)
    assert value['matches'][0]['interaction_id']=='internal' and value['matches'][0]['api_id']=='SR::API-1'


def test_nested_call_is_not_collapsed_and_repeated_actual_calls_are_not_guessed():
    x=sample();v=x['fused-ssd'];rr,sr,inner=v['interactions']
    v['rr_sr_links'][0]['sr_ids']=['internal'];assert not canonical_fused(v,x)['aliases']
    v['rr_sr_links'][0]['sr_ids']=['sr','sr-second'];second=deepcopy(sr);second['id']='sr-second';v['interactions'].append(second)
    out=canonical_fused(v,x);assert not out['aliases'] and out['pending']


def test_calling_API_rule_from_a_different_actual_request_cannot_move_the_failure():
    from scene_completion.normal_rules import normalize_scenarios
    from tests.test_workflow import scenario
    x=sample();s=scenario('t');s.update(interaction_id='rr',field='name',object='name',concern_key='api.data.length',scope='interface',data_location='body',rule_id='internal-rule')
    x['normal-rules']={'rules':[{'id':'internal-rule','interaction_id':'internal','concern_key':'api.data.length','fields':['name']}],'pending':[]}
    out=normalize_scenarios({'scenarios':[s]},x,truth=True)['scenarios'][0]
    assert out['interaction_id']=='rr' and out['rule_id'] is None


def test_normal_rule_and_inverse_context_keep_local_validation_ownership():
    from scene_completion.failure_units import normalize_bindings
    from scene_completion.task_context import inverse_concern_context
    x=sample();x['branches']={'branches':[{'id':'b','description':'AdminService检查名称唯一性失败','source_refs':R}]}
    b={'branch_id':'b','interaction_id':'rr','status':'confirmed','basis':'校验失败','source_refs':R}
    assert normalize_bindings({'bindings':[b]},x)['bindings'][0]['interaction_id']=='internal'
    x['bindings']={'bindings':[{**b,'interaction_id':'internal'}]}
    view=inverse_concern_context(x)
    assert [i['api_id'] for i in view['interface_ownership']]==['SR::API-1']
    assert {a['id'] for a in view['normal-constraints']['apis']}==set()  # branch does not name an API field


def test_pipeline_extracts_RR_and_SR_API_tables_from_separate_documents(tmp_path):
    from scene_completion.workflow import Execution,build_pipeline
    rr,sr,tests,mocks=fake_pipeline(tmp_path)
    for docs,path in [(rr,'/v1/memory-instances'),(sr,'/mx/v1/memory-instances')]:
        start=max(r['number'] for r in docs[0]['lines'])+1
        docs[0]['lines'] += [{'number':start,'text':'## API-1 创建记忆实例'},{'number':start+1,'text':'POST '+path},{'number':start+2,'text':'name: string，必填，长度'+('1-30' if docs is rr else '1-100')}]
    seen=[]
    def mapping(p):
        layer='RR' if 'RR' in p['input'] else 'SR';doc=p['input'][layer][0];seen.append(layer)
        line=next(r for r in doc['lines'] if r['text'].startswith('POST '))
        ref=[{'source_id':doc['source_id'],'line_start':line['number'],'line_end':line['number'],'quote':line['text']}]
        return {'services':[{'name':'PlatformService' if layer=='RR' else 'AdminService','interfaces':[{'id':'API-1','name':'创建记忆实例','method':'POST','address':'/v1/memory-instances' if layer=='RR' else '/mx/v1/memory-instances','source_refs':ref}],'source_refs':ref}]}
    def params(p):
        layer='RR' if 'RR' in p['input'] else 'SR';interface=p['input']['interface'];doc=p['input'][layer][0];line=next(r for r in doc['lines'] if r['text'].startswith('name:'))
        ref=[{'source_id':doc['source_id'],'line_start':line['number'],'line_end':line['number'],'quote':line['text']}]
        field=parameter('name','body',True,'string',rules=[('length','1-30' if layer=='RR' else '1-100')]);field['source_refs']=ref
        for c in field['constraints']:c['source_refs']=ref
        return {'apis':[{'id':interface['id'],'name':interface['name'],'address':interface['address'],'parameters':[field],'source_refs':ref}]}
    mocks['api-map']=mapping;mocks['api-parameters']=params
    ex=Execution(tmp_path/'run',mocks=mocks,config={'max_concurrency':3});build_pipeline(ex,rr,sr,[]);result=ex.finish()
    assert result['complete'],{k:r.get('failure') for k,r in ex.scheduler.state['tasks'].items() if r['status']!='passed'}
    assert sorted(seen)==['RR','SR']
    from scene_completion.storage import read_json
    def output(key):return read_json(ex.root/ex.scheduler.state['tasks'][key]['output_file'])['payload']
    assert output('rr-api-parameters')['apis'][0]['id']=='RR::API-1'
    assert output('sr-api-parameters')['apis'][0]['id']=='SR::API-1'
    assert len(output('api-parameters')['apis'])==2


def test_distinct_interfaces_never_merge_even_when_caller_and_callee_are_equal():
    x=sample();rr,sr,internal=x['fused-ssd']['interactions']
    internal['sender']=deepcopy(rr['sender']);internal['receiver']=deepcopy(rr['receiver'])
    x['fused-ssd']['rr_sr_links'][0]['sr_ids']=['internal']
    out=canonical_fused(x['fused-ssd'],x)
    assert not out['aliases'] and len(out['interactions'])==3


def test_legacy_duplicate_views_keep_the_single_explicit_API_without_guessing_a_new_one():
    x=sample();x['api-map']={'services':[]};x['api-parameters']['apis']=x['api-parameters']['apis'][:1]
    x['normal-constraints']=x['api-parameters'];rr,sr,_=x['fused-ssd']['interactions']
    sr['operation']['name']='创建';out=canonical_fused(x['fused-ssd'],x)
    assert out['aliases']==[{'source_id':'rr','interaction_id':'sr'}]
    assert out['interactions'][0]['api_id']=='RR::API-1'


def test_same_concern_and_field_on_different_interfaces_does_not_score_as_a_match():
    x=sample()
    def one(iid):return {'interaction_id':iid,'target':'data','object':'name','data_location':'body','concern_key':'api.data.length','basis':'接口明示长度','concrete_rule':'长度约束','source_refs':R}
    g=recognize(x,{'matches':[one('rr')]});gt=recognize(x,{'matches':[one('internal')]},inverse=True)
    out=compare(g,{'matches':[]},gt)
    assert out['metrics']['generation_validity']['value']==0


def test_multihop_sender_receiver_is_rejected_for_minimal_SSD_remodelling():
    from scene_completion.use_cases import validate_catalogue
    x=sample();x['fused-ssd']['interactions'][0]['receiver']['name']='PlatformService→AdminService'
    doc={'source_id':R[0]['source_id'],'name':'spec.md','channel':'normal','lines':[{'number':1,'text':R[0]['quote']}]}
    with pytest.raises(ValueError,match='最小双方交互'):
        validate_catalogue('fused-ssd',x['fused-ssd'],{'RR':[doc],'SR':[doc],'case-group':{'id':'CASE-A'}})


def test_rule_partition_retains_distinct_API_identity_when_abstract_operation_names_are_equal():
    from scene_completion.api_layers import qualify_fused_calls
    from scene_completion.task_partitions import split_task
    x=sample();rr,sr,internal=x['fused-ssd']['interactions']
    rr['sender']['name']=sr['sender']['name']='ServiceA'
    rr['operation']['name']=sr['operation']['name']='创建'
    sr['api_id']='API-1'
    # Both source documents reuse API-1; layer-specific definitions prove
    # different wire interfaces despite identical participants/operation text.
    raw=qualify_fused_calls(x['fused-ssd'],x)
    assert raw['interactions'][0]['api_id']=='RR::API-1' and raw['interactions'][1]['api_id']=='SR::API-1'
    units=split_task('normal-rules',{'fused-ssd':raw,'normal-documents':[]})
    assert {key for key,_ in units}=={'rr','sr','internal'}


def test_imported_parameter_file_cannot_cross_interface_or_layer():
    from scene_completion.api_layers import scoped_imports
    part={'payload':{'apis':[{'id':'API-1','address':'/mx/v1/memory-instances','parameters':[]}]}}
    rr={'id':'RR::API-1','declared_id':'API-1','source_layer':'RR','address':'/v1/memory-instances'}
    sr={**rr,'id':'SR::API-1','source_layer':'SR','address':'/mx/v1/memory-instances'}
    assert scoped_imports([part],rr)==[]
    assert scoped_imports([part],sr)[0]['payload']['apis'][0]['id']=='SR::API-1'
    assert part['payload']['apis'][0]['id']=='API-1'
