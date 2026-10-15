from copy import deepcopy
from pathlib import Path
import pytest
from scene_completion import concern_gap_batches as b
from scene_completion.semantic_backend import read_json
from scene_completion.interaction_protocol import build_ssd,route_mounts
from scene_completion.sources import index_sources,validate_refs
from tests.test_interaction_protocol import model,reference


@pytest.fixture
def index(tmp_path):
    p=tmp_path/'rr.md';p.write_text('# Requirements\n## UC-1\n用户提交商品编号。商品编号必须存在。\n',encoding='utf8')
    data=index_sources([str(p)]);data['documents'][0]['requirement_layer']='RR'
    return data


def raw_scene(index,ssd):
    m=route_mounts(ssd)[0]
    return {'scenario_id':'G','name':'请求超时','scenario_type':'exception','requirement_layer':'RR','use_case_id':'UC-1',
        'exchange_id':m['exchange_id'],'concern_keys':[m['concern_key']], 'exception_object':'请求','operation':'提交',
        'failure_mechanism':'超时','trigger_condition':'请求超过允许时间','necessary_conditions':[], 'source_refs':reference(index)}


def normalized(index,lid,key):
    return {'mapping_status':'mapped','location_id':lid,'concern_key':key,'object_code':'request','cause_code':'timeout',
        'condition_codes':[],'exception_object':'请求','operation':'提交','failure_mechanism':'超时','trigger_condition':'请求超过允许时间',
        'necessary_conditions':[],'evidence_quote':'请求超过允许时间','source_refs':reference(index),'reason':'实际请求'}


def test_normalization_channels_do_not_include_other_collections_and_keep_mount(index,tmp_path):
    ssd=build_ssd(model(index));source=raw_scene(index,ssd)
    manifest=b.normalized_packets([source],ssd,tmp_path,'G')
    p=read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    assert not any(k in p['input'] for k in ['existing','test_conditions','recommendations'])
    location=p['input']['locations'][0]['location_id']
    u={k:v for k,v in normalized(index,location,source['concern_keys'][0]).items() if k in {'object_code','cause_code','condition_codes','reason'}}
    output={'items':[{'source_scenario_id':'G','units':[u]}]}
    result=b.normalize_validator(index)(p,output)
    assert result[0]['name']==source['name'] and result[0]['source_basis']=='explicit'
    wrong=deepcopy(output);wrong['items'][0]['units'][0]['concern_key']='human.authorization'
    with pytest.raises(ValueError,match='immutable identification'):b.normalize_validator(index)(p,wrong)
    omitted={'items':[{'source_scenario_id':'G','units':[]}]}
    with pytest.raises(ValueError,match='exception requires'):b.normalize_validator(index)(p,omitted)


def test_normalization_needs_each_necessary_condition_code(index,tmp_path):
    ssd=build_ssd(model(index));source=raw_scene(index,ssd)
    manifest=b.normalized_packets([source],ssd,tmp_path,'G')
    p=read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    p['input']['scenarios'][0]['necessary_conditions']=['有请求']
    u={k:v for k,v in normalized(index,p['input']['locations'][0]['location_id'],source['concern_keys'][0]).items() if k in {'object_code','cause_code','condition_codes','reason'}}
    with pytest.raises(ValueError,match='semantic code'):
        b.normalize_validator(index)(p,{'items':[{'source_scenario_id':'G','units':[u]}]})


def test_g_normalization_keeps_full_location_closure_without_unrelated_calls(index,tmp_path):
    ssd=build_ssd(model(index));source=raw_scene(index,ssd)
    source['necessary_conditions']=['有请求','服务可调用']
    extra=deepcopy(ssd['exchanges'][0])
    extra.update(exchange_id='UNRELATED',parent_exchange_id=None,parent_sr_exchange_id=None,
        operation='unrelated operation')
    ssd['exchanges'].append(extra)
    manifest=b.normalized_packets([source],ssd,tmp_path,'G')
    packet=read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    data=packet['input']
    assert 'UNRELATED' not in {e['exchange_id'] for e in data['exchange_details']}
    assert source['exchange_id'] in {e['exchange_id'] for e in data['exchange_details']}
    assert {s['scenario_id'] for s in data['scenarios']}=={'G'}
    assert data['source_condition_counts']=={'G':2}
    assert set(data['concern_definitions'])==set(source['concern_keys'])
    # The original strict validator still refuses missing condition identities.
    unit={'object_code':'request','cause_code':'timeout','condition_codes':['request_present'], 'reason':'source'}
    with pytest.raises(ValueError,match='every necessary condition'):
        b.normalize_validator(index)(packet,{'items':[{'source_scenario_id':'G','units':[unit]}]})


def test_features_must_include_actual_checked_operation_trait(index):
    exchange={'exchange_id':'X','operation_kinds':['read']}
    packet={'input':{'exchanges':[exchange]}}
    trait={'name':'operation_kinds','value':['read'],'basis':'explicit','evidence_quote':'用户提交商品编号',
        'source_refs':reference(index),'rationale':'actual operation'}
    assert b.feature_validator(index)(packet,{'items':[{'exchange_id':'X','traits':[trait]}]})
    trait['value']=['write']
    with pytest.raises(ValueError,match='positive operation'):
        b.feature_validator(index)(packet,{'items':[{'exchange_id':'X','traits':[trait]}]})


def test_ar_trace_cannot_invent_component_or_analysis_interaction(index):
    packet={'input':{}}
    with pytest.raises(ValueError,match='literal source'):
        b.ar_validator(index)(packet,{'components':[{'name':'ImaginaryDatabase','evidence_quote':'用户提交商品编号','source_refs':reference(index)}]})
    rows=b.ar_validator(index)(packet,{'components':[{'name':'商品编号','evidence_quote':'用户提交商品编号','source_refs':reference(index)}]})
    assert rows[0]['analysis_enabled'] is False and rows[0]['layer']=='AR'


def test_graph_checker_requires_all_nodes_and_exchange_source_evidence(index):
    packet={'input':{'exchanges':[{'exchange_id':'X'}],'nodes':[{'node_id':'N'}]}}
    with pytest.raises(ValueError,match='every node'):
        b.graph_validator(index)(packet,{'checks':[]})
    rows=[{'id':i,'kind':kind,'valid':True,'evidence_quote':'用户提交商品编号','source_refs':reference(index),'reason':'source'} for i,kind in [('X','ssd'),('N','composition')]]
    assert len(b.graph_validator(index)(packet,{'checks':rows}))==2
    rows[0]['evidence_quote']='Fabricated source'
    with pytest.raises(ValueError,match='quote cited'):
        b.graph_validator(index)(packet,{'checks':rows})


def test_inverse_diagnostic_preserves_invalid_output_and_provides_literal_condition(index,tmp_path):
    from scene_completion.concern_gap_normalize_diagnostics import validator
    ssd=build_ssd(model(index));source=raw_scene(index,ssd)
    manifest=b.normalized_packets([source],ssd,tmp_path,'E')
    packet=read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    u=normalized(index,packet['input']['locations'][0]['location_id'],source['concern_keys'][0])
    u['evidence_quote']='用户提交商品编号'
    raw={'items':[{'source_scenario_id':'G','units':[u]}]};saved=deepcopy(raw)
    with pytest.raises(ValueError,match='exact_condition'):validator(index)(packet,raw)
    assert raw==saved


def test_confirmation_rechecks_only_rejected_g_without_existing_or_gt(index,tmp_path):
    from scene_completion.concern_gap_review_confirm import packets
    ssd=build_ssd(model(index));source=raw_scene(index,ssd)
    units=[{'unit_id':i,'source_scenario_id':'G','use_case_id':'UC-1'} for i in ['ok','bad']]
    reviews=[{'unit_id':'ok','passed':True},{'unit_id':'bad','passed':False}]
    manifest=packets(units,[source],ssd,index,reviews,tmp_path)
    packet=read_json(tmp_path/'packets'/(manifest['batches'][0]['batch_id']+'.json'))
    assert [u['unit_id'] for u in packet['input']['units']]==['bad']
    assert packet['input']['generation_basis'].startswith('SSD-derived')
    assert not any(k in packet['input'] for k in ['existing','test_conditions','recommendations'])


def test_boundary_alias_is_resolved_only_by_explicit_same_use_case_membership(index):
    from scene_completion.concern_gap_normalize_diagnostics import validator
    source=raw_scene(index,build_ssd(model(index)))
    packet={'input':{'collection':'E','scenarios':[source],
        'locations':[{'location_id':'RR','exchange_ids':['RR','SR'],'use_case_id':'UC-1'}]}}
    u=normalized(index,'SR',source['concern_keys'][0]);raw={'items':[{'source_scenario_id':'G','units':[u]}]}
    original=deepcopy(raw);rows=validator(index)(packet,raw)
    assert rows[0]['location_id']=='RR' and raw==original
    packet['input']['locations'][0]['use_case_id']='OTHER'
    with pytest.raises(ValueError,match='same use case'):validator(index)(packet,raw)


def test_reverse_source_pointer_preserves_raw_and_semantic_rejection():
    from scene_completion.concern_gap_repair import reverse_validator
    packet={'input':{'units':[{'unit_id':'U','source_scenario_id':'C'}],
        'original_scenarios':[{'scenario_id':'C','trigger_condition':'商品缺失','failure_mechanism':'不存在'}]}}
    raw={'reviews':[{'unit_id':'U','evidence_source_scenario_id':'C','reason':'错误位置',
        'source_supported':True,'atomic':True,'mapping_correct':False,'cause_correct':True}]}
    original=deepcopy(raw)
    result=reverse_validator(packet,raw)
    assert result[0]['evidence_quote']=='商品缺失'
    assert result[0]['passed'] is False
    assert raw==original
    raw['reviews'][0]['evidence_source_scenario_id']='OTHER'
    with pytest.raises(ValueError,match='exact unit original source ID'):
        reverse_validator(packet,raw)


def test_case_dag_review_materials_bind_test_and_ar_sources(tmp_path):
    from scene_completion.concern_gap_replay import proof_files
    from scene_completion.semantic_backend import write_json
    write_json(tmp_path/'run_manifest.json', {'execution_mode': 'case-dag'})
    for name in ('sources_index.json', 'test_sources_index.json', 'ar_sources_index.json'):
        write_json(tmp_path/name, {'documents': []})
    before = proof_files(tmp_path)
    assert {'sources_index.json', 'test_sources_index.json', 'ar_sources_index.json'} <= set(before)
    write_json(tmp_path/'test_sources_index.json', {'documents': ['changed']})
    assert proof_files(tmp_path)['test_sources_index.json'] != before['test_sources_index.json']
