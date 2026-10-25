"""Evidence-gated inheritance for a single actual service interaction.

Functional kinds come from the SSD operation, never from the capability union.
Registry membership is not evidence for a concrete security/deadline rule.
"""
from copy import deepcopy
import re
from .concern_registry import registry,inheritance_paths
from .storage import fingerprint

FUNCTION_KINDS={'display_interaction':{'display'},'query_retrieval':{'read'},
 'resource_mutation':{'create','update','delete'},'analysis_generation':{'process'},'release_activation':{'publish'}}
DATA_KINDS={'completeness':'required','type':'type','format':'format','length':'length','size':'size','range':'range','legality':'legality'}


def unique(rows):return list({fingerprint(x):x for x in rows}.values())


def context(interaction,inputs):
    from .interaction_enrichment import interactions,resource_metadata
    view=next((v for v in inputs.get('enriched-interactions',{}).get('interactions',[]) if v['id']==interaction['id']),interaction)
    request=interaction
    if interaction['direction']=='return' and interaction.get('parent_id'):
        request=next((v for v in interactions(inputs) if v['id']==interaction['parent_id'] and v['direction']=='request' and v['case_id']==interaction['case_id']),interaction)
    role='receiver' if interaction['direction']=='request' else 'sender'
    party=view[role];position=party['position'];name=party['name']
    resources=resource_metadata(inputs.get('components',{'components':[]}))['resource_services']
    database=bool(party.get('resource_service')) or '数据库' in position or name in {v['name'] for v in resources}
    llm=bool(re.search(r'llm|大语言|large\s*language',name+' '+position,re.I))
    human='人类' in position
    service=not human and (database or llm or any(s in position for s in ('服务','系统边界','外部Actor（系统）','AI模型','UI/前端')) or
        any(s['name']==name for s in inputs.get('api-map',{}).get('services',[])))
    kinds=set(request['operation']['kinds'])
    for rule in inputs.get('normal-rules',{}).get('rules',[]):
        if rule['interaction_id']==request['id']:kinds.update(rule['functional_kinds'])
    return {'view':view,'request':request,'role':role,'party':party,'service':service,'name':name,
      'functions':[k for k,v in FUNCTION_KINDS.items() if kinds&v],
      'technologies':(['database'] if database else [])+(['llm'] if llm else []),'kinds':kinds}


def explicit_guards(match,kind):
    return [g for g in match.get('activation_evidence',[]) if g['kind']==kind and g.get('status','explicit')=='explicit'
            and g.get('value') is not None and g.get('condition') and g.get('source_refs')]


def _data_rule(match,interaction,inputs):
    from .interaction_enrichment import parameters_for
    if match.get('scope','interface')=='storage':
        ctx=context(interaction,inputs)
        if 'database' not in ctx['technologies']:return 'not_applicable','本次对象不是数据库服务'
        if interaction['direction']=='request' and not ctx['kinds']&{'create','update','delete'}:
            return 'not_applicable','只读请求不检查写入存储字段约束'
        guards=explicit_guards(match,'storage_field')
        expected=match['concern_key'].split('.')[-1]
        kinds={'completeness':{'required'},'type':{'type'},'format':{'format','pattern'},'length':{'length'},'size':{'size'},'range':{'minimum','maximum'},'legality':{'enum','other'}}[expected]
        known=[g for g in guards if g.get('field')==match['object'] and g.get('constraint_kind') in kinds]
        if expected=='completeness' and known and all(g['value'] is False for g in known):return 'not_applicable','存储字段不是必填，缺省正常'
        return ('applicable','明示存储Schema规则') if known else ('pending','存储字段的具体规则待确认')
    params=[p for p in parameters_for(interaction,inputs) if p['name']==match['object'] and (not match.get('data_location') or p['location']==match['data_location'])]
    if len(params)!=1:return 'pending','字段位置或参数定义待确认'
    p=params[0];kind=match['concern_key'].split('.')[-1]
    indexed=[r for r in inputs.get('normal-rules',{}).get('rules',[]) if r['interaction_id']==interaction['id'] and r['concern_key']==match['concern_key'] and p['name'] in r['fields']]
    if indexed:return 'applicable','本交互的独立正向规则明确声明该字段校验，具体标准可标条件级'
    known={'completeness':p['required'] is True,'type':p['data_type'] is not None,
      'range':any(r['kind'] in {'minimum','maximum'} and r['status']=='explicit' for r in p['constraints']),
      'legality':any(r['kind'] in {'enum','other'} and r['status']=='explicit' for r in p['constraints'])}
    if kind not in known:
        from .normal_rules import conditional_constraint
        known[kind]=any(r['kind'] in ({'format','pattern'} if kind=='format' else {kind}) and (r['status']=='explicit' or conditional_constraint(r)) for r in p['constraints'])
    if kind=='completeness' and p['required'] is False:return 'not_applicable','可选字段缺省正常'
    return ('applicable','接口中有对应的明示字段约束') if known.get(kind) else ('pending','该字段的具体约束待确认')


def applicability(match,interaction,inputs):
    definition=registry()['definitions'][match['concern_key']];ctx=context(interaction,inputs)
    if match['concern_key'].startswith('api.data.'):return _data_rule(match,interaction,inputs)
    if not ctx['service']:return 'not_applicable','本次对应对象不是被调用Service'
    if definition['technology'] and definition['technology'] not in ctx['technologies']:
        # Explicit technology evidence can establish an otherwise unknown model type.
        if not any(g['value']==definition['technology'] for g in explicit_guards(match,'technology')):
            return 'not_applicable','本次对象没有对应的技术身份依据'
    if definition['operation_kinds'] and not ctx['kinds']&set(definition['operation_kinds']):
        return 'not_applicable','关注点不适用于本次实际操作，不能使用其他支持能力'
    key=match['concern_key']
    if key=='service.base.availability':return 'applicable','本次确实调用该服务，检查调用能否执行'
    if key in {'service.base.request_data','service.base.response_contract'}:
        phase='request' if key.endswith('request_data') else 'return'
        if interaction['direction']!=phase:return 'not_applicable','在对应请求或返回交互中检查'
        from .interaction_enrichment import parameters_for
        return ('applicable','字段检查由共享七类数据关注点细化') if parameters_for(interaction,inputs) else ('pending','具体接口字段或契约待确认')
    if key in {'human.authentication','human.authorization','service_relation.authentication','service_relation.authorization'} and interaction['direction']!='request':
        return 'not_applicable','调用身份和权限在请求方向检查，不在返回交互重复检查'
    if key.startswith('human.') and '人类' not in interaction['sender']['position']:
        return 'not_applicable','仅适用于人类调用方'
    guard_kind=definition['guard'];guards=explicit_guards(match,guard_kind) if guard_kind else []
    if key=='service.query_retrieval.resource_existence':
        from .exception_generation import query_matches
        if any(m['interaction_id']==interaction['id'] for m in query_matches(inputs)):
            return 'applicable','本次实际集合查询及路径资源定位规则'
    if guard_kind in {'authentication','authorization'}:
        values={g['value'] for g in guards if type(g['value']) is bool}
        if values=={False}:return 'not_applicable','明示该接口不要求此项认证或授权'
        if len(values)>1:return 'pending','同一范围的安全要求存在冲突，需确认'
        if not guards:return 'pending','认证或授权的适用条件和正常规则待确认'
    if guard_kind=='timing':
        if not any(g['kind']=='timing' for g in match.get('activation_evidence',[])):return 'not_applicable','本次没有声明实时性、截止时间或时序条件'
        guards=[g for g in guards if (type(g['value']) in (int,float) and g['value']>=0 and g.get('unit')) or (isinstance(g['value'],str) and g['value'].strip())]
        if not guards:return 'pending','已提出时限要求，但阈值、单位或可判定时序条件待确认'
    if guard_kind=='stability':
        guards=[g for g in guards if (isinstance(g['value'],str) and g['value'].strip()) or (type(g['value']) in (int,float) and g.get('unit'))]
    if definition['layer']=='relation':
        # A relation concern applies to this SSD call edge, not merely to two
        # components that happen to appear elsewhere in the composition.
        if not all(any(t in interaction[s]['position'] for t in ('服务','数据库','系统','AI模型')) for s in ('sender','receiver')):
            return 'not_applicable','本次交互不是有依据的服务调用边'
    if not guards:return 'pending','缺少该关注点可判定的正常规则，不生成确定异常'
    return 'applicable','有本次操作适用的明示正常规则及来源'


def concern_scope(match):
    if match.get('scope'):return match['scope']
    if match['concern_key']=='llm.context_sufficiency':return 'context'
    if match['concern_key'].startswith('api.data.'):return 'interface'
    if match['concern_key'].startswith('service_relation.'):return 'relation'
    return 'service'


def decorate(match,interaction,inputs):
    m=deepcopy(match);ctx=context(interaction,inputs);key=m['concern_key']
    m.setdefault('scope',concern_scope(m))
    m.setdefault('data_location',None);m.setdefault('activation_evidence',[])
    m['service']=ctx['name'] if ctx['service'] else None
    m['functional_types']=ctx['functions'];m['technologies']=ctx['technologies']
    for g in explicit_guards(m,'technology'):
        if g['value'] in {'llm','database'} and g['value'] not in m['technologies']:m['technologies'].append(g['value'])
    m['inheritance_paths']=inheritance_paths(key,interaction['direction'],ctx['functions'])
    m['status'],reason=applicability(m,interaction,inputs)
    m['status_reason']=reason
    if m['status']!='applicable':m['concrete_rule']=None
    elif registry()['definitions'][key]['kind']=='family':m['concrete_rule']=None
    elif not m['concrete_rule']:
        if key=='service.base.availability':m['concrete_rule']='本次被调用服务能够执行当前操作'
        else:m['concrete_rule']='；'.join(g['condition'] for g in m['activation_evidence'] if g.get('status','explicit')=='explicit' and g.get('value') is not None) or None
    return m


def resolve_matches(inputs,matches):
    from .interaction_enrichment import interactions
    from .concern_matching import complete_data_matches
    from .exception_generation import query_matches
    from .normal_rules import rule_matches
    reg=registry();by_id={i['id']:i for i in interactions(inputs)};rows=complete_data_matches(inputs,matches)+query_matches(inputs)+rule_matches(inputs)
    # Each *actual provider* inherits the same base profile. Conditional and
    # technology checks are visible in the matrix even when pending/inapplicable.
    for i in by_id.values():
        ctx=context(i,inputs)
        if not ctx['service']:continue
        technology_evidence=unique([g for m in matches if m['interaction_id']==i['id'] for g in explicit_guards(m,'technology')])
        for g in technology_evidence:
            if g['value'] in {'database','llm'} and g['value'] not in ctx['technologies']:ctx['technologies'].append(g['value'])
        keys=list(reg['profiles']['base'])
        if i['direction']=='request' and '人类' in i['sender']['position']:keys+=reg['profiles']['human']
        for function in ctx['functions']:keys+=reg['profiles']['functional'][function]
        for tech in ctx['technologies']:keys+=reg['profiles']['technology'][tech]
        keys+=reg['profiles']['conditional']+reg['profiles']['relation']
        for key in keys:
            rows.append({'interaction_id':i['id'],'target':ctx['role'],'object':ctx['name'],'concern_key':key,
              'basis':'基础继承/本次实际功能/技术身份/条件性规则','concrete_rule':None,'source_refs':i['source_refs'],'activation_evidence':technology_evidence})
    grouped={}
    for raw in rows:
        i=by_id[raw['interaction_id']];m=deepcopy(raw);ctx=context(i,inputs)
        # Authentication belongs to the incoming caller of this service. Do not
        # duplicate it once on a human and again on the provider.
        if m['concern_key'] in {'human.authentication','human.authorization','service_relation.authentication','service_relation.authorization'} and i['direction']=='request':
            m.update(target='sender',object=i['sender']['name'])
        if m['target']=='data' and not m.get('data_location') and m.get('scope','interface')=='interface':
            from .interaction_enrichment import parameters_for
            parameters=[v for v in parameters_for(i,inputs) if v['name']==m['object']]
            if len(parameters)==1:m['data_location']=parameters[0]['location']
        scope=concern_scope(m)
        key=(m['interaction_id'],m['target'],m['object'],m['concern_key'],scope,m.get('data_location'))
        if key not in grouped:grouped[key]=m
        else:
            old=grouped[key];old['source_refs']=unique(old['source_refs']+m['source_refs'])
            old['activation_evidence']=unique(old.get('activation_evidence',[])+m.get('activation_evidence',[]))
            if not old.get('concrete_rule'):old['concrete_rule']=m.get('concrete_rule')
    for child in list(grouped.values()):
        parents={k for path in inheritance_paths(child['concern_key']) for k in path[:-1]}
        for parent in grouped.values():
            if parent['interaction_id']==child['interaction_id'] and parent['concern_key'] in parents and parent['object']==child['object'] and child['target']!='data':
                parent['activation_evidence']=unique(parent.get('activation_evidence',[])+child.get('activation_evidence',[]))
    resolved=[decorate(m,by_id[m['interaction_id']],inputs) for m in grouped.values()]
    pending=[{'interaction_id':m['interaction_id'],'object':m['object'],'concern_key':m['concern_key'],
              'reason':m['status_reason'],'source_refs':m['source_refs']} for m in resolved if m['status']=='pending']
    return {'matches':resolved,'pending':unique(pending)}


def match_is_applicable(match,interaction,inputs):
    # Re-evaluate supplied standalone inputs, not just the claimed status.
    status,_=applicability(match,interaction,inputs)
    return match.get('status',status)=='applicable' and status=='applicable'
