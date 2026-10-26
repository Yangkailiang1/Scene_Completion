"""Compare within canonical interactions; retain an exhaustive flat decision matrix."""
from pathlib import Path
import re
from .contracts import packet,PROTOCOL
from .storage import fingerprint,read_json,write_json
from .validation import validate_result
from .exception_comparison import missing_report

def exact_failure_signature(s):
    """Narrow, auditable aliases; never equate timeout and unavailability."""
    text=s['cause']+' '+' '.join(s['conditions']);field=s.get('field')
    if field and s.get('failure_rule'):
        import json
        return ('explicit_field_rule',s.get('scope'),s.get('data_location'),field,json.dumps(s['failure_rule'],ensure_ascii=False,sort_keys=True),(s.get('predicate') or {}).get('measure') if s['failure_rule']['kind'].startswith('size') else None)
    if s['concern_key']=='service.base.availability' and not re.search(r'超时|timeout|deadline',text,re.I):
        if re.search(r'不可用|无法执行|service_unavailable',text,re.I):return ('unavailable',s['object'])
    if field and s['concern_key']=='api.data.range':
        if s['cause']=='minimum':
            m=re.search(r'minimum约束:\s*(-?\d+(?:\.\d+)?)',text)
            if m:return ('below',field,float(m[1]))
        if s['cause']=='maximum':
            m=re.search(r'maximum约束:\s*(-?\d+(?:\.\d+)?)',text)
            if m:return ('above',field,float(m[1]))
        if re.search(r'负数|<\s*0',text):return ('below',field,0.)
    return None

def distinct_unit(a,b):
    """Only structural exclusions; uncertain names still need semantic review."""
    constrained={'interface','storage','context'}
    if a.get('scope') in constrained and b.get('scope') in constrained and a['scope']!=b['scope']:
        return '约束作用域不同，无法构成完整对应'
    if a.get('data_location') and b.get('data_location') and a['data_location']!=b['data_location']:
        return '字段位置不同，无法构成完整对应'
    if a.get('concern_key')==b.get('concern_key')=='api.data.size':
        from .data_requirements import measure
        units=[(s.get('predicate') or {}).get('measure') or measure(' '.join(s['conditions'])) for s in (a,b)]
        if units[0]!=units[1]:return '大小约束的数据属性不同或尚未统一；文件大小与数量不能互相命中'
    if a.get('failure_rule') and b.get('failure_rule') and a.get('field')==b.get('field') and a['failure_rule']!=b['failure_rule']:
        return '同一字段的不同独立契约约束，不是同一个失败单元'
    # Literal API identifiers are case-sensitive except HTTP header names.
    # Natural-language labels and absent fields do not establish inequality.
    fields=[s.get('field') for s in (a,b)]
    if all(isinstance(f,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.\[\]-]*',f) for f in fields):
        if a.get('data_location')==b.get('data_location')=='header':fields=[f.lower() for f in fields]
        if fields[0]!=fields[1]:return '明确的API字段标识不同，字段异常不是同一个匹配单元'
    return None

def pair_cache_key(node,purpose,a,b,guidance,rules):
    from .normal_rules import RULESET_VERSION
    from .task_context import semantic_view
    facts=semantic_view('semantic-compare',{'left':[a],'right':[b]})
    return fingerprint({'node':node if guidance else None,'purpose':purpose,'facts':facts,'guidance':guidance,'rules':rules,'ruleset':RULESET_VERSION})

def restrict_candidate_decisions(value,inputs,normalizations):
    """Keep requested decisions; never invent missing ones or choose conflicts."""
    if 'candidate_pairs' not in inputs:return value
    from copy import deepcopy
    result=deepcopy(value);allowed={(p['left_id'],p['right_id']) for p in inputs['candidate_pairs']}
    known={(a['id'],b['id']) for a in inputs['left'] for b in inputs['right']};rows=[];seen={}
    for row in result['decisions']:
        pair=(row['left_id'],row['right_id'])
        if pair in known and pair not in allowed:
            normalizations.append({'pair':list(pair),'action':'ignore unrequested known pair; retain separately computed decision'})
        elif pair in seen and row==seen[pair]:
            normalizations.append({'pair':list(pair),'action':'collapse identical duplicate decision'})
        else:rows.append(row);seen[pair]=row
    result['decisions']=rows
    return result

def compare_in_batches(parent,client,root,guidance_revision=0,call=None):
    root=Path(root);inputs=parent['input'];left,right=inputs['left'],inputs['right']
    decisions=[];groups={};proofs=[];programmatic_unmatched=0
    from .workflow import skill_path
    rules=skill_path('semantic-compare').read_text()
    from .exception_comparison import broad_covers
    from .exception_generation import scenario_key
    for a in left:
        unresolved=[]
        for b in right:
            reason=None;status='full'
            if inputs['purpose']=='GT_self' and a['id']>=b['id']:
                status='unmatched';reason='补充集内部去重只比较一次无序候选对；自对与镜像对不计匹配'
            elif (a['case_id'],a['interaction_id'])!=(b['case_id'],b['interaction_id']):
                status='unmatched';reason='不同用例或不同融合交互，不能互相覆盖'
            elif (a.get('matching_version') or b.get('matching_version')) and (not a.get('concern_binding_ids') or not b.get('concern_binding_ids') or not set(a['concern_binding_ids']) & set(b['concern_binding_ids'])):
                status='unmatched';reason='四要素对象或关注点ID不同，须先独立统一分类；不跨关注点匹配'
            elif inputs['purpose'] in {'G_E','GT_E'} and broad_covers(a,b):
                reason='已确认的同交互宽泛输入参数分支覆盖本字段规则'
            elif a.get('rule_id') and a['rule_id']==b.get('rule_id') and a.get('field')==b.get('field') and scenario_key(a)==scenario_key(b):
                reason='同一正常约束ID及完整失败单元逐字段一致'
            elif distinct_unit(a,b):status='unmatched';reason=distinct_unit(a,b)
            elif exact_failure_signature(a) is not None and exact_failure_signature(a)==exact_failure_signature(b):
                reason='同一交互、对象/字段及可判定失败条件一致；响应及后续行为不作为失败命中必要条件'
            if reason:
                decisions.append({'left_id':a['id'],'right_id':b['id'],'status':status,'reason':reason})
                programmatic_unmatched+=status=='unmatched'
            else:
                key=pair_cache_key(parent['node_key'],inputs['purpose'],a,b,guidance_revision,rules)
                saved=root/'comparison_decisions'/(key+'.json');cached=None
                if saved.exists():
                    try:
                        value=read_json(saved)
                        if value.get('identity')==key:
                            validate_result('semantic-compare',{'decisions':[value['decision']]},{'left':[a],'right':[b],'purpose':inputs['purpose']});cached=value['decision']
                    except (ValueError,KeyError,OSError):pass
                if cached is not None:
                    decisions.append(cached);proofs.append({'reused':True,'source_file':str(saved.relative_to(root))})
                else:unresolved.append(b)
        if unresolved:
            # Rows with the same unresolved right set form a rectangle. Known
            # pairs never return to the model through another partition.
            key=(a['case_id'],a['interaction_id'])
            groups.setdefault(key,[]).extend((a,b) for b in unresolved)
    from .execution_events import emit,fields
    jobs=[]
    max_bytes=getattr(client,'config',{}).get('comparison_input_max_bytes',14000)
    max_pairs=getattr(client,'config',{}).get('comparison_max_pairs',16)
    if type(max_pairs) is not int or not 1<=max_pairs<=32:raise ValueError('comparison_max_pairs must be 1..32')
    from .task_context import semantic_view
    for (case,interaction),pairs in groups.items():
        batch=[]
        for pair in pairs:
            proposed=batch+[pair]
            slim=semantic_view('semantic-compare',{'left':list({a['id']:a for a,b in proposed}.values()),'right':list({b['id']:b for a,b in proposed}.values())})
            import json
            if batch and (len(proposed)>max_pairs or len(json.dumps(slim,ensure_ascii=False).encode())>max_bytes):jobs.append((interaction,batch));batch=[]
            batch.append(pair)
        if batch:jobs.append((interaction,batch))
    for n,(interaction,pairs) in enumerate(jobs,1):
        a=list({x['id']:x for x,_ in pairs}.values());b=list({y['id']:y for _,y in pairs}.values())
        child_input={'left':a,'right':b,'purpose':inputs['purpose'],
          'candidate_pairs':[{'left_id':x['id'],'right_id':y['id']} for x,y in pairs]}
        child=packet('semantic-compare',child_input,parent.get('case_ids'))
        child['node_key']=parent['node_key'];child['skill_text']=rules
        child['instructions']+='\n本片只判断candidate_pairs逐项列出的候选对，不输出left与right的笛卡尔积。每个列出的候选对恰好输出一项；已排除的其他对由程序保存。'
        if parent.get('repair'):
            child['repair']={k:v for k,v in parent['repair'].items() if k!='candidate'}
            candidate=(child['repair'].get('failure') or {}).get('rejected_output')
            if candidate:
                file=(root/candidate).resolve()
                if file.is_relative_to(root.resolve()) and file.exists():
                    v=read_json(file)
                    if v.get('task')=='semantic-compare' and v.get('node_key')==child['node_key'] and v.get('input_hash')==fingerprint(child_input):child['repair']['candidate']=v['payload']
        identity=fingerprint({'input':child_input,'schema':child['output_schema'],'rules':child['skill_text'],'instructions':child['instructions'],
          'model':client.model('agent'),'endpoint':fingerprint(getattr(client,'base_url',None)),'guidance':guidance_revision})
        cache=root/'comparison_parts'/(identity+'.json');value=None;proof={}
        if cache.exists():
            try:
                v=read_json(cache)
                if isinstance(v,dict) and v.get('protocol')==PROTOCOL:
                    clean={**v['payload'],'decisions':[{k:x for k,x in d.items() if k not in {'follow_up_comparison','concern_alignment'}} for d in v['payload']['decisions']]}
                    validate_result('semantic-compare',clean,child_input);value=clean;proof={**v.get('execution',{}),'reused':True}
            except (ValueError,KeyError,OSError):pass
        emit('comparison_partition',index=n,total=len(jobs),interaction_id=interaction,reused=value is not None)
        if value is None:
            child['batch_id']=fingerprint(child);write_json(root/'packets'/(child['batch_id']+'.json'),child)
            with fields(comparison_partition=interaction):raw=(call or client.agent)(child)
            proof={k:raw[k] for k in ('execution_model_evidence','native_execution') if k in raw}
            value={k:v for k,v in raw.items() if k not in proof}
            value['decisions']=[{k:v for k,v in d.items() if k not in {'follow_up_comparison','concern_alignment'}} for d in value['decisions']]
            validate_result('semantic-compare',value,child_input)
            write_json(cache,{'protocol':PROTOCOL,'payload':value,'execution':proof})
        left_ids={x['id']:x for x in a};right_ids={x['id']:x for x in b}
        for decision in value['decisions']:
            x,y=left_ids[decision['left_id']],right_ids[decision['right_id']]
            key=pair_cache_key(parent['node_key'],inputs['purpose'],x,y,guidance_revision,rules)
            write_json(root/'comparison_decisions'/(key+'.json'),{'identity':key,'decision':decision,'source_file':str(cache.relative_to(root))})
        decisions+=value['decisions'];proofs.append(proof)
    result={'decisions':decisions}
    all_left={s['id']:s for s in left};all_right={s['id']:s for s in right}
    for d in decisions:
        d['concern_alignment']='same' if all_left[d['left_id']]['concern_key']==all_right[d['right_id']]['concern_key'] else 'different'
        d['follow_up_comparison']='not_scored'
    order_left={s['id']:n for n,s in enumerate(left)};order_right={s['id']:n for n,s in enumerate(right)}
    decisions.sort(key=lambda d:(order_left[d['left_id']],order_right[d['right_id']]))
    if parent['task']=='gap-compare':result['missing']=missing_report(left,right,decisions)['M']
    validate_result(parent['task'],result,inputs)
    return {**result,'execution_model_evidence':{'provider':'interaction_partitioned_comparison','requested_model':client.model('agent'),
      'partitions':proofs,'partition_count':len(jobs),'programmatic_full_pairs':sum(d['status']=='full' and d['reason'] in {'已确认的同交互宽泛输入参数分支覆盖本字段规则','同一正常约束ID及完整失败单元逐字段一致'} for d in decisions),'programmatic_unmatched_pairs':programmatic_unmatched}}
