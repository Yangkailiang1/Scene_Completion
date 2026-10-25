"""Display saved pairwise decisions as rows, without making new matches."""
from collections import Counter
from .storage import fingerprint


def align_rows(channels, pairs, decisions=None):
    decisions=decisions or {}
    ids={k:{s['id']:s for s in v} for k,v in channels.items()}
    edges={k:{(p['checker_scenario_id'],p['generated_scenario_id']) for p in pairs.get(k,[])} for k in ('G_E','GT_G','GT_E')}
    used={k:set() for k in ids};rows=[]
    def add(g=None,t=None,es=()):
        es=sorted(es);items={'G':[g] if g else [],'GT':[t] if t else [],'E':es}
        evidence=[]
        for purpose,options in [('G_E',[(g,e) for e in es] if g else []),('GT_G',[(t,g)] if t and g else []),('GT_E',[(t,e) for e in es] if t else [])]:
            for a,b in options:
                d=next((d for d in decisions.get(purpose,[]) if (d['left_id'],d['right_id'])==(a,b)),None)
                evidence.append({'purpose':purpose,'left_id':a,'right_id':b,'status':'full' if (a,b) in edges[purpose] else (d or {}).get('status','not_compared'),'reason':(d or {}).get('reason','已保存的完整对应' if (a,b) in edges[purpose] else '没有已保存的完整对应')})
        all_three=bool(g and t and es)
        status='triple' if all_three and all((t,e) in edges['GT_E'] for e in es) else 'conflict' if all_three else 'pair' if sum(bool(v) for v in items.values())==2 else 'single'
        anchor=(ids['G'].get(g) or ids['GT'].get(t) or ids['E'][es[0]])
        rows.append({'id':fingerprint(items)[:20],'status':status,'anchor':anchor,'cells':{k:[ids[k][i] for i in values] for k,values in items.items()},'matching':evidence,
                     'classification_difference':len({ids[k][i].get('concern_key') for k,values in items.items() for i in values if not(k=='E' and ids[k][i].get('coverage_kind')=='input_parameters')})>1})
        for k,v in items.items():used[k].update(v)
    for g in ids['G']:
        ts=[t for t,gg in sorted(edges['GT_G']) if gg==g and t in ids['GT']]
        es=[e for gg,e in sorted(edges['G_E']) if gg==g and e in ids['E']]
        add(g,ts[0] if ts else None,es)
    for t in ids['GT']:
        if t not in used['GT']:add(t=t,es=[e for tt,e in sorted(edges['GT_E']) if tt==t and e in ids['E']])
    for e in ids['E']:
        if e not in used['E']:add(es=[e])
    counts=Counter(s['id'] for row in rows for s in row['cells']['E'])
    for row in rows:row['shared_e_ids']=[s['id'] for s in row['cells']['E'] if counts[s['id']]>1]
    for row in rows:
        # Saved near-candidate decisions explain omissions; they are never
        # promoted into row membership or scoring edges.
        gs={s['id'] for s in row['cells']['G']};ts={s['id'] for s in row['cells']['GT']}
        if bool(gs)!=bool(ts):
            candidates=[d for d in decisions.get('GT_G',[]) if (d['left_id'] in ts and d['right_id'] in ids['G'] or d['right_id'] in gs and d['left_id'] in ids['GT']) and d['status']!='full']
            candidates.sort(key=lambda d:(d['status']!='partial',d['left_id'],d['right_id']))
            row['matching'] += [{'purpose':'GT_G','candidate_only':True,**d} for d in candidates[:3]]
        row['diagnostics']=(['关注点分类差异'] if row['classification_difference'] else [])+(['GT未验证'] if gs and not ts else [])+(['需核对生成及正向依据'] if ts and not gs else [])
        broad={};cells=[]
        for s in row['cells']['E']:
            branch=s.get('original_branch_id')
            if s.get('coverage_kind')=='input_parameters' and branch:
                if branch in broad:
                    broad[branch].setdefault('covered_variant_ids',[broad[branch]['id']]).append(s['id']);continue
                s=dict(s,coverage_description='原文输入参数非法分支，覆盖当前交互中有依据的输入参数约束');broad[branch]=s
            cells.append(s)
        row['cells']['E']=cells
        if any(len(s.get('source_unit_ids',[]))>1 for values in row['cells'].values() for s in values):row['diagnostics'].append('重复来源已合并')
    priority={'triple':0,'pair':1,'conflict':2,'single':3}
    return sorted(rows,key=lambda r:(priority[r['status']],r['id']))


def aggregate_metrics(cases):
    out={}
    for key in ('missing_exception_miss_rate','generation_validity'):
        available=[r['metrics'][key] for r in cases if r.get('metrics',{}).get(key,{}).get('status')=='适用']
        n=sum(v['numerator'] for v in available);d=sum(v['denominator'] for v in available)
        out[key]={'value':100*n/d if d else None,'numerator':n,'denominator':d,'status':'适用' if d else '不适用' if any(r.get('metrics',{}).get(key) for r in cases) else '未评测'}
    return out
