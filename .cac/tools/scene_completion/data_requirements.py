"""Positive field requirements shared by G and independent test construction.

No generated exception, E, GT or comparison input is accepted here.
"""
from copy import deepcopy
import re
from .storage import fingerprint

VERSION='data-union-size-v2'


def size_bounds(value,text):
    """Preserve declared directions; a directionless size check has two modes.

    None is a symbolic unknown bound, never zero or a guessed numeric value.
    """
    if isinstance(value,dict):
        out=[]
        for side,keys in [('minimum',('min','minimum','minBytes','minItems')),('maximum',('max','maximum','maxBytes','maxItems'))]:
            vals=[value[k] for k in keys if k in value]
            if vals:out.append((side,vals[0] if len(vals)==1 else None))
        if out:return out
    low=bool(re.search(r'下界|下限|最小|至少|不少于|低于|过小|太小|minimum|minBytes|>=|≥',text,re.I))
    high=bool(re.search(r'上界|上限|最大|最多|不超过|超过|超出|超限|过大|太大|maximum|maxBytes|<=|≤',text,re.I))
    if low!=high:return [('minimum' if low else 'maximum',value if type(value) in (int,float) else None)]
    return [('minimum',None),('maximum',None)]


def measure(text):
    if re.search(r'数量|个数|张数|条数|数组.*(?:长度|元素)|minItems|maxItems',text,re.I):return 'item_count'
    if re.search(r'文件|图片|图像|字节|bytes|\b[KMGT]?B\b',text,re.I):return 'file_size'
    return 'unspecified'


def field_requirements(p):
    from .normal_rules import conditional_constraint,descriptive_constraint
    rows=[]
    if p['required'] is True:rows.append({'kind':'required','value':True,'status':'explicit','source_refs':p['source_refs']})
    if p['data_type'] is not None:rows.append({'kind':'type','value':p['data_type'],'status':'explicit','source_refs':p['source_refs']})
    rows += [deepcopy(r) for r in p['constraints'] if (r['status']=='explicit' or conditional_constraint(r)) and not descriptive_constraint(r)]
    unique={}
    for row in rows:
        if row['kind']=='type' and row.get('value') is None:continue
        conditional=conditional_constraint(row) or row.get('status')=='pending' or row.get('value') is None
        text=' '.join(r['quote'] for r in row['source_refs'])
        variants=size_bounds(row['value'],text) if row['kind']=='size' else [(None,row['value'])]
        for side,value in variants:
            r=deepcopy(row);r.update(kind='size.'+side if side else row['kind'],value=value,conditional=conditional or value is None)
            if side:r['measure']=measure(text)
            key=fingerprint([r['kind'],r['value'],r.get('measure')])
            if key not in unique:unique[key]=r
            else:unique[key]['source_refs']=list({fingerprint(x):x for x in unique[key]['source_refs']+r['source_refs']}.values())
    return list(unique.values())


def positive_parameters(i,inputs):
    from .interaction_enrichment import parameters_for
    material={**inputs,'api-parameters':inputs.get('api-parameters',inputs.get('normal-constraints',{'apis':[]}))}
    params=parameters_for(i,material)
    for p in params:
        if any(c['kind']=='size' for c in p['constraints']):continue
        for r in inputs.get('normal-rules',{}).get('rules',[]):
            if r['interaction_id']==i['id'] and r['concern_key']=='api.data.size' and p['name'] in r['fields']:
                p['constraints'].append({'id':'positive-size-'+fingerprint([r['id'],p['name']])[:20],'kind':'size','value':None,'status':'pending','source_refs':deepcopy(r['source_refs'])})
    return params


def trigger(name,rule):
    if rule['kind']=='required':return name+'未提供'
    noun={'file_size':'文件大小','item_count':'数量','unspecified':'大小'}.get(rule.get('measure'),'')
    if rule['kind'].startswith('size.'):
        side='低于允许下界' if rule['kind'].endswith('minimum') else '超过允许上界'
        return name+'对应数据的'+noun+side+('（具体阈值待确认）' if rule['value'] is None else '：'+str(rule['value']))
    import json
    return name+'已提供；违反'+rule['kind']+'约束: '+json.dumps(rule['value'],ensure_ascii=False,sort_keys=True)


def split_size_scenarios(rows):
    """Independent normalization of one channel, without borrowing other sets."""
    out=[]
    for s in rows:
        if s.get('concern_key')!='api.data.size' or not s.get('field'):
            out.append(s);continue
        rule=s.get('failure_rule',{})
        if rule.get('kind') in {'size.minimum','size.maximum'}:
            out.append(s);continue
        own=' '.join([s.get('cause','')]+s.get('conditions',[]))
        text=own+' '+' '.join(r['quote'] for r in s.get('source_refs',[]))
        # Each recognized size failure is an evidenced size requirement;
        # don't manufacture size modes for unrelated concerns.
        bounds=size_bounds(rule.get('value'),text)
        directions=size_bounds(None,own)
        if len(directions)==1:bounds=[(directions[0][0],dict(bounds).get(directions[0][0]))]
        for side,value in bounds:
            child=deepcopy(s);r={'kind':'size.'+side,'value':value,'measure':measure(text)}
            child.update(id='size-'+fingerprint([s['id'],side,value])[:24],cause=r['kind'],failure_rule={'kind':r['kind'],'value':value})
            child['conditions']=[trigger(s['field'],r)];child['steps']['trigger']=child['conditions'][0]
            child['predicate']={**child.get('predicate',{}),'measure':r['measure']}
            if value is None:
                child.update(resolution='conditional',executable=False)
                child['pending_details']=list(dict.fromkeys(child.get('pending_details',[])+['大小'+side+'阈值待确认']))
            child.setdefault('quality_notes',[]).append(VERSION+'：从本渠道大小失败按方向细化；未知数值不补造')
            out.append(child)
    return out
