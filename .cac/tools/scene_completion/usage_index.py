"""Incremental request accounting; never scan packets on the summary path."""
from pathlib import Path
import csv, io, json, sqlite3, time
from .usage_audit import summarize_requests

def indexed_usage(root, *, view='summary', task_key=None, role=None, model=None,
                  case=None, search='', offset=0, limit=50, after=None, prices=None, session_id=None, account=None, sort='tokens'):
    if sort not in {'tokens','seconds','longest','recent'}:raise ValueError('invalid usage sort')
    if view not in {'summary','tasks','requests','export'}:raise ValueError('invalid usage view')
    if offset<0 or not 1<=limit<=200:raise ValueError('invalid usage pagination')
    root=Path(root);source=root/'execution_events.sqlite3'
    if not source.exists():return {'totals':{},'items':[],'count':0,'revision':0}
    # Derived index is rebuildable and separate from the immutable audit events.
    with sqlite3.connect(root/'usage_index.sqlite3',timeout=30) as cache:
        cache.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)')
        cache.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT)')
        cursor=int((cache.execute("SELECT value FROM meta WHERE key='cursor'").fetchone() or ['0'])[0])
        with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as db:
            rows=db.execute("SELECT id,payload FROM events WHERE id>? AND kind IN ('request_started','request_finished','request_failed') ORDER BY id",(cursor,)).fetchall()
        if rows:
            # Keep only the small request event projection; no model text/tool deltas.
            for seq,raw in rows:
                event=json.loads(raw);d=event['data'];key=d.get('model_call_id')
                if not key:
                    if event['kind']=='request_started':key=str(seq)
                    else:key=(cache.execute('SELECT id FROM requests WHERE json_extract(payload,\'$.task_key\')=? ORDER BY rowid DESC LIMIT 1',(event.get('task_key'),)).fetchone() or [None])[0]
                if key is None:continue
                old=cache.execute('SELECT payload FROM requests WHERE id=?',(key,)).fetchone()
                events=json.loads(old[0]) if old else []
                events.append({**event,'id':seq,'data':{**event['data'],'model_call_id':key}})
                cache.execute('INSERT OR REPLACE INTO requests VALUES (?,?)',(key,json.dumps(events,ensure_ascii=False)))
            cursor=rows[-1][0]
            cache.execute("INSERT OR REPLACE INTO meta VALUES ('cursor',?)",(str(cursor),))
        events=[e for row in cache.execute('SELECT payload FROM requests ORDER BY rowid') for e in json.loads(row[0])]
    sessions=json.loads((root/'execution_sessions.json').read_text()) if (root/'execution_sessions.json').exists() else []
    if session_id:
        session=next((s for s in sessions if s['id']==session_id),None)
        if session is None:raise ValueError('unknown execution session')
        starts={e['data'].get('model_call_id') for e in events if e['kind']=='request_started' and session['started_at']<=e['at']<=(session['finished_at'] or time.time())}
        events=[e for e in events if e['data'].get('model_call_id') in starts]
    if after is not None:
        starts={e['data'].get('model_call_id') for e in events if e['kind']=='request_started' and e['at']>=after}
        events=[e for e in events if e['data'].get('model_call_id') in starts]
    report=summarize_requests(events)
    statefile=root/'workflow_tasks.json';graphfile=root/'workflow_graph.json'
    states=json.loads(statefile.read_text()).get('tasks',{}) if statefile.exists() else {}
    nodes=json.loads(graphfile.read_text()).get('nodes',[]) if graphfile.exists() else []
    from .execution_graph import LABELS
    from .deepagents_client import role_for
    metadata={key:{'id':key,'stage':r.get('stage'),'case':r.get('case'),'role':role_for(r.get('stage','')),'label':LABELS.get(r.get('stage'),r.get('stage'))} for key,r in states.items()}
    metadata.update({n['id']:n for n in nodes})
    for key,t in report['tasks'].items():
        n=metadata.get(key,{});t.update(label=n.get('label') or LABELS.get(n.get('stage'),key),
            stage=n.get('stage'),case=n.get('case'),role=n.get('role'),status=states.get(key,{}).get('status','historical'))
    request_rows=report['requests']
    for row in request_rows:
        n=metadata.get(row['task_key'],{});row.update(label=n.get('label') or row['task_key'],stage=n.get('stage'),role=row.get('role') or n.get('role'),case=row.get('case') or n.get('case'))
        price=(prices or {}).get(row['model']);u=row.get('usage') or {}
        row.update(estimated_cost=None,cost_status='未知：未提供实际扣费或估算单价')
        if price and u:
            cached=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0)
            row['estimated_cost']=((u.get('prompt_tokens',0)-cached)*price['input']+cached*price.get('cached_input',price['input'])+u.get('completion_tokens',0)*price['output'])/1_000_000
            row['cost_status']='估算，未扣除免费额度；不是实际账单'
    def accepts(row):
        n=metadata.get(row.get('task_key'),{});models=row.get('models',[row.get('model')])
        return (not account or row.get('account')==account) and (not task_key or row.get('task_key')==task_key) and (not role or row.get('role',n.get('role'))==role) and (not model or model in models) and (not case or row.get('case',n.get('case'))==case) and (not search or search.casefold() in json.dumps(row,ensure_ascii=False).casefold())
    requests=[r for r in request_rows if accepts(r)]
    # Filters, including model, must apply to requests before totals aggregation.
    selected_ids={r['id'] for r in requests}
    selected_events=[e for e in events if (e['data'].get('model_call_id') or str(e['id'])) in selected_ids]
    filtered=summarize_requests(selected_events)
    tasks=list(filtered['tasks'].values())
    request_stats={}
    for r in requests:
        bucket=request_stats.setdefault(r['task_key'],{'costs':[],'accounts':{},'max_seconds':0,'max_input':None,'max_total':None,'sent':0,'failed':0,'repair':0,'unknown_attempt':0})
        if r['estimated_cost'] is not None:bucket['costs'].append(r['estimated_cost'])
        bucket['accounts'][r.get('account','历史未标注账号')]=None
        if r['status']!='not_sent':
            bucket['max_seconds']=max(bucket['max_seconds'],r['seconds']);bucket['sent']+=1
            bucket['failed']+=r['status']=='failed';bucket['repair']+=bool(r.get('attempt') and r['attempt']>1);bucket['unknown_attempt']+=r.get('attempt') is None
            for field,target in [('prompt_tokens','max_input'),('total_tokens','max_total')]:
                value=(r.get('usage') or {}).get(field)
                if isinstance(value,int):bucket[target]=max(bucket[target] or 0,value)
    for t in tasks:
        n=metadata.get(t['task_key'],{});t.update(label=n.get('label') or LABELS.get(n.get('stage'),t['task_key']),stage=n.get('stage'),case=n.get('case'),role=n.get('role'),status=states.get(t['task_key'],{}).get('status','historical'))
        bucket=request_stats[t['task_key']];costs=bucket['costs']
        t.update(max_request_seconds=bucket['max_seconds'],max_input_tokens=bucket['max_input'],max_total_tokens=bucket['max_total'],sent_calls=bucket['sent'],failed_calls=bucket['failed'],repair_calls=bucket['repair'],unknown_attempt_calls=bucket['unknown_attempt'])
        t['accounts']=list(bucket['accounts'])
        t.update(estimated_cost=sum(costs) if costs else None,actual_cost=None,cost_status='估算，非实际账单' if costs else '未知：未配置单价或用量未知')
    keys=('calls','completed_calls','not_sent_calls','unknown_usage_calls','in_flight_calls','input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','reported_total_tokens','request_seconds')
    totals={k:sum(t.get(k,0) for t in filtered['tasks'].values()) for k in keys}
    estimates=[r['estimated_cost'] for r in requests if r['estimated_cost'] is not None]
    totals.update(actual_cost=None,estimated_cost=sum(estimates) if estimates else None,cost_status='部分估算' if estimates and len(estimates)<sum(bool(r.get('usage')) for r in requests) else '估算' if estimates else '未知')
    groups={}
    for dimension in ('account','role','model','case','stage'):
        parts={}
        for r in requests:
            name=r.get(dimension) or metadata.get(r['task_key'],{}).get(dimension) or '未分类'
            p=parts.setdefault(name,{'name':name,'requests':0,'tokens':0,'seconds':0,'input_tokens':0,'output_tokens':0,'reasoning_tokens':0})
            p['requests']+=r['status']!='not_sent';p['tokens']+=(r.get('usage') or {}).get('total_tokens',0);p['seconds']+=r['seconds'] if r['status']!='not_sent' else 0
            u=r.get('usage') or {};p['input_tokens']+=u.get('prompt_tokens',0);p['output_tokens']+=u.get('completion_tokens',0);p['reasoning_tokens']+=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0)
        groups[dimension]=list(parts.values())
    def score(row):
        if sort=='recent':return row.get('started_at',0)
        if sort=='seconds':return row.get('request_seconds',row.get('seconds',0))
        if sort=='longest':return row.get('max_request_seconds',row.get('seconds',0))
        return row.get('reported_total_tokens',(row.get('usage') or {}).get('total_tokens',0))
    items=sorted(requests if view=='requests' else tasks,key=lambda r:(-score(r),r.get('task_key','')))
    # Rank the entire filtered task set before pagination, never just the displayed page.
    rank_fields=('task_key','label','case','role','stage','status','calls','not_sent_calls','input_tokens','output_tokens','reasoning_tokens','reported_total_tokens','request_seconds','max_request_seconds','max_input_tokens','max_total_tokens','sent_calls','failed_calls','repair_calls','unknown_attempt_calls','unknown_usage_calls','models','accounts')
    ranking=lambda field:[{k:t.get(k) for k in rank_fields} for t in sorted(tasks,key=lambda t:(-t.get(field,0),t['task_key']))[:5]]
    rankings={'tokens':ranking('reported_total_tokens'),'seconds':ranking('request_seconds')}

    result={'rankings':rankings,'sort':sort,'task_count':len(tasks),'totals':totals,'groups':groups,'sessions':sessions,'prices':prices or {},'revision':cursor,'generated_at':time.time(),
            'count':len(items),'offset':offset,'limit':limit,'items':items[offset:offset+limit] if view in {'tasks','requests'} else [],
            'notes':['输出已包含思考；缓存输入是输入子集。','累计请求耗时不是并行运行墙钟时间。','失败无usage为未知，不记为0；预留额度不是扣费。']}
    with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as db:
        sql="SELECT COUNT(*) FROM events WHERE kind='result_reused'";args=[]
        if session_id:sql+=' AND at>=? AND at<=?';args=[session['started_at'],session['finished_at'] or time.time()]
        elif after is not None:sql+=' AND at>=?';args=[after]
        if task_key:sql+=' AND task_key=?';args.append(task_key)
        result['reuse_events']=db.execute(sql,args).fetchone()[0]
    result['reuse_note']='复用事件次数，不是扣费请求数；复用产物的原始历史成本仍可在历史累计中查看'
    if view=='export':result.update(tasks=tasks,requests=requests)
    return result

def usage_csv(report):
    out=io.StringIO();cols=['task_key','label','role','case','models','calls','not_sent_calls','input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','reported_total_tokens','unknown_usage_calls','sent_calls','failed_calls','repair_calls','max_input_tokens','max_total_tokens','max_request_seconds','request_seconds','estimated_cost','actual_cost','cost_status']
    w=csv.DictWriter(out,fieldnames=cols,extrasaction='ignore');w.writeheader()
    for row in report['tasks']:w.writerow(row)
    return '\ufeff'+out.getvalue()
