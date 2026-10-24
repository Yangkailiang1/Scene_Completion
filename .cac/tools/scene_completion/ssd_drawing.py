"""Editable layered SSD; refinement links determine SR insertion, never text similarity."""
from pathlib import Path
from html import escape
import textwrap

def ordered_messages(value):
    rows=value['interactions'];by_id={i['id']:i for i in rows};used=set();out=[]
    links={x['rr_id']:x for x in value['rr_sr_links'] if x['status']=='confirmed'}
    for rr in sorted((i for i in rows if i['layer']=='RR'),key=lambda i:i['sequence']):
        out.append(rr);used.add(rr['id'])
        link=links.get(rr['id'])
        if link:
            for sid in sorted(link['sr_ids'],key=lambda sid:by_id[sid]['sequence']):
                if sid not in used:out.append(by_id[sid]);used.add(sid)
    pending=[i for i in rows if i['id'] not in used]
    return out,pending

def render_fused_ssd(value,path):
    ordered,pending=ordered_messages(value);rows=ordered+sorted(pending,key=lambda i:(i['layer'],i['sequence']))
    parties=list(dict.fromkeys((i['layer'],p['name']) for i in rows for p in (i['sender'],i['receiver'])))
    x={p:160+j*310 for j,p in enumerate(parties)};w=max(900,len(parties)*310+50)
    labels=[]
    for i in rows:
        label=f"{i['layer']} {i['sequence']}. {i['operation']['name']}"
        if i['data']['sequence']:label+=' | '+', '.join(p['name'] for p in i['data']['sequence'])
        if i['api_id']:label+=' | '+i['api_id']
        labels.append(textwrap.wrap(label,52) or [''])
    heights=[max(85,len(t)*19+35) for t in labels];h=190+sum(heights)
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0 0L9 3L0 6" fill="#376bb5"/></marker></defs><rect width="100%" height="100%" fill="white"/><text x="30" y="32" font-size="22">RR / SR 完整 SSD</text>']
    for (layer,name),cx in x.items():
        s.append(f'<rect x="{cx-140}" y="55" width="280" height="58" rx="8" fill="{"#e8f1ff" if layer=="RR" else "#fff2d8"}" stroke="#457ac7"/>')
        chunks=textwrap.wrap(name,25) or ['']
        for j,line in enumerate([layer]+chunks):s.append(f'<text x="{cx}" y="{75+j*15}" font-size="13" text-anchor="middle">{escape(line)}</text>')
        s.append(f'<line x1="{cx}" y1="115" x2="{cx}" y2="{h-20}" stroke="#acbcd1" stroke-dasharray="5 4"/>')
    y=130
    pending_ids={i['id'] for i in pending}
    for i,ls,rh in zip(rows,labels,heights):
        if pending and i['id']==pending[0]['id']:s.append(f'<text x="20" y="{y}" font-size="13" fill="#b45309">以下消息缺少已确认的RR展开对应；未猜测其插入位置</text>');y+=20
        a=x[(i['layer'],i['sender']['name'])];b=x[(i['layer'],i['receiver']['name'])];yy=y+rh-20
        for j,t in enumerate(ls):s.append(f'<text x="{(a+b)/2}" y="{y+18+j*19}" text-anchor="middle" font-size="13">{escape(t)}</text>')
        dash=' stroke-dasharray="6 4"' if i['direction']=='return' else ''
        if a==b:s.append(f'<path d="M{a} {yy}h45v20h-45" stroke="#376bb5" fill="none" marker-end="url(#a)"/>')
        else:s.append(f'<line data-message-id="{escape(i["id"],quote=True)}" x1="{a}" y1="{yy}" x2="{b}" y2="{yy}" stroke="#376bb5"{dash} marker-end="url(#a)"/>')
        y+=rh
    s.append('</svg>');Path(path).write_text(''.join(s),encoding='utf8')
