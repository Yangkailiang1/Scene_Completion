"""Positive-only rules and normalization, never cross-channel answers."""
from copy import deepcopy
import re
from .storage import fingerprint
RULESET_VERSION='two-level-concern-scenario-20261026-v1'
LOCATIONS={'header','path','query','body','response','business','storage','context'}

def identity_concern(key,interaction):
    """Authentication taxonomy follows the explicit caller identity, not wording."""
    if key not in {'human.authentication','human.authorization','service_relation.authentication','service_relation.authorization'}:return key
    family='human' if '人类' in interaction['sender']['position'] else 'service_relation'
    return family+'.'+key.rsplit('.',1)[1]

def rule_subject(rule,interaction):
    caller=caller_concern(rule['concern_key'])
    party=interaction['sender' if caller else 'receiver']
    if party.get('resource_service'):return party['resource_service']['name']
    if '数据库' in party['position']:
        from .interaction_enrichment import resource_service_name
        return resource_service_name(party['name'])
    return party['name']

def caller_concern(key):
    from .concern_registry import registry
    d=registry()['definitions'].get(key,{})
    return key.startswith('human.') or d.get('layer')=='relation' and d.get('guard') in {'authentication','authorization'}

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
    if rule.get('status')!='pending' and str(rule.get('value') if rule.get('value') is not None else '').strip() not in {'','合法','有效','格式合法','长度合法','允许范围','格式有效'}:return False
    text=' '.join(r['quote'] for r in rule.get('source_refs',[]))
    return bool(re.search(r'格式(?:合法|有效|校验)|URL.*(?:合法|有效|格式)|长度(?:合法|有效|限制)|数量.*(?:范围|限制)|允许范围|上限|下限|format.*(?:valid|check)|size.*limit',text,re.I))

def documented_normal_tolerance(inputs):
    """Only explicit optional tolerance with normal fallback, never all optional tests."""
    rows=[r['text'] for d in inputs.get('test-documents',[]) for r in d['lines'] if re.match(r'^\s*\|',r['text'])]
    return bool(rows) and all(re.search(r'\|\s*可选\s*\|',r) and '容错' in r and re.search(r'隐藏|缺省|默认|忽略',r) and not re.search(r'必须|应当失败|应拒绝|崩溃',r) for r in rows)

def separate_unknown_criteria(value,normalizations=None):
    """Information missing from the spec is a pending issue, not a runtime fault."""
    out=deepcopy(value);rules=[]
    for r in out['rules']:
        unknown=r['resolution']=='conditional' and r.get('pending_details') and re.search(r'(?:缺少|缺乏|未给出).*(?:具体)?(?:阈值|判定标准)|无法判定',r['violation'])
        unsupported=r['resolution']=='conditional' and not declared_check(r)
        if unknown or unsupported:
            out.setdefault('pending',[]).append({'interaction_id':r['interaction_id'],'reason':'条件级异常的判定依据/关注点分类待确认：'+'；'.join(r['pending_details']),'source_refs':r['source_refs']})
            if normalizations is not None:normalizations.append({'rule_id':r['id'],'action':'move missing-spec criterion to pending; no runtime exception inferred','original_violation':r['violation']})
        else:rules.append(r)
    out['rules']=rules
    return out

def declared_check(rule):
    return bool(re.search(r'校验|合法|有效|范围|约束|规则|valid|check|limit',' '.join(r['quote'] for r in rule['source_refs']),re.I))


def separate_foreign_checks(value,inputs,normalizations=None):
    """Don't assign a caller's explicit local check to its database callee."""
    out=deepcopy(value);by_id={i['id']:i for i in inputs.get('fused-ssd',{}).get('interactions',[])};kept=[]
    for rule in out['rules']:
        i=by_id.get(rule['interaction_id']);refs=[]
        invoked=re.search(r'调用\s*([A-Za-z_][A-Za-z0-9_]*Service)\s*(?:的)?(?:校验|验证)',rule.get('condition',''))
        if i and invoked and rule['owner_service']!=invoked[1]:
            from .source_documents import validate_evidence
            validate_evidence(rule['source_refs'],inputs['normal-documents'])
            quote=' '.join(r['quote'] for r in rule['source_refs'])
            if re.sub(r'\s+','',rule['condition']) in re.sub(r'\s+','',quote):
                reason='原文明示将校验委托给'+invoked[1]+'，当前接收方为'+i['receiver']['name']+'；保留待确认，不把委托的业务判断视为当前资源服务已执行。请在对应实际服务交互核对。'
                out.setdefault('pending',[]).append({'interaction_id':i['id'],'reason':reason,'source_refs':rule['source_refs']})
                if normalizations is not None:normalizations.append({'rule_id':rule['id'],'action':'retain delegated validation as pending; do not claim foreign ownership','source_refs':rule['source_refs']})
                continue
        if i and i['sender']['name']!=i['receiver']['name'] and rule['fields']:
            actual={p['name'] for p in i['data']['sequence']};quoted=' '.join(r['quote'] for r in rule['source_refs'])
            if not any(f in actual or f in quoted for f in rule['fields']):
                refs=[r for r in i['operation']['source_refs'] if all(f in r['quote'] for f in rule['fields']) and re.search(re.escape(i['sender']['name'])+r'.*(?:校验|检查)',r['quote']) and i['receiver']['name'] not in r['quote']]
        if refs:
            from .source_documents import validate_evidence
            validate_evidence(refs,inputs['normal-documents'])
            reason='规则归属核查：明示执行者是发送方'+i['sender']['name']+'，并非当前接收方'+i['receiver']['name']+'；本子任务不代领该本地校验，需在执行者的实际接收请求核对'
            out.setdefault('pending',[]).append({'interaction_id':i['id'],'reason':reason,'source_refs':refs})
            if normalizations is not None:normalizations.append({'rule_id':rule['id'],'action':'keep foreign-owner check as pending, not a fabricated callee rule','source_refs':refs})
        else:kept.append(rule)
    out['rules']=kept;return out


def has_compound_failure(text):
    # “SHIPPED or later” describes one ordered-state predicate, not two
    # independently triggered failures. Other OR causes still require splits.
    predicate=re.sub(r'(?:或者|或)\s*(?:更(?:后|前|高|低)(?:状态|阶段|等级)?|以上|以下)|\bor\s+(?:later|earlier|higher|lower)\b','',text,flags=re.I)
    return bool(re.search(r'或者|或|\bor\b',predicate,re.I))

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
        if rule['concern_key'] not in registry()['definitions'] or not registry()['definitions'][rule['concern_key']].get('enabled',True) or registry()['definitions'][rule['concern_key']]['kind']!='check':raise ValueError('unknown, disabled or non-leaf normal-rule concern')
        if identity_concern(rule['concern_key'],i)!=rule['concern_key']:raise ValueError('authentication/authorization concern must follow this actual caller identity')
        if has_compound_failure(rule['violation']):raise ValueError('one rule must describe one independent failure, not an OR of causes; split into separate rules: '+rule['violation'])
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
        if rule['resolution']=='conditional' and not declared_check(rule):raise ValueError('conditional rule requires a declared normal check')

def rule_matches(inputs):
    from .contracts import registry
    out=[];definitions=registry()['definitions']
    for r in inputs.get('normal-rules',{}).get('rules',[]):
        d=definitions[r['concern_key']]
        from .interaction_enrichment import interactions
        i=next((i for i in interactions(inputs) if i['id']==r['interaction_id']),None)
        if not i:continue
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
        caller=caller_concern(r['concern_key'])
        out.append({'interaction_id':r['interaction_id'],'target':'sender' if caller else 'receiver','object':rule_subject(r,i),
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
        data=r['concern_key'].startswith('api.data.');obj=r['fields'][0] if data else rule_subject(r,i)
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
        s=deepcopy(raw)
        if s.get('scope')=='business':s['scope']='interface' if s['concern_key'].startswith('api.data.') else 'service'
        original={'interaction_id':s['interaction_id'],'object':s['object'],'field':s.get('field'),'data_location':s.get('data_location')}
        mapped_service=s.get('rule_id') in rules and not s['concern_key'].startswith('api.data.') and not rules[s['rule_id']]['concern_key'].startswith('api.data.')
        if not mapped_service:s['field'],s['data_location']=normalize_location(s.get('field'),s.get('data_location'))
        if s.get('rule_id') in rules:
            r=rules[s['rule_id']];i=rows.get(r['interaction_id'])
            conflict=None
            if s['concern_key'].startswith('api.data.') and r['concern_key'].startswith('api.data.'):
                f=s.get('field')
                if f and r['fields'] and not any(f==rf or f.endswith('.'+rf) or rf.endswith('.'+f) for rf in r['fields']):
                    conflict='规则字段'+str(r['fields'])+'与异常字段'+f+'不一致'
                elif s['concern_key']!=r['concern_key']:conflict='规则与异常的数据失败类别不一致'
            if conflict:
                from .execution_events import emit
                emit('normal_rule_reference_ignored',scenario_id=s['id'],rule_id=s['rule_id'],reason=conflict,action='保留原异常对象、字段、条件及绑定；取消无效索引引用，不替换为另一种异常')
                s['derivation']+='；索引对齐诊断：'+conflict+'，取消该规则引用，保留原测试/分支依据，未改变异常原因和字段。'
                s['rule_id']=None;i=None
            if i:
                s.update(interaction_id=i['id'],canonical_interaction_id=i['id'],layer=i['layer'],operation=i['operation']['name'])
                s['concern_key']=r['concern_key']
                if s['concern_key'].startswith('api.data.'):
                    from .interaction_enrichment import parameters_for
                    api_inputs={**inputs,'api-parameters':inputs.get('api-parameters',inputs.get('normal-constraints',{'apis':[]}))}
                    ps=[p for p in parameters_for(i,api_inputs) if p['name'] in r['fields']]
                    if len(ps)==1:s.update(object=ps[0]['name'],field=ps[0]['name'],data_location=ps[0]['location'],scope='interface')
                else:s.update(object=rule_subject(r,i),field=None,data_location=None,scope='service')
        s['field'],s['data_location']=normalize_location(s.get('field'),s.get('data_location'))
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
