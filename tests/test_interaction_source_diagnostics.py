"""Invalid source evidence is diagnosed; semantic support is never invented."""
from copy import deepcopy
from types import SimpleNamespace

from scene_completion.interaction_source_diagnostics import source_audit_hint


def fixture():
    return {'input': {'normal_model': {'exchanges': [{'local_id': 'read', 'requirement_layer': 'SR',
        'source_refs': [{'document': 'lab.md', 'line_start': 3, 'line_end': 5}]}]},
        'normal_source_lines': [
            {'line_id': 'lab.md:L3', 'requirement_layer': 'SR', 'source_origin': 'normal',
                'text': 'LabService calls SpecimenService.', 'source_refs': [{'document': 'lab.md', 'line_start': 3}]},
            {'line_id': 'lab.md:L4', 'requirement_layer': 'SR', 'source_origin': 'abnormal',
                'text': 'Specimen absent: reject.', 'source_refs': [{'document': 'lab.md', 'line_start': 4}]},
            {'line_id': 'customer.md:L5', 'requirement_layer': 'RR', 'source_origin': 'normal',
                'text': 'Patient opens results.', 'source_refs': [{'document': 'customer.md', 'line_start': 5}]}]}}


def test_source_hint_quotes_only_existing_bound_own_layer_positive_clauses():
    packet = fixture()
    before = deepcopy(packet)
    hint = source_audit_hint(packet, 'normal graph evidence is not its own-layer positive flow: record=read; layer=SR')
    assert 'LabService calls SpecimenService.' in hint
    assert 'Specimen absent' not in hint and 'Patient opens' not in hint
    assert 'not asserted semantic support' in hint
    assert packet == before


def test_data_hint_reports_missing_mapping_instead_of_filling_field():
    hint = source_audit_hint(fixture(), 'source datum must map an actual same-layer field')
    assert 'mappings=[] reports an omission' in hint
    assert 'never invent a field' in hint


def test_data_hint_locates_nonliteral_quote_without_rewriting_it():
    raw = {'source_data_reviews': [{'line_id': 'lab.md:L3', 'datums': [
        {'datum': 'specimen', 'direction': 'response', 'evidence_quote': 'LabService retrieves specimen.'}]}]}
    before = deepcopy(raw)
    hint = source_audit_hint(fixture(), 'source data item needs one exact original transfer datum and direction', raw)
    assert 'lab.md:L3' in hint and 'LabService calls SpecimenService.' in hint
    assert raw == before


def test_source_hint_handles_scenario_index_without_guessing_exchange():
    packet = fixture()
    packet['input']['normal_model']['normal_scenarios'] = [{
        'requirement_layer': 'SR', 'source_refs': [{'document': 'lab.md', 'line_start': 3, 'line_end': 3}]}]
    assert 'LabService calls SpecimenService.' in source_audit_hint(packet, 'quote invalid: record=0; source=original')
    assert 'LabService calls SpecimenService.' not in source_audit_hint(packet, 'quote invalid: record=10; source=original')


def test_long_source_diagnostic_keeps_literal_tail_without_supplying_corrected_quote():
    packet = fixture()
    source = 'Service writes the case record (' + 'context ' * 35 + ') and specimen record (fields include specimen_id).'
    packet['input']['normal_source_lines'][0]['text'] = source
    raw = {'source_data_reviews': [{'line_id': 'lab.md:L3', 'datums': [
        {'datum': 'specimen_id', 'direction': 'request',
         'evidence_quote': 'specimen record fields include specimen_id'}]}]}
    before = deepcopy((packet, raw))
    hint = source_audit_hint(packet, 'source data item needs one exact original transfer datum and direction', raw)
    assert 'literal_source_end' in hint and ') and specimen record (fields include specimen_id).' in hint
    assert 'received_quote' in hint and (packet, raw) == before


def test_duplicate_source_datum_hint_preserves_all_actual_transfer_positions():
    raw = {'source_data_reviews': [{'line_id': 'lab.md:L3', 'datums': [
        {'datum': 'LabService', 'direction': 'request', 'evidence_quote': 'LabService'},
        {'datum': 'LabService', 'direction': 'request', 'evidence_quote': 'LabService'}]}]}
    before = deepcopy(raw)
    hint = source_audit_hint(fixture(), 'source data item needs one exact original transfer datum and direction', raw)
    assert "'duplicate_identity': True" in hint and 'all genuine transfers' in hint
    assert 'do not invent a renamed datum' in hint.lower() and raw == before


def test_resource_inventory_hint_locates_unknown_caller_and_nonliteral_quote():
    packet = fixture()
    packet['input']['normal_model']['components'] = [{'component_id': 'svc-lab', 'layer': 'SR'}]
    raw = {'resource_operation_reviews': [{'resource_component_id': 'specimen-db', 'operations': [
        {'line_id': 'lab.md:L3', 'caller_component_id': 'LabService', 'operation': 'read',
         'evidence_quote': 'LabService queries specimen.', 'local_exchange_ids': []}]}]}
    before = deepcopy((packet, raw))
    hint = source_audit_hint(packet, 'resource operation needs a unique positive SR clause, real SR caller and exact quote', raw)
    assert 'unknown/non-SR caller ID' in hint and 'LabService calls SpecimenService.' in hint
    assert 'These facts do not certify' in hint and (packet, raw) == before


def test_long_exchange_quote_diagnostic_exposes_shared_predicate_tail_without_rewriting():
    packet = fixture()
    source = 'LabService writes patient record (' + 'field ' * 40 + ') and specimen record.'
    packet['input']['normal_source_lines'][0]['text'] = source
    raw = {'exchange_reviews': [{'local_exchange_id': 'read', 'evidence_quote': 'writes specimen record'}]}
    before = deepcopy((packet, raw))
    hint = source_audit_hint(packet, "quote invalid: record=read; received='writes specimen record'", raw)
    assert source in hint and 'do not repeat a verb' in hint
    assert (packet, raw) == before


def test_resource_quote_diagnostic_does_not_reject_valid_missing_original_caller():
    packet = fixture()
    packet['input']['normal_model']['components'] = []
    packet['input']['resource_caller_source_required'] = True
    raw = {'resource_operation_reviews': [{'resource_component_id': 'specimen-db', 'operations': [
        {'line_id': 'lab.md:L3', 'caller_component_id': '', 'caller_source_name': 'LabService',
         'operation': 'read', 'evidence_quote': 'LabService retrieves specimen.', 'local_exchange_ids': []}]}]}
    hint = source_audit_hint(packet, 'resource operation requires an exact original quote', raw)
    assert 'quote is not an exact fragment' in hint and 'unknown/non-SR caller ID' not in hint
    assert 'empty caller_component_id' in hint


def test_resource_inventory_hint_keeps_real_instantiations_without_duplicate_operation_rows():
    packet = fixture()
    packet['input']['normal_model']['components'] = [{'component_id': 'svc-lab', 'layer': 'SR'}]
    operation = {'line_id': 'lab.md:L3', 'caller_component_id': 'svc-lab', 'operation': 'read',
        'evidence_quote': 'LabService calls SpecimenService.', 'local_exchange_ids': []}
    raw = {'resource_operation_reviews': [{'resource_component_id': 'specimen-db',
        'operations': [operation, deepcopy(operation)]}]}
    hint = source_audit_hint(packet, 'resource operation needs a unique positive SR clause', raw)
    assert 'duplicate operation identity' in hint and 'distinct real instantiations' in hint.lower()


def test_contradictory_audit_hint_identifies_missing_flags_without_supplying_a_decision():
    raw = {'exchange_reviews': [
        {'local_exchange_id': 'read', 'issues': []},
        {'local_exchange_id': 'other', 'supported': True, 'issues': ['The original call is absent.']}]}
    before = deepcopy(raw)
    hint = source_audit_hint(fixture(), 'normal graph decision needs explicit flags and concrete issues', raw)
    assert "'exchange_id': 'read'" in hint and "'exchange_id': 'other'" in hint
    assert 'never discard a real defect' in hint and raw == before


def test_quote_hint_identifies_audit_array_instead_of_rejecting_all_return_evidence():
    raw = {'exchange_reviews': [{'local_exchange_id': 'read', 'evidence_quote': 'returns the result'}],
        'field_reviews': [{'local_exchange_id': 'read', 'field': 'result', 'evidence_quote': 'other evidence'}]}
    before = deepcopy(raw)
    hint = source_audit_hint(fixture(), "not positive: record=read; layer=SR; quote='returns the result'", raw)
    assert "'array': 'exchange_reviews'" in hint
    assert "'array': 'field_reviews'" not in hint
    assert 'Return guarantees can support a returned datum' in hint and raw == before


def test_prepared_diagnostic_preserves_original_native_attempt_before_validation(tmp_path, monkeypatch):
    from scene_completion.interaction_source_diagnostics import run_source_audit_diagnostics
    from scene_completion.semantic_backend import write_json, read_json
    from scene_completion.sources import fingerprint
    root = tmp_path / 'round'
    folder = root / 'batches/interaction-model-audit'
    bid = 'audit-clinic'
    packet = fixture()
    packet.update(batch_id=bid, input_hash='source-input')
    manifest = {'batches': [{'batch_id': bid, 'input_hash': 'source-input'}]}
    write_json(root / 'sources_index.json', {})
    write_json(folder / 'manifest.json', manifest)
    write_json(folder / 'packets' / (bid + '.json'), packet)
    raw = {'batch_id': bid, 'input_hash': 'source-input', 'original_payload': True}
    original_path = folder / 'attempts' / (bid + '-original.json')
    write_json(original_path, {'result': raw, 'validation_error': 'invalid quote'})
    monkeypatch.setattr('scene_completion.interaction_model_audit.model_audit_packets', lambda *args, **kwargs: manifest)
    def failing_validator(packet, result):
        result['normalized_source_refs'] = ['in-memory normalization']
        raise ValueError('invalid quote: record=read')
    monkeypatch.setattr('scene_completion.interaction_model_audit.model_audit_validator', lambda _: failing_validator)
    report, code = run_source_audit_diagnostics(SimpleNamespace(output_dir=str(root), prepare_retry=True))
    finding = report['findings'][0]
    assert code == 2 and finding['original_result_hash'] == fingerprint(raw)
    assert read_json(finding['retry_feedback_file'])['result'] == raw
    assert read_json(original_path)['result'] == raw
def test_line_inventory_diagnostic_keeps_semantic_flags_and_reports_exact_missing_sources():
    from copy import deepcopy
    from scene_completion.interaction_source_diagnostics import source_audit_hint
    packet = {'input': {'normal_model': {'exchanges': []}, 'normal_source_lines': [
        {'line_id': 'clinic.md:L1', 'text': '## Basic flow'},
        {'line_id': 'clinic.md:L2', 'text': 'RecordService reads visits.'},
        {'line_id': 'clinic.md:L3', 'text': 'Failure: visit unavailable.'}]}}
    raw = {'line_reviews': [{'line_id': 'clinic.md:L1', 'covered': True},
        {'line_id': 'clinic.md:L1', 'covered': True}, {'line_id': 'other.md:L9', 'covered': False}]}
    original = deepcopy(raw)
    hint = source_audit_hint(packet, 'normal graph audit must inspect every assigned positive flow line exactly once', raw)
    assert "'missing_line_ids': ['clinic.md:L2', 'clinic.md:L3']" in hint
    assert "'duplicate_line_ids': ['clinic.md:L1']" in hint
    assert "'unknown_line_ids': ['other.md:L9']" in hint
    assert 'RecordService reads visits.' in hint
    assert 'Failure: visit unavailable.' in hint
    assert 'no classification decision supplied' in hint
    assert raw == original


def test_guarantee_field_hint_exposes_existing_transfer_without_inventing_quote():
    packet = fixture()
    exchange = packet['input']['normal_model']['exchanges'][0]
    exchange.update(return_description='System returns the visit number, followed by status.', response_fields=['visit number'])
    raw = {'field_reviews': [{'local_exchange_id': 'read', 'field': 'visit number', 'direction': 'response',
        'supported': True, 'evidence_quote': 'System returns the visit number.'}]}
    before = deepcopy(raw)
    hint = source_audit_hint(packet, "normal graph evidence is not its own-layer positive flow: record=read; layer=RR; quote='System returns the visit number.'", raw)
    assert 'System returns the visit number, followed by status.' in hint
    assert 'not a source approval' in hint and 'preserve a concrete negative finding' in hint
    assert raw == before


def test_data_inventory_hint_reports_missing_duplicate_unknown_without_rewriting_output():
    packet = {'input': {'normal_model': {'exchanges': []}, 'normal_source_lines': [
        {'line_id': 'clinic.md:L1', 'text': 'Patient sends visitId.'},
        {'line_id': 'clinic.md:L2', 'text': 'RecordService validates access.'},
        {'line_id': 'clinic.md:L3', 'text': 'Failure: visit unavailable.'}]}}
    raw = {'source_data_reviews': [
        {'line_id': 'clinic.md:L1', 'datums': []},
        {'line_id': 'clinic.md:L1', 'datums': []},
        {'line_id': 'other.md:L9', 'datums': []}]}
    before = deepcopy(raw)
    hint = source_audit_hint(packet, 'source data coverage must independently inspect every original flow line', raw)
    assert "'missing_line_ids': ['clinic.md:L2', 'clinic.md:L3']" in hint
    assert "'duplicate_line_ids': ['clinic.md:L1']" in hint
    assert "'unknown_line_ids': ['other.md:L9']" in hint
    assert 'RecordService validates access.' in hint and 'Failure: visit unavailable.' in hint
    assert 'no transferred-datum decision supplied' in hint and 'supplies no semantic decision' in hint
    assert raw == before
