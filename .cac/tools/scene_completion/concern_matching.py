from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .interaction_enrichment import interactions,parameters_for
def concern_by_label(label):
    found=[k for k,v in registry()['definitions'].items() if v['label']==label]
    if len(found)!=1:raise ValueError('ambiguous concern label: '+label)
    return found[0]


def complete_data_matches(inputs, matches):
    """Known parameter properties have deterministic matches to fixed definitions."""
    matches=deepcopy(matches)
    kinds={'type':'数据类型','enum':'数据合法性','minimum':'数据范围','maximum':'数据范围','format':'数据格式',
           'length':'数据长度','size':'数据大小','pattern':'数据格式','other':'数据合法性'}
    for i in interactions(inputs):
        for p in parameters_for(i,inputs):
            rules=[]
            if p['required'] is True:rules.append(('数据完整性','required',True,p['source_refs']))
            if p['data_type'] is not None:rules.append(('数据类型','type',p['data_type'],p['source_refs']))
            rules += [(kinds[r['kind']],r['kind'],r['value'],r['source_refs']) for r in p['constraints'] if r['status']=='explicit']
            for label,rule,value,refs in rules:
                matches.append({'interaction_id':i['id'],'target':'data','object':p['name'],'concern_key':concern_by_label(label),
                                'basis':'当前请求/返回接口的明示字段属性','concrete_rule':rule+'='+json.dumps(value,ensure_ascii=False),'source_refs':refs,
                                'scope':'interface','data_location':p['location'],'activation_evidence':[{'kind':'data','condition':p['name']+' '+rule+'='+json.dumps(value,ensure_ascii=False),'value':value,'unit':None,'status':'explicit','field':p['name'],'constraint_kind':rule,'source_refs':refs}]})
    return list({fingerprint(m):m for m in matches}.values())
