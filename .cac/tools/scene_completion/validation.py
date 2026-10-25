from copy import deepcopy
import json
from .storage import fingerprint
from .contracts import PROTOCOL,registry,validate
from .source_documents import validate_evidence,documents_in,evidence_refs
from .interaction_enrichment import interactions,parameters_for
from .concern_hierarchy import applicability,match_is_applicable,context
from .concern_registry import inheritance_paths
from .exception_generation import scenario_key,data_exceptions,query_matches,storage_exceptions,deduplicate
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
    if task in {'use-case-extract','use-case-align','fused-ssd'}:
        from .use_cases import validate_catalogue
        validate_catalogue(task,payload,inputs)
    docs=documents_in(inputs)
    allowed={fingerprint(r) for r in evidence_refs(inputs)}
    evidence_errors=[]
    for ref in evidence_refs(payload):
        if fingerprint(ref) not in allowed:
            if not docs:
                candidates=[r for r in evidence_refs(inputs) if r['source_id']==ref['source_id']]
                sample=candidates[:4] or evidence_refs(inputs)[:4]
                raise ValueError('output uses evidence outside task dependencies; offending='+json.dumps(ref,ensure_ascii=False)+'; copy an existing dependency source_refs object verbatim (do not invent line numbers or abbreviate quotes); examples='+json.dumps(sample,ensure_ascii=False))
            try:validate_evidence(ref,docs)
            except ValueError as e:evidence_errors.append(str(e))
    if evidence_errors:raise ValueError('; '.join(dict.fromkeys(evidence_errors[:8])))
    refs_required(payload)
    if task=='api-map':
        from .api_documents import explicit_http_interfaces
        declared=explicit_http_interfaces(inputs['SR'])
        actual={(a['method'].upper(),a['address']) for s in payload['services'] for a in s['interfaces'] if a.get('method') and a.get('address')}
        missing=set(declared)-actual
        if missing:raise ValueError('API mapping omitted explicit method/path declarations or downstream calls; include each evidenced service/interface (generate a stable local ID if no document API ID exists): '+json.dumps([{'method':m,'path':p,'source_ref':declared[(m,p)]} for m,p in sorted(missing)[:8]],ensure_ascii=False))
    # Numerical rule values must be traceable, even when the model cites a
    # real sentence. Citation presence alone is not a threshold source.
    import re
    def rule_values(node):
        if isinstance(node,dict):
            for g in node.get('activation_evidence',[]):
                value=g.get('value');kind=g['kind']
                if g.get('status')!='explicit' or kind not in {'timing','resource_limit','stability'}:continue
                text=' '.join(r['quote'] for r in g['source_refs'])
                if type(value) in (int,float) and g.get('unit'):
                    numbers=[float(n) for n in re.findall(r'\d+(?:\.\d+)?',text)]
                    if kind=='timing':
                        import math
                        units={'ms':.001,'millisecond':.001,'milliseconds':.001,'毫秒':.001,'s':1,'sec':1,'second':1,'seconds':1,'秒':1,'min':60,'minute':60,'minutes':60,'分钟':60}
                        unit=g['unit'].casefold()
                        if unit in units:
                            pairs=re.findall(r'(\d+(?:\.\d+)?)\s*(毫秒|milliseconds?|ms|分钟|minutes?|min|秒|seconds?|sec|s)(?![a-z])',text,re.I)
                            if not any(math.isclose(float(number)*units[u.casefold()],float(value)*units[unit],rel_tol=1e-9) for number,u in pairs):raise ValueError('timing value/unit is not supported by cited normal evidence')

                    if float(value) not in numbers:
                        unit=g['unit'].casefold();seconds=unit in {'s','sec','second','seconds','秒'};millis=unit in {'ms','millisecond','milliseconds','毫秒'}
                        converted=[]
                        if seconds:converted += [float(v)/1000 for v in re.findall(r'(\d+(?:\.\d+)?)\s*(?:毫秒|ms)',text,re.I)]
                        if millis:converted += [float(v)*1000 for v in re.findall(r'(\d+(?:\.\d+)?)\s*(?:秒|s(?:ec(?:onds?)?)?)(?![a-z])',text,re.I)]
                        if float(value) not in converted:raise ValueError('numeric rule value is not supported by cited normal evidence')
                if isinstance(value,str) and value.strip() and value not in text:raise ValueError('qualitative deadline/stability criterion must cite its exact normal wording')
            for child in node.values():rule_values(child)
        elif isinstance(node,list):
            for child in node:rule_values(child)
    rule_values(payload)
    if 'scenarios' in payload and len({s['id'] for s in payload['scenarios']})!=len(payload['scenarios']):raise ValueError('duplicate scenario ID')
    definitions=registry()['definitions']
    def visit(v):
        if isinstance(v,dict):
            for key in v.get('concern_origins',[]):
                if key not in definitions:raise ValueError('unregistered concern origin')
            for path in v.get('concern_paths',v.get('inheritance_paths',[])):
                if not path or any(k not in definitions for k in path) or path not in inheritance_paths(path[-1]):raise ValueError('invalid concern inheritance path')
            if 'concern_key' in v and v['concern_key'] not in definitions:raise ValueError('unregistered concern')
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(payload)
    if task=='api-parameters' and 'interface' in inputs:
        if len(payload['apis'])!=1 or payload['apis'][0]['id']!=inputs['interface']['id']:raise ValueError('API child must output exactly the indexed interface, preserving its ID')
        expected=inputs['interface'].get('address')
        if expected and payload['apis'][0]['address']!=expected:raise ValueError('接口目录已明确地址，参数表必须保留该地址，不得改为待确认')
        if inputs['interface'].get('source_role')=='invocation_only':
            import re
            for p in payload['apis'][0]['parameters']:
                text=' '.join(r['quote'] for r in p['source_refs'])
                if p['required'] is not None and not re.search(r'必填|可选|required|optional',text,re.I):raise ValueError('只有调用材料，字段出现不等于接口必填/可选；required请设null待确认')
                if p['data_type'] is not None and not re.search(r'类型|type|字符串|string|整数|integer|布尔|boolean|浮点|float|double|数组|array|对象|object',text,re.I):raise ValueError('只有调用材料，不能猜接口字段类型；data_type请设null待确认')
                if p['default'] is not None and not re.search(r'默认|default',text,re.I):raise ValueError('本次调用绑定值不是接口默认值；default请设null')
                for rule in p['constraints']:
                    if rule['status']=='explicit' and rule['kind']=='enum' and not re.search(r'枚举|允许|有效值|只能|enum', ' '.join(r['quote'] for r in rule['source_refs']),re.I):raise ValueError('本次调用固定值不能扩展为接口全局枚举；调用绑定保留在本用例SSD，枚举范围待确认')
    if task=='api-index':
        ids=set();docs={d['source_id']:d for d in inputs['SR']}
        for a in payload['apis']:
            if a['id'] in ids or not a['source_ranges']:raise ValueError('API index requires unique identities and source ranges')
            ids.add(a['id'])
            for span in a['source_ranges']:
                numbers={r['number'] for r in docs.get(span['source_id'],{}).get('lines',[])}
                if span['start'] not in numbers or span['end'] not in numbers or span['start']>span['end']:raise ValueError('API index range outside allowed source')
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
            if i['direction']=='return' and any(p['location'] in {'header','path','query','body'} for p in i['data']['sequence']):raise ValueError('request fields cannot enter response data: message '+i['id']+' contains '+', '.join(p['name']+'@'+p['location'] for p in i['data']['sequence'] if p['location'] in {'header','path','query','body'})+'; response messages permit response/business fields only')
            if i['direction']=='request' and any(p['location']=='response' for p in i['data']['sequence']):raise ValueError('response fields cannot enter request data: message '+i['id']+' contains '+', '.join(p['name'] for p in i['data']['sequence'] if p['location']=='response')+'; output projection columns are not request payload. Keep request criteria in this message; put explicitly returned fields on its actual return message, or record local projection in operation.sequence without inventing returned values.')
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
            for m in payload['matches']:
                i=by_id[m['interaction_id']];d=definitions[m['concern_key']]
                if m['target'] in {'sender','receiver'} and m['object']!=i[m['target']]['name']:
                    raise ValueError('concern party must be actual sender/receiver: '+m['interaction_id']+' target='+m['target']+' object='+m['object']+'; actual sender='+i['sender']['name']+', receiver='+i['receiver']['name']+'. Keep the evidenced object and select its actual side; do not replace it with another service.')
                kinds=context(i,inputs)['kinds']
                if kinds <= {'read','display'} and d['operation_kinds'] and not kinds&set(d['operation_kinds']) and m.get('status') not in {'not_applicable','pending'}:
                    raise ValueError('read-only interaction cannot activate mutation concerns')
                if m['concern_key']=='service.base.availability' and (m['target']!=context(i,inputs)['role'] or m['object']!=context(i,inputs)['name']):
                    raise ValueError('availability belongs to this actual called service')
                if m['target']=='data' and m.get('scope','interface') not in {'storage','context'} and m['object'] not in {p['name'] for p in parameters_for(i,inputs)}:
                    raise ValueError('data concern must identify an actual field')
                status,reason=applicability(m,i,inputs)
                if m.get('status')=='applicable' and status!='applicable':raise ValueError('concern applicability lacks evidence: '+reason)
        else:
            matches={(m['interaction_id'],m['object'],m['concern_key']) for m in inputs['concern-match']['matches'] if match_is_applicable(m,by_id[m['interaction_id']],inputs)}
            for s in payload['scenarios']:
                i=by_id[s['interaction_id']]
                if s['operation']!=i['operation']['name'] or s['case_id']!=i['case_id'] or s['layer']!=i['layer']:
                    raise ValueError('G must use this SSD operation, case and layer')
                if (s['interaction_id'],s['object'],s['concern_key']) not in matches:
                    raise ValueError('G must have an applicable matched concern')
                if s['source_status']!='framework_inferred' or not s['derivation']:
                    raise ValueError('G requires recorded positive-rule derivation')
                if s['field'] is not None:
                    expected={scenario_key(x) for x in data_exceptions(inputs)+storage_exceptions(inputs)}
                    if scenario_key(s) not in expected: raise ValueError('unsupported or invented field exception')
                else:
                    match=[m for m in inputs['concern-match']['matches'] if (m['interaction_id'],m['object'],m['concern_key'])==(s['interaction_id'],s['object'],s['concern_key']) and match_is_applicable(m,i,inputs)]
                    if definitions[s['concern_key']]['kind']=='family':raise ValueError('abstract concern family cannot generate an independent exception')
                    if not any(m['concrete_rule'] for m in match):raise ValueError('no concrete rule; move to pending')
                if s['concern_key']=='service.base.availability':
                    import re
                    if re.search(r'认证|凭证|身份|token|authenticat',s['cause']+' '+str(s['conditions']),re.I):raise ValueError('authentication failure is not service availability')
    if task in {'existing-extract','test-ground-truth'}:
        test_ids={d['source_id'] for d in documents_in(inputs) if d.get('channel')=='test'}
        for s in payload['scenarios']:
            if task=='test-ground-truth' and not any(r['source_id'] in test_ids for r in s['source_refs']):
                raise ValueError('each GT unit must cite its independent test description')
            if task=='existing-extract' and s['source_status']=='framework_inferred' and not s.get('original_branch_id'):raise ValueError('E inference requires original branch provenance')
            if s['source_status']=='framework_inferred' and not s['derivation']:raise ValueError('GT inference needs derivation')
    if task=='existing-bind':
        branches={b['id'] for b in inputs['branches']['branches']}
        from .inverse_alignment import canonical_fused
        ids={i['id'] for i in canonical_fused(inputs['fused-ssd'])['interactions']}
        for b in payload['bindings']:
            if b['branch_id'] not in branches:raise ValueError('unknown original branch')
            if b['status']=='confirmed' and b['interaction_id'] not in ids:raise ValueError('binding needs a concrete canonical interaction')
    if task=='existing-extract' and 'fused-ssd' in inputs:
        from .inverse_alignment import normalized_scenarios
        normalized_scenarios(payload,inputs['fused-ssd'])
    if task in {'gap-compare','semantic-compare'}:
        expected={(a['id'],b['id']) for a in inputs['left'] for b in inputs['right']}
        if task=='semantic-compare' and 'candidate_pairs' in inputs:
            pairs=inputs['candidate_pairs']
            if not isinstance(pairs,list) or not pairs or any(not isinstance(p,dict) or set(p)!={'left_id','right_id'} or not all(isinstance(v,str) for v in p.values()) for p in pairs):raise ValueError('invalid sparse candidate pairs')
            selected={(p['left_id'],p['right_id']) for p in pairs}
            if len(selected)!=len(pairs) or not selected<=expected:raise ValueError('sparse candidate pairs must be unique known IDs')
            expected=selected
        got=[(d['left_id'],d['right_id']) for d in payload['decisions']]
        if len(got)!=len(set(got)) or set(got)!=expected:
            from collections import Counter
            raise ValueError('comparison must inspect every candidate pair exactly once; missing='+str(sorted(expected-set(got))[:10])+'; extra='+str(sorted(set(got)-expected)[:10])+'; duplicates='+str([p for p,n in Counter(got).items() if n>1][:10])+'. When candidate_pairs is provided, emit only those pairs.')
        left={s['id']:s for s in inputs['left']}; right={s['id']:s for s in inputs['right']}
        for d in payload['decisions']:
            a,b=left[d['left_id']],right[d['right_id']]
            if d['status']=='full' and (a['case_id']!=b['case_id'] or a['interaction_id']!=b['interaction_id']):
                raise ValueError('full match cannot cross case/fused interaction')
            if d['status']=='full' and a.get('scope') in {'interface','storage','context'} and b.get('scope') in {'interface','storage','context'} and a['scope']!=b['scope']:raise ValueError('full match cannot cross constraint scope')
            if d['status']=='full' and a.get('data_location') and b.get('data_location') and a['data_location']!=b['data_location']:raise ValueError('full match cannot cross field location')
            if d['status']=='full' and {a['cause'],b['cause']} & {'no_matching_records','empty_list'} and {a['cause'],b['cause']} & {'instance_missing','instance_not_found','requested_resource_not_found'}:raise ValueError('no match cannot cover missing instance')
    if task=='gap-compare':
        from .exception_comparison import missing_report
        expected=missing_report(inputs['left'],inputs['right'],payload['decisions'])['M']
        if deduplicate(payload['missing'])!=expected:raise ValueError('missing must equal G minus complete one-to-one E coverage')
    return payload
