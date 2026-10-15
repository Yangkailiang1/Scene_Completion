import json

import pytest

from scene_completion import finalize
from scene_completion.semantic_backend import write_json, read_json
from scene_completion.sources import fingerprint
from scene_completion.interaction_execution_identity import validate_result_execution
from scene_completion.interaction_evidence import file_hash


def test_review_compaction_keeps_semantics_and_excludes_vectors_and_transport():
    assert finalize.compact({'G': [{'exception_object': 'resource', 'execution_versions': {'v': 'long'}}],
        'vectors': {'secret': [1, 2]}, 'scope': 'full-case'}) == {
        'G': [{'exception_object': 'resource'}], 'scope': 'full-case'}


def test_shared_review_evidence_roundtrips_every_value():
    entry = {'document': 'req.md', 'evidence': 'same precise original condition ' * 20}
    original = {'role': 'generation', 'projection': {'G': [entry, entry],
        'conditions': [entry['evidence'], entry['evidence']]}, 'source_documents': [entry]}
    packed = finalize._shared_view(original)
    assert finalize._encoded_size(packed) < finalize._encoded_size(original)
    packed = finalize._decode_review_tables(packed)
    def expand(value):
        if isinstance(value, dict):
            if set(value) == {'$shared'}:
                return expand(packed['shared_values'][value['$shared']])
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list): return [expand(v) for v in value]
        return value
    restored = {k: expand(v) for k, v in packed.items()
        if k not in ('shared_values', 'shared_values_rule')}
    assert restored == original


def test_shared_review_sections_are_interned_losslessly():
    repeated = {'document': 'req.md', 'text': 'same source condition ' * 20}
    original = {'projection_sections': [
        {'path': ['projection', 'G', 0], 'value': repeated},
        {'path': ['projection', 'G', 1], 'value': repeated}]}
    packed = finalize._shared_view(original)
    assert finalize._encoded_size(packed) < finalize._encoded_size(original)
    packed = finalize._decode_review_tables(packed)
    def expand(value):
        if isinstance(value, dict):
            if set(value) == {'$shared'}:
                return expand(packed['shared_values'][value['$shared']])
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list): return [expand(v) for v in value]
        return value
    restored = {k: expand(v) for k, v in packed.items()
        if k not in ('shared_values', 'shared_values_rule')}
    assert restored == original


def test_review_table_encoding_is_lossless_and_reduces_repeated_record_keys():
    rows = [{'scenario_id': f'G-{index}', 'failure_mechanism': 'stale version',
        'conditions': ['concurrent update', None], 'source_refs': [{'document': 'req.md', 'line': index}]}
        for index in range(20)]
    original = {'records': rows, 'other': [{'short': 1}, {'different': 2}],
        'literal_marker': {'$review_table_v1': {'columns': ['keep'], 'rows': [['literal']]}}}
    encoded = finalize._encode_review_tables(original)
    assert finalize._encoded_size(encoded) < finalize._encoded_size(original)
    assert finalize._decode_review_tables(encoded) == original
    assert '$review_table_v1' in encoded['records']


def test_oversized_role_splits_all_projection_and_source_sections_without_truncation():
    repeated = 'full causal condition and evidence ' * 12
    projection = {'G': [{'scenario_id': f'G-{i}', 'exception_object': repeated,
        'operation': 'write', 'failure_mechanism': 'stale version'} for i in range(12)],
        'history': [{'scenario_id': f'H-{i}', 'mapping_status': 'mapped',
            'operation': 'write', 'text': repeated} for i in range(4)]}
    source_documents = [{'document': 'req.md', 'layer': 'RR',
        'text': ('complete source clause ' * 100)}]
    content = {'role': 'fixture', 'areas': ['four_metric_denominators', 'historical_ranking'],
        'materials_hash': 'materials', 'projection': projection, 'source_documents': source_documents}
    fixed_size = finalize._encoded_size({k: v for k, v in content.items()
        if k not in ('projection', 'source_documents')}) + finalize._encoded_size({'projection_sections': []})
    section_limit = max(1024, min(24_000, (5000 - fixed_size) // 3))
    original_sections = finalize._sections(projection, ['projection'], section_limit)
    original_sections += finalize._sections(source_documents, ['source_documents'], section_limit)
    packets = finalize._split_area_content(content, 5000)
    assert len(packets) > 1
    assert all(finalize._encoded_size(packet) <= 5000 - finalize._packet_reserve(5000) for packet in packets)
    assert any(set(section) == {'$review_section_table_v1'} for packet in packets
        for section in packet['projection_sections'])

    def expand(value, shared):
        if isinstance(value, dict):
            if set(value) == {'$shared'}:
                return expand(shared[value['$shared']], shared)
            return {k: expand(v, shared) for k, v in value.items()}
        if isinstance(value, list): return [expand(v, shared) for v in value]
        return value
    actual = []
    areas = set()
    actual_closures = set()
    for packet in packets:
        areas.update(packet['areas'])
        actual_closures.update(packet['closure_ids'])
        decoded = finalize._decode_review_tables(packet)
        actual.extend(expand(section, decoded.get('shared_values', {}))
            for section in decoded['projection_sections'])
    assert sorted(actual, key=repr) == sorted(original_sections, key=repr)
    assert areas == {'four_metric_denominators', 'historical_ranking'}
    expected_closures = {finalize._closure_id({'projection': projection,
        'source_documents': source_documents}, section['path']) for section in original_sections}
    assert actual_closures == expected_closures


def test_selected_case_review_keeps_full_source_clause_not_just_extracted_quotes(tmp_path):
    bundle = {'scope': {'use_case_ids': ['UC-1']}, 'source_index': {'documents': [{
        'document': 'req.md', 'requirement_layer': 'RR', 'text': 'heading\nnormal\nMISSED EXCEPTION\nother case',
        'chapters': [{'document': 'req.md', 'title': 'UC-1', 'line_start': 1, 'line_end': 3}]}]}}
    docs = finalize._source_documents(tmp_path, bundle)
    assert docs[0]['sections'] == [{'line_start': 1, 'line_end': 3, 'text': 'heading\nnormal\nMISSED EXCEPTION'}]


def test_other_case_historical_sources_do_not_expand_selected_causal_review():
    bundle = {'scope': {'use_case_ids': ['UC-1']}, 'source_existing': [
        {'scenario_id': 'E1', 'use_case_id': 'UC-1'}, {'scenario_id': 'E2', 'use_case_id': 'UC-2'}]}
    view, omitted = finalize._project_bundle(bundle, ('source_existing',))
    assert [row['scenario_id'] for row in view['source_existing']] == ['E1']
    assert omitted['historical_other_case_sources']['count'] == 1


def test_role_projection_preserves_audit_fields_and_hashes_omissions():
    bundle = {'G': [{'scenario_id': 'G-1', 'exception_object': 'cache entry', 'operation': 'write',
        'failure_mechanism': 'stale version', 'trigger_condition': 'concurrent update',
        'necessary_conditions': ['old version'], 'source_refs': [{'document': 'req.md', 'chapter_id': 'C',
            'heading_path': ['large', 'heading'], 'line_start': 7, 'line_end': 8}],
        'mount_id': 'M-1', 'location_id': 'method A', 'reason': 'long redundant narrative',
        'members': [{'duplicate': 'payload'}]}]}
    view, omitted = finalize._project_bundle(bundle, ('G',))
    row = view['G'][0]
    assert row['exception_object'] == 'cache entry'
    assert row['operation'] == 'write'
    assert row['failure_mechanism'] == 'stale version'
    assert row['necessary_conditions'] == ['old version']
    assert row['source_refs'] == [{'document': 'req.md', 'chapter_id': 'C', 'line_start': 7, 'line_end': 8}]
    assert 'reason' not in row and 'members' not in row
    assert 'G' in omitted and 'not_in_role_view' in omitted


def test_cross_role_overview_keeps_metric_denominators_and_numeric_ranking_summary():
    bundle = {'G': [{'scenario_id': 'G-1'}], 'E': [{'scenario_id': 'E-1'}], 'T': [],
        'relations': {'EG': [{'checker_scenario_id': 'E-1', 'generated_scenario_id': 'G-1',
            'status': 'matched', 'same_object': True, 'same_operation': True,
            'same_mechanism': True, 'compatible_conditions': True}]},
        'metrics': {'overall': {'metrics': [{'numerator': 1, 'denominator': 2,
            'numerator_ids': ['G-1'], 'denominator_ids': ['G-1', 'G-2'], 'value': 0.5}]},
            'set_sizes': {'G': 2}},
        'ranking': {'model': 'ranker', 'seed': 3, 'selected_ids': ['G-1'],
            'categories': [{'concern_key': 'C', 'candidate_count': 2, 'history_count': 4,
                'selected_count': 1, 'method': 'cosine'}]}}
    overview = finalize._global_overview(bundle)
    metric = overview['metrics']['overall']['metrics'][0]
    assert (metric['numerator'], metric['denominator'], metric['numerator_ids'],
        metric['denominator_ids']) == (1, 2, ['G-1'], ['G-1', 'G-2'])
    assert overview['ranking_summary']['categories'][0]['candidate_count'] == 2
    assert overview['entity_ids']['G'] == ['G-1']


def test_historical_ranking_projection_keeps_exact_embedding_inputs_and_text_hashes():
    history = [{'unit_id': 'HU-1', 'scenario_id': 'E-1', 'mapping_status': 'mapped',
        'exception_object': 'cache', 'operation': 'write', 'failure_mechanism': 'stale version',
        'trigger_condition': 'parallel update', 'necessary_conditions': ['old version'],
        'concern_keys': ['consistency'], 'source_refs': [{'document': 'history.md',
            'line_start': 5, 'line_end': 5}], 'reason': 'omitted audit narrative'}]
    hashes = {'E-1': 'a' * 64}
    bundle = {'history': history, 'ranking': {'history_hash': 'b' * 64,
        'text_hashes': hashes, 'vectors': {'E-1': [0.1, 0.2]}}}
    view, omitted = finalize._project_bundle(bundle, ('history', 'ranking'))
    row = view['history'][0]
    assert row['mapping_status'] == 'mapped'
    assert row['operation'] == 'write'
    assert row['trigger_condition'] == 'parallel update'
    assert row['necessary_conditions'] == ['old version']
    assert view['ranking']['text_hashes'] == hashes
    assert 'vectors' not in view['ranking']
    assert 'history' in omitted


def test_source_unit_projection_preserves_record_fields_without_duplicate_members():
    source_unit = {'unit_id': 'U-1', 'source_scenario_id': 'S-1', 'collection': 'G',
        'object_code': 'resource', 'cause_code': 'stale_write', 'condition_codes': ['parallel'],
        'exception_object': 'cache', 'operation': 'write', 'failure_mechanism': 'stale version',
        'trigger_condition': 'parallel update', 'necessary_conditions': ['old version'],
        'mapping_status': 'mapped', 'location_id': 'method-x', 'concern_key': 'consistency',
        'reason': 'atomic source unit', 'source_refs': [{'document': 'req.md', 'line_start': 3}],
        'members': [{'unit_id': 'U-1a'}, {'unit_id': 'U-1b'}], 'large_duplicate_payload': 'x' * 1000}
    view, omitted = finalize._project_bundle({'source_units': {'G': [source_unit]}}, ('source_units',))
    row = view['source_units']['G'][0]
    assert row['source_scenario_id'] == 'S-1'
    assert row['mapping_status'] == 'mapped'
    assert row['cause_code'] == 'stale_write'
    assert 'members' not in row
    assert 'large_duplicate_payload' not in row
    assert 'source_units' in omitted


def test_base_source_unit_projection_keeps_full_mapping_assignment_but_not_raw_text():
    row = {'unit_id': 'U-1', 'source_scenario_id': 'S-1', 'collection': 'G',
        'mapping_status': 'mapped', 'concern_key': 'consistency', 'concern_keys': ['consistency'],
        'original_concern_keys': ['consistency'], 'requirement_layer': 'SR', 'use_case_id': 'UC-1',
        'source_refs': [{'document': 'req.md', 'line_start': 3}], 'source_layers': ['SR'],
        'reason': 'free-form provenance prose', 'evidence_quote': 'long copied quote'}
    view, omitted = finalize._project_bundle({'base_source_units': {'G': [row]}}, ('base_source_units',))
    projected = view['base_source_units']['G'][0]
    assert projected['source_scenario_id'] == 'S-1'
    assert projected['mapping_status'] == 'mapped'
    assert projected['concern_key'] == 'consistency'
    assert projected['source_refs'][0]['document'] == 'req.md'
    assert 'reason' not in projected and 'evidence_quote' not in projected
    assert 'base_source_units' in omitted


def test_text_review_sections_split_without_losing_unicode_or_newlines():
    original = ('第一行\n' + '完整长行🙂' * 500 + '\n最后一行')
    sections = finalize._sections({'text': original}, [], 300)
    values = [section['value'] for section in sections]
    assert ''.join(values) == original
    assert all(len(json.dumps(section, ensure_ascii=False, separators=(',', ':')).encode('utf8')) <= 300
        for section in sections)


def test_source_collection_includes_complete_test_and_ar_documents():
    bundle = {'source_index': {'documents': [{'document': 'req.md', 'requirement_layer': 'RR', 'text': 'RR full'}]},
        'test_source_index': {'documents': [{'document': 'test.md', 'text': 'all GT rows'}]}}
    from pathlib import Path
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        root = Path(directory)
        write_json(root / 'ar_sources_index.json', {'documents': [
            {'document': 'arch.md', 'text': 'full AR trace source'}]})
        docs = finalize._source_documents(root, bundle)
    assert {(doc['layer'], doc['document'], doc['text']) for doc in docs} == {
        ('RR', 'req.md', 'RR full'), ('TEST', 'test.md', 'all GT rows'), ('AR', 'arch.md', 'full AR trace source')}


def test_oversized_role_package_is_blocked_instead_of_fragmented(tmp_path):
    from scene_completion.concern_gap_replay import AREAS
    text = ('要求步骤与预期结果🙂\n' * 900)
    bundle = {'source_index': {'documents': []}, 'test_source_index': {'documents': [
        {'document': 'full-test.md', 'text': text}]}, 'ar_trace': [], 'scope': {'use_case_ids': []},
        'source_tests': [], 'source_units': {'T': []}, 'T': []}
    write_json(tmp_path / 'ar_sources_index.json', {'documents': []})
    write_json(tmp_path / 'validation.json', {'complete': True, 'result_hash': 'result'})
    materials = {'files': {'result_bundle.json': 'hash', 'test_sources_index.json': 'test-hash'}}
    prepared = {'materials_hash': 'bound-materials', 'result_hash': 'result', 'areas': AREAS}
    with pytest.raises(ValueError, match='exceeds review context'):
        finalize._review_jobs(tmp_path, prepared, materials, bundle, packet_bytes=1024)


def _complete_review_fixture(root):
    from scene_completion.concern_gap_replay import AREAS, proof_files

    for name, value in [('sources_index.json', {'documents': []}), ('generator_base_identity.json', {}),
            ('scene_model.json', {}), ('historical_ssd.json', {}), ('model_authorization.json', {}),
            ('case_tasks.json', {'tasks': {}}), ('validation.json', {'complete': True, 'result_hash': 'result',
                'junit_counts': {}, 'network_calls': 0, 'resumed_batches': 0, 'exit_code': 0})]:
        write_json(root / name, value)
    bundle = {'protocol': 'rr-sr-concern-gap-v2', 'result_hash': 'result',
        'source_index': {'documents': []}, 'test_source_index': {'documents': []},
        'ar_trace': [], 'scope': {'kind': 'full', 'use_case_ids': []}}
    write_json(root / 'result_bundle.json', bundle)
    run = {'execution_mode': 'case-dag', 'review_policy': {'model': 'fixture-model',
        'runtime': 'openai-compatible', 'reasoning_effort': None}}
    write_json(root / 'run_manifest.json', run)
    files = proof_files(root)
    from scene_completion.concern_gap_replay import PROTOCOL
    materials = {'protocol': PROTOCOL, 'result_hash': 'result', 'files': files, 'areas': AREAS}
    write_json(root / 'effect_review_materials.json', materials)
    materials_hash = fingerprint(materials)
    prepared = {'complete': True, 'materials_hash': materials_hash, 'result_hash': 'result', 'areas': AREAS}
    manifest, packets = finalize._expected_local_packets(root, materials_hash, 12000)
    proofs, values, local_values = [], [], []
    endpoint_hash = fingerprint('https://review.example/v1')
    def make_phase(phase, manifest, packets):
      review_dir = root / 'batches' / 'independent-effect-review' / phase
      write_json(review_dir / 'manifest.json', manifest)
      phase_values = []
      for batch in manifest['batches']:
        bid = batch['batch_id']; packet = packets[bid]
        write_json(review_dir / 'packets' / f'{bid}.json', packet)
        raw = {'batch_id': bid, 'input_hash': batch['input_hash'], 'model': 'fixture-model',
            'execution_model_evidence': {'requested_model': 'fixture-model', 'api_endpoint_hash': endpoint_hash},
            'areas': [{'area': area, 'passed': True, 'reason': 'audited complete supplied role',
                'evidence_ids': ['F0']} for area in packet['input']['areas']],
            'unresolved_findings': []}
        if phase == 'global':
            raw['global_review'] = {'passed': True, 'reason': 'cross-role IDs and denominators reconcile',
                'coverage_check': {'complete': True, 'unique': True, 'missing_ids': [],
                    'duplicate_ids': [], 'orphan_ids': []}, 'evidence_ids': ['F0']}
        path = review_dir / 'results' / f'{bid}.json'
        write_json(path, raw)
        identity = validate_result_execution(raw, result_path=path)
        proofs.append({'phase': phase, 'path': str(path.resolve()), 'hash': fingerprint(raw), 'batch_id': bid,
            'input_hash': batch['input_hash'], 'packet_hash': fingerprint(packet), 'identity': identity})
        value = finalize._validate_review_packet(packet, raw)
        phase_values.append(value)
        if phase == 'local':
            local_values.append({'input': packet['input'], 'result': value})
      return phase_values
    values.extend(make_phase('local', manifest, packets))
    global_manifest, global_packets = finalize._expected_global_packets(root, materials_hash, 12000, local_values)
    values.extend(make_phase('global', global_manifest, global_packets))
    catalog = finalize._evidence_catalog({'files': files})
    aggregate = finalize._aggregate_review(values, materials_hash, catalog)
    write_json(root / 'effect_review_raw.json', aggregate)
    meta = {'model': 'fixture-model', 'runtime': 'openai-compatible', 'reasoning_effort': None,
        'endpoint_hash': endpoint_hash, 'packet_bytes': 12000, 'materials_hash': materials_hash,
        'result_hash': 'result', 'executions': proofs, 'passed': True, 'unresolved_findings': [],
        'raw_review_hash': file_hash(root / 'effect_review_raw.json')}
    write_json(root / 'effect_review.json', meta)
    return meta


def test_review_execution_is_bound_to_full_plan_and_raw_aggregation(tmp_path):
    meta = _complete_review_fixture(tmp_path)
    finalize.verify_review_execution(tmp_path, meta)

    raw = read_json(tmp_path / 'effect_review_raw.json')
    raw['areas'][0]['reason'] = 'edited after API review'
    write_json(tmp_path / 'effect_review_raw.json', raw)
    meta['raw_review_hash'] = file_hash(tmp_path / 'effect_review_raw.json')
    with pytest.raises(ValueError, match='summary differs'):
        finalize.verify_review_execution(tmp_path, meta)


def test_global_review_packet_contains_all_local_results_and_full_global_directories(tmp_path):
    _complete_review_fixture(tmp_path)
    from scene_completion.concern_gap_replay import AREAS
    manifest = read_json(tmp_path / 'batches/independent-effect-review/global/manifest.json')
    packet = read_json(tmp_path / 'batches/independent-effect-review/global/packets' /
        (manifest['batches'][0]['batch_id'] + '.json'))
    payload = finalize._decode_review_tables(packet['input'])
    assert payload['areas'] == list(AREAS)
    assert payload['local_review_results']
    assert {row['area'] for result in payload['local_review_results'] for row in result['review']} == set(AREAS)
    assert payload['global_overview']['entity_ids']['G'] == []
    assert set(payload['global_overview']['relations']) == set()


def test_review_execution_rejects_packet_with_same_material_hash_but_changed_payload(tmp_path):
    meta = _complete_review_fixture(tmp_path)
    manifest = read_json(tmp_path / 'batches/independent-effect-review/local/manifest.json')
    packet_path = tmp_path / 'batches/independent-effect-review/local/packets' / (manifest['batches'][0]['batch_id'] + '.json')
    packet = read_json(packet_path)
    packet['input']['projection'] = {'forged': True}
    write_json(packet_path, packet)
    with pytest.raises(ValueError, match='packet'):
        finalize.verify_review_execution(tmp_path, meta)


def test_review_execution_requires_a_complete_execution_proof_set(tmp_path):
    meta = _complete_review_fixture(tmp_path)
    meta['executions'].pop()
    with pytest.raises(ValueError, match='incomplete|duplicated'):
        finalize.verify_review_execution(tmp_path, meta)


def test_review_runtime_must_match_the_run_policy(tmp_path):
    meta = _complete_review_fixture(tmp_path)
    meta['runtime'] = 'different-runtime'
    with pytest.raises(ValueError, match='identity differs from run policy'):
        finalize.verify_review_execution(tmp_path, meta)


def test_actual_review_runner_builds_the_same_plan_and_preserves_configured_output_budget(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scene_completion import concern_gap_replay as replay, role_cli, model_access
    _complete_review_fixture(tmp_path)
    material = read_json(tmp_path/'effect_review_materials.json')
    prepared = {'complete': True, 'materials_hash': fingerprint(material),
        'result_hash': 'result', 'areas': replay.AREAS}
    monkeypatch.setattr(replay, 'prepare_review', lambda root: (prepared, 0))
    client = SimpleNamespace(config={'max_tokens': 12345, 'thinking': False},
        base_url='https://review.example/v1', model=lambda kind: 'fixture-model')
    calls = []
    def agent(packet):
        calls.append(packet)
        rows = [{'area': area, 'passed': True, 'reason': 'examined supplied view', 'evidence_ids': ['F0']}
            for area in packet['input']['areas']]
        raw = {'model': 'fixture-model', 'areas': rows, 'unresolved_findings': [],
            'execution_model_evidence': {'requested_model': 'fixture-model', 'thinking': False,
                'reasoning_effort': None, 'api_endpoint_hash': fingerprint(client.base_url)}}
        if packet['input']['role'] == 'cross_role_global':
            raw['global_review'] = {'passed': True, 'reason': 'cross-role sets reconcile', 'evidence_ids': ['F0']}
            raw['global_review']['coverage_check'] = {'complete': True, 'unique': True,
                'missing_ids': [], 'duplicate_ids': [], 'orphan_ids': []}
        return raw
    client.agent = agent
    monkeypatch.setattr(role_cli, '_client', lambda *a: client)
    monkeypatch.setattr(model_access, 'preflight', lambda c: {'available': True})
    result = finalize.review(tmp_path, 'fixture-config')
    assert result['complete'] and result['passed']
    assert client.config['max_tokens'] == 12345
    assert len(calls) == 4
    finalize.verify_review_execution(tmp_path, read_json(tmp_path/'effect_review.json'))


def test_causal_role_includes_generated_units_and_original_rr_sr_evidence(tmp_path, monkeypatch):
    write_json(tmp_path/'validation.json', {})
    monkeypatch.setattr(finalize, '_evidence_catalog', lambda _: [])
    monkeypatch.setattr(finalize, '_source_documents', lambda *_: [
        {'layer': layer, 'document': layer+'.md', 'text': 'source '+layer}
        for layer in ('RR','SR','TEST')])
    jobs = finalize._review_jobs(tmp_path, {'materials_hash': 'x'}, {},
        {'source_generated': [{'scenario_id': 'G1', 'exception_object': 'item'}]}, 100000)
    role = finalize._decode_review_tables(next(j for j in jobs if j['role'] == 'causal_mapping'))
    assert role['projection']['source_generated'][0]['scenario_id'] == 'G1'
    assert {d['layer'] for d in role['source_documents']} == {'RR','SR','TEST'}
