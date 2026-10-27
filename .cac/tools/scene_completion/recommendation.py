"""Deterministic, project-local ranking. GT is accepted only by evaluate()."""
from copy import deepcopy
from .storage import fingerprint
from .scenario_patterns import normalize_settings,risk_for,RISK_VALUES

FEATURES=('functional_types','technologies','actual_operation','boundary','direction','timeliness')

def similarity(a,b):
    values=[]
    for key in FEATURES:
        x,y=a.get(key),b.get(key)
        if x in (None,[], '') or y in (None,[], ''):continue
        if key=='functional_types':
            aliases={'read':'query_retrieval','display':'display_interaction','create':'resource_mutation','update':'resource_mutation','delete':'resource_mutation','process':'analysis_generation','publish':'release_activation'}
            x=[aliases.get(v,v) for v in x] if isinstance(x,list) else x;y=[aliases.get(v,v) for v in y] if isinstance(y,list) else y
        if isinstance(x,list) and isinstance(y,list):values.append(len(set(x)&set(y))/len(set(x)|set(y)))
        else:values.append(float(x==y))
    return sum(values)/len(values) if values else 0.

def historical_score(s,history,case_id,run_id,library_version=None):
    numerator=1.;denominator=2.;proof=[]
    for row in history:
        if row.get('source_channel') in {'test_gt','automatic_gt','machine_unreviewed'} or not row.get('human_reviewed') or row.get('decision') not in {'adopt','not_needed'}:continue
        if row.get('run_id')==run_id:continue
        if library_version and row.get('library_version')!=library_version:continue
        if row['pattern_id'] not in s.get('linked_pattern_ids',[s['pattern_id']]):continue
        if library_version and row.get('pattern_hash')!=s.get('pattern_versions',{}).get(row['pattern_id']):continue
        weight=similarity(s.get('scenario_context',{}),row['context'])
        if not weight:continue
        numerator+=weight*(row['decision']=='adopt');denominator+=weight;proof.append({'history_id':row['id'],'similarity':weight,'decision':row['decision']})
    return numerator/denominator,proof

def rank(missing,matrix,settings=None,history=None,*,case_id='',run_id=''):
    settings=normalize_settings(settings);history=deepcopy(history or []);patterns={p['id']:p for p in settings['library']['patterns'] if p['enabled']};ranked=[]
    for original in missing:
        if original.get('scenario_type','exception')!='exception' or 'pattern_id' not in original:continue
        s=deepcopy(original);pattern=patterns.get(s['pattern_id'])
        if pattern is None or s['confidence']['score']<settings['threshold']:continue
        s['risk']=max((risk_for(patterns[k],settings) for k in s.get('linked_pattern_ids',[s['pattern_id']]) if k in patterns),key=lambda r:r['score']);h,proof=historical_score(s,history,case_id,run_id,settings['library']['version'])
        score=settings['risk_weight']*s['risk']['score']+settings['history_weight']*h
        ranked.append({'scenario_id':s['id'],'pattern_id':s['pattern_id'],'priority':score,'risk':s['risk'],'confidence':s['confidence'],'history_score':h,'history_sources':proof,'mandatory':s['risk']['level']=='critical','scenario':s})
    # Diversity only breaks exact score ties, never displaces a higher score.
    result=[];seen=set()
    while ranked:
        best=max(r['priority'] for r in ranked);tied=[r for r in ranked if r['priority']==best]
        r=min(tied,key=lambda r:(r['pattern_id'] in seen,r['scenario_id']));result.append(r);seen.add(r['pattern_id']);ranked.remove(r)
    critical=[r for r in result if r['mandatory']];ordinary=[r for r in result if not r['mandatory']];selected=critical+ordinary[:max(0,settings['top_k']-len(critical))]
    chosen={r['scenario_id'] for r in selected}
    for n,r in enumerate(result,1):r.update(rank=n,selected=r['scenario_id'] in chosen,reason='关键风险保底' if r['mandatory'] else '风险与已审核历史加权排序')
    review=[]
    for item in matrix.get('instances',[]):
        if item['status']!='pending':continue
        s=deepcopy(item['scenario']);p=patterns.get(s['pattern_id'])
        if p:
            s['risk']=risk_for(p,settings)
            if s['risk']['level']=='critical':review.append({'candidate_id':item['id'],'scenario':s,'reason':'关键风险但证据不足；确认前不进入G或Q'})
    review += [{'candidate_id':'gap-'+fingerprint(issue)[:24],'issue':issue,'reason':'关注点/模式定义缺项，需业务审核，不自动新增'} for issue in matrix.get('issues',[])]
    return {'enabled':True,'status':'已推荐','Q':[r['scenario'] for r in selected],'ranked':result,'critical_review':review,'top_k':settings['top_k'],'critical_overflow':max(0,len(critical)-settings['top_k']),'settings_hash':settings['hash'],'history_hash':fingerprint(history),'history_scope':'project_human_reviewed_before_run','case_id':case_id,'run_id':run_id,'formula':f"priority={settings['risk_weight']}R+{settings['history_weight']}H",'library_version':settings['library']['version'],'human_adoption':{'value':None,'status':'待审核'}}

def evaluate(report,recommendation):
    from .assignment import full_assignment
    from .exception_comparison import coverage_assignment
    out=deepcopy(report)
    if not {'GT','M','full_matches'}<=set(report):
        out['recommendation_comparison']={'status':'未评测','unit':'独立异常场景'}
        return out
    truth={s['id'] for s in report['GT'] if s.get('scenario_type','exception')=='exception'}
    pairs=report.get('full_candidate_pairs_GT_G',[{'left_id':p['checker_scenario_id'],'right_id':p['generated_scenario_id'],'status':'full','reason':'已保存完整失败对应'} for p in report['full_matches']['GT_G']])
    rate=lambda n,d:{'value':100*n/d if d else None,'numerator':n,'denominator':d,'status':'适用' if d else '不适用'}
    def snapshot(ids):
        hits=full_assignment(pairs,truth,ids)
        return {'candidate_count':len(ids),'gt_count':len(truth),'matched':len(hits),'metrics':{'recommendation_adoption':rate(len(hits),len(ids)),'recommendation_false_positive':rate(len(ids)-len(hits),len(truth))}}
    mids={s['id'] for s in report.get('M',[]) if s.get('scenario_type','exception')=='exception'}
    out['recommendation_comparison']={'baseline':{'set':'M','label':'推荐前：全部缺失场景',**snapshot(mids)},'recommended':{'set':'Q','status':'未启用'},'unit':'独立异常场景','basis':'同一冻结GT与已保存完整匹配；推荐排序不读取GT'}
    if not recommendation.get('enabled'):return out
    ids={s['id'] for s in recommendation['Q']};hits=full_assignment(pairs,truth,ids)
    if not ids<=mids:raise ValueError('推荐结果Q必须是缺失场景M的子集')
    out['recommendation_comparison']['recommended']={'set':'Q','label':'推荐后：算法筛选场景',**snapshot(ids)}
    out['metrics']['recommendation_adoption']=rate(len(hits),len(ids));out['metrics']['recommendation_false_positive']=rate(len(ids)-len(hits),len(truth))
    covered={p['checker_scenario_id'] for p in report['full_matches']['GT_E']};critical={s['id'] for s in report['GT'] if s.get('risk',{}).get('level')=='critical'}-covered
    out['metrics']['critical_missing_recall']=rate(len(full_assignment(pairs,critical,ids)),len(critical))
    out['recommendation']={k:v for k,v in recommendation.items() if k not in {'ranked','critical_review'}};out['full_matches']['GT_Q']=hits
    out.setdefault('formula_notes',{}).update(recommendation_adoption='|Q∩GT|/|Q|×100%；GT命中率，不等于人工采纳率',recommendation_false_positive='|Q−GT|/|GT|×100%；分母为GT，可能超过100%',critical_missing_recall='|Q∩关键(GT−E)|/|关键(GT−E)|×100%')
    return out


def comparison_for_view(report,recommendation):
    """Read saved results without merging incompatible historical snapshots."""
    saved=report.get('recommendation_comparison')
    if saved:return deepcopy(saved)
    try:return evaluate(report,recommendation).get('recommendation_comparison')
    except ValueError as error:
        value=evaluate(report,{'enabled':False})['recommendation_comparison']
        value['recommended']={'set':'Q','status':'版本不一致，待重算','reason':str(error)}
        return value


def aggregate_comparison(comparisons):
    out={'unit':'独立异常场景','basis':'按用例合并分子分母；推荐前取完整M，推荐后取Q'}
    for side in ('baseline','recommended'):
        rows=[c[side] for c in comparisons if c and c.get(side,{}).get('metrics')]
        value={'set':'M' if side=='baseline' else 'Q','label':'推荐前：全部缺失场景' if side=='baseline' else '推荐后：算法筛选场景','evaluated_cases':len(rows),'metrics':{}}
        for key in ('candidate_count','gt_count','matched'):value[key]=sum(r[key] for r in rows)
        for metric in ('recommendation_adoption','recommendation_false_positive'):
            items=[r['metrics'][metric] for r in rows];n=sum(v['numerator'] for v in items);d=sum(v['denominator'] for v in items)
            value['metrics'][metric]={'value':100*n/d if d else None,'numerator':n,'denominator':d,'status':'适用' if d else '不适用' if rows else '未评测'}
        out[side]=value
    return out
