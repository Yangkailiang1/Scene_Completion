from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .interaction_enrichment import interactions,parameters_for,resolved_api_id,stable,resource_metadata
from .concern_matching import concern_by_label
from .concern_registry import inheritance_paths,failure_family
from .concern_hierarchy import match_is_applicable,context
def data_exceptions(inputs):
    """One known violation per field/rule. Missing optional parameters never fail."""
    from .normal_rules import conditional_constraint,descriptive_constraint
    output=[]
    labels={'required':'数据完整性','type':'数据类型','enum':'数据合法性','minimum':'数据范围','maximum':'数据范围',
            'format':'数据格式','length':'数据长度','size':'数据大小','pattern':'数据格式','other':'数据合法性'}
    for i in interactions(inputs):
        matches={(m.get('data_location'),m['object'],m['concern_key']) for m in inputs.get('concern-match',{}).get('matches',[]) if m['interaction_id']==i['id'] and m['target']=='data' and m.get('scope','interface')=='interface' and match_is_applicable(m,i,inputs)}
        for p in parameters_for(i,inputs):
            rules=[]
            if p['required'] is True:rules.append(('required','missing_required',True,p['source_refs']))
            if p['data_type'] is not None:rules.append(('type','type',p['data_type'],p['source_refs']))
            rules += [(r['kind'],r['kind'],r['value'],r['source_refs']) for r in p['constraints'] if (r['status']=='explicit' or conditional_constraint(r)) and r['kind']!='type' and not descriptive_constraint(r)]
            for kind,cause,value,refs in rules:
                key=concern_by_label(labels[kind])
                if (p['location'],p['name'],key) not in matches and (None,p['name'],key) not in matches: continue
                rule_id=stable('rule',[resolved_api_id(i,inputs),p['location'],p['name'],kind,value])
                conditions=([p['name']+'未提供'] if cause=='missing_required' else [p['name']+'已提供',f'违反{kind}约束: '+json.dumps(value,ensure_ascii=False,sort_keys=True)])
                s={'id':stable('G',[i['id'],rule_id]),'case_id':i['case_id'],'interaction_id':i['id'],'layer':i['layer'],
                   'object':p['name'],'operation':i['operation']['name'],'cause':cause,'conditions':conditions,
                   'concern_key':key,'field':p['name'],'rule_id':rule_id,'source_status':'framework_inferred',
                   'derivation':f'字段{p["name"]}的明示{kind}规则取反；可选字段仅在提供时检查。','source_refs':refs,'steps':scenario_steps(i,conditions),'scope':'interface','data_location':p['location'],
                   'concern_origins':[key],'concern_paths':inheritance_paths(key,i['direction'])}
                conditional=any(r['kind']==kind and conditional_constraint(r) for r in p['constraints'])
                s.update(resolution='conditional' if conditional else 'explicit',executable=not conditional,pending_details=[kind+'具体约束待确认'] if conditional else [])
                if conditional:
                    s['conditions']=[p['name']+'已提供','不满足原文明示的'+kind+'规则（具体标准待确认）'];s['steps']=scenario_steps(i,s['conditions'])
                output.append(s)
    return deduplicate(output)


def scenario_key(s):
    # Different inheritance labels do not create different failure units.
    normalize=lambda v:' '.join(v.casefold().split())
    cause={'服务不可用':'service_unavailable','超时':'timeout','结果错误':'incorrect_result'}.get(s['cause'],s['cause'])
    return (s['case_id'],s.get('canonical_interaction_id',s['interaction_id']),s['object'],s['operation'],cause,
            tuple(sorted({normalize(x) for x in s['conditions']})),(s.get('scope','interface' if s.get('field') else 'service') if s.get('field') or s.get('scope') in {'interface','storage','context'} else 'service'),
            s.get('data_location'),failure_family(s['concern_key']))


def annotate_scenario(s):
    s=deepcopy(s);s.setdefault('scope','interface' if s.get('field') else 'service');s.setdefault('data_location',None)
    s['concern_origins']=list(dict.fromkeys(s.get('concern_origins',[])+[s['concern_key']]))
    paths=s.get('concern_paths') or inheritance_paths(s['concern_key'])
    if s['scope']=='interface' and s.get('field'):
        # The interaction ID keeps directions separate; a deterministic field
        # producer supplies its exact request/return inheritance path.
        paths=s.get('concern_paths') or paths
    s['concern_paths']=list({fingerprint(p):p for p in paths}.values())
    return s


def deduplicate(scenarios):
    result={}
    for raw in scenarios:
        s=annotate_scenario(raw);key=scenario_key(s)
        if key not in result:result[key]=s;continue
        previous=result[key]
        # Prefer a more specific refinement and retain every original path.
        rank=lambda row:(max(map(len,inheritance_paths(row['concern_key']))),row['concern_key'])
        chosen=deepcopy(max((previous,s),key=rank))
        chosen['id']=previous['id']
        for field in ('source_refs','concern_paths','concern_origins','source_unit_ids','quality_notes'):
            chosen[field]=list({fingerprint(v):v for v in previous.get(field,[])+s.get(field,[])}.values())
        chosen['steps']['documented_follow_up']=list({fingerprint(v):v for v in previous['steps']['documented_follow_up']+s['steps']['documented_follow_up']}.values())
        result[key]=chosen
    return list(result.values())


def pending_rules(inputs):
    """Unknown positive properties are diagnostic, never failure scenarios."""
    from .normal_rules import conditional_constraint
    out=[]
    for i in interactions(inputs):
        for p in parameters_for(i,inputs):
            for rule in p['constraints']:
                if rule['status']=='pending' or conditional_constraint(rule):out.append({'interaction_id':i['id'],'object':p['name'],
                  'concern_key':{'format':'api.data.format','length':'api.data.length','size':'api.data.size','type':'api.data.type'}.get(rule['kind'],'api.data.legality'),
                  'reason':f'{rule["kind"]}具体约束待确认，已有条件级异常，不能直接执行' if conditional_constraint(rule) else f'{rule["kind"]}具体约束待确认，不进入G','source_refs':rule['source_refs'] or p['source_refs']})
            if p['required'] is True and p['data_type'] is None and not any(r['status']=='explicit' for r in p['constraints']):
                out.append({'interaction_id':i['id'],'object':p['name'],'concern_key':'api.data.legality',
                  'reason':'必填字段已提供但违反约束：具体类型、格式或取值规则待确认，不进入G','source_refs':p['source_refs']})
    return list({fingerprint(x):x for x in out}.values())



def scenario_steps(i,conditions):
    return {'normal_context':[i['sender']['name']+' → '+i['receiver']['name']+'：'+i['operation']['name']],
            'trigger':'；'.join(conditions),'documented_follow_up':[]}

def query_matches(inputs):
    """An actual list/collection query implies a distinct no-match candidate."""
    import re
    out=[]
    for i in interactions(inputs):
        ctx=context(i,inputs)
        if i['direction']!='request' or 'query_retrieval' not in ctx['functions'] or not ctx['service']:continue
        collection=bool(re.search(r'列表|集合|list\b|collection|search\b',i['operation']['name'],re.I))
        key='service.query_retrieval.resource_existence'
        if collection:out.append({'interaction_id':i['id'],'target':'receiver','object':i['receiver']['name'],'concern_key':key,
          'basis':'本次操作明确查询列表或集合','concrete_rule':'查询集合可能无匹配记录（不等同实例不存在）','source_refs':i['operation']['source_refs']})
        api=next((a for a in inputs.get('api-parameters',{}).get('apis',[]) if a['id']==resolved_api_id(i,inputs)),None)
        if api and api['address']:
            for p in parameters_for(i,inputs):
                if p['location']=='path' and p['required'] is True and ('{'+p['name']+'}') in api['address']:
                    out.append({'interaction_id':i['id'],'target':'receiver','object':i['receiver']['name'],'concern_key':key,
                     'basis':'接口以必填路径参数定位指定资源','concrete_rule':'指定路径资源不存在: '+p['name'],'source_refs':p['source_refs']})
    return out

def query_exceptions(inputs):
    by_id={i['id']:i for i in interactions(inputs)};out=[]
    for m in query_matches(inputs):
        i=by_id[m['interaction_id']]
        resource=m['concrete_rule'].startswith('指定路径资源不存在: ')
        cause='requested_resource_not_found' if resource else 'no_matching_records'
        conditions=[m['concrete_rule']] if resource else ['按本次查询条件检索无匹配记录']
        out.append({'id':stable('G',[i['id'],cause,conditions]),'case_id':i['case_id'],'interaction_id':i['id'],
        'layer':i['layer'],'object':m['object'],'operation':i['operation']['name'],'cause':cause,
        'conditions':conditions,'concern_key':m['concern_key'],'field':None,'rule_id':None,
        'source_status':'framework_inferred','derivation':m['concrete_rule'],'source_refs':m['source_refs'],'steps':scenario_steps(i,conditions)})
    return deduplicate(out)


def service_exceptions(inputs):
    """Availability is a framework check on the actual call, not on all nodes."""
    out=[]
    for i in interactions(inputs):
        if i['direction']!='request':continue
        ctx=context(i,inputs)
        matches=[m for m in inputs.get('concern-match',{}).get('matches',[]) if m['interaction_id']==i['id'] and m['concern_key']=='service.base.availability' and match_is_applicable(m,i,inputs)]
        if not ctx['service'] or not matches:continue
        conditions=['本次被调用服务无法执行当前操作']
        out.append({'id':stable('G',[i['id'],'service_unavailable']),'case_id':i['case_id'],'interaction_id':i['id'],
         'layer':i['layer'],'object':ctx['name'],'operation':i['operation']['name'],'cause':'service_unavailable',
         'conditions':conditions,'concern_key':'service.base.availability','field':None,'rule_id':None,'source_status':'framework_inferred',
         'derivation':'所有实际调用的Service均继承基础可用性；不推断具体故障原因或响应行为','source_refs':i['source_refs'],
         'steps':scenario_steps(i,conditions)})
    return deduplicate(out)


def storage_exceptions(inputs):
    out=[];by_id={i['id']:i for i in interactions(inputs)}
    labels={'required':'completeness','type':'type','enum':'legality','minimum':'range','maximum':'range','format':'format','pattern':'format','length':'length','size':'size','other':'legality'}
    for m in inputs.get('concern-match',{}).get('matches',[]):
        i=by_id.get(m['interaction_id'])
        if i is None or m.get('scope')!='storage' or not match_is_applicable(m,i,inputs):continue
        for g in m.get('activation_evidence',[]):
            kind=g.get('constraint_kind');value=g.get('value')
            if g['kind']!='storage_field' or g.get('status')!='explicit' or kind not in labels or value is None or not g.get('field'):continue
            if 'api.data.'+labels[kind]!=m['concern_key']:continue
            if kind=='required' and value is not True:continue
            conditions=[g['field']+'未提供'] if kind=='required' else [g['field']+'已提供','违反'+kind+'约束: '+json.dumps(value,ensure_ascii=False,sort_keys=True)]
            rule=stable('rule',['storage',m['service'],g['field'],kind,value])
            out.append({'id':stable('G',[i['id'],rule]),'case_id':i['case_id'],'interaction_id':i['id'],'layer':i['layer'],
             'object':g['field'],'operation':i['operation']['name'],'cause':'missing_required' if kind=='required' else kind,'conditions':conditions,
             'concern_key':m['concern_key'],'field':g['field'],'rule_id':rule,'source_status':'framework_inferred',
             'derivation':'本次操作的明示存储Schema规则取反，不混同接口字段约束','source_refs':g['source_refs'],'steps':scenario_steps(i,conditions),
             'scope':'storage','data_location':'storage','concern_origins':[m['concern_key']],'concern_paths':inheritance_paths(m['concern_key'],i['direction'])})
    return deduplicate(out)


def attach_provenance(inputs,scenarios):
    by_id={i['id']:i for i in interactions(inputs)};out=[]
    for raw in scenarios:
        s=deepcopy(raw);i=by_id[s['interaction_id']]
        matches=[m for m in inputs['concern-match']['matches'] if (m['interaction_id'],m['object'],m['concern_key'])==(s['interaction_id'],s['object'],s['concern_key']) and match_is_applicable(m,i,inputs)]
        if matches:
            s.setdefault('scope',matches[0].get('scope','interface' if s.get('field') else 'service'))
            if s.get('field'):s.setdefault('data_location',matches[0].get('data_location'))
        paths=[path for m in matches for path in m.get('inheritance_paths',[])]
        s['concern_paths']=list({fingerprint(path):path for path in paths}.values()) or inheritance_paths(s['concern_key'],i['direction'],context(i,inputs)['functions'])
        s['concern_origins']=[s['concern_key']]
        out.append(s)
    return out
