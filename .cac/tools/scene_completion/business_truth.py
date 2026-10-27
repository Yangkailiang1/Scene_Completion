"""Derived human-review GT. Frozen independent GT and M/Q are never edited."""
from copy import deepcopy
from pathlib import Path
import re
from .storage import fingerprint, read_json, write_json


def signature(s):
    clean=lambda text:re.sub(r'\s+', '', str(text)).casefold()
    return (s.get('canonical_interaction_id',s.get('interaction_id')),tuple(sorted(s.get('concern_binding_ids',[]))),
            s.get('data_location'),s.get('field'),tuple(sorted(clean(x) for x in s.get('conditions',[]))))


def candidates(s, truth):
    """Only propose potential duplicates; never decide semantic equality."""
    anchors=set(s.get('concern_binding_ids',[]));patterns=set(s.get('linked_pattern_ids',[s.get('pattern_id')]))-{None}
    return [t for t in truth if anchors and anchors & set(t.get('concern_binding_ids',[]))
            and patterns & (set(t.get('linked_pattern_ids',[t.get('pattern_id')]))-{None})]


def snapshot(project, case):
    from .result_views import ResultView
    from .pattern_settings import history
    from .concern_alignment import compare
    from .assignment import full_assignment
    from .recommendation import evaluate
    view=ResultView(project);base=view.payload(case+':exception-evaluation');q=view.payload(case+':gap-recommend')
    if 'GT' not in base: return {'status':'未评测','reason':'冻结扩展GT尚未完成','evaluation':base,'added':[],'pending_duplicates':[]}
    records=history(project);latest={}
    for r in records['feedback']:
        if r.get('case_id')==case and r.get('run_id')==q.get('run_id'):latest[r['scenario_id']]=r
    version=fingerprint({'version':'business-gt-v1','base':base,'Q':q,'feedback':latest})
    cache=Path(project)/'business_truth_versions'/(version+'.json')
    if cache.exists():return read_json(cache)
    result=deepcopy(base);truth=result['GT'];byid={s['id']:s for s in truth};generated={s['id']:s for s in result.get('G',[])}
    qids={s['id'] for s in q.get('Q',[])}
    pairs=deepcopy(result.get('full_candidate_pairs_GT_G',[{'left_id':p['checker_scenario_id'],'right_id':p['generated_scenario_id'],'status':'full','reason':'冻结完整匹配'} for p in result.get('full_matches',{}).get('GT_G',[])]))
    added=[];confirmations=[];pending=[]
    for gid,r in sorted(latest.items()):
        if r['decision']!='adopt' or gid not in qids or gid not in generated:continue
        s=generated[gid]
        known=next((p['checker_scenario_id'] for p in base.get('full_matches',{}).get('GT_G',[]) if p['generated_scenario_id']==gid),None)
        exact=next((t['id'] for t in truth if signature(t)==signature(s)),None)
        target=known or exact
        resolution=r.get('truth_resolution') or {}
        if resolution.get('choice')=='link':
            if resolution.get('truth_id') not in {t['id'] for t in candidates(s,truth)}:raise ValueError('人工关联GT不在同定位候选中')
            target=resolution['truth_id']
        possible=candidates(s,truth)
        if not target and possible and resolution.get('choice')!='new':
            pending.append({'scenario_id':gid,'candidate_ids':[t['id'] for t in possible],'reason':'疑似与现有GT重复，请确认关联或新增独立失败'});continue
        if not target:
            target='business-GT-'+fingerprint([case,gid,q.get('run_id')])[:20]
            new=deepcopy(s);new.update(id=target,source_status='explicit',truth_source='business_review',reviewer=r.get('reviewer'),review_id=r['id'],generated_source_id=gid)
            truth.append(new);byid[target]=new;added.append(new)
        pairs.append({'left_id':target,'right_id':gid,'status':'full','reason':'业务明确采纳并确认同一失败','source':'business_review','review_id':r['id']})
        confirmations.append({'scenario_id':gid,'truth_id':target,'review_id':r['id'],'reviewer':r.get('reviewer')})
    result['full_candidate_pairs_GT_G']=pairs
    result.setdefault('full_matches',{})['GT_G']=full_assignment(pairs,set(byid),set(generated))
    concern=deepcopy(base.get('concern_level') or view.payload(case+':concern-evaluation'))
    if concern:
        cg={x['binding_id']:x for x in concern.get('G_c',[])};ct={x['binding_id']:x for x in concern.get('GT_c',[])}
        for a in confirmations:
            for bid in generated[a['scenario_id']].get('concern_binding_ids',[]):
                if bid in cg and bid not in ct:ct[bid]={**deepcopy(cg[bid]),'truth_source':'business_review','review_id':a['review_id']}
        concern=compare({'matches':concern.get('G_c',[])},{'matches':concern.get('E_c',[])},{'matches':list(ct.values())})
        result['concern_level']=concern;result['metrics']={**result.get('metrics',{}),**concern['metrics']}
    result=evaluate(result,q)
    out={'status':'已评测（有重复归属待确认）' if pending else '已评测','version':version,'baseline':'冻结扩展测试GT＋人工确认增补',
         'base_fingerprint':fingerprint(base),'run_id':q.get('run_id'),'evaluation':result,'added':added,'confirmations':confirmations,'pending_duplicates':pending,
         'note':'业务采纳改变GT，不表示生成模型质量提升；原始/扩展GT和本轮G/E/M/Q保持冻结。','llm_called':False}
    write_json(cache,out)
    return out
