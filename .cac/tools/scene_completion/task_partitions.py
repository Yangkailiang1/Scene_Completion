"""Small, independently schedulable semantic tasks; parent artifacts stay complete."""
from copy import deepcopy
import re
from .storage import fingerprint
from .source_documents import evidence_refs

def _documents_at(documents,refs):
    ranges={}
    for r in refs:ranges.setdefault(r['source_id'],set()).update(range(r['line_start'],r['line_end']+1))
    return [{**d,'lines':[r for r in d['lines'] if r['number'] in ranges.get(d['source_id'],set())]} for d in documents if any(r['number'] in ranges.get(d['source_id'],set()) for r in d['lines'])]

def split_task(task,inputs):
    if task=='normal-rules':
        from .inverse_alignment import canonical_fused
        units=[]
        for i in canonical_fused(inputs['fused-ssd'])['interactions']:
            if i['direction']!='request':continue
            q=deepcopy(inputs);q['fused-ssd']={'interactions':[deepcopy(i)],'rr_sr_links':[],'pending':[]}
            units.append((i['id'],q))
        return units
    if task in {'concern-match','exception-generate'}:
        from .interaction_enrichment import interactions
        rows=interactions(inputs);requests=[i for i in rows if i['direction']=='request'];units=[]
        for request in requests:
            ids={request['id']}|{i['id'] for i in rows if i['direction']=='return' and i.get('parent_id')==request['id']}
            q=deepcopy(inputs)
            for key in ('rr-ssd','sr-ssd','enriched-interactions'):
                if key in q:q[key]['interactions']=[i for i in q[key]['interactions'] if i['id'] in ids]
            if 'concern-match' in q:q['concern-match']={k:[m for m in v if m['interaction_id'] in ids] for k,v in q['concern-match'].items()}
            if 'normal-rules' in q:q['normal-rules']={'rules':[r for r in q['normal-rules']['rules'] if r['interaction_id'] in ids],'pending':[r for r in q['normal-rules'].get('pending',[]) if r['interaction_id'] in ids]}
            if 'normal-documents' in q and 'normal-rules' in q:q['normal-documents']=_documents_at(q['normal-documents'],evidence_refs(q['normal-rules']))
            units.append((request['id'],q))
        # A return without a modeled request must not silently disappear.
        covered={i['id'] for _,q in units for key in ('rr-ssd','sr-ssd') for i in q.get(key,{}).get('interactions',[])}
        missing=[i for i in rows if i['id'] not in covered]
        if missing:
            q=deepcopy(inputs)
            for key in ('rr-ssd','sr-ssd','enriched-interactions'):
                if key in q:q[key]['interactions']=[i for i in q[key]['interactions'] if i['id'] in {m['id'] for m in missing}]
            units.append(('unpaired-returns',q))
        return units
    if task in {'existing-bind','existing-extract'}:
        units=[]
        for branch in inputs.get('branches',{}).get('branches',[]):
            q=deepcopy(inputs);q['branches']={'branches':[deepcopy(branch)]}
            if 'bindings' in q:q['bindings']={'bindings':[b for b in q['bindings']['bindings'] if b['branch_id']==branch['id']]}
            if 'existing-documents' in q:q['existing-documents']=_documents_at(q['existing-documents'],branch['source_refs'])
            units.append((branch['id'],q))
        return units
    if task=='test-ground-truth':
        units=[]
        for d in inputs['test-documents']:
            rows=[r for r in d['lines'] if re.match(r'^\s*\|',r['text']) and re.search(r'\bTEST[-_][A-Za-z0-9_-]+',r['text'])]
            for row in rows:
                if not re.search(r'异常|可选|exception|optional',row['text'],re.I):continue
                q=deepcopy(inputs);q['test-documents']=[{**d,'lines':[row]}]
                units.append((d['source_id']+':'+str(row['number']),q))
        return units or ([('document',deepcopy(inputs))] if inputs['test-documents'] else [])
    return [('all',deepcopy(inputs))]

def merge_parts(task,parts):
    from .exception_generation import deduplicate
    if task in {'exception-generate','existing-extract','test-ground-truth'}:
        out={'scenarios':deduplicate([s for p in parts for s in p.get('scenarios',[])])}
        from .exception_generation import scenario_key
        for s in out['scenarios']:
            s.setdefault('source_scenario_id',s['id'])
            s['id']=task+'-'+fingerprint([scenario_key(s),s.get('field'),s.get('rule_id')])[:20]
        if task in {'exception-generate','test-ground-truth'}:out['pending']=list({fingerprint(p):p for v in parts for p in v.get('pending',[])}.values())
        return out
    keys={'normal-rules':('rules','pending'),'concern-match':('matches','pending'),'existing-bind':('bindings',)}[task]
    return {key:list({fingerprint(r):r for p in parts for r in p.get(key,[])}.values()) for key in keys}
