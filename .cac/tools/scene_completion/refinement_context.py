"""Scoped inverse refinement, using only independently recognized anchors.

Known normal idempotent replay is excluded before semantic refinement.
"""
from copy import deepcopy
from .storage import fingerprint


def bindings(inputs):
    return {m['binding_id']:m for m in inputs.get('identified-concerns',{}).get('matches',[]) if m.get('status')=='applicable' and m.get('binding_id')}


def narrow(out,original):
    known=bindings(original)
    if not known or 'fused-ssd' not in out:return out
    selected=list(known.values());ids={m['interaction_id'] for m in selected};keys={m['concern_key'] for m in selected};fields={m['object'] for m in selected if m['target']=='data'}
    rows=out.get('fused-ssd',{}).get('interactions',[])
    out['interaction_index']=[{'id':i['id'],'direction':i['direction'],'sender':i['sender']['name'],'receiver':i['receiver']['name'],'operation':i['operation']['name']} for i in rows]
    out['fused-ssd']['interactions']=[i for i in rows if i['id'] in ids]
    rules=out.get('normal-rules',{}).get('rules',[])
    out['normal-rules']={'rules':[r for r in rules if r['interaction_id'] in ids and (r['concern_key'] in keys or set(r['fields']) & fields)],'pending':[]}
    apis=out.get('normal-constraints',{}).get('apis',[]);api_ids={i.get('api_id') for i in original.get('fused-ssd',{}).get('interactions',[]) if i['id'] in ids};api_ids.discard(None)
    scoped=[]
    for a in apis:
        if api_ids and a['id'] not in api_ids:continue
        p=[p for p in a['parameters'] if p['name'] in fields and any(m['object']==p['name'] and m.get('data_location') in (None,p['location']) for m in selected if m['target']=='data')]
        if p:scoped.append({**a,'parameters':p})
    out['normal-constraints']={'apis':scoped}
    if 'registry' in out:
        defs=out['registry']['definitions'];needed=set(keys)
        while True:
            parents={p for k in needed for p in defs.get(k,{}).get('parents',[])}
            if parents<=needed:break
            needed.update(parents)
        out['registry']['definitions']={k:d for k,d in defs.items() if k in needed}
    out['identified-concerns']={'matches':[{'binding_ref':k,**{f:deepcopy(m[f]) for f in ('interaction_id','target','object','concern_key','data_location','source_refs') if f in m}} for k,m in known.items()]}
    return out


def compact_schema(schema,inputs):
    from .contracts import S,arr
    result=deepcopy(schema);row=result['properties']['scenarios']['items'];props=row['properties']
    keep={'cause','conditions','derivation','source_refs','resolution','executable','pending_details','scenario_type','coverage_kind'}
    row['properties']={k:v for k,v in props.items() if k in keep}
    row['properties'].update(binding_ref={'enum':list(bindings(inputs))},trigger=S,documented_follow_up=deepcopy(props['steps']['properties']['documented_follow_up']))
    row['required']=[k for k in row['required'] if k in keep]+['binding_ref','trigger','documented_follow_up']
    return result


def expand(row,inputs,task):
    if 'binding_ref' not in row:return row
    value=deepcopy(row);ref=value.pop('binding_ref');m=bindings(inputs).get(ref)
    if m is None:raise ValueError('binding_ref must be an independently recognized concern in this task')
    i=next(i for i in inputs['fused-ssd']['interactions'] if i['id']==m['interaction_id'])
    bid=next((b['id'] for b in inputs.get('branches',{}).get('branches',[]) if not m.get('source_branch_ids') or b['id'] in m['source_branch_ids']),None)
    value.update(id='refined-'+fingerprint([ref,value])[:24],case_id=i['case_id'],interaction_id=i['id'],layer=i['layer'],object=m['object'],operation=i['operation']['name'],concern_key=m['concern_key'],field=m['object'] if m['target']=='data' else None,rule_id=None,scope=m.get('scope','interface' if m['target']=='data' else 'service'),data_location=m.get('data_location'),source_status='explicit' if task=='existing-extract' else 'framework_inferred',original_branch_id=bid if task=='existing-extract' else None)
    value.setdefault('coverage_kind','exact')
    # A declared check is evidence for a conditional scenario, not enough to
    # claim an executable test when its actual criterion is still unknown.
    kinds={'api.data.format':{'format','pattern'},'api.data.length':{'length'},'api.data.size':{'size'},'api.data.range':{'minimum','maximum'}}.get(m['concern_key'])
    if m['target']=='data' and kinds and not m.get('concrete_rule'):
        from .normal_rules import conditional_constraint
        criteria=[c for a in inputs.get('normal-constraints',{}).get('apis',[]) if i.get('api_id') and a['id']==i['api_id'] for p in a['parameters'] if p['name']==m['object'] and p['location']==m.get('data_location') for c in p['constraints'] if c['kind'] in kinds]
        if not any(c.get('status')=='explicit' and c.get('value') is not None and not conditional_constraint(c) for c in criteria):
            value.update(resolution='conditional',executable=False)
            value['pending_details']=list(dict.fromkeys(value.get('pending_details',[])+['具体约束标准待确认，不能直接构造可执行测试']))
    value['steps']={'normal_context':[i['sender']['name']+' → '+i['receiver']['name']+'：'+i['operation']['name']], 'trigger':value.pop('trigger'), 'documented_follow_up':value.pop('documented_follow_up')}
    return value


def encode(row,inputs):
    match=next((k for k,m in bindings(inputs).items() if m['interaction_id']==row['interaction_id'] and m['concern_key']==row['concern_key'] and m['object']==row['object'] and (m.get('data_location') is None or m['data_location']==row.get('data_location'))),None)
    if match is None:return row
    keep={'cause','conditions','derivation','source_refs','resolution','executable','pending_details','scenario_type','coverage_kind'}
    return {**{k:v for k,v in row.items() if k in keep},'binding_ref':match,'trigger':row['steps']['trigger'],'documented_follow_up':row['steps']['documented_follow_up']}
