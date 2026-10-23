from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
def stable(prefix, value): return prefix+'-'+fingerprint(value)[:20]


def interactions(inputs):
    return [i for layer in ('rr-ssd','sr-ssd') for i in inputs.get(layer,{}).get('interactions',[])]


def resolved_api_id(i,inputs):
    apis=inputs.get('api-parameters',{}).get('apis',[])
    if i['direction']=='return' and i.get('parent_id'):
        request=next((x for x in interactions(inputs) if x['id']==i['parent_id'] and x['direction']=='request' and x['case_id']==i['case_id']),None)
        if request and not i['api_id']:return resolved_api_id(request,inputs)
    if i['api_id'] and any(a['id']==i['api_id'] for a in apis):return i['api_id']
    # Link independently extracted API tables by an explicit identity/address,
    # never path similarity or overlapping parameter names.
    interfaces=[api for service in inputs.get('api-map',{}).get('services',[]) for api in service['interfaces']
                if (i['api_id'] and api['id']==i['api_id']) or
                   (service['name']==i['receiver']['name'] and api['name']==i['operation']['name'])]
    found=set()
    for api in interfaces:
        for a in apis:
            if a['id']==api['id'] or (api['address'] is not None and a['address']==api['address']) or (api['address'] is None and a['address'] is None and a['name']==api['name']):
                found.add(a['id'])
    return next(iter(found)) if len(found)==1 else None


def parameters_for(i, inputs):
    is_return=i['direction']=='return'
    valid=lambda p:p['location']=='response' if is_return else p['location']!='response'
    params=[deepcopy(p) for p in i['data']['sequence'] if valid(p)]
    api_id=resolved_api_id(i,inputs)
    if api_id:
        apis=[a for a in inputs.get('api-parameters',{}).get('apis',[]) if a['id']==api_id]
        if len(apis)>1:raise ValueError('duplicate API identity')
        if apis:
            # API contract wins over an incomplete interaction presentation.
            by_name={(p['location'],p['name']):p for p in params}
            by_name.update({(p['location'],p['name']):p for p in apis[0]['parameters'] if valid(p)})
            params=list(by_name.values())
    return params


def bind_resource_services(inputs):
    """Canonical SR view retains physical objects and logical-only mappings."""
    inputs=deepcopy(inputs)
    if 'components' not in inputs or 'sr-ssd' not in inputs:return inputs
    components=inputs['components']['components'];meta=resource_metadata(inputs['components'])
    by_physical={c['id']:c for c in components}
    by_name={by_physical[s['physical_resource_id']]['name']:s for s in meta['resource_services']}
    for i in inputs['sr-ssd']['interactions']:
        for side in ('sender','receiver'):
            p=i[side]
            if p['name'] in by_name:
                p['name']=by_name[p['name']]['name'];p['position']='内部服务（SR逻辑资源服务）'
    return inputs


def capability_union(inputs):
    """Summarize evidenced capabilities; never feed these back into SSD/G."""
    objects={}
    def add(name,op,refs):
        if not name or not op:return
        c=canonical_name(name,inputs['components']['components'])
        name=c['name'] if c else name
        by_op=objects.setdefault(name,{})
        by_op.setdefault(op,[]).extend(refs)
    for i in inputs['rr-ssd']['interactions']:
        if i['direction']=='request':
            add(i['receiver']['name'],i['operation']['name'],i['operation']['source_refs'])
            for op in i['operation']['sequence']+i['operation']['optional']:
                add(i['receiver']['name'],op,i['operation']['source_refs'])
    for item in inputs['test-operations']['objects']:
        for op in item['supported_operations']:add(item['name'],op['name'],op['source_refs'])
    return {'objects':[{'name':name,'supported_operations':[{'name':op,'source_refs':list({fingerprint(r):r for r in refs}.values())}
                       for op,refs in sorted(ops.items())]} for name,ops in sorted(objects.items())]}



def resource_metadata(payload):
    services=[];mappings=[]
    for c in payload['components']:
        if c['composition_type'] not in {'内部数据库','外部数据库'}:continue
        sid=stable('resource-service',c['id'])
        services.append({'node_id':sid,'name':c['name']+'资源服务','kind':'internal_service',
         'service_role':'resource_service','physical_resource_id':c['id'],'logical_only':True,
         'resource_origin':'internal' if c['composition_type']=='内部数据库' else 'external','source_refs':c['source_refs']})
        mappings.append({'physical_resource_id':c['id'],'logical_service_id':sid,'source_refs':c['source_refs']})
    return {'resource_services':services,'resource_mappings':mappings}

def canonical_name(name,components,aliases=()):
    normalize=lambda s:''.join(s.casefold().split())
    rows=[c for c in components if normalize(c['name'])==normalize(name)]
    rows += [c for a in aliases if a['name']==name for c in components if a['component_id']==c['id']]
    unique={c['id']:c for c in rows}
    return next(iter(unique.values())) if len(unique)==1 else None

def enrich(inputs,alignment):
    """Bindings/capabilities enrich views without creating or changing actual operations."""
    value=bind_resource_services(inputs);components=value['components']['components']
    services=resource_metadata(value['components'])['resource_services']
    capabilities=value['object-operations']['objects'];pending=[];views=[]
    for i in interactions(value):
        i=deepcopy(i)
        for side in ('sender','receiver'):
            party=i[side];c=canonical_name(party['name'],components,alignment['aliases'])
            logical=next((s for s in services if s['name']==party['name']),None)
            party['component_id']=c['id'] if c else (logical['physical_resource_id'] if logical else None)
            if c:party.update(name=c['name'],position=c['composition_type'])
            party['resource_service']=logical
            party['supported_operations']=[op for row in capabilities if canonical_name(row['name'],components,alignment['aliases'])==c and c is not None or row['name']==party['name'] for op in row['supported_operations']] if side=='receiver' else []
            party['concerns']=[]
            if not party['component_id']:pending.append({'interaction_id':i['id'],'reason':side+'在系统组成中的位置待确认','source_refs':party['source_refs']})
        # SR services expose evidenced API operations in addition to the RR
        # capability table; these never replace the actual operation.
        if i['layer']=='SR':
            for service in value['api-map']['services']:
                if service['name']==i['receiver']['name']:
                    i['receiver']['supported_operations'] += [{'name':a['name'],'source_refs':a['source_refs']} for a in service['interfaces']]
        i['data']['sequence']=parameters_for(i,value)
        i['associated_api']=resolved_api_id(i,value)
        i['data']['concerns']=[]
        if not i['receiver']['supported_operations'] or i['operation']['name'] not in {o['name'] for o in i['receiver']['supported_operations']}:
            pending.append({'interaction_id':i['id'],'reason':'本次操作未在接收方能力表中得到对应，需核对；不得据此改写操作','source_refs':i['operation']['source_refs']})
        views.append(i)
    for rr in value['rr-ssd']['interactions']:
        if not any(l['rr_id']==rr['id'] and l['status']=='confirmed' for l in alignment['links']):
            pending.append({'interaction_id':rr['id'],'reason':'RR步骤—SR展开对应待确认','source_refs':rr['source_refs']})
    return {'interactions':views,'rr_sr_links':alignment['links'],'pending':pending,'resource_mappings':resource_metadata(value['components'])['resource_mappings']}

def with_concerns(enriched,matches):
    view=deepcopy(enriched)
    for i in view['interactions']:
        for m in matches['matches']:
            if m['interaction_id']==i['id']:
                target=i['data'] if m['target']=='data' else i[m['target']]
                target['concerns'].append(m)
    return view

def actual_context(enriched):
    """G cannot see unrelated supported capabilities or test-operation evidence."""
    v=deepcopy(enriched)
    for i in v['interactions']:
        for side in ('sender','receiver'):
            i[side]['supported_operations']=[op for op in i[side]['supported_operations'] if op['name']==i['operation']['name']]
    return v


def basic_views(enriched):
    """Expose the canonical four-tuples without enrichment-only machine fields."""
    from .contracts import INTERACTION,PARTY
    result={'rr-ssd':{'interactions':[]},'sr-ssd':{'interactions':[]}}
    for i in enriched['interactions']:
        b={k:deepcopy(i[k]) for k in INTERACTION['properties']}
        for side in ('sender','receiver'):b[side]={k:deepcopy(i[side][k]) for k in PARTY['properties']}
        b['data']={'sequence':deepcopy(i['data']['sequence'])}
        result['rr-ssd' if i['layer']=='RR' else 'sr-ssd']['interactions'].append(b)
    return result
