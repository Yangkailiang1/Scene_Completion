"""Render actual layered SSD messages through the existing SVG renderer.

This presentation adapter does not infer operations, participants or returns.
The canonical SSD and concern mounts remain the authoritative graph inputs.
"""
from pathlib import Path
import re

from .svg_renderer import render_ssd_svg
from .schemas import stable_id


def diagram_stem(use_case_id, layer):
    if layer not in {'RR', 'SR', 'fused'}:
        raise ValueError('diagram layer must be RR, SR or fused')
    value = str(use_case_id)
    reserved = re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', value.split('.')[0], re.I)
    safe = (0 < len(value) <= 80 and value not in {'.', '..'} and not value.endswith(('.', ' '))
        and not reserved and not re.search(r'[<>:"/\\|?*\x00-\x1f]', value))
    return (value if safe else stable_id('SSD', value)) + '-' + layer


def render_interaction_ssd(ssd, use_case_id, layer, path):
    exchanges = {e['exchange_id']: e for e in ssd['exchanges']
        if e['use_case_id'] == use_case_id and (layer == 'fused' or e['requirement_layer'] == layer)}
    original = [m for m in ssd['messages'] if m['exchange_id'] in exchanges]
    participants = list(dict.fromkeys(m[key] for m in original for key in ('from_node', 'to_node')))
    nodes = {n['node_id']: n for n in ssd['nodes']}
    messages = []
    for number, message in enumerate(original):
        exchange = exchanges[message['exchange_id']]
        text = '[' + exchange['requirement_layer'] + '] ' + message['text']
        if message.get('fields'):
            text += '\n数据：' + '、'.join(message['fields'])
        if message.get('derived_data'):
            text += '\n查询语义推导（协议结构待确认）：' + '、'.join(row['field'] for row in message['derived_data'])
        if message['direction'] == 'request' and exchange.get('guard'):
            text += '\n条件：' + exchange['guard']
        messages.append({'from_node': message['from_node'], 'to_node': message['to_node'],
            'sequence': number, 'source_step_index': message['message_id'], 'message': text,
            'layer': exchange['requirement_layer'],
            'message_kind': 'response' if message['direction'] == 'response' else 'request'})
    view = {'use_case_id': use_case_id, 'layer': layer, 'messages': messages,
        'lifelines': [{'node_id': nid, 'label': nodes[nid]['name'] + ' (' + nodes[nid]['layer'] + ')'} for nid in participants]}
    return render_ssd_svg(view, {'system_composition': {'nodes': list(nodes.values())}}, Path(path))
