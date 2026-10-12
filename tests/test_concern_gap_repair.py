from copy import deepcopy
import pytest
from scene_completion.concern_gap_repair import apply_repairs,reverse_validator
from scene_completion.semantic_backend import write_json


def test_repair_preserves_successful_scene_order_and_content(tmp_path):
    original=[{'scenario_id':i,'value':i} for i in ['Z','B','A']]
    write_json(tmp_path/'generation_repairs.json',[{'replacements':[{'rejected_scenario_id':'B',
        'replacement_scenarios':[{'scenario_id':'C','value':'fixed'}]}]}])
    assert apply_repairs(tmp_path,original)==[original[0],{'scenario_id':'C','value':'fixed'},original[2]]
    assert original[1]['value']=='B'


def test_repair_cannot_drop_or_duplicate_successful_source(tmp_path):
    write_json(tmp_path/'generation_repairs.json',[{'replacements':[{'rejected_scenario_id':'B',
        'replacement_scenarios':[{'scenario_id':'A'}]}]}])
    with pytest.raises(ValueError,match='duplicated'):apply_repairs(tmp_path,[{'scenario_id':'A'},{'scenario_id':'B'}])
    with pytest.raises(ValueError,match='targets changed'):apply_repairs(tmp_path,[{'scenario_id':'A'}])


def test_reverse_retry_feedback_never_replaces_the_model_quote_or_decision():
    packet={'input':{'units':[{'unit_id':'U','source_scenario_id':'G'}],
        'original_scenarios':[{'scenario_id':'G','trigger_condition':'价格为负数','failure_mechanism':'价格低于零'}]}}
    raw={'reviews':[{'unit_id':'U','source_supported':False,'atomic':True,'mapping_correct':True,
        'cause_correct':True,'evidence_quote':'负数价格','reason':'not atomic'}]}
    copy=deepcopy(raw)
    with pytest.raises(ValueError,match='exact_quote_choices'):reverse_validator(packet,raw)
    assert raw==copy
    raw['reviews'][0]['evidence_quote']='价格为负数'
    assert reverse_validator(packet,raw)[0]['passed'] is False
