from copy import deepcopy
from scene_completion.comparison_batches import compare_in_batches
from scene_completion.contracts import packet
from scene_completion.exception_comparison import compare_report
from tests.test_workflow import scenario

class Client:
    base_url='http://offline/v1'
    def __init__(self):self.calls=[]
    def model(self,kind):return 'test'
    def agent(self,p):
        self.calls.append(p['input'])
        pairs={(r['left_id'],r['right_id']) for r in p['input'].get('candidate_pairs',[])}
        return {'decisions':[{'left_id':a['id'],'right_id':b['id'],'status':'full' if a['cause']==b['cause'] else 'unmatched','reason':'fixture semantic decision'} for a in p['input']['left'] for b in p['input']['right'] if not pairs or (a['id'],b['id']) in pairs]}

def test_partitioned_comparison_keeps_exhaustive_decisions_and_reuses_valid_parts(tmp_path):
    a,b=scenario('a'),scenario('b');b['interaction_id']='second'
    x,y=deepcopy(a),deepcopy(b);x['id']='x';y['id']='y'
    p=packet('gap-compare',{'left':[a,b],'right':[x,y],'purpose':'G_E'});p['node_key']='case:gap-compare'
    client=Client();v=compare_in_batches(p,client,tmp_path)
    assert len(client.calls)==2 and all(len(r['left'])==len(r['right'])==1 for r in client.calls)
    assert len(v['decisions'])==4 and not v['missing']
    assert sum(d['status']=='unmatched' for d in v['decisions'])==2
    again=compare_in_batches(p,client,tmp_path)
    assert len(client.calls)==2 and again['decisions']==v['decisions']

def test_large_interaction_matrix_is_bounded_per_model_request(tmp_path):
    left=[scenario('l'+str(n)) for n in range(17)];right=[scenario('r'+str(n)) for n in range(10)]
    p=packet('semantic-compare',{'left':left,'right':right,'purpose':'GT_G'});p['node_key']='case:GT_G'
    c=Client();v=compare_in_batches(p,c,tmp_path)
    assert len(v['decisions'])==170 and len(c.calls)==6
    assert all(len(x['candidate_pairs'])<=32 for x in c.calls)


def test_sparse_field_comparison_excludes_only_known_identifiers_and_preserves_all_pairs(tmp_path):
    left=[];right=[]
    for field in ('page','pageSize','中文字段'):
        a=scenario('l-'+field);a.update(field=field,scope='interface',data_location='query');left.append(a)
        b=deepcopy(a);b['id']='r-'+field;right.append(b)
    p=packet('semantic-compare',{'left':left,'right':right,'purpose':'GT_G'});p['node_key']='test:GT_G'
    c=Client();v=compare_in_batches(p,c,tmp_path)
    assert len(v['decisions'])==9 and len(c.calls)==1
    candidates={(r['left_id'],r['right_id']) for r in c.calls[0]['candidate_pairs']}
    assert ('l-page','r-pageSize') not in candidates and ('l-pageSize','r-page') not in candidates
    assert ('l-中文字段','r-page') in candidates
    # A later superset reuses individually verified decisions, rather than
    # rerunning old pairs just because their rectangular batch changed.
    compare_in_batches(p,c,tmp_path);assert len(c.calls)==1
    extra=scenario('extra');p['input']['right'].append(extra)
    compare_in_batches(p,c,tmp_path)
    assert len(c.calls)==2 and all(r['right_id']=='extra' for r in c.calls[-1]['candidate_pairs'])


def test_header_case_is_insensitive_and_sparse_decisions_reject_unrequested_pairs(tmp_path):
    import pytest
    from scene_completion.validation import validate_result
    from scene_completion.comparison_batches import distinct_unit
    a=scenario('a');a.update(field='Authorization',scope='interface',data_location='header')
    b=deepcopy(a);b.update(id='b',field='authorization')
    assert distinct_unit(a,b) is None
    b['data_location']='query';assert distinct_unit(a,b)
    inputs={'left':[a],'right':[b],'purpose':'GT_G','candidate_pairs':[{'left_id':'a','right_id':'b'}]}
    with pytest.raises(ValueError):validate_result('semantic-compare',{'decisions':[]},inputs)
    inputs['candidate_pairs'].append({'left_id':'a','right_id':'unknown'})
    with pytest.raises(ValueError,match='known IDs'):validate_result('semantic-compare',{'decisions':[]},inputs)


def test_exact_normal_rules_and_approved_broad_coverage_need_no_model(tmp_path):
    a=scenario('g');a.update(rule_id='normal-required-id',field='id',scope='interface',data_location='query',concern_key='api.data.completeness')
    exact=deepcopy(a);exact['id']='e-exact'
    broad=deepcopy(a);broad.update(id='e-broad',rule_id=None,field=None,coverage_kind='input_parameters',original_branch_id='branch')
    p=packet('gap-compare',{'left':[a],'right':[exact,broad],'purpose':'G_E'});p['node_key']='test:gap'
    client=Client();v=compare_in_batches(p,client,tmp_path)
    assert not client.calls and len(v['decisions'])==2 and not v['missing']
    # A different necessary condition remains a semantic decision, despite ID.
    exact['conditions']=['another failure condition']
    p=packet('semantic-compare',{'left':[a],'right':[exact],'purpose':'GT_G'});p['node_key']='test:GT_G'
    compare_in_batches(p,client,tmp_path)
    assert len(client.calls)==1
