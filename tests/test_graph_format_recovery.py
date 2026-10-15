import copy
import pytest
from scene_completion.concern_gap_batches import graph_validator
from scene_completion.sources import index_sources


def test_unique_local_ids_are_normalized_but_ambiguities_and_duplicate_checks_fail(tmp_path):
    path=tmp_path/'RR.md';path.write_text('# UC\n读取资源\n',encoding='utf8')
    index=index_sources([str(path)])
    packet={'input':{'exchanges':[{'exchange_id':'RR-EX-1','local_id':'e1'}],'nodes':[]}}
    raw={'checks':[{'id':'e1','kind':'ssd','valid':True,'reason':'原文读取资源',
        'evidence_quote':'读取资源','source_refs':[{'document':'RR.md','line_start':2,'line_end':2}]}]}
    original=copy.deepcopy(raw)
    rows=graph_validator(index)(packet,raw)
    assert raw==original and rows[0]['id']=='RR-EX-1' and rows[0]['original_id']=='e1'
    packet['input']['exchanges'].append({'exchange_id':'SR-EX-2','local_id':'e1'})
    with pytest.raises(ValueError,match='every node'):graph_validator(index)(packet,raw)
    packet['input']['exchanges'].pop()
    duplicate=copy.deepcopy(raw);duplicate['checks']*=2
    with pytest.raises(ValueError,match='every node'):graph_validator(index)(packet,duplicate)
    raw['checks'][0]['id']='unknown'
    with pytest.raises(ValueError,match='every node'):graph_validator(index)(packet,raw)
