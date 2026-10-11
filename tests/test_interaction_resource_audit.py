"""Portable lab example: a business call cannot conceal its resource read."""
from copy import deepcopy

import pytest

from scene_completion.interaction_resource_audit import resource_universe, validate_resource_reviews


@pytest.mark.parametrize('model', [{}, {'nodes': [{'kind': 'internal_database', 'layer': 'SR'}]}, {'components': None}])
def test_wrong_model_schema_cannot_silently_claim_no_resource_checks(model):
    with pytest.raises(ValueError, match='normal-model components schema'):
        resource_universe(model)


def test_explicit_model_without_resources_has_empty_universe():
    assert resource_universe({'components': []}) == []


def fixture():
    ref = {'document': 'clinic.md', 'line_start': 4, 'line_end': 4}
    nodes = [{'component_id': 'entry', 'kind': 'internal_service', 'layer': 'SR'},
        {'component_id': 'lab', 'kind': 'internal_service', 'layer': 'SR'},
        {'component_id': 'db', 'kind': 'external_database', 'layer': 'SR'},
        {'component_id': 'facade', 'kind': 'internal_service', 'layer': 'SR', 'physical_resource_id': 'db'}]
    lines = {'clinic.md:L4': {'line_id': 'clinic.md:L4', 'requirement_layer': 'SR',
        'source_origin': 'normal', 'text': 'LabService reads specimen table.', 'source_refs': [ref]}}
    exchanges = {'parent': {'requirement_layer': 'SR', 'from_component_id': 'entry',
        'to_component_id': 'lab', 'source_refs': [ref]},
        'read': {'requirement_layer': 'SR', 'from_component_id': 'lab', 'to_component_id': 'db', 'source_refs': [ref]}}
    data = {'source_resource_coverage_required': True, 'normal_model': {'components': nodes}}
    result = {'resource_operation_reviews': [{'resource_component_id': 'db', 'reason': 'Original specimen read',
        'operations': [{'line_id': 'clinic.md:L4', 'caller_component_id': 'lab', 'operation': 'read specimen',
            'evidence_quote': 'LabService reads specimen table.', 'local_exchange_ids': ['read']}]}]}
    return data, result, lines, exchanges


@pytest.mark.parametrize('target', ['db', 'facade'])
def test_actual_resource_call_or_explicit_facade_counts(target):
    data, result, lines, exchanges = fixture()
    exchanges['read']['to_component_id'] = target
    before = deepcopy(exchanges)
    findings = []
    assert validate_resource_reviews(data, result, lines, exchanges, findings) == result['resource_operation_reviews']
    assert findings == [] and exchanges == before


def test_omission_reported_without_creating_resource_call():
    data, result, lines, exchanges = fixture()
    result['resource_operation_reviews'][0]['operations'][0]['local_exchange_ids'] = []
    findings = []
    validate_resource_reviews(data, result, lines, exchanges, findings)
    assert findings[0]['code'] == 'source_resource_call_omitted'
    assert set(exchanges) == {'parent', 'read'}


@pytest.mark.parametrize('error', ['parent', 'wrong_caller', 'wrong_layer', 'exception', 'quote', 'missing_resource'])
def test_resource_inventory_cannot_claim_unrelated_or_abnormal_call(error):
    data, result, lines, exchanges = fixture()
    if error == 'parent':
        result['resource_operation_reviews'][0]['operations'][0]['local_exchange_ids'] = ['parent']
    elif error == 'wrong_caller':
        exchanges['read']['from_component_id'] = 'entry'
    elif error == 'wrong_layer':
        exchanges['read']['requirement_layer'] = 'RR'
    elif error == 'exception':
        lines['clinic.md:L4']['source_origin'] = 'abnormal'
    elif error == 'quote':
        result['resource_operation_reviews'][0]['operations'][0]['evidence_quote'] = 'invented normal read'
    else:
        result['resource_operation_reviews'] = []
    with pytest.raises(ValueError):
        validate_resource_reviews(data, result, lines, exchanges, [])


def test_resource_call_requires_exact_own_anchor():
    data, result, lines, exchanges = fixture()
    exchanges['read']['source_refs'] = []
    findings = []
    validate_resource_reviews(data, result, lines, exchanges, findings)
    assert findings[0]['code'] == 'source_resource_call_without_anchor'


def test_architecture_only_resource_does_not_invent_dependency():
    data, result, lines, exchanges = fixture()
    result['resource_operation_reviews'][0].update(operations=[], reason='Declared in architecture; no positive call in this assigned flow')
    findings = []
    validate_resource_reviews(data, result, lines, exchanges, findings)
    assert not findings


def test_original_missing_caller_is_a_blocking_gap_without_fabricated_nodes():
    data, result, lines, exchanges = fixture()
    data['resource_caller_source_required'] = True
    data['normal_model']['components'] = [n for n in data['normal_model']['components'] if n['component_id'] != 'lab']
    op = result['resource_operation_reviews'][0]['operations'][0]
    op.update(caller_source_name='LabService', caller_component_id='', local_exchange_ids=[])
    before = deepcopy(data)
    findings = []
    validate_resource_reviews(data, result, lines, exchanges, findings)
    assert findings[0]['code'] == 'resource_caller_not_modeled'
    assert findings[0]['caller_source_name'] == 'LabService'
    assert data == before


@pytest.mark.parametrize('defect', ['no_name', 'invented_name', 'invented_id', 'claim_existing_call'])
def test_missing_caller_cannot_be_hidden_or_invented(defect):
    data, result, lines, exchanges = fixture()
    data['resource_caller_source_required'] = True
    op = result['resource_operation_reviews'][0]['operations'][0]
    op.update(caller_source_name='LabService', caller_component_id='', local_exchange_ids=[])
    if defect == 'no_name':
        del op['caller_source_name']
    elif defect == 'invented_name':
        op['caller_source_name'] = 'InventedService'
    elif defect == 'invented_id':
        op['caller_component_id'] = 'invented'
    else:
        op['local_exchange_ids'] = ['read']
    with pytest.raises(ValueError):
        validate_resource_reviews(data, result, lines, exchanges, [])


def test_current_resource_caller_also_requires_original_name_in_new_protocol():
    data, result, lines, exchanges = fixture()
    data['resource_caller_source_required'] = True
    with pytest.raises(ValueError, match='caller_source_name'):
        validate_resource_reviews(data, result, lines, exchanges, [])
    result['resource_operation_reviews'][0]['operations'][0]['caller_source_name'] = 'LabService'
    findings = []
    validate_resource_reviews(data, result, lines, exchanges, findings)
    assert findings == []
