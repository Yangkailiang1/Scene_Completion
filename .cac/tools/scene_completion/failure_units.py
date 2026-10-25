"""Conservative inverse-unit repairs using only own evidence and positive SSD."""
from copy import deepcopy
import re
from .storage import fingerprint


def source_tests(s):
    return tuple(sorted({(r['source_id'],m) for r in s['source_refs'] for m in re.findall(r'\bTEST[-_][A-Za-z0-9_-]+',r['quote'])}))


def normalize_bindings(value,inputs):
    out=deepcopy(value);branches={b['id']:b for b in inputs.get('branches',{}).get('branches',[])}
    rows=inputs.get('fused-ssd',{}).get('interactions',[])
    for b in out.get('bindings',[]):
        branch=branches.get(b['branch_id'],{});text=branch.get('description','')
        if b['status']!='confirmed' or not re.search(r'超时|timeout|不可用|unavailable|连接失败|同步失败',text,re.I):continue
        requests={i['id']:i for i in rows if i.get('direction')=='request' and i['receiver']['name'] in text}
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
        named=[i for i in rows if i.get('direction')=='request' and i['receiver']['name'] in s['cause']]
        unique={i['id']:i for i in named}
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
