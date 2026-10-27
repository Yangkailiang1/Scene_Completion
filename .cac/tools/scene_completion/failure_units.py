"""Conservative inverse-unit repairs using only own evidence and positive SSD."""
from copy import deepcopy
import re
from .storage import fingerprint

MODEL_METADATA_FIELDS=('concern_origins','concern_paths','canonical_interaction_id','interaction_type','normalization_origin','source_scenario_id','source_unit_ids','quality_notes','failure_rule','pattern_id','linked_pattern_ids','confidence','risk','scenario_context','pattern_versions','predicate')


def clean_model_scenarios(value):
    result=deepcopy(value)
    for s in result.get('scenarios',[]):
        for key in MODEL_METADATA_FIELDS:s.pop(key,None)
    return result


def source_tests(s):
    from .test_sources import test_ids
    explicit={(r['source_id'],m) for r in s['source_refs'] for m in test_ids(r['quote'])}
    return tuple(sorted(explicit or {(r['source_id'],'line:'+str(r['line_start'])+':'+str(r['line_end'])) for r in s['source_refs']}))


def normalize_test_assertions(value, inputs):
    """Keep a test's failure trigger separate from its expected handling.

    Only explicit Markdown test rows and the positive SSD are consulted. A
    response/recovery fault explicitly injected by the test remains a failure.
    No G, E, coverage decision or response code is used to invent a trigger.
    """
    out=deepcopy(value);rows=inputs.get('fused-ssd',{}).get('interactions',[])
    by_id={i['id']:i for i in rows};groups={}
    from .test_sources import records,records_for_inputs
    test_docs=inputs.get('test-documents',[])
    if not test_docs:
        # Legacy tool callers supply only the already retained nine-column
        # test citation. The parser applies the same exact type-column rule.
        test_docs=[{'source_id':r['source_id'],'name':'retained-test-citation','channel':'test','lines':[{'number':r['line_start'],'text':r['quote']}]} for s in out.get('scenarios',[]) for r in s.get('source_refs',[])]
    typed={}
    for r in records_for_inputs(inputs) if inputs.get('test-documents') else records(test_docs):typed.setdefault((r['source_id'],r['id']),r)
    by_location={(r['source_id'],r['row']):r for r in typed.values()}
    for s in out.get('scenarios',[]):
        for ref in s.get('source_refs',[]):
            record=by_location.get((ref['source_id'],ref['line_start']))
            if record:
                groups.setdefault((ref['source_id'],record['id']),{'record':record,'ref':ref,'units':[]})['units'].append(s)
                break
    removed=set()
    for group in groups.values():
        record=group['record']
        trigger=record['触发条件'];expected=record['预期结果'];precondition=record['前置条件'];units=group['units']
        # A test may deliberately corrupt the response or recovery itself.
        if re.search(r'返回|响应|回滚|恢复|重试|补偿',trigger):continue
        assertions=[]
        for s in units:
            i=by_id.get(s['interaction_id'],{})
            if i.get('direction')!='return' or not re.search(r'返回|响应|提示|状态更新|重试|恢复|回滚',s['cause']):continue
            assertions.append(s)
        primary=[s for s in units if s not in assertions]
        for s in assertions:
            follow={'action':expected,'source_refs':[group['ref']]}
            if primary:
                for target in primary:
                    steps=target.setdefault('steps',{});followups=steps.setdefault('documented_follow_up',[])
                    if fingerprint(follow) not in {fingerprint(x) for x in followups}:followups.append(follow)
                    target['source_unit_ids']=list(dict.fromkeys(target.get('source_unit_ids',[target['id']])+[s['id']]))
                    target.setdefault('quality_notes',[]).append('handling_assertion：同一测试的预期返回/恢复是原失败的处理断言，不单独计为GT；原始单位'+s['id'])
                removed.add(s['id'])
            else:
                # The model emitted only the expected handling. Recover the
                # already explicit trigger only if it names one actual call.
                targets={i['id']:i for i in rows if i.get('direction')=='request' and i['receiver']['name'] in trigger}
                if len(targets)!=1 or not re.search(r'失败|超时|不可用|不存在|错误',trigger):continue
                target=next(iter(targets.values()))
                s.setdefault('normalization_origin',{'interaction_id':s['interaction_id'],'object':s['object'],'field':s.get('field'),'data_location':s.get('data_location')})
                s.update(cause=trigger,conditions=[precondition,trigger],interaction_id=target['id'],canonical_interaction_id=target['id'],layer=target['layer'],operation=target['operation']['name'],object=target['receiver']['name'],field=None,data_location=None,scope='service')
                s['steps']={'normal_context':[target['sender']['name']+' → '+target['receiver']['name']+'：'+target['operation']['name']],'trigger':trigger,'documented_follow_up':[follow]}
                s.setdefault('quality_notes',[]).append('handling_assertion：采用测试动作栏明示的失败原因，绑定唯一实际调用；预期恢复仅作处理断言。保留原关注点分类供分类核查，不因分类决定失败匹配')
    out['scenarios']=[s for s in out.get('scenarios',[]) if s['id'] not in removed]
    return out



def failed_requests(text,rows):
    requests=[i for i in rows if i.get('direction')=='request']
    explicit=[i for i in requests if re.search(re.escape(i['receiver']['name'])+r'\s*(?:也|同时)?\s*(?:(?:查询|调用|读取|写入|访问|处理|支付)\s*)?(?:发生)?(?:同步失败|连接失败|不可用|超时|unavailable|timeout)',text,re.I)]
    # Handling may mention a second service. It is not a second failed callee.
    return {i['id']:i for i in (explicit or [i for i in requests if i['receiver']['name'] in text])}

def normalize_bindings(value,inputs):
    out=deepcopy(value);branches={b['id']:b for b in inputs.get('branches',{}).get('branches',[])}
    rows=inputs.get('fused-ssd',{}).get('interactions',[])
    for b in out.get('bindings',[]):
        branch=branches.get(b['branch_id'],{})
        # A model summary may retain only the propagated HTTP response. The
        # branch's own cited line still names the failed callee; do not lose it.
        text=' '.join([branch.get('description',''),branch.get('case_hint','')]+[r.get('quote','') for r in branch.get('source_refs',[])])
        if b['status']!='confirmed' or not re.search(r'超时|timeout|不可用|unavailable|连接失败|同步失败',text,re.I):continue
        requests=failed_requests(text,rows)
        if len(requests)==1:
            iid=next(iter(requests))
            if b['interaction_id']!=iid:b['interaction_id']=iid;b['basis']+='；根据原分支明示的故障服务与本用例唯一实际请求统一失败位置，传播步骤另保留'
    return out


def normalize_inverse_units(value, inputs):
    out=deepcopy(value);rows=inputs.get('fused-ssd',{}).get('interactions',[]);by_id={i['id']:i for i in rows}
    for s in out.get('scenarios',[]):
        s.setdefault('source_unit_ids',[s['id']]);s.setdefault('quality_notes',[])
        current=by_id.get(s['interaction_id'])
        # A named callee's transport failure belongs to its actual request,
        # not a later HTTP response propagated by a different service.
        if not current or s.get('field') or not re.search(r'超时|timeout|不可用|unavailable|连接失败|同步失败',s['cause'],re.I):continue
        unique=failed_requests(s['cause'],rows)
        if len(unique)!=1:continue
        target=next(iter(unique.values()))
        if current['id']==target['id']:continue
        s.setdefault('normalization_origin',{'interaction_id':s['interaction_id'],'object':s['object'],'field':s.get('field'),'data_location':s.get('data_location')})
        s.update(interaction_id=target['id'],canonical_interaction_id=target['id'],layer=target['layer'],operation=target['operation']['name'],object=target['receiver']['name'],data_location=None,scope='service')
        s['quality_notes'].append('failure_owner：异常明示的被调用服务在本用例只有一个实际请求；从传播步骤定位到该请求，未新增交互或异常原因')
        s['steps']['normal_context']=[target['sender']['name']+' → '+target['receiver']['name']+'：'+target['operation']['name']]
    result={}
    for s in out.get('scenarios',[]):
        # Only a same-test, same-location duplicate with an identical failure
        # statement after removing a tautological suffix is collapsed. Other
        # near-synonyms remain the model's responsibility, not a fuzzy merge.
        cause=re.sub(r'导致(?:格式)?校验失败[。.]?$','',s['cause']).strip(' ，。')
        tests=source_tests(s)
        key=(tests,s['interaction_id'],s.get('field'),s.get('data_location'),s['object'],s['operation'],cause,s['concern_key']) if tests else ('unique',s['id'])
        if key not in result:result[key]=s;continue
        old=result[key]
        for k in ('source_refs','source_unit_ids','quality_notes'):
            old[k]=list({fingerprint(v):v for v in old.get(k,[])+s.get(k,[])}.values())
        old['quality_notes'].append('duplicate_gt：同一测试来源、同一具体交互与失败条件的重复表达合并；原始ID均保留')
    out['scenarios']=list(result.values());return out
