import pytest
from scene_completion.sources import index_sources
from scene_completion.concern_gap_batches import feature_validator


def test_feature_errors_identify_every_trait_without_accepting_unknown_false_flags(tmp_path):
    path=tmp_path/'records.md';path.write_text('# Read\nService reads a record.\n',encoding='utf8')
    index=index_sources([str(path)])
    ref={'document':'records.md','line_start':2,'line_end':2}
    packet={'input':{'exchanges':[{'exchange_id':'e1','operation_kinds':['read']}]}}
    operation={'name':'operation_kinds','value':['read'],'basis':'explicit','rationale':'documented read',
        'evidence_quote':'Service reads a record.','source_refs':[ref]}
    row={'exchange_id':'e1','traits':[operation,
        {'name':'cancellable','value':False,'basis':'inferred','rationale':'not stated','evidence_quote':'','source_refs':[]},
        {'name':'guard','value':'logged in','basis':'explicit','rationale':'assumed','evidence_quote':'logged in','source_refs':[ref]}]}
    with pytest.raises(ValueError) as raised:feature_validator(index)(packet,{'items':[row]})
    text=str(raised.value)
    assert 'cancellable' in text and 'guard' in text and 'e1' in text and 'pending_details' in text
    row['traits']=[operation];row['pending_details']=['No guard or cancellation contract supplied.']
    assert feature_validator(index)(packet,{'items':[row]})[0]['pending_details']==row['pending_details']
