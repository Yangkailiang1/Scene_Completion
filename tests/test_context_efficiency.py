from copy import deepcopy
import json
from pathlib import Path

import pytest

from scene_completion import context_projection as c
from scene_completion.semantic_backend import compose_packet, prepare_packets, read_json, write_json, SemanticClient
from scene_completion.review_scope import causal_scope
from scene_completion import verification_context as v
from scene_completion.validation_issues import direct_plan, normalization_issue
from scene_completion.sources import fingerprint


def test_wire_roundtrip_preserves_duplicate_evidence_roles_and_distinct_citations():
    quote = '原文明确的字段约束，不是模型推导。' * 40
    data = {'collection': 'G', 'scenarios': [{'scenario_id': 'G1', 'trigger_condition': quote,
        'pending_details': ['未确认具体上限']}],
        'original_evidence': [{'text': quote, 'source_ref': {'document': 'a.md', 'line_start': 1}},
            {'text': quote, 'source_ref': {'document': 'b.md', 'line_start': 8}}]}
    with c.settings({'context_profile': 'compact-v1'}):
        packet = compose_packet('gap-fixture', data, [], {})
    wire, stats = c.project(packet)
    assert c.expand(wire) == packet
    assert json.dumps(wire, ensure_ascii=False).count(quote) == 1
    assert stats['wire_bytes'] < stats['original_bytes']
    assert stats['coverage']['required_item_ids'] == ['G1']
    assert c.expand(wire)['input']['original_evidence'][1]['source_ref']['document'] == 'b.md'


def test_literal_marker_collision_and_missing_refs_fail_closed():
    value = {c.MARKER: 'literal original object ' * 40}
    with c.settings({'context_profile': 'compact-v1'}):
        packet = compose_packet('fixture', {'a': value, 'b': value}, [], {})
    wire, _ = c.project(packet)
    assert c.expand(wire) == packet
    if wire.get('context_values'):
        wire['context_values'].clear()
        with pytest.raises(ValueError, match='invalid context reference'): c.expand(wire)


def test_legacy_packet_identity_unchanged_and_compact_has_distinct_identity():
    legacy = compose_packet('fixture', {'source': 'full source'}, [], {})
    with c.settings({'context_profile': 'compact-v1'}):
        compact = compose_packet('fixture', {'source': 'full source'}, [], {})
    assert 'context_policy' not in legacy
    assert fingerprint(legacy) != fingerprint(compact)
    assert c.project(legacy)[0] == legacy


def test_duplicate_test_skill_removed_and_execution_rules_are_versioned():
    text = 'controller only\n<!-- batch-rules:start -->Required real evidence<!-- batch-rules:end -->\nextra method'
    with c.settings({'context_profile': 'compact-v1'}):
        packet = compose_packet('gap-test-extract', {'skill': text, 'test_condition_skill': text}, [], {})
    view = c.expand(c.project(packet)[0])
    assert view['input']['skill'] == 'Required real evidence'
    assert 'test_condition_skill' not in view['input']
    assert packet['input']['test_condition_skill'] == text  # full validator packet untouched


def test_packet_split_covers_every_item_and_preserves_cross_chapter_evidence(tmp_path):
    rows = [{'scenario_id': f'S-{i}', 'trigger_condition': 'different condition ' * 50 + str(i)} for i in range(8)]
    data = {'collection': 'G', 'scenarios': rows, 'original_evidence': [
        {'scenario_id': r['scenario_id'], 'text': 'chapter ' + r['scenario_id'],
            'source_ref': {'document': 'a.md', 'line_start': 100 + i}} for i, r in enumerate(rows)],
        'exchange_details': [{'operation': 'cross chapter dependency', 'source_refs': [{'document': 'b.md', 'line_start': 99}]}]}
    with c.settings({'context_profile': 'compact-v1', 'stage_request_bytes': {'gap-fixture': 7000}}):
        manifest = prepare_packets(tmp_path, 'gap-fixture', [data], [], {})
    assert len(manifest['batches']) > 1
    packets = [read_json(tmp_path/'packets'/(b['batch_id']+'.json')) for b in manifest['batches']]
    assert [s['scenario_id'] for p in packets for s in p['input']['scenarios']] == [r['scenario_id'] for r in rows]
    assert all(p['input']['exchange_details'] == data['exchange_details'] for p in packets)
    assert len(list((tmp_path/'context_metrics').glob('*.json'))) == len(packets)


def test_single_oversized_record_and_missing_dependency_are_never_truncated(tmp_path):
    with c.settings({'context_profile': 'compact-v1', 'stage_request_bytes': {'*': 4000}}):
        with pytest.raises(ValueError, match='single context item'):
            prepare_packets(tmp_path, 'gap-fixture', [{'scenarios': [{'scenario_id': 'S', 'text': 'z'*9000}]}], [], {})
        bad = compose_packet('gap-reverse-check-G', {'units': [{'unit_id': 'U', 'source_scenario_id': 'missing'}], 'original_scenarios': []}, [], {})
    with pytest.raises(ValueError, match='dependency missing'): c.project(bad)
    assert not (tmp_path/'manifest.json').exists()


def test_causal_scope_retains_explicit_other_case_closure_unknown_and_unmapped():
    own = {'unit_id': 'U1', 'scenario_id': 'E1', 'source_scenario_id': 'S1', 'use_case_id': 'A', 'mapping_status': 'unmapped'}
    related = {'unit_id': 'U2', 'scenario_id': 'E2', 'source_scenario_id': 'S2', 'use_case_id': 'B'}
    unrelated = {'unit_id': 'U3', 'scenario_id': 'E3', 'source_scenario_id': 'S3', 'use_case_id': 'B'}
    unknown = {'unit_id': 'U4', 'source_scenario_id': 'S4'}
    bundle = {'scope': {'use_case_ids': ['A']}, 'E': [own], 'history': [own, related, unrelated],
        'source_units': {'E': [own, related, unrelated, unknown]}, 'base_source_units': {'E': [own, related, unrelated, unknown]},
        'source_existing': [{'scenario_id': 'S'+str(i), 'use_case_id': 'A' if i == 1 else 'B'} for i in (1,2,3)],
        'dedup': {'E': [{'left_unit_id': 'U1', 'right_unit_id': 'U2'}, {'left_unit_id': 'U3', 'right_unit_id': 'U3'}]},
        'reverse_checks': {'E': {'reviews': [{'unit_id': 'U'+str(i)} for i in (1,2,3,4)]}}}
    original = deepcopy(bundle)
    scoped, omitted = causal_scope(bundle)
    assert bundle == original
    assert [r['unit_id'] for r in scoped['source_units']['E']] == ['U1', 'U2', 'U4']
    assert [r['scenario_id'] for r in scoped['source_existing']] == ['S1', 'S2']
    assert scoped['history'] == original['history']
    assert len(scoped['dedup']['E']) == 1 and omitted


def test_known_contract_failures_bypass_diagnosis_but_semantic_ambiguity_does_not():
    source = {'scenario_id': 'G1', 'source_refs': [{'document': 'a.md', 'line_start': 4}]}
    issue = normalization_issue(source, 'every necessary condition needs a semantic code')
    failure = {'errors': {'B': 'condition count'}, 'validation_diagnostics': {'B': {'issues': [issue]}}}
    plan, proof = direct_plan(failure)
    assert plan['targets'] == ['G1.condition_codes'] and proof['model_calls'] == 0
    failure['validation_diagnostics']['B']['issues'][0]['directed_repair_safe'] = False
    assert direct_plan(failure) is None
    failure['findings'] = [{'source_supported': False}]
    assert direct_plan(failure) is None


def test_verification_cache_is_invocation_local_and_cache_resume_always_executes(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(v, 'guard', lambda root: (tmp_path/'source').read_text())
    (tmp_path/'source').write_text('one')
    @v.cached_replay
    def replay(root, cache_resume=False):
        calls.append(cache_resume)
        return {'complete': True, 'values': ['immutable']}
    with v.session(tmp_path):
        replay(tmp_path)['values'].append('mutation')
        assert replay(tmp_path)['values'] == ['immutable']
        replay(tmp_path, cache_resume=True)
        (tmp_path/'source').write_text('two')
        replay(tmp_path)
    replay(tmp_path)
    assert calls == [False, True, False, False]


def test_guard_detects_external_proof_content_changes_and_tool_changes(tmp_path, monkeypatch):
    from scene_completion import concern_gap_replay as r
    outside = tmp_path.parent / (tmp_path.name + '-external.json')
    write_json(outside, {'proof': 'before'})
    write_json(tmp_path/'case.json', {'binding': {'proofs': {str(outside): 'hash'}}})
    write_json(tmp_path/'run_manifest.json', {})
    monkeypatch.setattr(r, 'proof_files', lambda root: {'case.json': fingerprint(read_json(tmp_path/'case.json'))})
    before = v.guard(tmp_path)
    assert before is not None
    write_json(outside, {'proof': 'after'})
    assert v.guard(tmp_path) != before


def test_compact_state_suppresses_unchanged_context_and_ignores_historical_failure(tmp_path):
    from scene_completion.controller_status import inspect_run
    write_json(tmp_path/'run_manifest.json', {})
    write_json(tmp_path/'case_tasks.json', {'tasks': {'A:normal': {'stage': 'normal', 'status': 'passed', 'reason': 'old rejection'}}})
    first = inspect_run(tmp_path)
    second = inspect_run(tmp_path, since_state=first['state_fingerprint'])
    assert first['blocked'] == [] and first['passed_tasks_with_historical_failures'] == 1
    assert second['unchanged'] and len(json.dumps(second)) < len(json.dumps(first))


def test_batch_rule_summaries_retain_generation_invariants():
    root = Path(__file__).resolve().parents[1] / '.cac/skills'
    rules = c._rules((root/'scene-generate/SKILL.md').read_text(encoding='utf8'))
    for term in ('mount_id', 'E、测试GT', '适用性筛选', 'AR只追溯', 'pending_details', '确认', '成功条目'):
        assert term in rules
    assert '模型来源与完整性检查' not in rules


def test_partial_normalization_patch_retains_successes_and_rejects_widening(tmp_path):
    from scene_completion import normalization_item_patch as patch
    from scene_completion.concern_gap_batches import normalize_validator
    from scene_completion.concern_gap_normalize_diagnostics import validator as diagnostic_validator
    ref = {'document': 'req.md', 'line_start': 1, 'line_end': 1}
    sources = [{'scenario_id': sid, 'use_case_id': 'A', 'requirement_layer': 'SR', 'name': sid,
        'exception_object': 'record', 'operation': 'read', 'failure_mechanism': 'permission absent',
        'trigger_condition': 'caller has no permission', 'necessary_conditions': ['authenticated caller'],
        'source_refs': [ref], 'exchange_id': 'X', 'concern_keys': ['human.authorization']}
        for sid in ('G1', 'G2')]
    data = {'collection': 'G', 'scenarios': sources, 'locations': [
        {'location_id': 'L', 'use_case_id': 'A', 'exchange_ids': ['X']}]}
    folder = tmp_path/'batch'
    with c.settings({'context_profile': 'compact-v1'}):
        manifest = prepare_packets(folder, 'gap-normalize-G', [data], [], {'items': []})
    bid = manifest['batches'][0]['batch_id']
    packet_path = folder/'packets'/(bid+'.json'); original = read_json(packet_path)
    good = {'object_code': 'record', 'cause_code': 'permission_absent', 'condition_codes': ['authenticated_caller'], 'reason': 'original condition'}
    bad = {**good, 'condition_codes': []}
    raw = {'batch_id': bid, 'input_hash': original['input_hash'], 'model': 'test-model',
        'execution_model_evidence': {'requested_model': 'test-model'},
        'items': [{'source_scenario_id': 'G1', 'units': [bad]}, {'source_scenario_id': 'G2', 'units': [good]}]}
    result_path = folder/'attempts'/(bid+'-1.json')
    write_json(result_path, {'result': raw, 'validation_error': 'code count'})
    index = {'documents': [{'document': 'req.md', 'line_count': 1, 'text': 'contract', 'chapters': [
        {'chapter_id': 'C', 'document': 'req.md', 'title': 'Contract', 'level': 1,
            'heading_path': ['Contract'], 'line_start': 1, 'line_end': 1}]}]}
    with pytest.raises(ValueError) as caught: diagnostic_validator(index)(original, raw)
    assert caught.value.validation_diagnostic['issues'][0]['item_id'] == 'G1'
    one = deepcopy(original); one['input']['scenarios'] = [sources[1]]
    normalize_validator(index)(one, {'items': [raw['items'][1]]})
    built = patch.prepare(original, raw, packet_path, result_path, index)
    assert [s['scenario_id'] for s in built['payload']['scenarios']] == ['G1']
    with c.settings({'context_profile': 'compact-v1'}):
        prepared = compose_packet('gap-normalize-G', built['payload'], built['instructions'], built['contract'])
    fixed = {'edits': [{'source_scenario_id': 'G1', 'unit_index': 0,
        'values': {'condition_codes': ['authenticated_caller']}}]}
    values = normalize_validator(index)(prepared, fixed)
    expected = normalize_validator(index)(original, {**raw, 'items': [
        {'source_scenario_id': 'G1', 'units': [good]}, raw['items'][1]]})
    assert values == expected
    unassigned = deepcopy(fixed); unassigned['edits'][0]['values']['object_code'] = 'different_record'
    with pytest.raises(ValueError, match='unassigned'): normalize_validator(index)(prepared, unassigned)
    widened = deepcopy(prepared); widened['input']['scenarios'].append(sources[1])
    with pytest.raises(ValueError, match='widened'): normalize_validator(index)(widened, fixed)
    write_json(result_path, {'result': {**raw, 'model': 'forged'}})
    with pytest.raises(ValueError, match='modified'): normalize_validator(index)(prepared, fixed)


def test_actual_request_uses_projected_view_and_records_execution_profile(monkeypatch):
    client = SemanticClient({'agent_model': 'configured-model'})
    seen = []
    def post(endpoint, body):
        seen.append(body)
        return {'choices': [{'message': {'content': '{"items":[]}'}}], 'model': 'configured-model'}
    monkeypatch.setattr(client, 'post', post)
    with c.settings({'context_profile': 'compact-v1'}):
        packet = compose_packet('fixture', {'one': 'evidence'*150, 'two': 'evidence'*150}, [], {'items': []})
    result = client.agent(packet)
    sent = json.loads(seen[0]['messages'][1]['content'])
    assert c.expand(sent) == packet
    assert result['execution_model_evidence']['context_profile'] == 'compact-v1'


def test_configured_request_budget_stops_before_http(monkeypatch):
    client = SemanticClient({'agent_model': 'configured-model', 'stage_request_bytes': {'fixture': 1024}})
    monkeypatch.setattr(client, 'post', lambda *a: pytest.fail('oversized request must not reach HTTP'))
    packet = compose_packet('fixture', {'source': 'original evidence ' * 1000}, [], {})
    with pytest.raises(RuntimeError, match='stage_request_bytes'): client.agent(packet)


def test_recheck_keeps_context_profile_and_does_not_relabel_retained_packets(tmp_path):
    from scene_completion.concern_gap_dag import Pipeline
    with c.settings({'context_profile': 'compact-v1'}):
        first = prepare_packets(tmp_path, 'gap-fixture', [{'scenarios': [{'scenario_id': 'S1'}]},
            {'scenarios': [{'scenario_id': 'S2'}]}], [], {})
    retained = first['batches'][0]
    original = (tmp_path/'packets'/(retained['batch_id']+'.json')).read_bytes()
    Pipeline.salt(tmp_path, {'action': 'recheck', 'reason': 'original source'}, 1, retained=[retained['batch_id']])
    updated = read_json(tmp_path/'manifest.json')
    assert updated['batches'][0] == retained
    assert (tmp_path/'packets'/(retained['batch_id']+'.json')).read_bytes() == original
    for row in updated['batches']:
        assert read_json(tmp_path/'packets'/(row['batch_id']+'.json'))['context_policy']['profile'] == 'compact-v1'


def test_missing_external_path_appearance_invalidates_guard(tmp_path, monkeypatch):
    from scene_completion import concern_gap_replay as r
    external = tmp_path.parent/(tmp_path.name+'-later.json')
    write_json(tmp_path/'proof.json', {'original_absolute_path': str(external)})
    write_json(tmp_path/'run_manifest.json', {})
    monkeypatch.setattr(r, 'proof_files', lambda root: {'proof.json': fingerprint(read_json(tmp_path/'proof.json'))})
    before = v.guard(tmp_path)
    assert before is not None
    write_json(external, {'appeared': True})
    assert v.guard(tmp_path) != before


def test_causal_role_projection_keeps_cross_case_source_rows_and_full_ranking_history():
    from scene_completion.finalize import _role_content
    own = {'unit_id': 'U1', 'source_scenario_id': 'S1', 'use_case_id': 'A'}
    other = {'unit_id': 'U2', 'source_scenario_id': 'S2', 'use_case_id': 'B'}
    irrelevant = {'unit_id': 'U3', 'source_scenario_id': 'S3', 'use_case_id': 'C'}
    bundle = {'scope': {'use_case_ids': ['A']}, 'E': [own], 'source_units': {'E': [own, other, irrelevant]},
        'base_source_units': {'E': [own, other, irrelevant]}, 'source_existing': [
            {'scenario_id': 'S1', 'use_case_id': 'A'}, {'scenario_id': 'S2', 'use_case_id': 'B'}, {'scenario_id': 'S3', 'use_case_id': 'C'}],
        'history': [own, other, irrelevant], 'dedup': {'E': [{'left_unit_id': 'U1', 'right_unit_id': 'U2'}]}}
    data = _role_content('causal_mapping', ['reverse_atomicity'], {'materials_hash': 'm'}, [], [], {}, bundle, 'case-closure-v1')['projection']
    assert [r['unit_id'] for r in data['source_units']['E']] == ['U1', 'U2']
    assert [r['scenario_id'] for r in data['source_existing']] == ['S1', 'S2']
    ranking = _role_content('metrics_ranking', ['historical_ranking'], {'materials_hash': 'm'}, [], [], {}, bundle, 'case-closure-v1')['projection']
    assert len(ranking['history']) == 3
