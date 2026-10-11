"""Snapshot reconstruction checks completeness without claiming execution."""
import pytest
from scene_completion.interaction_snapshot import validate_pairs, rebuild_snapshot
from scene_completion.semantic_backend import write_json
from tests.test_interaction_protocol import scene,pair


def test_snapshot_pair_universe_cannot_drop_unmatched_or_inject_other_ids():
    first, second = pair('C','G'), pair('C','G2','unmatched')
    first.update(condition_evidence=[],missing_condition_evidence=[])
    second.update(condition_evidence=[],missing_condition_evidence=[])
    gs=[scene('G'),scene('G2')]
    decisions=[second,first]
    assert validate_pairs(gs,[scene('C')],decisions,'interaction-matching') == decisions
    with pytest.raises(ValueError,match='incomplete'):
        validate_pairs(gs,[scene('C')],decisions[:1],'interaction-matching')
    with pytest.raises(ValueError,match='duplicate'):
        validate_pairs(gs,[scene('C')],[first,first],'interaction-matching')
    with pytest.raises(ValueError,match='unknown'):
        validate_pairs(gs,[scene('C')],[*decisions,pair('Other','G')],'interaction-matching')


def test_modified_snapshot_is_rejected_before_writing_a_report(tmp_path):
    path=tmp_path/'snapshot.json'
    write_json(path,{'payload':{'schema':1},'payload_hash':'modified'})
    with pytest.raises(ValueError,match='integrity'):
        rebuild_snapshot(path,tmp_path/'reports')
    assert not (tmp_path/'reports').exists()
