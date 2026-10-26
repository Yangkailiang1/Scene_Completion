"""Read-only presentation of the persisted DAG, not a second workflow definition."""
from pathlib import Path
import time
from .storage import read_json
from .deepagents_client import role_for

LABELS={'normal-rules':'正向正常规则整理','ssd-context':'用例SSD上下文取片（工具）','source-index':'Markdown章节与证据索引（工具）','components':'系统组成','use-case-extract':'用例目录抽取','use-case-align':'RR / SR 用例对应',
 'api-index':'接口目录与参数任务拆分','existing-branches':'原文已有异常分支','existing-bind':'异常与融合交互绑定','api-map':'API 接口映射','api-parameters':'API 参数','fused-ssd':'完整 SSD 建模','rr-ssd':'RR SSD 视图','sr-ssd':'SR SSD 视图',
 'test-operation-project':'测试操作投影','object-operations':'对象支持操作','interaction-align':'步骤展开对应','interaction-enrich':'交互属性补全',
 'concern-match':'LLM识别关注点 G_c','enriched-view':'交互与关注点','exception-generate':'生成异常 G','existing-extract':'关注点逆向归类与细化 E',
 'gap-compare':'缺失比较 M','missing-report':'缺失异常报告','test-ground-truth':'测试真值整理','semantic-compare':'评测语义对应',
 'exception-evaluation':'异常评测','extraction-evaluation':'抽取 Acc','pattern-applicability':'模式适用性与证据分级','gap-recommend':'风险保底推荐'}
LABELS.update({'test-supplement':'独立异常测试补全','test-additional-truth':'补充异常测试GT（工具）','test-additional-dedup':'补充测试内部去重（工具）','test-expanded':'扩展异常测试集去重合并（工具）'})

LABELS.update({'existing-concerns':'独立识别原文关注点 E_c','test-concerns':'独立识别测试关注点 GT_c',
 'test-additional-concerns':'补充测试关注点（独立结构化识别）','concern-compare':'关注点规则比较 M_c','concern-evaluation':'关注点层评测',
 'exception-evaluation':'两层指标汇总','gap-compare':'具体场景比较 M_s','existing-extract':'已有异常场景细化 E_s','test-ground-truth':'测试异常场景细化 GT_s'})

def artifact_folder(root,key,case):
    from .storage import fingerprint
    return Path(root)/'artifacts'/('shared' if case=='shared' else fingerprint(case)[:12])

INPUTS={'normal-rules':'本用例正向原文＋实际服务交互，不含E/GT','components':'RR＋SR正向文档','rr-use-cases':'RR正向文档','sr-use-cases':'SR正向文档',
 'api-index':'SR接口定义','api-map':'SR服务及接口定义','api-parameters':'SR接口定义与约束（按接口分任务）',
 'fused-ssd':'对应RR/SR用例＋系统组成','object-operations':'组成＋RR视图＋测试操作投影',
 'concern-match':'具体交互＋接口表＋预定义关注点','exception-generate':'正向交互及已匹配关注点，隔离E/GT',
 'existing-branches':'RR＋SR原文已有异常（独立通道）','existing-bind':'原分支＋融合SSD＋用例对应',
 'existing-extract':'已绑定分支＋接口约束＋关注点体系','test-ground-truth':'独立测试spec＋融合SSD＋正常约束',
 'test-supplement':'正向SSD＋正常规则＋接口约束，隔离G/E/比较结果','test-additional-truth':'已验证补充测试，不读取G/E','test-additional-dedup':'补充测试集内部的完整失败对应','test-expanded':'原始异常GT＋补充GT独立去重','gap-compare':'生成G＋逆向细化E','missing-report':'G/E覆盖明细＋具体交互','pattern-applicability':'正向交互＋规则＋模式库；不读取E/GT','gap-recommend':'缺失M＋项目已审核历史＋风险设置；不读取GT','exception-evaluation':'独立GT与G/E/Q对齐结果'}
INPUTS.update({'existing-concerns':'已绑定原文异常＋正向交互／约束；隔离G/GT','test-concerns':'独立异常测试＋正向交互／约束；隔离G/E','concern-compare':'已识别G_c＋E_c，稳定ID规则比较，不调用LLM','concern-evaluation':'独立G_c/E_c/GT_c，按关注点绑定计分','test-additional-concerns':'独立补充测试中已经识别的关注点，不读取G/E'})
PREVIEWS=[('modeler','concern-match','LLM识别四要素上的关注点 G_c'),('checker','existing-concerns','原文已有关注点 E_c'),('checker','test-concerns','独立测试关注点 GT_c'),('checker','concern-compare','关注点层精确规则比较'),('checker','existing-branches','按用例抽取原文已有异常'),('modeler','fused-ssd','完整SSD与两层视图'),('modeler','object-operations','对象支持操作'),('modeler','pattern-applicability','模式适用性与证据分级'),('modeler','exception-generate','细粒度场景生成G'),('checker','existing-bind','原文异常绑定具体交互'),('checker','existing-extract','关注点逆向归类与粒度细化E'),('checker','test-ground-truth','测试spec异常绑定与细化GT'),('checker','gap-compare','覆盖比较与缺失M'),('checker','exception-evaluation','漏报率与生成有效率')]

def expected_files(key,case,stage):
    stem=(key if case=='shared' else key[len(case)+1:]).replace(':','--')
    suffixes=['json']
    if stage in {'components','fused-ssd','rr-ssd','sr-ssd'}:suffixes+=['svg']
    if stage in {'components','api-map','api-parameters','object-operations','concern-match','existing-concerns','test-concerns','concern-compare','concern-evaluation','rr-ssd','sr-ssd','missing-report','existing-branches','existing-bind','existing-extract','test-ground-truth','exception-generate','pattern-applicability','gap-recommend'}:suffixes+=['md']
    return [stem+'.'+s for s in suffixes]

def graph_snapshot(root):
    root=Path(root);definition=read_json(root/'workflow_graph.json') if (root/'workflow_graph.json').exists() else {'nodes':[]}
    state=read_json(root/'workflow_tasks.json')['tasks'] if (root/'workflow_tasks.json').exists() else {}
    phases={}
    if (root/'execution_events.sqlite3').exists():
        from .execution_events import EventStore
        phases=EventStore(root).latest_phases()
    from .node_conversations import Conversations
    conversations=Conversations(root)
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
        if event and event['kind']=='rate_limit_wait' and status=='running':phase='rate_limit_wait'
        if node['stage']=='gap-recommend' and node.get('case','shared')=='shared':phase='disabled';status='disabled'
        if node['stage']=='gap-recommend' and record.get('status')=='passed':
            v=read_json(root/record['output_file']).get('payload',{}) if record.get('output_file') else {}
            if not v.get('enabled'):phase='disabled';status='disabled'
        blocked=[d for d in node['deps'] if state.get(d,{}).get('status')!='passed']
        failure=record.get('failure',{}).get('transport_failure',{})
        if status=='pending' and failure.get('failure_category') in {'transport_timeout','connection_failed','stream_incomplete'}:phase=failure['failure_category']
        if blocked and status in {'pending','blocked_dependency'}:phase='dependency_wait'
        started=record.get('started_at');ended=record.get('finished_at')
        actual=[]
        folder=artifact_folder(root,key,node['case']);stem=(key if node['case']=='shared' else key[len(node['case'])+1:]).replace(':','--')
        for f in folder.glob(stem+'.*'):
            if f.is_file():actual.append({'name':f.name,'path':'run/'+str(f.relative_to(root)).replace('\\','/'),'status':'saved'})
        if status=='awaiting_review':
            from .storage import fingerprint
            preview=root/'reviews/previews'/fingerprint(key)
            for f in preview.glob('*'):
                if f.is_file():actual.append({'name':f.name,'path':'run/'+str(f.relative_to(root)).replace('\\','/'),'status':'awaiting_review'})
        question=conversations.pending(key)
        nodes.append({**node,'planned':False,'input_summary':INPUTS.get(key,INPUTS.get(node['stage'],'依赖上游已验证产物')),'artifacts':actual,'question':question,'guidance_revision':conversations.revision(key),
          'retry_at':event.get('data',{}).get('retry_at') if event else None,'retry_count':event.get('data',{}).get('retry_count') if event else None,'label':node.get('label') or LABELS.get(node['stage'],node['stage']),'status':status,'phase':phase or 'pending',
          'blocked_by':blocked,'failure':record.get('failure') if status not in {'passed','awaiting_review','disabled'} else None,'attempt':record.get('rounds',0)+1,
          'elapsed_seconds':max(0,(ended or time.time())-started) if started else None,'last_event_at':event['at'] if event else None})
        edges += [{'id':d+'->'+key,'source':d,'target':key} for d in node['deps']]
    if not any(n['case']!='shared' and not n.get('planned') for n in nodes):
        for role,stage,label in PREVIEWS:
            nodes.append({'id':'planned:'+stage,'stage':stage,'case':'待用例对应','role':role,'label':label,'planned':True,'status':'planned','phase':'planned','deps':[],'expected_files':expected_files(stage,'shared',stage),'input_summary':INPUTS.get(stage,'按用例展开'),'artifacts':[],'blocked_by':[],'failure':None,'attempt':0,'elapsed_seconds':None,'question':None})
    if not any(n['stage']=='gap-recommend' for n in nodes):
        nodes.append({'id':'planned:gap-recommend','stage':'gap-recommend','case':'shared','role':'recommender','label':'等待用例对应后展开推荐','planned':True,'status':'disabled','phase':'disabled','deps':[],'expected_files':[],'input_summary':'缺失报告M；当前不执行','artifacts':[],'blocked_by':[],'failure':None,'attempt':0,'elapsed_seconds':None})
    # Old runs have status records but no graph. Make that limitation explicit.
    return {'nodes':nodes,'edges':edges,'definition_available':bool(definition['nodes']),
      'case_expansion_pending':not any(n['case']!='shared' and not n.get('planned') for n in nodes),
      'roles':[{'id':r,'label':label,'completed':sum(n['role']==r and not n.get('planned') and n['status']=='passed' for n in nodes),
        'known':sum(n['role']==r and not n.get('planned') and n['status']!='disabled' for n in nodes),'disabled':r=='recommender'}
        for r,label in [('modeler','建模器'),('checker','检查器'),('recommender','推荐器')]]}
