"""SysML 1.6 BDD view of saved component facts, with editable source exports.

This is a presentation projection, not an architectural authority or a new LLM
extraction. Classification and ownership are separate relationships. Use cases
remain behavioral elements in the original composition/use-case view.
"""
from pathlib import Path
from html import escape
import json, math, os, threading
from threading import RLock
_LOCK=RLock()

def _write_text(path,text):
    path=Path(path);temporary=path.with_name(path.name+f".{os.getpid()}.{threading.get_ident()}.tmp")
    temporary.write_text(text,encoding="utf8");temporary.replace(path)
from .storage import fingerprint,write_json

VERSION='sysml-bdd-v3'
STANDARD='https://www.omg.org/spec/SysML/1.6/'
EXTERNAL={'外部Actor（人类）','外部Actor（系统）','外部数据库','外部资源'}

def build_bdd(payload):
    components=payload.get('components',[])
    sources={c['id']:c for c in components if c.get('composition_type')!='用例'}
    blocks=[];edges=[];pending=[];types={}
    for c in sources.values():
        typ=c['composition_type'];tid='type-'+fingerprint(typ)[:10]
        types[typ]=tid
        blocks.append({'id':c['id'],'name':c['name'],'kind':'component','composition_type':typ,
                       'source_status':c.get('source_status','pending'),'source_refs':c.get('source_refs',[]),'parent_id':c.get('parent_id')})
        edges.append({'kind':'generalization','from_id':c['id'],'to_id':tid,'label':'','basis':'既存组成类型分类','source_refs':c.get('source_refs',[])})
    for typ,tid in types.items():
        blocks.append({'id':tid,'name':typ,'kind':'classifier','abstract':True,'source_status':'view_definition','source_refs':[]})
    def cycle(cid):
        seen={cid};node=sources[cid]
        while node.get('parent_id') in sources:
            parent=node['parent_id']
            if parent in seen:return True
            seen.add(parent);node=sources[parent]
        return False
    for c in sources.values():
        parent=c.get('parent_id')
        if not parent:continue
        if parent not in sources or cycle(c['id']):
            pending.append({'component_id':c['id'],'reason':'所属对象不存在或所属关系成环','parent_id':parent});continue
        # An external actor is never owned by the software merely because it participates.
        explicit=c.get('source_status')=='explicit' and c.get('composition_type') not in EXTERNAL
        edges.append({'kind':'composition' if explicit else 'association','from_id':parent,'to_id':c['id'],
                      'label':'' if explicit else '所属待确认','basis':'已保存parent_id；非新增推断','source_refs':c.get('source_refs',[])})
        if not explicit:pending.append({'component_id':c['id'],'reason':'外部对象或推断的所属不绘制组合关系','parent_id':parent})
    for r in payload.get('relations',[]):
        a,b=r.get('from_id'),r.get('to_id')
        if a not in sources or b not in sources or a==b:continue
        if any(e['kind']=='composition' and {e['from_id'],e['to_id']}=={a,b} for e in edges):continue
        edges.append({'kind':'association','from_id':a,'to_id':b,'label':r.get('relation',''),
                      'basis':'已保存对象关系；关联线不表示调用时序','source_refs':r.get('source_refs',[])})
    seen=set();dedup=[]
    for e in edges:
        sig=(e['kind'],e['from_id'],e['to_id'],e['label'])
        if sig not in seen:seen.add(sig);dedup.append(e)
    return {'notation':'SysML 1.6 Block Definition Diagram','version':VERSION,'source_hash':fingerprint(payload),
            'standard':STANDARD,'title':'系统上下文 — 块定义图','blocks':blocks,'relationships':dedup,
            'excluded_behavior':[{'id':c['id'],'name':c['name'],'reason':'用例属于行为视图，不改画为结构块'} for c in components if c.get('composition_type')=='用例'],
            'pending':pending,'notes':['矩形«block»为块；实心菱形在整体端表示组合；空心三角指向一般类型表示泛化；无箭头实线表示关联。',
              '分类块为视图类型定义，不是额外部署的模块。外部人类、Service和资源不作为软件的组成部分。',
              '系统上下文由图框界定；未声明多重性、接口和硬件时不补造。依据为已保存组成和来源，仍需业务审核。']}

def _source(model):
    names={b['id']:'B'+str(i) for i,b in enumerate(model['blocks'])}
    q=lambda v:json.dumps(v,ensure_ascii=False)
    puml=['@startuml','title bdd [package] 系统上下文','hide empty members','skinparam classAttributeIconSize 0']
    dot=['digraph BDD {','graph [rankdir=LR, label="bdd [package] 系统上下文", labelloc=t, bgcolor=white];','node [shape=box, fontname="Microsoft YaHei"];']
    for b in model['blocks']:
        label='«block»\n'+b['name']+ ('\n{abstract}' if b.get('abstract') else '')
        puml.append(('abstract class ' if b.get('abstract') else 'class ')+q(b['name'])+' as '+names[b['id']]+' <<block>>')
        dot.append(names[b['id']]+' [label='+q(label)+'];')
    for e in model['relationships']:
        a,b=names[e['from_id']],names[e['to_id']];kind=e['kind'];label=e['label']
        op={'composition':'*--','generalization':'--|>','association':'--'}[kind]
        puml.append(f'{a} {op} {b}'+(' : '+label.replace('\n',' ') if label else ''))
        attrs={'composition':'dir=both, arrowtail=diamond, arrowhead=none','generalization':'arrowhead=empty','association':'dir=none'}[kind]
        dot.append(f'{a} -> {b} [{attrs}, label={q(label)}];')
    return '\n'.join(puml+['@enduml','']), '\n'.join(dot+['}',''])

def render_bdd(model,path):
    """Native SVG: context/parts at top, classification tree below.

    SysML parts compartments express composition without dozens of crossing
    ownership lines. Full, identical composition edges remain in editable sources.
    """
    blocks=model['blocks'];lookup={b['id']:b for b in blocks};parts={}
    for e in model['relationships']:
        if e['kind']=='composition':parts.setdefault(e['from_id'],[]).append(lookup[e['to_id']])
    owners=[b for b in blocks if b['id'] in parts]
    boundaries=[b for b in blocks if b.get('composition_type')=='系统边界']
    externals=[b for b in blocks if b.get('composition_type') in EXTERNAL]
    width=1600;items=[];y=140
    def txt(x,yy,label,size=13,color='#294465',anchor='start'):
        return f'<text x="{x}" y="{yy}" text-anchor="{anchor}" font-size="{size}" fill="{color}">{escape(str(label))}</text>'
    def box(b,x,yy,w=250,h=62):
        result=[f'<g data-block-id="{escape(b["id"],quote=True)}"><title>{escape(b["name"]+" · "+b["source_status"])}</title><rect x="{x}" y="{yy}" width="{w}" height="{h}" fill="{"#edf3fe" if b.get("abstract") else "white"}" stroke="#7993b9"/>',txt(x+w/2,yy+18,'«block»'+(' {abstract}' if b.get('abstract') else ''),11,'#7f92ab','middle')]
        chunks=[b['name'][i:i+25] for i in range(0,len(b['name']),25)]
        for j,label in enumerate(chunks):result.append(txt(x+w/2,yy+39+j*15,label,13,anchor='middle'))
        result.append('</g>');return ''.join(result)
    items.append(txt(36,107,'A · 系统上下文与组成',18))
    ownerpos={};externalpos={}
    # Every owner gets its own block definition with standard parts compartment.
    for b in owners+[b for b in boundaries if b not in owners]:
        rows=parts.get(b['id'],[]);columns=3;h=110+max(1,math.ceil(len(rows)/columns))*31
        x=365;w=870;ownerpos[b['id']]=(x,y,w,h)
        items.append(f'<g data-owner-id="{escape(b["id"],quote=True)}"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" stroke="#547cab" stroke-width="1.5"/>')
        items.extend([txt(x+w/2,y+22,'«block»',12,'#748cac','middle'),txt(x+w/2,y+48,b['name'],19,anchor='middle'),f'<line x1="{x}" y1="{y+65}" x2="{x+w}" y2="{y+65}" stroke="#b4c5db"/>',txt(x+18,y+87,'parts',12,'#758aa6')])
        for n,child in enumerate(rows):
            col=n%columns;row=n//columns;prop='p'+str(n+1)+' : '+child['name']
            items.append(txt(x+18+col*285,y+115+row*31,prop,12))
        items.append('</g>');y+=h+48
    context_bottom=max(y,140+math.ceil(len(externals)/2)*98)
    for n,b in enumerate(externals):
        side=n%2;yy=140+(n//2)*98;x=55 if side==0 else 1295
        externalpos[b['id']]=(x,yy,250,62);items.append(box(b,x,yy))
    # Context associations only. No phantom owner connects external actors.
    lines=[]
    for e in model['relationships']:
        if e['kind']!='association':continue
        a,b=e['from_id'],e['to_id'];rev=False
        if a in ownerpos and b in externalpos:a,b=b,a;rev=True
        if a not in externalpos or b not in ownerpos:continue
        ext=externalpos[a];own=ownerpos[b];right=ext[0]>own[0]
        x1=ext[0] if right else ext[0]+ext[2];x2=own[0]+own[2] if right else own[0];yy=ext[1]+ext[3]/2
        y2=max(own[1]+10,min(own[1]+own[3]-10,yy))
        lines.append(f'<path data-kind="association" d="M{x1},{yy} L{x2},{y2}" fill="none" stroke="#9cacbf"><title>{escape(e["label"])}</title></path>')
    items=lines+items
    # Expand one real owner's representative parts as a conventional composition
    # tree as well; all parts stay listed in its compartment, not synthetic groups.
    if owners:
        owner=owners[0];seen_types=set();examples=[]
        for child in parts[owner['id']]:
            if child['composition_type'] not in seen_types:
                seen_types.add(child['composition_type']);examples.append(child)
        examples=examples[:3];a=ownerpos[owner['id']];rootx=a[0]+a[2]/2;rooty=a[1]+a[3];yy=context_bottom+22
        items.append(txt(365,yy,'所属展开示例（全部子项见parts）',11,'#8495ab'));yy+=20
        bus=yy-10
        items.append(f'<path data-kind="composition" d="M{rootx},{rooty} V{bus}" fill="none" stroke="#547cab"/>')
        items.append(f'<polygon data-symbol="composition-diamond" points="{rootx},{rooty} {rootx-6},{rooty+9} {rootx},{rooty+18} {rootx+6},{rooty+9}" fill="#294465"/>')
        for n,child in enumerate(examples):
            x=365+n*300;cx=x+125
            items.append(f'<path data-kind="composition" d="M{rootx},{bus} H{cx} V{yy}" fill="none" stroke="#547cab"/>');items.append(box(child,x,yy))
        context_bottom=yy+62
    y=context_bottom+36;items.extend([txt(36,y,'组合由parts区室表达；每一项为“属性名 : 块类型”，来源是已保存的所属关系。',12,'#7a8da5'),txt(36,y+23,'外部对象只关联系统。完整内部关联与来源见JSON、DOT和PlantUML；无依据的所属另列待确认。',12,'#7a8da5')]);y+=85
    items.append(txt(36,y,'B · 块类型分类（空心三角指向一般类型）',18));y+=30
    classifiers=[b for b in blocks if b['kind']=='classifier']
    order={'外部Actor（人类）':0,'系统边界':1,'UI/前端':2,'内部服务':3,'内部数据库':4,'AI模型':5,'外部Actor（系统）':6}
    classifiers.sort(key=lambda b:(order.get(b['name'],10),b['name']))
    cols=5;cw=300
    for start in range(0,len(classifiers),cols):
        chunk=classifiers[start:start+cols];rowheight=0
        for col,c in enumerate(chunk):
            children=[b for b in blocks if b.get('composition_type')==c['name']];x=45+col*cw;h=145+len(children)*78;rowheight=max(rowheight,h)
            items.append(f'<rect x="{x}" y="{y}" width="288" height="{h}" rx="8" fill="#f8fafe" stroke="#e3ebf6"/>')
            cx=x+24;cy=y+20
            # Draw the shared generalization trunk outside all name boxes.
            for n,b in enumerate(children):
                yy=y+125+n*78
                items.append(f'<path data-kind="generalization" d="M{cx+240},{yy+31} H{x+277} V{cy+31} H{cx+240}" fill="none" stroke="#8da4c4" marker-end="url(#bdd-triangle)"/>')
            items.append(box(c,cx,cy,240))
            for n,b in enumerate(children):items.append(box(b,cx,y+125+n*78,240))
        y+=rowheight+35
    height=y+110
    head=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="SysML块定义图" font-family="Microsoft YaHei,PingFang SC,sans-serif">',
      '<defs><marker id="bdd-triangle" markerWidth="14" markerHeight="12" refX="12" refY="6" orient="auto"><path d="M1,1 L12,6 L1,11 Z" fill="white" stroke="#6a84ac"/></marker></defs>',
      '<rect width="100%" height="100%" fill="white"/>',f'<rect x="14" y="14" width="{width-28}" height="{height-28}" fill="none" stroke="#627991"/>',
      '<path d="M14,58 H460 L476,42 V14" fill="none" stroke="#627991"/>',txt(29,41,'bdd [package] 系统上下文',17)]
    footer=[txt(36,y+15,'◆ 组合：整体拥有parts　▷ 泛化：具体块属于一般类型　— 关联：对象之间的关系，非时序',13),txt(36,y+42,'用例保留在行为图。分类块是视图类型定义，并非新增部署组件；数据、关系仍需业务审核。',12,'#8190a4'),'</svg>']
    _write_text(path,'\n'.join(head+items+footer))

def export_bdd(payload,folder):
    with _LOCK:return _export_bdd(payload,folder)

def _export_bdd(payload,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);model=build_bdd(payload)
    target=folder/'system-bdd.json'
    if target.exists():
        try:
            old=json.loads(target.read_text()).get('payload',{})
            if old.get('version')==VERSION and old.get('source_hash')==model['source_hash'] and all((folder/('system-bdd.'+ext)).is_file() for ext in ('svg','puml','dot','md')):return model
        except (ValueError,OSError):pass
    puml,dot=_source(model);_write_text(folder/'system-bdd.puml',puml);_write_text(folder/'system-bdd.dot',dot)
    render_bdd(model,folder/'system-bdd.svg')
    rows=['# 系统上下文：SysML BDD','',*model['notes'],'','规范：'+STANDARD,'','| 类型 | 起点 | 终点 | 依据 |','| --- | --- | --- | --- |']
    names={b['id']:b['name'] for b in model['blocks']}
    for e in model['relationships']:rows.append('| '+' | '.join(str(x).replace('|','\\|') for x in (e['kind'],names[e['from_id']],names[e['to_id']],e['basis']))+' |')
    rows+=['','## 待确认',*[json.dumps(p,ensure_ascii=False) for p in model['pending']]]
    _write_text(folder/'system-bdd.md','\n'.join(rows)+'\n')
    write_json(target,{'task':'bdd','payload':model})
    return model
