from copy import deepcopy

import pytest

from scene_completion.response_contract import contract_view, source_id_differences


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
    for invalid in ({'m1': raw['m1']}, {**raw, 'unknown': []}, {**raw, 'm2': {'scenario': 'invalid'}}):
        assert 'items' not in contract_view(packet, invalid)

