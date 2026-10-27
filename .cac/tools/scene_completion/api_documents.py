"""Build interface work items from the complete mapped catalog, without a second LLM catalog."""
import re
from .storage import fingerprint

def case_parameters(inputs,views):
    """Retain only evidenced interfaces used by this case; do not guess unknown IDs."""
    from .interaction_enrichment import resolved_api_id
    rows=views['interactions']
    context={**inputs,'rr-ssd':{'interactions':[i for i in rows if i['layer']=='RR']},'sr-ssd':{'interactions':[i for i in rows if i['layer']=='SR']}}
    used={i.get('associated_api') or resolved_api_id(i,context) for i in rows}
    used.discard(None)
    if not used:return {'apis':[]}
    return {'apis':[a for a in inputs['api-parameters']['apis'] if a['id'] in used]}

def index_interfaces(inputs):
    docs={d['source_id']:d for d in inputs['SR']};found={}
    for service in inputs['api-map']['services']:
        for api in service['interfaces']:
            signature=(api.get('method'),api.get('address'))
            if api['id'] in found:
                if found[api['id']][0]!=signature:raise ValueError('同一接口标识对应不同方法/地址，请确认接口身份')
                continue
            spans=[]
            for sid,d in docs.items():
                lines=d['lines'];headings=[]
                for n,row in enumerate(lines):
                    match=re.match(r'^(#{1,6})\s+(.+)',row['text'])
                    if match:headings.append((n,len(match[1]),match[2]))
                targets=[(r['line_start'],r['line_end']) for r in api['source_refs'] if r['source_id']==sid]
                tokens=[x for x in (api['id'],api.get('address')) if x]
                patterns=[re.compile(re.escape(t)+(r'(?![A-Za-z0-9_/{}-])' if t.startswith('/') else r'(?![A-Za-z0-9_-])')) for t in tokens]
                targets += [(row['number'],row['number']) for row in lines if any(pattern.search(row['text']) for pattern in patterns)]
                for start,end in targets:
                    position=next((n for n,row in enumerate(lines) if row['number']>=start),None)
                    if position is None:continue
                    # Only expand an interface-specific ancestor, never a whole
                    # shared API chapter/table. Positive projection stays intact.
                    enclosing=[]
                    for n,level,title in headings:
                        stop=next((m for m,l,_ in headings if m>n and l<=level),len(lines))
                        if n<=position<stop and any(t in title for t in (api['id'],api['name']) if t):enclosing.append((n,stop))
                    if enclosing:
                        lo,hi=max(enclosing,key=lambda span:span[0]);start=lines[lo]['number'];end=lines[hi-1]['number']
                    spans.append({'source_id':sid,'start':start,'end':end})
            unique={fingerprint(s):s for s in spans}
            if not unique:raise ValueError('接口没有可定位的正向原文依据：'+api['id'])
            found[api['id']]=(signature,{'id':api['id'],'name':api['name'],'source_ranges':list(unique.values()),'source_refs':api['source_refs']})
    return {'apis':[entry for _,entry in found.values()]}


def explicit_http_interfaces(documents):
    """Literal method/path declarations and calls, not inferred endpoint names."""
    found={}
    from .http_interfaces import declarations
    for d in documents:
        for row in d['lines']:
            for method,path in declarations(row['text']):
                found.setdefault((method,path),{'source_id':d['source_id'],'line_start':row['number'],'line_end':row['number'],'quote':row['text']})
    return found
