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
                    # Bold interface labels and peer success-response headings
                    # belong to the same interface until the next API declaration.
                    markers=[n for n,row in enumerate(lines) if re.match(r'^\s*(?:#{1,6}\s*|\*\*)',row['text']) and any(t and t in row['text'] for t in (api['id'],api['name']))]
                    prior=[n for n in markers if n<=position]
                    if prior:
                        lo=max(prior);hi=len(lines)
                        for n in range(lo+1,len(lines)):
                            text=lines[n]['text']
                            if re.match(r'^\s*(?:#{1,6}\s*|\*\*)',text) and re.search(r'API[-–—][A-Za-z0-9]|\b(?:GET|POST|PUT|PATCH|DELETE)\s+/',text) and not any(t and t in text for t in (api['id'],api['address'])):
                                hi=n;break
                            if re.match(r'^\s*#\s+',text):hi=n;break
                        if lo<=position<hi:
                            start=min(start,lines[lo]['number']);end=max(end,lines[hi-1]['number'])
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


def complete_success_responses(value, inputs):
    """Preserve explicit success-response table declarations, without inferred types.

    Only a single-interface task may use this completion. JSON examples alone
    do not declare requiredness or types and are left to the semantic extractor.
    """
    from copy import deepcopy
    interface=inputs.get('interface')
    if not interface:return value
    out=deepcopy(value)
    apis=[a for a in out.get('apis',[]) if a['id']==interface['id']]
    if len(apis)!=1:return out
    api=apis[0];known={(p['location'],p['name']) for p in api['parameters']}
    for doc in inputs.get('SR',[]):
        response=False;headers=None
        for row in doc['lines']:
            text=row['text'].strip()
            if re.match(r'^(?:#{1,6}\s*|\*\*|[-*]\s)',text):
                if re.search(r'API[-–—][A-Za-z0-9]',text) and interface['id'] not in text:
                    response=False;headers=None;continue
                if re.search(r'成功响应|正常响应|响应参数|返回参数|响应体|response\s*(?:body|parameters)|200\s*(?:OK|响应)',text,re.I):response=True;headers=None
                elif re.search(r'请求|request|错误|异常|[45]\d\d',text,re.I):response=False;headers=None
            if not response or not text.startswith('|'):continue
            cells=[c.strip().replace('`','').replace('**','') for c in text.strip('|').split('|')]
            if all(re.fullmatch(r'[:\s-]+',c) for c in cells):continue
            if any(c in {'参数','参数名','参数名称','字段','字段名','字段名称','名称','name','field'} for c in cells):
                headers=cells;continue
            if not headers or len(headers)!=len(cells):continue
            values=dict(zip(headers,cells))
            name=next((values[k] for k in ('参数','参数名','参数名称','字段','字段名','字段名称','名称','name','field') if k in values),'')
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.\[\]-]*',name):continue
            if ('response',name) in known:continue
            dtype=next((values[k] for k in ('数据类型','类型','type','Type') if k in values),None)
            req=next((values[k] for k in ('必填','是否必填','必选','required') if k in values),None)
            required=True if req in {'是','必填','必选','true','True','Y'} else False if req in {'否','可选','false','False','N'} else None
            refs=[{'source_id':doc['source_id'],'line_start':row['number'],'line_end':row['number'],'quote':row['text']}]
            api['parameters'].append({'name':name,'location':'response','data_type':dtype or None,'required':required,'default':None,'constraints':[],'source_refs':refs})
            known.add(('response',name))
    return out
