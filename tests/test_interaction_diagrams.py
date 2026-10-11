"""Rendered SSD keeps actual message order and resource-service lifelines."""
from copy import deepcopy
import xml.etree.ElementTree as ET

from scene_completion.interaction_diagrams import render_interaction_ssd
from scene_completion.interaction_protocol import build_ssd
from tests.test_interaction_protocol import sources, model


def test_svg_preserves_nested_messages_and_wrapped_databases(sources, tmp_path):
    ssd = build_ssd(model(sources))
    original = deepcopy(ssd)
    path = render_interaction_ssd(ssd, 'UC-1', 'fused', tmp_path / 'fused.svg')
    root = ET.parse(path).getroot()
    ns = {'s': 'http://www.w3.org/2000/svg'}
    texts = [t.text or '' for t in root.findall('s:text', ns)]
    content = ''.join(texts)
    assert 'productId' in content and '数据：' in content
    assert '内部数据库 (AR)' not in content and '外部数据库 (AR)' not in content
    nodes = {n['node_id']: n for n in ssd['nodes']}
    assert all(nodes[r['resource_service_id']]['name'] in content for r in ssd['resource_service_mappings'])
    message_positions = [content.index(m['message_id']) for m in ssd['messages']]
    assert message_positions == sorted(message_positions)
    lines = root.findall('s:line', ns)
    assert sum(line.get('stroke-dasharray') == '7,5' for line in lines) == len(ssd['exchanges'])
    assert ssd == original


def test_rr_svg_has_only_its_own_messages_and_no_sr_protocol_fields(sources, tmp_path):
    ssd = build_ssd(model(sources))
    root = ET.parse(render_interaction_ssd(ssd, 'UC-1', 'RR', tmp_path / 'rr.svg')).getroot()
    content = ''.join(root.itertext())
    assert 'productId' not in content
    for message in ssd['messages']:
        exchange = next(e for e in ssd['exchanges'] if e['exchange_id'] == message['exchange_id'])
        assert (message['message_id'] in content) == (exchange['requirement_layer'] == 'RR')


def test_logical_query_result_keeps_derived_marker_on_actual_response(sources, tmp_path):
    source_model = model(sources)
    exchange = source_model['use_cases'][0]['exchanges'][2]
    marker = {'field':'product query result', 'derivation_reason':'Documented query; structure unspecified.',
        'evidence_quote':'读取商品', 'source_refs':exchange['source_refs'], 'protocol_structure_unknown':True}
    exchange.update(operation_kinds=['read'], response_fields=[marker['field']], derived_response_data=[marker])
    before = deepcopy(source_model)
    ssd = build_ssd(source_model)
    actual = next(e for e in ssd['exchanges'] if e['local_id'] == 'sr2')
    messages = [m for m in ssd['messages'] if m['exchange_id'] == actual['exchange_id']]
    assert len(messages) == 2
    assert next(m for m in messages if m['direction'] == 'request')['derived_data'] == []
    assert next(m for m in messages if m['direction'] == 'response')['derived_data'] == [marker]
    content = ''.join(ET.parse(render_interaction_ssd(ssd, 'UC-1', 'SR', tmp_path / 'derived.svg')).getroot().itertext())
    assert '查询语义推导（协议结构待确认）' in content and marker['field'] in content
    assert source_model == before


def test_cross_project_ids_cannot_escape_diagram_output_directory(sources, tmp_path):
    from scene_completion.interaction_reports import write_diagrams
    from scene_completion.interaction_diagrams import diagram_stem
    ssd = build_ssd(model(sources))
    for exchange in ssd['exchanges']:
        exchange['use_case_id'] = '../../clinic:visit'
    folder = tmp_path / 'diagrams'
    write_diagrams(folder, ssd, [])
    assert len(list(folder.glob('*.svg'))) == 3
    from scene_completion.semantic_backend import read_json
    records = read_json(folder / 'ssd_diagram_files.json')
    assert {record['use_case_id'] for record in records} == {'../../clinic:visit'}
    assert all((folder / record['svg']).is_file() for record in records)
    assert not (tmp_path / 'clinic:visit-fused.svg').exists()
    assert diagram_stem('UC-1', 'RR') == 'UC-1-RR'
    assert all(':' not in diagram_stem(value, 'SR') and '/' not in diagram_stem(value, 'SR')
        for value in ('../../clinic:visit', 'CON', 'NUL.txt', 'visit.'))
