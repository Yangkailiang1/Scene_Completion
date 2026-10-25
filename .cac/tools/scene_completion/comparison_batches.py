"""Compare within canonical interactions; retain an exhaustive flat decision matrix."""
from pathlib import Path
import re
from .contracts import packet,PROTOCOL
from .storage import fingerprint,read_json,write_json
from .validation import validate_result
from .exception_comparison import missing_report

def distinct_unit(a,b):
    """Only structural exclusions; uncertain names still need semantic review."""
    for key,label in (('scope','约束作用域'),('data_location','字段位置')):
        if a.get(key) and b.get(key) and a[key]!=b[key]:return label+'不同，无法构成完整对应'
    # Literal API identifiers are case-sensitive except HTTP header names.
    # Natural-language labels and absent fields do not establish inequality.
    fields=[s.get('field') for s in (a,b)]
    if all(isinstance(f,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.\[\]-]*',f) for f in fields):
        if a.get('data_location')==b.get('data_location')=='header':fields=[f.lower() for f in fields]
        if fields[0]!=fields[1]:return '明确的API字段标识不同，字段异常不是同一个匹配单元'
    return None

def pair_cache_key(node,purpose,a,b,guidance,rules):
    return fingerprint({'node':node,'purpose':purpose,'left':a,'right':b,'guidance':guidance,'rules':rules})

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
            if (a['case_id'],a['interaction_id'])!=(b['case_id'],b['interaction_id']):
                status='unmatched';reason='不同用例或不同融合交互，不能互相覆盖'
            elif inputs['purpose'] in {'G_E','GT_E'} and broad_covers(a,b):
                reason='已确认的同交互宽泛输入参数分支覆盖本字段规则'
            elif a.get('rule_id') and a['rule_id']==b.get('rule_id') and a.get('field')==b.get('field') and scenario_key(a)==scenario_key(b):
                reason='同一正常约束ID及完整失败单元逐字段一致'
            elif distinct_unit(a,b):status='unmatched';reason=distinct_unit(a,b)
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
    for (case,interaction),pairs in groups.items():
        for i in range(0,len(pairs),32):jobs.append((interaction,pairs[i:i+32]))
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
                    validate_result('semantic-compare',v['payload'],child_input);value=v['payload'];proof={**v.get('execution',{}),'reused':True}
            except (ValueError,KeyError,OSError):pass
        emit('comparison_partition',index=n,total=len(jobs),interaction_id=interaction,reused=value is not None)
        if value is None:
            child['batch_id']=fingerprint(child);write_json(root/'packets'/(child['batch_id']+'.json'),child)
            with fields(comparison_partition=interaction):raw=(call or client.agent)(child)
            proof={k:raw[k] for k in ('execution_model_evidence','native_execution') if k in raw}
            value={k:v for k,v in raw.items() if k not in proof};validate_result('semantic-compare',value,child_input)
            write_json(cache,{'protocol':PROTOCOL,'payload':value,'execution':proof})
        left_ids={x['id']:x for x in a};right_ids={x['id']:x for x in b}
        for decision in value['decisions']:
            x,y=left_ids[decision['left_id']],right_ids[decision['right_id']]
            key=pair_cache_key(parent['node_key'],inputs['purpose'],x,y,guidance_revision,rules)
            write_json(root/'comparison_decisions'/(key+'.json'),{'identity':key,'decision':decision,'source_file':str(cache.relative_to(root))})
        decisions+=value['decisions'];proofs.append(proof)
    result={'decisions':decisions}
    order_left={s['id']:n for n,s in enumerate(left)};order_right={s['id']:n for n,s in enumerate(right)}
    decisions.sort(key=lambda d:(order_left[d['left_id']],order_right[d['right_id']]))
    if parent['task']=='gap-compare':result['missing']=missing_report(left,right,decisions)['M']
    validate_result(parent['task'],result,inputs)
    return {**result,'execution_model_evidence':{'provider':'interaction_partitioned_comparison','requested_model':client.model('agent'),
      'partitions':proofs,'partition_count':len(jobs),'programmatic_full_pairs':sum(d['status']=='full' and d['reason'] in {'已确认的同交互宽泛输入参数分支覆盖本字段规则','同一正常约束ID及完整失败单元逐字段一致'} for d in decisions),'programmatic_unmatched_pairs':programmatic_unmatched}}
