"""Inverse units are built only from original branches and positive contracts, never G."""
from copy import deepcopy
from .storage import fingerprint
from .interaction_types import classify
from .interaction_enrichment import interactions,parameters_for
from .exception_generation import data_exceptions,deduplicate
from .concern_registry import inheritance_paths

def canonical_fused(value):
    rows=value['interactions'];by_id={i['id']:i for i in rows};aliases={}
    for link in value.get('rr_sr_links',[]):
        if link['status']!='confirmed':continue
        rr=by_id.get(link['rr_id'])
        if not rr:continue
        # Only identical endpoint/direction messages in an evidenced expansion
        # are duplicate views. Downstream service calls remain distinct.
        for sid in link['sr_ids']:
            sr=by_id[sid]
            if rr['sender']['name']==sr['sender']['name'] and rr['receiver']['name']==sr['receiver']['name'] and rr['direction']==sr['direction']:
                aliases[rr['id']]=sr['id'];break
    for rr in rows:
        if rr['layer']!='RR' or rr['direction']!='return' or rr.get('parent_id') not in aliases:continue
        candidates=[sr for sr in rows if sr['layer']=='SR' and sr['direction']=='return' and sr.get('parent_id')==aliases[rr['parent_id']] and rr['sender']['name']==sr['sender']['name'] and rr['receiver']['name']==sr['receiver']['name']]
        if len(candidates)==1:aliases[rr['id']]=candidates[0]['id']
    kept=[deepcopy(i) for i in rows if i['id'] not in aliases]
    for i in kept:
        if i.get('parent_id') in aliases:i['parent_id']=aliases[i['parent_id']]
    return {'interactions':kept,
      'aliases':[{'source_id':k,'interaction_id':v} for k,v in aliases.items()]}

def normalized_scenarios(value,fused):
    canonical=canonical_fused(fused);aliases={x['source_id']:x['interaction_id'] for x in canonical['aliases']};by_id={i['id']:i for i in canonical['interactions']}
    from .normal_rules import normalize_scenarios
    out=normalize_scenarios(value,{'fused-ssd':fused})
    for s in out.get('scenarios',[]):
        iid=aliases.get(s['interaction_id'],s['interaction_id']);i=by_id.get(iid)
        if not i:raise ValueError('异常必须绑定本用例融合SSD中的具体交互')
        s.update(interaction_id=iid,canonical_interaction_id=iid,interaction_type=classify(i,fused['interactions'])['kind'])
    out['scenarios']=deduplicate(out.get('scenarios',[]));return out

def broad_input_branch(description):
    import re
    return bool(re.search(r'参数.{0,6}(非法|无效|错误)|invalid.{0,16}param|parameter.{0,16}(invalid|error)',description,re.I))

def expand_inverse(value,inputs):
    from .normal_rules import normalize_scenarios
    value=normalize_scenarios(value,inputs)
    from .failure_units import normalize_inverse_units
    value=normalize_inverse_units(value,inputs)
    value=normalized_scenarios(value,inputs['fused-ssd'])
    branches={b['id']:b for b in inputs.get('branches',{}).get('branches',[])}
    from .failure_units import normalize_bindings
    verified_bindings=normalize_bindings(inputs.get('bindings',{}),inputs)
    bindings={(b['branch_id'],b['interaction_id']) for b in verified_bindings.get('bindings',[]) if b['status']=='confirmed'}
    rows=canonical_fused(inputs['fused-ssd'])['interactions'];out=[];broad_parents={}
    for s in value['scenarios']:
        branch=s.get('original_branch_id')
        if branches and (branch not in branches or (branch,s['interaction_id']) not in bindings):raise ValueError('细化项必须有已确认的原分支和交互绑定')
        if s.get('coverage_kind')!='input_parameters':out.append(s);continue
        if not branches or branch not in branches:raise ValueError('宽泛覆盖必须保留原始分支')
        b=branches[branch]
        if not broad_input_branch(b['description']):raise ValueError('原分支 '+branch+' 不支持参数非法宽泛覆盖: '+b['description'][:180]+'。只有明确宽泛参数非法的本分支才可用input_parameters；其他分支须按自身具体原因使用exact，不能把相邻分支合并成宽泛覆盖。')
        i=next(i for i in rows if i['id']==s['interaction_id'])
        if i['direction']!='request':raise ValueError('参数非法不能覆盖输出交互')
        identity=(branch,i['id'])
        if identity in broad_parents:
            parent=broad_parents[identity]
            parent['source_unit_ids']=list(dict.fromkeys(parent.get('source_unit_ids',[parent['id']])+s.get('source_unit_ids',[s['id']])))
            continue
        # The broad parent is retained for auditable one-to-many coverage.
        s.update(scope='interface',data_location=None,field=None,object='请求参数',cause='输入参数非法',conditions=['当前输入参数违反原文明示约束'],source_refs=b['source_refs'])
        s['steps']['trigger']='当前输入参数违反原文明示约束（原文宽泛分支）'
        s['quality_notes']=list(dict.fromkeys(s.get('quality_notes',[])+['broad_branch：同一原分支和交互只保留一个宽泛父项；具体字段由正常接口约束细化']))
        broad_parents[identity]=s;out.append(s)
        model={'rr-ssd':{'interactions':[i] if i['layer']=='RR' else []},'sr-ssd':{'interactions':[i] if i['layer']=='SR' else []},'api-parameters':inputs['normal-constraints']}
        matches=[]
        for p in parameters_for(i,model):
            for suffix in ('completeness','type','format','length','size','range','legality'):
                k='api.data.'+suffix
                matches.append({'interaction_id':i['id'],'target':'data','object':p['name'],'concern_key':k,'scope':'interface','data_location':p['location'],'source_refs':p['source_refs'],'concrete_rule':'接口明示约束'})
        model['concern-match']={'matches':matches}
        for child in data_exceptions(model):
            child.update(id='E-'+fingerprint([branch,child['rule_id'],i['id']])[:20],original_branch_id=branch,coverage_kind='exact',source_status='framework_inferred',canonical_interaction_id=i['id'],interaction_type=s['interaction_type'],derivation='原文参数非法分支按本交互明示请求约束细化；'+child['derivation'],source_refs=b['source_refs']+child['source_refs'])
            out.append(child)
    value['scenarios']=deduplicate(out);return value

def expand_truth(value,inputs):
    """Broad test descriptions expand against normal rules, independent of G/E."""
    from .normal_rules import normalize_scenarios
    value=normalized_scenarios(normalize_scenarios(value,inputs,truth=True),inputs['fused-ssd']);out=[];pending=[]
    for s in value['scenarios']:
        if s.get('coverage_kind')=='input_parameters' and not broad_input_branch(' '.join(r['quote'] for r in s['source_refs'])):
            s['coverage_kind']='exact';s.setdefault('quality_notes',[]).append('具体测试不是宽泛参数分支；移除错误覆盖标签，保留触发条件与测试原文')
        if s.get('coverage_kind')!='input_parameters':out.append(s);continue
        bid=s.get('original_branch_id') or s['id']
        branch={'id':bid,'description':' '.join(r['quote'] for r in s['source_refs']),'source_refs':s['source_refs']}
        parent=deepcopy(s);parent['original_branch_id']=bid
        refined=expand_inverse({'scenarios':[parent]},{**inputs,'branches':{'branches':[branch]},'bindings':{'bindings':[{'branch_id':bid,'interaction_id':s['interaction_id'],'status':'confirmed'}]}})['scenarios']
        children=[x for x in refined if x.get('coverage_kind')=='exact']
        for child in children:
            child['id']='GT-'+fingerprint([bid,child['interaction_id'],child['rule_id']])[:20]
            child['derivation']='独立测试异常描述按正常约束细化；'+child['derivation']
        out+=children
        if not children:pending.append({'interaction_id':s['interaction_id'],'object':s['object'],'concern_key':s['concern_key'],'reason':'测试描述宽泛但缺少可细化的明示参数规则，不凭G补真值','source_refs':s['source_refs']})
    value['scenarios']=deduplicate(out)
    if pending:value['pending']=pending
    return value
