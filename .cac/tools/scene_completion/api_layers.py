"""Tool-owned namespaces keep RR public and SR internal API contracts separate."""
from copy import deepcopy


def qualify_mapping(value,layer):
    out=deepcopy(value)
    for service in out['services']:
        for api in service['interfaces']:
            declared=api.get('declared_id',api['id'])
            api.update(id=layer+'::'+declared,declared_id=declared,source_layer=layer)
    return out


def merge_mappings(parts):
    return {'services':[service for layer,value in parts for service in qualify_mapping(value,layer)['services']]}


def qualify_index(value,layer):
    return {'apis':[{**deepcopy(a),'id':layer+'::'+a['id'],'declared_id':a['id'],'source_layer':layer} for a in value['apis']]}


def scoped_parameters(values,layer):
    return {'apis':[{**deepcopy(a),'source_layer':layer,'declared_id':a.get('declared_id',a['id'].split('::',1)[-1])} for value in values for a in value['apis']]}


def candidates_for_layer(apis,layer):
    """A known source layer restricts unqualified IDs, never exact qualified IDs."""
    return [a for a in apis if a.get('source_layer') in (None,layer)]


def explicit_api_target(text,inputs,rows):
    """A literal source path/qualified ID can locate a failure; field names cannot.

    Returns None when the original exception does not identify an interface.
    Repeated occurrences of the same API remain multiple possible targets.
    """
    import re
    from .interaction_enrichment import resolved_api_id
    apis=inputs.get('api-parameters',inputs.get('normal-constraints',{})).get('apis',[])
    matched=[]
    for a in apis:
        address=a.get('address')
        by_path=address and re.search(r'(?<![A-Za-z0-9_/{-])'+re.escape(address)+r'(?![A-Za-z0-9_/{-])',text)
        by_id='::' in a['id'] and a['id'] in text
        if by_path or by_id:matched.append(a['id'])
    if len(set(matched))!=1:return None
    target=matched[0]
    context={**inputs,'rr-ssd':{'interactions':[i for i in rows if i['layer']=='RR']},'sr-ssd':{'interactions':[i for i in rows if i['layer']=='SR']}}
    return [i['id'] for i in rows if i['direction']=='request' and resolved_api_id(i,context)==target]


def qualify_fused_calls(value,inputs):
    """Attach only known API identities; keep all original RR/SR messages."""
    from .interaction_enrichment import resolved_api_id
    out=deepcopy(value);rows=out['interactions']
    context={**inputs,'rr-ssd':{'interactions':[i for i in rows if i.get('layer')=='RR']},'sr-ssd':{'interactions':[i for i in rows if i.get('layer')=='SR']}}
    for i in rows:
        linked=resolved_api_id(i,context)
        if linked:i['api_id']=linked
    return out


def scoped_imports(parts,scope):
    """Admit imported contracts only to their proven layer/interface."""
    selected=[];layer=scope['source_layer'];declared=scope.get('declared_id',scope.get('id'))
    for part in parts:
        p=deepcopy(part);payload=p['payload'];source=p.get('source_layer')
        if 'apis' in payload and declared:
            apis=[]
            for a in payload['apis']:
                owner=a.get('source_layer',source)
                address=a.get('address');known=scope.get('address')
                exact_path=bool(address and known and address==known)
                id_match=a.get('declared_id',a['id']) in {declared,scope['id']}
                if owner and owner!=layer:continue
                if owner is None and layer=='RR' and not exact_path:continue
                if known and address and address!=known:continue
                if not (id_match or exact_path):continue
                a.update(id=scope['id'],declared_id=declared,source_layer=layer);apis.append(a)
            if not apis:continue
            p['payload']['apis']=apis
        elif 'services' in payload:
            services=[]
            for service in payload['services']:
                entries=[i for i in service['interfaces'] if i.get('source_layer',source or 'SR')==layer]
                if entries:services.append({**service,'interfaces':entries})
            if not services:continue
            p['payload']['services']=services
        selected.append(p)
    return selected
