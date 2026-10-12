from copy import deepcopy
import pytest
from scene_completion.concern_gap_inverse_repair import apply


def test_inverse_repair_replaces_only_selected_source_and_keeps_other_units():
    before=[{'unit_id':'u1','source_scenario_id':'c1'},
        {'unit_id':'u2','source_scenario_id':'c2'},{'unit_id':'u3','source_scenario_id':'c2'},
        {'unit_id':'u4','source_scenario_id':'c3'}]
    fixed=[{'unit_id':'v2','source_scenario_id':'c2'},{'unit_id':'v3','source_scenario_id':'c2'}]
    record={'sources':[{'scenario_id':'c2'}],'prior_units':before[1:3],'replacements':fixed}
    original=deepcopy(before)
    assert apply(before,[record])==[before[0],*fixed,before[3]] and before==original


def test_inverse_repair_cannot_change_prior_evidence_or_remove_source():
    before=[{'unit_id':'u1','source_scenario_id':'c1'}]
    record={'sources':[{'scenario_id':'c1'}],'prior_units':[],
        'replacements':[{'unit_id':'u2','source_scenario_id':'c1'}]}
    with pytest.raises(ValueError,match='prior units changed'):apply(before,[record])
    record['prior_units']=before;record['replacements']=[]
    with pytest.raises(ValueError,match='dropped or added'):apply(before,[record])
