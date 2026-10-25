"""Independent negative tests from positive contracts, never from G/E/results."""
from copy import deepcopy
import json,re
from .storage import fingerprint

def positive_inputs(fused,apis,rules,catalogue,definitions):
    from .inverse_alignment import canonical_fused
    fused=canonical_fused(fused)
    fused={'interactions':fused['interactions'],'rr_sr_links':[],'pending':[]}
    clean=deepcopy(rules)
    for r in clean.get('rules',[]):r.pop('violation',None)
    return {'fused-ssd':deepcopy(fused),'normal-constraints':deepcopy(apis),'normal-rules':clean,
            'test-catalogue':[{k:r[k] for k in ('id','测试名称','触发条件','关联需求')} for r in catalogue if r['scenario_type']=='exception'],'registry':definitions}

def mechanical_tests(inputs):
    """One typed constraint mutation per explicit rule, with independent steps."""
    from .interaction_enrichment import parameters_for
    from .normal_rules import conditional_constraint,descriptive_constraint
    out=[]
    suffix={'required':'completeness','type':'type','enum':'legality','minimum':'range','maximum':'range','format':'format','pattern':'format','length':'length','size':'size','other':'legality'}
    for i in inputs['fused-ssd']['interactions']:
        ps=parameters_for(i,{'api-parameters':inputs['normal-constraints']})
        for p in ps:
            constraints=[]
            if p['required'] is True:constraints.append({'kind':'required','value':True,'status':'explicit','source_refs':p['source_refs']})
            if p['data_type']:constraints.append({'kind':'type','value':p['data_type'],'status':'explicit','source_refs':p['source_refs']})
            constraints += [r for r in p['constraints'] if r['kind']!='type' and (r['status']=='explicit' or conditional_constraint(r)) and not descriptive_constraint(r)]
            for r in constraints:
                kind=r['kind'];conditional=conditional_constraint(r) if kind!='required' else False
                name=p['name'];value=json.dumps(r['value'],ensure_ascii=False,sort_keys=True)
                trigger=name+'未提供' if kind=='required' else name+'已提供；违反'+kind+'约束: '+value
                if conditional:trigger=name+'已提供；不满足原文明示的'+kind+'规则（具体标准待确认）'
                out.append({'interaction_id':i['id'],'concern_key':'api.data.'+suffix[kind],'field':name,'scope':'interface','data_location':p['location'],
                 'preconditions':['其他字段及前置业务条件满足正常要求'], 'trigger':trigger,'test_data':trigger,
                 'steps':['准备满足正常约束的'+('请求' if i['direction']=='request' else '响应'),'仅对'+name+'施加上述失败条件','执行'+i['operation']['name']+'并核查约束处理'],
                 'expected_result':'识别该字段违反明示约束；具体错误响应未在本正向依据中声明，不补造',
                 'source_refs':r['source_refs'],'executable':not conditional,'pending_details':[kind+'具体标准待确认'] if conditional else [],'failure_rule':{'kind':kind,'value':r['value']}})
        if i['direction']=='request':
            out.append({'interaction_id':i['id'],'concern_key':'service.base.availability','field':None,'scope':'service','data_location':None,
             'preconditions':['调用方及其他依赖满足本次操作前置条件'],'trigger':i['receiver']['name']+'不可用，无法执行当前操作','test_data':'使本次被调用服务不可用',
             'steps':['准备本次合法调用','使'+i['receiver']['name']+'不可用','发起'+i['operation']['name']+'并记录调用结果'],'expected_result':'本次操作无法正常完成；具体故障原因、错误码和恢复行为未声明，不补造',
             'source_refs':i['source_refs'],'executable':True,'pending_details':[]})
    from .scenario_patterns import security_rules
    # Independent positive-rule construction, not a call to G/matrix/ranking.
    for rec in security_rules(inputs):
        if not rec['supported']:continue
        i,r=rec['interaction'],rec['rule'];trigger=rec['trigger']
        out.append({'interaction_id':i['id'],'concern_key':r['concern_key'],'field':None,'scope':'relation' if r['concern_key'].startswith('service_relation.') else 'service','data_location':None,
            'preconditions':[r['condition']],'trigger':trigger,'test_data':'只违反当前已确认认证/授权条件','steps':['准备合法调用环境',trigger,'发起本次操作并核查处理'],'expected_result':'不得把违反认证/授权条件的调用作为合法成功；未明确错误码或处理方式不补造','source_refs':r['source_refs'],'executable':True,'pending_details':[],'normal_rule_id':r['id']})
    units=[]
    for t in out:
        rule=t.get('failure_rule',{});value=rule.get('value');kind=rule.get('kind');bounds=[]
        if kind in {'length','size'} and isinstance(value,dict):
            for side,aliases in [('minimum',('min','minimum','minLength','minItems','minBytes')),('maximum',('max','maximum','maxLength','maxItems','maxBytes'))]:
                values=[value[k] for k in aliases if k in value]
                if len(values)==1 and type(values[0]) in (int,float):bounds.append((side,values[0]))
        if not bounds:units.append(t);continue
        for side,number in bounds:
            child=deepcopy(t);child['failure_rule']={'kind':kind+'.'+side,'value':number};child['trigger']=t['field']+'已提供；违反'+kind+'.'+side+'约束: '+str(number);child['test_data']=child['trigger'];child['steps']=[t['steps'][0],child['trigger'],t['steps'][-1]];units.append(child)
    return {'tests':units}

def to_truth(value,inputs):
    rows={i['id']:i for i in inputs['fused-ssd']['interactions']};out=[]
    for t in value['tests']:
        i=rows[t['interaction_id']];sid='SUP-'+fingerprint(t)[:20]
        s={'id':sid,'case_id':i['case_id'],'interaction_id':i['id'],'layer':i['layer'],'object':t['field'] or i['receiver' if i['direction']=='request' else 'sender']['name'],
         'operation':i['operation']['name'],'cause':t['trigger'],'conditions':[t['trigger']],'concern_key':t['concern_key'],'field':t['field'],'rule_id':t.get('normal_rule_id'),
         'source_status':'framework_inferred','derivation':'独立测试补全：仅依据正向交互、正常约束及版本化框架；未读取G、E或比较结果。',
         'source_refs':t['source_refs'],'steps':{'normal_context':[i['sender']['name']+' → '+i['receiver']['name']+'：'+i['operation']['name']], 'trigger':t['trigger'],'documented_follow_up':[]},
         'scope':t['scope'],'data_location':t['data_location'],'source_scenario_id':sid,'original_branch_id':sid,'coverage_kind':'exact','scenario_type':'exception',
         'resolution':'explicit' if t['executable'] else 'conditional','executable':t['executable'],'pending_details':t['pending_details'],
         'quality_notes':['机器补充异常测试，自动计分；测试步骤和预期断言保存于test-supplement产物']}
        if t.get('normal_rule_id'):
            from .normal_rules import caller_concern
            if caller_concern(t['concern_key']):s['object']=i['sender']['name']
        out.append(s)
        if t.get('failure_rule'):s['failure_rule']=deepcopy(t['failure_rule'])
    return {'scenarios':list({fingerprint([s['interaction_id'],s['field'],s['data_location'],s['cause']]):s for s in out}.values()),'pending':deepcopy(value.get('pending',[]))}

def combine_truth(original,additional,decisions):
    covered={d['left_id'] for d in decisions if d['status']=='full'}
    out=deepcopy(original);out['scenarios']+= [s for s in additional['scenarios'] if s['id'] not in covered]
    out['pending']=original.get('pending',[])+additional.get('pending',[])
    out['merged_supplement_ids']=additional.get('merged_supplement_ids',[])
    out['merged_test_ids']=[{'supplement_id':d['left_id'],'original_id':d['right_id'],'reason':d['reason']} for d in decisions if d['status']=='full']
    return out

def evaluate_test_sets(d):
    from .exception_comparison import compare_report
    original=compare_report(d['exception-generate']['scenarios'],d['existing-extract']['scenarios'],d['test-ground-truth']['scenarios'],d['gap-compare']['decisions'],d['GT_G']['decisions'],d['GT_E']['decisions'])
    original['formula_notes']['GT']='原始异常测试经机器整理（含单列框架推导）；非全部人工确认'
    original['test_set']='original';original['test_set_hash']=fingerprint(d['test-ground-truth'])
    if 'test-expanded' not in d:return original
    expanded=compare_report(d['exception-generate']['scenarios'],d['existing-extract']['scenarios'],d['test-expanded']['scenarios'],d['gap-compare']['decisions'],d['GT_expanded_G']['decisions'],d['GT_expanded_E']['decisions'])
    expanded['formula_notes']['GT']='原始异常测试＋独立机器补充，自动GT计分；非全部人工确认'
    expanded.update(test_set='expanded',test_set_hash=fingerprint(d['test-expanded']),original_evaluation=original,
      test_set_notes='机器补充基于独立正向材料自动计分；集合扩充不等于生成质量提升',merged_test_ids=d['test-expanded'].get('merged_test_ids',[]))
    return expanded


def deduplicate_truth(value,decisions):
    """Merge only full same-failure cliques; do not take transitive guesses."""
    full={frozenset((d['left_id'],d['right_id'])):d['reason'] for d in decisions if d['status']=='full'}
    groups=[]
    for item in value['scenarios']:
        group=next((g for g in groups if all(frozenset((item['id'],s['id'])) in full for s in g)),None)
        if group is None:groups.append([item])
        else:group.append(item)
    out=deepcopy(value);out['scenarios']=[];out['merged_supplement_ids']=[]
    for group in groups:
        keeper=deepcopy(group[0]);out['scenarios'].append(keeper)
        for duplicate in group[1:]:
            out['merged_supplement_ids'].append({'retained_id':keeper['id'],'duplicate_id':duplicate['id'],'reason':full[frozenset((keeper['id'],duplicate['id']))]})
    return out

def dedup_candidates(value):
    # Data rules and availability are already canonical tools; only business
    # paraphrases require semantic comparison, within their actual interaction.
    return [s for s in value['scenarios'] if not s.get('failure_rule') and s['concern_key']!='service.base.availability']


def quarantine_invalid_tests(value,inputs):
    """After bounded repair, rejected candidates remain reviewable, never GT."""
    from .validation import validate_result
    out={'tests':[],'pending':deepcopy(value.get('pending',[]))}
    for pending in out['pending']:
        pending.setdefault('object','待确认');pending.setdefault('concern_key','pending.unclassified')
    for t in value.get('tests',[]):
        try:validate_result('test-supplement',{'tests':[t]},inputs)
        except (ValueError,KeyError,TypeError) as e:
            rule=next((r for r in inputs['normal-rules']['rules'] if r['id']==t.get('normal_rule_id')),None)
            refs=(rule or {}).get('source_refs') or [r for i in inputs['fused-ssd']['interactions'] for r in i['source_refs']]
            iid=(rule or {}).get('interaction_id') or inputs['fused-ssd']['interactions'][0]['id']
            out['pending'].append({'interaction_id':iid,'object':t.get('field') or next(i['receiver']['name'] for i in inputs['fused-ssd']['interactions'] if i['id']==iid),'concern_key':(rule or {}).get('concern_key') or t.get('concern_key') or 'pending.unclassified','reason':'补充测试经有界修复仍未通过，不计GT：'+str(e)+'；原候选：'+str(t.get('trigger','')),'source_refs':refs})
        else:out['tests'].append(deepcopy(t))
    return out
