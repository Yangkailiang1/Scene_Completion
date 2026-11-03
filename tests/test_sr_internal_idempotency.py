"""Explicit SR internal R/U/D default, separate from source evidence and GT."""
from copy import deepcopy
import pytest
from tests.test_workflow import exchange,R,memory_inputs
from scene_completion.framework_idempotency import KEY,POLICY,applicable,scenarios
from scene_completion.concern_alignment import recognize,compare
from scene_completion.concern_registry import registry,registry_scope
from scene_completion.validation import validate_result
from scene_completion.scenario_patterns import applicability,generated,normalize_settings
from scene_completion.storage import fingerprint,write_json,read_json


def sample(kinds=('read',),source_layer='SR'):
    i=exchange(api=source_layer+'::API-1');i['sender'].update(name='PlatformService',position='系统边界')
    i['receiver'].update(name='AdminService',position='内部服务');i['operation']['kinds']=list(kinds)
    api={'id':i['api_id'],'source_layer':source_layer,'name':'记忆操作','address':'/mx/v1/memory-instances','parameters':[],'source_refs':R}
    return {'enriched-interactions':{'interactions':[i]},'rr-ssd':{'interactions':[]},'sr-ssd':{'interactions':[i]},
       'api-parameters':{'apis':[api]},'components':{'components':[]},'normal-rules':{'rules':[],'pending':[]},
       'registry':registry()}


@pytest.mark.parametrize('kinds',[('read',),('update',),('delete',),('read','update','delete')])
def test_internal_RUD_enabled_without_spec_guards_counts_once(kinds):
    x=sample(kinds);raw={'matches':[]};g=recognize(x,raw);assert raw=={'matches':[]}
    assert len(g['matches'])==1
    m=g['matches'][0];assert m['status']=='applicable' and m['concern_key']==KEY
    assert m['policy_id']==POLICY and m['identification']=='framework_policy' and not m['activation_evidence']
    assert m['api_source_layer']=='SR'
    validate_result('concern-match',g,x)
    x['concern-match']=g;s=scenarios(x);assert len(s)==1
    assert s[0]['policy_id']==POLICY and not s[0]['executable'] and s[0]['resolution']=='conditional'
    validate_result('exception-generate',{'scenarios':s,'pending':[]},x)
    pattern=applicability(x);result=generated(pattern)
    assert len(result['scenarios'])==1 and result['scenarios'][0]['confidence']['score']==.85
    assert '用户确认' in result['scenarios'][0]['confidence']['basis']


@pytest.mark.parametrize('change',['human','ui','external','RR','create','return','unknown-crud','local-processing'])
def test_public_C_returns_and_unconfirmed_CRUD_do_not_force(change):
    x=sample();i=x['enriched-interactions']['interactions'][0]
    if change=='human':i['sender'].update(name='开发者',position='外部Actor（人类）')
    elif change=='ui':i['sender'].update(name='控制台',position='UI/前端')
    elif change=='external':i['receiver']['position']='外部Actor（系统）'
    elif change=='RR':x['api-parameters']['apis'][0]['source_layer']='RR'
    elif change=='create':i['operation']['kinds']=['create']
    elif change=='return':i['direction']='return'
    elif change=='unknown-crud':x['business-crud']={'rows':[]}
    elif change=='local-processing':i['sender']=deepcopy(i['receiver'])
    assert not applicable(i,x)
    assert not recognize(x,{'matches':[]})['matches']


def test_RR_public_API_stays_public_after_duplicate_view_uses_SR_identity():
    x=sample(source_layer='RR');assert x['enriched-interactions']['interactions'][0]['layer']=='SR'
    assert not recognize(x,{'matches':[]})['matches']


def test_empty_E_GT_not_filled_by_policy_and_inverse_aliases_align_only_own_observation():
    x=sample();g=recognize(x,{'matches':[]})
    e=recognize(x,{'matches':[]},inverse=True);gt=recognize(x,{'matches':[]},inverse=True)
    assert not e['matches'] and not gt['matches']
    observed={'interaction_id':'req','target':'receiver','object':'AdminService','concern_key':'service.crud.update.idempotency',
        'basis':'独立测试描述重复操作破坏状态','concrete_rule':'重复请求不应产生额外影响','source_refs':R}
    x=sample(('update',));gt=recognize(x,{'matches':[observed]},inverse=True)
    assert len(gt['matches'])==1 and gt['matches'][0]['concern_key']==KEY
    assert gt['matches'][0]['identification']=='inverse_llm' and 'policy_id' not in gt['matches'][0]
    assert compare(recognize(x,{'matches':[]}),e,gt)['metrics']['generation_validity']['value']==100


def test_duplicate_aliases_count_once_real_requests_count_separately():
    x=sample(('read','update','delete'))
    raw=[{'interaction_id':'req','target':'receiver','object':'AdminService','concern_key':key,'basis':'幂等要求','concrete_rule':'重复执行不多写','source_refs':R} for key in ('service.crud.update.idempotency','service.crud.delete.idempotency')]
    assert len(recognize(x,{'matches':raw})['matches'])==1
    second=deepcopy(x['enriched-interactions']['interactions'][0]);second['id']='second';second['sequence']=2
    x['enriched-interactions']['interactions'].append(second)
    assert len(recognize(x,{'matches':[]})['matches'])==2


def test_manual_disable_respected_and_no_scenario_before_recognition():
    x=sample();x['concern-match']={'matches':[]};assert scenarios(x)==[]
    r=registry();r['definitions'][KEY]['enabled']=False;r['hash']=fingerprint({k:v for k,v in r.items() if k!='hash'})
    with registry_scope(r):assert not recognize(x,{'matches':[]})['matches']


def test_existing_project_migration_versions_once_preserves_custom_values(tmp_path):
    from scene_completion.project_review import project_registry
    r=registry();r['framework_policies'].pop('sr_internal_rud_idempotency');r['definitions'][KEY]['enabled']=False
    r['definitions']['api.data.type']['description']='项目自定义类型说明';r['hash']=fingerprint({k:v for k,v in r.items() if k!='hash'})
    write_json(tmp_path/'run/registry_override.json',r)
    new=project_registry(tmp_path);assert new['definitions'][KEY]['enabled']
    assert new['definitions']['api.data.type']['description']=='项目自定义类型说明'
    history=list((tmp_path/'concern_versions').glob('*.json'));assert len(history)==2
    assert project_registry(tmp_path)==new and len(list((tmp_path/'concern_versions').glob('*.json')))==2
    new['definitions'][KEY]['enabled']=False;new['hash']=fingerprint({k:v for k,v in new.items() if k!='hash'})
    write_json(tmp_path/'run/registry_override.json',new);assert not project_registry(tmp_path)['definitions'][KEY]['enabled']


def test_pattern_policy_migrates_once_and_later_removal_is_not_undone():
    value=normalize_settings();value.pop('framework_policy_versions')
    pid='rule.'+KEY;value['library']['patterns']=[p for p in value['library']['patterns'] if p['id']!=pid]
    upgraded=normalize_settings(value);assert any(p['id']==pid for p in upgraded['library']['patterns'])
    upgraded['library']['patterns']=[p for p in upgraded['library']['patterns'] if p['id']!=pid]
    assert not any(p['id']==pid for p in normalize_settings(upgraded)['library']['patterns'])


def test_actual_business_CRUD_not_supported_capability_controls_policy():
    x=sample(('create',));x['business-crud']={'rows':[{'interaction_id':'req','operation':'read'}]}
    assert recognize(x,{'matches':[]})['matches']
    x['business-crud']['rows'][0]['operation']='create'
    assert not recognize(x,{'matches':[]})['matches']


def test_explicit_idempotency_rule_refines_default_instead_of_duplicate_generic_scene():
    from scene_completion.normal_rules import rule_exceptions
    x=sample(('update',));x['concern-match']=recognize(x,{'matches':[]})
    x['normal-rules']['rules']=[{'id':'actual-idem','interaction_id':'req','concern_key':'service.crud.update.idempotency','fields':[],
        'condition':'同一请求重试不重复修改状态','violation':'同一请求重试重复修改状态','functional_kinds':['update'],'owner_service':'AdminService',
        'source_refs':R,'resolution':'explicit','pending_details':[]}]
    source=deepcopy(x['normal-rules'])
    actual=rule_exceptions(x);assert len(actual)==1 and actual[0]['concern_key']==KEY
    assert scenarios(x)==[] and x['normal-rules']==source
    result=generated(applicability(x));assert len(result['scenarios'])==1
    assert result['scenarios'][0]['rule_id']=='actual-idem'
