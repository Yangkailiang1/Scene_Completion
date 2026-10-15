from __future__ import annotations

import copy

import pytest

from scene_completion.evidence_refs import expand_result, prepare_packet


def _section(document, chapter, start, lines):
    return {'document': document, 'chapter_id': chapter, 'line_start': start,
        'line_end': start + len(lines) - 1,
        'numbered_text': '\n'.join(f'{number}: {line}' for number, line in enumerate(lines, start))}


def _packet():
    sections = [_section('UC.md', 'UC-1', 1, [
        'Participants: ExternalLab and LocalCache',
        'ExternalLab is an external service.',
        'RequestAPI sends a specimen request to ExternalLab.',
        'LocalCache is an internal database.',
        'RequestAPI reads LocalCache.',
    ])]
    architecture = [_section('Architecture.md', 'ARCH-1', 10, [
        'ExternalLab provides specimen analysis.',
        'LocalCache stores local records.',
    ])]
    return prepare_packet({'stage': 'interaction-participants', 'input': {
        'use_case_id': 'UC-1', 'sections': sections, 'architecture_sections': architecture,
        'normal_model': {
            'components': [
                {'component_id': 'lab', 'name': 'ExternalLab', 'layer': 'SR', 'kind': 'external_service',
                    'source_refs': [{'document': 'UC.md', 'line_start': 2, 'line_end': 2}]},
                {'component_id': 'cache', 'name': 'LocalCache', 'layer': 'SR', 'kind': 'internal_database',
                    'source_refs': [{'document': 'UC.md', 'line_start': 4, 'line_end': 4}]},
            ],
            'exchanges': [
                {'local_id': 'call-lab', 'requirement_layer': 'SR', 'from_component_id': 'api',
                    'to_component_id': 'lab', 'source_refs': [{'document': 'UC.md', 'line_start': 3, 'line_end': 3}]},
                {'local_id': 'read-cache', 'requirement_layer': 'SR', 'from_component_id': 'api',
                    'to_component_id': 'cache', 'source_refs': [{'document': 'UC.md', 'line_start': 5, 'line_end': 5}]},
            ],
        },
    }})


def _entry(packet, kind, component_id, quote):
    matches = [row for row in packet['input']['evidence_catalog']
        if row['scope']['kind'] == kind and row['scope']['component_id'] == component_id and row['quote'] == quote]
    assert len(matches) == 1
    return matches[0]['id']


def _ref(field, evidence_id):
    return {field + '_ref': {'evidence_id': evidence_id}}


def test_participant_quote_refs_expand_exact_scoped_source_lines():
    packet = _packet()
    raw = {'component_reviews': [
        {'component_id': 'lab', 'status': 'declared',
            **_ref('role_quote', _entry(packet, 'participant_role', 'lab', 'ExternalLab is an external service.')),
            **_ref('interaction_quote', _entry(packet, 'participant_interaction', 'lab',
                'RequestAPI sends a specimen request to ExternalLab.')),
                **_ref('declared_participant_quote', _entry(packet, 'participant_declaration', 'lab',
                'Participants: ExternalLab and LocalCache')),
            'role_refs': [{'document': 'UC.md', 'line_start': 2, 'line_end': 2}],
            'interaction_refs': [{'document': 'UC.md', 'line_start': 3, 'line_end': 3}],
            'participant_refs': [{'document': 'UC.md', 'line_start': 1, 'line_end': 1}]},
        {'component_id': 'cache', 'status': 'resource',
            **_ref('role_quote', _entry(packet, 'participant_role', 'cache', 'LocalCache is an internal database.')),
            **_ref('interaction_quote', _entry(packet, 'participant_interaction', 'cache',
                'RequestAPI reads LocalCache.')),
            'role_refs': [{'document': 'UC.md', 'line_start': 4, 'line_end': 4}],
            'interaction_refs': [{'document': 'UC.md', 'line_start': 5, 'line_end': 5}]},
    ], 'missing_model_calls': [{'participant_name': 'Unresolved service', 'role_quote': 'literal unresolved role'}],
        'unresolved_candidates': [{'participant_name': 'Potential actor', 'role_quote': 'literal architecture note'}]}

    expanded = expand_result(packet, raw)
    lab, cache = expanded['component_reviews']
    assert lab['role_quote'] == 'ExternalLab is an external service.'
    assert lab['interaction_quote'] == 'RequestAPI sends a specimen request to ExternalLab.'
    assert lab['declared_participant_quote'] == 'Participants: ExternalLab and LocalCache'
    assert cache['role_quote'] == 'LocalCache is an internal database.'
    assert cache['interaction_quote'] == 'RequestAPI reads LocalCache.'
    assert expanded['missing_model_calls'] == raw['missing_model_calls']
    assert expanded['unresolved_candidates'] == raw['unresolved_candidates']
    assert 'role_quote' not in raw['component_reviews'][0]


@pytest.mark.parametrize('field,kind,borrowed_component,quote', [
    ('role_quote', 'participant_role', 'cache', 'LocalCache is an internal database.'),
    ('interaction_quote', 'participant_interaction', 'cache', 'RequestAPI reads LocalCache.'),
    ('declared_participant_quote', 'participant_declaration', 'cache', 'Participants: ExternalLab and LocalCache'),
])
def test_component_reviews_cannot_borrow_another_components_quote(field, kind, borrowed_component, quote):
    packet = _packet()
    evidence_id = _entry(packet, kind, borrowed_component, quote)
    raw = {'component_reviews': [{'component_id': 'lab', 'role_refs': [
        {'document': 'UC.md', 'line_start': 2, 'line_end': 2}],
        'interaction_refs': [{'document': 'UC.md', 'line_start': 3, 'line_end': 3}],
        'participant_refs': [{'document': 'UC.md', 'line_start': 1, 'line_end': 1}],
        **_ref(field, evidence_id)}]}
    with pytest.raises(ValueError, match='outside this result item'):
        expand_result(packet, raw)


def test_interaction_ref_requires_same_layer_ssd_exchange_and_its_source_refs():
    packet = _packet()
    interaction_id = _entry(packet, 'participant_interaction', 'lab',
        'RequestAPI sends a specimen request to ExternalLab.')
    raw = {'component_reviews': [{'component_id': 'lab', 'interaction_refs': [
        {'document': 'UC.md', 'line_start': 5, 'line_end': 5}],
        **_ref('interaction_quote', interaction_id)}]}
    with pytest.raises(ValueError, match='outside this result item'):
        expand_result(packet, raw)

    wrong_layer = copy.deepcopy(packet)
    wrong_layer['input']['normal_model']['components'][0]['layer'] = 'RR'
    wrong_layer = prepare_packet(wrong_layer)
    assert not any(row['scope']['kind'] == 'participant_interaction'
        and row['scope']['component_id'] == 'lab' for row in wrong_layer['input']['evidence_catalog'])


def test_role_sections_must_name_component_and_declaration_must_be_own_use_case():
    packet = _packet()
    role_ids = {row['quote']: row['id'] for row in packet['input']['evidence_catalog']
        if row['scope']['kind'] == 'participant_role' and row['scope']['component_id'] == 'lab'}
    assert 'ExternalLab provides specimen analysis.' in role_ids
    assert 'LocalCache stores local records.' not in role_ids
    declarations = [row for row in packet['input']['evidence_catalog']
        if row['scope']['kind'] == 'participant_declaration']
    assert {row['scope']['component_id'] for row in declarations} == {'lab', 'cache'}
    assert all(row['ref']['document'] == 'UC.md' for row in declarations)


def test_empty_catalog_keeps_literal_unresolved_protocol_unchanged():
    packet = prepare_packet({'stage': 'interaction-participants', 'input': {
        'sections': [], 'architecture_sections': [],
        'normal_model': {'components': [{'component_id': 'x', 'name': 'X', 'layer': 'SR'}], 'exchanges': []},
    }})
    raw = {'component_reviews': [{'component_id': 'x', 'status': 'not_involved',
        'role_quote': '', 'interaction_quote': '', 'declared_participant_quote': ''}],
        'missing_model_calls': [{'participant_name': 'Unknown', 'role_quote': 'literal unresolved'}],
        'unresolved_candidates': [{'participant_name': 'Unknown', 'role_quote': 'literal unresolved'}]}
    assert packet['input']['evidence_catalog'] == []
    assert expand_result(packet, raw) == raw
