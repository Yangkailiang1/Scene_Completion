"""Offline, quote-only repair for rejected E/T normalization packets."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .semantic_backend import read_json
from .sources import fingerprint


_ERROR = 'normalization needs exact original abnormal scenario evidence'
_VERSION = 'normalization-evidence-quote-v1'
_MAX_PAYLOAD_BYTES = 8000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _packet_identity(packet):
    return fingerprint({key: value for key, value in packet.items()
        if key not in {'batch_id', 'input_hash'}})


def _load_original(packet_path, attempt_path, prior_raw):
    packet_path, attempt_path = Path(packet_path).resolve(), Path(attempt_path).resolve()
    packet, shell = read_json(packet_path), read_json(attempt_path)
    raw = shell.get('result') if isinstance(shell, dict) else None
    if not isinstance(packet, dict) or packet.get('stage') not in {'gap-normalize-E', 'gap-normalize-T'}:
        raise ValueError('normalization evidence source must be an E/T normalization packet')
    batch_id, input_hash = packet.get('batch_id'), packet.get('input_hash')
    if (not isinstance(batch_id, str) or not batch_id
            or input_hash != _packet_identity(packet)
            or packet_path.name != batch_id + '.json' or packet_path.parent.name != 'packets'):
        raise ValueError('original normalization packet identity is invalid')
    if (attempt_path.parent.name != 'attempts' or not attempt_path.name.startswith(batch_id + '-')
            or not isinstance(raw, dict) or raw != prior_raw
            or not isinstance(shell.get('validation_error'), str)):
        raise ValueError('prior normalization attempt is not the supplied rejected execution')
    if raw.get('batch_id') != batch_id or raw.get('input_hash') != input_hash:
        raise ValueError('prior normalization result is not bound to the original packet')
    from .interaction_execution_identity import validate_result_execution
    validate_result_execution(raw, result_path=attempt_path)
    return packet, shell, raw, packet_path, attempt_path


def _validator(index):
    from .concern_gap_batches import normalize_validator
    return normalize_validator(index)


def _target_failures(packet, raw, index):
    """Return quote-only failures after proving exact evidence edits resolve the whole packet."""
    data = packet.get('input', {})
    collection = data.get('collection')
    if collection not in {'E', 'T'} or packet.get('stage') != 'gap-normalize-' + collection:
        return None
    scenes = data.get('scenarios')
    items = raw.get('items')
    if not isinstance(scenes, list) or not isinstance(items, list):
        return None
    source_by_id = {scene.get('scenario_id'): scene for scene in scenes if isinstance(scene, dict)}
    if len(source_by_id) != len(scenes):
        return None

    failures = []
    preview = copy.deepcopy(raw)
    preview_items = preview.get('items', [])
    if len(preview_items) != len(source_by_id):
        return None
    seen = set()
    for item in preview_items:
        if not isinstance(item, dict):
            return None
        scenario_id = item.get('source_scenario_id')
        if scenario_id not in source_by_id or scenario_id in seen:
            return None
        seen.add(scenario_id)
        scene = source_by_id[scenario_id]
        units = item.get('units')
        if not isinstance(units, list):
            return None
        for unit_index, unit in enumerate(units):
            if not isinstance(unit, dict):
                return None
            quote = unit.get('evidence_quote')
            if not isinstance(quote, str) or not quote or not any(
                    quote in str(scene.get(field, '')) for field in ('trigger_condition', 'failure_mechanism')):
                trigger = scene.get('trigger_condition')
                if not isinstance(trigger, str) or not trigger.strip():
                    return None
                failures.append({'source_scenario_id': scenario_id, 'unit_index': unit_index,
                    'exact_trigger_condition': trigger})
                unit['evidence_quote'] = trigger
    if not failures:
        return None

    # Only a deterministic evidence-string substitution may make this packet pass.
    try:
        _validator(index)(packet, preview)
    except (ValueError, KeyError, TypeError):
        return None
    return failures


def _is_evidence_failure(packet, raw, error, index):
    if not isinstance(error, str) or not error.startswith(_ERROR):
        return None
    try:
        _validator(index)(packet, copy.deepcopy(raw))
    except (ValueError, KeyError, TypeError) as exc:
        if str(exc) != _ERROR:
            return None
    else:
        return None
    return _target_failures(packet, raw, index)


def prepare(packet, prior_raw, original_packet_path, original_result_path, error, index):
    """Prepare a quote-only patch, or return None unless that alone fixes validation."""
    if not isinstance(packet, dict) or packet.get('stage') not in {'gap-normalize-E', 'gap-normalize-T'}:
        return None
    source_packet, shell, raw, packet_path, attempt_path = _load_original(
        original_packet_path, original_result_path, prior_raw)
    if packet != source_packet:
        raise ValueError('normalization patch packet differs from its original source packet')
    failures = _is_evidence_failure(source_packet, raw, error, index)
    if not failures:
        return None
    sources = {scene['scenario_id']: scene for scene in source_packet['input']['scenarios']}
    units = []
    for failed in failures:
        scene = sources[failed['source_scenario_id']]
        units.append({'source_scenario_id': failed['source_scenario_id'],
            'unit_index': failed['unit_index'],
            'scene_text': {key: copy.deepcopy(scene.get(key)) for key in (
                'scenario_id', 'name', 'exception_object', 'operation', 'failure_mechanism',
                'trigger_condition', 'necessary_conditions', 'source_refs', 'original_condition_quote')
                if key in scene}})
    payload = {'normalization_evidence_patch': {
        'version': _VERSION, 'collection': source_packet['input']['collection'],
        'validation_error': error, 'failed_units': units,
        'original_packet_path': str(packet_path), 'original_packet_sha256': _sha256(packet_path),
        'original_packet_batch_id': source_packet['batch_id'],
        'original_packet_input_hash': source_packet['input_hash'],
        'original_result_path': str(attempt_path), 'original_result_sha256': _sha256(attempt_path),
        'prior_raw_result_hash': fingerprint(raw),
        'prior_validation_error': shell['validation_error'],
        'attempt_number': shell.get('attempt'),
    }}
    if len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')) > _MAX_PAYLOAD_BYTES:
        return None
    instructions = [
        'Repair only the listed normalization evidence_quote fields. Return one evidence_quotes entry for every listed source_scenario_id and unit_index, and no other fields.',
        'For each entry copy the complete exact trigger_condition from that entry scene_text. Do not paraphrase, infer, translate, alter, or add any content.',
        'Do not change any unit field other than evidence_quote. Do not create identifiers, diagnostic IDs, or facts.',
    ]
    contract = {'evidence_quotes': [{'source_scenario_id': row['source_scenario_id'],
        'unit_index': row['unit_index'], 'evidence_quote': row['scene_text']['trigger_condition']}
        for row in units]}
    return {'payload': payload, 'instructions': instructions, 'contract': contract}


def _bound_patch_source(packet, index):
    patch = packet.get('input', {}).get('normalization_evidence_patch')
    if not isinstance(patch, dict) or patch.get('version') != _VERSION:
        raise ValueError('normalization evidence patch binding is missing or unsupported')
    source_path, attempt_path = patch.get('original_packet_path'), patch.get('original_result_path')
    if not isinstance(source_path, str) or not isinstance(attempt_path, str):
        raise ValueError('normalization evidence patch source paths are missing')
    source_packet, shell = read_json(Path(source_path)), read_json(Path(attempt_path))
    raw = shell.get('result') if isinstance(shell, dict) else None
    rebuilt = prepare(source_packet, raw, source_path, attempt_path, patch.get('validation_error'), index)
    if rebuilt is None:
        raise ValueError('normalization evidence patch no longer matches the current validator failure')
    from .semantic_backend import compose_packet
    from .partial_packet_reuse import semantic_packet
    expected = compose_packet(source_packet['stage'], rebuilt['payload'],
        rebuilt['instructions'], rebuilt['contract'])
    if semantic_packet(packet) != semantic_packet(expected):
        raise ValueError('normalization evidence patch packet differs from its bound source and instructions')
    if packet.get('input_hash') != _packet_identity(packet):
        raise ValueError('normalization evidence patch packet identity is invalid')
    return source_packet, raw, patch, rebuilt


def validate(packet, result, index):
    """Apply only exact trigger quotations, then run the unchanged full normalizer."""
    from .interaction_execution_identity import validate_result_execution
    from .response_contract import ENVELOPE_METADATA

    source_packet, prior_raw, patch, rebuilt = _bound_patch_source(packet, index)
    if (not isinstance(result, dict) or result.get('batch_id') != packet.get('batch_id')
            or result.get('input_hash') != packet.get('input_hash')):
        raise ValueError('normalization evidence patch result is not bound to its packet')
    validate_result_execution(result)
    semantic = {key: value for key, value in result.items() if key not in ENVELOPE_METADATA}
    if set(semantic) != {'evidence_quotes'} or not isinstance(semantic['evidence_quotes'], list):
        raise ValueError('normalization evidence patch must return only evidence_quotes')

    expected = {(row['source_scenario_id'], row['unit_index']): row['scene_text']['trigger_condition']
        for row in rebuilt['payload']['normalization_evidence_patch']['failed_units']}
    replacements = {}
    for row in semantic['evidence_quotes']:
        if not isinstance(row, dict) or set(row) != {'source_scenario_id', 'unit_index', 'evidence_quote'}:
            raise ValueError('each evidence patch row must contain exactly source_scenario_id, unit_index, evidence_quote')
        key = (row['source_scenario_id'], row['unit_index'])
        if key not in expected or key in replacements:
            raise ValueError('normalization evidence patch contains an unknown or duplicate unit')
        if row['evidence_quote'] != expected[key]:
            raise ValueError('normalization evidence patch must copy the exact original trigger_condition')
        replacements[key] = row['evidence_quote']
    if set(replacements) != set(expected):
        raise ValueError('normalization evidence patch omitted a rejected unit')

    merged = copy.deepcopy(prior_raw)
    items = {row['source_scenario_id']: row for row in merged['items']}
    for (scenario_id, unit_index), quote in replacements.items():
        item = items.get(scenario_id)
        if not isinstance(item, dict) or not isinstance(item.get('units'), list) or unit_index >= len(item['units']):
            raise ValueError('normalization evidence patch target is no longer present')
        item['units'][unit_index]['evidence_quote'] = quote

    from .concern_gap_batches import normalize_validator
    return normalize_validator(index)(source_packet, merged)
