"""Role inputs and evidence checks have no shopping-system identity dependency."""
import copy

import pytest

from scene_completion.interaction_batches import (recommendation_packets, recommendation_validator,
    checker_packets, pair_packets)
from scene_completion.semantic_backend import read_json
from scene_completion.sources import index_sources, validate_refs


def test_positive_role_sources_exclude_guarantees_other_layers_and_exceptions(tmp_path):
    from scene_completion.interaction_batches import rr_positive_role_sources
    rr = tmp_path / 'clinic_rr.md'
    rr.write_text('# Clinic\n## Visit\nPrecondition\nPatient is registered.\n## Basic flow\n1. Patient requests appointment.\n2. System reserves appointment.\n## Exception scenario\n3. System fails to reserve.\n', encoding='utf-8')
    sr = tmp_path / 'clinic_sr.md'
    sr.write_text('# Clinic\n## Basic flow\n1. ReservationAPI calls RecordService.\n', encoding='utf-8')
    index = index_sources([rr, sr])
    for doc in index['documents']:
        doc['requirement_layer'] = 'RR' if doc['document'] == rr.name else 'SR'
    sections = [{'document': doc['document'], 'line_start': 1, 'line_end': doc['line_count']} for doc in index['documents']]
    rows = rr_positive_role_sources(index, sections)
    assert [(r['document'], r['line']) for r in rows] == [(rr.name, 6), (rr.name, 7)]


def test_known_sr_interface_alias_is_not_a_new_deployment_component():
    from scene_completion.interaction_cli import architecture_proposals
    base = {'use_cases': [{'use_case_id': 'BORROW', 'architecture': {'sr': {
        'service_name': '借阅服务', 'abstract_api_id': 'BOOK-BORROW'}}}]}
    value = {'nodes': [{'node_id': 'entry', 'name': 'BOOK-BORROW', 'kind': 'internal_service',
        'layer': 'SR', 'source_refs': []}, {'node_id': 'new', 'name': '外部信誉服务',
        'kind': 'external_service', 'layer': 'SR', 'source_refs': []}],
        'use_cases': [{'use_case_id': 'BORROW', 'exchanges': []}]}
    proposals = architecture_proposals(value, base)
    assert len(proposals) == 1 and proposals[0]['node_id'] == 'new'


def test_existing_external_actor_can_receive_its_authorized_rr_boundary_role():
    from scene_completion.interaction_cli import architecture_proposals
    base = {'use_cases': [], 'system_composition': {'nodes': [
        {'name': '外部回调服务', 'kind': 'external_service', 'layer': 'SR'}]}}
    nodes = [{'node_id': name, 'name': name, 'kind': 'external_service', 'layer': 'RR', 'source_refs': []}
        for name in ('外部回调服务', '新外部服务')]
    proposals = architecture_proposals({'nodes': nodes, 'use_cases': []}, base)
    assert len(proposals) == 1 and proposals[0]['node_id'] == '新外部服务'


def test_test_condition_skill_and_parser_are_actual_input_versions(tmp_path, monkeypatch):
    from scene_completion.interaction_batches import test_packets
    import scene_completion.assessment as parser
    from scene_completion.sources import fingerprint
    path = tmp_path / '验收.md'
    path.write_text('# Tests\n### T-1：借阅资源不存在\n场景类型：异常\n前置条件：已登录\n触发条件：资源不存在\n关联需求：BORROW\n测试目标：识别不存在资源\n预期结果：提示缺失\n来源定位：服务描述\n', encoding='utf-8')
    index = index_sources([path])
    folder = tmp_path / 'test-packets'
    manifest = test_packets({'use_cases': [{'use_case_id': 'BORROW'}]}, index, folder)
    packet = read_json(folder / 'packets' / (manifest['batches'][0]['batch_id'] + '.json'))
    assert '不得读取 G、C' in packet['input']['test_condition_skill']
    from pathlib import Path
    assert packet['input']['test_parser_version'] == fingerprint(Path(parser.__file__).read_text(encoding='utf-8'))
    assert not {'generated', 'checker', 'recommendations'} & set(packet['input'])
    original_read = Path.read_text
    def changed_parser_text(path, *args, **kwargs):
        text = original_read(path, *args, **kwargs)
        return text + '\n# changed extraction rule\n' if path.name == 'assessment.py' else text
    monkeypatch.setattr(Path, 'read_text', changed_parser_text)
    changed = test_packets({'use_cases': [{'use_case_id': 'BORROW'}]}, index, tmp_path / 'changed-test-packets')
    assert changed['input_hash'] != manifest['input_hash']


def test_representative_test_scope_keeps_all_related_types_without_layer_filter(tmp_path):
    from scene_completion.interaction_batches import test_packets
    path = tmp_path / 'tests.md'
    def record(number, uc, label):
        return (f'### T-{number}：资源场景\n场景类型：{label}\n前置条件：已登录\n'
            f'触发条件：资源不存在\n关联需求：{uc}\n测试目标：识别异常\n'
            '预期结果：提示缺失\n来源定位：原文\n')
    path.write_text('# Tests\n' + record(1, 'BORROW', '异常') + record(2, 'BORROW', '可选')
        + record(3, 'RETURN', '异常') + record(4, 'BORROW2', '异常'), encoding='utf-8')
    folder = tmp_path / 'packets'
    manifest = test_packets({'use_cases': [{'use_case_id': 'BORROW'}]}, index_sources([path]), folder)
    records = [r for batch in manifest['batches'] for r in read_json(
        folder / 'packets' / (batch['batch_id'] + '.json'))['input']['records']]
    assert len(records) == 2 and {r['requirements'] for r in records} == {'BORROW'}


@pytest.mark.parametrize('domain,rr_id,sr_id,field', [('图书借阅', 'READER-BORROW', 'LIBRARY-CHECK', 'bookCode'),
    ('影像审核', 'EDITOR-SUBMIT', 'MEDIA-REVIEW', 'assetVersion')])
def test_roles_load_skills_and_recommend_real_project_evidence(tmp_path, domain, rr_id, sr_id, field):
    rr, sr = tmp_path / '需求.md', tmp_path / '服务.md'
    rr.write_text(f'# {domain}\n## {rr_id}\n用户提交业务对象。\n', encoding='utf-8')
    sr.write_text(f'# 服务契约\n## {sr_id}\n{field} 是操作要求的字段。\n异常：字段缺失。\n', encoding='utf-8')
    index = index_sources([rr, sr])
    for doc, layer in zip(index['documents'], ('RR', 'SR')):
        doc['requirement_layer'] = layer
    ref = validate_refs([{'document': '服务.md', 'line_start': 3, 'line_end': 3}], index)
    candidate = {'scenario_id': 'G', 'requirement_layer': 'SR', 'use_case_id': rr_id,
        'layer_use_case_id': sr_id, 'exchange_id': 'exchange', 'scenario_type': 'exception',
        'exception_object': field, 'operation': domain, 'failure_mechanism': '字段缺失',
        'trigger_condition': field + ' 缺失', 'necessary_conditions': [], 'source_refs': ref}
    exchange = {'exchange_id': 'exchange', 'source_refs': ref, 'request_fields': [field], 'contracts': []}
    folder = tmp_path / 'recommend'
    manifest = recommendation_packets([candidate], {'exchanges': [exchange]}, folder, index)
    packet = read_json(folder / 'packets' / (manifest['batches'][0]['batch_id'] + '.json'))
    assert packet['input']['source_evidence'][0]['text'] == field + ' 是操作要求的字段。'
    assert all(s['requirement_layer'] == 'SR' for s in packet['input']['target_sections']['G'])
    assert '0.7' in packet['input']['recommendation_skill']
    raw = {'items': [{'scenario_id': 'G', 'support_score': .8, 'missing_score': 1,
        'support_reason': '契约字段和真实调用', 'missing_reason': '无对应 C 匹配', 'source_refs': ref,
        'suggested_sections': ref, 'recommendation': '服务.md → 服务契约 → 操作：建议补充异常'}]}
    assert recommendation_validator(index)(packet, raw)[0]['confidence'] == pytest.approx(.86)
    wrong = copy.deepcopy(raw)
    wrong['items'][0]['suggested_sections'] = [{'document': '需求.md', 'line_start': 3, 'line_end': 3}]
    with pytest.raises(ValueError, match='outside assigned'):
        recommendation_validator(index)(packet, wrong)
    base = {'use_cases': [{'use_case_id': rr_id, 'source_use_case_ids': {'SR': [sr_id]}}]}
    checker_folder = tmp_path / 'checker'
    manifest = checker_packets(base, index, checker_folder)
    for batch in manifest['batches']:
        checker = read_json(checker_folder / 'packets' / (batch['batch_id'] + '.json'))
        assert '检查' in checker['input']['checker_skill']
        assert not {'generated', 'generator_model', 'test'} & set(checker['input'])
    pairs_folder = tmp_path / 'pairs'
    manifest = pair_packets([candidate], [{**candidate, 'scenario_id': 'C'}], pairs_folder)
    pair = read_json(pairs_folder / 'packets' / (manifest['batches'][0]['batch_id'] + '.json'))
    assert '响应' in pair['input']['matching_skill']
    assert '2.0.0' in pair['input']['matching_skill']
