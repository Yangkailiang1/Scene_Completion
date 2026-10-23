from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .assignment import full_assignment

UNITS={'components':'名称—系统组成类型','rr-ssd':'整条有序发送方、操作、数据、接收方',
 'sr-ssd':'整条有序发送方、操作、数据、接收方','object-operations':'名称—单项支持操作',
 'api-map':'服务名称—单项接口（方法与路径）','api-parameters':'接口—参数—属性—属性值'}


def extraction_units(task,payload):
    if task=='components':return [(x['name'],x['composition_type']) for x in payload['components']]
    if task in {'rr-ssd','sr-ssd'}:
        # All nested attributes remain part of one tuple; refs/IDs are metadata.
        def clean(v):
            if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in {'source_refs','id','source_status','status'} and x is not None}
            if isinstance(v,list):return [clean(x) for x in v if not isinstance(x,dict) or x.get('status')!='pending']
            return v
        return [(x['case_id'],x['layer'],x['sequence'],clean(x['sender']),clean(x['operation']),clean(x['data']),clean(x['receiver'])) for x in payload['interactions']]
    if task=='object-operations':return [(x['name'],op['name']) for x in payload['objects'] for op in x['supported_operations']]
    if task=='api-map':return [(x['name'],i['id'] if i['method'] is None and i['address'] is None else None,i['method'],i['address']) for x in payload['services'] for i in x['interfaces']]
    if task=='api-parameters':
        out=[]
        for a in payload['apis']:
            for p in a['parameters']:
                base=(a.get('address') or a['id'],p['location'],p['name'])
                if p['data_type'] is not None:out.append((*base,'数据类型',p['data_type']))
                if p['required'] is not None:out.append((*base,'可选/必填',p['required']))
                for r in p['constraints']:
                    if r['status']=='explicit' and r['kind']!='type':out.append((*base,'约束:'+r['kind'],r['value']))
        return out
    raise ValueError('no extraction metric for predefined concerns or disabled recommendation')


def accuracy(task, extracted, truth, decisions=None):
    """GT attributes constrain matches; extra unknown GT fields are not scored.

    Semantic decisions may be supplied after human/model one-to-one adjudication.
    Without decisions only exact canonical values score; no similarity heuristic.
    """
    a={fingerprint(x):x for x in extraction_units(task,extracted)}
    t={fingerprint(x):x for x in extraction_units(task,truth)}
    if decisions is None:
        def contains(actual,gt,key=None):
            if gt is None or gt=='待确认':return True
            if isinstance(gt,dict):
                return isinstance(actual,dict) and all(k in actual and contains(actual[k],v,k) for k,v in gt.items())
            if isinstance(gt,(list,tuple)):
                if not isinstance(actual,(list,tuple)):return False
                if key=='constraints':return all(any(contains(x,y) for x in actual) for y in gt)
                return len(actual)==len(gt) and all(contains(x,y) for x,y in zip(actual,gt))
            return actual==gt
        exact=[{'left_id':tid,'right_id':aid,'status':'full','reason':'all GT-defined attributes agree'}
               for tid,tu in t.items() for aid,au in a.items() if contains(au,tu)]
        h=len(full_assignment(exact,set(t),set(a)))
    else:
        if isinstance(decisions,dict):
            if decisions.get('protocol')!=PROTOCOL or decisions.get('task')!=task or decisions.get('extracted_hash')!=fingerprint(extracted) or decisions.get('truth_hash')!=fingerprint(truth):raise ValueError('adjudication not bound to these extraction inputs')
            decisions=decisions['decisions']
        from .contracts import DECISION
        from jsonschema import Draft202012Validator
        if list(Draft202012Validator({'type':'array','items':DECISION}).iter_errors(decisions)):raise ValueError('invalid extraction decisions')
        pairs=[(d['left_id'],d['right_id']) for d in decisions]
        if len(pairs)!=len(set(pairs)):raise ValueError('duplicate adjudication pair')
        if task in {'rr-ssd','sr-ssd'}:
            for d in decisions:
                if d['status']=='full' and d['left_id'] in t and d['right_id'] in a and t[d['left_id']][:3]!=a[d['right_id']][:3]:raise ValueError('SSD correspondence must preserve case, layer and order')
        if any(d['left_id'] not in t or d['right_id'] not in a for d in decisions):raise ValueError('unknown extraction unit')
        h=len(full_assignment(decisions,set(t),set(a)))
    return {'protocol':PROTOCOL,'Acc':100*h/len(t) if t else None,'H':h,'N':len(t),
            'symbols':{'Acc':'抽取准确率（GT命中率）','H':'命中的真值单元数','N':'真值单元总数','GT':'人工真值集合'},
            'input_identity':{'extracted_hash':fingerprint(extracted),'truth_hash':fingerprint(truth)},
            'minimum_unit':UNITS[task],'status':'适用' if t else '不适用',
            'truth_units':[{'id':k,'value':v} for k,v in t.items()],
            'extracted_units':[{'id':k,'value':v} for k,v in a.items()]}



def not_evaluated(task):
    return {'protocol':PROTOCOL,'Acc':None,'H':None,'N':None,'minimum_unit':UNITS[task],'status':'未评测'}
