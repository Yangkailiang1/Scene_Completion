"""Lossless shared-catalog encoding for repeated generation feature evidence."""
from __future__ import annotations

import copy
import json

from .sources import fingerprint


_MARKER = 'shared-feature-evidence-v1'
_CATALOG = 'feature_evidence_catalog'
_INTEGRITY = 'feature_evidence_compaction_hash'
INSTRUCTION = ('When generation_compaction=shared-feature-evidence-v1, each mount.feature_evidence_refs and '
    'checked_features.trait_refs points to the complete original object in feature_evidence_catalog. Read those '
    'objects as the mount evidence/checked traits; this is lossless sharing, not omitted facts or applicability filtering.')


def _json_size(value) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(',', ':')).encode('utf-8'))
    except (TypeError, ValueError) as exc:
        raise ValueError('generation payload must contain JSON-compatible evidence objects') from exc


def _catalog_key(value) -> str:
    try:
        return fingerprint(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('feature evidence must be JSON-compatible') from exc


def _reference_manifest(value):
    return {collection: [copy.deepcopy(row[refs_field]) if refs_field in row else None for row in value[collection]]
        for collection, refs_field in (('mounts', 'feature_evidence_refs'),
            ('checked_features', 'trait_refs'))}


def decode(payload):
    """Restore an encoded generation payload, rejecting ambiguous or damaged references."""
    if not isinstance(payload, dict):
        raise ValueError('generation payload must be an object')
    value = copy.deepcopy(payload)
    marker = value.get('generation_compaction')
    if marker is None:
        if _CATALOG in value or _INTEGRITY in value:
            raise ValueError('feature evidence catalog has no compaction marker')
        return value
    if marker != _MARKER:
        raise ValueError('unsupported generation compaction marker')
    catalog = value.get(_CATALOG)
    if not isinstance(catalog, dict):
        raise ValueError('compacted generation payload lacks its evidence catalog')
    for key, evidence in catalog.items():
        if not isinstance(key, str) or key != _catalog_key(evidence) or not isinstance(evidence, dict):
            raise ValueError('generation evidence catalog key or value is invalid')
    used = set()
    for collection, old_field, refs_field in (
            ('mounts', 'feature_evidence', 'feature_evidence_refs'),
            ('checked_features', 'traits', 'trait_refs')):
        rows = value.get(collection)
        if not isinstance(rows, list):
            raise ValueError('compacted generation payload has an invalid ' + collection + ' list')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('compacted generation rows must be objects')
            if old_field in row and refs_field in row:
                raise ValueError('compacted generation row has a conflicting original field and reference')
            if old_field not in row and refs_field not in row:
                continue
            if refs_field not in row:
                raise ValueError('compacted generation row has a missing reference')
            refs = row[refs_field]
            if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                raise ValueError('generation evidence references must be an ordered string list')
            if any(ref not in catalog for ref in refs):
                raise ValueError('generation evidence reference is missing from its catalog')
            used.update(refs)
    if used != set(catalog):
        raise ValueError('generation evidence catalog has unused or missing references')
    if value.get(_INTEGRITY) != fingerprint({
            'catalog_keys': sorted(catalog), 'references': _reference_manifest(value)}):
        raise ValueError('generation evidence reference integrity hash is invalid')

    for collection, old_field, refs_field in (
            ('mounts', 'feature_evidence', 'feature_evidence_refs'),
            ('checked_features', 'traits', 'trait_refs')):
        for row in value[collection]:
            if refs_field not in row:
                continue
            row[old_field] = [copy.deepcopy(catalog[ref]) for ref in row.pop(refs_field)]
    value.pop(_CATALOG)
    value.pop('generation_compaction')
    value.pop(_INTEGRITY)
    return value


def encode(payload):
    """Compress repeated object evidence through a content-addressed shared catalog."""
    if not isinstance(payload, dict):
        raise ValueError('generation payload must be an object')
    original = copy.deepcopy(payload)
    if 'generation_compaction' in original or _CATALOG in original or _INTEGRITY in original:
        if original.get('generation_compaction') != _MARKER:
            raise ValueError('generation payload has an incomplete or unsupported compaction marker')
        decode(original)  # Validate all hashes, references, and old-field conflicts first.
        return original

    if not isinstance(original.get('mounts'), list) or not isinstance(original.get('checked_features'), list):
        raise ValueError('generation payload requires mounts and checked_features lists')
    catalog = {}
    encoded = copy.deepcopy(original)
    for collection, old_field, refs_field in (
            ('mounts', 'feature_evidence', 'feature_evidence_refs'),
            ('checked_features', 'traits', 'trait_refs')):
        for row in encoded[collection]:
            if not isinstance(row, dict):
                raise ValueError('generation rows must be objects')
            if refs_field in row:
                raise ValueError('unmarked generation row already has a compaction reference field')
            if old_field not in row:
                continue
            objects = row[old_field]
            if not isinstance(objects, list) or any(not isinstance(item, dict) for item in objects):
                raise ValueError('feature evidence and traits must be lists of objects')
            refs = []
            for item in objects:
                key = _catalog_key(item)
                if key in catalog and catalog[key] != item:
                    raise ValueError('feature evidence fingerprint collision')
                catalog[key] = copy.deepcopy(item)
                refs.append(key)
            row[refs_field] = refs
            del row[old_field]
    if not catalog:
        return original
    encoded['generation_compaction'] = _MARKER
    encoded[_CATALOG] = catalog
    encoded[_INTEGRITY] = fingerprint({
        'catalog_keys': sorted(catalog), 'references': _reference_manifest(encoded)})
    if _json_size(encoded) >= _json_size(original):
        return original
    # Internal round-trip check ensures this remains a lossless transform.
    if decode(encoded) != original:
        raise ValueError('generation compaction failed its lossless round-trip check')
    return encoded
