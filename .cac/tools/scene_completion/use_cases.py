"""Source-bounded use-case catalogues, correspondence and fused SSD validation."""
from copy import deepcopy
from .contracts import obj,arr,S,STR,REFS,enum,INTERACTION,SCHEMAS,INPUT_KEYS,TASKS

CASE=obj(id=S,name=S,goal=S,actors=arr(S),layer=enum('RR','SR'),source_ranges=arr(obj(source_id=S,start={'type':'integer','minimum':1},end={'type':'integer','minimum':1})),source_refs=REFS)
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
            ranges=[(a,next((start-1 for start in starts if start>a),last)) for a,b in ranges]
        rows=[deepcopy(r) for r in d['lines'] if any(a<=r['number']<=b for a,b in ranges)]
        if rows:result.append({**d,'lines':rows})
    return result

def validate_catalogue(task,value,inputs):
    if task=='use-case-extract':
        ids=set();docs={d['source_id']:d for d in inputs['documents']}
        for c in value['cases']:
            if c['id'] in ids or c['layer']!=inputs['layer']:raise ValueError('duplicate use case or wrong source layer')
            ids.add(c['id'])
            if not c['source_ranges']:raise ValueError('use case must identify source range')
            for span in c['source_ranges']:
                d=docs.get(span['source_id']);numbers={x['number'] for x in d['lines']} if d else set()
                if span['start'] not in numbers or span['end'] not in numbers or span['start']>span['end']:raise ValueError('case range outside source')
        if inputs['documents'] and not value['cases']:raise ValueError('no use cases extracted; document needs review')
    elif task=='use-case-align':
        rr={c['id'] for c in inputs['rr-cases']['cases']};sr={c['id'] for c in inputs['sr-cases']['cases']};seen=set();covered_rr=set();covered_sr=set()
        for g in value['groups']:
            if g['id'] in seen or not set(g['rr_ids'])<=rr or not set(g['sr_ids'])<=sr:raise ValueError('invalid use-case correspondence')
            if not g['rr_ids'] and not g['sr_ids']:raise ValueError('empty correspondence')
            if g['status']=='confirmed' and (not g['rr_ids'] or not g['sr_ids']):raise ValueError('unpaired case must remain pending')
            if covered_rr&set(g['rr_ids']):raise ValueError('one RR use case cannot belong to competing groups; use a single one-to-many group')
            seen.add(g['id']);covered_rr.update(g['rr_ids']);covered_sr.update(g['sr_ids'])
        if covered_rr!=rr or covered_sr!=sr:raise ValueError('catalogue entries must be matched or explicitly pending')
    elif task=='fused-ssd':
        rows=value['interactions'];ids={r['id']:r for r in rows}
        if len(ids)!=len(rows) or not rows:raise ValueError('empty SSD or duplicate message id')
        orders=set()
        for i in rows:
            if i['case_id']!=inputs['case-group']['id']:raise ValueError('SSD outside selected case group')
            k=(i['layer'],i['sequence'])
            if k in orders:raise ValueError('duplicate layer-local SSD order')
            orders.add(k)
            if i['parent_id']:
                parent=ids.get(i['parent_id'])
                if not parent or parent['layer']!=i['layer'] or parent['sequence']>=i['sequence']:raise ValueError('parent must precede message within its layer')
                if i['direction']=='return' and (parent['direction']!='request' or parent['sender']['name']!=i['receiver']['name'] or parent['receiver']['name']!=i['sender']['name']):raise ValueError('return must reverse its request endpoints')
            elif i['direction']=='return':raise ValueError('return requires its request id')
        for link in value['rr_sr_links']:
            if link['rr_id'] not in ids or ids[link['rr_id']]['layer']!='RR':raise ValueError('unknown RR refinement source')
            if any(k not in ids or ids[k]['layer']!='SR' for k in link['sr_ids']):raise ValueError('unknown SR refinement target')
            if link['status']=='confirmed' and not link['sr_ids']:raise ValueError('confirmed refinement needs SR messages')
        # Existing validators check evidence, request/return fields, and known constraints.
        from .validation import validate_result
        for layer in ('RR','SR'):
            selected=[i for i in rows if i['layer']==layer]
            if not selected:raise ValueError('fused SSD must preserve RR and SR views')
            validate_result(layer.lower()+'-ssd',{'interactions':selected},inputs)

register()
