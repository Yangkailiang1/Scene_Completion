"""Canonical identities for proven duplicate RR/SR views, never call-chain flattening."""
from copy import deepcopy
from .storage import fingerprint

VERSION='actual-call-identity-v2'


def unique(rows):return list({fingerprint(r):deepcopy(r) for r in rows}.values())


def merge_data(primary,secondary):
    rows=deepcopy(primary)+deepcopy(secondary);locations={}
    for p in rows:
        if p['location']!='business':locations.setdefault(p['name'],set()).add(p['location'])
    result={}
    for p in rows:
        candidates=locations.get(p['name'],set())
        if p['location']=='business' and len(candidates)==1:p['location']=next(iter(candidates))
        key=(p['location'],p['name'].casefold() if p['location']=='header' else p['name'])
        if key not in result:result[key]=p;continue
        old=result[key]
        if old['data_type'] is None:old['data_type']=p['data_type']
        elif p['data_type'] is not None and old['data_type']!=p['data_type']:
            old['constraints'].append({'id':'source-type-'+fingerprint([key,p['data_type']])[:16],'kind':'type','value':p['data_type'],'status':'explicit','source_refs':deepcopy(p['source_refs'])})
        old['required']=True if old['required'] is True or p['required'] is True else old['required'] if old['required'] is not None else p['required']
        if old['default'] is None:old['default']=deepcopy(p['default'])
        constraints={}
        for c in old['constraints']+p['constraints']:
            ck=fingerprint([c['kind'],c['value']])
            if ck not in constraints:constraints[ck]=deepcopy(c)
            else:
                constraints[ck]['source_refs']=unique(constraints[ck]['source_refs']+c['source_refs'])
                if c['status']=='explicit':constraints[ck]['status']='explicit'
        old['constraints']=list(constraints.values());old['source_refs']=unique(old['source_refs']+p['source_refs'])
    return list(result.values())


def same_endpoints(a,b):
    return a.get('case_id')==b.get('case_id') and a['direction']==b['direction'] and all(a[p]['name']==b[p]['name'] for p in ('sender','receiver'))


def canonical_fused(value,api_context=None):
    rows=deepcopy(value['interactions'])
    if api_context and (api_context.get('api-parameters') or api_context.get('normal-constraints')):
        from .interaction_enrichment import resolved_api_id
        material={**api_context,'rr-ssd':{'interactions':[i for i in rows if i['layer']=='RR']},'sr-ssd':{'interactions':[i for i in rows if i['layer']=='SR']}}
        for i in rows:
            linked=resolved_api_id(i,material)
            if linked:i['api_id']=linked
    by_id={i['id']:i for i in rows};aliases={};pending=[]
    for link in value.get('rr_sr_links',[]):
        rr=by_id.get(link['rr_id'])
        if link['status']!='confirmed' or not rr or rr.get('layer')!='RR':continue
        candidates=[by_id[sid] for sid in link['sr_ids'] if sid in by_id and by_id[sid]['layer']=='SR' and same_endpoints(rr,by_id[sid])]
        if len(candidates)==1:
            sr=candidates[0]
            # Distinct explicitly declared interfaces are different calls even
            # when both happen to use the same participants in a refinement.
            from .http_interfaces import declarations
            rr_calls=declarations(rr['operation']['name']);sr_calls=declarations(sr['operation']['name'])
            if rr_calls and sr_calls and rr_calls!=sr_calls:continue
            left,right=rr.get('api_id'),sr.get('api_id')
            if left and right and left!=right:
                both_qualified='::' in left and '::' in right
                if both_qualified or left.split('::')[-1]!=right.split('::')[-1]:continue
            aliases[rr['id']]=sr['id']
        elif len(candidates)>1:
            pending.append({'interaction_id':rr['id'],'reason':'同一RR展开中有多个同向同端点实际请求，不能选择第一条作为重复视图','source_refs':link.get('source_refs',rr['source_refs'])})
    for rr in rows:
        if rr.get('layer')!='RR' or rr['direction']!='return' or rr.get('parent_id') not in aliases or rr['id'] in aliases:continue
        candidates=[sr for sr in rows if sr['layer']=='SR' and sr['direction']=='return' and sr.get('parent_id')==aliases[rr['parent_id']] and same_endpoints(rr,sr)]
        if len(candidates)==1:aliases[rr['id']]=candidates[0]['id']
    groups={}
    for original,target in aliases.items():groups.setdefault(target,[]).append(by_id[original])
    kept=[];origins={}
    for original in rows:
        if original['id'] in aliases:continue
        row=deepcopy(original);sources=groups.get(row['id'],[])
        for other in sources:
            row['api_id']=row.get('api_id') or other.get('api_id')
            row['data']['sequence']=merge_data(row['data']['sequence'],other['data']['sequence'])
            for prop in ('source_refs',):row[prop]=unique(row[prop]+other[prop])
            for side in ('sender','receiver'):row[side]['source_refs']=unique(row[side]['source_refs']+other[side]['source_refs'])
            for key in ('kinds','sequence','optional'):row['operation'][key]=list(dict.fromkeys(row['operation'][key]+other['operation'][key]))
            row['operation']['source_refs']=unique(row['operation']['source_refs']+other['operation']['source_refs'])
        if row.get('parent_id') in aliases:row['parent_id']=aliases[row['parent_id']]
        if sources:
            origins[row['id']]=[{'id':x['id'],'layer':x['layer'],'api_id':x.get('api_id'),'operation':x['operation']['name'],'source_refs':deepcopy(x['source_refs'])} for x in [original]+sources]
        kept.append(row)
    return {'interactions':kept,'aliases':[{'source_id':k,'interaction_id':v} for k,v in aliases.items()],'source_views':origins,'pending':pending}


def alias_ids(inputs):
    if 'fused-ssd' not in inputs:return {}
    return {a['source_id']:a['interaction_id'] for a in canonical_fused(inputs['fused-ssd'],inputs)['aliases']}


def normalize_records(value,inputs,keys=('interaction_id',)):
    """Rename only proven view aliases, never transfer a failure to another call."""
    out=deepcopy(value);aliases=alias_ids(inputs)
    def visit(v):
        if isinstance(v,dict):
            for k in keys:
                if isinstance(v.get(k),str) and v[k] in aliases:
                    old_id=v[k];v[k]=aliases[old_id]
                    if v.get('target')=='operation':
                        original=next((i for i in inputs['fused-ssd']['interactions'] if i['id']==old_id),None)
                        canonical=next((i for i in inputs['fused-ssd']['interactions'] if i['id']==v[k]),None)
                        if original and canonical and v.get('object')==original['operation']['name']:v['object']=canonical['operation']['name']
            for child in v.values():visit(child)
        elif isinstance(v,list):
            for child in v:visit(child)
    visit(out);return out
