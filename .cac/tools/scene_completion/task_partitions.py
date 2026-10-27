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
    if task in {'existing-extract','test-ground-truth'} and inputs.get('identified-concerns'):
        # Keep the existing source-unit partition, then refine independent
        # located object groups. Never split a cross-field constraint itself.
        base={k:v for k,v in inputs.items() if k!='identified-concerns'}
        source_units=split_task(task,base);out=[]
        for unit,q in source_units:
            selected=deepcopy(inputs['identified-concerns'])
            if task=='existing-extract':
                ids={b['id'] for b in q['branches']['branches']}
                selected['matches']=[m for m in selected['matches'] if not m.get('source_branch_ids') or ids & set(m['source_branch_ids'])]
            else:
                refs={(d['source_id'],r['number']) for d in q['test-documents'] for r in d['lines']}
                from .test_sources import records_for_inputs
                source_ids={r['id'] for r in records_for_inputs(q)}
                selected['matches']=[m for m in selected['matches'] if (bool(set(m['source_unit_ids']) & source_ids) if m.get('source_unit_ids') else any((r['source_id'],n) in refs for r in m['source_refs'] for n in range(r['line_start'],r['line_end']+1)))]
                if 'excluded' in selected:selected['excluded']=[m for m in selected['excluded'] if m.get('original_id') in source_ids]
            groups={}
            for m in selected['matches']:
                if m.get('status')!='applicable':continue
                key=(m['interaction_id'],m['target'],m['object'],m.get('data_location'))
                groups.setdefault(key,[]).append(m)
            if len(groups)<=1:
                q['identified-concerns']=selected;out.append((unit,q));continue
            for key,matches in groups.items():
                child=deepcopy(q);child['identified-concerns']={**selected,'matches':matches}
                out.append((unit+':object:'+fingerprint(key)[:12],child))
        return out
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
        from .test_sources import exception_documents,records,records_for_inputs,is_test_header,ALIASES,HEADERS,cells
        if 'test-inventory' not in inputs:inputs={**inputs,'test-documents':exception_documents(inputs['test-documents'])}
        units=[]
        if 'test-inventory' in inputs:
            for record in records_for_inputs(inputs):
                if record['scenario_type']!='exception':continue
                q=deepcopy(inputs);cat=q['test-inventory'];cat['tests']=[t for t in cat['tests'] if t['id']==record['id']];owners={t['case_id'] for t in cat['tests']};cat['cases']=[c for c in cat['cases'] if c['id'] in owners]
                q['test-documents']=_documents_at(inputs['test-documents'],record['source_refs']+[r for c in cat['cases'] for r in c['source_refs']])
                if 'identified-concerns' in q:
                    selected=q['identified-concerns'];selected['matches']=[m for m in selected['matches'] if record['id'] in m.get('source_unit_ids',[]) or not m.get('source_unit_ids') and any(a['source_id']==b['source_id'] and a['line_start']<=b['line_end'] and b['line_start']<=a['line_end'] for a in m['source_refs'] for b in record['source_refs'])]
                units.append((record['source_id']+':'+record['id'],q))
            return units
        for d in inputs['test-documents']:
            for record in records([d]):
                if record['scenario_type']!='exception':continue
                row=next(r for r in d['lines'] if r['number']==record['row'])
                headers=[r for r in d['lines'] if r['number']<row['number'] and is_test_header(cells(r['text']))][-1:]
                if headers and len(cells(headers[-1]['text']))==9 and all(h in ALIASES[HEADERS[n]] for n,h in enumerate(cells(headers[-1]['text']))):headers=[]
                context=[r for r in d['lines'] if r['number'] in record.get('context_rows',[])]
                q=deepcopy(inputs);q['test-documents']=[{**d,'lines':headers+context+[row]}]
                if 'identified-concerns' in q:
                    ids={record['id']}
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
