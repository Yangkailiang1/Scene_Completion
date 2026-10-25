"""Frozen positive inputs: scenario granularity, isolation and risk backstop."""
from copy import deepcopy
import pytest
from tests.test_workflow import memory_inputs,R,scenario,decision,fake_pipeline
from scene_completion.scenario_patterns import applicability,generated,normalize_settings,default_library,canonical_instances,inverse_metadata,VERSION
from scene_completion.recommendation import rank,evaluate,historical_score
from scene_completion.pattern_settings import settings,save_settings,import_history,feedback,review_candidate,history,adoption
from scene_completion.contracts import registry,validate,packet
from scene_completion.validation import validate_result
from scene_completion.workflow import Execution,build_pipeline
from scene_completion.exception_comparison import coverage_assignment,compare_report

def positive():
    x=memory_inputs();x['enriched-interactions']={'interactions':deepcopy(x['sr-ssd']['interactions'])};x['normal-rules']={'rules':[],'pending':[]};return x

def auth(x,key='human.authentication',condition='请求必须携带有效Token，校验Token有效期，过期不可使用'):
    x['normal-rules']['rules'].append({'id':'nr-'+key,'interaction_id':'req','owner_service':'Platform','concern_key':key,'condition':condition,'violation':'SECRET_INVERSE_NOT_READ','fields':[],'functional_kinds':['read'],'resolution':'explicit','pending_details':[],'source_refs':R})

def accepted(matrix):return generated(matrix)['scenarios']

def test_eight_rules_split_bounds_not_values_and_optional_absence_normal():
    x=positive();matrix=applicability(x);g=accepted(matrix)
    assert len([s for s in g if s['concern_key'].startswith('api.data.')])==8
    assert {(s['pattern_id'],s['failure_rule']['value']) for s in g if s['field']=='pageSize' and s['concern_key']=='api.data.range'}=={('data.minimum',1),('data.maximum',100)}
    assert not any(s['cause']=='missing_required' and s['field'] in {'page','pageSize','memoryType'} for s in g)
    assert all(s['confidence']['score']==1 for s in g if s['field'])
    validate('pattern-applicability',matrix);validate_result('pattern-applicability',matrix,{'positive':x,'settings':normalize_settings()})
    validate_result('exception-generate',generated(matrix),{'pattern-applicability':matrix})
    bad=deepcopy(matrix);bad['instances'][0]['scenario']['confidence']['score']=.99
    with pytest.raises(ValueError):validate_result('pattern-applicability',bad,{'positive':x,'settings':normalize_settings()})

def test_security_one_to_many_and_unknown_critical_separate():
    x=positive();auth(x);m=applicability(x)
    gs={s['pattern_id'] for s in accepted(m)}
    assert {'human.credential.missing','human.credential.expired'}<=gs
    assert 'human.credential.invalid' not in gs
    assert 'human.credential.revoked' not in gs
    auth(x,'human.authorization','调用需要权限校验，资源必须属于当前用户')
    m=applicability(x);r=rank(accepted(m),m)
    assert any(s['pattern_id']=='human.authorization.horizontal' for s in r['Q'])
    assert any(v['scenario']['pattern_id']=='human.authorization.tenant' for v in r['critical_review'])
    assert all(s['confidence']['score']>=.85 for s in r['Q'])
    assert 'SECRET_INVERSE_NOT_READ' not in str(m)

def test_missing_premise_framework_only_never_enters_G():
    x=positive();x['concern-match']['matches'].append({'interaction_id':'req','target':'sender','object':'开发者','concern_key':'human.authorization','status':'pending','source_refs':R})
    m=applicability(x);assert not any(s['pattern_id'].startswith('human.authorization') for s in accepted(m))
    assert any(i['scenario']['confidence']['score']==.6 for i in m['instances'])

def test_project_confirmation_requires_premise_and_versions(tmp_path):
    x=positive();auth(x,'human.authorization','执行本次操作需要权限');m=applicability(x);item=next(i for i in m['instances'] if i['pattern_id']=='human.authorization.tenant')
    v=settings(tmp_path);body={'expected_version':v['version'],'candidate_id':item['id'],'choice':'confirm','note':'业务确认'}
    with pytest.raises(ValueError):review_candidate(tmp_path,body,m)
    new=review_candidate(tmp_path,{**body,'positive_condition':'当前接口按租户隔离资源，调用方仅可访问本租户'},m)
    updated=applicability(x,new['settings']);s=next(i for i in updated['instances'] if i['id']==item['id'])
    assert s['status']=='accepted' and s['scenario']['executable'] is False
    assert s['scenario']['confidence']['score']==.85
    assert settings(tmp_path,v['version'])['version']==v['version']
    with pytest.raises(ValueError):save_settings(tmp_path,{'expected_version':v['version'],'settings':v['settings']})

def test_disabled_pattern_critical_gap_not_in_G():
    x=positive();v=normalize_settings();v['library']['patterns']=[p for p in v['library']['patterns'] if p['id']!='data.minimum'];m=applicability(x,v)
    assert not any(s['pattern_id']=='data.minimum' for s in accepted(m))
    assert any('data.minimum' in i['reason'] for i in m['issues'])
    assert rank(accepted(m),m,v)['critical_review']

def test_one_failure_multiple_concerns_not_multiple_scores():
    x=positive();i=x['enriched-interactions']['interactions'][0]
    from tests.test_workflow import parameter
    i['data']['sequence']=[parameter('Authorization','header',True)]
    x['api-parameters']['apis'][0]['parameters'].append(parameter('Authorization','header',True))
    x['concern-match']['matches'].append({'interaction_id':'req','target':'data','object':'Authorization','concern_key':'api.data.completeness','basis':'必填','concrete_rule':'required','source_refs':R})
    auth(x);g=accepted(applicability(x));rows=[s for s in g if 'human.credential.missing' in s['linked_pattern_ids']]
    assert len(rows)==1 and {'human.authentication','api.data.completeness'}<=set(rows[0]['concern_origins'])
    assert canonical_instances(rows+rows)==rows

def test_generic_E_auth_covers_children_only_same_interaction_and_not_GT():
    x=positive();auth(x);auth(x,'human.authorization','调用需要权限校验');m=applicability(x);g=accepted(m)
    e=scenario('e',status='explicit');e.update(object='开发者',concern_key='human.authentication',original_branch_id='b',coverage_kind='exact')
    inputs={'fused-ssd':x['enriched-interactions'],'branches':{'branches':[{'id':'b','description':'认证失败'}]}}
    annotated=inverse_metadata({'scenarios':[e]},inputs)['scenarios'][0]
    assert annotated['coverage_kind']=='authentication'
    pairs=coverage_assignment([],g,[annotated]);ids={p['checker_scenario_id'] for p in pairs}
    assert ids=={s['id'] for s in g if s['concern_key']=='human.authentication'}
    other=deepcopy(annotated);other['interaction_id']='other';assert not coverage_assignment([],g,[other])
    assert inverse_metadata({'scenarios':[e]},inputs,truth=True)['scenarios'][0]['coverage_kind']=='exact'

def test_zero_history_critical_above_K_stable_and_GT_not_ranking_input():
    x=positive();auth(x,'human.authorization','角色权限由管理员控制，资源属于当前用户，按租户隔离权限');m=applicability(x);v=normalize_settings({'top_k':1});g=accepted(m)
    r=rank(g,m,v,case_id='case',run_id='run');critical=[s for s in g if s['risk']['level']=='critical']
    assert len(critical)>=2 and len(r['Q'])==len(critical)
    assert r['critical_overflow']==len(critical)-1
    assert all(a['history_score']==.5 for a in r['ranked'])
    assert r==rank(list(reversed(g)),m,v,case_id='case',run_id='run')
    with pytest.raises(TypeError):rank(g,m,v,GT=[])

def test_history_human_version_case_run_isolation_and_neutral_prior(tmp_path):
    x=positive();m=applicability(x);s=accepted(m)[0]
    row={'id':'h','pattern_id':s['pattern_id'],'pattern_hash':s['pattern_versions'][s['pattern_id']],'library_version':VERSION,'context':s['scenario_context'],'human_reviewed':True,'decision':'adopt','source_channel':'business_review','case_id':'old-case','run_id':'old-run','reviewed_at':1,'source':'人工复核'}
    h=import_history(tmp_path,{'revision':0,'items':[row]})
    score,proof=historical_score(s,h['items'],'new-case','new-run',VERSION);assert score> .5 and proof
    for patch in [{'case_id':'new-case'},{'run_id':'new-run'},{'source_channel':'automatic_gt'},{'human_reviewed':False},{'library_version':'old'}]:
        assert historical_score(s,[{**row,**patch}],'new-case','new-run',VERSION)==(.5,[])
    with pytest.raises(ValueError):import_history(tmp_path,{'revision':1,'items':[{**row,'id':'gt','source_channel':'test_gt'}]})

def test_feedback_latest_only_and_defer_not_negative(tmp_path):
    m=applicability(positive());r=rank(accepted(m),m,case_id='c',run_id='r');s=r['Q'][0]
    b={'revision':0,'settings_hash':r['settings_hash'],'scenario_id':s['id'],'choice':'adopt'}
    h=feedback(tmp_path,b,r);assert len(h['items'])==1 and adoption(tmp_path,r)['value']==100
    h=feedback(tmp_path,{**b,'revision':h['revision'],'choice':'defer'},r)
    assert not h['items'] and adoption(tmp_path,r)['value'] is None

def test_recommendation_formulas_GT_independent_and_empty():
    m=applicability(positive());g=accepted(m);r=rank(g,m,{'top_k':1});q=r['Q'][0]
    gt=deepcopy(q);gt.update(id='gt',source_status='explicit')
    report=compare_report(g,[],[gt],[],[decision('gt',q['id'])],[]);out=evaluate(report,r)
    assert out['metrics']['recommendation_adoption']['value']==100 and out['metrics']['recommendation_false_positive']['value']==0
    report=compare_report(g,[],[],[],[],[]);assert evaluate(report,r)['metrics']['recommendation_false_positive']['status']=='不适用'

def test_new_pipeline_nodes_and_no_test_dependency_in_G_or_Q(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);ex=Execution(tmp_path/'v4',mocks=m,config={'scenario_patterns':True});build_pipeline(ex,rr,sr,[]);out=ex.finish()
    assert out['complete'],ex.scheduler.state
    tasks=ex.scheduler.tasks
    assert tasks['UC-X:exception-generate'].deps==('UC-X:pattern-applicability',)
    assert set(tasks['UC-X:gap-recommend'].deps)=={'UC-X:missing-report','UC-X:pattern-applicability'}
    assert not any('GT' in d or 'test-' in d for d in tasks['UC-X:gap-recommend'].deps)

def test_structured_length_bounds_and_test_samples_do_not_inflate_count():
    from tests.test_workflow import parameter
    from scene_completion.test_supplement import mechanical_tests
    x=positive();p=parameter('name','query',False,'string',rules=[('length',{'min':1,'max':20})]);x['api-parameters']['apis'][0]['parameters'].append(p)
    x['concern-match']['matches'].append({'interaction_id':'req','target':'data','object':'name','concern_key':'api.data.length','basis':'明确区间','concrete_rule':'length','source_refs':R})
    rows=[s for s in accepted(applicability(x)) if s['field']=='name' and s['concern_key']=='api.data.length']
    assert len(rows)==2 and {s['pattern_id'] for s in rows}=={'data.length.minimum','data.length.maximum'}
    tests=mechanical_tests({'fused-ssd':x['enriched-interactions'],'normal-constraints':x['api-parameters'],'normal-rules':{'rules':[]}})['tests']
    assert {t['failure_rule']['kind'] for t in tests if t['field']=='name' and t['concern_key']=='api.data.length'}=={'length.minimum','length.maximum'}

def test_mode_semantic_revision_excludes_old_history():
    x=positive();v=normalize_settings();m=applicability(x,v);s=accepted(m)[0]
    row={'id':'old','pattern_id':s['pattern_id'],'library_version':VERSION,'pattern_hash':'different-definition','context':s['scenario_context'],'human_reviewed':True,'decision':'adopt','source_channel':'business_review','case_id':'old','run_id':'old'}
    assert historical_score(s,[row],'new','new',VERSION)==(.5,[])

def test_no_unknown_NaN_or_duplicate_pattern_settings():
    for patch in [{'threshold':float('nan')},{'risk_weight':float('nan')},{'library':[]}]:
        with pytest.raises(ValueError):normalize_settings(patch)
    s=normalize_settings();s['library']['patterns'].append(s['library']['patterns'][0])
    with pytest.raises(ValueError):normalize_settings(s)

def test_patterns_project_api_isolated_and_run_recommendation_visible(tmp_path):
    from fastapi.testclient import TestClient
    from scene_completion.workbench import create_app
    client=TestClient(create_app(tmp_path))
    def create(name):return client.post('/api/projects',json={'name':name,'sources':{'RR':[{'name':'rr.md','content':'# RR'}],'SR':[{'name':'sr.md','content':'# SR'}]}}).json()['id']
    a,b=create('A'),create('B');url=f'/api/projects/{a}/patterns';v=client.get(url).json();v['settings']['top_k']=3
    saved=client.put(url,json={'expected_version':v['version'],'settings':v['settings']});assert saved.status_code==200
    assert client.get(f'/api/projects/{b}/patterns').json()['settings']['top_k']==10
    assert client.put(url,json={'expected_version':v['version'],'settings':v['settings']}).status_code==400
    assert client.get(url,params={'version':v['version']}).status_code==200
    assert client.get(f'/api/projects/{a}/recommendations').json()['result']=={}
    assert client.post(f'/api/projects/{a}/recommendation-history',json={'revision':0,'items':[{'id':'test_gt'}]}).status_code==400

def test_proven_no_send_does_not_consume_budget_but_timeout_still_reserves(tmp_path):
    from scene_completion.model_client import SemanticClient
    from scene_completion.storage import read_json
    def failure(not_sent):
        def transport(*args):
            e=RuntimeError('network');e.response_diagnostic={'failure_category':'connection_failed','request_not_sent':not_sent};raise e
        return transport
    cfg={'base_url':'http://offline/v1','api_key':'test','token_budget_limit':100000,'token_budget_ledger':str(tmp_path/'ledger.json'),'unknown_usage_policy':'reserve_and_continue'}
    body={'model':'offline','messages':[{'role':'user','content':'hi'}],'max_tokens':10}
    with pytest.raises(RuntimeError):SemanticClient(cfg,transport=failure(True)).post('/chat/completions',body)
    assert read_json(tmp_path/'ledger.json')['committed_tokens']==0
    with pytest.raises(RuntimeError):SemanticClient(cfg,transport=failure(False)).post('/chat/completions',body)
    assert read_json(tmp_path/'ledger.json')['committed_tokens']>0

def test_different_concrete_samples_same_structured_violation_only_one_unit():
    s=next(s for s in accepted(applicability(positive())) if s['pattern_id']=='data.minimum')
    a,b=deepcopy(s),deepcopy(s);a['conditions']=['page=-1'];b['conditions']=['page=-2'];b['id']='second-sample'
    assert len(canonical_instances([a,b]))==1

def test_branch_error_code_evidence_restored_only_inside_allowed_case():
    from scene_completion.branch_evidence import complete
    b={'id':'b','description':'库存不足，OUT_OF_STOCK','source_refs':R}
    x={'existing-documents':[{'source_id':'sr','lines':[{'number':10,'text':'- A3：库存不足，错误码 OUT_OF_STOCK。'}]}]}
    assert complete({'branches':[b]},x)['branches'][0]['source_refs'][-1]['line_start']==10
    with pytest.raises(ValueError):complete({'branches':[b]},{'existing-documents':[]})

def test_ranking_validation_rejects_GT_input_and_non_M_candidate():
    m=applicability(positive());s=normalize_settings();g=accepted(m);r=rank(g,m,s,[],case_id='c',run_id='r');inputs={'missing-report':{'M':g},'pattern-applicability':m,'settings':s,'history':[],'case_id':'c','run_id':'r'}
    validate_result('gap-recommend',r,inputs)
    with pytest.raises(ValueError):validate_result('gap-recommend',r,{**inputs,'GT':[]})
    tamper=deepcopy(r);tamper['Q']=[]
    with pytest.raises(ValueError):validate_result('gap-recommend',tamper,inputs)

def test_metadata_migration_pins_new_hash_without_overwriting_old_snapshot(tmp_path):
    from scene_completion.storage import write_json,read_json
    v=settings(tmp_path);raw=deepcopy(v['settings'])
    for p in raw['library']['patterns']:p.pop('definition_hash',None)
    from scene_completion.storage import fingerprint
    raw['hash']=fingerprint({k:x for k,x in raw.items() if k!='hash'});old=raw['hash']
    write_json(tmp_path/'pattern-versions'/(old+'.json'),raw);write_json(tmp_path/'pattern-settings.json',{'version':old,'history':[{'version':old,'at':1}]})
    new=settings(tmp_path);assert new['version']==new['settings']['hash'] and new['version']!=old
    assert read_json(tmp_path/'pattern-versions'/(old+'.json'))==raw

def test_positive_reuse_never_reads_E_GT_and_revalidates_contract(tmp_path):
    from scene_completion.positive_reuse import find,normalized_skill
    from scene_completion.storage import write_json,fingerprint
    from scene_completion.contracts import schema
    row={'task':'api-map','skill':'same','schema_hash':fingerprint(schema('api-map')),'payload':{'services':[]},'source_project':'old','source_key':'api-map','source_output_hash':'proof'}
    write_json(tmp_path/'positive_reuse.json',{'seeds':[row]})
    assert find(tmp_path,'api-map',{'SR':[]},[],'same')[0]=={'services':[]}
    assert find(tmp_path,'api-map',{'SR':[]},[],'changed') is None
    assert find(tmp_path,'existing-extract',{},[],'same') is None
    row['schema_hash']='wrong';write_json(tmp_path/'positive_reuse.json',{'seeds':[row]});assert find(tmp_path,'api-map',{'SR':[]},[],'same') is None
