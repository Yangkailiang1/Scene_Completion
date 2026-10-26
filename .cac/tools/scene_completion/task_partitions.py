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
    if task=='test-supplement':
        units=[]
        for i in inputs['fused-ssd']['interactions']:
            if i['direction']!='request':continue
            ids={i['id']}|{x['id'] for x in inputs['fused-ssd']['interactions'] if x.get('parent_id')==i['id']}
            base=deepcopy(inputs);base['fused-ssd']['interactions']=[x for x in base['fused-ssd']['interactions'] if x['id'] in ids]
            rules=[r for r in base['normal-rules']['rules'] if r['interaction_id']==i['id'] and not r['concern_key'].startswith('api.data.') and r['concern_key']!='service.base.availability']
            tool=deepcopy(base);tool['normal-rules']={'rules':[],'pending':[]}
            units.append(('contracts:'+i['id'],tool))
            for rule in rules:
                q=deepcopy(base);q['normal-rules']={'rules':[rule],'pending':[]};q['normal-constraints']={'apis':[]}
                units.append(('business:'+rule['id'],q))
        return units
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
    if task in {'existing-bind','existing-extract','existing-concerns'}:
        units=[]
        for branch in inputs.get('branches',{}).get('branches',[]):
            q=deepcopy(inputs);q['branches']={'branches':[deepcopy(branch)]}
            if 'identified-concerns' in q:q['identified-concerns']={**q['identified-concerns'],'matches':[m for m in q['identified-concerns']['matches'] if not m.get('source_branch_ids') or branch['id'] in m['source_branch_ids']]}
            if 'bindings' in q:q['bindings']={'bindings':[b for b in q['bindings']['bindings'] if b['branch_id']==branch['id']]}
            if 'existing-documents' in q:q['existing-documents']=_documents_at(q['existing-documents'],branch['source_refs'])
            units.append((branch['id'],q))
        return units
    if task in {'test-ground-truth','test-concerns'}:
        from .test_sources import exception_documents
        inputs={**inputs,'test-documents':exception_documents(inputs['test-documents'])}
        units=[]
        for d in inputs['test-documents']:
            rows=[r for r in d['lines'] if re.match(r'^\s*\|',r['text']) and re.search(r'\b(?:TEST|SUP)[-_][A-Za-z0-9_-]+',r['text'])]
            for row in rows:
                from .test_sources import ALIASES,HEADERS,cells
                headers=[r for r in d['lines'] if any(h in cells(r['text']) for h in ALIASES['测试ID'])]
                if headers and len(cells(headers[-1]['text']))==9 and all(h in ALIASES[HEADERS[n]] for n,h in enumerate(cells(headers[-1]['text']))):headers=[]
                q=deepcopy(inputs);q['test-documents']=[{**d,'lines':headers+[row]}]
                if 'identified-concerns' in q:
                    ids=set(re.findall(r'\b(?:TEST|SUP)[-_][A-Za-z0-9_-]+',row['text']))
                    def own(m):
                        if m.get('source_unit_ids'):return bool(set(m['source_unit_ids']) & ids)
                        return any(ref['source_id']==d['source_id'] and ref['line_start']<=row['number']<=ref['line_end'] for ref in m.get('source_refs',[]))
                    q['identified-concerns']={k:[m for m in values if own(m) or m.get('original_id') in ids] for k,values in q['identified-concerns'].items() if k in {'matches','pending','excluded'}}
                units.append((d['source_id']+':'+str(row['number']),q))
        return units or ([('document',deepcopy(inputs))] if inputs['test-documents'] else [])
    return [('all',deepcopy(inputs))]

def merge_parts(task,parts):
    if task=='test-supplement':return {'tests':list({fingerprint(t):t for p in parts for t in p['tests']}.values()),'pending':list({fingerprint(t):t for p in parts for t in p.get('pending',[])}.values())}
    from .exception_generation import deduplicate
    if task in {'exception-generate','existing-extract','test-ground-truth'}:
        out={'scenarios':deduplicate([s for p in parts for s in p.get('scenarios',[])])}
        from .exception_generation import scenario_key
        for s in out['scenarios']:
            s.setdefault('source_scenario_id',s['id'])
            s['id']=task+'-'+fingerprint([scenario_key(s),s.get('field'),s.get('rule_id')])[:20]
        if task in {'exception-generate','test-ground-truth','existing-extract'}:out['pending']=list({fingerprint(p):p for v in parts for p in v.get('pending',[])}.values())
        out['excluded']=[x for p in parts for x in p.get('excluded',[])]
        return out
    keys={'normal-rules':('rules','pending'),'concern-match':('matches','pending'),'existing-concerns':('matches','pending'),'test-concerns':('matches','pending'),'existing-bind':('bindings',)}[task]
    result={key:list({fingerprint(r):r for p in parts for r in p.get(key,[])}.values()) for key in keys}
    if task in {'concern-match','existing-concerns','test-concerns'} and any(p.get('excluded') for p in parts):result['excluded']=[r for p in parts for r in p.get('excluded',[])]
    return result
