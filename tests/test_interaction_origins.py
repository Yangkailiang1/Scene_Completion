"""Control-flow provenance is checked before any exception is generated."""
from argparse import Namespace

import pytest

from scene_completion.interaction_origins import audit_model_origins, line_origins, normal_model_line_origins, run_model_repair
from scene_completion.sources import index_sources


def test_same_layer_positive_flow_not_participants_or_failure_returns(tmp_path):
    rr, sr = tmp_path / 'rr.md', tmp_path / 'sr.md'
    rr.write_text('# 需求\n## 用户操作\n5. 主成功路径：\n①系统更新摘要。\n6. 扩展路径：\n3.a 可选场景：不筛选，展示默认结果。\n', encoding='utf-8')
    sr.write_text('# Design\n## S-Update\n### Participants\n- SummaryService\n### Basic flow\n1. Entry calls SummaryService.\n### Alternative flows\n- A1: query failed; return cached result.\n- Optional scenario: use default ordering.\n', encoding='utf-8')
    index = index_sources([rr, sr])
    for doc, layer in zip(index['documents'], ('RR', 'SR')):
        doc['requirement_layer'] = layer
    def ref(name, line):
        return {'document': name, 'line_start': line, 'line_end': line}
    def exchange(eid, refs, kind='main_success'):
        return {'local_id': eid, 'requirement_layer': 'SR', 'path_type': kind, 'source_refs': refs, 'operation': 'update'}
    model = {'use_cases': [{'use_case_id': 'UserAction', 'exchanges': [
        exchange('valid', [ref('sr.md', 6)]),
        exchange('participant-only', [ref('rr.md', 4), ref('sr.md', 4)]),
        exchange('return-only', [ref('sr.md', 8)], 'alternative'),
        exchange('ordinary-optional', [ref('sr.md', 9)], 'alternative')]}]}
    outcome = audit_model_origins(model, index)
    assert {c['local_exchange_id']: c['passed'] for c in outcome['checks']} == {
        'valid': True, 'participant-only': False, 'return-only': False, 'ordinary-optional': True}
    assert not outcome['passed']
    assert outcome['checks'][1]['evidence'][0]['role'] == 'context'


def test_unknown_document_flow_structure_is_an_explicit_gap():
    assert line_origins('# Spec\n## Workflow\nCall a service.')[3] == 'context'
    assert line_origins('# Spec\n## Normal flow\nCall a service.')[3] == 'normal'


@pytest.mark.parametrize('title,path_type', [('## Basic flow', 'main_success'), ('## Alternative flows', 'alternative')])
def test_flow_heading_alone_never_supports_real_call(tmp_path, title, path_type):
    path = tmp_path / 'sr.md'
    path.write_text('# Use case\n' + title + '\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    model = {'use_cases': [{'use_case_id': 'Consult', 'exchanges': [{
        'local_id': 'invented', 'requirement_layer': 'SR', 'path_type': path_type, 'operation': 'invented call',
        'source_refs': [{'document': path.name, 'line_start': 2, 'line_end': 2}]}]}]}
    assert normal_model_line_origins(path.read_text(encoding='utf-8'))[2] == 'context'
    assert not audit_model_origins(model, index)['passed']


@pytest.mark.parametrize('body', [
    '## Exception scenario: lab unavailable\n1. UI displays fallback.\n',
    '## Alternative flows\nA1. Exception scenario: lab unavailable\n1. UI displays fallback.\n',
    '## Exception scenario: lab unavailable\n### Optional scenario: use cached data\n1. UI displays fallback.\n',
    '## Alternative flows\nA1. Exception scenario: lab unavailable\n### Optional scenario: use cached data\n1. UI displays fallback.\n'])
def test_exception_label_covers_numbered_continuation_not_ordinary_optional(tmp_path, body):
    path = tmp_path / 'sr.md'
    path.write_text('# Consult\n## Basic flow\n1. Read lab result.\n' + body, encoding='utf-8')
    text = path.read_text(encoding='utf-8')
    number = len(text.splitlines())
    assert normal_model_line_origins(text)[number] == 'abnormal'
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    model = {'use_cases': [{'use_case_id': 'Consult', 'exchanges': [], 'normal_scenarios': [
        {'name': 'Fallback', 'requirement_layer': 'SR', 'scenario_type': 'alternative',
         'source_refs': [{'document': path.name, 'line_start': number, 'line_end': number}]}]}]}
    fake = [{'use_case_id': 'Consult', 'passed': True, 'exchange_reviews': [],
        'scenario_reviews': [{'scenario_index': 0, 'supported': True}]}]
    result = audit_model_origins(model, index, fake)
    assert not result['passed'] and not result['checks'][0]['needs_semantic_branch_review']


@pytest.mark.parametrize('text,trigger_line', [
    ('# 用例\n2. 前置条件：\n已登录。\n3. 后置条件：\n已保存。\n4. 触发事件：\n医生确认预约。\n5. 主成功路径：\n①系统读取排班。\n6. 扩展路径：\n2.a 异常场景：排班已取消。', 7),
    ('# Appointment\n## Preconditions\nSigned in.\n## Triggering event\nClinician submits appointment.\n## Basic flow\n1. Read schedule.\n## Alternative flows\nA1. Schedule missing.', 5)])
def test_normal_trigger_is_positive_without_changing_checker_branch_origin(text, trigger_line, tmp_path):
    path = tmp_path / 'rr.md'
    path.write_text(text, encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    assert normal_model_line_origins(text)[trigger_line] == 'trigger'
    assert line_origins(text)[trigger_line] in {'context', 'precondition'}
    assert normal_model_line_origins(text)[len(text.splitlines())] in {'branch', 'abnormal'}
    assert line_origins(text)[len(text.splitlines())] == 'branch'
    model = {'use_cases': [{'use_case_id': 'Schedule', 'exchanges': [{'local_id': 'submit',
        'requirement_layer': 'RR', 'operation': 'submit appointment', 'path_type': 'main_success',
        'source_refs': [{'document': 'rr.md', 'line_start': trigger_line, 'line_end': trigger_line}]}]}]}
    assert audit_model_origins(model, index)['passed']


@pytest.mark.parametrize('branch', ['4.a 异常场景：用户退出，状态保持有效。',
    'A2. Exception scenario: visitor exits; return HTTP 200.'])
def test_explicit_exception_cannot_be_certified_as_ordinary_optional(tmp_path, branch):
    path = tmp_path / 'requirement.md'
    path.write_text('# Use case\n## Basic flow\n1. Start action.\n## Alternative flows\n' + branch + '\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'RR'
    model = {'use_cases': [{'use_case_id': 'Action', 'exchanges': [], 'normal_scenarios': [
        {'name': 'Exit', 'requirement_layer': 'RR', 'scenario_type': 'alternative',
         'source_refs': [{'document': path.name, 'line_start': 5, 'line_end': 5}]}]}]}
    fake = [{'use_case_id': 'Action', 'passed': True, 'exchange_reviews': [],
        'scenario_reviews': [{'scenario_index': 0, 'supported': True}]}]
    result = audit_model_origins(model, index, fake)
    assert line_origins(path.read_text(encoding='utf-8'))[5] == 'branch'
    assert not result['passed'] and not result['checks'][0]['needs_semantic_branch_review']


def test_handled_failure_cannot_be_a_normal_optional_scene(tmp_path):
    path = tmp_path / 'sr.md'
    path.write_text('# UseCase\n## Basic flow\n1. Read document.\n## Alternative flows\nA1. Document missing: display empty data with HTTP 200.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    model = {'use_cases': [{'use_case_id': 'ReadDocument', 'exchanges': [], 'normal_scenarios': [
        {'name': 'Missing document', 'requirement_layer': 'SR', 'scenario_type': 'alternative',
         'source_refs': [{'document': 'sr.md', 'line_start': 5, 'line_end': 5}]}]}]}
    checked = audit_model_origins(model, index)
    assert not checked['passed'] and checked['checks'][0]['normal_scenario_index'] == 0


def test_model_origin_repair_cannot_rewrite_existing_generated_set(tmp_path):
    (tmp_path / 'generated_scenarios.json').write_text('must never be read or rewritten')
    with pytest.raises(ValueError, match='G already exists'):
        run_model_repair(Namespace(output_dir=str(tmp_path)))
    assert (tmp_path / 'generated_scenarios.json').read_text() == 'must never be read or rewritten'


def test_unlabelled_ordinary_optional_requires_current_semantic_source_proof(tmp_path):
    path = tmp_path / 'sr.md'
    path.write_text('# S-Read\n## Basic flow\n1. Read data.\n## Alternative flows\nA1. Without filters, display all results.\n', encoding='utf-8')
    index = index_sources([path])
    index['documents'][0]['requirement_layer'] = 'SR'
    model = {'use_cases': [{'use_case_id': 'Read', 'exchanges': [], 'normal_scenarios': [
        {'name': 'Default results', 'requirement_layer': 'SR', 'scenario_type': 'alternative',
         'source_refs': [{'document': 'sr.md', 'line_start': 5, 'line_end': 5}]}]}]}
    pending = audit_model_origins(model, index)
    assert not pending['passed'] and pending['checks'][0]['needs_semantic_branch_review']
    # Internal helper receives already validated complete source audit rows;
    # replay additionally verifies actual raw packets/model identity and scope.
    proof = [{'use_case_id': 'Read', 'passed': True, 'exchange_reviews': [],
        'scenario_reviews': [{'scenario_index': 0, 'supported': True}]}]
    assert audit_model_origins(model, index, proof)['passed']
    proof[0]['passed'] = False
    assert not audit_model_origins(model, index, proof)['passed']


def test_source_only_model_gap_is_included_in_reextract_feedback(tmp_path, monkeypatch):
    from scene_completion import interaction_batches, interaction_cli, role_cli, semantic_backend
    from scene_completion.semantic_backend import write_json, read_json
    gap = {'use_case_id': 'LabOrder', 'description': 'Original unit mapping is uncertain',
        'source_refs': [{'document': 'lab.md', 'line_start': 4, 'line_end': 4}]}
    model = {'use_cases': [{'use_case_id': 'LabOrder', 'exchanges': [], 'normal_scenarios': []}],
        'model_gaps': [gap]}
    folder = tmp_path / 'batches/interaction-model'
    write_json(tmp_path / 'sources_index.json', {'documents': []})
    write_json(tmp_path / 'generator_base_identity.json', {'use_cases': [{'use_case_id': 'LabOrder'}]})
    write_json(folder / 'manifest.json', {'batches': [{'batch_id': 'model-lab'}]})
    write_json(folder / 'packets/model-lab.json', {'input': {'use_case_id': 'LabOrder'}})
    raw = {'normal_only': True}
    write_json(folder / 'results/model-lab.json', raw)
    (tmp_path / 'existing_scenarios.json').write_text('checker must never be read')
    monkeypatch.setattr(interaction_batches, 'model_validator', lambda index: lambda p, r: [{}])
    monkeypatch.setattr(semantic_backend, 'collect_packets', lambda *a: ([{}], {'complete': True}))
    monkeypatch.setattr(interaction_cli, 'merge_model', lambda *a: model)
    class Client:
        def model(self, kind):
            return 'ecnu-max'
    monkeypatch.setattr(role_cli, '_client', lambda *a: Client())
    selected = []
    def worker(folder, client, validator, batch_ids):
        selected.extend(batch_ids)
        return {'complete': False}
    monkeypatch.setattr(semantic_backend, 'run_agent_packets', worker)
    report, code = run_model_repair(Namespace(output_dir=str(tmp_path)))
    assert code == 2 and selected == report['repaired_batch_ids'] == ['model-lab']
    record = read_json(next((folder / 'attempts').glob('*.json')))
    assert record['result'] == raw
    assert record['model_origin_feedback'][0]['semantic_source_audit']['unresolved_model_gaps'] == [gap]
    assert (tmp_path / 'existing_scenarios.json').read_text() == 'checker must never be read'


@pytest.mark.parametrize('audit_complete', [False, True])
def test_selected_source_repair_preserves_unselected_use_case_even_with_failed_audit(tmp_path, monkeypatch, audit_complete):
    from scene_completion import interaction_batches, interaction_cli, interaction_origins
    from scene_completion import interaction_graph_checks, interaction_model_audit, interaction_source_review
    from scene_completion import role_cli, semantic_backend
    from scene_completion.semantic_backend import read_json, write_json
    folder = tmp_path / 'batches/interaction-model'
    audit_folder = tmp_path / 'batches/interaction-model-audit'
    cases = ['LabOrder', 'ReadResults']
    model = {'use_cases': [{'use_case_id': uc, 'exchanges': [], 'normal_scenarios': []} for uc in cases],
        'model_gaps': [{'use_case_id': uc, 'description': 'Uncertain source anchor'} for uc in cases]}
    write_json(tmp_path / 'sources_index.json', {'documents': []})
    write_json(tmp_path / 'generator_base_identity.json', model)
    write_json(folder / 'manifest.json', {'batches': [{'batch_id': uc} for uc in cases]})
    for uc in cases:
        write_json(folder / 'packets' / (uc + '.json'), {'input': {'use_case_id': uc}})
        write_json(folder / 'results' / (uc + '.json'), {'original': uc})
    write_json(audit_folder / 'manifest.json', {'current': True})
    monkeypatch.setattr(interaction_batches, 'model_validator', lambda index: lambda p, r: [])
    monkeypatch.setattr(interaction_cli, 'merge_model', lambda *args: model)
    rows = [{'model_batch_id': uc, 'passed': False,
        'unreviewed_defect': 'Invent an unsupported field to satisfy a mistaken audit'} for uc in cases]
    monkeypatch.setattr(semantic_backend, 'collect_packets', lambda path, validator:
        (rows, {'complete': audit_complete}) if path == audit_folder else ([{}], {'complete': True}))
    monkeypatch.setattr(interaction_model_audit, 'model_audit_packets', lambda *args, **kwargs: {'current': True})
    monkeypatch.setattr(interaction_model_audit, 'model_audit_validator', lambda *args: None)
    monkeypatch.setattr(interaction_source_review, 'source_review_feedback', lambda *args:
        {'LabOrder': [{'finding_id': 'source-lab', 'source_only': True}]})
    monkeypatch.setattr(interaction_origins, 'audit_model_origins', lambda *args:
        {'checks': [{'use_case_id': uc, 'passed': False} for uc in cases]})
    monkeypatch.setattr(interaction_graph_checks, 'check_graph_anchors', lambda *args:
        {'checks': [{'use_case_id': uc, 'code': 'missing_anchor'} for uc in cases]})
    class Client:
        def model(self, kind):
            return 'ecnu-max'
    monkeypatch.setattr(role_cli, '_client', lambda *args: Client())
    monkeypatch.setattr(semantic_backend, 'run_agent_packets', lambda *args, **kwargs: {'complete': True})
    report, _ = run_model_repair(Namespace(output_dir=str(tmp_path), source_review_file='source-review.json',
        source_finding_id=['source-lab']))
    assert report['repaired_batch_ids'] == ['LabOrder']
    assert report['complete'] is False
    assert read_json(folder / 'results/ReadResults.json') == {'original': 'ReadResults'}
    assert not list((folder / 'attempts').glob('ReadResults*'))
    record = read_json(next((folder / 'attempts').glob('LabOrder*')))
    assert 'unreviewed_defect' not in repr(record['model_origin_feedback'])
    assert 'source-lab' in repr(record['model_origin_feedback'])
def test_new_numbered_optional_heading_ends_inline_exception_not_exception_ancestor():
    from scene_completion.interaction_origins import normal_model_line_origins
    ordinary = '# Use case\n## Alternative flows\nA1. Exception scenario: no permission.\n### A2. Default to all results\nCall the search service without filters.\n'
    assert normal_model_line_origins(ordinary)[5] == 'branch'
    labelled = ordinary.replace('A2. Default', 'A2. Optional scenario: default')
    assert normal_model_line_origins(labelled)[5] == 'branch'
    exceptional = '# Use case\n## Exception scenario\nDenied request.\n### A2. Optional scenario: default\nCall the search service without filters.\n'
    assert normal_model_line_origins(exceptional)[5] == 'abnormal'
