"""Obsolete mutation business constraints remain readable, never live taxonomy."""
from copy import deepcopy
from pathlib import Path
from scene_completion.concern_registry import registry,registry_scope
from scene_completion.project_review import project_registry,registry_view
from scene_completion.scenario_patterns import normalize_settings
from scene_completion.storage import write_json,read_json,fingerprint
from scene_completion.concern_alignment import recognize
from tests.test_workflow import memory_inputs,R

KEY='service.resource_mutation.business_constraint'
NEW='service.business_attribute_constraint'


def historical_registry():
    r=registry();r['definitions'][KEY]['enabled']=True
    r['profiles']['functional']['resource_mutation'].append(KEY)
    r['hash']=fingerprint({k:v for k,v in r.items() if k!='hash'});return r


def test_default_only_enables_new_business_entity_constraint():
    r=registry();assert not r['definitions'][KEY]['enabled']
    assert r['definitions'][NEW].get('enabled',True)
    x=memory_inputs();m={'interaction_id':'req','target':'receiver','object':'Platform','concern_key':KEY,'basis':'旧版分类','concrete_rule':'状态不能改','source_refs':R}
    result=recognize(x,{'matches':[m]})
    assert not any(m['concern_key']==KEY for m in result['matches']) and result['pending']


def test_old_project_retires_once_preserves_custom_and_historical_reports(tmp_path):
    r=historical_registry();r['definitions']['api.data.type']['description']='项目类型说明'
    r['hash']=fingerprint({k:v for k,v in r.items() if k!='hash'})
    write_json(tmp_path/'run/registry_override.json',r)
    write_json(tmp_path/'run/registry_used'/(r['hash']+'.json'),r)
    report=tmp_path/'run/missing_report.md';report.write_text('旧报告分数与分类不可改写\n');before=report.read_bytes()
    value=project_registry(tmp_path)
    assert not value['definitions'][KEY]['enabled']
    assert KEY not in value['profiles']['functional']['resource_mutation']
    assert value['definitions']['api.data.type']['description']=='项目类型说明'
    assert report.read_bytes()==before
    old=registry_view(tmp_path,r['hash']);assert old['read_only'] and old['registry']['definitions'][KEY]['enabled']
    n=len(list((tmp_path/'concern_versions').glob('*.json')))
    assert project_registry(tmp_path)==value and len(list((tmp_path/'concern_versions').glob('*.json')))==n


def test_old_patterns_disabled_without_relabelling_or_changing_frozen_snapshot():
    r=historical_registry()
    with registry_scope(r):old=normalize_settings()
    source=deepcopy(old);new=normalize_settings(old)
    pattern=next(p for p in new['library']['patterns'] if p['id']=='rule.'+KEY)
    assert not pattern['enabled'] and pattern['concern_keys']==[KEY] and old==source
    with registry_scope(r):assert next(p for p in normalize_settings(old)['library']['patterns'] if p['id']=='rule.'+KEY)['enabled']


def test_normal_rules_prompt_does_not_advertise_retired_keys_as_active():
    text=(Path(__file__).resolve().parents[1]/'.cac/skills/scene-normal-rules/SKILL.md').read_text()
    assert KEY not in text and 'service.resource_mutation.persistence_consistency' not in text
    assert NEW in text and 'enabled' in text
