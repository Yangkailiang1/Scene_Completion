"""Offline, single-row repair for an invalid normal-model hierarchy source ID."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from .semantic_backend import read_json
from .sources import fingerprint


_ERROR = re.compile(
    r"^hierarchy source_id must occur in its cited original text/chapter or be its exact document:Lline anchor: "
    r"unit=(?P<unit>[^;]+); source_id=(?P<source>.+)$")
_PATCH_VERSION = 'normal-hierarchy-source-id-v1'
_ALLOWED_CHANGES = {'name', 'source_id', 'source_refs'}
_MAX_PAYLOAD_BYTES = 8000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _packet_identity(packet):
    return fingerprint({key: value for key, value in packet.items()
        if key not in {'batch_id', 'input_hash'}})


def _load_original(packet_path, attempt_path, prior_raw, error):
    packet_path = Path(packet_path).resolve()
    attempt_path = Path(attempt_path).resolve()
    packet = read_json(packet_path)
    shell = read_json(attempt_path)
    raw = shell.get('result') if isinstance(shell, dict) else None
    if not isinstance(packet, dict) or packet.get('stage') != 'interaction-model':
        raise ValueError('normal patch source packet must be an interaction-model packet')
    batch_id = packet.get('batch_id')
    input_hash = packet.get('input_hash')
    if (not isinstance(batch_id, str) or not batch_id or input_hash != _packet_identity(packet)
            or packet_path.name != batch_id + '.json' or packet_path.parent.name != 'packets'):
        raise ValueError('original normal packet identity is invalid')
    if (attempt_path.parent.name != 'attempts' or not attempt_path.name.startswith(batch_id + '-')
            or not isinstance(raw, dict) or raw != prior_raw
            or not isinstance(shell.get('validation_error'), str)):
        raise ValueError('prior normal attempt is not the supplied rejected execution')
    if raw.get('batch_id') != batch_id or raw.get('input_hash') != input_hash:
        raise ValueError('prior normal result is not bound to the original packet')
    from .interaction_execution_identity import validate_result_execution
    validate_result_execution(raw, result_path=attempt_path)
    return packet, shell, raw, packet_path, attempt_path


def _matches_error(error):
    return _ERROR.fullmatch(error) if isinstance(error, str) else None


def _line_map(section):
    lines = {}
    for text in str(section.get('numbered_text', '')).splitlines():
        match = re.match(r'^\s*(\d+):\s?(.*)$', text)
        if match:
            lines[int(match.group(1))] = match.group(2)
    return lines


def _make_snippets(packet, row, source_id):
    """Select only exact normal packet source lines near refs and source labels."""
    data = packet.get('input', {})
    sections = [*data.get('sections', []), *data.get('context_sections', [])]
    refs = row.get('source_refs', [])
    if not isinstance(refs, list) or not refs:
        return None
    selected_by_section = {}
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        lines = _line_map(section)
        if not lines:
            continue
        chosen = set()
        # Keep all original cited text plus a small line neighborhood.
        for ref in refs:
            if ref.get('document') != section.get('document'):
                continue
            start, end = ref.get('line_start'), ref.get('line_end')
            if type(start) is not int or type(end) is not int:
                continue
            if not all(number in lines for number in range(start, end + 1)):
                continue
            chosen.update(range(max(min(lines), start - 2), min(max(lines), end + 2) + 1))
        # Include source-ID and original-name occurrences elsewhere in this
        # packet's allowed normal source context, with nearby lines.
        needles = [value for value in (source_id, row.get('name'))
            if isinstance(value, str) and value.strip()]
        for number, text in lines.items():
            if any(needle in text for needle in needles):
                chosen.update(range(max(min(lines), number - 2), min(max(lines), number + 2) + 1))
        chosen.intersection_update(lines)
        if chosen:
            selected_by_section[index] = (section, lines, chosen)

    snippets = []
    for index in sorted(selected_by_section):
        section, lines, chosen = selected_by_section[index]
        ordered = sorted(chosen)
        groups = []
        for number in ordered:
            if not groups or number != groups[-1][-1] + 1:
                groups.append([number])
            else:
                groups[-1].append(number)
        for group in groups:
            snippets.append({'document': section['document'],
                'requirement_layer': section.get('requirement_layer'),
                'heading_path': copy.deepcopy(section.get('heading_path', [])),
                'line_start': group[0], 'line_end': group[-1],
                'numbered_text': '\n'.join(f'{n}: {lines[n]}' for n in group)})
    return snippets or None


def _validate_source_failure(packet, raw, error, index, unit_id, source_id):
    from .interaction_batches import model_validator
    result_rows = raw.get('use_case_hierarchy')
    if not isinstance(result_rows, list):
        return False
    targets = [row for row in result_rows if isinstance(row, dict) and row.get('unit_id') == unit_id]
    if len(targets) != 1 or targets[0].get('source_id') != source_id:
        return False
    try:
        model_validator(index)(packet, copy.deepcopy(raw))
    except (ValueError, KeyError, TypeError) as exc:
        return str(exc) == error
    return False


def prepare(packet, prior_raw, original_packet_path, original_result_path, error, index):
    """Prepare one targeted replacement, or return None if scope/evidence is insufficient."""
    match = _matches_error(error)
    if not match:
        return None
    source_packet, shell, raw, packet_path, attempt_path = _load_original(
        original_packet_path, original_result_path, prior_raw, error)
    if packet != source_packet:
        raise ValueError('normal patch packet differs from its original source packet')
    unit_id, source_id = match.group('unit'), match.group('source')
    if not _validate_source_failure(source_packet, raw, error, index, unit_id, source_id):
        return None
    rows = raw['use_case_hierarchy']
    original_rows = [row for row in rows if row['unit_id'] == unit_id]
    if len(original_rows) != 1:
        return None
    original_row = copy.deepcopy(original_rows[0])
    snippets = _make_snippets(source_packet, original_row, source_id)
    if not snippets:
        return None
    payload = {'use_case_id': source_packet['input'].get('use_case_id'),
        'normal_item_patch': {
            'version': _PATCH_VERSION,
            'target_collection': 'use_case_hierarchy',
            'unit_id': unit_id,
            'rejected_source_id': source_id,
            'validation_error': error,
            'original_row': original_row,
            'original_row_hash': fingerprint(original_row),
            'visible_source_snippets': snippets,
            'original_packet_path': str(packet_path),
            'original_packet_sha256': _sha256(packet_path),
            'original_packet_batch_id': source_packet['batch_id'],
            'original_packet_input_hash': source_packet['input_hash'],
            'original_result_path': str(attempt_path),
            'original_result_sha256': _sha256(attempt_path),
            'prior_raw_result_hash': fingerprint(raw),
            'prior_validation_error': shell['validation_error'],
            'attempt_number': shell.get('attempt'),
        }}
    if len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf8')) > _MAX_PAYLOAD_BYTES:
        return None
    instructions = [
        'Repair exactly the one rejected use_case_hierarchy row identified by input.normal_item_patch.unit_id. Return one complete replacement row.',
        'Use only the supplied original normal RR/SR sections in visible_source_snippets. Do not use checker, test, exception, generated, or external answer content.',
        'Only name, source_id, and source_refs may change. Preserve unit_id, layer, parent_ids, and every other original row field exactly. Do not add, remove, merge, split, or rename any other hierarchy row, component, exchange, or scenario.',
        'Choose source_id only when the exact original identifier/name is supported by the supplied source lines. Cite only lines present in visible_source_snippets. If the source cannot support a correction, do not invent an identifier; leave source_id unchanged so offline validation rejects it.',
    ]
    contract = {'replacement': copy.deepcopy(original_row)}
    contract['replacement']['source_id'] = 'exact source-backed original identifier'
    contract['replacement']['name'] = 'original source-backed hierarchy name'
    contract['replacement']['source_refs'] = [{'document': 'supplied document',
        'line_start': 1, 'line_end': 1}]
    return {'payload': payload, 'instructions': instructions, 'contract': contract}


def _bound_patch_source(packet, index):
    data = packet.get('input', {})
    patch = data.get('normal_item_patch')
    if not isinstance(patch, dict) or patch.get('version') != _PATCH_VERSION:
        raise ValueError('normal item patch binding is missing or unsupported')
    error = patch.get('validation_error')
    source_packet_path, original_result_path = patch.get('original_packet_path'), patch.get('original_result_path')
    if not isinstance(source_packet_path, str) or not isinstance(original_result_path, str):
        raise ValueError('normal item patch source paths are missing')
    source_packet = read_json(Path(source_packet_path))
    shell = read_json(Path(original_result_path))
    raw = shell.get('result') if isinstance(shell, dict) else None
    rebuilt = prepare(source_packet, raw, source_packet_path, original_result_path, error, index)
    if rebuilt is None:
        raise ValueError('normal item patch no longer matches the current validator failure or source evidence')
    from .semantic_backend import compose_packet
    from .partial_packet_reuse import semantic_packet
    expected = compose_packet(source_packet['stage'], rebuilt['payload'],
        rebuilt['instructions'], rebuilt['contract'])
    if semantic_packet(packet) != semantic_packet(expected):
        raise ValueError('normal item patch packet differs from its bound source and scoped instructions')
    if packet.get('input_hash') != _packet_identity(packet):
        raise ValueError('normal item patch packet identity is invalid')
    return source_packet, shell, raw, patch, rebuilt


def source_packet(packet, index):
    """Expose the bound original sources to downstream model consumers."""
    if not packet.get('input', {}).get('normal_item_patch'):
        return packet
    return _bound_patch_source(packet, index)[0]


def validate(packet, result, index):
    """Validate one replacement and run the unchanged full normal validator on the merged output."""
    from .interaction_execution_identity import validate_result_execution
    from .interaction_batches import model_validator
    from .response_contract import ENVELOPE_METADATA

    source_packet, shell, prior_raw, patch, rebuilt = _bound_patch_source(packet, index)
    if not isinstance(result, dict) or result.get('batch_id') != packet.get('batch_id') \
            or result.get('input_hash') != packet.get('input_hash'):
        raise ValueError('normal item patch result is not bound to its prepared packet')
    validate_result_execution(result)
    semantic = {key: value for key, value in result.items() if key not in ENVELOPE_METADATA}
    if set(semantic) != {'replacement'} or not isinstance(semantic['replacement'], dict):
        raise ValueError('normal item patch must return exactly one complete replacement row')
    replacement = copy.deepcopy(semantic['replacement'])
    original_row = patch['original_row']
    if fingerprint(original_row) != patch.get('original_row_hash'):
        raise ValueError('normal item patch target row hash is invalid')
    if set(replacement) != set(original_row):
        raise ValueError('normal item patch replacement must preserve the complete original row shape')
    for key in set(original_row) - _ALLOWED_CHANGES:
        if replacement.get(key) != original_row.get(key):
            raise ValueError('normal item patch changed an immutable hierarchy field: ' + key)
    for key in ('name', 'source_id'):
        if not isinstance(replacement.get(key), str) or not replacement[key].strip():
            raise ValueError('normal item patch requires a nonempty ' + key)

    snippets = patch['visible_source_snippets']
    visible_sections = [{'document': row['document'], 'line_start': row['line_start'],
        'line_end': row['line_end'], 'heading_path': row.get('heading_path', [])} for row in snippets]
    from .sources import validate_refs
    refs = validate_refs(replacement.get('source_refs'), index, visible_sections)
    from .interaction_batches import source_identifier_supported
    if not source_identifier_supported(replacement['source_id'], refs, index):
        raise ValueError('replacement source_id is unsupported by its visible original citations')
    replacement['source_refs'] = refs

    expected_prior, _, _, _, _ = _load_original(patch['original_packet_path'],
        patch['original_result_path'], prior_raw, patch['validation_error'])
    merged_raw = copy.deepcopy(prior_raw)
    target_count = 0
    merged_rows = []
    for row in merged_raw['use_case_hierarchy']:
        if row.get('unit_id') == patch['unit_id']:
            target_count += 1
            merged_rows.append(copy.deepcopy(replacement))
        else:
            merged_rows.append(copy.deepcopy(row))
    if target_count != 1:
        raise ValueError('normal item patch target is no longer unique')
    merged_raw['use_case_hierarchy'] = merged_rows
    return model_validator(index)(expected_prior, merged_raw)
