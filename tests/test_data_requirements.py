from copy import deepcopy
from scene_completion.data_requirements import field_requirements,split_size_scenarios
from scene_completion.interaction_enrichment import parameters_for,requirement_sources
from scene_completion.exception_generation import data_exceptions
from scene_completion.test_supplement import mechanical_tests
from scene_completion.concern_alignment import recognize,compare
from scene_completion.scenario_patterns import applicability,generated,inverse_metadata
from scene_completion.comparison_batches import compare_in_batches
from scene_completion.contracts import packet
from tests.test_workflow import memory_inputs,parameter,R,scenario
from tests.test_comparison_batches import Client


def inputs_for(p):
    x=memory_inputs();x['sr-ssd']['interactions'][0]['data']['sequence']=[deepcopy(p)]
    x['api-parameters']['apis'][0]['parameters']=[deepcopy(p)]
    x['normal-rules']={'rules':[],'pending':[]}
    x['enriched-interactions']={'interactions':x['sr-ssd']['interactions']}
    return x


def identify(x,keys):
    i=x['sr-ssd']['interactions'][0];p=i['data']['sequence'][0]
    rows=[{'interaction_id':i['id'],'target':'data','object':p['name'],'concern_key':key,'basis':'本交互的明示要求','concrete_rule':'按文档校验字段','data_location':p['location'],'source_refs':p['source_refs']} for key in keys]
    x['concern-match']=recognize(x,{'matches':rows,'pending':[]})
    return x['concern-match']


def independent_tests(x):
    return mechanical_tests({'fused-ssd':x['sr-ssd'],'normal-constraints':x['api-parameters'],'normal-rules':x['normal-rules']})['tests']


def test_union_keeps_both_types_required_and_source_defaults_without_mutating_inputs():
    actual=parameter('payload','body',True,'string');actual['default']='a'
    x=inputs_for(actual);api=x['api-parameters']['apis'][0]['parameters'][0];api.update(data_type='integer',required=False,default=20)
    original=deepcopy(x);i=x['sr-ssd']['interactions'][0];p=parameters_for(i,x)[0]
    assert p['required'] is True and {r['value'] for r in field_requirements(p) if r['kind']=='type'}=={'integer','string'}
    sources=requirement_sources(i,x)[0]['sources']
    assert {(s['origin'],str(s['default'])) for s in sources}=={('SSD','a'),('API','20')}
    assert x==original
    identify(x,['api.data.type','api.data.completeness'])
    g=data_exceptions(x);gt=independent_tests(x)
    assert {s['failure_rule']['value'] for s in g if s['failure_rule']['kind']=='type'}=={'integer','string'}
    assert {s['failure_rule']['value'] for s in gt if s.get('failure_rule',{}).get('kind')=='type'}=={'integer','string'}
    assert sum(s['cause']=='missing_required' for s in g)==1
    assert not any('默认' in s['cause'] or '一致性' in s['cause'] for s in g)


def test_unknown_attributes_do_not_erase_known_and_locations_or_directions_do_not_merge():
    p=parameter('id','path',True,'string');x=inputs_for(p);api=x['api-parameters']['apis'][0]['parameters'][0];api.update(data_type=None,required=None,default=None)
    api['constraints']=[{'id':'max','kind':'maximum','value':9,'status':'explicit','source_refs':R}]
    x['sr-ssd']['interactions'][0]['data']['sequence'][0]['constraints']=[{'id':'min','kind':'minimum','value':1,'status':'explicit','source_refs':R}]
    x['api-parameters']['apis'][0]['parameters'] += [parameter('id','query',False,'integer'),parameter('secret','response',True,'string')]
    rows=parameters_for(x['sr-ssd']['interactions'][0],x)
    assert {(p['location'],p['name']) for p in rows}=={('path','id'),('query','id')}
    assert rows[0]['data_type']=='string' and len(rows[0]['constraints'])==2
    again=parameters_for({**x['sr-ssd']['interactions'][0],'data':{'sequence':rows}},x)
    assert again==rows


def test_directionless_evidenced_size_is_one_concern_two_conditional_scenes_and_independent_tests():
    p=parameter('image','body',False)
    p['constraints']=[{'id':'size','kind':'size','value':None,'status':'pending','source_refs':[{**R[0],'quote':'校验图片文件大小符合要求'}]}]
    x=inputs_for(p);c=identify(x,['api.data.size']);assert len(c['matches'])==1
    g=generated(applicability(x))['scenarios'];gt=independent_tests(x)
    assert {s['failure_rule']['kind'] for s in g}=={'size.minimum','size.maximum'}
    assert all(s['resolution']=='conditional' and not s['executable'] and s['failure_rule']['value'] is None for s in g)
    assert {s['failure_rule']['kind'] for s in gt if s['concern_key']=='api.data.size'}=={'size.minimum','size.maximum'}
    assert len(compare(c,{'matches':[]},c)['G_c'])==1
    x['concern-match']={'matches':[],'pending':[]}
    assert not generated(applicability(x))['scenarios']


def test_explicit_one_sided_size_only_expands_that_side():
    p=parameter('file','body',False)
    p['constraints']=[{'id':'s','kind':'size','value':100,'status':'explicit','source_refs':[{**R[0],'quote':'文件大小不超过100字节'}]}]
    assert [(r['kind'],r['value']) for r in field_requirements(p)]==[('size.maximum',100)]
    p['constraints'][0]['source_refs'][0]['quote']='文件大小至少100字节'
    assert [(r['kind'],r['value']) for r in field_requirements(p)]==[('size.minimum',100)]


def test_duplicate_constraints_merge_provenance_and_positive_rule_only_size_is_shared():
    p=parameter('image','body',False)
    ref={**R[0],'quote':'校验图片文件大小符合要求'}
    p['constraints']=[{'id':'ssd-size','kind':'size','value':None,'status':'pending','source_refs':[ref]}]
    x=inputs_for(p);api=x['api-parameters']['apis'][0]['parameters'][0]
    api['constraints'][0].update(id='api-size',source_refs=[{**ref,'source_id':'other'}])
    union=parameters_for(x['sr-ssd']['interactions'][0],x)[0]
    assert len(union['constraints'])==1 and len(union['constraints'][0]['source_refs'])==2
    x=inputs_for(parameter('image','body',False));i=x['sr-ssd']['interactions'][0]
    x['normal-rules']['rules']=[{'id':'positive','interaction_id':i['id'],'concern_key':'api.data.size','fields':['image'],'functional_kinds':['read'],'source_refs':[ref]}]
    identify(x,['api.data.size'])
    assert {s['failure_rule']['kind'] for s in data_exceptions(x)}=={'size.minimum','size.maximum'}
    assert {s['failure_rule']['kind'] for s in independent_tests(x) if s.get('concern_key')=='api.data.size'}=={'size.minimum','size.maximum'}


def test_return_provenance_never_imports_api_request_business_fields():
    x=inputs_for(parameter('businessResult','business',False))
    i=x['sr-ssd']['interactions'][0];i['direction']='return'
    x['api-parameters']['apis'][0]['parameters']=[parameter('requestOnly','business',True),parameter('result','response',True)]
    expected={('business','businessResult'),('response','result')}
    assert {(p['location'],p['name']) for p in parameters_for(i,x)}==expected
    assert {(p['location'],p['name']) for p in requirement_sources(i,x)}==expected


def test_inverse_size_modes_are_independent_and_do_not_convert_format_or_quantity(tmp_path):
    a=scenario('size');a.update(concern_key='api.data.size',field='image',object='image',cause='图片大小不符合要求',conditions=['图片大小不符合要求'],scope='interface',data_location='body')
    g=split_size_scenarios([a]);assert len(g)==2 and split_size_scenarios(g)==g
    only=deepcopy(a);only.update(cause='图片太大',conditions=['超过上限'])
    assert [s['failure_rule']['kind'] for s in split_size_scenarios([only])]==['size.maximum']
    fmt=deepcopy(a);fmt['concern_key']='api.data.format';assert split_size_scenarios([fmt])==[fmt]
    file=deepcopy(g[0]);count=deepcopy(file);count['id']='count';count['predicate']['measure']='item_count'
    p=packet('semantic-compare',{'left':[file],'right':[count],'purpose':'GT_G'});p['node_key']='compare';c=Client()
    assert compare_in_batches(p,c,tmp_path)['decisions'][0]['status']=='unmatched' and not c.calls
    known=deepcopy(file);known['id']='numeric';known['failure_rule']['value']=10
    p['input']['right']=[known]
    assert compare_in_batches(p,c,tmp_path)['decisions'][0]['status']=='unmatched'
