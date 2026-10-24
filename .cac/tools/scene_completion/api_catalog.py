"""Derived API review table. No model calls or guessed interface identities."""
from pathlib import Path
import json
from .storage import read_json, write_json, fingerprint
from .contracts import PROTOCOL

COLUMNS = [('service','服务名称'),('api_name','API名称'),('method','方法'),('address','接口地址'),
 ('mapping_status','归属状态'),('parameter_status','参数状态'),('direction','方向'),('location','位置'),
 ('name','参数'),('data_type','数据类型'),('required','可选/必填'),('default','默认值'),('constraints','约束条件')]

def combine(mapping, parameters, *, mapping_status='未完成', parameters_complete=False):
    interfaces=[(s,i) for s in mapping.get('services',[]) for i in s['interfaces']]
    apis=parameters.get('apis',[]);links={};rows=[]
    for n,(_,i) in enumerate(interfaces):
        candidates=[j for j,a in enumerate(apis) if a['id']==i['id'] and
                    (not a.get('address') or not i.get('address') or a['address']==i['address'])]
        if not candidates and i.get('address'):
            candidates=[j for j,a in enumerate(apis) if a.get('address')==i['address']]
        if len(candidates)==1:links[n]=candidates[0]
    # A path alone cannot distinguish GET/POST variants or multiple owners.
    for j in set(links.values()):
        owners=[n for n,target in links.items() if target==j]
        if len(owners)>1:
            for n in owners:links.pop(n)
    def append(s,i,a):
        base={'service':s['name'] if s else None,'api_id':i['id'] if i else a['id'],
              'api_name':i['name'] if i else a['name'],'method':i.get('method') if i else None,
              'address':(i.get('address') if i else None) or (a.get('address') if a else None),
              'mapping_status':mapping_status if s else '服务归属待确认',
              'parameter_status':a.get('_status','未完成') if a else '待提取或身份待确认',
              'source_refs':(i.get('source_refs',[]) if i else [])+(a.get('source_refs',[]) if a else [])}
        params=a['parameters'] if a else []
        if not params:rows.append({**base,'name':'文档未列出参数' if a else '尚未取得参数结果'})
        for p in params:
            rows.append({**base,**{k:p.get(k) for k in ('name','location','data_type','default','constraints')},
                         'direction':'输出' if p['location']=='response' else '输入',
                         'required':'必填' if p['required'] is True else '可选' if p['required'] is False else '待确认',
                         'parameter_source_refs':p.get('source_refs',[])})
    for n,(s,i) in enumerate(interfaces):append(s,i,apis[links[n]] if n in links else None)
    for j,a in enumerate(apis):
        if j not in links.values():append(None,None,a)
    unresolved=len(interfaces)-len(links)+len(apis)-len(set(links.values()))
    return {'protocol':PROTOCOL,'view':'api-catalog','rows':rows,
            'complete':mapping_status=='已完成' and parameters_complete and not unresolved,
            'identity_pending':unresolved,'mapping_status':mapping_status,'parameters_complete':parameters_complete}

def saved_catalog(root):
    root=Path(root);state=root/'workflow_tasks.json'
    records=read_json(state).get('tasks',{}) if state.exists() else {}
    def load(key):
        record=records.get(key,{});status=record.get('status')
        if status=='passed' and record.get('output_file'):
            f=(root/record['output_file']).resolve()
            if f.is_relative_to(root.resolve()) and f.exists():
                envelope=read_json(f)
                if envelope.get('protocol')==PROTOCOL:return envelope['payload'],'已完成'
        if status=='awaiting_review':
            f=root/'reviews'/(fingerprint(key)+'.json')
            if f.exists():
                review=read_json(f)
                if review.get('status') in {'draft','approved','auto'}:
                    return review['payload'],'待审核' if review['status']=='draft' else '已审核，待流程确认'
        return None,'未完成'
    mapping,mapping_status=load('api-map');params,status=load('api-parameters')
    if params is not None:apis=[{**a,'_status':status} for a in params['apis']]
    else:
        apis=[]
        for key in sorted(records):
            if not key.startswith('api-parameters-part-'):continue
            part,status=load(key)
            if part:apis.extend({**a,'_status':status} for a in part['apis'])
    return combine(mapping or {},{'apis':apis},mapping_status=mapping_status,
                   parameters_complete=records.get('api-parameters',{}).get('status')=='passed')

def markdown(catalog):
    def cell(v):
        if v is None:return '待确认'
        return (json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v)).replace('|','\\|').replace('\n','<br>')
    lines=['# API接口总表','','状态：'+('已完成' if catalog['complete'] else '中间结果，含待审核或未完成接口'),'',
           '| '+' | '.join(label for _,label in COLUMNS)+' |','| '+' | '.join('---' for _ in COLUMNS)+' |']
    lines+=['| '+' | '.join(cell(row.get(k)) for k,_ in COLUMNS)+' |' for row in catalog['rows']]
    return '\n'.join(lines)+'\n'

def save_catalog(root,catalog):
    folder=Path(root)/'artifacts/shared';folder.mkdir(parents=True,exist_ok=True);target=folder/'api-catalog.json'
    if not target.exists() or read_json(target)!=catalog:
        write_json(target,catalog)
        text=folder/'api-catalog.md';temporary=text.with_suffix('.md.tmp')
        temporary.write_text(markdown(catalog),encoding='utf8');temporary.replace(text)
