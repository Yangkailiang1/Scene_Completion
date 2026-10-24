"""Compare within canonical interactions; retain an exhaustive flat decision matrix."""
from pathlib import Path
from .contracts import packet,PROTOCOL
from .storage import fingerprint,read_json,write_json
from .validation import validate_result
from .exception_comparison import missing_report

def compare_in_batches(parent,client,root,guidance_revision=0,call=None):
    root=Path(root);inputs=parent['input'];left,right=inputs['left'],inputs['right']
    decisions=[];groups={};proofs=[]
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
            if reason:decisions.append({'left_id':a['id'],'right_id':b['id'],'status':status,'reason':reason})
            else:unresolved.append(b)
        if unresolved:
            # Rows with the same unresolved right set form a rectangle. Known
            # pairs never return to the model through another partition.
            key=(a['case_id'],a['interaction_id'],tuple(b['id'] for b in unresolved))
            group=groups.setdefault(key,{'left':{},'right':{}})
            group['left'][a['id']]=a
            for b in unresolved:group['right'][b['id']]=b
    from .workflow import skill_path
    from .execution_events import emit,fields
    jobs=[]
    for (case,interaction,_),group in groups.items():
        a,b=list(group['left'].values()),list(group['right'].values())
        for i in range(0,len(a),8):
            for j in range(0,len(b),8):jobs.append((interaction,a[i:i+8],b[j:j+8]))
    for n,(interaction,a,b) in enumerate(jobs,1):
        child_input={'left':a,'right':b,'purpose':inputs['purpose']}
        child=packet('semantic-compare',child_input,parent.get('case_ids'))
        child['node_key']=parent['node_key'];child['skill_text']=skill_path('semantic-compare').read_text()
        child['instructions']+='\n本次只比较同一个融合交互内的给定候选。其余交互由程序判定为不覆盖；本片仍须完整枚举输入左右候选对。'
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
        decisions+=value['decisions'];proofs.append(proof)
    result={'decisions':decisions}
    if parent['task']=='gap-compare':result['missing']=missing_report(left,right,decisions)['M']
    validate_result(parent['task'],result,inputs)
    return {**result,'execution_model_evidence':{'provider':'interaction_partitioned_comparison','requested_model':client.model('agent'),
      'partitions':proofs,'partition_count':len(jobs),'programmatic_full_pairs':sum(d['status']=='full' and d['reason'] in {'已确认的同交互宽泛输入参数分支覆盖本字段规则','同一正常约束ID及完整失败单元逐字段一致'} for d in decisions),'programmatic_unmatched_pairs':sum(d['reason']=='不同用例或不同融合交互，不能互相覆盖' for d in decisions)}}
