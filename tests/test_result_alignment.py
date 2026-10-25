from copy import deepcopy
from scene_completion.result_alignment import align_rows,aggregate_metrics
from scene_completion.failure_units import normalize_inverse_units
from scene_completion.task_context import semantic_view
from tests.test_workflow import scenario,exchange


def test_rows_require_all_three_saved_edges_and_keep_broad_references_and_orphans():
    channels={k:[{'id':v,'conditions':['failure']} for v in vs] for k,vs in {'G':['g1','g2','g3'],'E':['e','alone'],'GT':['t1','t2','orphan']}.items()}
    p=lambda a,b:{'checker_scenario_id':a,'generated_scenario_id':b,'status':'full'}
    pairs={'G_E':[p('g1','e'),p('g2','e')],'GT_G':[p('t1','g1'),p('t2','g2')],'GT_E':[p('t1','e')]}
    rows=align_rows(channels,pairs)
    assert [r['status'] for r in rows]==['triple','conflict','single','single','single']
    assert sum('e' in r['shared_e_ids'] for r in rows)==2
    assert {s['id'] for r in rows for s in r['cells']['GT']}=={'t1','t2','orphan'}
    assert all(len(r['cells']['GT'])<=1 for r in rows)


def test_metrics_sum_counts_not_percentages_and_empty_stays_na():
    rows=[{'metrics':{'generation_validity':{'status':'适用','numerator':1,'denominator':2}}},{'metrics':{'generation_validity':{'status':'适用','numerator':1,'denominator':8}}}]
    v=aggregate_metrics(rows);assert v['generation_validity']['value']==20
    assert v['missing_exception_miss_rate']['value'] is None


def test_case_metrics_route_is_not_captured_as_a_case_id(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    app=create_app(tmp_path/'projects');client=TestClient(app)
    rid=client.post('/api/projects',json={'name':'A','sources':{'RR':[{'name':'r.md','content':'RR'}],'SR':[{'name':'s.md','content':'SR'}]}}).json()['id']
    response=client.get('/api/projects/'+rid+'/results/metrics')
    assert response.status_code==200 and response.json()['cases']==[]
    assert response.json()['metrics']['generation_validity']['value'] is None


def test_named_transport_failure_moves_only_to_unique_actual_call_and_keeps_origin():
    request=exchange(sid='call');request['receiver']['name']='LookupService'
    response=deepcopy(request);response.update(id='outer',direction='return');response['receiver']['name']='Human';response['sender']['name']='Boundary'
    s=scenario('t');s.update(interaction_id='outer',object='Boundary',cause='LookupService 查询超时',field=None,data_location=None)
    inputs={'fused-ssd':{'interactions':[request,response]}}
    v=normalize_inverse_units({'scenarios':[s]},inputs)['scenarios'][0]
    assert v['interaction_id']=='call' and v['normalization_origin']['interaction_id']=='outer'
    assert v['cause']==s['cause'] and s['interaction_id']=='outer'
    another=deepcopy(request);another['id']='another';inputs['fused-ssd']['interactions'].append(another)
    assert normalize_inverse_units({'scenarios':[s]},inputs)['scenarios'][0]['interaction_id']=='outer'


def test_binding_and_refinement_use_the_same_unique_failure_owner():
    from scene_completion.failure_units import normalize_bindings
    request=exchange(sid='call');request['receiver']['name']='LookupService'
    result=normalize_bindings({'bindings':[{'branch_id':'B','interaction_id':'return','status':'confirmed','basis':'old'}]},
        {'branches':{'branches':[{'id':'B','description':'LookupService 查询超时，系统返回504'}]},'fused-ssd':{'interactions':[request]}})
    assert result['bindings'][0]['interaction_id']=='call' and '唯一' in result['bindings'][0]['basis']


def test_same_test_tautological_duplicate_merges_but_different_fields_do_not():
    a=scenario('a');a.update(field='id',data_location='path',cause='标识格式错误',source_refs=[{'source_id':'test','line_start':1,'line_end':1,'quote':'| TEST-ID-A | 标识格式错误 |'}])
    b=deepcopy(a);b.update(id='b',cause='标识格式错误导致格式校验失败')
    c=deepcopy(b);c.update(id='c',field='other')
    out=normalize_inverse_units({'scenarios':[a,b,c]},{})['scenarios']
    assert len(out)==2 and out[0]['source_unit_ids']==['a','b'] and out[0]['quality_notes']


def test_semantic_comparison_cannot_be_biased_by_concern_or_response_but_keeps_failure_scope():
    s=scenario('s');s.update(scope='interface',field='id',data_location='path',concern_key='some.classification')
    out=semantic_view('semantic-compare',{'left':[s],'right':[deepcopy(s)],'purpose':'GT_G'})
    assert 'concern_key' not in out['left'][0] and 'steps' not in out['left'][0]
    assert out['left'][0]['scope']=='interface' and out['left'][0]['conditions']==s['conditions']


def test_foreign_local_check_is_evidence_bound_pending_not_a_database_rule():
    from scene_completion.normal_rules import separate_foreign_checks
    i=exchange();i['sender']['name']='Writer';i['receiver']['name']='Database'
    ref={'source_id':'normal','line_start':1,'line_end':1,'quote':'Writer按 requestKey 执行幂等校验。'}
    i['operation']['source_refs']=[ref];i['data']['sequence']=[]
    rule={'id':'r','interaction_id':i['id'],'fields':['requestKey'],'source_refs':[{'source_id':'normal','line_start':2,'line_end':2,'quote':'Writer写入记录。'}]}
    inputs={'fused-ssd':{'interactions':[i]},'normal-documents':[{'source_id':'normal','lines':[{'number':1,'text':ref['quote']},{'number':2,'text':'Writer写入记录。'}]}]}
    out=separate_foreign_checks({'rules':[rule],'pending':[]},inputs)
    assert out['rules']==[] and out['pending'][0]['source_refs']==[ref] and '发送方Writer' in out['pending'][0]['reason']
    i['operation']['source_refs']=[]
    assert separate_foreign_checks({'rules':[rule],'pending':[]},inputs)['rules']==[rule]  # no invented proof
