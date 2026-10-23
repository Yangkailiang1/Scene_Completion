from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .source_documents import validate_evidence,documents_in,evidence_refs
from .interaction_enrichment import interactions,parameters_for
from .exception_generation import scenario_key,data_exceptions,query_matches
def refs_required(value):
    def visit(v):
        if isinstance(v,dict):
            if 'source_refs' in v and not v['source_refs']:
                # Empty refs are allowed only for pending constraints, never known facts.
                if v.get('status')!='pending': raise ValueError('known facts require source evidence')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value)


def validate_result(task, payload, inputs):
    validate(task,payload)
    if task=='gap-recommend':return payload
    docs=documents_in(inputs)
    allowed={fingerprint(r) for r in evidence_refs(inputs)}
    for ref in evidence_refs(payload):
        if fingerprint(ref) not in allowed:
            if not docs:raise ValueError('output uses evidence outside task dependencies')
            validate_evidence(ref,docs)
    refs_required(payload)
    if 'scenarios' in payload and len({s['id'] for s in payload['scenarios']})!=len(payload['scenarios']):raise ValueError('duplicate scenario ID')
    definitions=registry()['definitions']
    def visit(v):
        if isinstance(v,dict):
            if 'concern_key' in v and v['concern_key'] not in definitions:raise ValueError('unregistered concern')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(payload)
    if task=='components':
        ids=[c['id'] for c in payload['components']]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate component ID')
        if any(c['parent_id'] is not None and c['parent_id'] not in ids for c in payload['components']):raise ValueError('unknown parent')
        if any(r['from_id'] not in ids or r['to_id'] not in ids for r in payload['relations']):raise ValueError('unknown relation endpoint')
    if task in {'rr-ssd','sr-ssd'}:
        layer='RR' if task=='rr-ssd' else 'SR'
        seen=set(); ids=set()
        for i in payload['interactions']:
            key=(i['case_id'],i['sequence'])
            if i['layer']!=layer or key in seen or i['id'] in ids:raise ValueError('wrong SSD layer, duplicate ID or order')
            seen.add(key); ids.add(i['id'])
            if not i['operation']['kinds']: raise ValueError('actual operation kind required')
        if any(i['parent_id'] and i['parent_id'] not in ids for i in payload['interactions']):
            raise ValueError('SSD parent must be in the same supplied layer')
    if task in {'api-parameters','rr-ssd','sr-ssd'}:
        params=[p for a in payload.get('apis',[]) for p in a['parameters']]
        params += [p for i in payload.get('interactions',[]) for p in i['data']['sequence']]
        for i in payload.get('interactions',[]):
            if i['direction']=='return' and any(p['location'] in {'header','path','query','body'} for p in i['data']['sequence']):raise ValueError('request fields cannot enter response data')
            if i['direction']=='request' and any(p['location']=='response' for p in i['data']['sequence']):raise ValueError('response fields cannot enter request data')
        for p in params:
            for rule in p['constraints']:
                if rule['status']=='explicit' and rule['value'] is None: raise ValueError('explicit constraint needs a known value')
                if rule['status']=='explicit' and rule['kind']=='type' and p['data_type']!=rule['value']:
                    raise ValueError('known type must be recorded consistently in data_type')
            if p['location']=='path' and p['required'] is False: raise ValueError('path parameters cannot be optional')
    if task=='test-operation-project':
        for item in payload['objects']:
            for op in item['supported_operations']:
                if any(ref['quote']!=op['name'] for ref in op['source_refs']):
                    raise ValueError('test projection quotes must contain only the supported operation name')
                import re
                if re.search(r'异常|错误|失败|预期|缺失|非法|无效|越界|无权限|\b[45]\d\d\b|exception|error|invalid|missing|unauthori|forbidden',op['name'],re.I):
                    raise ValueError('test projection cannot expose exception/response details')
    if task=='object-operations':
        # Capability inputs include only a whitelisted test operation projection.
        validate_result('test-operation-project',inputs['test-operations'],inputs)
        allowed={c['name'] for c in inputs['components']['components']}
        allowed|={p['name'] for i in inputs['rr-ssd']['interactions'] for p in (i['sender'],i['receiver'])}
        allowed|={o['name'] for o in inputs['test-operations']['objects']}
        if any(o['name'] not in allowed for o in payload['objects']):raise ValueError('unsupported capability object')
    if task=='interaction-align':
        comps={c['id'] for c in inputs['components']['components']}
        rr={i['id']:i for i in inputs['rr-ssd']['interactions']};sr={i['id']:i for i in inputs['sr-ssd']['interactions']}
        aliases={}
        for a in payload['aliases']:
            if a['name'] in aliases and aliases[a['name']]!=a['component_id']:raise ValueError('ambiguous component alias')
            aliases[a['name']]=a['component_id']
            if a['component_id'] not in comps:raise ValueError('unknown alias component')
        used=set()
        for link in payload['links']:
            if link['rr_id'] not in rr or any(x not in sr for x in link['sr_ids']):raise ValueError('unknown RR/SR link')
            if link['status']=='confirmed':
                if not link['sr_ids'] or not link['source_refs']:raise ValueError('confirmed link requires evidence')
                for sid in link['sr_ids']:
                    if sid in used or rr[link['rr_id']]['case_id']!=sr[sid]['case_id']:raise ValueError('conflicting expansion')
                    used.add(sid)
    if task in {'concern-match','exception-generate'}:
        by_id={i['id']:i for i in interactions(inputs)}
        for x in payload.get('matches',[])+payload.get('scenarios',[])+payload.get('pending',[]):
            if x['interaction_id'] not in by_id:raise ValueError('unknown actual interaction')
        if task=='concern-match':
            correct_query={(m['interaction_id'],m['object']):m['concern_key'] for m in query_matches(inputs)}
            for m in payload['matches']:
                expected_key=correct_query.get((m['interaction_id'],m['object']))
                if m['target']=='receiver' and expected_key and m['concern_key'].endswith('.resource_existence') and m['concern_key']!=expected_key:raise ValueError('wrong query/database resource concern')
                i=by_id[m['interaction_id']]
                if m['target'] in {'sender','receiver'} and m['object']!=i[m['target']]['name']:
                    raise ValueError('concern party must be actual sender/receiver')
                if set(i['operation']['kinds']) <= {'read','display'} and (m['concern_key'].startswith('service.resource_mutation.') or m['concern_key'] in {'internal_database.persistence','internal_database.idempotency','internal_database.uniqueness'}):
                    raise ValueError('read-only interaction cannot activate mutation concerns')
                if m['target']=='data' and m['object'] not in {p['name'] for p in parameters_for(i,inputs)}:
                    raise ValueError('data concern must identify an actual field')
        else:
            matches={(m['interaction_id'],m['object'],m['concern_key']) for m in inputs['concern-match']['matches']}
            for s in payload['scenarios']:
                i=by_id[s['interaction_id']]
                if s['operation']!=i['operation']['name'] or s['case_id']!=i['case_id'] or s['layer']!=i['layer']:
                    raise ValueError('G must use this SSD operation, case and layer')
                if (s['interaction_id'],s['object'],s['concern_key']) not in matches:
                    raise ValueError('G must have an applicable matched concern')
                if s['source_status']!='framework_inferred' or not s['derivation']:
                    raise ValueError('G requires recorded positive-rule derivation')
                if s['field'] is not None:
                    expected={scenario_key(x) for x in data_exceptions(inputs)}
                    if scenario_key(s) not in expected: raise ValueError('unsupported or invented field exception')
                else:
                    match=[m for m in inputs['concern-match']['matches'] if (m['interaction_id'],m['object'],m['concern_key'])==(s['interaction_id'],s['object'],s['concern_key'])]
                    if not any(m['concrete_rule'] for m in match):raise ValueError('no concrete rule; move to pending')
    if task in {'existing-extract','test-ground-truth'}:
        test_ids={d['source_id'] for d in documents_in(inputs) if d.get('channel')=='test'}
        for s in payload['scenarios']:
            if task=='test-ground-truth' and not any(r['source_id'] in test_ids for r in s['source_refs']):
                raise ValueError('each GT unit must cite its independent test description')
            if task=='existing-extract' and s['source_status']!='explicit':raise ValueError('E may contain only documented exceptions')
            if s['source_status']=='framework_inferred' and not s['derivation']:raise ValueError('GT inference needs derivation')
    if task in {'gap-compare','semantic-compare'}:
        expected={(a['id'],b['id']) for a in inputs['left'] for b in inputs['right']}
        got=[(d['left_id'],d['right_id']) for d in payload['decisions']]
        if len(got)!=len(set(got)) or set(got)!=expected:raise ValueError('comparison must inspect every candidate pair exactly once')
        left={s['id']:s for s in inputs['left']}; right={s['id']:s for s in inputs['right']}
        for d in payload['decisions']:
            a,b=left[d['left_id']],right[d['right_id']]
            if d['status']=='full' and (a['case_id']!=b['case_id'] or a['layer']!=b['layer']):
                raise ValueError('full match cannot cross case/layer')
            if d['status']=='full' and {a['cause'],b['cause']} & {'no_matching_records','empty_list'} and {a['cause'],b['cause']} & {'instance_missing','instance_not_found','requested_resource_not_found'}:raise ValueError('no match cannot cover missing instance')
    if task=='gap-compare':
        from .exception_comparison import missing_report
        expected=missing_report(inputs['left'],inputs['right'],payload['decisions'])['M']
        if payload['missing']!=expected:raise ValueError('missing must equal G minus complete one-to-one E coverage')
    return payload

