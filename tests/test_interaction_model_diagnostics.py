"""Portable structural feedback identifies roles without inventing calls."""
from argparse import Namespace

import pytest

from scene_completion.interaction_model_diagnostics import structural_diagnostics, run_model_diagnostics
from scene_completion.semantic_backend import read_json, write_json


def test_component_reference_diagnostic_shows_literal_positions_without_editing_model(tmp_path):
    import copy
    from scene_completion.sources import index_sources
    from scene_completion.interaction_model_diagnostics import component_identity_diagnostics
    path = tmp_path / 'clinic.md'
    path.write_text('# VISIT\n## Basic flow\n1. RecordService reads visit 表.\n2. System validates image URLs.\n## Exception scenario\n3. visit 表 is unavailable.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    raw = {'components': [{'component_id': 'visits', 'name': 'visit 表', 'layer': 'SR',
        'source_refs': [{'document': path.name, 'line_start': 4, 'line_end': 4}]}]}
    before = copy.deepcopy(raw)
    packet = {'input': {'sections': [{'document': path.name, 'line_start': 1, 'line_end': 6}]}}
    error = 'component name must quote its own original source, not an architecture hint or invented alias: visit 表'
    row = component_identity_diagnostics(raw, packet, index, error)[0]
    assert row['bound_original_lines'][0]['line'] == 4
    assert [v['line'] for v in row['literal_original_matches']] == [3]
    assert raw == before
    assert not component_identity_diagnostics(raw, packet, index, 'another validation error')


def test_diagnostic_validation_cannot_mutate_original_attempt_or_feedback(tmp_path, monkeypatch):
    from scene_completion import interaction_batches
    from scene_completion.sources import fingerprint
    def reject(packet, raw):
        raw['components'].append({'component_id': 'changed'})
        raise ValueError('missing SR parent')
    monkeypatch.setattr(interaction_batches, 'model_validator', lambda index: reject)
    folder = tmp_path / 'batches/interaction-model'
    write_json(tmp_path / 'sources_index.json', {'documents': []})
    write_json(folder / 'manifest.json', {'batches': [{'batch_id': 'normal-1'}]})
    write_json(folder / 'packets/normal-1.json', {'input_hash': 'current', 'input': {'sections': []}})
    raw = {'batch_id': 'normal-1', 'input_hash': 'current', 'components': [
        {'component_id': 'service', 'kind': 'internal_service'}], 'exchanges': [
        {'local_id': 'read', 'requirement_layer': 'SR', 'from_component_id': 'service', 'to_component_id': 'resource'}]}
    original = {'result': raw}
    path = folder / 'attempts/normal-1-original.json'
    write_json(path, original)
    report, _ = run_model_diagnostics(Namespace(output_dir=str(tmp_path), prepare_retry=True))
    finding = report['findings'][0]
    feedback = read_json(finding['retry_feedback_file'])
    assert finding['original_result_hash'] == fingerprint(raw)
    assert feedback['result'] == raw and read_json(path) == original


def test_missing_entry_and_wrong_boundary_are_explained_for_unrelated_project():
    raw = {'components': [
        {'component_id': 'ui', 'kind': 'frontend_ui', 'boundary_role': 'ui'},
        {'component_id': 'entry', 'kind': 'abstract_service', 'service_types': ['query_retrieval']},
        {'component_id': 'lab', 'kind': 'internal_service', 'service_types': ['query']}],
        'exchanges': [{'local_id': 'test-query', 'requirement_layer': 'SR', 'from_component_id': 'entry',
            'to_component_id': 'lab', 'parent_rr_local_id': 'rr-book', 'source_refs': [], 'operation_kinds': ['query']}]}
    result = structural_diagnostics(raw)
    assert {r['code'] for r in result} == {'unknown_service_type', 'unknown_operation_kind', 'sr_caller_without_enclosing_request'}
    assert raw['exchanges'][0].get('parent_sr_local_id') is None  # advice cannot edit the graph
    raw['components'][1]['boundary_role'] = 'receiver'
    raw['exchanges'].insert(0, {'local_id': 'entry-request', 'requirement_layer': 'SR',
        'from_component_id': 'ui', 'to_component_id': 'entry', 'parent_rr_local_id': 'rr-book'})
    assert 'sr_target_is_logical_boundary' in {r['code'] for r in structural_diagnostics(raw)}


def test_parent_advice_is_scoped_to_prior_same_rr_request():
    raw = {'components': [{'component_id': 'entry', 'kind': 'abstract_service'}], 'exchanges': [
        {'local_id': 'foreign', 'requirement_layer': 'SR', 'to_component_id': 'entry', 'parent_rr_local_id': 'rr-a'},
        {'local_id': 'current', 'requirement_layer': 'SR', 'to_component_id': 'entry', 'parent_rr_local_id': 'rr-b'},
        {'local_id': 'nested', 'requirement_layer': 'SR', 'from_component_id': 'entry',
         'parent_rr_local_id': 'rr-b', 'parent_sr_local_id': 'foreign'},
        {'local_id': 'future', 'requirement_layer': 'SR', 'to_component_id': 'entry', 'parent_rr_local_id': 'rr-b'}]}
    row = next(r for r in structural_diagnostics(raw) if r['local_exchange_id'] == 'nested')
    assert row['eligible_structural_parent_ids'] == ['current']
    raw['exchanges'][2]['parent_sr_local_id'] = 'current'
    assert not structural_diagnostics(raw)


def test_context_ids_and_rr_boundary_advice_do_not_edit_extracted_graph():
    import copy
    raw = {'covered_section_ids': ['own', 'global-context'], 'components': [
        {'component_id': 'human', 'kind': 'human_actor'},
        {'component_id': 'ui', 'kind': 'frontend_ui', 'boundary_role': 'ui'},
        {'component_id': 'receiver', 'kind': 'frontend_ui', 'boundary_role': 'receiver'}], 'exchanges': [
        {'local_id': 'rr', 'requirement_layer': 'RR', 'from_component_id': 'human', 'to_component_id': 'ui'},
        {'local_id': 'sr', 'requirement_layer': 'SR', 'from_component_id': 'receiver',
         'to_component_id': 'service', 'parent_rr_local_id': 'rr'}]}
    before = copy.deepcopy(raw)
    packet = {'input': {'sections': [{'chapter_id': 'own'}], 'context_sections': [{'chapter_id': 'global-context'}]}}
    rows = structural_diagnostics(raw, packet)
    assert {r['code'] for r in rows} == {'covered_sections_include_context_or_omit_assigned', 'sr_boundary_differs_from_rr_parent'}
    assert rows[0]['required_section_ids'] == ['own']
    assert raw == before


def test_retry_feedback_preserves_raw_evidence_and_rejects_stale_attempt(tmp_path, monkeypatch):
    from scene_completion import interaction_batches
    def reject(packet, raw):
        raise ValueError('missing SR parent')
    monkeypatch.setattr(interaction_batches, 'model_validator', lambda index: reject)
    folder = tmp_path / 'batches/interaction-model'
    write_json(tmp_path / 'sources_index.json', {'documents': []})
    write_json(folder / 'manifest.json', {'batches': [{'batch_id': 'normal-1'}]})
    write_json(folder / 'packets/normal-1.json', {'input_hash': 'current', 'input': {'sections': []}})
    raw = {'batch_id': 'normal-1', 'input_hash': 'current', 'components': [
        {'component_id': 'service', 'kind': 'internal_service'}], 'exchanges': [
        {'local_id': 'read', 'requirement_layer': 'SR', 'from_component_id': 'service', 'to_component_id': 'resource'}]}
    original = {'result': raw, 'validation_error': 'missing SR parent'}
    path = folder / 'attempts/normal-1-original.json'
    write_json(path, original)
    report, code = run_model_diagnostics(Namespace(output_dir=str(tmp_path), prepare_retry=True))
    feedback = read_json(report['findings'][0]['retry_feedback_file'])
    assert code == 0 and not report['complete_model']
    assert feedback['result'] == raw and read_json(path) == original
    assert feedback['model_origin_feedback'][0]['code'] == 'sr_caller_without_enclosing_request'
    assert not (folder / 'results/normal-1.json').exists()
    raw['input_hash'] = 'stale'
    write_json(folder / 'attempts/normal-1-stale.json', {'result': raw})
    import os
    for p in (folder / 'attempts').glob('*.json'):
        os.utime(p, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    with pytest.raises(ValueError, match='current packet'):
        run_model_diagnostics(Namespace(output_dir=str(tmp_path), prepare_retry=False))
