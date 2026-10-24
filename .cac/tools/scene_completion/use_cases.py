"""Source-bounded use-case catalogues, correspondence and fused SSD validation."""
from copy import deepcopy
from .contracts import obj,arr,S,STR,REFS,enum,INTERACTION,SCHEMAS,INPUT_KEYS,TASKS

def declared_case_ids(documents):
    """Explicit metadata identifiers, without assuming a numbering convention."""
    import re
    found=set()
    for d in documents:
        for row in d['lines']:
            text=row['text']
            match=re.match(r'^\s*\|\s*(?:用例编号|用例ID|Use\s*case\s*(?:ID|Identifier))\s*\|\s*([^|]+)\|',text,re.I)
            if not match:match=re.match(r'^\s*(?:[-*]\s*)?(?:\*\*)?(?:用例编号|用例ID|Use\s*case\s*ID)(?:\*\*)?\s*[:：]\s*(.+?)\s*$',text,re.I)
            if not match:continue
            identifier=match[1].strip().strip('`* ')
            if identifier and len(identifier)<=120 and not re.search(r'\s',identifier) and identifier.casefold() not in {'待定','待补充','tbd','n/a','—','-'}:found.add(identifier)
    return found

CASE=obj(id=S,name=S,goal=S,actors=arr(S),layer=enum('RR','SR'),source_ranges=arr(obj(source_id=S,start={'type':'integer','minimum':1},end={'type':'integer','minimum':1})),source_refs=REFS)

def canonical_case_ids(value,inputs):
    """Normalize only declared source-case aliases to their confirmed group ID.

    This is identifier normalization, not semantic case matching. Other IDs are
    deliberately left untouched so that scope validation still rejects them.
    """
    result=deepcopy(value);group=inputs.get('case-group',{})
    if group.get('status')!='confirmed' or not group.get('id'):return result
    for row in result.get('interactions',[]):
        aliases=group.get('rr_ids' if row.get('layer')=='RR' else 'sr_ids',[]) if row.get('layer') in ('RR','SR') else []
        if row.get('case_id') in aliases:row['case_id']=group['id']
    return result
CASE_GROUP=obj(id=S,rr_ids=arr(S),sr_ids=arr(S),status=enum('confirmed','pending'),reason=S,source_refs=REFS)
FUSED_LINK=obj(rr_id=S,sr_ids=arr(S),status=enum('confirmed','pending'),basis=S,source_refs=REFS)

def register():
    SCHEMAS.update({'use-case-extract':obj(cases=arr(CASE)),
      'use-case-align':obj(groups=arr(CASE_GROUP)),
      'fused-ssd':obj(interactions=arr(INTERACTION),rr_sr_links=arr(FUSED_LINK),pending=arr(obj(interaction_id=S,reason=S,source_refs=REFS)))})
    INPUT_KEYS.update({'use-case-extract':{'documents','layer'},'use-case-align':{'rr-cases','sr-cases'},
      'fused-ssd':{'RR','SR','components','case-group'}})
    TASKS.update({'use-case-extract':('scene-use-cases','用例抽取'),'use-case-align':('scene-use-case-align','RR/SR用例对应'),'fused-ssd':('scene-fused-ssd','完整SSD建模')})

def select_documents(documents,entries,all_entries=None):
    """Use only selected source ranges; preserve channels and original line numbers."""
    spans={}
    for c in entries:
        for span in c['source_ranges']:spans.setdefault(span['source_id'],[]).append((span['start'],span['end']))
    result=[]
    for d in documents:
        ranges=spans.get(d['source_id'],[])
        if all_entries and d['channel']=='existing':
            starts=sorted({sp['start'] for c in all_entries for sp in c['source_ranges'] if sp['source_id']==d['source_id']})
            last=max((r['number'] for r in d['lines']),default=0)
            expanded=[]
            for a,b in ranges:
                end=next((start-1 for start in starts if start>a),last)
                # Include this use case's exception sections, but stop at the
                # next peer/parent Markdown section (e.g. a global appendix).
                line=next((r for r in d['lines'] if r['number']==a),None)
                import re
                heading=re.match(r'^(#{1,6})\s+',line['text']) if line else None
                if heading:
                    level=len(heading[1])
                    next_section=next((r['number']-1 for r in d['lines'] if r['number']>a and (m:=re.match(r'^(#{1,6})\s+',r['text'])) and len(m[1])<=level),last)
                    end=min(end,max(b,next_section))
                expanded.append((a,end))
            ranges=expanded
        rows=[deepcopy(r) for r in d['lines'] if any(a<=r['number']<=b for a,b in ranges)]
        if rows:result.append({**d,'lines':rows})
    return result

def validate_catalogue(task,value,inputs):
    if task=='use-case-extract':
        occupied={};ids=set();docs={d['source_id']:d for d in inputs['documents']}
        for c in value['cases']:
            if c['id'] in ids or c['layer']!=inputs['layer']:raise ValueError('duplicate use case or wrong source layer')
            ids.add(c['id'])
            if not c['source_ranges']:raise ValueError('use case must identify source range')
            # Formal metadata must be inside the chosen use case. A same-named
            # brief summary cannot stand in for its detailed request/return flow.
            import re
            metadata=[]
            for d in inputs['documents']:
                for row in d['lines']:
                    m=re.match(r'^\s*\|\s*(?:用例编号|用例ID|Use\s*case\s*ID)\s*\|\s*([^|]+)\|',row['text'],re.I)
                    if m and m[1].strip().strip('`* ')==c['id']:metadata.append((d['source_id'],row['number']))
            if metadata and not all(any(span['source_id']==sid and span['start']<=n<=span['end'] for span in c['source_ranges']) for sid,n in metadata):
                raise ValueError('use case '+c['id']+' must select the detailed section containing its explicit 用例编号 metadata; the brief summary is not the modeling source')
            for span in c['source_ranges']:
                d=docs.get(span['source_id']);numbers={x['number'] for x in d['lines']} if d else set()
                indexed=any(s['line_start']==span['start'] and s['line_end']==span['end'] for doc in inputs.get('source-index',{}).get('documents',[]) if doc['source_id']==span['source_id'] for s in doc['sections'])
                for a,b,owner in occupied.get(span['source_id'],[]):
                    if owner!=c['id'] and span['start']<=b and a<=span['end']:raise ValueError('overlapping use-case source ranges')
                occupied.setdefault(span['source_id'],[]).append((span['start'],span['end'],c['id']))
                if (not indexed and (span['start'] not in numbers or span['end'] not in numbers)) or span['start']>span['end']:raise ValueError('case range outside source/index')
        if inputs['documents'] and not value['cases']:raise ValueError('no use cases extracted; document needs review')
        missing=declared_case_ids(inputs['documents'])-ids
        if missing:raise ValueError('用例目录遗漏原文明示的用例编号，不能用业务模块/用例组代替单个用例：'+', '.join(sorted(missing)))
    elif task=='use-case-align':
        rr={c['id'] for c in inputs['rr-cases']['cases']};sr={c['id'] for c in inputs['sr-cases']['cases']};seen=set();covered_rr=set();covered_sr=set()
        for g in value['groups']:
            if g['id'] in seen or not set(g['rr_ids'])<=rr or not set(g['sr_ids'])<=sr:raise ValueError('invalid use-case correspondence')
            if not g['rr_ids'] and not g['sr_ids']:raise ValueError('empty correspondence')
            if g['status']=='confirmed' and (not g['rr_ids'] or not g['sr_ids']):raise ValueError('unpaired case must remain pending')
            if g['status']=='confirmed' and len(g['rr_ids'])!=1:raise ValueError('每个confirmed对应组必须以一个RR用例为单位，允许一个RR对应多个SR，不得合并不同RR用例')
            if covered_rr&set(g['rr_ids']):raise ValueError('one RR use case cannot belong to competing groups; use a single one-to-many group')
            seen.add(g['id']);covered_rr.update(g['rr_ids']);covered_sr.update(g['sr_ids'])
        if covered_rr!=rr or covered_sr!=sr:raise ValueError('catalogue entries must be matched or explicitly pending')
    elif task=='fused-ssd':
        rows=value['interactions'];ids={r['id']:r for r in rows}
        if len(ids)!=len(rows) or not rows:raise ValueError('empty SSD or duplicate message id')
        orders=set()
        for i in rows:
            from .source_documents import validate_evidence
            try:validate_evidence(i['source_refs']+i['operation']['source_refs'],inputs[i['layer']])
            except ValueError as exc:raise ValueError('message '+i['id']+' ('+i['layer']+'): '+str(exc)) from exc
            if i['case_id']!=inputs['case-group']['id']:raise ValueError('SSD outside selected case group')
            k=(i['layer'],i['sequence'])
            if k in orders:raise ValueError('duplicate layer-local SSD order')
            orders.add(k)
            if i['parent_id']:
                parent=ids.get(i['parent_id'])
                if not parent or parent['layer']!=i['layer'] or parent['sequence']>=i['sequence']:raise ValueError('message '+i['id']+' parent/reply_to must precede message within its layer and reference an earlier request; cross-layer mapping belongs only to refinements/rr_sr_links')
                if i['direction']=='return' and (parent['direction']!='request' or parent['sender']['name']!=i['receiver']['name'] or parent['receiver']['name']!=i['sender']['name']):raise ValueError('return must reverse its request endpoints: '+i['id']+' replies to '+parent['id']+' but sends '+i['sender']['name']+' -> '+i['receiver']['name']+'; required reverse endpoints are '+parent['receiver']['name']+' -> '+parent['sender']['name']+'. If this is a new downstream resource call, keep evidenced endpoints and use direction=request, reply_to=null; do not invent or alter parties to pass validation.')
            elif i['direction']=='return':raise ValueError('return requires its request id')
        linked_rr=set();sr_owner={}
        for link in value['rr_sr_links']:
            if link['rr_id'] not in ids or ids[link['rr_id']]['layer']!='RR':raise ValueError('rr_sr_links.rr_id must reference an RR message ID, not a use-case ID; allowed: '+', '.join(i['id'] for i in rows if i['layer']=='RR'))
            if any(k not in ids or ids[k]['layer']!='SR' for k in link['sr_ids']):raise ValueError('rr_sr_links.sr_ids must reference SR message IDs, not use-case IDs; allowed: '+', '.join(i['id'] for i in rows if i['layer']=='SR'))
            if link['status']=='confirmed' and not link['sr_ids']:raise ValueError('confirmed refinement needs SR messages')
            if link['rr_id'] in linked_rr:raise ValueError('Each RR message needs at most one rr_sr_links entry; combine its SR message IDs into one sr_ids list: '+link['rr_id'])
            linked_rr.add(link['rr_id'])
            if link['status']=='confirmed':
                for sid in link['sr_ids']:
                    if sid in sr_owner and sr_owner[sid]!=link['rr_id']:raise ValueError('SR message is assigned to conflicting RR expansions: '+sid)
                    sr_owner[sid]=link['rr_id']
        # Existing validators check evidence, request/return fields, and known constraints.
        from .validation import validate_result
        for layer in ('RR','SR'):
            selected=[i for i in rows if i['layer']==layer]
            if not selected:raise ValueError('fused SSD must preserve RR and SR views')
            validate_result(layer.lower()+'-ssd',{'interactions':selected},inputs)

register()
