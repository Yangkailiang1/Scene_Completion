"""Task-specific model views; retained artifacts keep the full validated contract."""
from copy import deepcopy
import re


def ssd_context(inputs):
    """Select only identities mentioned/evidenced in this paired use case and ancestors.

    This tool does not discover new actors or infer calls. Unresolved identities
    remain a model clarification rather than falling back to the global graph.
    """
    docs=inputs['RR']+inputs['SR']
    text='\n'.join(r['text'] for d in docs for r in d['lines'])
    ranges={d['source_id']:{r['number'] for r in d['lines']} for d in docs}
    components=inputs['components']['components'];selected=set()
    for c in components:
        if c['composition_type']=='用例':continue
        name=c['name']
        table=re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s*表',name)
        pattern=(r'(?<![A-Za-z0-9_])'+re.escape(table[1])+r'\s*表' if table else
          r'(?<![A-Za-z0-9_])'+re.escape(name)+r'(?![A-Za-z0-9_])' if name.isascii() else re.escape(name))
        if re.search(pattern,text,re.I) or any(set(range(r['line_start'],r['line_end']+1)) & ranges.get(r['source_id'],set()) for r in c['source_refs']):selected.add(c['id'])
    while True:
        parents={c['parent_id'] for c in components if c['id'] in selected and c.get('parent_id')}
        if parents<=selected:break
        selected.update(parents)
    if not selected:
        from .scheduler import TaskBlocked
        raise TaskBlocked('awaiting_context',{'reason':'当前用例无法与系统组成身份对应，请确认名称/组成，不回退全量组成图','case':inputs['case-group']['id']})
    return {**deepcopy(inputs),'components':{'components':[deepcopy(c) for c in components if c['id'] in selected],
      'relations':[deepcopy(r) for r in inputs['components'].get('relations',[]) if {r['from_id'],r['to_id']}<=selected]}}


def generation_matches(inputs):
    from .interaction_enrichment import interactions
    from .concern_hierarchy import match_is_applicable
    by_id={i['id']:i for i in interactions(inputs)}
    mechanical={'service.base.availability','service.query_retrieval.resource_existence'}
    from .normal_rules import rule_matches
    indexed={(r['interaction_id'],r['object'],r['concern_key']) for r in rule_matches(inputs)}
    return [deepcopy(m) for m in inputs['concern-match']['matches'] if (m['interaction_id'],m['object'],m['concern_key']) not in indexed and m['interaction_id'] in by_id
      and match_is_applicable(m,by_id[m['interaction_id']],inputs) and m.get('concrete_rule')
      and not m['concern_key'].startswith('api.data.') and m['concern_key'] not in mechanical]


def semantic_view(task,inputs):
    """Remove duplicate views and derived display metadata, never source facts."""
    out=deepcopy(inputs)
    relevant={'normal-rules','concern-match','exception-generate','existing-bind','existing-extract','test-ground-truth'}
    if task not in relevant:return out
    from .inverse_alignment import canonical_fused
    if 'fused-ssd' in out:
        # Inverse binding accepts only canonical interaction IDs, not aliases.
        out['fused-ssd']=canonical_fused(out['fused-ssd'])
        out['fused-ssd'].pop('aliases',None)
        if task=='normal-rules':
            out['fused-ssd']['interactions']=[{k:i[k] for k in ('id','direction','sender','receiver','operation','data','source_refs')} for i in out['fused-ssd']['interactions'] if i['direction']=='request']
    if 'enriched-interactions' in out:
        rows=out.pop('enriched-interactions')['interactions']
        messages=[]
        for i in rows:
            v={k:deepcopy(i[k]) for k in ('id','case_id','sequence','parent_id','layer','sender','receiver','operation','data','direction','api_id','source_refs')}
            v['associated_api']=i.get('associated_api');v['classification']=i.get('classification')
            # Capability unions and repeated resolved concerns are display data;
            # the actual operation is already explicit in each message.
            for role in ('sender','receiver'):
                v[role]={k:v[role][k] for k in ('name','position','source_refs')}
                resource=i[role].get('resource_service')
                if resource:v[role]['resource_service']=resource
            v['data']={'sequence':v['data']['sequence']}
            messages.append(v)
        out['interactions']=messages
        # Explicit field attributes occur once on each actual interaction.
        for key in ('rr-ssd','sr-ssd','api-map','api-parameters','object-operations','components'):out.pop(key,None)
    if task=='exception-generate' and 'concern-match' in out:
        # The full review matrix includes inherited, pending and inapplicable
        # rows for every interaction. Generation receives only semantic checks
        # with an actual rule; mechanical candidates are supplied once by tools.
        keys={'interaction_id','target','object','concern_key','basis','concrete_rule','source_refs','activation_evidence','scope','data_location'}
        matches=[{k:v for k,v in m.items() if k in keys} for m in generation_matches(inputs)]
        out['concern-match']={'matches':matches}
    if 'registry' in out:
        out['registry']['definitions']={key:{k:v for k,v in row.items() if k in {'label','description','guard','kind','operation_kinds','technology','parents'}} for key,row in out['registry']['definitions'].items() if row.get('enabled',True)}
    if task in {'existing-extract','test-ground-truth'}:
        # Original branches/test rows are retained; no duplicate composition or
        # full API table. normal-constraints is already scoped to this use case.
        out.pop('components',None);out.pop('api-map',None)
        if 'normal-rules' in out and task=='existing-extract':out.pop('existing-documents',None)
    if task in {'existing-bind','existing-extract','test-ground-truth'}:
        # Inverse tasks receive positive facts, never the positive generator's
        # derived negative candidates through a shared-rule side channel.
        for rule in out.get('normal-rules',{}).get('rules',[]):rule.pop('violation',None)
        if task=='existing-extract' and 'bindings' in out:
            ids={b['interaction_id'] for b in out['bindings']['bindings'] if b['status']=='confirmed'}
            if ids:
                out['fused-ssd']['interactions']=[i for i in out['fused-ssd']['interactions'] if i['id'] in ids]
                out['normal-rules']['rules']=[r for r in out.get('normal-rules',{}).get('rules',[]) if r['interaction_id'] in ids]
        for i in out.get('fused-ssd',{}).get('interactions',[]):
            for side in ('sender','receiver'):i[side]={k:i[side][k] for k in ('name','position')}
            i['operation']={k:i['operation'][k] for k in ('name','kinds','sequence')}
            i['data']={'sequence':[{k:p[k] for k in ('name','location')} for p in i['data']['sequence']]}
        if 'registry' in out:
            text=str(out.get('fused-ssd',{}))
            techs=({'database'} if '数据库' in text else set())|({'llm'} if any(k in text.lower() for k in ('llm','大语言','large language')) else set())
            out['registry']['definitions']={k:v for k,v in out['registry']['definitions'].items() if not v.get('technology') or v['technology'] in techs}
    return out
