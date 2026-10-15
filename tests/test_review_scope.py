from copy import deepcopy

import pytest

from scene_completion.review_scope import concern_closure
from scene_completion.partial_packet_reuse import semantic_packet
from scene_completion.interaction_protocol import baseline


def test_generated_review_scope_preserves_all_records_and_source_labels():
    registry = {'a': {'name': 'a'}, 'b': {'name': 'b'}, 'c': {'name': 'c'}}
    payload = {'collection': 'G', 'concern_definitions': registry,
        'units': [{'concern_key': 'a', 'original_concern_keys': ['b'], 'unit_id': 'u1'}],
        'original_scenarios': [{'concern_keys': ['a']}], 'locations': [{'id': 'l1'}],
        'original_evidence': ['complete source evidence']}
    before = deepcopy(payload)
    scoped = concern_closure(payload, registry)
    assert payload == before
    assert set(scoped['concern_definitions']) == {'a', 'b'}
    assert {k: v for k, v in scoped.items() if k != 'concern_definitions'} == {
        k: v for k, v in payload.items() if k != 'concern_definitions'}
    assert concern_closure(dict(payload, collection='T'), registry) == dict(payload, collection='T')
    with pytest.raises(ValueError):
        concern_closure(dict(payload, concern_definitions={'a': registry['a']}), registry)
    with pytest.raises(ValueError):
        concern_closure(dict(payload, concern_definitions={**registry, 'c': {'name': 'changed'}}), registry)


def test_old_full_registry_review_is_equivalent_only_with_identical_required_definitions():
    registry = baseline()
    key = next(iter(registry))
    payload = {'collection': 'G', 'concern_definitions': registry,
        'units': [{'concern_key': key}], 'original_scenarios': []}
    old = {'stage': 'gap-reverse-check-G', 'input': payload, 'instructions': ['check'],
        'output_contract': {'reviews': []}}
    new = dict(old, input=concern_closure(payload, registry))
    assert semantic_packet(old) == semantic_packet(new)
    changed = deepcopy(new)
    changed['input']['concern_definitions'][key]['name'] = 'different definition'
    with pytest.raises(ValueError):
        semantic_packet(changed)
