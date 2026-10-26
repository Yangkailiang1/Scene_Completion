"""Versioned four-element identities and exact concern-set comparison.

This module never reads a different channel to classify a concern. Candidates
in the registry are not observations; only validated recognition rows enter Gc.
"""
from copy import deepcopy
import re
from .storage import fingerprint
from .concern_registry import registry

VERSION = 'two-level-concern-scenario-v1'
TARGETS = {'sender': '发送方', 'operation': '操作序列', 'data': '数据序列', 'receiver': '接收方'}
DATA_KEYS = {'required':'completeness','type':'type','format':'format','pattern':'format',
             'length':'length','size':'size','minimum':'range','maximum':'range','enum':'legality'}


def interaction_rows(inputs):
    from .interaction_enrichment import interactions
    if inputs.get('enriched-interactions',{}).get('interactions'):
        return inputs['enriched-interactions']['interactions']
    if 'fused-ssd' in inputs and 'enriched-interactions' not in inputs:
        from .inverse_alignment import canonical_fused
        return canonical_fused(inputs['fused-ssd'])['interactions']
    return interactions(inputs)


def index_elements(inputs):
    """One actual occurrence has one identity, independent of RR/SR aliases."""
    from .interaction_enrichment import parameters_for
    out=[]
    for i in interaction_rows(inputs):
        base={'case_id':i['case_id'],'interaction_id':i['id'],'direction':i['direction']}
        def add(target,name,location=None,scope=None,**extra):
            canonical=name.casefold() if location=='header' else name
            identity=[*base.values(),target,location,scope,canonical,extra.get('operation_index')]
            out.append({**base,'target':target,'object':name,'data_location':location,'scope':scope,
                        'element_id':'element-'+fingerprint(identity)[:24],**extra})
        for side in ('sender','receiver'):add(side,i[side]['name'])
        # The call is an actual operation, not a fabricated additional message.
        add('operation',i['operation']['name'],operation_index=None,caller=i['sender']['name'],callee=i['receiver']['name'])
        for n,name in enumerate(i['operation'].get('sequence',[])):
            add('operation',name,operation_index=n,caller=i['sender']['name'],callee=i['receiver']['name'])
        params=list(i['data']['sequence'])
        if 'api-parameters' in inputs or 'normal-constraints' in inputs:
            material=inputs if 'api-parameters' in inputs else {**inputs,'api-parameters':inputs['normal-constraints']}
            params+=parameters_for(i,material)
        seen=set()
        for p in params:
            key=(p['location'],p['name'])
            if key not in seen:add('data',p['name'],p['location'],'interface');seen.add(key)
    return out


def _normalize_field(row):
    if row.get('target')!='data':return
    name=row['object']
    m=re.match(r'^(header|path|query|body|response|business|storage)\.(.+)$',name)
    if m:
        if row.get('data_location') and row['data_location']!=m[1]:raise ValueError('字段路径与位置冲突')
        row.update(object=m[2],data_location=m[1])


def recognize(inputs,raw,*,inverse=False):
    """Validate only submitted rows; do not fill recognition from the registry."""
    from .concern_hierarchy import decorate
    rows={i['id']:i for i in interaction_rows(inputs)};elements=index_elements(inputs)
    definitions=registry()['definitions'];accepted=[];pending=deepcopy(raw.get('pending',[]))
    for original in raw.get('matches',[]):
        m=deepcopy(original);iid=m['interaction_id'];key=m['concern_key']
        reason=None
        if iid not in rows:reason='关注点没有绑定到本片实际交互'
        elif key not in definitions or not definitions[key].get('enabled',True):reason='关注点未注册或已停用'
        if reason:
            pending.append({'interaction_id':iid,'object':m['object'],'concern_key':key,'reason':reason,'source_refs':m['source_refs']});continue
        i=rows[iid]
        if inverse and ('test-documents' in inputs or 'existing-documents' in inputs):
            own_docs=inputs.get('test-documents',inputs.get('existing-documents',[]))
            own_lines={}
            for d in own_docs:own_lines.setdefault(d['source_id'],set()).update(r['number'] for r in d['lines'])
            if not any(any(r['line_start']<=n<=r['line_end'] for n in own_lines.get(r['source_id'],set())) for r in m['source_refs']):
                extra=[ref for b in inputs.get('branches',{}).get('branches',[]) for ref in b['source_refs']]
                if inputs.get('test-documents'):
                    from .test_sources import records
                    extra=[ref for row in records(inputs['test-documents']) for ref in row['source_refs']]
                pending.append({'interaction_id':iid,'object':m['object'],'concern_key':key,'reason':'模型没有提供本条异常来源的识别证据，仅有正向规则引用；未计分，保留任务来源供核查','source_refs':m['source_refs']+extra})
                continue
        from .normal_rules import identity_concern
        canonical=identity_concern(key,i)
        if canonical!=key:m['classification_origin']=key;m['concern_key']=key=canonical
        if (key.startswith('human.') or key in {'service_relation.authentication','service_relation.authorization'}) and i['direction']!='request':
            reason='身份/授权检查须定位到实际调用请求，不能在返回中重复计数'
        try:_normalize_field(m)
        except ValueError as e:reason=str(e)
        # Classification is normalized from this row's own structured evidence.
        kinds={DATA_KEYS[g['constraint_kind']] for g in m.get('activation_evidence',[]) if g.get('constraint_kind') in DATA_KEYS and g.get('status','explicit')=='explicit'}
        if key.startswith('api.data.') and len(kinds)==1:
            canonical='api.data.'+next(iter(kinds))
            if canonical!=key:m['classification_origin']=key;m['concern_key']=key=canonical
        elif key.startswith('api.data.') and len(kinds)>1:
            reason='同一关注点识别项混合多个分类的约束，请分别识别'
        if key=='service.base.availability':
            provider='receiver' if i['direction']=='request' else 'sender'
            if m['object']!=i[provider]['name']:reason='可用性异常的对象不是本次被调用服务，实际失败位置待确认'
        if definitions[key].get('layer') in {'base','functional','technology'} and m['target'] in {'data','operation'}:
            # These registry classes describe the provider's responsibility.
            # A field/operation in the failure remains provenance, not a new
            # owning object for a service-level concern.
            known=any(e['interaction_id']==iid and e['target']==m['target'] and e['object']==m['object'] for e in elements)
            if known:
                m['element_origin']={k:m.get(k) for k in ('target','object','operation_index','data_location')}
                provider='receiver' if i['direction']=='request' else 'sender'
                m.update(target=provider,object=i[provider]['name'],data_location=None,operation_index=None,scope='service')
                if key=='service.base.availability' and m['element_origin']['target']=='operation':reason=None
        if inverse:
            from .concern_hierarchy import context
            kinds=context(i,inputs)['kinds'];required=definitions[key].get('operation_kinds',[])
            if kinds <= {'read','display'} and required and not kinds & set(required):reason='本次为只读交互，不能绑定变更关注点；实际失败调用或分类待确认'
        if definitions[key].get('layer')=='relation':
            m.update(target='operation')
            if m.get('operation_index') is None:m['object']=i['operation']['name']
        elif key.startswith('human.'):
            m.update(target='sender',object=i['sender']['name'])
        candidates=[e for e in elements if e['interaction_id']==iid and e['target']==m['target']]
        if m['target']=='operation':
            candidates=[e for e in candidates if e.get('operation_index')==m.get('operation_index') and
                        (e['object']==m['object'] or m['object'] in {i['sender']['name'],i['receiver']['name']})]
        else:
            candidates=[e for e in candidates if (e['object'].casefold()==m['object'].casefold() if e.get('data_location')=='header' else e['object']==m['object']) and
                        (m['target']!='data' or not m.get('data_location') or m['data_location']==e['data_location'])]
        # Storage/context fields require an explicit same-row field evidence.
        if not candidates and m['target']=='data' and m.get('scope') in {'storage','context'}:
            if any(g.get('field')==m['object'] and g.get('source_refs') for g in m.get('activation_evidence',[])):
                candidates=[{'case_id':i['case_id'],'interaction_id':iid,'direction':i['direction'],'target':'data','object':m['object'],
                    'scope':m['scope'],'data_location':m.get('data_location'),
                    'element_id':'element-'+fingerprint([i['case_id'],iid,i['direction'],'data',m['scope'],m.get('data_location'),m['object']])[:24]}]
        if len(candidates)!=1:reason=reason or '四要素位置或具体对象不唯一，需确认；不回退为整个请求'
        if reason:
            pending.append({'interaction_id':iid,'object':m['object'],'concern_key':key,'reason':reason,'source_refs':m['source_refs']});continue
        element=candidates[0];m.update({k:v for k,v in element.items() if k not in {'scope'} or v is not None})
        if inverse:
            # Reverse recognition is evidence of a failure from its own channel,
            # not applicability inherited from the generator's recognition.
            m.update(status='applicable',status_reason='独立异常来源已识别并定位',inheritance_paths=[])
            branches=inputs.get('branches',{}).get('branches',[])
            if len(branches)==1:
                m['source_branch_ids']=[branches[0]['id']]
            if inputs.get('test-documents'):
                from .test_sources import records
                source_units=records(inputs['test-documents'])
                own=[r['id'] for r in source_units if any(ref['source_id']==r.get('source_id') and
                     ref['line_start']<=r.get('row',-1)<=ref['line_end'] for ref in m['source_refs'])]
                if len(source_units)==1:own=[source_units[0]['id']]
                m['source_unit_ids']=own or m.get('source_unit_ids',[])
        else:
            m=decorate(m,i,inputs)
        m['binding_id']='concern-'+fingerprint([element['element_id'],key])[:24]
        m['identification']='inverse_llm' if inverse else 'llm'
        if definitions[key].get('kind')!='check':
            m.update(status='not_applicable',status_reason='父级分类只导航，不作为计分单元')
        if m['status']=='pending':pending.append({'interaction_id':iid,'object':m['object'],'concern_key':key,'reason':m['status_reason'],'source_refs':m['source_refs']})
        accepted.append(m)
    unique={}
    for m in accepted:
        key=(m['binding_id'],m['status'])
        if key not in unique:unique[key]=m
        else:
            old=unique[key]
            for name in ('source_refs','source_unit_ids','source_branch_ids'):
                old[name]=list({fingerprint(v):v for v in old.get(name,[])+m.get(name,[])}.values())
    return {'matches':list(unique.values()),'pending':list({fingerprint(p):p for p in pending}.values()),**({'excluded':deepcopy(raw['excluded'])} if raw.get('excluded') else {})}


def definite(value):
    return {m['binding_id']:m for m in value.get('matches',[]) if m.get('status')=='applicable' and m.get('binding_id')}


def compare(g,e,gt=None):
    channels={'G_c':definite(g),'E_c':definite(e)}
    if gt is not None:channels['GT_c']=definite(gt)
    gs,es=set(channels['G_c']),set(channels['E_c']);ms=gs-es
    ts=set(channels.get('GT_c',{}));missing=ts-es
    def rate(n,d):return {'value':100*n/d if d else None,'numerator':n,'denominator':d,'status':'适用' if d else '不适用','unit':'关注点绑定'}
    metrics={'missing_exception_miss_rate':rate(len(missing-ms),len(missing)),'generation_validity':rate(len(gs&ts),len(gs))} if gt is not None else {}
    order=lambda key:(-sum(key in c for c in channels.values()),key)
    aligned=[]
    for bid in sorted(set().union(*(set(c) for c in channels.values())),key=order):
        cells={k.removesuffix('_c'):[v[bid]] if bid in v else [] for k,v in channels.items()}
        cells.setdefault('GT',[])
        anchor=next(v[bid] for v in channels.values() if bid in v)
        aligned.append({'id':bid,'anchor':anchor,'cells':cells,'status':'triple' if all(cells.values()) else 'pair' if sum(bool(v) for v in cells.values())==2 else 'single',
                        'reason':'统一用例、交互、方向、四要素对象和关注点ID精确对应','missing':bid in ms})
    return {'version':VERSION,'unit':'关注点绑定','G_c':list(channels['G_c'].values()),'E_c':list(channels['E_c'].values()),
            **({'GT_c':list(channels['GT_c'].values())} if gt is not None else {}),'M_c':[channels['G_c'][k] for k in sorted(ms)],'rows':aligned,'metrics':metrics,
            'excluded':{k:v.get('excluded',[])+v.get('pending',[])+[m for m in v.get('matches',[]) if m.get('status')!='applicable'] for k,v in [('G',g),('E',e)]+([('GT',gt)] if gt is not None else [])}}


def scenario_bindings(s,inputs):
    """Resolve a scene against positive element facts, without reading another channel."""
    i=next((i for i in interaction_rows(inputs) if i['id']==s.get('canonical_interaction_id',s['interaction_id'])),None)
    if i is None:return []
    result=[]
    for key in dict.fromkeys([s['concern_key']]+s.get('concern_origins',[])):
        definition=registry()['definitions'].get(key,{})
        if definition.get('kind')!='check':continue
        field=s.get('field')
        if key.startswith('api.data.'):
            target='data';name=field or s['object']
        elif definition.get('layer')=='relation':
            target='operation';name=i['operation']['name']
            sequence=i['operation'].get('sequence',[])
            if sequence.count(s.get('operation'))==1:name=s['operation']
        elif key.startswith('human.'):target='sender';name=i['sender']['name']
        else:
            target=next((side for side in ('sender','receiver') if i[side]['name']==s['object']),None);name=s['object']
            if target is None:continue
        raw={'interaction_id':i['id'],'target':target,'object':name,'concern_key':key,'basis':s.get('cause','异常来源'),'concrete_rule':None,
             'source_refs':s.get('source_refs',[]),'scope':s.get('scope','interface' if field else 'service'),'data_location':s.get('data_location'),
             'activation_evidence':s.get('activation_evidence',[])}
        if target=='operation' and name!=i['operation']['name']:raw['operation_index']=i['operation']['sequence'].index(name)
        value=recognize(inputs,{'matches':[raw]},inverse=True)
        result+=list(definite(value).values())
    return result


def bind_scenarios(value,inputs,recognized=None,*,gate=False):
    result=deepcopy(value);accepted=[];excluded=result.setdefault('excluded',[])
    allowed=definite(recognized or {})
    for s in result.get('scenarios',[]):
        bindings=scenario_bindings(s,inputs)
        if s.get('original_branch_id') and s.get('coverage_kind')=='input_parameters' and recognized is not None:
            # A recognized broad E branch can cite multiple request-field
            # bindings; it never covers returns or unrecognized definitions.
            bindings=[b for b in allowed.values() if b['interaction_id']==s['interaction_id'] and b['direction']=='request' and
                      b['target']=='data' and b['concern_key'].startswith('api.data.') and
                      s['original_branch_id'] in b.get('source_branch_ids',[])]
        if gate:bindings=[b for b in bindings if b['binding_id'] in allowed]
        if not bindings:
            excluded.append({'original_id':s['id'],'scenario_type':'pending','interaction_id':s['interaction_id'],'object':s['object'],'concern_key':s['concern_key'],
                             'reason':'场景没有对应的已识别关注点或四要素定位，未进入确定场景集合','source_refs':s.get('source_refs',[])})
            if recognized is not None and (any(k in inputs for k in ('identified-concerns','test-documents','existing-documents')) or any(m['interaction_id']==s['interaction_id'] and m['concern_key'] in [s['concern_key']]+s.get('concern_origins',[]) for m in recognized.get('matches',[]))):
                result.setdefault('pending',[]).append({'interaction_id':s['interaction_id'],'object':s['object'],'concern_key':s['concern_key'],
                    'reason':'关注点已识别，但本条场景未能对应到其四要素位置，保留来源待确认','source_refs':s.get('source_refs',[])})
            continue
        s['concern_binding_ids']=[b['binding_id'] for b in bindings]
        s['element_anchors']=[{k:b.get(k) for k in ('case_id','interaction_id','direction','target','element_id','object','data_location','concern_key','binding_id','operation_index')} for b in bindings]
        s['matching_version']=VERSION;accepted.append(s)
    result['scenarios']=accepted
    return result


def supplemental_concerns(tests,fused,parameters=None):
    """Typed independent test construction records its concerns before scenes.

    No G/E, generated negative candidates or evaluation results are accepted.
    """
    rows={i['id']:i for i in fused['interactions']};raw=[]
    for t in tests['tests']:
        i=rows[t['interaction_id']];key=t['concern_key'];definition=registry()['definitions'].get(key,{})
        target='data' if key.startswith('api.data.') else 'operation' if definition.get('layer')=='relation' else 'sender' if key.startswith('human.') else 'receiver' if i['direction']=='request' else 'sender'
        name=t.get('field') if target=='data' else i['operation']['name'] if target=='operation' else i[target]['name']
        if not name:continue
        raw.append({'interaction_id':i['id'],'target':target,'object':name,'concern_key':key,'scope':t['scope'],
                    'data_location':t.get('data_location'),'source_refs':t['source_refs'],'basis':'独立补充测试中已经识别的具体关注点',
                    'concrete_rule':t['trigger'],'source_unit_ids':['supplement-test-'+fingerprint(t)[:20]]})
    value=recognize({'fused-ssd':fused,**({'normal-constraints':parameters} if parameters else {})},{'matches':raw},inverse=True)
    for m in value['matches']:m['identification']='independent_typed_test'
    return value


def attach_report(report,concerns,*,original=None):
    result=deepcopy(report);result['legacy_scenario_metrics']=result.get('metrics',{})
    result['concern_level']=concerns;result['matching_version']=VERSION
    result['metrics']={**concerns['metrics'],**{k:v for k,v in result.get('metrics',{}).items() if k.startswith('recommendation_') or k=='critical_missing_recall'}}
    result['metric_units']={k:'关注点绑定' for k in concerns['metrics']}
    result['metric_units'].update({k:'独立异常场景' for k in result['metrics'] if k.startswith('recommendation_') or k=='critical_missing_recall'})
    if original is not None and result.get('original_evaluation'):
        result['original_evaluation']=attach_report(result['original_evaluation'],original)
    return result
