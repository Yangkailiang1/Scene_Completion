from copy import deepcopy
import pytest
from scene_completion.concern_gap_dedup import pairs,merge
from tests.test_concern_gap import unit


def source(k,conditions):
    u=unit(k);u.update(unit_id=k,source_scenario_id=k,collection='G',condition_codes=conditions,
        necessary_conditions=conditions,source_basis='explicit')
    return u


def decision(l,r,same):
    return {'left_unit_id':l,'right_unit_id':r,'equivalent':same}


def test_duplicate_context_views_merge_but_keep_all_original_conditions_and_tags():
    a=source('a',['query_is_executed']);b=source('b',[]);b['concern_keys']=['internal_database.resource_existence']
    assert len(pairs([a,b]))==1
    merged=merge([a,b],'G2',[decision('a','b',True)])
    assert len(merged)==1 and len(merged[0]['members'])==2
    assert {m['source_basis'] for m in merged[0]['members']}=={'ssd_derived'}
    assert [m['original_necessary_conditions'] for m in merged[0]['members']]==[['query_is_executed'],[]]
    assert len(merged[0]['necessary_conditions'])==len(merged[0]['condition_codes'])
    assert 'internal_database.resource_existence' in merged[0]['concern_keys']


def test_additional_causal_condition_is_preserved_when_not_equivalent():
    a=source('a',[]);b=source('b',['resource_was_deleted'])
    assert len(merge([a,b],'G2',[decision('a','b',False)]))==2
    with pytest.raises(ValueError,match='incomplete'):merge([a,b],'G2',[])


def test_equivalence_conflicts_and_different_objects_do_not_merge():
    a=source('a',[]);b=source('b',['b']);c=source('c',['c'])
    with pytest.raises(ValueError,match='contradictory'):
        merge([a,b,c],'G2',[decision('a','b',True),decision('a','c',False),decision('b','c',True)])
    c['object_code']='different_object'
    assert len(pairs([a,c]))==0 and len(merge([a,c],'G2',[]))==2
