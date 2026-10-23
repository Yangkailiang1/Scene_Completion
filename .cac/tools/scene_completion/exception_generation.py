from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .interaction_enrichment import interactions,parameters_for,resolved_api_id,stable,resource_metadata
from .concern_matching import concern_by_label
def data_exceptions(inputs):
    """One known violation per field/rule. Missing optional parameters never fail."""
    output=[]
    labels={'required':'数据完整性','type':'数据类型','enum':'数据合法性','minimum':'数据范围','maximum':'数据范围',
            'format':'数据格式','length':'数据长度','size':'数据大小','pattern':'数据格式','other':'数据合法性'}
    for i in interactions(inputs):
        matches={(m['object'],m['concern_key']) for m in inputs.get('concern-match',{}).get('matches',[]) if m['interaction_id']==i['id'] and m['target']=='data'}
        for p in parameters_for(i,inputs):
            rules=[]
            if p['required'] is True:rules.append(('required','missing_required',True,p['source_refs']))
            if p['data_type'] is not None:rules.append(('type','type',p['data_type'],p['source_refs']))
            rules += [(r['kind'],r['kind'],r['value'],r['source_refs']) for r in p['constraints'] if r['status']=='explicit' and r['kind']!='type']
            for kind,cause,value,refs in rules:
                key=concern_by_label(labels[kind])
                if (p['name'],key) not in matches: continue
                rule_id=stable('rule',[resolved_api_id(i,inputs),p['location'],p['name'],kind,value])
                conditions=([p['name']+'未提供'] if cause=='missing_required' else [p['name']+'已提供',f'违反{kind}约束: '+json.dumps(value,ensure_ascii=False,sort_keys=True)])
                s={'id':stable('G',[i['id'],rule_id]),'case_id':i['case_id'],'interaction_id':i['id'],'layer':i['layer'],
                   'object':p['name'],'operation':i['operation']['name'],'cause':cause,'conditions':conditions,
                   'concern_key':key,'field':p['name'],'rule_id':rule_id,'source_status':'framework_inferred',
                   'derivation':f'字段{p["name"]}的明示{kind}规则取反；可选字段仅在提供时检查。','source_refs':refs,'steps':scenario_steps(i,conditions)}
                output.append(s)
    return deduplicate(output)


def scenario_key(s):
    return (s['case_id'],s['layer'],s['interaction_id'],s['object'],s['operation'],s['cause'],tuple(sorted(set(s['conditions']))))


def deduplicate(scenarios):
    result={}
    for s in scenarios:
        k=scenario_key(s)
        if k not in result:result[k]=deepcopy(s)
        else:result[k]['source_refs']=list({fingerprint(r):r for r in result[k]['source_refs']+s['source_refs']}.values())
    return list(result.values())


def pending_rules(inputs):
    """Unknown positive properties are diagnostic, never failure scenarios."""
    out=[]
    for i in interactions(inputs):
        for p in parameters_for(i,inputs):
            for rule in p['constraints']:
                if rule['status']=='pending':out.append({'interaction_id':i['id'],'object':p['name'],
                  'concern_key':{'format':'api.data.format','length':'api.data.length','size':'api.data.size','type':'api.data.type'}.get(rule['kind'],'api.data.legality'),
                  'reason':f'{rule["kind"]}具体约束待确认，不进入G','source_refs':rule['source_refs'] or p['source_refs']})
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
    meta=inputs.get('enriched-interactions',{}).get('interactions',[])
    for i in interactions(inputs):
        if i['direction']!='request' or not set(i['operation']['kinds'])<={'read','display'}:continue
        # The operation's own wording must establish collection semantics.
        if not re.search(r'列表|集合|list\b|collection|search\b',i['operation']['name'],re.I):continue
        v=next((x for x in meta if x['id']==i['id']),i)
        party=v['receiver'];facades=resource_metadata(inputs.get('components',{'components':[]}))['resource_services']
        db=party.get('resource_service') is not None or '数据库' in party['position'] or party['name'] in {f['name'] for f in facades}
        service=db or '服务' in party['position'] or 'service' in party['position'].lower()
        if not service:continue
        key='internal_database.resource_existence' if db else 'service.query_retrieval.resource_existence'
        out.append({'interaction_id':i['id'],'target':'receiver','object':i['receiver']['name'],'concern_key':key,
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
    return out
