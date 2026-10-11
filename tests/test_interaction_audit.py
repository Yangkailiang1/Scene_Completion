"""Per-run guard rails work across projects and never repair G from C."""
import copy

import pytest

from scene_completion.interaction_audit import (checker_audit_packets, checker_audit_validator,
    verify_checker_audit, check_run, prepare_checker_repairs, normal_model_findings)
from scene_completion.interaction_baseline import import_baseline
from scene_completion.interaction_protocol import baseline, PROTOCOL
from scene_completion.interaction_cli import versions
from scene_completion.semantic_backend import read_json, write_json
from scene_completion.sources import fingerprint
from scene_completion.interaction_batches import checker_validator
from tests.test_interaction_baseline import original


def fixture_audit(tmp_path):
    root, index, base, baseline_value = original(tmp_path)
    folder = root / 'batches/interaction-checker-audit'
    batch = read_json(folder / 'manifest.json')['batches'][0]
    return root, index, base, folder, read_json(folder / 'packets' / (batch['batch_id'] + '.json')), read_json(folder / 'results' / (batch['batch_id'] + '.json'))


def test_source_audit_inputs_are_independent_and_bind_exact_c(tmp_path):
    root, index, _, folder, packet, result = fixture_audit(tmp_path)
    assert not {'generated', 'generator_model', 'test', 'recommendations'} & set(packet['input'])
    assert checker_audit_validator(index)(packet, result)[0]['passed']
    assert all(row['passed'] for row in verify_checker_audit(root, index))
    assert packet['input']['checker_result_hash'] == fingerprint(packet['input']['scenarios'])
    assert packet['input']['source_chapters']


def test_preserved_rejected_audit_can_repair_exact_draft_after_newer_pass(tmp_path):
    from scene_completion.semantic_backend import prepare_packets
    root, index, _, folder, packet, raw = fixture_audit(tmp_path)
    (root / 'existing_scenarios.json').unlink()
    raw['reviews'][0].update(atomic=False, issues=['Two independent failure mechanisms were merged'])
    write_json(folder / 'results' / (packet['batch_id'] + '.json'), raw)
    old = read_json(folder / 'manifest.json')
    current = prepare_packets(folder, 'interaction-checker-audit', [packet['input']], ['new audit wording'], {})
    newer = copy.deepcopy(raw)
    newer.update(current['batches'][0])
    newer['reviews'][0].update(atomic=True, issues=[])
    write_json(folder / 'results' / (current['batches'][0]['batch_id'] + '.json'), newer)
    assert collect_current_audit(folder, index)[0]['passed']
    selected = [packet['input']['checker_batch_id']]
    historic = folder / 'manifest_history' / (fingerprint(old) + '.json')
    assert prepare_checker_repairs(root, index, historic, selected) == selected
    assert not (root / 'batches/interaction-checker/results' / (selected[0] + '.json')).exists()
    assert read_json(folder / 'results' / (packet['batch_id'] + '.json')) == raw


def collect_current_audit(folder, index):
    from scene_completion.semantic_backend import collect_packets
    return collect_packets(folder, checker_audit_validator(index))[0]


def test_historical_repair_rejects_arbitrary_or_unrejected_selection(tmp_path):
    from scene_completion.interaction_audit import historical_checker_findings
    _, index, _, folder, packet, _ = fixture_audit(tmp_path)
    old = read_json(folder / 'manifest.json')
    historic = folder / 'manifest_history' / (fingerprint(old) + '.json')
    write_json(historic, old)
    with pytest.raises(ValueError, match='only existing rejected'):
        historical_checker_findings(folder, historic, index, [packet['input']['checker_batch_id']])
    with pytest.raises(ValueError, match='saved local'):
        historical_checker_findings(folder, folder / 'manifest.json', index, [packet['input']['checker_batch_id']])


def test_per_run_normal_diagnostics_preserve_only_rejected_rows_and_omissions():
    review = {'use_case_id': 'CareSchedule', 'model_batch_id': 'care-model',
        'line_reviews': [{'line_id': 'rr.md:L4', 'covered': True, 'issues': []}],
        'exchange_reviews': [{'local_exchange_id': 'read', 'supported': False, 'issues': ['Not an initiating call']}],
        'scenario_reviews': [{'scenario_index': 0, 'supported': False, 'issues': ['Exception is not optional'], 'evidence_quote': 'Appointment missing.'}],
        'omitted_calls': [{'caller': 'ScheduleService', 'callee': 'schedule', 'operation': 'read schedule'}],
        'tool_findings': [{'code': 'claimed_call_without_source_anchor', 'line_id': 'sr.md:L8'}]}
    before = copy.deepcopy(review)
    result = normal_model_findings([review])
    assert len(result) == 4 and all(v['use_case_id'] == 'CareSchedule' for v in result)
    assert result[1]['evidence_quote'] == 'Appointment missing.'
    assert review == before


def test_role_mount_gap_is_visible_in_per_run_diagnostics():
    rows = normal_model_findings([{'use_case_id': 'ClinicRequest', 'model_batch_id': 'clinic',
        'line_reviews': [], 'exchange_reviews': [], 'scenario_reviews': [],
        'responsibility_reviews': [{'local_exchange_id': 'rr', 'service_type': 'query_retrieval',
            'correctly_modeled': False, 'issues': ['Missing source-backed query role']}]}])
    assert len(rows) == 1 and rows[0]['finding_kind'] == 'responsibility_reviews'
    assert rows[0]['service_type'] == 'query_retrieval'


def test_source_audit_preserves_rejected_c_and_blocks_frozen_import(tmp_path):
    root, index, base, folder, packet, result = fixture_audit(tmp_path)
    result['reviews'][0].update(source_supported=False, issues=['原文只有正常校验，没有异常分支'])
    rows = checker_audit_validator(index)(packet, result)
    assert not rows[0]['passed']
    original_c = read_json(root / 'existing_scenarios.json')
    write_json(folder / 'results' / (packet['batch_id'] + '.json'), result)
    with pytest.raises(ValueError, match='unresolved'):
        import_baseline(root / 'existing_scenarios.json', tmp_path / 'next', index, base)
    assert read_json(root / 'existing_scenarios.json') == original_c


def test_omission_blocks_source_audit_even_when_every_supplied_c_passes(tmp_path):
    root, index, _, folder, packet, result = fixture_audit(tmp_path)
    result['omitted_conditions'] = [{'condition': '另一条异常遗漏', 'evidence_quote': '异常条件',
        'source_refs': result['reviews'][0]['source_refs'], 'layer_use_case_id': packet['input']['use_case_id'],
        'extraction_basis': 'explicit_named', 'failure_source_refs': result['reviews'][0]['source_refs'],
        'failure_evidence_quote': '异常条件', 'contract_source_refs': []}]
    assert not checker_audit_validator(index)(packet, result)[0]['passed']
    broken = copy.deepcopy(result)
    broken['omitted_conditions'][0]['evidence_quote'] = '伪造原文'
    with pytest.raises(ValueError, match='exact original'):
        checker_audit_validator(index)(packet, broken)


def test_audit_cannot_skip_ids_or_use_unquoted_evidence(tmp_path):
    _, index, _, _, packet, result = fixture_audit(tmp_path)
    broken = copy.deepcopy(result)
    broken['reviews'] = []
    with pytest.raises(ValueError, match='every C'):
        checker_audit_validator(index)(packet, broken)
    broken = copy.deepcopy(result)
    broken['reviews'][0]['evidence_quote'] = '不是原文'
    with pytest.raises(ValueError, match='quote'):
        checker_audit_validator(index)(packet, broken)


def test_audit_positive_notes_are_not_failure_findings(tmp_path):
    _, index, _, _, packet, raw = fixture_audit(tmp_path)
    raw['reviews'][0]['issues'] = ['原文确实支持此条件']
    with pytest.raises(ValueError, match='contradict'):
        checker_audit_validator(index)(packet, raw)


def test_audit_omission_cannot_be_a_normal_validation_inversion(tmp_path):
    _, index, _, _, packet, raw = fixture_audit(tmp_path)
    document = next(d for d in index['documents'] if d['document'] == packet['input']['requirement_layer'] + '.md')
    document['text'] = document['text'].replace('异常条件', '基本流程\n校验字段必须存在。')
    document['line_count'] += 1
    for chapter in document['chapters']:
        chapter['line_end'] += 1
    ref = {'document': document['document'], 'line_start': 4, 'line_end': 4}
    for section in packet['input']['sections']:
        section['line_end'] += 1
    raw['reviews'][0].update(evidence_quote='校验字段必须存在。', source_refs=[ref])
    raw['omitted_conditions'] = [{'condition': '字段缺失', 'evidence_quote': '校验字段必须存在。',
        'source_refs': [ref], 'layer_use_case_id': 'UC-1', 'extraction_basis': 'explicit_named',
        'failure_source_refs': [ref], 'failure_evidence_quote': '校验字段必须存在。', 'contract_source_refs': []}]
    with pytest.raises(ValueError, match='normal validation'):
        checker_audit_validator(index)(packet, raw)


def test_partial_run_check_is_not_acceptance_and_detects_source_change(tmp_path):
    root, index, _, _, _, _ = fixture_audit(tmp_path)
    write_json(root / 'sources_index.json', index)
    write_json(root / 'concern_baseline.json', baseline())
    write_json(root / 'run_manifest.json', {'protocol': PROTOCOL, 'complete': False, 'accepted': False,
        'source_hash': fingerprint(index), 'tool_versions': versions()})
    result = check_run(root)
    assert not result['passed'] and result['status'] == 'pending'
    changed = copy.deepcopy(index)
    changed['documents'][0]['text'] += '\n原文改动'
    result = check_run(root, changed)
    assert any(i['code'] == 'original_source_changed' for i in result['issues'])
    assert result['status'] == 'blocked'


def test_normal_model_failure_cannot_mask_altered_independent_baseline(tmp_path, monkeypatch):
    from scene_completion import interaction_cli
    root, index, _, _, _, _ = fixture_audit(tmp_path)
    write_json(root / 'sources_index.json', index)
    write_json(root / 'concern_baseline.json', baseline())
    write_json(root / 'run_manifest.json', {'protocol': PROTOCOL, 'complete': False,
        'source_hash': fingerprint(index), 'tool_versions': versions()})
    write_json(root / 'batches/interaction-model/manifest.json', {'stage': 'interaction-model', 'batches': [], 'input_hash': 'empty-model'})
    write_json(root / 'generator_base_identity.json', {'use_cases': []})
    write_json(root / 'scene_model.json', {'use_cases': []})
    def broken_model(*args):
        raise ValueError('normal model defect')
    monkeypatch.setattr(interaction_cli, 'merge_model', broken_model)
    frozen = read_json(root / 'existing_scenarios.json')
    frozen['scenarios'] = []
    write_json(root / 'existing_scenarios.json', frozen)
    result = check_run(root)
    assert any(i['detail'] == 'normal model defect' for i in result['issues'])
    assert any(i['code'] == 'altered_baseline' for i in result['issues'])
    assert not result['formally_accepted']


def test_changing_c_invalidates_its_audit(tmp_path):
    root, index, _, folder, packet, _ = fixture_audit(tmp_path)
    checker_folder = root / 'batches/interaction-checker'
    filename = checker_folder / 'results' / (packet['input']['checker_batch_id'] + '.json')
    raw = read_json(filename)
    raw['scenarios'][0]['trigger_condition'] = '另一个具体异常条件'
    write_json(filename, raw)
    with pytest.raises(ValueError, match='stale'):
        verify_checker_audit(root, index)


def test_stage_versions_isolate_unrelated_output_changes(tmp_path, monkeypatch):
    from scene_completion import interaction_batches as b, interaction_cli as cli
    from scene_completion.interaction_versions import packet_versions
    before_checker = packet_versions('interaction-checker')
    before_model = packet_versions('interaction-model')
    monkeypatch.setattr(cli, 'versions', lambda: {'report': 'changed'})
    assert packet_versions('interaction-checker') == before_checker
    def changed_binding(*args):
        raise ValueError('changed source binding rule')
    monkeypatch.setattr(b, 'validate_checker_binding', changed_binding)
    assert packet_versions('interaction-checker') != before_checker
    assert packet_versions('interaction-model') == before_model


def test_source_repair_preserves_raw_and_complete_feedback_without_editing_c(tmp_path):
    from scene_completion.semantic_backend import run_agent_packets
    root, index, _, folder, packet, result = fixture_audit(tmp_path)
    (root / 'existing_scenarios.json').unlink()  # fixture is now an unfrozen draft
    result['reviews'][0].update(source_supported=False, issues=['正常校验不是异常分支'] * 200)
    write_json(folder / 'results' / (packet['batch_id'] + '.json'), result)
    checker_folder = root / 'batches/interaction-checker'
    rejected = checker_folder / 'results' / (packet['input']['checker_batch_id'] + '.json')
    raw = read_json(rejected)
    selected = prepare_checker_repairs(root, index)
    assert selected == [packet['input']['checker_batch_id']] and not rejected.exists()
    attempt = read_json(next((checker_folder / 'attempts').glob('*source-audit*.json')))
    assert attempt['result'] == raw
    class Client:
        config = {'max_concurrency': 1, 'thinking': False}
        packets = []
        def model(self, kind):
            return 'ecnu-max'
        def agent(self, p):
            self.packets.append(p)
            return raw
    client = Client()
    assert run_agent_packets(checker_folder, client, checker_validator(index), batch_ids=selected)['complete']
    assert len(client.packets[0]['source_audit_feedback']['reviews'][0]['issues']) == 200
    assert 'previous_output' not in client.packets[0] and 'repair_instruction' not in client.packets[0]
    # Worker completion alone does not clear the failed source audit.
    with pytest.raises(ValueError, match='unresolved'):
        verify_checker_audit(root, index)


def test_frozen_c_cannot_be_mutated_by_repair(tmp_path):
    root, index, _, _, _, _ = fixture_audit(tmp_path)
    with pytest.raises(ValueError, match='frozen'):
        prepare_checker_repairs(root, index)
