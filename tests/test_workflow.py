"""Offline acceptance frozen against the approved 27-page method, not a live run."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from scene_completion.contracts import PROTOCOL,registry,validate,packet
from scene_completion.source_documents import read_documents,normal_projection
from scene_completion.exception_generation import data_exceptions
from scene_completion.validation import validate_result
from scene_completion.exception_comparison import compare_report
from scene_completion.interaction_enrichment import resource_metadata
from scene_completion.concern_matching import concern_by_label
from scene_completion.evaluation import accuracy
from scene_completion.workflow import Execution,build_pipeline

REF={'source_id':'positive','line_start':1,'line_end':1,'quote':'known positive constraint'}
R=[REF]

def parameter(name,location='query',required=False,dtype=None,rules=(),default=None):
    return {'name':name,'location':location,'required':required,'data_type':dtype,'default':default,
            'constraints':[{'id':name+'-'+kind,'kind':kind,'value':v,'status':'explicit','source_refs':R} for kind,v in rules], 'source_refs':R}

def exchange(case='CASE-A',sid='req',layer='SR',api='API-M-IF2'):
    return {'id':sid,'case_id':case,'sequence':1,'parent_id':None,'layer':layer,
     'sender':{'name':'开发者','position':'外部Actor（人类）','source_refs':R},
     'receiver':{'name':'Platform','position':'系统边界','source_refs':R},
     'operation':{'name':'查询记忆库列表','kinds':['read'],'sequence':['查询记忆库列表'],'optional':[],'source_refs':R},
     'data':{'sequence':[]},'direction':'request','api_id':api,'source_refs':R}

def memory_inputs():
    i=exchange()
    params=[parameter('x-wisecloud-service-id','header',True),parameter('memoryInstanceID','path',True),
     parameter('memoryType',rules=[('enum',['PROFILE','SEMANTIC'])]),
     parameter('page',dtype='integer',rules=[('minimum',1)],default=1),
     parameter('pageSize',dtype='integer',rules=[('minimum',1),('maximum',100)],default=20)]
    api={'id':'API-M-IF2','name':'查询记忆库列表','address':'/ms/v1/memory-instances/{memoryInstanceID}/mem-repos','parameters':params,'source_refs':R}
    matches=[]
    labels={'required':'数据完整性','type':'数据类型','enum':'数据合法性','minimum':'数据范围','maximum':'数据范围'}
    for p in params:
        keys=set([r['kind'] for r in p['constraints']]+(['required'] if p['required'] else [])+(['type'] if p['data_type'] else []))
        for k in keys:matches.append({'interaction_id':'req','target':'data','object':p['name'],'concern_key':concern_by_label(labels[k]),'basis':'known positive constraint','concrete_rule':k,'source_refs':R})
    return {'components':{'components':[],'relations':[]},'rr-ssd':{'interactions':[]},'sr-ssd':{'interactions':[i]},
      'api-map':{'services':[]},'api-parameters':{'apis':[api]},'concern-match':{'matches':matches,'pending':[]},'enriched-interactions':{'interactions':[]},'registry':registry()}

def scenario(sid='one',cause='missing_required',status='framework_inferred'):
    return {'id':sid,'case_id':'CASE-A','interaction_id':'req','layer':'SR','object':'instance','operation':'read',
     'cause':cause,'conditions':['id not found'],'concern_key':'service.query_retrieval.resource_existence',
     'field':None,'rule_id':None,'source_status':status,'derivation':'normal contract negation' if status!='explicit' else '', 'source_refs':R,'steps':{'normal_context':['read'],'trigger':cause,'documented_follow_up':[]}}

def decision(a,b,status='full'):return {'left_id':a,'right_id':b,'status':status,'reason':'same complete cause and necessary conditions'}

def test_registry_and_eight_data_exceptions():
    approved=json.loads((Path(__file__).parent/'fixtures/workflow_v1/acceptance.json').read_text())
    assert registry()['version']=='interaction-concerns-v3'
    assert len(registry()['legacy_mapping'])==57
    x=memory_inputs();out=data_exceptions(x)
    assert sorted([s['field'],s['cause']] for s in out)==sorted(approved['expected_data_rules'])
    validate_result('exception-generate',{'scenarios':out,'pending':[]},x)
    assert not any('default' in s['cause'] for s in out)


def test_unknown_constraints_and_required_provided_are_not_invented():
    x=memory_inputs();p=x['api-parameters']['apis'][0]['parameters'][0]
    p['constraints']=[{'id':'unknown-format','kind':'format','value':None,'status':'pending','source_refs':[]}]
    assert len(data_exceptions(x))==8
    assert [s['cause'] for s in data_exceptions(x) if s['field']==p['name']]==['missing_required']


def test_generic_case_not_hardcoded():
    x=memory_inputs();x['sr-ssd']['interactions'][0].update(id='generic-call',case_id='UC-GENERIC',api_id='search-jobs')
    x['sr-ssd']['interactions'][0]['operation']['name']='list jobs'
    x['api-parameters']['apis'][0]['id']='search-jobs'
    for p in x['api-parameters']['apis'][0]['parameters']:p['name']='job_'+p['name']
    for m in x['concern-match']['matches']:m.update(interaction_id='generic-call',object='job_'+m['object'])
    out=data_exceptions(x)
    assert len(out)==8 and all(s['case_id']=='UC-GENERIC' and s['operation']=='list jobs' for s in out)


def test_no_mutation_for_read_even_if_object_has_write_capability():
    x=memory_inputs();x.pop('concern-match')
    m={'interaction_id':'req','target':'receiver','object':'Platform','concern_key':'service.resource_mutation.persistence_consistency',
       'basis':'supports write','concrete_rule':'can write','source_refs':R}
    with pytest.raises(ValueError,match='read-only'):validate_result('concern-match',{'matches':[m],'pending':[]},x)


def test_channel_isolation_and_operation_projection():
    x=memory_inputs()
    with pytest.raises(ValueError):packet('exception-generate',{**x,'E':[]})
    with pytest.raises(ValueError):packet('test-ground-truth',{'test-documents':[],'normal-constraints':{},'registry':registry(),'G':[]})
    with pytest.raises(ValueError):packet('object-operations',{'components':{},'rr-ssd':{},'test-operations':{'objects':[],'exceptions':['secret']}})
    with pytest.raises(ValueError):packet('rr-ssd',{'RR':[{'channel':'existing','lines':[]}]})


def test_positive_projection_excludes_extension_section(tmp_path):
    p=tmp_path/'rr.md';p.write_text('# UC-1\n5. 主成功路径：\n①查询\n6. 扩展路径：\n1.a 无匹配项\n1.b 错误码404\n### UC-2\n5. 主成功路径：\n查询其他对象\n')
    normal=normal_projection(read_documents([p],'existing'))
    text=str(normal)
    assert '404' not in text and '无匹配项' not in text and '查询其他对象' in text


def test_resource_service_preserves_db_and_no_endpoint():
    comps={'components':[{'id':'db','name':'SomeDB','composition_type':'外部数据库','source_refs':R}],'relations':[]}
    m=resource_metadata(comps)
    service=m['resource_services'][0]
    assert service['physical_resource_id']=='db' and service['resource_origin']=='external' and service['logical_only']
    assert 'address' not in service and 'method' not in service


def test_full_only_partial_and_empty_list_not_instance_missing():
    g=[scenario('g',cause='instance_missing')];e=[scenario('e',cause='empty_list',status='explicit')];t=[scenario('t',cause='instance_missing',status='explicit')]
    r=compare_report(g,e,t,[decision('g','e','partial')],[decision('t','g')],[decision('t','e','partial')])
    assert len(r['M'])==1 and r['metrics']['missing_exception_miss_rate']['value']==0
    assert r['metrics']['generation_validity']['value']==100
    assert r['metrics']['recommendation_adoption']=={'value':None,'status':'未启用'}
    assert len(r['partial_diagnostics'])==2


def test_duplicates_one_to_one_and_inferred_gt_scores_separately():
    g=scenario('g');t=scenario('t')
    r=compare_report([g,deepcopy(g)],[],[t],[],[decision('t','g')],[])
    assert r['metrics']['generation_validity']['denominator']==1
    assert r['truth_breakdown']['framework_inferred']['numerator']==1
    assert r['truth_breakdown']['explicit']['status']=='不适用'
    empty=compare_report([],[],[],[],[],[])
    assert empty['metrics']['generation_validity']['value'] is None


def test_partial_never_scores_and_match_scope():
    r=compare_report([scenario('g')],[],[scenario('t')],[],[decision('t','g','partial')],[])
    assert r['metrics']['missing_exception_miss_rate']['value']==100
    assert r['metrics']['generation_validity']['value']==0
    a=scenario('a');b=scenario('b');b['layer']='RR'
    with pytest.raises(ValueError,match='cross'):validate_result('semantic-compare',{'decisions':[decision('a','b')]},{'left':[a],'right':[b],'purpose':'GT_G'})


def test_extraction_units_acc_and_pending():
    a={'objects':[{'name':'actor','supported_operations':[{'name':'read','source_refs':R},{'name':'read','source_refs':R}]}]}
    t=deepcopy(a);t['objects'][0]['supported_operations'].append({'name':'write','source_refs':R})
    r=accuracy('object-operations',a,t)
    assert (r['Acc'],r['H'],r['N'])==(50,1,2)
    p=memory_inputs()['api-parameters'];truth=deepcopy(p)
    assert accuracy('api-parameters',p,truth)['Acc']==100
    assert accuracy('components',{'components':[]},{'components':[]})['status']=='不适用'


def fake_pipeline(tmp_path,mocks=None):
    def doc(name,text,channel):
        p=tmp_path/name;p.write_text(text);return read_documents([p],channel)
    rr=doc('rr.md','# UC-X\nnormal request\n6. 扩展路径：\nexisting empty result\n','existing')
    sr=doc('sr.md','# UC-X\nnormal call\n','existing');tests=doc('test.md','# UC-X\ncheck read\n','test')
    empty={
      'components':{'components':[],'relations':[]},'rr-ssd':{'interactions':[]},'sr-ssd':{'interactions':[]},
      'api-map':{'services':[]},'api-parameters':{'apis':[]},'test-operation-project':{'objects':[]},
      'object-operations':{'objects':[]},'concern-match':{'matches':[],'pending':[]},
      'exception-generate':{'scenarios':[],'pending':[]},'existing-extract':{'scenarios':[]},
      'test-ground-truth':{'scenarios':[]},'gap-compare':{'decisions':[],'missing':[]},'interaction-align':{'aliases':[],'links':[]}}
    def ref(doc):return [{'source_id':doc[0]['source_id'],'line_start':2,'line_end':2,'quote':doc[0]['lines'][1]['text']}]
    def rewrite(v,refs):
        if isinstance(v,dict):
            return {k:deepcopy(refs) if k=='source_refs' else rewrite(x,refs) for k,x in v.items()}
        if isinstance(v,list):return [rewrite(x,refs) for x in v]
        return v
    rr_i=rewrite(exchange(case='UC-X',sid='rr-call',layer='RR',api=None),ref(rr))
    sr_i=rewrite(exchange(case='UC-X',sid='sr-call',layer='SR',api=None),ref(sr))
    empty['rr-ssd']={'interactions':[rr_i]};empty['sr-ssd']={'interactions':[sr_i]}
    empty['components']={'components':[{'id':'actor','name':'开发者','composition_type':'外部Actor（人类）','parent_id':None,'source_status':'explicit','source_refs':ref(rr)},
      {'id':'platform','name':'Platform','composition_type':'系统边界','parent_id':None,'source_status':'explicit','source_refs':ref(rr)}],'relations':[]}
    if mocks is not None:empty=mocks
    install_catalogue_mocks(empty)
    return rr,sr,tests,empty


def install_catalogue_mocks(m):
    def catalogue(p):
        cases=[]
        for d in p['input']['documents']:
            title=d['lines'][0];cid=title['text'].lstrip('# ').split('：')[0]
            cases.append({'id':cid,'name':cid,'goal':'normal request','actors':['开发者'],'layer':p['input']['layer'],'source_ranges':[{'source_id':d['source_id'],'start':title['number'],'end':d['lines'][-1]['number']}],
              'source_refs':[{'source_id':d['source_id'],'line_start':title['number'],'line_end':title['number'],'quote':title['text']}]})
        return {'cases':cases}
    def align(p):
        rr=p['input']['rr-cases']['cases'];sr=p['input']['sr-cases']['cases']
        return {'groups':[{'id':a['id'],'rr_ids':[a['id']],'sr_ids':[b['id'] for b in sr if b['id']==a['id']],
           'status':'confirmed','reason':'test fixture explicit shared case','source_refs':a['source_refs']} for a in rr]}
    def fused(p):
        values=[]
        for t in ('rr-ssd','sr-ssd'):
            v=m[t](p) if callable(m[t]) else deepcopy(m[t])
            if 'interactions' not in v:return v
            values+=v['interactions']
        rr=[i for i in values if i['layer']=='RR'];sr=[i for i in values if i['layer']=='SR']
        return {'interactions':values,'rr_sr_links':[{'rr_id':rr[0]['id'],'sr_ids':[i['id'] for i in sr],
          'status':'confirmed','basis':'explicit fixture refinement','source_refs':rr[0]['source_refs']}],'pending':[]}
    m.update({'use-case-extract':catalogue,'use-case-align':align,'fused-ssd':fused})


def test_pipeline_mock_completes_without_recommendation_or_embedding_and_cache(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);calls=[]
    def capture(task,value):
        def f(p):calls.append(p['task']);return value(p) if callable(value) else deepcopy(value)
        return f
    mocks={k:capture(k,v) for k,v in m.items()}
    run=tmp_path/'run'
    ex=Execution(run,mocks=mocks);build_pipeline(ex,rr,sr,t)
    assert ex.finish()['complete'];n=len(calls)
    ex=Execution(run,mocks=mocks);build_pipeline(ex,rr,sr,t)
    assert ex.finish()['complete'] and len(calls)==n
    assert 'gap-recommend' not in calls
    result=json.loads((run/'missing_report.json').read_text())
    assert 'Q' not in result and result['recommendation']['enabled'] is False
    for file in (run/'packets').glob('*.json'):
        packet=json.loads(file.read_text())
        if packet['task']=='exception-generate':assert 'existing empty result' not in json.dumps(packet)
    with pytest.raises(ValueError,match='mock'):Execution(run)


def test_legacy_cache_refused(tmp_path):
    (tmp_path/'run_manifest.json').write_text('{"protocol":"rr-sr-concern-gap-v2"}')
    with pytest.raises(ValueError,match='different protocol'):Execution(tmp_path)


def test_invalid_schema_rejected_bounded_and_preserved(tmp_path):
    ex=Execution(tmp_path,mocks={'rr-ssd':{'unknown':True}})
    ex.add('rr-ssd','rr-ssd',static={'RR':[]})
    assert not ex.finish()['complete']
    assert ex.scheduler.state['tasks']['rr-ssd']['rounds']<=2
    assert list((tmp_path/'attempts').rglob('*.json'))


def test_projection_cannot_smuggle_test_answers_in_quote():
    source={'source_id':'test','channel':'test','name':'test.md','lines':[{'number':1,'text':'read fails with 404'}]}
    bad={'objects':[{'name':'actor','supported_operations':[{'name':'read','source_refs':[{'source_id':'test','line_start':1,'line_end':1,'quote':'read fails with 404'}]}]}]}
    with pytest.raises(ValueError,match='only'):validate_result('test-operation-project',bad,{'test-operation-source':[source]})
    bad['objects'][0]['supported_operations'][0]['source_refs'][0]['quote']='read'
    validate_result('test-operation-project',bad,{'test-operation-source':[source]})


def test_sr_resource_binding_keeps_physical_identity():
    from scene_completion.interaction_enrichment import bind_resource_services
    from scene_completion.exception_generation import pending_rules
    x=memory_inputs();x['components']['components']=[{'id':'db','name':'AnyDB','composition_type':'内部数据库','source_refs':R}]
    x['sr-ssd']['interactions'][0]['receiver'].update(name='AnyDB',position='内部数据库')
    bound=bind_resource_services(x)
    assert bound['sr-ssd']['interactions'][0]['receiver']['name']=='AnyDB资源服务'
    assert bound['components']['components'][0]['name']=='AnyDB'
    assert len(pending_rules(x))==2


def test_dependency_local_retry_test_change_cannot_invalidate_G(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);calls=[]
    def capture(task,val):
        def f(p):calls.append(task);return val(p) if callable(val) else deepcopy(val)
        return f
    mocks={k:capture(k,v) for k,v in m.items()};root=tmp_path/'run'
    ex=Execution(root,mocks=mocks);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    calls.clear();t[0]['lines'].append({'number':3,'text':'new test exception, private expected response'})
    ex=Execution(root,mocks=mocks);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert 'test-ground-truth' in calls and 'test-operation-project' in calls
    assert not set(calls)&{'components','rr-ssd','sr-ssd','api-map','api-parameters','concern-match','exception-generate','existing-extract'}


def test_real_semantic_transport_schema_mode_is_explicit_and_validated(tmp_path):
    from scene_completion.model_client import SemanticClient
    sent=[]
    def transport(url,key,body,timeout,retries):
        sent.append(body)
        return {'model':'mock-provider','choices':[{'finish_reason':'stop','message':{'content':'{"interactions":[]}'}}]}
    config={'base_url':'http://test.invalid/v1','agent_model':'mock','max_retries':0,'max_tokens':2000}
    c=SemanticClient(config,transport=transport)
    c.api_key='offline-test-only'
    p=packet('rr-ssd',{'RR':[]})
    assert c.agent(p)['interactions']==[]
    assert sent[-1]['response_format']=={'type':'json_object'}
    c.config['structured_output']='json_schema';c.agent(p)
    assert sent[-1]['response_format']['json_schema']['strict'] is True
    assert sent[-1]['response_format']['json_schema']['schema']['additionalProperties'] is False


def test_exhaustive_comparison_rejects_missing_pairs():
    with pytest.raises(ValueError,match='every candidate'):validate_result('semantic-compare',{'decisions':[]},{'left':[scenario('g')],'right':[scenario('e')],'purpose':'G_E'})


def test_first_rr_interaction_uses_explicit_receiver_api_map():
    x=memory_inputs();i=x['sr-ssd']['interactions'].pop();i.update(layer='RR',api_id=None)
    x['rr-ssd']['interactions']=[i]
    x['api-map']={'services':[{'name':'Platform','interfaces':[{'id':'API-M-IF2','name':i['operation']['name'],'method':None,'address':None,'source_refs':R}],'source_refs':R}]}
    assert len(data_exceptions(x))==8
    x['api-map']['services'][0]['name']='Unrelated service'
    assert data_exceptions(x)==[]


def test_gt_unknown_ssd_attribute_not_required_to_match():
    out=exchange();out['data']['sequence']=[parameter('p',dtype='integer',rules=[('minimum',1)])]
    truth=deepcopy(out);truth['data']['sequence'][0]['data_type']=None
    truth['data']['sequence'][0]['constraints']=[]
    assert accuracy('rr-ssd',{'interactions':[out]},{'interactions':[truth]})['Acc']==100


def test_checked_in_schema_matches_runtime():
    from scene_completion.contracts import SCHEMAS,schema
    folder=Path(__file__).resolve().parents[1]/'docs/scene-workflow-v2/schemas'
    for key in SCHEMAS:assert json.loads((folder/(key+'.schema.json')).read_text())==schema(key)


def test_GT_cannot_be_inferred_only_from_normal_rules_without_test_description():
    s=scenario()
    with pytest.raises(ValueError,match='test description'):
        validate_result('test-ground-truth',{'scenarios':[s]}, {'test-documents':[],'normal-constraints':{'source_refs':R},'registry':registry()})


def test_capability_union_not_extra_ssd_interactions():
    from scene_completion.interaction_enrichment import capability_union
    rr=exchange(layer='RR',api=None)
    p={'components':{'components':[],'relations':[]},'rr-ssd':{'interactions':[rr]},
       'test-operations':{'objects':[{'name':'Platform','supported_operations':[{'name':'write','source_refs':R}]}]}}
    table=capability_union(p)
    assert {o['name'] for o in table['objects'][0]['supported_operations']}=={'查询记忆库列表','write'}
    assert len(p['rr-ssd']['interactions'])==1 and p['rr-ssd']['interactions'][0]['operation']['kinds']==['read']


def test_independent_api_table_ids_resolve_by_exact_documented_address():
    x=memory_inputs();i=x['sr-ssd']['interactions'][0];i['api_id']='map-id'
    a=x['api-parameters']['apis'][0]
    x['api-map']={'services':[{'name':'Platform','interfaces':[{'id':'map-id','name':a['name'],'method':None,'address':a['address'],'source_refs':R}],'source_refs':R}]}
    a['id']='parameters-id'
    assert len(data_exceptions(x))==8
    a['address']='a completely different address'
    assert data_exceptions(x)==[]


def test_cli_task_disabled_does_not_require_model_configuration(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1];source=tmp_path/'empty.json';source.write_text('{}')
    p=subprocess.run([sys.executable,str(root/'.cac/tools/scene_completion.py'),'task','--task','gap-recommend',
                      '--input-json',str(source),'--output-dir',str(tmp_path/'out'),'--agent-mode','external'],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    out=json.loads((tmp_path/'out/artifacts/shared/gap-recommend.json').read_text())
    assert out['payload']=={'enabled':False,'status':'未启用'}


def test_cli_default_prepares_scoped_packets_without_model(tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    rr=tmp_path/'rr.md';sr=tmp_path/'sr.md';rr.write_text('# UC-X\nactor requests read\n');sr.write_text('# UC-X\nservice reads\n')
    p=subprocess.run([sys.executable,str(root/'.cac/tools/scene_completion.py'),'pipeline',
      '--rr-spec-document',str(rr),'--sr-spec-document',str(sr),'--output-dir',str(tmp_path/'out')],capture_output=True,text=True)
    assert p.returncode==2,p.stderr
    manifest=json.loads((tmp_path/'out/run_manifest.json').read_text())
    assert manifest['protocol']==PROTOCOL and not manifest['complete']
    assert manifest['tasks']['gap-recommend']=='passed'
    packets=[json.loads(x.read_text()) for x in (tmp_path/'out/packets').glob('*.json')]
    assert packets and all(x['protocol']==PROTOCOL for x in packets)


def test_invalidated_run_does_not_publish_stale_report(tmp_path):
    rr,sr,t,m=fake_pipeline(tmp_path);root=tmp_path/'run'
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);assert ex.finish()['complete']
    assert (root/'missing_report.json').exists()
    rr[0]['lines'][1]['text']='changed normal request'
    m['rr-ssd']={'interactions':[]}
    ex=Execution(root,mocks=m);build_pipeline(ex,rr,sr,t);assert not ex.finish()['complete']
    assert not (root/'missing_report.json').exists()
    assert not (root/'artifacts'/__import__('scene_completion.workflow',fromlist=['safe_case']).safe_case('UC-X')/'rr-ssd.json').exists()


def test_bad_input_shape_is_a_contract_error():
    with pytest.raises(ValueError,match='named JSON'):packet('rr-ssd',[])
    with pytest.raises(ValueError,match='comparison scenario'):packet('gap-compare',{'left':[{}],'right':[],'purpose':'G_E'})


def test_unmarked_exception_section_is_excluded_conservatively(tmp_path):
    p=tmp_path/'rr.md';p.write_text('# UC-1\n主成功请求\n**扩展路径**\n返回未找到\n错误码404\n## UC-2\n正常请求\n')
    result=normal_projection(read_documents([p],'existing'))
    assert '未找到' not in str(result) and '404' not in str(result) and '正常请求' in str(result)
