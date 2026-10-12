from copy import deepcopy
import pytest
from scene_completion.concern_gap import metrics,merge_units,eligible,locations
from scene_completion.concern_gap_ranking import rank,cosine
from scene_completion import concern_gap_batches as batches
from scene_completion.semantic_backend import read_json


KEY='human.authorization'


def unit(sid,cause='permission_absent',location='X',keys=None,basis='explicit'):
    return {'scenario_id':sid,'unit_id':sid,'source_scenario_id':sid,'use_case_id':'Clinic',
        'requirement_layer':'SR','scenario_type':'exception','location_id':location,
        'mapping_status':'mapped','object_code':'patient_record','cause_code':cause,'condition_codes':[],
        'concern_keys':keys or [KEY],'exception_object':'patient record','operation':'read record',
        'name':cause,
        'failure_mechanism':cause,'trigger_condition':cause,'necessary_conditions':[], 'source_refs':[],
        'source_basis':basis,'members':[{'source_basis':basis,'source_scenario_id':sid,'requirement_layer':'SR','source_refs':[]}]}


def pair(l,r,status='full'):
    return {'checker_scenario_id':l,'generated_scenario_id':r,'status':status}


def table(left,right,accepted):
    return [pair(l['scenario_id'],r['scenario_id'],'full' if (l['scenario_id'],r['scenario_id']) in accepted else 'unmatched')
        for l in left for r in right if eligible(l,r)]


def test_four_metrics_use_missing_gt_and_do_not_complement_adoption_false_positive():
    g=[unit('g1'),unit('g2','timeout'),unit('g3','unavailable'),unit('g4','format')]
    e=[unit('e1')];t=[unit('t1'),unit('t2','timeout')]
    rel={'EG':table(e,g,{('e1','g1')}),'TG':table(t,g,{('t1','g1'),('t2','g2')}),'TE':table(t,e,{('t1','e1')})}
    result=metrics(g,e,t,['g2','g3','g4'],rel)
    rows={r['metric']:r for r in result['overall']['metrics']}
    assert rows['miss_rate']['value']==0
    assert rows['miss_rate']['denominator']==1
    assert rows['generation_validity']['value']==.5
    assert rows['adoption_rate']['value']==1/3
    assert rows['recommendation_false_positive_rate']['value']==1 # 2 false / 2 GT


def test_false_positive_can_exceed_one_and_zero_denominators_are_null():
    g=[unit('g'+str(i),'c'+str(i)) for i in range(4)];t=[unit('t')]
    result=metrics(g,[],t,[u['scenario_id'] for u in g],{'EG':[],'TG':table(t,g,set()),'TE':[]})
    assert result['overall']['metrics'][3]['value']==4
    empty=metrics([],[],[],[],{'EG':[],'TG':[],'TE':[]})
    assert all(r['value'] is None for r in empty['overall']['metrics'])


def test_each_metric_assigns_its_restricted_set_before_counting():
    # All-G tie chooses a, but missing-M must independently assign z.
    g=[unit('a'),unit('z')];e=[unit('e')];t=[unit('t')]
    rel={'EG':table(e,g,{('e','a')}),'TE':table(t,e,set()),'TG':table(t,g,{('t','a'),('t','z')})}
    r=metrics(g,e,t,['z'],rel)
    assert r['assignments']['TG']['selected_pairs'][0]['generated_scenario_id']=='a'
    assert r['assignments']['TM']['selected_pairs'][0]['generated_scenario_id']=='z'
    assert r['assignments']['TR']['selected_pairs'][0]['generated_scenario_id']=='z'
    assert r['overall']['metrics'][0]['value']==0


def test_same_cause_merges_layer_views_but_not_different_location_or_condition():
    a=unit('a');b=unit('b');b['requirement_layer']='RR'
    c=unit('c',location='other');d=unit('d');d['condition_codes']=['already_created']
    out=merge_units([a,b,c,d],'G')
    assert len(out)==3
    merged=next(u for u in out if len(u['members'])==2)
    assert merged['source_layers']==['RR','SR']


def test_unmapped_units_are_retained_and_cannot_match():
    a=unit('a');a['mapping_status']='unmapped';a['location_id']=''
    b=unit('b');b['mapping_status']='unmapped';b['location_id']=''
    assert len(merge_units([a,b],'E'))==2
    assert eligible(a,b) is False


class Vectors:
    def model(self,kind):return 'fake-embedding'
    def embeddings(self,texts):return [[1.,0.] for t in texts]


@pytest.mark.parametrize('n,expected',[(0,0),(1,1),(9,9),(10,10),(11,10),(99,10),(100,10),(101,11),(201,21)])
def test_historical_top_n_per_concern(n,expected):
    scenes=[unit('g'+str(i),'cause'+str(i)) for i in range(n)]
    old=[unit('h')]
    r=rank(scenes,old,Vectors())
    assert len(r['selected_ids'])==expected
    if n:assert r['categories'][0]['selected_count']==expected


def test_raw_sum_includes_all_unique_same_category_history_and_negative_values():
    class Signed(Vectors):
        def embeddings(self,texts):return [[-1.,0.] if 'opposite' in t else [1.,0.] for t in texts]
    g=[unit('g')];history=[unit('h1'),unit('h2','opposite'),unit('different',keys=['api.data.format'])]
    r=rank(g,history,Signed())
    row=r['categories'][0]['items'][0]
    assert row['score']==0
    assert {d['history_id'] for d in row['similarities']}=={'h1','h2'}
    assert any(d['cosine']==-1 for d in row['similarities'])


def test_no_history_sampling_caps_at_ten_and_is_reproducible_and_not_zero_score():
    class NoCall(Vectors):
        def embeddings(self,texts):assert texts==[];return []
    g=[unit('g'+str(i),'c'+str(i)) for i in range(200)]
    a=rank(g,[],NoCall(),42);b=rank(list(reversed(g)),[],NoCall(),42)
    assert a['selected_ids']==b['selected_ids']
    assert len(a['selected_ids'])==10
    assert all(r['score'] is None and r['rank'] is None for r in a['categories'][0]['items'])
    assert a['selected_ids']!=rank(g,[],NoCall(),43)['selected_ids']


def test_multi_category_selected_unit_is_counted_once():
    g=[unit('g',keys=[KEY,'api.data.format'])]
    r=rank(g,[],Vectors())
    assert len(r['categories'])==2 and r['selected_ids']==['g']


def test_missing_or_unrelated_comparison_and_nonmissing_recommendations_are_rejected():
    g=[unit('g')];e=[unit('e')]
    with pytest.raises(ValueError,match='comparison'):
        metrics(g,e,[],[],{'EG':[],'TG':[],'TE':[]})
    with pytest.raises(ValueError,match='missing G'):
        metrics(g,e,[],['g'],{'EG':[pair('e','g')],'TG':[],'TE':[]})


def test_only_ambiguities_inside_location_concern_bucket_get_semantic_packets(tmp_path):
    left=[unit('e1'),unit('e2',location='other')]
    right=[unit('g1'),unit('g2','timeout'),unit('g3','invalid_format',keys=['api.data.format'])]
    m=batches.comparison_packets(left,right,tmp_path,'EG')
    assert len(m['batches'])==1
    packet=read_json(tmp_path/'packets'/(m['batches'][0]['batch_id']+'.json'))
    assert [s['scenario_id'] for s in packet['input']['generated']]==['g2']
    assert batches.exact_decisions(left,right)[0]['generated_scenario_id']=='g1'


def test_location_catalog_merges_boundary_views_not_nested_service_calls():
    ssd={'nodes':[{'node_id':'actor'},{'node_id':'ui','boundary_role':'ui'},{'node_id':'api'},{'node_id':'db'}],
        'exchanges':[{'exchange_id':'R','requirement_layer':'RR','use_case_id':'Clinic','from_node':'actor','to_node':'ui','operation':'submit','source_refs':[]},
            {'exchange_id':'S','requirement_layer':'SR','parent_exchange_id':'R','use_case_id':'Clinic','from_node':'ui','to_node':'api','operation':'create','source_refs':[]},
            {'exchange_id':'D','requirement_layer':'SR','parent_exchange_id':'R','parent_sr_exchange_id':'S','use_case_id':'Clinic','from_node':'api','to_node':'db','operation':'persist','source_refs':[]}]}
    catalog=locations(ssd)
    assert len(catalog)==2 and catalog[0]['exchange_ids']==['R','S']
    assert catalog[1]['location_id']=='D'


def test_cosine_rejects_invalid_and_zero_vectors():
    for a,b in [([1],[1,2]),([0],[1]),([float('nan')],[1])]:
        with pytest.raises(ValueError):cosine(a,b)


def test_reverse_check_cannot_pass_on_generic_topic_without_original_evidence():
    u=unit('u');u['source_scenario_id']='source'
    p={'input':{'units':[u],'original_scenarios':[unit('source')]}}
    r={'reviews':[{'unit_id':'u','source_supported':True,'atomic':True,'mapping_correct':True,'cause_correct':True,
        'evidence_quote':'generic topic','reason':'same concern'}]}
    with pytest.raises(ValueError,match='original condition'):batches.review_validator(p,r)


def test_ar_never_becomes_analysis_location():
    assert locations({'nodes':[],'exchanges':[{'exchange_id':'A','requirement_layer':'AR'}]})==[]


def test_same_actual_canonical_cause_is_not_rejected_for_layer_view_tags():
    a=unit('a',cause='missing_resource',keys=['service.query_retrieval.resource_existence'])
    b=unit('b',cause='missing_resource',keys=['internal_database.resource_existence'])
    assert eligible(a,b) is True
