"""Reuse proven individual packets when only execution metadata/prose changed."""
from copy import deepcopy
from pathlib import Path

from .semantic_backend import read_json, write_json
from .sources import fingerprint
from .response_contract import contract_view
from .interaction_execution_identity import validate_result_execution


EXECUTION_PARAGRAPHS = ('批量运行默认按用例的依赖通过后立即推进', '批量无法完成时',
    '批量语义模型从运行配置', '运行前先执行可用模型检查及配置')


def semantic_packet(packet):
    value = deepcopy(packet)
    for key in ('input_hash', 'batch_id'):
        value.pop(key, None)
    for key in ('execution_versions', 'test_parser_version'):
        value['input'].pop(key, None)
    for key in ('skill', 'generator_skill'):
        text = value['input'].get(key)
        if isinstance(text, str) and 'name: scene-concern-gap\n' in text:
            value['input'][key] = '\n\n'.join(p for p in text.split('\n\n')
                if not p.startswith(EXECUTION_PARAGRAPHS))
    return value


def reuse(folder, previous, validator, cache_identity):
    folder = Path(folder)
    current = read_json(folder / 'manifest.json')
    candidates = {}
    for row in previous.get('batches', []):
        packet = read_json(folder / 'packets' / (row['batch_id'] + '.json'))
        if fingerprint({k: v for k, v in packet.items() if k not in ('batch_id', 'input_hash')}) != row['input_hash']:
            raise ValueError('partial reuse original packet hash changed')
        candidates.setdefault(fingerprint(semantic_packet(packet)), []).append((row, packet))
    proofs = []
    for i, row in enumerate(current['batches']):
        packet = read_json(folder / 'packets' / (row['batch_id'] + '.json'))
        peers = candidates.get(fingerprint(semantic_packet(packet)), [])
        if len(peers) != 1:
            continue
        old, original = peers[0]
        path = folder / 'results' / (old['batch_id'] + '.json')
        if old == row or not path.is_file():
            continue
        try:
            raw = read_json(path)
            validate_result_execution(raw, result_path=path)
            cache_identity(raw)
            validator(original, contract_view(original, raw))
        except (ValueError, KeyError, TypeError):
            continue
        current['batches'][i] = old
        proofs.append({'original_batch_id': old['batch_id'], 'original_input_hash': old['input_hash'],
            'current_expected_hash': row['input_hash'], 'result_hash': fingerprint(raw),
            'semantic_input_hash': fingerprint(semantic_packet(packet))})
    if proofs:
        current['input_hash'] = fingerprint(current['batches'])
        write_json(folder / 'manifest.json', current)
        history = folder / 'compatible_packet_reuse.json'
        records = read_json(history) if history.exists() else []
        write_json(history, records + [p for p in proofs if p not in records])
    return proofs
