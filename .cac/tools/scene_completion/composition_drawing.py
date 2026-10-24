"""Native SVG composition view adapted from the historical partitioned layout.

Only declared nodes and relations are drawn. No CRUD/deployment/call inference.
"""
from pathlib import Path
from html import escape
import math
from .storage import write_json

def text(x,y,label,size=15,color='#203a54',anchor='middle'):
    return f'<text x="{x}" y="{y}" font-family="Microsoft YaHei,PingFang SC,sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}">{escape(str(label))}</text>'

def render_composition(payload,path):
    cs=payload['components'];relations=payload['relations'];pos={};elements=[];backgrounds=[]
    groups=[('外部 Actor',40,240,{'外部Actor（人类）'}),('UI / 前端',320,260,{'UI/前端'}),
      ('系统内部：用例 / Service',620,850,{'用例','内部服务','系统边界'}),
      ('外部系统 / 服务 / 资源',1510,300,{'外部Actor（系统）','外部数据库','外部资源'})]
    reserved={t for g in groups for t in g[3]}
    middle=[c for c in cs if c['composition_type'] in groups[2][3]]
    externals=[c for c in cs if c['composition_type'] in groups[3][3]]
    height=max(440,math.ceil(len(middle)/3)*100+110,len(externals)*100+110,
      max((sum(c['composition_type'] in ts for c in cs)*100+110 for _,_,_,ts in groups[:2]),default=440))
    width=1850
    def group(label,x,y,w,h,fill='#f4f8fe'):
        backgrounds.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="#9bb2d0"/>');elements.append(text(x+16,y+27,label,17,anchor='start'))
    def node(c,x,y,w=230,h=66):
        oval=c['composition_type']=='用例';pos[c['id']]=(x,y,w,h)
        tag=(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}"' if oval else f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"')
        elements.append(tag+f' data-node-id="{escape(c["id"],quote=True)}" fill="#eaf1fc" stroke="#457ac7"/>')
        label=c['name'];chunks=[label[i:i+19] for i in range(0,len(label),19)]
        for j,line in enumerate(chunks):elements.append(text(x+w/2,y+h/2-(len(chunks)-1)*9+j*18+5,line,14))
        if '人类' in c['composition_type']:
            elements.append(f'<g stroke="#457ac7" fill="none"><circle cx="{x+13}" cy="{y+12}" r="5"/><path d="M{x+13} {y+17}v15m-8 -10h16m-8 10l-7 9m7 -9l7 9"/></g>')
        if c['source_status']=='inferred':elements.append(text(x+w-8,y+h-6,'推断',10,anchor='end'))
    for label,x,w,types in groups:
        group(label,x,55,w,height)
        rows=[c for c in cs if c['composition_type'] in types]
        cols=3 if x==620 else 1
        for idx,c in enumerate(rows):
            row,col=divmod(idx,cols);node(c,x+16+col*275,110+row*100,240 if cols==3 else w-32)
    below=height+90
    for label,types in [('内部资源 / 数据库 / LLM',{'内部数据库','内部资源','AI模型'}),('连接设备',{'连接设备'}),('部署硬件 / 运行环境',{'部署硬件','运行环境'})]:
        rows=[c for c in cs if c['composition_type'] in types];h=max(110,math.ceil(len(rows)/5)*90+45)
        group(label,40,below,1770,h)
        for idx,c in enumerate(rows):row,col=divmod(idx,5);node(c,60+col*350,below+42+row*90,320)
        below+=h+20
    lines=[]
    for r in relations:
        if r['from_id'] not in pos or r['to_id'] not in pos:continue
        a=pos[r['from_id']];b=pos[r['to_id']]
        ax=a[0]+a[2]/2;ay=a[1]+a[3]/2;bx=b[0]+b[2]/2;by=b[1]+b[3]/2
        if ax<=bx:ax=a[0]+a[2];bx=b[0]
        else:ax=a[0];bx=b[0]+b[2]
        lines.append(f'<line data-relation="{escape(r["relation"],quote=True)}" x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#7b98c1" opacity="0.8"/>')
    title=text(40,32,'系统组成总览',25,anchor='start')
    # Lines are behind nodes and cannot obscure names.
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{below+25}" viewBox="0 0 {width} {below+25}"><rect width="100%" height="100%" fill="white"/>'+title+''.join(backgrounds)+''.join(lines)+''.join(elements)+'</svg>'
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(svg,encoding='utf8')
    write_json(p.with_suffix('.layout.json'),{'nodes':pos,'relations':relations,'source':'partitioned participation view, adapted from 52b4a30'})
    return p
