"""Versioned concern -> failure mode -> interaction instance. No E/GT/history input."""
from copy import deepcopy
import re,math
from .storage import fingerprint
from .concern_registry import registry

VERSION='scenario-patterns-v1'
RISK_VALUES={'low':.25,'normal':.5,'high':.75,'critical':1.0}
AUTH_MODES={
 'credential.missing':('凭证缺失','必填认证凭证未提供','必填|必须.*(?:Token|token|凭证)|携带.*(?:Token|token)|Authorization','high'),
 'credential.invalid':('凭证无效','凭证不满足明示的有效性要求','校验.*(?:Token|token|凭证)|(?:Token|token|凭证).*有效','high'),
 'credential.malformed':('凭证格式错误','凭证不符合约定格式','(?:Token|token|凭证).*格式|格式.*(?:Token|token|凭证)','high'),
 'credential.expired':('凭证过期','凭证已过期，超过声明的有效期','过期|有效期|expires|expiry','high'),
 'credential.revoked':('凭证被撤销','使用已经撤销的凭证','撤销|吊销|revok','high'),
 'credential.signature':('凭证签名无效','凭证签名校验失败','签名|signature','high'),
 'authorization.action':('操作未授权','调用方没有执行当前操作的权限','权限|授权|permission|authoriz','high'),
 'authorization.horizontal':('水平越权','调用方访问不属于自己的受保护资源','归属|所属|属于.*(?:用户|商家)|merchant_id.*匹配|owner|ownership','critical'),
 'authorization.vertical':('垂直越权','低权限调用方执行仅允许高权限角色的操作','管理员|角色.*权限|role.*permission|高权限|低权限','critical'),
 'authorization.tenant':('跨租户越权','调用方访问其他租户隔离范围内的资源','租户.*(?:隔离|权限|归属)|tenant.*(?:isolat|scope|owner)','critical'),
}

def _pattern(pid,key,label,premise,trigger,risk='normal',selector=None):
    return {'id':pid,'concern_keys':[key],'label':label,'preconditions':[premise],'trigger_template':trigger,'required_evidence':premise,'risk_level':risk,'risk_reason':'预置参考等级；仅在模式适用时使用，可按项目调整','selector':selector,'enabled':True,'version':1}

def default_library():
    result=[]
    for key,d in registry()['definitions'].items():
        if d['kind']!='check' or not d.get('enabled',True):continue
        risk='high' if d['layer'] in {'human','relation','technology'} or 'release' in key else 'normal'
        if key in {'service.resource_mutation.persistence_consistency','service_relation.cross_service_consistency','llm.prompt_security'}:risk='critical'
        result.append(_pattern('rule.'+key,key,d['label']+'规则违反','存在本交互明确正常规则','违反该规则的一个独立条件',risk))
    for suffix,key,kind in [('required','completeness','required'),('nonempty','completeness','not_empty'),('type','type','type'),('enum','legality','enum'),('format','format','format'),('pattern','format','pattern'),('minimum','range','minimum'),('maximum','range','maximum'),('length.minimum','length','length.minimum'),('length.maximum','length','length.maximum'),('size.minimum','size','size.minimum'),('size.maximum','size','size.maximum'),('relation','legality','relation')]:
        result.append(_pattern('data.'+suffix,'api.data.'+key,{'required': '必填字段未提供', 'nonempty': '非空字段为空', 'type': '数据类型错误', 'enum': '枚举值非法', 'format': '数据格式错误', 'pattern': '不满足格式模式', 'minimum': '违反数值下界', 'maximum': '违反数值上界', 'length.minimum': '低于长度下界', 'length.maximum': '超过长度上界', 'size.minimum': '低于大小下界', 'size.maximum': '超过大小上界', 'relation': '跨字段关系违反'}[suffix],'接口或存储Schema明确声明本约束','只违反本字段的一个独立约束','normal',kind))
    for root in ('human','service_relation'):
        for suffix,(label,trigger,pattern,risk) in AUTH_MODES.items():
            key=root+('.authentication' if suffix.startswith('credential.') else '.authorization')
            result.append(_pattern(root+'.'+suffix,key,label,'本次认证/授权适用，且明确声明：'+pattern,trigger,risk,pattern))
    return {'version':VERSION,'patterns':result}

def normalize_settings(value=None):
    v=deepcopy(value or {});v['concern_registry_hash']=registry()['hash'];v.setdefault('library',default_library());v.setdefault('threshold',.85);v.setdefault('top_k',10);v.setdefault('risk_weight',.7);v.setdefault('history_weight',.3);v.setdefault('overrides',{});v.setdefault('reviews',{})
    if type(v['threshold']) not in (int,float) or not math.isfinite(v['threshold']) or not 0<=v['threshold']<=1:raise ValueError('证据阈值必须为0至1')
    if type(v['top_k']) is not int or not 1<=v['top_k']<=1000:raise ValueError('K必须为1至1000的整数')
    if any(type(v[x]) not in (int,float) or (not math.isfinite(v[x]) or v[x]<0) for x in ('risk_weight','history_weight')) or abs(v['risk_weight']+v['history_weight']-1)>1e-9:raise ValueError('排序权重非负且合计为1')
    if not isinstance(v['library'],dict) or not isinstance(v['library'].get('patterns'),list):raise ValueError('模式库格式无效')
    if v['library'].get('version')!=VERSION:raise ValueError('不支持的模式库版本')
    if not isinstance(v['overrides'],dict) or not isinstance(v['reviews'],dict):raise ValueError('项目风险/审核格式无效')
    ids=set();definitions=registry()['definitions']
    for p in v['library']['patterns']:
        if not isinstance(p,dict) or not {'id','concern_keys','label','preconditions','trigger_template','required_evidence','risk_level','risk_reason','enabled','version'}<=p.keys():raise ValueError('模式缺少必要字段')
        if not isinstance(p['id'],str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,160}',p['id']) or type(p['enabled']) is not bool:raise ValueError('模式ID或启用状态无效')
        if not isinstance(p['concern_keys'],list) or not isinstance(p['preconditions'],list) or any(not isinstance(x,str) or not x.strip() for x in p['preconditions']):raise ValueError('前提必须是非空文本列表')
        if p['id'] in ids:raise ValueError('模式ID重复')
        ids.add(p['id'])
        if any(not isinstance(p.get(k),str) or not p[k].strip() for k in ('label','trigger_template','required_evidence','risk_reason')) or type(p['version']) is not int or p['version']<1:raise ValueError('模式文本/修订格式无效')
        if p.get('selector') is not None and (not isinstance(p['selector'],str) or len(p['selector'])>2048):raise ValueError('模式表达式必须是最多2048字符的文本')
        if any(not isinstance(k,str) for k in p['concern_keys']):raise ValueError('关注点ID必须为文本')
        if not p['concern_keys'] or any(k not in definitions or definitions[k]['kind']!='check' for k in p['concern_keys']):raise ValueError('模式必须关联现有具体关注点')
        if p['risk_level'] not in RISK_VALUES or not p['preconditions'] or not p['trigger_template'] or not p['required_evidence']:raise ValueError('模式缺少前提、触发、证据或风险等级')
        if p.get('selector'):
            try:re.compile(p['selector'])
            except re.error as e:raise ValueError('模式前提表达式无效') from e
        p['definition_hash']=fingerprint({k:p.get(k) for k in ('id','concern_keys','preconditions','trigger_template','required_evidence','selector')} | {'concern_definitions':{k:definitions[k] for k in p['concern_keys']}})
    for override in v['overrides'].values():
        if not isinstance(override,dict):raise ValueError('风险覆盖项格式无效')
        if override.get('risk_level') not in RISK_VALUES:raise ValueError('风险覆盖等级无效')
    for review in v['reviews'].values():
        if not isinstance(review,dict) or review.get('choice') not in {'confirm','reject','needs_info'} or not isinstance(review.get('note'),str) or not review['note'].strip():raise ValueError('模式审核缺少结论/理由')
        if review['choice']=='confirm' and (not isinstance(review.get('positive_condition'),str) or not review['positive_condition'].strip()):raise ValueError('确认适用必须提供正常规则')
        if review.get('policy_hash')!=fingerprint({k:x for k,x in review.items() if k!='policy_hash'})[:24]:raise ValueError('审核记录校验失败')
    v['hash']=fingerprint({k:x for k,x in v.items() if k!='hash'});return v

def context_for(i):
    position=i['sender'].get('position','')+' '+i['receiver'].get('position','')
    functions={'display':'display_interaction','read':'query_retrieval','create':'resource_mutation','update':'resource_mutation','delete':'resource_mutation','process':'analysis_generation','publish':'release_activation'}
    return {'functional_types':sorted({functions[k] for k in i['operation']['kinds'] if k in functions}),'technologies':sorted(t for t,word in [('database','数据库'),('llm','AI模型')] if word in position),'actual_operation':i['operation']['name'],'boundary':i['sender'].get('position','')+'→'+i['receiver'].get('position',''),'direction':i['direction'],'timeliness':'explicit' if re.search(r'实时|时限|截止|超时|deadline',' '.join(r['quote'] for r in i['source_refs'])) else None,'caller':i['sender']['name'],'provider':i['receiver']['name']}

def choose_pattern(s):
    key=s['concern_key'];text=s['cause']+' '+' '.join(s.get('conditions',[]))
    if key.endswith(('.authentication','.authorization')):
        root='human' if key.startswith('human.') else 'service_relation'
        modes=[k for k in AUTH_MODES if k.startswith('credential.' if key.endswith('authentication') else 'authorization.')]
        for mode,words in [('credential.missing','未提供|未携带|缺失|missing'),('credential.expired','过期|expired'),('credential.revoked','撤销|吊销|revoked'),('credential.signature','签名|signature'),('credential.malformed','格式|malformed'),('authorization.tenant','跨租户|其他租户'),('authorization.horizontal','不属于|归属|所属|他人|其他用户|其他商家|merchant_id'),('authorization.vertical','管理员|高权限|低权限|角色|垂直')]:
            if mode in modes and re.search(words,text,re.I):return root+'.'+mode
        return root+('.credential.invalid' if key.endswith('authentication') else '.authorization.action')
    rule=s.get('failure_rule') or {};kind=rule.get('kind') or s.get('cause')
    if key.startswith('api.data.'):
        return 'data.'+{'missing_required':'required','not_empty':'nonempty','other':'relation'}.get(kind,kind) if kind in {'required','missing_required','type','enum','minimum','maximum','format','pattern','length.minimum','length.maximum','size.minimum','size.maximum','not_empty','other'} else 'rule.'+key
    return 'rule.'+key

def confidence(score,reason):return {'score':score,'basis':reason,'calibrated_probability':False}

def risk_for(pattern,settings,context=None):
    o=settings['overrides'].get(pattern['id'],{});level=o.get('risk_level',pattern['risk_level'])
    return {'level':level,'score':RISK_VALUES[level],'reason':o.get('reason') or pattern['risk_reason'],'source':'project_override' if o else 'pattern_default'}

def annotate(s,i,settings,score=None,reason=None,pattern_id=None):
    s=deepcopy(s);patterns={p['id']:p for p in settings['library']['patterns'] if p['enabled']};pid=pattern_id or choose_pattern(s);p=patterns.get(pid)
    if p is None:return None
    if score is None:
        rule=s.get('failure_rule',{});mechanical=rule.get('kind') in {'required','not_empty','type','enum','minimum','maximum','exclusiveMinimum','exclusiveMaximum','pattern','length.minimum','length.maximum','size.minimum','size.maximum'}
        score=1.0 if mechanical and s.get('resolution')!='conditional' else .85
        reason='结构化明示约束，工具构造违例' if score==1 else '明确正常规则/实际服务调用与适用前提；未知具体标准仍独立标可执行性'
        if rule.get('kind')=='other':
            s.update(executable=False,resolution='conditional');s['pending_details']=list(dict.fromkeys(s.get('pending_details',[])+['语义关系约束有依据；具体违例测试数据和判定方式待准备']))
    if 'executable' not in s:
        s['executable']=False;s.setdefault('resolution','conditional');s.setdefault('pending_details',[])
        s['pending_details']=list(dict.fromkeys(s['pending_details']+['模式与交互已有依据；具体故障注入方式或测试数据尚未准备']))
    s.update(pattern_id=pid,linked_pattern_ids=[pid],confidence=confidence(score,reason),risk=risk_for(p,settings),scenario_context=context_for(i),pattern_versions={pid:p['definition_hash']})
    s['concern_origins']=list(dict.fromkeys(s.get('concern_origins',[])+p['concern_keys']+[s['concern_key']]))
    s['predicate']={**s.get('predicate',{}),'scope':s.get('scope','service'),'location':s.get('data_location'),'field':s.get('field'),'operator':(s.get('failure_rule') or {}).get('kind',s['cause']),'value':(s.get('failure_rule') or {}).get('value')}
    if s['concern_key']=='api.data.size':
        from .data_requirements import measure
        s['predicate'].setdefault('measure',measure(' '.join(s['conditions'])))
    return s

def security_rules(inputs,library=None):
    """Only positive conditions and metadata: ignores violation/G/E/test answers."""
    rows={i['id']:i for i in inputs.get('enriched-interactions',inputs.get('fused-ssd',{})).get('interactions',[])}
    patterns={p['id']:p for p in (library or default_library())['patterns']}
    out=[]
    for r in inputs.get('normal-rules',{}).get('rules',[]):
        key=r['concern_key'];i=rows.get(r['interaction_id'])
        if not i or i['direction']!='request' or not key.endswith(('.authentication','.authorization')):continue
        root='human' if key.startswith('human.') else 'service_relation';text=r['condition']
        for suffix,(label,trigger,selector,level) in AUTH_MODES.items():
            if suffix.startswith('credential.')!=key.endswith('.authentication'):continue
            p=patterns.get(root+'.'+suffix)
            if p and p.get('selector'):selector=p['selector'];trigger=p['trigger_template']
            out.append({'pattern_id':root+'.'+suffix,'rule':r,'interaction':i,'supported':bool(re.search(selector,text,re.I)),'trigger':trigger})
    known={(r['interaction']['id'],r['rule']['concern_key']) for r in out}
    for m in inputs.get('concern-match',{}).get('matches',[]):
        key=m['concern_key'];i=rows.get(m['interaction_id'])
        if not i or i['direction']!='request' or (i['id'],key) in known or not key.endswith(('.authentication','.authorization')) or m.get('status')=='not_applicable':continue
        root='human' if key.startswith('human.') else 'service_relation'
        for suffix,(label,trigger,selector,level) in AUTH_MODES.items():
            if suffix.startswith('credential.')!=key.endswith('.authentication'):continue
            r={'id':'framework-'+fingerprint([i['id'],key])[:16],'interaction_id':i['id'],'condition':'具体业务前提待确认','concern_key':key,'fields':[],'source_refs':m['source_refs'] or i['source_refs']}
            out.append({'pattern_id':root+'.'+suffix,'rule':r,'interaction':i,'supported':False,'trigger':trigger})
    concrete={}
    for row in out:
        if row['supported']:
            suffix=row['pattern_id'].split('.',1)[1]
            if suffix not in {'credential.missing','credential.invalid','authorization.action'}:concrete.setdefault((row['interaction']['id'],row['rule']['concern_key']),set()).add(suffix)
    # A broad validity/permission predicate is a parent when the same call has
    # evidenced concrete mechanisms. Do not score both parent and children.
    out=[r for r in out if not (r['pattern_id'].endswith(('.credential.invalid','.authorization.action')) and concrete.get((r['interaction']['id'],r['rule']['concern_key'])))]
    return out

def scenario_from_rule(record):
    from .normal_rules import rule_subject
    from .exception_generation import scenario_steps
    i=record['interaction'];r=record['rule'];trigger=record['trigger']
    fields=[p['name'] for p in i['data']['sequence'] if p.get('location')=='header' and re.search(r'authorization|token|credential',p['name'],re.I)]
    credential=fields[0] if len(fields)==1 and record['pattern_id'].endswith('credential.missing') else None
    return {'id':'mode-'+fingerprint([i['case_id'],i['id'],record['pattern_id'],r.get('fields',[])])[:24],'case_id':i['case_id'],'interaction_id':i['id'],'layer':i['layer'],'object':rule_subject(r,i),'operation':i['operation']['name'],'cause':trigger,'conditions':[trigger],'concern_key':r['concern_key'],'field':credential,'rule_id':r['id'],'source_status':'framework_inferred','derivation':'正向规则与异常模式独立实例化','source_refs':r['source_refs'],'steps':scenario_steps(i,[trigger]),'scope':'relation' if r['concern_key'].startswith('service_relation.') else 'service','data_location':'header' if credential else None,'scenario_type':'exception','resolution':'explicit','executable':True,'pending_details':[]}

def canonical_instances(rows):
    """No concrete test values in identity; merge aliases of credential missing."""
    result={}
    for s in rows:
        context=s.get('scenario_context',{});predicate=s.get('predicate',{})
        missing=s.get('pattern_id','').endswith('credential.missing') or s.get('field') and re.search(r'authorization|token|credential',s['field'],re.I) and (s.get('failure_rule') or {}).get('kind')=='required'
        missing=missing and bool(s.get('field'))
        semantic=[str(x).strip().casefold() for x in s.get('conditions',[])]
        token=('credential_missing',context.get('caller'),context.get('provider'),s.get('field','').casefold()) if missing else (s['object'],predicate if s.get('failure_rule') else [predicate.get('scope'),predicate.get('location'),predicate.get('field')],None if s.get('failure_rule') else semantic)
        key=fingerprint([s['case_id'],s['interaction_id'],s.get('scope') if not missing else 'credential',s.get('data_location') if not missing else 'header',token])
        if key in result:
            old=result[key]
            for field in ('concern_origins','linked_pattern_ids','source_refs','source_unit_ids','concern_binding_ids','element_anchors'):old[field]=list({fingerprint(x):x for x in old.get(field,[])+s.get(field,[])}.values())
            old.setdefault('pattern_versions',{}).update(s.get('pattern_versions',{}))
            if s['confidence']['score']>old['confidence']['score']:old['confidence']=s['confidence']
            if s['risk']['score']>old['risk']['score']:old['risk']=s['risk']
        else:result[key]=deepcopy(s)
    return list(result.values())


def coalesce_explicit_data_rules(rows):
    """Merge only fully parsed numeric failure predicates, never label-only matches.

    A local rule may repeat a structured interface bound. Match its entire
    single-field failure phrase and the already evidenced bound/direction;
    preserve all evidence/mode links while keeping one independent failure.
    """
    numeric=r'(-?\d+(?:\.\d+)?)';out=[]
    for s in rows:
        if s.get('failure_rule') or not s.get('field') or s.get('concern_key')!='api.data.range':out.append(s);continue
        field=re.escape(s['field']);text=re.sub(r'\s+','',s['cause']).rstrip('。；;')
        bounds=[]
        for word,kind in [('小于等于','exclusiveMinimum'),('大于等于','exclusiveMaximum'),('小于','minimum'),('低于','minimum'),('大于','maximum'),('超过','maximum'),('<','minimum'),('>','maximum'),('<=','exclusiveMinimum'),('>=','exclusiveMaximum')]:
            m=re.fullmatch(field+re.escape(word)+numeric,text)
            if m:bounds=[(kind,float(m[1]))];break
        if not bounds:
            m=re.fullmatch(field+r'不在'+numeric+r'(?:到|至|~|～|—|-)'+numeric+r'(?:范围内|之间)',text)
            if m:bounds=[('minimum',float(m[1])),('maximum',float(m[2]))]
        matches=[]
        for kind,value in bounds:
            found=next((r for r in rows if (r.get('interaction_id'),r.get('object'),r.get('field'),r.get('data_location'),r.get('scope'))==(s['interaction_id'],s['object'],s['field'],s.get('data_location'),s.get('scope')) and r.get('failure_rule',{}).get('kind')==kind and type(r['failure_rule'].get('value')) in (int,float) and r['failure_rule']['value']==value),None)
            if found is not None:matches.append(found)
        if not bounds or len(matches)!=len(bounds):out.append(s);continue
        for r in matches:
            child=deepcopy(s);child['failure_rule']=deepcopy(r['failure_rule']);child['predicate']=deepcopy(r['predicate'])
            child['linked_pattern_ids']=list(dict.fromkeys(child['linked_pattern_ids']+r['linked_pattern_ids']))
            child['pattern_versions'].update(r['pattern_versions']);out.append(child)
    return out

def applicability(inputs,settings=None):
    from .exception_generation import data_exceptions,query_exceptions,service_exceptions,storage_exceptions,attach_provenance
    from .normal_rules import rule_exceptions
    settings=normalize_settings(settings);rows={i['id']:i for i in inputs['enriched-interactions']['interactions']};candidates=[];issues=[]
    security=security_rules(inputs,settings['library']);replaced={r['rule']['id'] for r in security}
    base=data_exceptions(inputs)+query_exceptions(inputs)+service_exceptions(inputs)+storage_exceptions(inputs)+[s for s in rule_exceptions(inputs) if s['rule_id'] not in replaced]
    from .scenario_types import filter_scenarios
    base=filter_scenarios({'scenarios':attach_provenance(inputs,base)},inputs,'exception-generate')['scenarios']
    base=split_structured_bounds(base)
    for s in base:
        value=annotate(s,rows[s['interaction_id']],settings)
        if value:candidates.append(value)
        else:issues.append({'interaction_id':s['interaction_id'],'object':s['object'],'concern_key':s['concern_key'],'reason':'模式库缺少或停用了对应模式：'+choose_pattern(s),'source_refs':s['source_refs']})
    for rec in security:
        s=scenario_from_rule(rec);value=annotate(s,rec['interaction'],settings,.85 if rec['supported'] else .6,'正向规则声明模式前提' if rec['supported'] else '只有框架提示，缺少该细分模式的业务前提',pattern_id=rec['pattern_id'])
        if value:
            value['pattern_id']=rec['pattern_id'];value['linked_pattern_ids']=[rec['pattern_id']]
            pattern=next((p for p in settings['library']['patterns'] if p['id']==rec['pattern_id'] and p['enabled']),None)
            if not pattern:continue
            value['risk']=risk_for(pattern,settings)
            if not rec['supported']:value.update(executable=False,resolution='conditional',pending_details=['模式前提需确认'],scenario_type='pending')
            candidates.append(value)
    for pattern in settings['library']['patterns']:
        if not pattern['enabled'] or not pattern['id'].startswith('custom.') or not pattern.get('selector'):continue
        for rule in inputs.get('normal-rules',{}).get('rules',[]):
            if rule['concern_key'] not in pattern['concern_keys'] or not re.search(pattern['selector'],rule['condition'],re.I):continue
            i=rows.get(rule['interaction_id'])
            if not i:continue
            value=annotate(scenario_from_rule({'pattern_id':pattern['id'],'rule':rule,'interaction':i,'trigger':pattern['trigger_template']}),i,settings,.85,'项目审核模式前提与明示正常规则对应',pattern_id=pattern['id'])
            value.update(executable=False,resolution='conditional',pending_details=['自定义模式的具体执行数据待准备'])
            candidates.append(value)
    for scenario in candidates:
        rules=[r for r in inputs.get('normal-rules',{}).get('rules',[]) if r['interaction_id']==scenario['interaction_id']]
        text=' '.join(r['condition'] for r in rules)
        if re.search(r'实时|时限|截止|超时|deadline|\d+(?:\.\d+)?\s*(?:毫秒|秒|ms)\s*(?:内|以内|返回|响应)',text,re.I):scenario['scenario_context']['timeliness']='explicit'
        for technology,prefix in [('llm','llm.'),('database','database.')]:
            if any(r['concern_key'].startswith(prefix) for r in rules):scenario['scenario_context']['technologies']=sorted(set(scenario['scenario_context']['technologies'])|{technology})
    from .concern_alignment import bind_scenarios
    scoped=bind_scenarios({'scenarios':candidates},inputs,inputs.get('concern-match',{}),gate=True)
    candidates=canonical_instances(coalesce_explicit_data_rules(scoped['scenarios']));instances=[]
    for s in candidates:
        sid='candidate-'+fingerprint([s['case_id'],s['interaction_id'],s['pattern_id'],s['predicate'],s.get('conditions'),s['source_refs'],s.get('pattern_versions')])[:24]
        review=settings['reviews'].get(sid)
        if review and review['choice']=='reject':s['confidence']=confidence(0,'项目审核明确不适用：'+review['note'])
        elif review and review['choice']=='confirm':
            ref={'source_id':'project-policy-'+review['policy_hash'],'line_start':1,'line_end':1,'quote':review['positive_condition']}
            s['source_refs']=s['source_refs']+[ref];s['confidence']=confidence(.85,'项目审核补充正常规则：'+review['positive_condition']);s['scenario_type']='exception';s['executable']=False;s['resolution']='conditional';s['pending_details']=['业务确认适用；执行数据仍需准备']
        status='accepted' if s['confidence']['score']>=settings['threshold'] and s['confidence']['score']>0 else 'excluded' if s['confidence']['score']==0 else 'pending'
        s['scenario_type']='exception' if status=='accepted' else 'pending';instances.append({'id':sid,'pattern_id':s['pattern_id'],'status':status,'scenario':s})
    return {'instances':instances,'settings_hash':settings['hash'],'library_version':VERSION,'threshold':settings['threshold'],'issues':issues,'excluded':scoped['excluded']}

def generated(matrix):
    rows=[i['scenario'] for i in matrix['instances'] if i['status']=='accepted'];pending=list(matrix['issues'])
    for item in matrix['instances']:
        if item['status']=='pending':
            s=item['scenario'];pending.append({'interaction_id':s['interaction_id'],'object':s['object'],'concern_key':s['concern_key'],'reason':s['confidence']['basis']+'；候选 '+item['id'],'source_refs':s['source_refs']})
    return {'scenarios':rows,'pending':pending,'excluded':matrix.get('excluded',[])}


def inverse_metadata(value,inputs,settings=None,*,truth=False):
    """Annotate independent inverse channel; generic coverage belongs to E only."""
    settings=normalize_settings(settings);out=deepcopy(value)
    from .data_requirements import split_size_scenarios
    out['scenarios']=split_size_scenarios(out['scenarios'])
    rows={i['id']:i for i in inputs.get('fused-ssd',{}).get('interactions',[])}
    branches={b['id']:b for b in inputs.get('branches',{}).get('branches',[])}
    for s in out['scenarios']:
        i=rows.get(s['interaction_id'])
        if not i:continue
        annotated=annotate(s,i,settings)
        if annotated:s.update(annotated)
        b=branches.get(s.get('original_branch_id'))
        if truth or not b:continue
        text=b['description']
        if s['concern_key'].endswith('.authentication') and re.search(r'认证失败|身份验证失败|认证不通过',text) and not re.search(r'过期|撤销|签名|格式|缺失|未提供',text):s['coverage_kind']='authentication'
        if s['concern_key'].endswith('.authorization') and re.search(r'权限不足|无权访问|未授权',text) and not re.search(r'水平|垂直|租户|归属',text):s['coverage_kind']='authorization'
    if truth:
        known=[s for s in out['scenarios'] if s.get('failure_rule') and 'pattern_id' in s]
        other=[s for s in out['scenarios'] if not (s.get('failure_rule') and 'pattern_id' in s)]
        out['scenarios']=other+canonical_instances(known)
    return out


def split_structured_bounds(rows):
    """Structured length/size intervals only; arbitrary prose is not a parser."""
    from .data_requirements import split_size_scenarios
    rows=split_size_scenarios(rows);out=[]
    for s in rows:
        rule=s.get('failure_rule',{});value=rule.get('value');kind=rule.get('kind')
        if kind not in {'length','size'} or not isinstance(value,dict):out.append(s);continue
        bounds=[]
        for side,aliases in [('minimum',('min','minimum','minLength','minItems','minBytes')),('maximum',('max','maximum','maxLength','maxItems','maxBytes'))]:
            found=[value[k] for k in aliases if k in value]
            if len(found)==1 and type(found[0]) in (int,float):bounds.append((side,found[0]))
        if not bounds:out.append(s);continue
        for side,number in bounds:
            child=deepcopy(s);predicate=kind+'.'+side;child['failure_rule']={'kind':predicate,'value':number};child['cause']=predicate
            child['conditions']=[s['field']+'已提供',f'违反{predicate}约束: {number}'];child['steps']['trigger']='；'.join(child['conditions']);child['id']='bound-'+fingerprint([s['case_id'],s['interaction_id'],s['data_location'],s['field'],predicate,number])[:24]
            out.append(child)
    return out
