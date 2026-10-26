"""Editable layered SSD with explicit, saved RR->SR refinement bands."""
from pathlib import Path
from html import escape
import textwrap

PALETTE=('#2563eb','#7c3aed','#0f766e','#c2410c','#be185d','#0369a1')

def ordered_messages(value):
    rows=value['interactions'];by_id={i['id']:i for i in rows};used=set();out=[]
    links={x['rr_id']:x for x in value['rr_sr_links'] if x['status']=='confirmed'}
    for rr in sorted((i for i in rows if i['layer']=='RR'),key=lambda i:i['sequence']):
        out.append(rr);used.add(rr['id'])
        link=links.get(rr['id'])
        if link:
            for sid in sorted(link['sr_ids'],key=lambda sid:by_id[sid]['sequence']):
                if sid not in used:out.append(by_id[sid]);used.add(sid)
    return out,[i for i in rows if i['id'] not in used]

def render_fused_ssd(value,path):
    ordered,pending=ordered_messages(value);rows=ordered+sorted(pending,key=lambda i:(i['layer'],i['sequence']))
    by_id={i['id']:i for i in rows}
    links=[l for l in value['rr_sr_links'] if l['status']=='confirmed' and l['rr_id'] in by_id and l['sr_ids'] and all(k in by_id for k in l['sr_ids'])]
    links.sort(key=lambda l:by_id[l['rr_id']]['sequence'])
    ownership={};rrlinks={}
    for n,link in enumerate(links):
        info={'tag':str(n+1),'color':PALETTE[n%len(PALETTE)],'link':link};rrlinks[link['rr_id']]=info
        for sid in link['sr_ids']:ownership[sid]=info
    parties=list(dict.fromkeys((i['layer'],p['name']) for i in rows for p in (i['sender'],i['receiver'])))
    # Keep abstraction layers separate; the corridor carries actual saved links.
    parties.sort(key=lambda p:0 if p[0]=='RR' else 1)
    x={p:160+j*310 for j,p in enumerate(parties)};w=max(900,len(parties)*310+50)
    legends=[]
    for l in links:
        rr=by_id[l['rr_id']];sr=[str(by_id[k]['sequence']) for k in l['sr_ids']]
        legends.append((rrlinks[rr['id']],f"RR {rr['sequence']} → SR {', '.join(sr)}"))
    legend_rows=(len(legends)+2)//3;header=104+legend_rows*28;lifetop=header+20;start=lifetop+75
    labels=[]
    for i in rows:
        info=rrlinks.get(i['id']) or ownership.get(i['id']);tag=f"[{info['tag']}] " if info else ''
        label=f"{tag}{i['layer']} {i['sequence']}. {i['operation']['name']}"
        if i['data']['sequence']:label+=' | '+', '.join(p['name'] for p in i['data']['sequence'])
        if i['api_id']:label+=' | '+i['api_id']
        labels.append(textwrap.wrap(label,52) or [''])
    heights=[max(102,len(t)*19+49) for t in labels];h=start+sum(heights)+50
    locations={};y=start
    for i,rh in zip(rows,heights):locations[i['id']]=(y,y+rh-20,rh);y+=rh
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, Microsoft YaHei, sans-serif">',
       '<title>RR / SR 完整SSD及已确认展开对应</title><desc>同色编号表示已保存的RR到SR对应；一条RR可以展开为多个SR交互。仅绘制confirmed关系，不推断缺失对应。</desc>',
       '<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0 0L9 3L0 6" fill="context-stroke"/></marker></defs><rect width="100%" height="100%" fill="white"/>',
       '<text x="30" y="32" font-size="22" fill="#163652">RR / SR 完整 SSD</text>',
       '<text x="30" y="58" font-size="13" fill="#5b708a">同色编号与展开框表示已确认对应 · RR业务操作 → SR接口调用及内部展开 · 不同层的同名参与方分别保留</text>']
    for n,(info,label) in enumerate(legends):
        lx=30+(n%3)*min(560,(w-60)//3);ly=86+(n//3)*28
        s.append(f'<rect x="{lx}" y="{ly-16}" width="26" height="21" rx="5" fill="{info["color"]}"/><text x="{lx+13}" y="{ly}" fill="white" font-size="12" text-anchor="middle">{info["tag"]}</text><text x="{lx+36}" y="{ly}" font-size="13" fill="{info["color"]}">{escape(label)}</text>')
    srcenters=[cx for (layer,_),cx in x.items() if layer=='SR'];rrcenters=[cx for (layer,_),cx in x.items() if layer=='RR']
    if srcenters and rrcenters:
        left=min(srcenters)-145;right=max(srcenters)+145;corridor=(max(rrcenters)+min(srcenters))/2
        for l in links:
            info=rrlinks[l['rr_id']];color=info['color'];ys=[locations[k] for k in l['sr_ids']];top=min(v[0] for v in ys);bottom=max(v[0]+v[2] for v in ys)-5;rry=locations[l['rr_id']][1]
            compact=', '.join(str(by_id[k]['sequence']) for k in l['sr_ids'])
            s.append(f'<g data-rr-id="{escape(l["rr_id"],quote=True)}" data-sr-ids="{escape(" ".join(l["sr_ids"]),quote=True)}"><title>{escape(l.get("basis", "已保存的展开对应"))}</title><rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" rx="10" fill="{color}" fill-opacity="0.035" stroke="{color}" stroke-opacity="0.35" stroke-dasharray="5 4"/><path d="M{max(rrcenters)+4} {rry} H{corridor} V{top+12} H{left}" fill="none" stroke="{color}" stroke-width="1.6"/><text x="{left+12}" y="{top+18}" font-size="12" fill="{color}">[{info["tag"]}] RR {by_id[l["rr_id"]]["sequence"]} 展开 → SR {compact}</text></g>')
    for (layer,name),cx in x.items():
        s.append(f'<rect x="{cx-140}" y="{lifetop}" width="280" height="58" rx="8" fill="{"#e8f1ff" if layer=="RR" else "#fff2d8"}" stroke="#457ac7"/>')
        for j,line in enumerate([layer]+(textwrap.wrap(name,25) or [''])):s.append(f'<text x="{cx}" y="{lifetop+20+j*15}" font-size="13" text-anchor="middle">{escape(line)}</text>')
        s.append(f'<line x1="{cx}" y1="{lifetop+60}" x2="{cx}" y2="{h-30}" stroke="#acbcd1" stroke-dasharray="5 4"/>')
    for i,ls in zip(rows,labels):
        y,yy,rh=locations[i['id']];a=x[(i['layer'],i['sender']['name'])];b=x[(i['layer'],i['receiver']['name'])]
        info=rrlinks.get(i['id']) or ownership.get(i['id']);color=info['color'] if info else '#64748b'
        for j,t in enumerate(ls):s.append(f'<text x="{(a+b)/2}" y="{y+37+j*19}" text-anchor="middle" font-size="13" fill="{color}">{escape(t)}</text>')
        dash=' stroke-dasharray="6 4"' if i['direction']=='return' else ''
        if a==b:s.append(f'<path data-message-id="{escape(i["id"],quote=True)}" d="M{a} {yy}h45v20h-45" stroke="{color}" fill="none" marker-end="url(#a)"/>')
        else:s.append(f'<line data-message-id="{escape(i["id"],quote=True)}" x1="{a}" y1="{yy}" x2="{b}" y2="{yy}" stroke="{color}"{dash} marker-end="url(#a)"/>')
        if i['layer']=='RR' and i['id'] not in rrlinks:
            s.append(f'<text x="{(a+b)/2}" y="{yy+18}" font-size="12" text-anchor="middle" fill="#b45309">未保存已确认的SR对应</text>')
        if i in pending and i['layer']=='SR':s.append(f'<text x="{min(srcenters)-130}" y="{yy+18}" font-size="12" fill="#b45309">未保存已确认的RR归属</text>')
    s.append('</svg>');Path(path).write_text(''.join(s),encoding='utf8')
