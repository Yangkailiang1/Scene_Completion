import copy

import pytest

from scene_completion.generation_compaction import INSTRUCTION, decode, encode


def _payload(repetitions=3):
    repeated = {'feature_id': 'trait_x', 'description': 'A repeated long evidence description.' * 20,
        'source_refs': [{'document': 'rr.md', 'line_start': 11, 'line_end': 12}]}
    other = {'feature_id': 'trait_y', 'description': 'A second trait.' * 18,
        'source_refs': [{'document': 'sr.md', 'line_start': 21, 'line_end': 22}]}
    return {
        'protocol': 'fixture', 'use_case_id': 'UC-1',
        'mounts': [{'mount_id': f'M{i}', 'feature_evidence': [copy.deepcopy(repeated),
            copy.deepcopy(other), copy.deepcopy(repeated)]} for i in range(repetitions)],
        'checked_features': [{'exchange_id': f'E{i}', 'traits': [copy.deepcopy(repeated),
            copy.deepcopy(other)]} for i in range(repetitions)],
        'unrelated': {'kept': [1, 2, {'opaque': True}]},
    }


def test_encode_decode_is_lossless_and_shares_repeated_objects():
    original = _payload()
    encoded = encode(original)
    assert encoded['generation_compaction'] == 'shared-feature-evidence-v1'
    assert encoded['mounts'][0]['feature_evidence_refs'][0] == encoded['mounts'][0]['feature_evidence_refs'][2]
    assert encoded['mounts'][0]['feature_evidence_refs'][0] == encoded['checked_features'][0]['trait_refs'][0]
    assert 'feature_evidence' not in encoded['mounts'][0]
    assert 'traits' not in encoded['checked_features'][0]
    assert decode(encoded) == original
    assert encode(encoded) == encoded
    assert INSTRUCTION.startswith('When generation_compaction=shared-feature-evidence-v1')


def test_non_target_fields_and_absent_evidence_fields_are_preserved():
    original = {'protocol': 'fixture', 'mounts': [{'mount_id': 'M1'}],
        'checked_features': [{'exchange_id': 'E1'}], 'arbitrary': {'x': [1, 2]}}
    assert encode(original) == original
    assert decode(original) == original

    shared = {'feature': 'x', 'description': 'repeated evidence ' * 24}
    mixed = {'mounts': [{'mount_id': f'M{i}', 'feature_evidence': [copy.deepcopy(shared)]}
            for i in range(5)] + [{'mount_id': 'M-absent'}],
        'checked_features': [{'exchange_id': f'E{i}', 'traits': [copy.deepcopy(shared)]}
            for i in range(5)] + [{'exchange_id': 'E-absent'}]}
    compact = encode(mixed)
    assert compact.get('generation_compaction') == 'shared-feature-evidence-v1'
    assert decode(compact) == mixed


@pytest.mark.parametrize('mutation', ['hash', 'missing_ref', 'unknown_ref', 'old_field_conflict'])
def test_decode_rejects_tampered_or_ambiguous_catalog(mutation):
    encoded = encode(_payload())
    broken = copy.deepcopy(encoded)
    row = broken['mounts'][0]
    if mutation == 'hash':
        key = next(iter(broken['feature_evidence_catalog']))
        broken['feature_evidence_catalog'][key]['description'] += ' altered'
    elif mutation == 'missing_ref':
        row['feature_evidence_refs'].pop()
    elif mutation == 'unknown_ref':
        row['feature_evidence_refs'][0] = '0' * 64
    else:
        row['feature_evidence'] = []
    with pytest.raises(ValueError):
        decode(broken)


def test_encode_rejects_unmarked_reference_conflict_and_bad_evidence_shapes():
    conflict = _payload()
    conflict['mounts'][0]['feature_evidence_refs'] = []
    with pytest.raises(ValueError, match='already has a compaction reference'):
        encode(conflict)
    malformed = _payload()
    malformed['checked_features'][0]['traits'] = ['not an object']
    with pytest.raises(ValueError, match='lists of objects'):
        encode(malformed)


def test_codec_does_not_add_catalog_when_not_smaller():
    tiny = {'mounts': [{'feature_evidence': [{'x': 1}]}],
        'checked_features': [{'traits': [{'y': 2}]}]}
    assert encode(tiny) == tiny
def test_expanded_packet_reuse_keeps_business_instructions_exact():
    from scene_completion.generation_compaction import encode, INSTRUCTION
    from scene_completion.partial_packet_reuse import semantic_packet
    evidence = {'name': 'field', 'value': 'bounded', 'quote': 'evidence ' * 150}
    payload = {'mounts': [{'mount_id': str(i), 'feature_evidence': [evidence]} for i in range(4)],
        'checked_features': [{'exchange_id': 'e1', 'traits': [evidence]}]}
    original = {'stage': 'gap-generation', 'input': payload,
        'instructions': ['Keep all mounts.'], 'output_contract': {'items': []}}
    compressed = {**original, 'input': encode(payload), 'instructions': [*original['instructions'], INSTRUCTION]}
    assert semantic_packet(compressed) == semantic_packet(original)
    compressed['instructions'] = ['Drop mounts.', INSTRUCTION]
    assert semantic_packet(compressed) != semantic_packet(original)

