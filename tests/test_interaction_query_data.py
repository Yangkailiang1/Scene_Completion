from copy import deepcopy

import pytest

from scene_completion.interaction_query_data import (QUERY_DATA_POLICY, audit_query_data,
    validate_derived_response_shape, validate_derived_response_sources)
from scene_completion.sources import index_sources, validate_refs


def setup_query(tmp_path):
    path = tmp_path / 'clinic.md'
    path.write_text('# Record lookup\n## Basic flow\n1. RecordsService queries patient records.\n2. RecordsService updates the record.\n## Alternative flows\nException scenario: record query failed.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    refs = lambda n: validate_refs([{'document': path.name, 'line_start': n, 'line_end': n}], index)
    marker = {'field':'patient query result', 'derivation_reason':'Result of the documented query; schema unspecified.',
        'evidence_quote':'RecordsService queries patient records.', 'source_refs':refs(3), 'protocol_structure_unknown':True}
    exchange = {'local_id':'read', 'requirement_layer':'SR', 'operation_kinds':['read'],
        'source_refs':refs(3), 'response_fields':[marker['field']], 'derived_response_data':[marker]}
    source = {'line_id':'clinic.md:L3','text':path.read_text(encoding='utf-8').splitlines()[2], 'source_refs':refs(3)}
    inventory = [{'line_id':source['line_id'], 'datums':[{'source_kind':'query_semantics','direction':'response',
        'mappings':[{'local_exchange_id':'read','field':marker['field']}]}]}]
    data = {'query_data_policy':QUERY_DATA_POLICY, 'normal_model':{'exchanges':[exchange]}, 'normal_source_lines':[source]}
    return index, exchange, data, inventory, refs


def test_logical_query_result_requires_independent_inventory_and_preserves_raw(tmp_path):
    index, exchange, data, inventory, _ = setup_query(tmp_path)
    before = deepcopy([data, inventory])
    validate_derived_response_sources(exchange, index)
    assert audit_query_data(data, inventory, index) == []
    assert [data, inventory] == before


@pytest.mark.parametrize('mutation', ['non_read','unbound','wrong_layer','abnormal','invented_quote','known_schema','wrong_field','extra_protocol_type','bad_shape'])
def test_rejects_unbound_or_fabricated_query_provenance(tmp_path, mutation):
    index, exchange, _, _, refs = setup_query(tmp_path)
    marker = exchange['derived_response_data'][0]
    if mutation == 'non_read': exchange['operation_kinds'] = ['update']
    if mutation == 'unbound': marker['source_refs'] = refs(4)
    if mutation == 'wrong_layer': exchange['requirement_layer'] = 'RR'
    if mutation == 'abnormal':
        marker['source_refs'] = exchange['source_refs'] = refs(6)
        marker['evidence_quote'] = 'record query failed.'
    if mutation == 'invented_quote': marker['evidence_quote'] = 'Returns {exists: true}'
    if mutation == 'known_schema': marker['protocol_structure_unknown'] = False
    if mutation == 'wrong_field': marker['field'] = 'other result'
    if mutation == 'extra_protocol_type': marker['type'] = 'boolean'
    if mutation == 'bad_shape': exchange['derived_response_data'] = ['result']
    with pytest.raises(ValueError): validate_derived_response_sources(exchange, index)


@pytest.mark.parametrize('mutation,expected', [('unmarked','derived_query_data_not_marked'),('unverified','logical_query_derivation_not_verified'),('explicit','logical_query_derivation_not_verified')])
def test_inference_cannot_pass_without_marked_and_independently_confirmed_links(tmp_path, mutation, expected):
    index, exchange, data, inventory, _ = setup_query(tmp_path)
    if mutation == 'unmarked': exchange['derived_response_data'] = []
    if mutation == 'unverified': inventory[0]['datums'] = []
    if mutation == 'explicit': inventory[0]['datums'][0]['source_kind'] = 'explicit'
    assert [f['code'] for f in audit_query_data(data, inventory, index)] == [expected]


def test_query_inference_never_creates_request_data(tmp_path):
    index, _, data, inventory, _ = setup_query(tmp_path)
    inventory[0]['datums'][0]['direction'] = 'request'
    with pytest.raises(ValueError, match='never invented request'):
        audit_query_data(data, inventory, index)


def test_legacy_model_not_silently_upgraded(tmp_path):
    index, _, data, inventory, _ = setup_query(tmp_path)
    data.pop('query_data_policy')
    before = deepcopy(data)
    assert audit_query_data(data, [], index) == []
    assert data == before


def test_structured_inventory_preserves_source_kind(tmp_path):
    from scene_completion.interaction_output_schema import audit_output_schema, validate_output_shape
    contract = {'line_reviews':[{'line_id':'id'}], 'source_data_reviews':[{'line_id':'id','reason':'reason',
        'datums':[{'datum':'data','direction':'request|response','source_kind':'explicit|query_semantics',
            'evidence_quote':'original','mappings':[{'local_exchange_id':'id','field':'field','reason':'identity'}]}]}]}
    schema = audit_output_schema(contract, source_lines=[{'line_id':'x','text':'Service queries records.'}])
    datum = schema['properties']['source_data_reviews']['items']['anyOf'][0]['properties']['datums']['items']
    assert 'source_kind' in datum['required']
    assert datum['properties']['source_kind']['enum'] == ['explicit','query_semantics']
