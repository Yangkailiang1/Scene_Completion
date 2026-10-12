"""Canonical comparison retains actual interaction and condition evidence guards."""
import copy

import pytest

from scene_completion.concern_gap_comparison import validator
from tests.test_interaction_protocol import scene, pair


def packet():
    left, right = scene('C', 'RR', ['query.exists']), scene('G', 'SR', ['query.exists'])
    return {'stage': 'gap-ambiguity-EG', 'input': {
        'comparison_scope': 'test_all', 'checker': [left], 'generated': [right],
        'canonical_metadata': {sid: {'location_id': 'actual-1', 'object_code': 'product',
                                    'cause_code': 'missing'} for sid in ('C', 'G')}}}


def test_cross_layer_canonical_same_actual_interaction_preserves_original_packet():
    data = packet()
    original = copy.deepcopy(data)
    assert validator(data, {'pairs': [pair('C', 'G')]})[0]['status'] == 'full'
    assert data == original


def test_canonical_different_actual_interaction_rejected():
    data = packet()
    data['input']['canonical_metadata']['G']['location_id'] = 'unrelated'
    with pytest.raises(ValueError, match='unrelated'):
        validator(data, {'pairs': [pair('C', 'G')]})


def test_exact_checker_conditions_required_with_actionable_retry_diagnostic():
    data = packet()
    data['input']['checker'][0]['necessary_conditions'] = ['查询已发起']
    with pytest.raises(ValueError, match='查询已发起'):
        validator(data, {'pairs': [pair('C', 'G')]})


def test_canonical_causal_evidence_still_requires_original_quote():
    decision = pair('C', 'G')
    decision['causal_facet_evidence']['generated'] = 'invented cause'
    with pytest.raises(ValueError, match='actual mechanism/trigger quote'):
        validator(packet(), {'pairs': [decision]})


def test_unmatched_same_actual_cause_with_compatible_conditions_requires_rejudgment():
    decision = pair('C', 'G', 'unmatched')
    decision['same_mechanism'] = False
    decision['same_object'] = False
    decision['reason'] = 'one handles it successfully; the other describes failure'
    with pytest.raises(ValueError, match='Unmatched contradicts'):
        validator(packet(), {'pairs': [decision]})
    # An actual different causal facet can still be unmatched; the guard never
    # rewrites a verdict to matched or guesses unsupported evidence.
    decision['same_causal_facet'] = False
    assert validator(packet(), {'pairs': [decision]})[0]['status'] == 'unmatched'
