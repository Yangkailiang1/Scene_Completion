"""Positive-only rules and normalization, never cross-channel answers."""
from copy import deepcopy
import re
from .storage import fingerprint
RULESET_VERSION='quality-rules-20261025-v1'
LOCATIONS={'header','path','query','body','response','business','storage','context'}

def normalize_location(field,location):
    if location in LOCATIONS or location is None:return field,location
    prefix,sep,tail=location.partition('.')
    if sep and prefix in LOCATIONS:return field or tail,prefix
    raise ValueError('unknown field location: '+str(location))

def descriptive_constraint(rule):
    text=str(rule.get('value') or '').strip()
    return rule['kind']=='other' and (not text or bool(re.fullmatch(r'.*(?:唯一编号|唯一标识|新版本号|字段说明|示例值)',text)))

def conditional_constraint(rule):
    if rule.get('kind') not in {'format','pattern','length','size','minimum','maximum'}:return False
    if rule.get('status')!='pending' and str(rule.get('value') or '').strip() not in {'','合法','有效','格式合法','长度合法','允许范围','格式有效'}:return False
    text=' '.join(r['quote'] for r in rule.get('source_refs',[]))
    return bool(re.search(r'格式(?:合法|有效|校验)|URL.*(?:合法|有效|格式)|长度(?:合法|有效|限制)|数量.*(?:范围|限制)|允许范围|上限|下限|format.*(?:valid|check)|size.*limit',text,re.I))

def validate_rules(value,inputs):
    from .contracts import registry
    from .inverse_alignment import canonical_fused
    from .source_documents import validate_evidence
    rows={i['id']:i for i in canonical_fused(inputs['fused-ssd'])['interactions']}
    if len({r['id'] for r in value['rules']})!=len(value['rules']):raise ValueError('normal rule IDs must be unique')
    for rule in value['rules']:
        i=rows.get(rule['interaction_id'])
        if not i or i['direction']!='request':raise ValueError('normal rule must bind an existing actual request')
        if rule['owner_service']!=i['receiver']['name']:raise ValueError('normal rule owner must be this actual receiver')
        if rule['concern_key'] not in registry()['definitions']:raise ValueError('unknown normal-rule concern')
        if re.search(r'或者|或|\bor\b',rule['violation'],re.I):raise ValueError('one rule must describe one independent failure, not an OR of causes; split into separate rules: '+rule['violation'])
        if rule['concern_key'].startswith('api.data.') and len(rule['fields'])!=1:raise ValueError('one data rule requires one field; split independent fields, keep genuine relational constraints under a business concern')
        validate_evidence(rule['source_refs'],inputs['normal-documents'])
        quote=' '.join(r['quote'] for r in rule['source_refs'])
        compact=lambda text:re.sub(r'\s+','',text)
        if compact(rule['condition']) not in compact(quote):raise ValueError('normal condition must be an exact clause of its cited normal evidence, not a neighbouring or paraphrased claim')
        invoked=re.search(r'调用\s*([A-Za-z_][A-Za-z0-9_]*Service)\s*(?:的)?(?:校验|验证)',rule['condition'])
        if invoked and rule['owner_service']!=invoked[1]:raise ValueError('the normal evidence delegates this validation to '+invoked[1]+'; this task must not claim that caller executes it; omit and let the matching provider task extract it')
        for field in rule['fields']:
            leaf=re.sub(r'\[\]','',field.split('.')[-1])
            actual={p['name'] for p in i['data']['sequence']}
            if leaf.isascii() and leaf not in quote and field not in actual:raise ValueError('normal-rule field absent from both cited evidence and the actual input: '+field)
        numbers=re.findall(r'(?:>=|<=|>|<|≥|≤|=)\s*(-?\d+(?:\.\d+)?)',rule['condition'])
        if any(n not in re.findall(r'-?\d+(?:\.\d+)?',quote) for n in numbers):raise ValueError('normal-rule threshold not in cited evidence')
        if rule['resolution']=='conditional' and not re.search(r'校验|合法|有效|范围|约束|规则|valid|check|limit',quote,re.I):raise ValueError('conditional rule requires a declared normal check')

def rule_matches(inputs):
    from .contracts import registry
    out=[];definitions=registry()['definitions']
    for r in inputs.get('normal-rules',{}).get('rules',[]):
        d=definitions[r['concern_key']]
        if r['concern_key'].startswith('api.data.'):
            from .interaction_enrichment import interactions,parameters_for
            i=next((i for i in interactions(inputs) if i['id']==r['interaction_id']),None)
            ps=[p for p in parameters_for(i,inputs) if p['name'] in r['fields']] if i else []
            if len(ps)!=1:continue
            p=ps[0]
            out.append({'interaction_id':i['id'],'target':'data','object':p['name'],'concern_key':r['concern_key'],
              'basis':'独立正向正常规则索引','concrete_rule':r['condition'],'source_refs':r['source_refs'],
              'scope':'interface','data_location':p['location'],'activation_evidence':[]})
            continue
        out.append({'interaction_id':r['interaction_id'],'target':'receiver','object':r['owner_service'],
          'concern_key':r['concern_key'],'basis':'独立正向正常规则索引','concrete_rule':r['condition'],'source_refs':r['source_refs'],
          'scope':'relation' if d['layer']=='relation' else 'service','data_location':None,
          'activation_evidence':[{'kind':d.get('guard') or 'business','condition':r['condition'],'value':r['condition'],'unit':None,'status':'explicit','source_refs':r['source_refs'],'field':None,'constraint_kind':None}]})
    return out

def rule_exceptions(inputs):
    from .interaction_enrichment import interactions
    from .exception_generation import scenario_steps
    from .concern_hierarchy import match_is_applicable
    rows={i['id']:i for i in interactions(inputs)};out=[]
    for r in inputs.get('normal-rules',{}).get('rules',[]):
        i=rows.get(r['interaction_id'])
        if not i:continue
        data=r['concern_key'].startswith('api.data.');obj=r['fields'][0] if data else r['owner_service']
        matches=[m for m in inputs.get('concern-match',{}).get('matches',[]) if (m['interaction_id'],m['object'],m['concern_key'])==(i['id'],obj,r['concern_key']) and match_is_applicable(m,i,inputs)]
        if not matches:continue
        out.append({'id':'G-rule-'+fingerprint([i['id'],r['id']])[:20],
          'case_id':i['case_id'],'interaction_id':i['id'],'layer':i['layer'],'object':obj,
          'operation':i['operation']['name'],'cause':r['violation'],'conditions':[r['violation']],
          'concern_key':r['concern_key'],'field':obj if data else None,'rule_id':r['id'],
          'source_status':'framework_inferred','derivation':'独立正向规则取反：'+r['condition'],'source_refs':r['source_refs'],
          'steps':scenario_steps(i,[r['violation']]),'scope':'interface' if data else 'service','data_location':matches[0].get('data_location') if data else None,
          'resolution':r['resolution'],'executable':r['resolution']=='explicit','pending_details':r['pending_details']})
    return out

def normalize_scenarios(value,inputs,*,truth=False):
    out=deepcopy(value);rules={r['id']:r for r in inputs.get('normal-rules',{}).get('rules',[])}
    fused=inputs.get('fused-ssd') or inputs.get('enriched-interactions',{})
    rows={i['id']:i for i in fused.get('interactions',[])};result=[]
    for raw in out.get('scenarios',[]):
        s=deepcopy(raw);original={'interaction_id':s['interaction_id'],'object':s['object'],'field':s.get('field'),'data_location':s.get('data_location')}
        s['field'],s['data_location']=normalize_location(s.get('field'),s.get('data_location'))
        if s.get('rule_id') in rules:
            r=rules[s['rule_id']];i=rows.get(r['interaction_id'])
            if i:
                s.update(interaction_id=i['id'],canonical_interaction_id=i['id'],layer=i['layer'],operation=i['operation']['name'])
                s['concern_key']=r['concern_key']
                if s['concern_key'].startswith('api.data.'):
                    from .interaction_enrichment import parameters_for
                    api_inputs={**inputs,'api-parameters':inputs.get('api-parameters',inputs.get('normal-constraints',{'apis':[]}))}
                    ps=[p for p in parameters_for(i,api_inputs) if p['name'] in r['fields']]
                    if len(ps)==1:s.update(object=ps[0]['name'],field=ps[0]['name'],data_location=ps[0]['location'],scope='interface')
                else:s.update(object=r['owner_service'],field=None,data_location=None,scope='service')
        if s['concern_key'].startswith('api.data.') and s.get('field'):s['object']=s['field']
        fields=re.split(r'\s*/\s*',s.get('field') or '')
        split=len(fields)>1 and all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.\[\]]*',f) for f in fields) and not re.search(r'>=|<=|≥|≤|与.*(?:比较|一致)',s['cause'])
        children=[]
        if split:
            for f in fields:
                child=deepcopy(s);child.update(id=s['id']+'--'+fingerprint(f)[:8],field=f,object=f)
                child['cause']=child['cause'].replace(s['field'],f);child['conditions']=[v.replace(s['field'],f) for v in child['conditions']];children.append(child)
        else:children=[s]
        for child in children:
            if original!={k:child.get(k) for k in original}:child['normalization_origin']=original
            result.append(child)
    out['scenarios']=result
    return out
