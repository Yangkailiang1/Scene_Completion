"""Editable source exports and GT-hit extraction scoring (no binary metrics)."""
from html import escape
from pathlib import Path
import json
from .semantic_backend import write_json
from .sources import fingerprint
from .ppt_contracts import PROTOCOL
from .ppt_method import full_assignment

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
                base=(a['id'],p['location'],p['name'])
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
        if any(d['left_id'] not in t or d['right_id'] not in a for d in decisions):raise ValueError('unknown extraction unit')
        h=len(full_assignment(decisions,set(t),set(a)))
    return {'protocol':PROTOCOL,'Acc':100*h/len(t) if t else None,'H':h,'N':len(t),
            'symbols':{'Acc':'抽取准确率（GT命中率）','H':'命中的真值单元数','N':'真值单元总数','GT':'人工真值集合'},
            'minimum_unit':UNITS[task],'status':'适用' if t else '不适用',
            'truth_units':[{'id':k,'value':v} for k,v in t.items()],
            'extracted_units':[{'id':k,'value':v} for k,v in a.items()]}


def export_task(root,task,payload):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    write_json(root/(task+'.json'),{'protocol':PROTOCOL,'task':task,'payload':payload})
    def show(x):return '待确认' if x is None else str(x)
    rows=[]; headers=[]
    if task=='components':headers=['名称','系统组成'];rows=[[x['name'],x['composition_type']] for x in payload['components']]
    elif task=='object-operations':headers=['名称','支持的操作'];rows=[[x['name'],'、'.join(o['name'] for o in x['supported_operations'])] for x in payload['objects']]
    elif task=='api-map':headers=['服务名称','对应接口列表'];rows=[[s['name'],'；'.join(' '.join(filter(None,[i['id'],i['method'],i['address']])) for i in s['interfaces'])] for s in payload['services']]
    elif task=='api-parameters':
        headers=['API名称','接口地址','请求参数','数据类型','可选/必填','约束条件']
        rows=[[a['name'],show(a['address']),p['name'],show(p['data_type']),show(p['required']),'; '.join(r['kind']+'='+show(r['value']) if r['status']=='explicit' else r['kind']+'待确认' for r in p['constraints'])] for a in payload['apis'] for p in a['parameters']]
    elif task in {'rr-ssd','sr-ssd'}:
        headers=['顺序','发送方','操作','数据','接收方'];rows=[[i['sequence'],i['sender']['name'],i['operation']['name'],'、'.join(p['name'] for p in i['data']['sequence']),i['receiver']['name']] for i in payload['interactions']]
    elif task=='concern-match':
        from .ppt_contracts import registry
        defs=registry()['definitions'];headers=['交互','系统组成/数据','关注点'];rows=[[m['interaction_id'],m['object'],defs[m['concern_key']]['label']] for m in payload['matches']]
    if headers:
        safe=lambda x:str(x).replace('|','\\|').replace('\n','<br>')
        text='| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'
        text+='\n'.join('| '+' | '.join(map(safe,r))+' |' for r in rows)
        (root/(task+'.md')).write_text(text+'\n',encoding='utf8')
    if task in {'components','rr-ssd','sr-ssd'}:
        # Native vector text/shapes; source .dot is also supplied for editing.
        if task=='components':
            nodes=[(c['id'],c['name'],c['composition_type']=='用例') for c in payload['components']]
            edges=[(r['from_id'],r['to_id'],r['relation']) for r in payload['relations']]
        else:
            names=list(dict.fromkeys(p['name'] for i in payload['interactions'] for p in (i['sender'],i['receiver'])))
            nodes=[(n,n,False) for n in names];edges=[(i['sender']['name'],i['receiver']['name'],str(i['sequence'])+' '+i['operation']['name']) for i in payload['interactions']]
        q=lambda s:json.dumps(s,ensure_ascii=False)
        dot='digraph model { rankdir=LR;\n'+''.join(f'{q(i)} [label={q(n)}, shape={"ellipse" if usecase else "box"}];\n' for i,n,usecase in nodes)
        dot+=''.join(f'{q(a)} -> {q(b)} [label={q(label)}];\n' for a,b,label in edges)+'}\n'
        (root/(task+'.dot')).write_text(dot,encoding='utf8')
        # Graphviz is optional; JSON, Markdown and DOT always export.
        import shutil,subprocess
        if shutil.which('dot'):subprocess.run(['dot','-Tsvg',str(root/(task+'.dot')),'-o',str(root/(task+'.svg'))],check=True,capture_output=True)
        if task in {'rr-ssd','sr-ssd'}:export_sequence_svg(root,task,payload)


def export_sequence_svg(root, task, payload):
    from .svg_renderer import render_ssd_svg
    from .interaction_diagrams import diagram_stem
    root=Path(root)
    case_ids=list(dict.fromkeys(i['case_id'] for i in payload['interactions']))
    for cid in case_ids:
        interactions=sorted((i for i in payload['interactions'] if i['case_id']==cid),key=lambda x:x['sequence'])
        names=list(dict.fromkeys(p['name'] for i in interactions for p in (i['sender'],i['receiver'])))
        nodes=[{'node_id':fingerprint(n)[:16],'name':n,'kind':'human_actor' if any(i['sender']['name']==n and '人类' in i['sender']['position'] for i in interactions) else 'internal_service'} for n in names]
        ids={n['name']:n['node_id'] for n in nodes}
        view={'use_case_id':cid,'layer':interactions[0]['layer'],
          'lifelines':[{'node_id':n['node_id'],'label':n['name']} for n in nodes],
          'messages':[{'from_node':ids[i['sender']['name']],'to_node':ids[i['receiver']['name']],
            'sequence':i['sequence'],'source_step_index':i['id'],
            'message':i['operation']['name']+('\n数据：'+'、'.join(p['name'] for p in i['data']['sequence']) if i['data']['sequence'] else ''),
            'message_kind':'response' if i['direction']=='return' else 'request','layer':i['layer']} for i in interactions]}
        target=root/(task+'.svg' if len(case_ids)==1 else task+'-'+diagram_stem(cid,interactions[0]['layer'])+'.svg')
        render_ssd_svg(view,{'system_composition':{'nodes':nodes}},target)
