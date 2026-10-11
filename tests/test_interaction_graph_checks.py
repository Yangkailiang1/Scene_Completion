"""Ordered UI requests and RR vocabulary cannot collapse into SR schemas."""
from scene_completion.interaction_graph_checks import check_graph_anchors
from scene_completion.sources import index_sources, validate_refs


def test_local_validation_does_not_create_service_interaction(tmp_path):
    path = tmp_path / 'design.md'
    path.write_text('# RecordUpdate\n## Basic flow\n1. RecordService validates request version locally.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    refs = validate_refs([{'document': path.name, 'line_start': 3, 'line_end': 3}], index)
    model = {'use_cases': [{'use_case_id': 'RecordUpdate', 'exchanges': [{
        'local_id': 'validation', 'requirement_layer': 'SR', 'from_node': 'record', 'to_node': 'record', 'source_refs': refs}]}]}
    checked = check_graph_anchors(model, index, None)
    assert not checked['passed'] and checked['checks'][0]['code'] == 'local_service_step_as_interaction'
    assert model['use_cases'][0]['exchanges'][0]['to_node'] == 'record'
    model['use_cases'][0]['exchanges'] = []
    assert check_graph_anchors(model, index, None)['passed']


def test_same_exchange_cannot_cover_two_numbered_initiating_steps(tmp_path):
    path = tmp_path / 'requirements.md'
    path.write_text('# Library\n## Main success path\n1. Reader opens catalog.\n2. System displays books.\n3. Reader submits title.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    refs = validate_refs([{'document': path.name, 'line_start': 3, 'line_end': 5}], index)
    model = {'use_cases': [{'use_case_id': 'BrowseLibrary', 'exchanges': [
        {'local_id': 'one', 'requirement_layer': 'RR', 'source_refs': refs, 'request_fields': ['title'], 'response_fields': []}]}]}
    review = [{'use_case_id': 'BrowseLibrary', 'line_reviews': [
        {'line_id': 'requirements.md:L3', 'classification': 'request_call', 'covered': True, 'local_exchange_ids': ['one']},
        {'line_id': 'requirements.md:L5', 'classification': 'request_call', 'covered': True, 'local_exchange_ids': ['one']}]}]
    checked = check_graph_anchors(model, index, review)
    assert not checked['passed']
    assert checked['checks'][0]['code'] == 'collapsed_separate_request_steps'
    model['use_cases'][0]['exchanges'].append({**model['use_cases'][0]['exchanges'][0], 'local_id': 'query'})
    review[0]['line_reviews'][1]['local_exchange_ids'] = ['query']
    assert check_graph_anchors(model, index, review)['passed']


def test_sr_parameter_names_do_not_become_unquoted_rr_data(tmp_path):
    rr, sr = tmp_path / 'customer.md', tmp_path / 'interface.md'
    rr.write_text('# Imaging\n## Main success path\n①用户上传影像。\n', encoding='utf-8')
    sr.write_text('# API\n## Basic flow\n1. Accept imagePayload and codecVersion.\n', encoding='utf-8')
    index = index_sources([rr, sr])
    for doc, layer in zip(index['documents'], ('RR', 'SR')):
        doc['requirement_layer'] = layer
    refs = validate_refs([{'document': p.name, 'line_start': 3, 'line_end': 3} for p in (rr, sr)], index)
    exchange = {'local_id': 'upload', 'requirement_layer': 'RR', 'source_refs': refs,
        'request_fields': ['影像', 'codecVersion'], 'response_fields': []}
    model = {'use_cases': [{'use_case_id': 'UploadImage', 'exchanges': [exchange]}]}
    checked = check_graph_anchors(model, index, None)
    assert checked['checks'][0]['fields'] == ['codecVersion']
    exchange['request_fields'] = ['影像']
    assert check_graph_anchors(model, index, None)['passed']
