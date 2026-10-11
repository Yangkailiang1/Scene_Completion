"""Source-only checks detect missing graph edges without C/G/test feedback."""
import pytest


@pytest.mark.parametrize('mutation', ['valid', 'unreviewed', 'rejected_optional', 'not_optional', 'wrong_layer', 'unbound', 'wrong_field', 'abnormal'])
def test_integrated_optional_return_requires_source_and_actual_field_chain(tmp_path, mutation):
    import copy
    from scene_completion.interaction_model_audit import _field_evidence
    path = tmp_path / 'appointment.md'
    path.write_text('# Appointment\n## Basic flow\n1. Patient submits a booking.\n## Alternative flows\nA1. Optional scenario: patient changes their mind.\nReturn the booking summary.\n', encoding='utf-8')
    if mutation == 'abnormal':
        path.write_text(path.read_text(encoding='utf-8').replace('Optional scenario: patient changes their mind.',
            'Exception scenario: booking failed.'), encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    ref = lambda start, end=None: validate_refs([{'document': path.name, 'line_start': start, 'line_end': end or start}], index)
    exchange = {'local_id':'rr', 'requirement_layer':'RR', 'path_type':'main_success',
        'source_refs':ref(3) + ref(5,6), 'response_fields':['summary'], 'return_description':'Show the original booking summary on cancellation.'}
    scene = {'requirement_layer':'RR', 'scenario_type':'alternative', 'source_refs':ref(5,6)}
    lines = normal_source_lines(index['documents'][0]['chapters'][:1], index)
    data = {'sections':index['documents'][0]['chapters'][:1], 'normal_source_lines':lines,
        'normal_model':{'exchanges':[exchange], 'normal_scenarios':[scene]}}
    result = {'line_reviews':[{'line_id':path.name+':L6','covered':True,'classification':'return','local_exchange_ids':['rr']}],
        'source_data_reviews':[{'line_id':path.name+':L6','datums':[{'direction':'response',
            'evidence_quote':'Return the booking summary.', 'mappings':[{'local_exchange_id':'rr','field':'summary'}]}]}],
        'scenario_reviews':[{'scenario_index':0,'supported':True,'evidence_quote':path.read_text(encoding='utf-8').splitlines()[4],
            'source_refs':ref(5,6), 'issues':[]}], 'contract_reviews':[]}
    row = {'local_exchange_id':'rr','direction':'response','field':'summary','supported':True,
        'evidence_quote':'Return the booking summary.','source_refs':ref(6)}
    if mutation == 'unreviewed': result['scenario_reviews'] = []
    if mutation == 'rejected_optional': result['scenario_reviews'][0]['supported'] = False
    if mutation == 'not_optional': scene['scenario_type'] = 'main_success'
    if mutation == 'wrong_layer': scene['requirement_layer'] = 'SR'
    if mutation == 'unbound': exchange['source_refs'] = ref(3)
    if mutation == 'wrong_field': result['source_data_reviews'][0]['datums'][0]['mappings'][0]['field'] = 'different'
    before = copy.deepcopy(result)
    if mutation == 'valid':
        _field_evidence(row, exchange, data, result, index)
    else:
        with pytest.raises(ValueError):
            _field_evidence(row, exchange, data, result, index)
    assert result == before

from scene_completion.interaction_model_audit import normal_source_lines, model_audit_validator, contract_source_lines
from scene_completion.interaction_resources import physical_identity
from scene_completion.sources import index_sources, validate_refs


@pytest.mark.parametrize('mutation', ['valid', 'internal_state', 'unbound_promise', 'wrong_field', 'wrong_direction'])
def test_guarantee_uses_actual_return_inventory_not_description_wording(tmp_path, mutation):
    from copy import deepcopy
    from scene_completion.interaction_model_audit import _field_evidence
    path = tmp_path / 'report.md'
    path.write_text('# Inspect\n## Basic flow\n1. User opens the report.\n2. System presents the report.\n## Success guarantee\nThe displayed report contains the count.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    def ref(n):
        return validate_refs([{'document': path.name, 'line_start': n, 'line_end': n}], index)
    sections = index['documents'][0]['chapters'][:1]
    exchange = {'local_id': 'report', 'requirement_layer': 'RR', 'source_refs': ref(3) + ref(4) + ref(6),
        'return_description': 'A report is presented to the user.', 'response_fields': ['count', 'timestamp']}
    data = {'sections': sections, 'normal_source_lines': normal_source_lines(sections, index)}
    row = {'local_exchange_id': 'report', 'direction': 'response', 'field': 'count', 'supported': True,
        'source_refs': ref(6), 'evidence_quote': 'The displayed report contains the count.'}
    result = {'line_reviews': [{'line_id': 'report.md:L4', 'classification': 'return',
        'covered': True, 'local_exchange_ids': ['report']}], 'source_data_reviews': [
        {'line_id': 'report.md:L4', 'datums': [{'datum': 'report', 'direction': 'response',
            'evidence_quote': 'System presents the report.',
            'mappings': [{'local_exchange_id': 'report', 'field': 'count'}]}]}]}
    if mutation == 'internal_state':
        result['line_reviews'][0]['classification'] = 'local_operation'
    elif mutation == 'unbound_promise':
        exchange['source_refs'] = ref(3) + ref(4)
    elif mutation == 'wrong_field':
        result['source_data_reviews'][0]['datums'][0]['mappings'][0]['field'] = 'timestamp'
    elif mutation == 'wrong_direction':
        result['source_data_reviews'][0]['datums'][0]['direction'] = 'request'
    original = deepcopy(result)
    if mutation == 'valid':
        _field_evidence(row, exchange, data, result, index)
    else:
        with pytest.raises(ValueError, match='positive flow'):
            _field_evidence(row, exchange, data, result, index)
    assert result == original


def fixture(tmp_path):
    path = tmp_path / 'design.md'
    path.write_text('# S-Inventory\n## Basic flow\n1. StockService reads warehouse.item 表.\n2. StockService writes warehouse.stock 表.\n3. Return the current stock.\n## Alternative flows\nA1. A missing item is handled with HTTP 200.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    sections = index['documents'][0]['chapters'][:1]
    def ref(line):
        return validate_refs([{'document': path.name, 'line_start': line, 'line_end': line}], index)
    model = {'exchanges': [{'local_id': 'read', 'requirement_layer': 'SR', 'source_refs': ref(3)}],
        'normal_scenarios': [{'requirement_layer': 'SR', 'scenario_type': 'alternative', 'source_refs': ref(7)}]}
    packet = {'input': {'use_case_id': 'InventoryUpdate', 'sections': sections, 'normal_source_lines': normal_source_lines(sections, index),
        'normal_model': model, 'model_batch_id': 'model-0', 'model_result_hash': 'hash'}}
    rows = [{'line_id': row['line_id'], 'classification': 'context', 'covered': True,
        'local_exchange_ids': [], 'reason': 'heading retained in source', 'issues': []}
        for row in packet['input']['normal_source_lines']]
    for row in rows:
        if row['line_id'].endswith(':L3'):
            row.update(classification='request_call', local_exchange_ids=['read'])
        if row['line_id'].endswith(':L4'):
            row.update(classification='request_call', covered=False, issues=['Explicit resource write exchange is absent'])
        if row['line_id'].endswith(':L5'):
            row.update(classification='return', local_exchange_ids=['read'], reason='response field')
    result = {'line_reviews': rows, 'exchange_reviews': [{'local_exchange_id': 'read', 'supported': True,
        'source_refs': ref(3), 'evidence_quote': '1. StockService reads warehouse.item 表.', 'issues': []}],
        'scenario_reviews': [{'scenario_index': 0, 'supported': False, 'source_refs': ref(7),
            'evidence_quote': 'A1. A missing item is handled with HTTP 200.', 'issues': ['Failure is not an ordinary optional success']}],
        'omitted_calls': [{'caller': 'StockService', 'callee': 'warehouse.stock', 'operation': 'write stock',
            'requirement_layer': 'SR', 'source_refs': ref(4), 'evidence_quote': '2. StockService writes warehouse.stock 表.'}]}
    return index, packet, result, ref


def test_source_only_audit_preserves_missing_resource_call_and_abnormal_normal_entry(tmp_path):
    index, packet, result, _ = fixture(tmp_path)
    checked = model_audit_validator(index)(packet, result)[0]
    assert not checked['passed']
    assert checked['omitted_calls'][0]['callee'] == 'warehouse.stock'
    assert not checked['scenario_reviews'][0]['supported']
    assert not {'scenarios', 'generated_scenarios', 'test_scenarios'} & packet['input'].keys()


def test_actual_retry_worker_receives_literal_source_diagnostic_without_approving_model(tmp_path):
    from copy import deepcopy
    from scene_completion.semantic_backend import run_agent_packets, read_json, write_json
    index, packet, result, _ = fixture(tmp_path)
    packet.update(stage='interaction-model-audit', batch_id='lab-audit', input_hash='lab-source-input')
    packet['input']['source_data_coverage_required'] = True
    result['source_data_reviews'] = [{'line_id': line['line_id'], 'reason': 'Original flow inspected', 'datums': []}
        for line in packet['input']['normal_source_lines']]
    source = next(r for r in result['source_data_reviews'] if r['line_id'].endswith(':L5'))
    source['datums'] = [{'datum': 'stock', 'direction': 'response', 'evidence_quote': 'Return stock.', 'mappings': []}]
    folder = tmp_path / 'audit-batches'
    write_json(folder / 'packets/lab-audit.json', packet)
    write_json(folder / 'manifest.json', {'batches': [{'batch_id': 'lab-audit', 'input_hash': 'lab-source-input'}]})
    seen = []
    class Client:
        config = {'max_concurrency': 1, 'semantic_max_attempts': 2}
        def model(self, kind):
            return 'ecnu-max'
        def agent(self, request):
            seen.append(deepcopy(request))
            value = deepcopy(result)
            if len(seen) == 2:
                next(r for r in value['source_data_reviews'] if r['line_id'].endswith(':L5'))['datums'][0]['evidence_quote'] = 'Return the current stock.'
            return value
    state = run_agent_packets(folder, Client(), model_audit_validator(index))
    assert state['complete'] and len(seen) == 2
    assert 'literal_source_start' in seen[1]['validation_feedback']
    assert 'Return the current stock.' in seen[1]['validation_feedback']
    assert seen[1]['input'] == packet['input']
    assert list((folder / 'attempts').glob('*.json'))
    checked = model_audit_validator(index)(packet, read_json(folder / 'results/lab-audit.json'))[0]
    assert not checked['passed']  # Valid JSON still reports the genuine source/model defects.


@pytest.mark.parametrize('mapping', ['present', 'missing', 'unknown_field', 'wrong_layer', 'unbound'])
def test_independent_source_data_inventory_detects_omission_even_when_field_universe_is_empty(tmp_path, mapping):
    index, packet, result, ref = fixture(tmp_path)
    packet['input']['source_data_coverage_required'] = True
    with pytest.raises(ValueError, match='every original flow line'):
        model_audit_validator(index)(packet, result)
    result['source_data_reviews'] = [{'line_id': line['line_id'], 'reason': 'No transferred data on this context line',
        'datums': []} for line in packet['input']['normal_source_lines']]
    source = next(row for row in result['source_data_reviews'] if row['line_id'].endswith(':L5'))
    source.update(reason='Original stock is returned', datums=[{'datum': 'current stock', 'direction': 'response',
        'evidence_quote': 'Return the current stock.', 'mappings': []}])
    exchange = packet['input']['normal_model']['exchanges'][0]
    if mapping != 'missing':
        source['datums'][0]['mappings'] = [{'local_exchange_id': 'read', 'field': 'stock',
            'reason': 'Current stock is the response datum at this read'}]
        exchange['response_fields'] = ['stock']
        if mapping != 'unbound':
            exchange['source_refs'] += ref(5)
    if mapping == 'unknown_field':
        exchange['response_fields'] = []
    if mapping == 'wrong_layer':
        exchange['requirement_layer'] = 'RR'
        for row in result['line_reviews']:
            row.update(local_exchange_ids=[], classification='context')
    if mapping in {'unknown_field', 'wrong_layer'}:
        with pytest.raises(ValueError, match='actual same-layer field'):
            model_audit_validator(index)(packet, result)
    else:
        checked = model_audit_validator(index)(packet, result)[0]
        codes = {f['code'] for f in checked['tool_findings']}
        assert ('source_transfer_data_omitted' in codes) == (mapping == 'missing')
        assert ('source_data_mapping_without_anchor' in codes) == (mapping == 'unbound')


def test_abnormal_branch_cannot_populate_normal_source_data_inventory(tmp_path):
    index, packet, result, _ = fixture(tmp_path)
    packet['input']['source_data_coverage_required'] = True
    result['source_data_reviews'] = [{'line_id': line['line_id'], 'reason': 'Retain source context', 'datums': []}
        for line in packet['input']['normal_source_lines']]
    row = next(row for row in result['source_data_reviews'] if row['line_id'].endswith(':L7'))
    row['datums'] = [{'datum': 'missing item', 'direction': 'response',
        'evidence_quote': 'missing item', 'mappings': []}]
    next(row for row in result['line_reviews'] if row['line_id'].endswith(':L7'))['classification'] = 'abnormal_context'
    with pytest.raises(ValueError, match='abnormal source'):
        model_audit_validator(index)(packet, result)


@pytest.mark.parametrize('invalid_member', [False, True])
def test_source_defined_return_collection_can_map_to_actual_member_fields(tmp_path, invalid_member):
    index, packet, result, ref = fixture(tmp_path)
    source_path = tmp_path / 'design.md'
    source_path.write_text(source_path.read_text(encoding='utf-8').replace(
        'Return the current stock.', 'Return stock report with quantity and warehouse.'), encoding='utf-8')
    index = index_sources([source_path])
    index['documents'][0]['requirement_layer'] = 'SR'
    packet['input']['normal_source_lines'] = normal_source_lines(packet['input']['sections'], index)
    packet['input']['source_data_coverage_required'] = True
    exchange = packet['input']['normal_model']['exchanges'][0]
    exchange['response_fields'] = ['quantity', 'warehouse']
    exchange['source_refs'] += ref(5)
    result['source_data_reviews'] = [{'line_id': line['line_id'], 'reason': 'Original line inspected', 'datums': []}
        for line in packet['input']['normal_source_lines']]
    row = next(r for r in result['source_data_reviews'] if r['line_id'].endswith(':L5'))
    row['datums'] = [{'datum': 'stock report', 'direction': 'response',
        'evidence_quote': 'Return stock report with quantity and warehouse.',
        'mappings': [{'local_exchange_id': 'read', 'field': field,
            'reason': 'Original return defines this member of the same stock-report collection'}
            for field in ('quantity', 'inventedWrapper' if invalid_member else 'warehouse')]}]
    if invalid_member:
        with pytest.raises(ValueError, match='actual same-layer field'):
            model_audit_validator(index)(packet, result)
    else:
        checked = model_audit_validator(index)(packet, result)[0]
        assert not any(f['code'] in {'source_transfer_data_omitted', 'source_data_mapping_without_anchor'}
            for f in checked['tool_findings'])
        assert exchange['response_fields'] == ['quantity', 'warehouse']


def test_contract_audit_rejects_exception_rewritten_as_positive_rule_and_missing_review(tmp_path):
    index, packet, result, ref = fixture(tmp_path)
    exchange = packet['input']['normal_model']['exchanges'][0]
    exchange['contracts'] = [{'rule': 'item must exist', 'source_refs': ref(7)}]
    with pytest.raises(ValueError, match='every bound rule'):
        model_audit_validator(index)(packet, result)
    result['contract_reviews'] = [{'local_exchange_id': 'read', 'contract_kind': 'contracts', 'contract_index': 0,
        'supported': True, 'evidence_quote': 'A1. A missing item is handled with HTTP 200.', 'source_refs': ref(7), 'issues': []}]
    with pytest.raises(ValueError, match='failure branch'):
        model_audit_validator(index)(packet, result)
    result['contract_reviews'][0].update(supported=False, issues=['Failure context cannot establish a positive contract'])
    checked = model_audit_validator(index)(packet, result)[0]
    assert not checked['passed'] and not checked['contract_reviews'][0]['supported']


def test_contract_audit_accepts_original_positive_normal_clause(tmp_path):
    index, packet, result, ref = fixture(tmp_path)
    document = index['documents'][0]
    document['text'] = document['text'].replace('3. Return the current stock.', '3. Return the current stock; quantity is nonnegative.')
    packet['input']['normal_model']['exchanges'][0]['contracts'] = [{'rule': 'quantity is nonnegative', 'source_refs': ref(5)}]
    result['contract_reviews'] = [{'local_exchange_id': 'read', 'contract_kind': 'contracts', 'contract_index': 0,
        'supported': True, 'evidence_quote': 'quantity is nonnegative.', 'source_refs': ref(5), 'issues': []}]
    assert model_audit_validator(index)(packet, result)[0]['contract_reviews'][0]['supported']


def test_positive_precondition_supports_contract_without_creating_call(tmp_path):
    index, packet, result, ref = fixture(tmp_path)
    document = index['documents'][0]
    document['text'] = document['text'].replace('## Basic flow', '## Preconditions')
    document['text'] = document['text'].replace('1. StockService reads warehouse.item 表.', '1. warehouse.item quantity is nonnegative.')
    packet['input']['normal_model']['exchanges'][0]['contracts'] = [{'rule': 'quantity is nonnegative', 'source_refs': ref(3)}]
    result['contract_reviews'] = [{'local_exchange_id': 'read', 'contract_kind': 'contracts', 'contract_index': 0,
        'supported': True, 'evidence_quote': 'quantity is nonnegative.', 'source_refs': ref(3), 'issues': []}]
    result['exchange_reviews'][0].update(supported=False, evidence_quote='quantity is nonnegative.',
        issues=['Precondition establishes a legal rule, not an initiating call'])
    result['omitted_calls'] = []
    checked = model_audit_validator(index)(packet, result)[0]
    assert checked['contract_reviews'][0]['supported']
    assert not checked['passed'] and not checked['exchange_reviews'][0]['supported']


def test_bound_global_contract_is_auditable_without_creating_global_calls(tmp_path):
    _, packet, result, _ = fixture(tmp_path)
    global_path = tmp_path / 'shared-contract.md'
    global_path.write_text('# Stock contract\n## Preconditions\nquantity is nonnegative.\n', encoding='utf-8')
    index = index_sources([tmp_path / 'design.md', global_path])
    for document in index['documents']:
        document['requirement_layer'] = 'SR'
    refs = validate_refs([{'document': global_path.name, 'line_start': 3, 'line_end': 3}], index)
    packet['input']['normal_model']['exchanges'][0]['contracts'] = [{'rule': 'quantity is nonnegative', 'source_refs': refs}]
    packet['input']['contract_source_lines'] = contract_source_lines(packet['input']['normal_model'], index)
    result['contract_reviews'] = [{'local_exchange_id': 'read', 'contract_kind': 'contracts', 'contract_index': 0,
        'supported': True, 'evidence_quote': 'quantity is nonnegative.', 'source_refs': refs, 'issues': []}]
    checked = model_audit_validator(index)(packet, result)[0]
    assert checked['contract_reviews'][0]['supported']
    assert all('shared-contract.md' not in row['line_id'] for row in packet['input']['normal_source_lines'])
    packet['input']['contract_source_lines'][0]['text'] = 'replacement rule'
    with pytest.raises(ValueError, match='source text differs'):
        model_audit_validator(index)(packet, result)


def test_original_return_datum_with_missing_exchange_anchor_is_model_gap(tmp_path):
    from scene_completion.interaction_model_audit import responsibility_universe
    path = tmp_path / 'clinic.md'
    path.write_text('# Consult\n## Basic flow\n1. Patient opens visit page.\n2. System returns available visits.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    sections = index['documents'][0]['chapters'][:1]
    def ref(line):
        return validate_refs([{'document': path.name, 'line_start': line, 'line_end': line}], index)
    model = {'exchanges': [{'local_id': 'open', 'requirement_layer': 'RR', 'source_refs': ref(3),
        'request_fields': [], 'response_fields': ['visits']}], 'normal_scenarios': []}
    packet = {'input': {'use_case_id': 'Consult', 'sections': sections, 'normal_model': model,
        'normal_source_lines': normal_source_lines(sections, index), 'model_batch_id': 'model', 'model_result_hash': 'hash'}}
    result = {'line_reviews': [{'line_id': r['line_id'], 'classification': 'context', 'covered': True,
        'local_exchange_ids': [], 'reason': 'Original flow retained', 'issues': []} for r in packet['input']['normal_source_lines']],
        'exchange_reviews': [{'local_exchange_id': 'open', 'supported': True, 'source_refs': ref(3),
            'evidence_quote': 'Patient opens visit page.', 'issues': []}], 'scenario_reviews': [], 'omitted_calls': [],
        'field_reviews': [{'local_exchange_id': 'open', 'direction': 'response', 'field': 'visits', 'supported': True,
            'source_refs': ref(4), 'evidence_quote': 'System returns available visits.', 'issues': []}],
        'responsibility_reviews': [{**r, 'applicable': False, 'correctly_modeled': True, 'reason': 'No mapped business service role',
            'mapped_sr_local_ids': [], 'source_refs': ref(3), 'evidence_quote': 'Patient opens visit page.', 'issues': []}
            for r in responsibility_universe(model)]}
    checked = model_audit_validator(index)(packet, result)[0]
    assert not checked['passed'] and checked['tool_findings'][0]['code'] == 'rr_field_source_not_bound'
    assert checked['field_reviews'][0]['supported']
    model['exchanges'][0]['source_refs'] += ref(4)
    assert model_audit_validator(index)(packet, result)[0]['passed']


def test_positive_role_review_cannot_hide_different_real_sr_mapping(tmp_path):
    from scene_completion.interaction_model_audit import responsibility_universe
    rr, sr = tmp_path / 'clinic.md', tmp_path / 'design.md'
    rr.write_text('# Consult\n## Basic flow\n1. System queries available visits.\n', encoding='utf-8')
    sr.write_text('# Visit query\n## Basic flow\n1. ClinicAPI calls VisitService.\n2. VisitService reads visit records.\n', encoding='utf-8')
    index = index_sources([rr, sr])
    for document, layer in zip(index['documents'], ('RR', 'SR')):
        document['requirement_layer'] = layer
    def ref(path, line):
        return validate_refs([{'document': path.name, 'line_start': line, 'line_end': line}], index)
    rr_ref = ref(rr, 3)
    model = {'exchanges': [{'local_id': 'rr', 'requirement_layer': 'RR', 'source_refs': rr_ref,
        'business_service_roles': [{'service_type': 'query_retrieval', 'mapped_sr_local_ids': ['service']}]}]
        + [{'local_id': eid, 'requirement_layer': 'SR', 'parent_rr_local_id': 'rr', 'source_refs': ref(sr, line)}
            for eid, line in (('service', 3), ('records', 4))], 'normal_scenarios': []}
    packet = {'input': {'use_case_id': 'Consult', 'sections': [d['chapters'][0] for d in index['documents']],
        'normal_model': model, 'normal_source_lines': [], 'model_batch_id': 'model', 'model_result_hash': 'hash'}}
    quotes = {'rr': 'System queries available visits.', 'service': 'ClinicAPI calls VisitService.', 'records': 'VisitService reads visit records.'}
    result = {'line_reviews': [], 'scenario_reviews': [], 'omitted_calls': [],
        'exchange_reviews': [{'local_exchange_id': e['local_id'], 'supported': True, 'issues': [],
            'source_refs': e['source_refs'], 'evidence_quote': quotes[e['local_id']]} for e in model['exchanges']],
        'responsibility_reviews': [{**r, 'applicable': r['service_type'] == 'query_retrieval', 'correctly_modeled': True,
            'source_refs': rr_ref, 'evidence_quote': quotes['rr'], 'reason': 'Original role decision', 'issues': [],
            'mapped_sr_local_ids': ['service', 'records'] if r['service_type'] == 'query_retrieval' else []}
            for r in responsibility_universe(model)]}
    checked = model_audit_validator(index)(packet, result)[0]
    assert not checked['passed'] and checked['tool_findings'][0]['code'] == 'rr_role_mapping_disagrees'
    assert all(r['correctly_modeled'] for r in checked['responsibility_reviews'])
    model['exchanges'][0]['business_service_roles'][0]['mapped_sr_local_ids'] += ['records']
    assert model_audit_validator(index)(packet, result)[0]['passed']


@pytest.mark.parametrize('binding', ['explicit_return', 'positive_contract', 'unbound_promise', 'exception_fallback'])
def test_rr_transfer_contract_supports_data_but_never_creates_call(tmp_path, binding):
    from scene_completion.interaction_model_audit import responsibility_universe
    path = tmp_path / 'clinic.md'
    path.write_text('# Consult\n## Basic flow\n1. Patient submits an application.\n## Success guarantee\nSystem returns the application number.\n', encoding='utf-8')
    if binding == 'exception_fallback':
        path.write_text(path.read_text(encoding='utf-8').replace('## Success guarantee', '## Exception flow'), encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    def ref(number):
        return validate_refs([{'document': path.name, 'line_start': number, 'line_end': number}], index)
    quote = 'System returns the application number.'
    exchange = {'local_id': 'application', 'requirement_layer': 'RR', 'source_refs': ref(3) + ref(5),
        'request_fields': [], 'response_fields': ['application number']}
    if binding in {'explicit_return', 'exception_fallback'}:
        exchange['return_description'] = quote
    if binding == 'positive_contract':
        exchange['response_contracts'] = [{'rule': quote, 'source_refs': ref(5)}]
    model = {'exchanges': [exchange], 'normal_scenarios': []}
    packet = {'input': {'use_case_id': 'Consult', 'sections': index['documents'][0]['chapters'][:1],
        'normal_source_lines': [], 'normal_model': model, 'model_batch_id': 'model', 'model_result_hash': 'hash'}}
    result = {'line_reviews': [], 'exchange_reviews': [{'local_exchange_id': 'application', 'supported': True,
        'source_refs': ref(3), 'evidence_quote': 'Patient submits an application.', 'issues': []}],
        'scenario_reviews': [], 'omitted_calls': [],
        'field_reviews': [{'local_exchange_id': 'application', 'direction': 'response', 'field': 'application number',
            'supported': True, 'source_refs': ref(5), 'evidence_quote': quote, 'issues': []}],
        'responsibility_reviews': [{**r, 'applicable': False, 'correctly_modeled': True,
            'reason': 'No service role evidenced', 'mapped_sr_local_ids': [], 'issues': [],
            'source_refs': ref(3), 'evidence_quote': 'Patient submits an application.'} for r in responsibility_universe(model)]}
    if binding == 'positive_contract':
        result['contract_reviews'] = [{'local_exchange_id': 'application', 'contract_kind': 'response_contracts',
            'contract_index': 0, 'supported': True, 'source_refs': ref(5), 'evidence_quote': quote, 'issues': []}]
    if binding in {'unbound_promise', 'exception_fallback'}:
        with pytest.raises(ValueError, match='positive flow'):
            model_audit_validator(index)(packet, result)
    else:
        assert model_audit_validator(index)(packet, result)[0]['passed']
    # A success guarantee can support data on an existing exchange; it cannot
    # replace the actual initiating clause, regardless of that field outcome.
    result['exchange_reviews'][0].update(source_refs=ref(5), evidence_quote=quote)
    with pytest.raises(ValueError, match='positive flow'):
        model_audit_validator(index)(packet, result)


@pytest.mark.parametrize('kind', ['exchange', 'rejected_scenario'])
def test_audit_quote_must_be_one_original_line_even_with_real_multiline_source(tmp_path, kind):
    index, packet, result, ref = fixture(tmp_path)
    row = result['exchange_reviews'][0] if kind == 'exchange' else result['scenario_reviews'][0]
    row['source_refs'] = ref(3) + ref(4)
    row['evidence_quote'] = '1. StockService reads warehouse.item 表.\n2. StockService writes warehouse.stock 表.'
    with pytest.raises(ValueError, match='one exact contiguous original line'):
        model_audit_validator(index)(packet, result)


def test_audit_cannot_approve_explicit_exception_as_optional(tmp_path):
    index, packet, result, ref = fixture(tmp_path)
    index['documents'][0]['text'] = index['documents'][0]['text'].replace(
        'A1. A missing item is handled with HTTP 200.', 'A1. Exception scenario: missing item, HTTP 200.')
    row = result['scenario_reviews'][0]
    row.update(supported=True, issues=[], evidence_quote='Exception scenario: missing item, HTTP 200.')
    with pytest.raises(ValueError, match='own-layer positive flow'):
        model_audit_validator(index)(packet, result)


@pytest.mark.parametrize('mutation', ['missing_line', 'foreign_exchange', 'wrong_layer', 'exception_omission', 'missing_scenario'])
def test_model_audit_cannot_skip_or_fake_positive_evidence(tmp_path, mutation):
    index, packet, result, ref = fixture(tmp_path)
    if mutation == 'missing_line':
        result['line_reviews'].pop()
    elif mutation == 'foreign_exchange':
        result['line_reviews'][1]['local_exchange_ids'] = ['made-up']
    elif mutation == 'wrong_layer':
        packet['input']['normal_model']['exchanges'][0]['requirement_layer'] = 'RR'
    elif mutation == 'exception_omission':
        result['omitted_calls'][0].update(source_refs=ref(7), evidence_quote='A1. A missing item is handled with HTTP 200.')
    else:
        result['scenario_reviews'] = []
    with pytest.raises(ValueError):
        model_audit_validator(index)(packet, result)


def test_structural_source_check_blocks_false_coverage_without_rewriting_raw_review(tmp_path):
    index, packet, result, _ = fixture(tmp_path)
    row = next(r for r in result['line_reviews'] if r['line_id'].endswith(':L4'))
    row.update(covered=True, issues=[], local_exchange_ids=['read'])
    checked = model_audit_validator(index)(packet, result)[0]
    assert row['covered'] is True and row['issues'] == []
    assert not checked['passed']
    assert checked['tool_findings'][0]['code'] == 'claimed_call_without_source_anchor'
    assert checked['tool_findings'][0]['line_id'] == 'design.md:L4'


def test_physical_alias_resolution_requires_cited_literal_table_identity(tmp_path):
    index, _, _, ref = fixture(tmp_path)
    node = {'name': 'warehouse.item 表', 'kind': 'internal_database', 'source_refs': ref(3)}
    name, proof = physical_identity(node, index)
    bare = physical_identity({**node, 'name': 'warehouse.item'}, index)
    assert name == bare[0] == 'warehouse.item' and proof == bare[1]
    assert proof['origin'] == 'internal' and proof['evidence_quote'] == 'warehouse.item 表'
    assert physical_identity({**node, 'source_refs': ref(5)}, index) == ('warehouse.item 表', None)
    external = physical_identity({**node, 'kind': 'external_database'}, index)
    assert external[1]['origin'] != proof['origin']
    assert physical_identity({**node, 'name': 'another.item 表'}, index)[1] is None
    # A qualified resource is not merged with another database's equally named table.
    assert name != 'another.item'


def test_unqualified_resource_does_not_guess_database_namespace(tmp_path):
    path = tmp_path / 'sr.md'
    path.write_text('# Spec\n## Basic flow\nRead item 表, east.item 表 and west.item 表.\n', encoding='utf-8')
    index = index_sources([path])
    node = {'name': 'item 表', 'kind': 'internal_database',
        'source_refs': validate_refs([{'document': path.name, 'line_start': 3, 'line_end': 3}], index)}
    assert physical_identity(node, index) == ('item 表', None)
    assert physical_identity({**node, 'name': 'east.item 表'}, index)[0] == 'east.item'


def test_merge_reuses_evidenced_table_but_preserves_origin_and_document_scope(tmp_path):
    from scene_completion.interaction_cli import merge_model
    paths = [tmp_path / name for name in ('east.md', 'west.md')]
    for path in paths:
        path.write_text('# Resource\n## Basic flow\nRead asset 表.\n', encoding='utf-8')
    index = index_sources(paths)
    def extraction(uc, name, kind, document):
        return {'use_case_id': uc, 'use_case_name': uc, 'components': [{'component_id': 'resource', 'name': name,
            'kind': kind, 'layer': 'AR', 'source_refs': validate_refs([{'document': document, 'line_start': 3, 'line_end': 3}], index)}],
            'exchanges': [], 'normal_scenarios': [], 'use_case_hierarchy': [], 'implementation_references': [], 'pending_details': [], 'model_gaps': []}
    rows = [extraction('first', 'asset', 'internal_database', 'east.md'),
        extraction('alias', 'asset 表', 'internal_database', 'east.md'),
        extraction('external', 'asset', 'external_database', 'east.md'),
        extraction('other', 'asset', 'internal_database', 'west.md')]
    merged = merge_model(rows, {'use_cases': [{'use_case_id': r['use_case_id']} for r in rows]}, index)
    assert len(merged['nodes']) == 3
    same = next(n for n in merged['nodes'] if set(n.get('source_aliases', [])) == {'asset', 'asset 表'})
    assert same['physical_identity']['documents'] == ['east.md']


def test_same_system_name_preserves_human_ui_and_external_receiver_roles():
    from scene_completion.interaction_cli import merge_model
    def extraction(uc, role):
        return {'use_case_id': uc, 'use_case_name': uc, 'components': [{'component_id': 'boundary',
            'name': 'Shared application', 'kind': 'frontend_ui', 'layer': 'RR', 'boundary_role': role, 'source_refs': []}],
            'exchanges': [], 'normal_scenarios': [], 'use_case_hierarchy': [], 'implementation_references': [], 'pending_details': [], 'model_gaps': []}
    rows = [extraction('human-operation', 'ui'), extraction('external-event', 'receiver')]
    model = merge_model(rows, {'use_cases': [{'use_case_id': r['use_case_id']} for r in rows]}, {'documents': []})
    assert len(model['nodes']) == 2
    assert {n['boundary_role'] for n in model['nodes']} == {'ui', 'receiver'}
    assert len({n['node_id'] for n in model['nodes']}) == 2


def test_unlabelled_optional_body_cannot_escape_source_line_audit(tmp_path):
    path = tmp_path / 'clinic.md'
    path.write_text('# Consult\n## Basic flow\n1. ScheduleAPI reads visits.\n## Alternative flows\nOptional flow: patient requests a printed summary.\n2. ScheduleAPI calls PrintService.\n3. Exception scenario: printer disconnected.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    sections = index['documents'][0]['chapters'][:1]
    lines = normal_source_lines(sections, index)
    assert any(v['line_id'] == 'clinic.md:L6' and v['source_origin'] == 'branch' for v in lines)
    assert any(v['line_id'] == 'clinic.md:L7' for v in lines)
    packet = {'input': {'use_case_id': 'Consult', 'sections': sections, 'normal_source_lines': lines,
        'normal_model': {'exchanges': [], 'normal_scenarios': []}, 'model_batch_id': 'model', 'model_result_hash': 'hash'}}
    result = {'line_reviews': [{'line_id': v['line_id'], 'classification': 'abnormal_context' if v['line_id'].endswith('L7') else 'context',
        'covered': True, 'local_exchange_ids': [], 'issues': [], 'reason': 'Retained source context'} for v in lines],
        'exchange_reviews': [], 'scenario_reviews': [], 'omitted_calls': []}
    missing = next(r for r in result['line_reviews'] if r['line_id'].endswith('L6'))
    missing.update(covered=False, classification='request_call', issues=['Optional PrintService call missing'], reason='Actual positive optional request is omitted')
    assert not model_audit_validator(index)(packet, result)[0]['passed']
    abnormal = next(r for r in result['line_reviews'] if r['line_id'].endswith('L7'))
    abnormal['classification'] = 'ordinary_optional'
    with pytest.raises(ValueError, match='abnormal audit context'):
        model_audit_validator(index)(packet, result)


def test_rr_five_role_audit_blocks_missing_category_and_false_mapping(tmp_path):
    from scene_completion.interaction_model_audit import responsibility_universe
    path = tmp_path / 'clinic.md'
    path.write_text('# Consult\n## Basic flow\n1. System queries the available visits.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    sections = index['documents'][0]['chapters'][:1]
    refs = validate_refs([{'document': path.name, 'line_start': 3, 'line_end': 3}], index)
    exchange = {'local_id': 'rr', 'requirement_layer': 'RR', 'source_refs': refs, 'business_service_roles': []}
    packet = {'input': {'use_case_id': 'Consult', 'sections': sections, 'normal_source_lines': [],
        'normal_model': {'exchanges': [exchange], 'normal_scenarios': []}, 'model_batch_id': 'model', 'model_result_hash': 'hash'}}
    result = {'line_reviews': [], 'exchange_reviews': [{'local_exchange_id': 'rr', 'supported': True,
        'source_refs': refs, 'evidence_quote': 'System queries the available visits.', 'issues': []}],
        'scenario_reviews': [], 'omitted_calls': []}
    with pytest.raises(ValueError, match='all five categories'):
        model_audit_validator(index)(packet, result)
    result['responsibility_reviews'] = [{**u, 'applicable': False, 'correctly_modeled': True,
        'source_refs': refs, 'evidence_quote': 'System queries the available visits.', 'reason': 'No such role in this request',
        'mapped_sr_local_ids': [], 'issues': []} for u in responsibility_universe(packet['input']['normal_model'])]
    query = next(r for r in result['responsibility_reviews'] if r['service_type'] == 'query_retrieval')
    query.update(applicable=True, correctly_modeled=False, issues=['Query role and its SR expansion are missing'], reason='Positive query clause needs a role')
    assert not model_audit_validator(index)(packet, result)[0]['passed']
    query.update(correctly_modeled=True, issues=[], mapped_sr_local_ids=['invented'])
    with pytest.raises(ValueError, match='real SR expansions'):
        model_audit_validator(index)(packet, result)
