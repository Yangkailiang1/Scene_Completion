"""Approved method rules, independent of model transport and legacy generation."""
from copy import deepcopy
import json
from .ppt_contracts import PROTOCOL, validate, registry
from .ppt_sources import validate_evidence, documents_in, evidence_refs
from .sources import fingerprint
from .interaction_assignment import assign_one_to_one


def stable(prefix, value): return prefix+'-'+fingerprint(value)[:20]

def interactions(inputs):
    return [i for layer in ('rr-ssd','sr-ssd') for i in inputs.get(layer,{}).get('interactions',[])]


def resource_metadata(payload):
    """Reuse the approved physical DB -> logical SR facade transformation."""
    from .interaction_protocol import normalize_resource_services
    nodes=[{'node_id':c['id'],'name':c['name'],'kind':{'内部数据库':'internal_database','外部数据库':'external_database'}.get(c['composition_type'],'component'),
            'source_refs':c['source_refs']} for c in payload['components']]
    nodes,mappings=normalize_resource_services(nodes)
    return {'resource_services':[n for n in nodes if n.get('service_role')=='resource_service'], 'resource_mappings':mappings}


def refs_required(value):
    def visit(v):
        if isinstance(v,dict):
            if 'source_refs' in v and not v['source_refs']:
                # Empty refs are allowed only for pending constraints, never known facts.
                if v.get('status')!='pending': raise ValueError('known facts require source evidence')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value)


def validate_result(task, payload, inputs):
    validate(task,payload)
    if task=='gap-recommend':return payload
    docs=documents_in(inputs)
    allowed={fingerprint(r) for r in evidence_refs(inputs)}
    for ref in evidence_refs(payload):
        if fingerprint(ref) not in allowed:
            if not docs:raise ValueError('output uses evidence outside task dependencies')
            validate_evidence(ref,docs)
    refs_required(payload)
    definitions=registry()['definitions']
    def visit(v):
        if isinstance(v,dict):
            if 'concern_key' in v and v['concern_key'] not in definitions:raise ValueError('unregistered concern')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(payload)
    if task=='components':
        ids=[c['id'] for c in payload['components']]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate component ID')
        if any(c['parent_id'] is not None and c['parent_id'] not in ids for c in payload['components']):raise ValueError('unknown parent')
        if any(r['from_id'] not in ids or r['to_id'] not in ids for r in payload['relations']):raise ValueError('unknown relation endpoint')
    if task in {'rr-ssd','sr-ssd'}:
        layer='RR' if task=='rr-ssd' else 'SR'
        seen=set(); ids=set()
        for i in payload['interactions']:
            key=(i['case_id'],i['sequence'])
            if i['layer']!=layer or key in seen or i['id'] in ids:raise ValueError('wrong SSD layer, duplicate ID or order')
            seen.add(key); ids.add(i['id'])
            if not i['operation']['kinds']: raise ValueError('actual operation kind required')
        if any(i['parent_id'] and i['parent_id'] not in ids for i in payload['interactions']):
            raise ValueError('SSD parent must be in the same supplied layer')
    if task in {'api-parameters','rr-ssd','sr-ssd'}:
        params=[p for a in payload.get('apis',[]) for p in a['parameters']]
        params += [p for i in payload.get('interactions',[]) for p in i['data']['sequence']]
        for p in params:
            for rule in p['constraints']:
                if rule['status']=='explicit' and rule['value'] is None: raise ValueError('explicit constraint needs a known value')
                if rule['status']=='explicit' and rule['kind']=='type' and p['data_type']!=rule['value']:
                    raise ValueError('known type must be recorded consistently in data_type')
            if p['location']=='path' and p['required'] is False: raise ValueError('path parameters cannot be optional')
    if task=='test-operation-project':
        for item in payload['objects']:
            for op in item['supported_operations']:
                if any(ref['quote']!=op['name'] for ref in op['source_refs']):
                    raise ValueError('test projection quotes must contain only the supported operation name')
                import re
                if re.search(r'异常|错误码|失败|预期|\b[45]\d\d\b|exception|error',op['name'],re.I):
                    raise ValueError('test projection cannot expose exception/response details')
    if task=='object-operations':
        # Capability inputs include only a whitelisted test operation projection.
        validate('test-operation-project',inputs['test-operations'])
        allowed={c['name'] for c in inputs['components']['components']}
        allowed|={p['name'] for i in inputs['rr-ssd']['interactions'] for p in (i['sender'],i['receiver'])}
        allowed|={o['name'] for o in inputs['test-operations']['objects']}
        if any(o['name'] not in allowed for o in payload['objects']):raise ValueError('unsupported capability object')
    if task in {'concern-match','exception-generate'}:
        by_id={i['id']:i for i in interactions(inputs)}
        for x in payload.get('matches',[])+payload.get('scenarios',[])+payload.get('pending',[]):
            if x['interaction_id'] not in by_id:raise ValueError('unknown actual interaction')
        if task=='concern-match':
            for m in payload['matches']:
                i=by_id[m['interaction_id']]
                if m['target'] in {'sender','receiver'} and m['object']!=i[m['target']]['name']:
                    raise ValueError('concern party must be actual sender/receiver')
                if set(i['operation']['kinds']) <= {'read','display'} and (m['concern_key'].startswith('service.resource_mutation.') or m['concern_key'] in {'internal_database.persistence','internal_database.idempotency','internal_database.uniqueness'}):
                    raise ValueError('read-only interaction cannot activate mutation concerns')
                if m['target']=='data' and m['object'] not in {p['name'] for p in parameters_for(i,inputs)}:
                    raise ValueError('data concern must identify an actual field')
        else:
            matches={(m['interaction_id'],m['object'],m['concern_key']) for m in inputs['concern-match']['matches']}
            for s in payload['scenarios']:
                i=by_id[s['interaction_id']]
                if s['operation']!=i['operation']['name'] or s['case_id']!=i['case_id'] or s['layer']!=i['layer']:
                    raise ValueError('G must use this SSD operation, case and layer')
                if (s['interaction_id'],s['object'],s['concern_key']) not in matches:
                    raise ValueError('G must have an applicable matched concern')
                if s['source_status']!='framework_inferred' or not s['derivation']:
                    raise ValueError('G requires recorded positive-rule derivation')
                if s['field'] is not None:
                    expected={scenario_key(x) for x in data_exceptions(inputs)}
                    if scenario_key(s) not in expected: raise ValueError('unsupported or invented field exception')
                else:
                    match=[m for m in inputs['concern-match']['matches'] if (m['interaction_id'],m['object'],m['concern_key'])==(s['interaction_id'],s['object'],s['concern_key'])]
                    if not any(m['concrete_rule'] for m in match):raise ValueError('no concrete rule; move to pending')
    if task in {'existing-extract','test-ground-truth'}:
        test_ids={d['source_id'] for d in documents_in(inputs) if d.get('channel')=='test'}
        for s in payload['scenarios']:
            if task=='test-ground-truth' and not any(r['source_id'] in test_ids for r in s['source_refs']):
                raise ValueError('each GT unit must cite its independent test description')
            if task=='existing-extract' and s['source_status']!='explicit':raise ValueError('E may contain only documented exceptions')
            if s['source_status']=='framework_inferred' and not s['derivation']:raise ValueError('GT inference needs derivation')
    if task=='gap-compare':
        expected={(a['id'],b['id']) for a in inputs['left'] for b in inputs['right']}
        got=[(d['left_id'],d['right_id']) for d in payload['decisions']]
        if len(got)!=len(set(got)) or set(got)!=expected:raise ValueError('comparison must inspect every candidate pair exactly once')
        left={s['id']:s for s in inputs['left']}; right={s['id']:s for s in inputs['right']}
        for d in payload['decisions']:
            a,b=left[d['left_id']],right[d['right_id']]
            if d['status']=='full' and (a['case_id']!=b['case_id'] or a['layer']!=b['layer']):
                raise ValueError('full match cannot cross case/layer')
    return payload


def resolved_api_id(i,inputs):
    apis=inputs.get('api-parameters',{}).get('apis',[])
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
    params=deepcopy(i['data']['sequence'])
    api_id=resolved_api_id(i,inputs)
    if api_id:
        apis=[a for a in inputs.get('api-parameters',{}).get('apis',[]) if a['id']==api_id]
        if len(apis)>1:raise ValueError('duplicate API identity')
        if apis:
            # API contract wins over an incomplete interaction presentation.
            by_name={(p['location'],p['name']):p for p in params}
            by_name.update({(p['location'],p['name']):p for p in apis[0]['parameters'] if p['location']!='response' or i['direction']=='return'})
            params=list(by_name.values())
    return params


def concern_by_label(label):
    found=[k for k,v in registry()['definitions'].items() if v['label']==label]
    if len(found)!=1:raise ValueError('ambiguous concern label: '+label)
    return found[0]


def data_exceptions(inputs):
    """One known violation per field/rule. Missing optional parameters never fail."""
    output=[]
    labels={'required':'数据完整性','type':'数据类型','enum':'数据合法性','minimum':'数据范围','maximum':'数据范围',
            'format':'数据格式','length':'数据长度','size':'数据大小','pattern':'数据格式','other':'数据合法性'}
    for i in interactions(inputs):
        if i['direction']!='request':continue
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
                   'derivation':f'字段{p["name"]}的明示{kind}规则取反；可选字段仅在提供时检查。','source_refs':refs}
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


def full_assignment(decisions, left_ids=None, right_ids=None):
    rows=[{'checker_scenario_id':d['left_id'],'generated_scenario_id':d['right_id'],'status':d['status']}
          for d in decisions if d['status']=='full' and (left_ids is None or d['left_id'] in left_ids) and (right_ids is None or d['right_id'] in right_ids)]
    return assign_one_to_one(rows)['selected_pairs']


def compare_report(g,e,gt,eg,tg,te):
    """Only complete pairs score. Reassign after restricting to missing truth/G."""
    g,e,gt=map(deduplicate,(g,e,gt))
    # Semantic duplicate edges to one target cannot score twice (one-to-one).
    gids,eids,tids=({s['id'] for s in xs} for xs in (g,e,gt))
    covered_g={p['checker_scenario_id'] for p in full_assignment(eg,gids,eids)}
    m=[s for s in g if s['id'] not in covered_g]
    existing_t={p['checker_scenario_id'] for p in full_assignment(te,tids,eids)}
    missing_t=tids-existing_t; mids={s['id'] for s in m}
    hits=full_assignment(tg,missing_t,mids)
    valid=full_assignment(tg,tids,gids)
    rate=lambda n,d: {'value':100*n/d if d else None,'numerator':n,'denominator':d,'status':'适用' if d else '不适用'}
    breakdown={kind:rate(sum(p['checker_scenario_id'] in {s['id'] for s in gt if s['source_status']==kind} for p in valid),sum(s['source_status']==kind for s in gt)) for kind in ('explicit','framework_inferred')}
    return {'protocol':PROTOCOL,'G':g,'E':e,'GT':gt,'M':m,'metrics':{
      'missing_exception_miss_rate':rate(len(missing_t)-len(hits),len(missing_t)),
      'generation_validity':rate(len(valid),len(g)),
      'recommendation_adoption':{'value':None,'status':'未启用'},
      'recommendation_false_positive':{'value':None,'status':'未启用'}},
      'truth_breakdown':breakdown,'full_matches':{'G_E':full_assignment(eg,gids,eids),'GT_G':valid,'GT_E':full_assignment(te,tids,eids)},
      'partial_diagnostics':[d for ds in (eg,tg,te) for d in ds if d['status']=='partial'],
      'recommendation':{'enabled':False,'status':'未启用'},'formula_notes':{
       'GT':'人工测试真值（含单列的框架推导项）','G':'生成异常集合','E':'文档已有异常集合','M':'G减去与E完整对应的项',
       'miss_rate':'(1-|M∩(GT-E)|/|GT-E|)×100%','validity':'|G∩GT|/|G|×100%','empty_denominator':'不适用'}}


def pending_rules(inputs):
    """Unknown positive properties are diagnostic, never failure scenarios."""
    out=[]
    for i in interactions(inputs):
        if i['direction']!='request':continue
        for p in parameters_for(i,inputs):
            for rule in p['constraints']:
                if rule['status']=='pending':out.append({'interaction_id':i['id'],'object':p['name'],
                  'concern_key':{'format':'api.data.format','length':'api.data.length','size':'api.data.size','type':'api.data.type'}.get(rule['kind'],'api.data.legality'),
                  'reason':f'{rule["kind"]}具体约束待确认，不进入G','source_refs':rule['source_refs'] or p['source_refs']})
            if p['required'] is True and p['data_type'] is None and not any(r['status']=='explicit' for r in p['constraints']):
                out.append({'interaction_id':i['id'],'object':p['name'],'concern_key':'api.data.legality',
                  'reason':'必填字段已提供但违反约束：具体类型、格式或取值规则待确认，不进入G','source_refs':p['source_refs']})
    return list({fingerprint(x):x for x in out}.values())


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


def complete_data_matches(inputs, matches):
    """Known parameter properties have deterministic matches to fixed definitions."""
    matches=deepcopy(matches)
    kinds={'type':'数据类型','enum':'数据合法性','minimum':'数据范围','maximum':'数据范围','format':'数据格式',
           'length':'数据长度','size':'数据大小','pattern':'数据格式','other':'数据合法性'}
    for i in interactions(inputs):
        for p in parameters_for(i,inputs):
            rules=[]
            if p['required'] is True:rules.append(('数据完整性','required',p['source_refs']))
            if p['data_type'] is not None:rules.append(('数据类型','type='+p['data_type'],p['source_refs']))
            rules += [(kinds[r['kind']],r['kind']+'='+json.dumps(r['value'],ensure_ascii=False),r['source_refs']) for r in p['constraints'] if r['status']=='explicit']
            for label,rule,refs in rules:
                matches.append({'interaction_id':i['id'],'target':'data','object':p['name'],'concern_key':concern_by_label(label),
                                'basis':'接收方接口的明示字段属性','concrete_rule':rule,'source_refs':refs})
    return list({fingerprint(m):m for m in matches}.values())
