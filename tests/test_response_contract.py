from copy import deepcopy

import pytest

from scene_completion.response_contract import contract_view, source_id_differences


def test_normalization_code_case_is_a_view_without_semantic_or_proof_rewrite():
    packet = {'stage': 'gap-normalize-G', 'input': {}, 'output_contract': {'items': []}}
    result = {'items': [{'source_scenario_id': 'G1', 'units': [{
        'object_code': 'response_productId', 'cause_code': 'invalidType',
        'condition_codes': ['hasToken'], 'exception_object': 'productId'}]}],
        'model': 'actual-model', 'input_hash': 'original-hash'}
    original = deepcopy(result)
    view = contract_view(packet, result)
    unit = view['items'][0]['units'][0]
    assert unit['object_code'] == 'response_product_id' and unit['cause_code'] == 'invalid_type'
    assert unit['condition_codes'] == ['hasToken'] and unit['exception_object'] == 'productId'
    assert view['model'] == result['model'] and view['input_hash'] == result['input_hash']
    assert result == original
    assert contract_view(dict(packet, stage='gap-generation'), result) == original
    malformed = deepcopy(result)
    malformed['items'][0]['units'][0].update(object_code='product-id', cause_code='未知')
    assert contract_view(packet, malformed) == malformed


def packet():
    return {'stage': 'gap-normalize-T', 'input': {'collection': 'T'}, 'output_contract': {'items': []}}


def test_echo_envelope_is_a_pure_view_retaining_actual_proof():
    raw = {'stage': 'gap-normalize-T', 'collection': 'T', 'output_contract': {'items': [{'source_scenario_id': 'T-1'}]},
        'model': 'actual-model', 'execution_model_evidence': {'requested_model': 'actual-model'}}
    before = deepcopy(raw)
    view = contract_view(packet(), raw)
    assert view['items'] == raw['output_contract']['items']
    assert view['model'] == 'actual-model' and raw == before
    view['items'].append({})
    assert raw == before


@pytest.mark.parametrize('extra', [
    {'items': [{'source_scenario_id': 'conflict'}]},
    {'other_answer': []}, {'collection': 'E'}, {'stage': 'another-stage'}])
def test_ambiguous_or_cross_channel_wrappers_are_rejected(extra):
    raw = {'output_contract': {'items': []}, **extra}
    with pytest.raises(ValueError): contract_view(packet(), raw)


def test_envelope_does_not_fill_missing_fields_or_accept_nested_transport_proof():
    with pytest.raises(ValueError, match='missing_inner_fields'):
        contract_view(packet(), {'output_contract': {}})
    with pytest.raises(ValueError, match='inner_transport_fields'):
        contract_view(packet(), {'output_contract': {'items': [], 'model': 'fake'}})


def test_plain_root_does_not_gain_missing_semantics():
    raw = {'items': [{'actual': 'data'}]}
    assert contract_view(packet(), raw) == raw
    assert contract_view(packet(), {}) == {}


def test_source_id_differences_identifies_missing_duplicate_and_unknown_entries():
    assert source_id_differences(['a','b'], ['a','a','unknown']) == {
        'expected_count': 2, 'actual_count': 3, 'missing_ids': ['b'], 'unknown_ids': ['unknown'], 'duplicate_ids': ['a']}
def test_generation_accepts_only_complete_id_keyed_collection_without_semantic_changes():
    from scene_completion.response_contract import contract_view
    packet = {'stage': 'gap-generation', 'input': {'mounts': [{'mount_id': 'm1'}, {'mount_id': 'm2'}]},
        'output_contract': {'items': []}}
    raw = {'m2': [{'trigger_condition': 'second'}], 'm1': [{'trigger_condition': 'first'}],
        'model': 'actual-model'}
    view = contract_view(packet, raw)
    assert view == {'model': 'actual-model', 'items': [
        {'mount_id': 'm1', 'scenarios': raw['m1']}, {'mount_id': 'm2', 'scenarios': raw['m2']}]}
    assert 'items' not in raw
    for wrapper in (lambda key,value: {'scenarios':value}, lambda key,value: {'mount_id':key,'scenarios':value}):
        wrapped={key:wrapper(key,value) for key,value in raw.items() if key!='model'}
        assert contract_view(packet,wrapped)['items']==view['items']
    assert 'items' not in contract_view(packet,{'m1':{'mount_id':'wrong','scenarios':raw['m1']},'m2':raw['m2']})
    for invalid in ({'m1': raw['m1']}, {**raw, 'unknown': []}, {**raw, 'm2': {'scenario': 'invalid'}}):
        assert 'items' not in contract_view(packet, invalid)

