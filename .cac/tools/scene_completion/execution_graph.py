"""Read-only presentation of the persisted DAG, not a second workflow definition."""
from pathlib import Path
import time
from .storage import read_json
from .deepagents_client import role_for

LABELS={'components':'系统组成','use-case-extract':'用例目录抽取','use-case-align':'RR / SR 用例对应',
 'api-map':'API 接口映射','api-parameters':'API 参数','fused-ssd':'完整 SSD 建模','rr-ssd':'RR SSD 视图','sr-ssd':'SR SSD 视图',
 'test-operation-project':'测试操作投影','object-operations':'对象支持操作','interaction-align':'步骤展开对应','interaction-enrich':'交互属性补全',
 'concern-match':'关注点匹配','enriched-view':'交互与关注点','exception-generate':'生成异常 G','existing-extract':'已有异常 E',
 'gap-compare':'缺失比较 M','missing-report':'缺失异常报告','test-ground-truth':'测试真值整理','semantic-compare':'评测语义对应',
 'exception-evaluation':'异常评测','extraction-evaluation':'抽取 Acc','gap-recommend':'推荐器'}

def expected_files(key,case,stage):
    stem=(key if case=='shared' else key[len(case)+1:]).replace(':','--')
    suffixes=['json']
    if stage in {'components','fused-ssd','rr-ssd','sr-ssd'}:suffixes+=['svg']
    if stage in {'components','api-map','api-parameters','object-operations','concern-match','rr-ssd','sr-ssd','missing-report'}:suffixes+=['md']
    return [stem+'.'+s for s in suffixes]

def graph_snapshot(root):
    root=Path(root);definition=read_json(root/'workflow_graph.json') if (root/'workflow_graph.json').exists() else {'nodes':[]}
    state=read_json(root/'workflow_tasks.json')['tasks'] if (root/'workflow_tasks.json').exists() else {}
    phases={}
    if (root/'execution_events.sqlite3').exists():
        from .execution_events import EventStore
        phases=EventStore(root).latest_phases()
    nodes=[];edges=[]
    declared=definition['nodes'] or [{'id':k,'case':r.get('case','shared'),'stage':r.get('stage',k),'role':role_for(r.get('stage',k)),'deps':[],'expected_files':expected_files(k,r.get('case','shared'),r.get('stage',k))} for k,r in state.items()]
    for node in declared:
        key=node['id'];record=state.get(key,{});status=record.get('status','pending');event=phases.get(key)
        phase=event.get('data',{}).get('phase') if event else None
        if status!='running':phase={'passed':'complete','awaiting_review':'awaiting_review','blocked_dependency':'dependency_wait'}.get(status,status)
        elif event and event['kind']=='stream_delta':phase='streaming'
        elif event and event['kind']=='request_started':phase='model_wait'
        elif event and event['kind']=='tool_started':phase='tool_running'
        elif event and event['kind']=='tool_finished':phase='preparing'
        if node['stage']=='gap-recommend':phase='disabled';status='disabled'
        blocked=[d for d in node['deps'] if state.get(d,{}).get('status')!='passed']
        if blocked and status in {'pending','blocked_dependency'}:phase='dependency_wait'
        started=record.get('started_at');ended=record.get('finished_at')
        nodes.append({**node,'label':LABELS.get(node['stage'],node['stage']),'status':status,'phase':phase or 'pending',
          'blocked_by':blocked,'failure':record.get('failure') if status not in {'passed','awaiting_review','disabled'} else None,'attempt':record.get('rounds',0)+1,
          'elapsed_seconds':max(0,(ended or time.time())-started) if started else None,'last_event_at':event['at'] if event else None})
        edges += [{'id':d+'->'+key,'source':d,'target':key} for d in node['deps']]
    # Old runs have status records but no graph. Make that limitation explicit.
    return {'nodes':nodes,'edges':edges,'definition_available':bool(definition['nodes']),
      'case_expansion_pending':not any(n['case']!='shared' for n in nodes),
      'roles':[{'id':r,'label':label,'completed':sum(n['role']==r and n['status']=='passed' for n in nodes),
        'known':sum(n['role']==r and n['status']!='disabled' for n in nodes),'disabled':r=='recommender'}
        for r,label in [('modeler','建模器'),('checker','检查器'),('recommender','推荐器')]]}
