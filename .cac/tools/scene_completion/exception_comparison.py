from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .exception_generation import deduplicate
from .assignment import full_assignment
def compare_report(g,e,gt,eg,tg,te):
    """Only complete pairs score. Reassign after restricting to missing truth/G."""
    g,e,gt=map(deduplicate,(g,e,gt))
    # Semantic duplicate edges to one target cannot score twice (one-to-one).
    gids,eids,tids=({s['id'] for s in xs} for xs in (g,e,gt))
    covered_g={p['checker_scenario_id'] for p in full_assignment(eg,gids,eids)}
    m=[s for s in g if s['id'] not in covered_g]
    existing_t={p['checker_scenario_id'] for p in full_assignment(te,tids,eids)}
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
      'truth_breakdown':breakdown,'full_matches':{'G_E':full_assignment(eg,gids,eids),'GT_G':valid,'GT_E':full_assignment(te,tids,eids)},
      'partial_diagnostics':[d for ds in (eg,tg,te) for d in ds if d['status']=='partial'],
      'recommendation':{'enabled':False,'status':'未启用'},'formula_notes':{
       'GT':'人工测试真值（含单列的框架推导项）','G':'生成异常集合','E':'文档已有异常集合','M':'G减去与E完整对应的项',
       'miss_rate':'(1-|M∩(GT-E)|/|GT-E|)×100%','validity':'|G∩GT|/|G|×100%','empty_denominator':'不适用'}}



def missing_report(g,e,decisions):
    g,e=map(deduplicate,(g,e));pairs=full_assignment(decisions,{s['id'] for s in g},{s['id'] for s in e})
    covered={p['checker_scenario_id'] for p in pairs}
    return {'protocol':PROTOCOL,'G':g,'E':e,'M':[s for s in g if s['id'] not in covered],
            'full_matches':pairs,'partial_diagnostics':[d for d in decisions if d['status']=='partial'],
            'decisions':decisions,'recommendation':{'enabled':False,'status':'未启用'}}
