"""Credential-free live pipeline telemetry and evidence-based DAG finish estimates.

Estimates cover discovered nodes, never undiscovered branches, human review or
future retries. No model is invoked and no artifact/cost ledger is modified.
"""
from pathlib import Path
from collections import defaultdict
import heapq
import json
import math
import sqlite3
import time
from .storage import read_json
from .model_resilience import validate
from .execution_graph import LABELS


def _number(v):
    return type(v) in (int, float) and math.isfinite(v)


def estimate(nodes, records, *, now, concurrency=3, complete=False, running=False):
    nodes={n['id']:n for n in nodes if not n.get('planned') and n.get('status')!='disabled'}
    done={k for k in nodes if records.get(k,{}).get('status') in {'passed','disabled'}}
    remaining=set(nodes)-done
    result={'scope':'discovered_nodes','known_nodes':len(nodes),'completed_nodes':len(done),
            'remaining_nodes':len(remaining),'lower_seconds':None,'seconds':None,'upper_seconds':None,
            'finish_at':None,'concurrency':max(1,min(3,int(concurrency))), 'unknown_nodes':[],
            'notes':['按当前已发现DAG、同阶段成功节点耗时及并发模拟；不是按完成百分比外推。',
                     '后续发现的分片/用例、未来失败重试及人工等待不在估算内；历史区间不是统计置信区间。','并发按项目配置上限且最多3路估算；其他项目/管理Agent共享网关或限流会延长实际时间。']}
    if not remaining:
        result.update(status='complete' if complete else 'discovering',reason='本轮执行已完成' if complete else '当前节点已完成，等待发现后续节点',seconds=0 if complete else None,lower_seconds=0 if complete else None,upper_seconds=0 if complete else None)
        return result
    samples=defaultdict(list)
    for key,row in records.items():
        start,end=row.get('started_at'),row.get('finished_at')
        if row.get('status')=='passed' and _number(start) and _number(end) and end>start:
            samples[row.get('stage',nodes.get(key,{}).get('stage'))].append((end,end-start))
    durations={};late=[]
    def percentile(values,q):
        values=sorted(values);index=(len(values)-1)*q;lo=int(index);hi=min(lo+1,len(values)-1)
        return values[lo]+(values[hi]-values[lo])*(index-lo)
    for key in remaining:
        row=records.get(key,{});stage=nodes[key].get('stage')
        values=[v for _,v in sorted(samples.get(stage,[]))[-40:]]
        if not values:
            result['unknown_nodes'].append({'id':key,'stage':stage,'label':nodes[key].get('label') or LABELS.get(stage,stage)})
            continue
        age=max(0,now-row['started_at']) if row.get('status')=='running' and _number(row.get('started_at')) else 0
        if age>max(values):late.append(key)
        # A late active task has unknown remaining work, not a negative duration.
        durations[key]=[max(0.,percentile(values,q)-age) if not age else max(percentile(values,q)-age,percentile(values,q)*.2) for q in (.2,.5,.8)]
    result['sample_count']=sum(len(v) for v in samples.values());result['late_nodes']=late
    blockers=[{'id':k,'status':records.get(k,{}).get('status')} for k in remaining if records.get(k,{}).get('status') in {'awaiting_review','awaiting_answer','awaiting_configuration','awaiting_context','failed','rejected','budget_exhausted','interrupted'}]
    result['blockers']=blockers
    if result['unknown_nodes']:
        result.update(status='insufficient',reason=f"{len(result['unknown_nodes'])}个节点阶段缺少成功耗时样本",known_work_seconds=round(sum(d[1] for d in durations.values()),1))
        return result
    if any(d not in nodes for k in remaining for d in nodes[k].get('deps',[])):
        return {**result,'status':'insufficient','reason':'存在当前DAG以外的依赖，不能推算完成时间'}
    def schedule(column):
        waiting=set(remaining);finished={k:0. for k in done};busy=[];clock=0.
        capacity=result['concurrency']
        while waiting or busy:
            ready=sorted((k for k in waiting if all(d in finished for d in nodes[k].get('deps',[]))),key=lambda k:(records.get(k,{}).get('status')!='running',k))
            for key in ready[:max(0,capacity-len(busy))]:
                waiting.remove(key);heapq.heappush(busy,(clock+durations[key][column],key))
            if not busy:raise ValueError('DAG包含循环依赖')
            clock=busy[0][0]
            while busy and busy[0][0]<=clock:
                at,key=heapq.heappop(busy);finished[key]=at
        return clock
    try:low,mid,high=[round(schedule(i),1) for i in range(3)]
    except ValueError:
        return {**result,'status':'insufficient','reason':'依赖循环，无法推算完成时间'}
    status='blocked' if blockers else 'estimated' if running else 'paused'
    result.update(status=status,reason='等待人工/技术问题处理，墙钟完成时间未知' if blockers else '基于当前DAG的自动执行净时间' if running else '当前未运行；显示恢复后的预计自动执行净时间',
                  lower_seconds=low,seconds=mid,upper_seconds=high,finish_at=now+mid if status=='estimated' else None,
                  confidence='low' if late or any(len(samples[nodes[k].get('stage')])<3 for k in remaining) else 'medium')
    return result


def snapshot(project,config,*,now=None,job=None):
    project=Path(project);root=project/'run';now=time.time() if now is None else now
    load=lambda name,default:read_json(root/name) if (root/name).exists() else default
    nodes=load('workflow_graph.json',{'nodes':[]}).get('nodes',[])
    records=load('workflow_tasks.json',{'tasks':{}}).get('tasks',{})
    manifest=load('run_manifest.json',{});job=job or (read_json(project/'job.json') if (project/'job.json').exists() else {})
    running=job.get('status')=='running' and job.get('worker_heartbeat',job.get('started_at',0))>=now-30
    policy=validate(config.get('resilience',{}));live=[];events=[]
    dbfile=root/'execution_events.sqlite3'
    metadata={n['id']:n for n in nodes}
    active=[k for k,r in records.items() if k in metadata and r.get('status')=='running'] if running else []
    if dbfile.exists():
        with sqlite3.connect(dbfile.as_uri()+'?mode=ro',uri=True,timeout=10) as db:
            for key in active:
                row=db.execute("SELECT id,at,payload FROM events WHERE task_key=? AND kind='request_started' ORDER BY id DESC LIMIT 1",(key,)).fetchone()
                if not row:continue
                seq,started,raw=row;data=json.loads(raw)['data'];call_id=data.get('model_call_id')
                terminal=db.execute("SELECT 1 FROM events WHERE task_key=? AND id>? AND kind IN ('request_finished','request_failed') LIMIT 1",(key,seq)).fetchone()
                if terminal:continue  # Local validation/tool work is not model generation.
                sample=db.execute("SELECT at,payload FROM events WHERE task_key=? AND id>? AND kind='throughput_sample' ORDER BY id DESC LIMIT 1",(key,seq)).fetchone()
                values=json.loads(sample[1])['data'] if sample else {};at=sample[0] if sample else None
                fresh=at is not None and now-at<=15
                byte_count=values.get('output_bytes');rate=values.get('tokens_per_second_estimate') if fresh and byte_count else None
                last_output_age=(values.get('last_output_age_seconds') or 0)+max(0,now-at) if at else max(0,now-started)
                status='no_measurable_output' if not byte_count else 'stale' if not fresh else 'low' if _number(rate) and rate<policy['min_tokens_per_second'] else 'streaming'
                live.append({'node':key,'label':metadata[key].get('label') or LABELS.get(metadata[key]['stage'],metadata[key]['stage']),
                             'model_call_id':call_id,'requested_model':data.get('requested_model'),'account_id':data.get('account_id'),
                             'started_at':started,'sample_at':at,'status':status,'tokens_per_second_estimate':rate,
                             'last_observed_rate':values.get('tokens_per_second_estimate'),'output_bytes':byte_count,
                             'last_output_age_seconds':round(last_output_age,1),'elapsed_seconds':round(max(0,now-started),1),
                             'threshold':policy['min_tokens_per_second'],'auto_switch':policy['enabled'],
                             'content_bytes':values.get('content_bytes'),'tool_argument_bytes':values.get('tool_argument_bytes'),'reasoning_bytes':values.get('reasoning_bytes')})
            for seq,raw in db.execute("SELECT id,payload FROM events WHERE kind IN ('model_switched','model_degraded','model_switch_skipped','rate_limit_wait') ORDER BY id DESC LIMIT 10"):
                event=json.loads(raw);d=event['data']
                events.append({'id':seq,'at':event['at'],'node':event.get('task_key'),'kind':event['kind'],**{k:d[k] for k in ('requested_model','previous_model','failure_category','reason','retry_at','retry_after_seconds') if k in d}})
    limits=load('concurrency_status.json',{})
    configured=config.get('max_concurrency',1)
    concurrency=min(configured,limits.get('effective_max',configured)) if running or limits.get('configured_max')==configured else configured
    eta=estimate(nodes,records,now=now,concurrency=concurrency,complete=bool(manifest.get('execution_complete',manifest.get('complete'))),running=running)
    if running and any(r['status'] in {'stale','no_measurable_output'} and r['elapsed_seconds']>policy['grace_seconds'] for r in live):
        eta['notes'].append('有请求尚无可测速率或采样已过期，完成时间估算可靠性降低。');eta['confidence']='low'
    sessions=load('execution_sessions.json',[])
    return {'effective_concurrency':max(1,min(3,concurrency)),'session_started_at':sessions[-1].get('started_at') if sessions else job.get('started_at'),'generated_at':now,'running':running,'requests':live,'measurable_tokens_per_second_estimate':round(sum(r['tokens_per_second_estimate'] for r in live if _number(r['tokens_per_second_estimate'])),3) if live and all(_number(r['tokens_per_second_estimate']) for r in live) else None,
            'policy':policy,'switch_events':events,'estimate':eta,'measurement':'UTF-8字节/4的窗口估算（包含网关公开的推理内容），不是供应商计费Token；不可测内容显示未知。'}
