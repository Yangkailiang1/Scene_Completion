"""Versioned, lossless request views; source packets remain validator inputs.

This is an execution representation, not semantic retrieval. Every assigned
record survives; common values are readable once in the same request.
"""
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import fnmatch
import json
from pathlib import Path

from .sources import fingerprint

PROFILE = 'compact-v1'
_settings = ContextVar('scene_context_settings', default={})
MARKER = '$context_ref_v1'
ESCAPE = '$context_literal_v1'
RULE = ('Resolve every {$context_ref_v1: ID} from context_values in THIS request before analysis. '
        '{$context_literal_v1: [[key,value],...]} restores a literal object. References preserve '
        'all values and their original roles: original_evidence/source_sections are source facts; '
        'scenarios/original_scenarios/units are scenario descriptions or deductions, not source facts; '
        'pending_details remain unknown. Inspect every coverage.required_item_ids entry. '
        'Do not interpret a reference as missing evidence or treat a generated claim as source proof.')


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf8'))


@contextmanager
def settings(config):
    profile = config.get('context_profile', 'legacy')
    if profile not in ('legacy', PROFILE):
        raise ValueError('context_profile must be legacy or compact-v1')
    token = _settings.set({k: deepcopy(config[k]) for k in
        ('context_profile', 'stage_request_bytes') if k in config})
    try:
        yield
    finally:
        _settings.reset(token)


def configured(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with settings(getattr(getattr(self, 'client', None), 'config', {})):
            return method(self, *args, **kwargs)
    return wrapped


def active():
    return _settings.get().get('context_profile') == PROFILE


def bind(packet):
    """Changing the request view changes the prepared packet's real identity."""
    if not active():
        return packet
    packet = deepcopy(packet)
    packet['context_policy'] = {'profile': PROFILE,
        'implementation_hash': fingerprint(Path(__file__).read_text(encoding='utf8'))}
    return packet


def _rules(text):
    start, end = '<!-- batch-rules:start -->', '<!-- batch-rules:end -->'
    if isinstance(text, str) and start in text and end in text:
        return text.split(start, 1)[1].split(end, 1)[0].strip()
    return text


def coverage(data):
    field = next((k for k in ('units', 'scenarios', 'mounts', 'records')
        if isinstance(data.get(k), list)), None)
    rows = data.get(field, []) if field else []
    ids = [str(next((r[k] for k in ('unit_id', 'scenario_id', 'mount_id', 'test_scenario_id', 'id')
        if r.get(k)), i)) for i, r in enumerate(rows) if isinstance(r, dict)]
    missing = []
    if field == 'units' and 'original_scenarios' in data:
        sources = {r['scenario_id'] for r in data['original_scenarios']}
        missing = sorted({u['source_scenario_id'] for u in rows
            if u.get('source_scenario_id') not in sources})
    return {'item_field': field, 'required_item_ids': ids,
        'use_case_ids': sorted({r['use_case_id'] for r in rows if isinstance(r, dict) and r.get('use_case_id')}),
        'exchange_ids': sorted({r['exchange_id'] for r in rows if isinstance(r, dict) and r.get('exchange_id')}),
        'mount_ids': sorted({r['mount_id'] for r in rows if isinstance(r, dict) and r.get('mount_id')}),
        'material_fields': sorted(data),
        'source_evidence_count': len(data.get('original_evidence', [])),
        'quote_reference_count': len(data.get('evidence_catalog', [])),
        'missing_dependencies': missing,
        'permitted_material_hash': fingerprint(data)}


def project(packet):
    """Return a lossless shared-value view and non-semantic size measurements."""
    original = deepcopy(packet)
    policy = original.get('context_policy', {})
    if not policy:
        return original, {'profile': 'legacy', 'original_bytes': size(original), 'wire_bytes': size(original)}
    if policy.get('profile') != PROFILE:
        raise ValueError('unsupported context policy')
    if policy.get('implementation_hash') != fingerprint(Path(__file__).read_text(encoding='utf8')):
        raise ValueError('context projection implementation changed; prepare a new packet instead of relabeling execution')
    data = original.get('input', {})
    # T historically supplies the exact same Skill twice. Keep one actual rule.
    if data.get('test_condition_skill') == data.get('skill'):
        data.pop('test_condition_skill', None)
    for key in ('skill', 'generator_skill'):
        if key in data:
            text = data[key]
            # The concern-gap marker is a generation subsection. Comparison
            # and other roles must retain their own method rather than inherit
            # an unrelated stage summary.
            if (not isinstance(text, str) or 'name: scene-concern-gap\n' not in text
                    or packet.get('stage') in ('gap-generation', 'interaction-generation')):
                data[key] = _rules(text)
    view_coverage = coverage(data)
    if view_coverage['missing_dependencies']:
        raise ValueError('context dependency missing: ' + ', '.join(view_coverage['missing_dependencies']))
    counts, values = Counter(), {}
    def count(value):
        if isinstance(value, (dict, str)) and size(value) >= 96:
            key = fingerprint(value)
            counts[key] += 1
            values[key] = value
        if isinstance(value, dict):
            for v in value.values(): count(v)
        elif isinstance(value, list):
            for v in value: count(v)
    count(original)
    shared = {}
    names = {key: 'C' + str(i) for i, key in enumerate(sorted(k for k, n in counts.items() if n > 1))}
    def encode(value, allow=True):
        key = fingerprint(value) if isinstance(value, (dict, str)) and size(value) >= 96 else None
        if allow and key and counts[key] > 1:
            ref = names[key]
            if ref not in shared:
                shared[ref] = encode(value, False)
            return {MARKER: ref}
        if isinstance(value, dict):
            if set(value) in ({MARKER}, {ESCAPE}):
                return {ESCAPE: [[k, encode(v)] for k, v in value.items()]}
            return {k: encode(v) for k, v in value.items()}
        if isinstance(value, list): return [encode(v) for v in value]
        return value
    packed = encode(original)
    packed.update(context_values=shared, context_value_rule=RULE, coverage=view_coverage)
    # A small packet may cost more to intern; retain the readable ordinary view.
    plain = {**original, 'coverage': view_coverage}
    wire = packed if size(packed) < size(plain) else plain
    return wire, {'profile': PROFILE, 'original_bytes': size(packet), 'wire_bytes': size(wire),
        'estimated_input_tokens_upper_bound': size(wire),
        'token_estimate_basis': 'utf8_byte_upper_bound_not_provider_usage',
        'shared_value_count': len(shared) if wire is packed else 0, 'coverage': view_coverage}


def expand(wire):
    """Offline roundtrip verification; rejects broken or circular references."""
    if 'context_value_rule' not in wire:
        return {k: deepcopy(v) for k, v in wire.items() if k != 'coverage'}
    shared = wire.get('context_values', {})
    def visit(value, seen=()):
        if isinstance(value, dict):
            if set(value) == {MARKER}:
                key = value[MARKER]
                if key not in shared or key in seen: raise ValueError('invalid context reference')
                return visit(shared[key], (*seen, key))
            if set(value) == {ESCAPE}: return {k: visit(v, seen) for k, v in value[ESCAPE]}
            return {k: visit(v, seen) for k, v in value.items()}
        if isinstance(value, list): return [visit(v, seen) for v in value]
        return value
    return {k: visit(v) for k, v in wire.items() if k not in ('context_values', 'context_value_rule', 'coverage')}


def byte_limit(stage):
    rules = _settings.get().get('stage_request_bytes', {})
    if not isinstance(rules, dict) or any(not isinstance(k, str) or type(v) is not int or v < 1024 for k, v in rules.items()):
        raise ValueError('stage_request_bytes must map stage patterns to byte limits >=1024')
    if stage in rules: return rules[stage]
    matches = [(sum(c not in '*?[]' for c in k), v) for k, v in rules.items() if fnmatch.fnmatchcase(stage, k)]
    if not matches: return None
    best = max(k for k, _ in matches)
    values = {v for k, v in matches if k == best}
    if len(values) != 1: raise ValueError('ambiguous stage_request_bytes rules')
    return values.pop()


def split_payload(payload):
    """Split assigned rows, preserve source context; never truncate a record."""
    if any(k in payload for k in ('normalization_item_patch', 'normalization_evidence_patch', 'directed_patch', 'review_patch')):
        raise ValueError('bound repair exceeds request budget; split the original failed-item assignment before preparing the patch')
    field = next((k for k in ('units', 'scenarios', 'mounts', 'records')
        if isinstance(payload.get(k), list) and len(payload[k]) > 1), None)
    if not field: raise ValueError('single context item exceeds request budget; enlarge budget or split source sections explicitly')
    groups = []
    for rows in (payload[field][:len(payload[field])//2], payload[field][len(payload[field])//2:]):
        data = deepcopy(payload)
        data[field] = rows
        if field == 'units':
            ids = {r['source_scenario_id'] for r in rows}
            if 'original_scenarios' in data:
                data['original_scenarios'] = [r for r in data['original_scenarios'] if r['scenario_id'] in ids]
        else:
            ids = {r.get('scenario_id') for r in rows}
        if field in ('units', 'scenarios'):
            if isinstance(data.get('source_condition_counts'), dict):
                data['source_condition_counts'] = {k: v for k, v in data['source_condition_counts'].items() if k in ids}
            for name in ('original_evidence',):
                if name in data: data[name] = [r for r in data[name] if r.get('scenario_id') in ids]
            data.pop('evidence_catalog', None)  # rebuilt with correct per-item scopes
            data.pop('evidence_catalog_format', None)
        groups.append(data)
    return groups
