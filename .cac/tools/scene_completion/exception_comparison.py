from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .exception_generation import deduplicate
from .assignment import full_assignment
def broad_covers(left,right):
    return (right.get('coverage_kind')=='input_parameters' and right.get('original_branch_id')
      and left['case_id']==right['case_id'] and left['interaction_id']==right['interaction_id']
      and left.get('scope','interface')=='interface' and bool(left.get('field'))
      and left.get('data_location') in {'header','path','query','body','business'}
      and left['concern_key'].startswith('api.data.'))

def coverage_assignment(decisions,left,right):
    lids={s['id'] for s in left};rids={s['id'] for s in right}
    broad=[{'checker_scenario_id':a['id'],'generated_scenario_id':b['id'],'status':'full','coverage':'input_parameters'} for a in left for b in right if broad_covers(a,b)]
    covered={p['checker_scenario_id'] for p in broad}
    exact=full_assignment(decisions,lids-covered,{s['id'] for s in right if s.get('coverage_kind')!='input_parameters'})
    return exact+broad

def compare_report(g,e,gt,eg,tg,te):
    """Only complete pairs score. Reassign after restricting to missing truth/G."""
    g,e,gt=map(deduplicate,(g,e,gt))
    # Semantic duplicate edges to one target cannot score twice (one-to-one).
    gids,eids,tids=({s['id'] for s in xs} for xs in (g,e,gt))
    covered_g={p['checker_scenario_id'] for p in coverage_assignment(eg,g,e)}
    m=[s for s in g if s['id'] not in covered_g]
    existing_t={p['checker_scenario_id'] for p in coverage_assignment(te,gt,e)}
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
      'generation_breakdown':{kind:{'count':sum(s.get('resolution','explicit')==kind for s in g),'matched':sum(next(s for s in g if s['id']==p['generated_scenario_id']).get('resolution','explicit')==kind for p in valid)} for kind in ('explicit','conditional')},
      'truth_breakdown':breakdown,'full_matches':{'G_E':coverage_assignment(eg,g,e),'GT_G':valid,'GT_E':coverage_assignment(te,gt,e)},
      'partial_diagnostics':[d for ds in (eg,tg,te) for d in ds if d['status']=='partial'],
      'recommendation':{'enabled':False,'status':'未启用'},'formula_notes':{
       'GT':'人工测试真值（含单列的框架推导项）','G':'生成异常集合','E':'文档已有异常集合','M':'G减去被E覆盖的细项（宽泛输入参数分支可覆盖同交互多项）',
       'miss_rate':'(1-|M∩(GT-E)|/|GT-E|)×100%','validity':'|G∩GT|/|G|×100%','empty_denominator':'不适用'}}



def missing_report(g,e,decisions):
    g,e=map(deduplicate,(g,e));pairs=coverage_assignment(decisions,g,e)
    covered={p['checker_scenario_id'] for p in pairs}
    return {'protocol':PROTOCOL,'G':g,'E':e,'M':[s for s in g if s['id'] not in covered],
            'full_matches':pairs,'partial_diagnostics':[d for d in decisions if d['status']=='partial'],
            'decisions':decisions,'recommendation':{'enabled':False,'status':'未启用'}}
