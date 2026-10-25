"""Exception-only evaluation eligibility; exclusions remain auditable."""
from copy import deepcopy
import re
from .test_sources import records
PROCESSOR_VERSION='exception-only-post-response-v1'

def filter_branches(value):
    out=deepcopy(value);kept=[];excluded=out.setdefault('excluded',[])
    for b in out['branches']:
        kind=b.get('scenario_type','exception');text=b['description'];reason='独立原文分支类型判断'
        normal_cancel=re.search(r'(?:顾客|用户|商家)(?:主动)?取消支付',text) and not re.search(r'取消.*(?:失败|错误|拒绝)',text)
        normal_empty=re.search(r'无(?:匹配|符合条件)|未匹配',text) and re.search(r'空列表|total\s*=\s*0|暂无',text) and not re.search(r'应当存在|必须.*(?:商品|记录)|HTTP\s*[45]\d\d',text)
        if normal_cancel or normal_empty:kind='optional';reason='原文明示普通取消或允许的空结果成功替代分支，不是违约失败'
        b['scenario_type']=kind
        if kind=='exception':kept.append(b)
        else:excluded.append({'original_id':b['id'],'scenario_type':kind,'reason':reason,'source_refs':b['source_refs']})
    out['branches']=kept;return out

def normal_replay(record):
    trigger=record.get('触发条件','');expected=record.get('预期结果','')
    return bool(re.search(r'重复(?:提交|请求)|相同幂等键',trigger) and not re.search(r'失败|错误|失效|不一致|未|多次|重复(?:创建|扣款|写入|生成)',trigger) and re.search(r'返回已有.*不重复|幂等命中.*不重复',expected))

def filter_scenarios(value,inputs,task):
    out=deepcopy(value);kept=[];excluded=out.setdefault('excluded',[])
    tests={r['id']:r for r in records(inputs.get('test-documents',[]))}
    for s in out.get('scenarios',[]):
        kind=s.get('scenario_type','exception');reason='模型明确的场景类型'
        if task=='test-ground-truth':
            ids={m for r in s.get('source_refs',[]) for m in re.findall(r'\b(?:TEST|SUP)[-_][A-Za-z0-9_-]+',r['quote'])}
            kinds={tests[x]['scenario_type'] for x in ids if x in tests}
            kind=next(iter(kinds)) if len(kinds)==1 else 'pending';reason='测试类型字段严格筛选'
            selected=[tests[x] for x in ids if x in tests]
            if selected and all(normal_replay(r) for r in selected):kind='normal';reason='源表标为异常，但触发仅正常幂等重放且预期返回已有、不重复创建；没有违约失败，不计分，保留原始来源'
        text=s.get('cause','')
        if task=='exception-generate' and text in {'no_matching_records','empty_list'}:
            required=[r for r in inputs.get('normal-rules',{}).get('rules',[]) if r['interaction_id']==s['interaction_id'] and re.search(r'非空|至少(?:一|1)|必须存在|必须.*匹配|不得为空',r.get('condition',''))]
            if not required:kind='optional';reason='普通集合查询的空结果没有违反非空/必有结果约定，不自动视为异常'
        # A customer's voluntary cancellation and a documented normal fallback
        # aren't violations. Cancellation failure is a distinct real fault.
        if re.search(r'^(?:顾客|用户|商家|开发者)(?:主动)?取消(?:支付|订单|操作)$',text.strip()):kind='normal';reason='普通主动取消，不是失败'
        s['scenario_type']=kind
        if kind=='exception':kept.append(s)
        else:excluded.append({'original_id':s['id'],'scenario_type':kind,'reason':reason,'source_refs':s['source_refs']})
    out['scenarios']=kept
    return out
